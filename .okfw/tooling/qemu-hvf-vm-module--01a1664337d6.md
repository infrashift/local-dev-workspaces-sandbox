---
id: "01a16643-37d6-785f-a727-64741924d073"
title: "qemu-hvf-vm Module"
type: "reference"
tags:
  - "terraform"
  - "modules"
  - "qemu"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "The Terraform module that creates overlay disks, cloud-init seeds and QEMU/HVF processes, and reports each VM's IP."
status: "deprecated"
---

# qemu-hvf-vm Module

> **Deprecated.** This page describes the original Apple Silicon Mac port, which the Linux x86_64 host replaced. It is kept for history. The current host is Pop!_OS or Ubuntu 24.04 LTS: see [Platform Overview](/platform-overview--01a1664337bc.md).

`terraform/modules/qemu-hvf-vm/` turns a `vms` map into running QEMU guests. It uses only `terraform_data`,
`local_file`, `random_id` and `external`, with no provider for the hypervisor.

## Resources (per VM)
1. `random_id.mac`: a stable `52:54:00:xx:xx:xx`, keyed on the VM name.
2. `terraform_data.disk`: `qemu-img create -b <base>` overlay, the overlay ≥ base guard (adapted from
   libvirt-qemu-kvm's virt-install module) and the EFI vars copy. Its destroy step removes the whole VM
   directory, so the `local_file`s use `replace_triggered_by` on it.
3. `local_file` user-data, meta-data and network-config, then `terraform_data.seed`, which builds the ISO
   with `hdiutil makehybrid` (no genisoimage on macOS).
4. `local_file.vm_env` + `terraform_data.vm`: runs `vm-ctl.sh start`. Any change to the launch
   parameters, disk or seed replaces the VM. The destroy step sends a QMP `system_powerdown`, then
   SIGTERM after 60 s.
5. `terraform_data.wait_for_ip` + `data.external.vm_ips`: waits for the bootpd lease and SSH.

Outputs: `provisioned_vms` (name → IP, the same contract as libvirt-qemu-kvm's modules), `mac_addresses`
and `vm_dirs`.

## Scripts
- `vm-ctl.sh start|stop|status <vm_dir>`: also used by `lab-provision.mk`. QEMU is launched with
  `nohup … &` and every stdio stream redirected, so the socket_vmnet fd is inherited and local-exec
  does not hang.
- `vm-ip.sh lookup|json|wait <mac>`, `vm-proxy.sh`.

## Inputs worth knowing
- `users`: a list of `{name, ssh_key_path, sudo}`; at least one must have sudo.
- `cloud_init_packages`: the lab passes `[]`. A first-boot dnf install fails behind ZScaler; the dnf
  bindings are installed by Ansible after `ca_trust`, and the Fedora 44 image ships them anyway.

## Related
- [QEMU HVF on Apple Silicon](/concepts/qemu-hvf-on-apple-silicon--01a1664337c1.md), [Base Images and Machine Overlays](/concepts/base-images-and-machine-overlays--01a1664337cc.md),
  [ansible-inventory Module](/tooling/ansible-inventory-module--01a1664337dc.md)
