"""From the host: each VM is running and has its DHCP reservation, and Terraform's state matches the configuration."""

import re

import lab
from lab import PROVISION

L = lab.lab()


def test_vm_is_running(host, vm):
    result = host.run("virsh -c %s domstate %s", L.libvirt_uri, vm)
    assert result.rc == 0 and result.stdout.strip() == "running", (
        f"{vm} is {result.stdout.strip() or 'unknown'}: run {PROVISION} start VM={vm}"
    )


def test_vm_has_its_dhcp_reservation(host, vm, spec):
    """vm-ip.sh reads libvirt's lease, as lab-provision.mk status and the ssh ProxyCommand do."""
    result = host.run("%s %s %s", str(L.vm_scripts / "vm-ip.sh"), vm, L.libvirt_uri)
    assert result.rc == 0, f"{vm} has no DHCP lease: run {PROVISION} restart VM={vm}"
    assert result.stdout.strip() == spec["ip"], (
        f"{vm} leased {result.stdout.strip()}, terraform.tfvars reserves {spec['ip']}: run {PROVISION} restart VM={vm}"
    )


def test_terraform_has_no_drift():
    """No pending changes: the VMs, the inventory and the last vm-baseline run match the configuration.

    terraform/ansible.tf re-runs vm-baseline when a file under ansible/, a
    guest role or the CA chain changes, so an edit not yet applied fails here.
    """
    result = lab.run(
        [str(L.terraform), f"-chdir={L.tf_dir}", "plan", "-detailed-exitcode", "-input=false", "-no-color"],
        # lab-config.mk exports the TF_VAR_* values to Make's children, pytest included.
        env_extra={"CHECKPOINT_DISABLE": "1"},
        timeout=600,
    )
    pending = [line.strip() for line in result.stdout.splitlines() if re.match(r"\s*(# .* will be|Plan:)", line)]
    assert result.returncode != 2, f"Terraform has pending changes: {pending}: run {PROVISION} apply"
    assert result.returncode == 0, f"terraform plan failed: {result.stderr.strip()}"
