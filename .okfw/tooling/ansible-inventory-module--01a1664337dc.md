---
id: "01a16643-37dc-73b2-ab67-195106e3dc4b"
title: "ansible-inventory Module"
type: "reference"
tags:
  - "terraform"
  - "modules"
  - "ansible"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "The host-agnostic module, copied verbatim from libvirt-qemu-kvm, that writes a role-grouped Ansible inventory from VM IPs."
---

# ansible-inventory Module

`terraform/modules/ansible-inventory/` was copied unchanged from libvirt-qemu-kvm, apart from
`terraform fmt` whitespace. It is pure `local_file`, so it runs on any host.

- Inputs: `host_vars` (the lab's `vms` map, which must carry `roles`), `host_ips` (name → IP from
  [qemu-hvf-vm Module](/tooling/qemu-hvf-vm-module--01a1664337d6.md)) and `inventory_path`.
- Output: a YAML inventory with one group per role, written to `terraform/output-data/terraform-hosts.yml`.
  The lab's `ansible.tf` re-runs the guest playbook whenever its hash changes.

Quirk carried over: the template always adds a `localhost` host with `ansible_connection: local`, and it
ignores the `ssh_user`/`ssh_key_path` inputs. Connection settings come from the lab's
`ansible/inventory/group_vars/all/vars.yml`.
