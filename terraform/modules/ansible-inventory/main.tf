locals {
  unique_roles = distinct(flatten([
    # use lookup() instead of dot notation
    for host, data in var.host_vars : lookup(data, "roles", [])
  ]))
}

resource "local_file" "inventory" {
  # UPDATED: Pointing to hosts.yaml.tpl
  content = templatefile("${path.module}/templates/hosts.yml.tpl", {
    host_ips     = var.host_ips
    host_vars    = var.host_vars
    unique_roles = local.unique_roles
    ssh_user     = var.ssh_user
    ssh_key      = var.ssh_key_path
  })

  filename = var.inventory_path
}