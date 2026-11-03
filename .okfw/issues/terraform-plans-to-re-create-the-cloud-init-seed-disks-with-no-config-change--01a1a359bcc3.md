---
id: "01a1a359-bcc3-7786-b083-8ce8d7b78ba0"
title: "Terraform plans to re-create the cloud-init seed disks with no config change"
type: "issue"
kind: "issue"
tags:
  - "issue"
  - "terraform"
  - "libvirt"
  - "drift"
created: "2026-11-03T15:38:49-06:00"
timestamp: "2026-11-03T15:38:49-06:00"
description: "After the lab sat shut off over a host restart, test_terraform_has_no_drift fails: the seed cloud-init disks are planned as created and their volumes replaced, with no Terraform or template change; cause suspected, not confirmed."
x:
  severity: "low"
  priority: "P3"
  state: "open"
  origin: "pre-existing (terraform/modules/libvirt-vm seed disks)"
  found: "2026-11-03, verifying the Day 2 operations change (lab-provision-verify.mk STACK=sandbox)"
---

# Terraform plans to re-create the cloud-init seed disks with no config change

**Severity low, P3, open.** Found 2026-11-03 while verifying the Day 2 operations change. The lab VMs
work; only the drift test fails.

## What happens
`make -f lab-provision-verify.mk STACK=sandbox`: 139 passed, 1 failed,
`tests/guest/baseline/test_vm.py::test_terraform_has_no_drift`:

```text
# module.vm.libvirt_cloudinit_disk.seed["fedora-dev-1"] will be created
# module.vm.libvirt_cloudinit_disk.seed["upstream-1"] will be created
# module.vm.libvirt_volume.seed[...] must be replaced   (create forces replacement)
# module.vm.libvirt_domain.this[...] will be updated in-place
# null_resource.run_ansible must be replaced            (triggers)
Plan: 5 to add, 2 to change, 3 to destroy.
```

The plan has two parts:
- **`null_resource.run_ansible`: expected.** Its triggers hash every Ansible file the lab applies (`terraform/ansible.tf`), so any change to a playbook, role or vars file shows here until the next `make -f lab-provision.mk apply`. The Day 2 change edited `vars/`, the playbooks and roles.
- **The seed disks: not caused by that change.** No Terraform file or cloud-init template changed. `libvirt_cloudinit_disk.seed` is planned as *created*, so Terraform no longer finds it.

## Suspected cause (analysis, unconfirmed)
The libvirt provider's cloud-init disk (dmacvicar/libvirt 0.9.x) may keep its rendered ISO in a
temporary path that a host restart clears. The pool's `<vm>-seed.iso` volumes still date from
2026-10-27. To confirm: compare `terraform state show 'module.vm.libvirt_cloudinit_disk.seed["fedora-dev-1"]'`
with the files on disk, before and after a host restart.

## Fix (open)
- If confirmed: decide whether the seed disk should be ignored once the VM exists (`lifecycle { ignore_changes }` on the seed volume, or `replace_triggered_by` only on content), so a restart is not drift.
- Meanwhile: `make -f lab-provision.mk apply` clears it, by re-creating the seed volumes and re-running the guest playbooks.

## Related
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
- [Operate the Sandbox (Day 2)](/runbooks/operate-the-sandbox-day-2--01a1a3594f4a.md)
