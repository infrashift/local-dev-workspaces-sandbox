locals {
  # locals inherited from main.tf: repo_root, lab_root

  # requirements.txt pins ansible-core and names the venv directory; the same
  # file drives lab-bootstrap.mk, so the two never drift.
  ansible_core_version   = regex("(?m)^ansible-core==([0-9.]+)", file("${local.repo_root}/requirements.txt"))[0]
  venv_bin               = "${local.repo_root}/.ansible-core-${local.ansible_core_version}/bin"
  ansible_artifacts_home = "${local.lab_root}/ansible"
  ansible_config         = "${local.ansible_artifacts_home}/ansible.cfg"
  playbook               = "${local.ansible_artifacts_home}/playbooks/site.yml"
  guest_roles            = "${local.repo_root}/ansible/roles/guest"
  ansible_inventory      = "${local.ansible_artifacts_home}/inventory"
  tf_inventory           = module.ansible_inventory.inventory_file

  # The gateway CA every sandbox guest trusts (ca_trust role); pathexpand so "~" works.
  ca_trust_dir = pathexpand(var.ca_trust_dir)
  # The optional TLS-inspecting proxy's chain every lab VM trusts.
  tls_inspection_dir = pathexpand(var.tls_inspection_dir)
}

# Execution trigger
resource "null_resource" "run_ansible" {
  triggers = {
    # Re-run if the inventory file content changes
    inventory_change = module.ansible_inventory.inventory_content_hash
    # Re-run if ANY file in the ansible directory changes
    # We scan for .yml, .yaml, .j2 (templates), and .cfg files recursively
    ansible_code_change = sha256(join("", [
      for f in fileset(local.ansible_artifacts_home, "**/*.{yml,yaml,j2,cfg}") :
      filemd5("${local.ansible_artifacts_home}/${f}")
    ]))
    # ...or any guest role the playbook applies (they live outside the lab)...
    guest_roles_change = sha256(join("", [
      for f in fileset(local.guest_roles, "**") : filemd5("${local.guest_roles}/${f}")
    ]))
    # ...or the gateway CA the guests trust (a re-issued CA)...
    ca_trust_change = sha256(join("", [
      for f in fileset(local.ca_trust_dir, "*.{pem,crt}") : filemd5("${local.ca_trust_dir}/${f}")
    ]))
    # ...or the TLS-inspection chain (added, rotated or removed)...
    tls_inspection_change = sha256(join("", [
      for f in fileset(local.tls_inspection_dir, "*.{pem,crt}") : filemd5("${local.tls_inspection_dir}/${f}")
    ]))
    # ...or the lab values (gateway address, ports).
    lab_vars_change = sha256(var.lab_vars)
  }

  provisioner "local-exec" {
    environment = {
      # Tell Ansible where the config file is so it finds the role paths
      ANSIBLE_CONFIG = local.ansible_config
    }
    command = <<EOT
      "${local.venv_bin}/ansible-playbook" \
        --inventory "${local.ansible_inventory}" --inventory "${local.tf_inventory}" \
        --extra-vars '${var.lab_vars}' \
        "${local.playbook}"
    EOT
  }

  # Explicit dependency: Do not start until the Ansible inventory file is generated
  depends_on = [module.ansible_inventory]
}
