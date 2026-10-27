---
id: "01a17e52-1736-7915-ba91-d7f19feb14ed"
title: "Baseline guest tests were never ported from the aarch64 Mac lab"
type: "issue"
tags:
  - "issue"
  - "pytest"
  - "guest-tests"
  - "porting"
created: "2026-10-27T12:04:31-05:00"
timestamp: "2026-10-27T12:04:31-05:00"
description: "tests/guest/baseline/test_os.py and test_vm.py still expected aarch64, a short hostname, a non-root cloud-init status and the Mac lab's vm-ctl.sh and bootpd leases, so six baseline tests failed on the first provisioned Linux lab."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (tests/guest/baseline, aarch64 port)"
  found: "2026-10-27, first lab-provision-verify.mk run"
---

# Baseline guest tests were never ported from the aarch64 Mac lab

# Baseline guest tests were never ported from the aarch64 Mac lab

**Severity medium, P2, fixed.** Pre-existing: the files were renamed into the x86_64 lab unchanged. The guest suite first ran there on 2026-10-27.

## What happens
- `test_is_fedora_44_aarch64` expected `aarch64`.
- `test_hostname_is_the_vm_name` compared `hostname` (`fedora-dev-1.local`: cloud-init gives a `.local` domain) with the VM name.
- `test_cloud_init_finished` ran `cloud-init status` as admin without sudo: `Permission denied: '/run/cloud-init/cloud.cfg'`.
- `test_vm.py` used `L.lab_machines` (`vm.env`, `vm-ctl.sh`, the bootpd lease database) and `L.homebrew_prefix`, which do not exist in the libvirt lab.

## Fix
The architecture comes from `PYTHON_PLATFORM`. The hostname test compares `hostname -s`. cloud-init's status is read with sudo, as `vm-baseline.yml` does. The VM state comes from `virsh domstate`, and the lease from the module's `vm-ip.sh`, compared with the reservation in `terraform.tfvars`. The drift check uses the `TF_VAR_*` values that `lab-config.mk` exports.

## Verified
2026-10-27: `make -f lab-provision-verify.mk` passed (43 passed, 8 skipped: no TLS-inspection chain).

## Related
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
