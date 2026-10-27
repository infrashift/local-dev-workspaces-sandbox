---
id: "01a16643-37d1-7694-bfa6-5eeeb09250d3"
title: "Lab SSH Identities"
type: "concept"
tags:
  - "ssh"
  - "identity"
  - "cloud-init"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "Per-lab admin and dev SSH key pairs and host configs, and the ProxyCommand that resolves a VM's DHCP address at connect time."
---

# Lab SSH Identities

Every lab has two guest users, created by cloud-init:

| Role | Guest user | Privileges | Used by |
|------|-----------|------------|---------|
| admin | `admin` | passwordless sudo (wheel) | Ansible, maintenance |
| dev | `dev` | none | day-to-day work |

The `lab_ssh` role creates, per lab:

- `~/.ssh/key.d/local.<lab>@admin` and `@dev`: ed25519 key pairs, never regenerated.
- `~/.ssh/config.d/local.<lab>@admin` and `@dev`: generated host configs.

If `~/.ssh/config` does not exist, it is created containing `Include config.d/*`. An existing config is
**never edited**: the role prints the line to add near the top, before any `Host` or `Match` block.

## Host aliases use `.`, not `@`

ssh splits `user@host` on the command line, so a Host alias containing `@` can never be matched. The
aliases are:

```
ssh local.fedora44min-aarch64-dev-ws.dev                    # the lab's only VM
ssh local.fedora44min-aarch64-dev-ws.admin.fedora-dev-1     # a specific VM
```

## Dynamic addresses

VM IPs come from DHCP and are unknown at bootstrap time, so each config uses
`ProxyCommand vm-proxy.sh <lab machines dir> %n %p`. It finds the VM's MAC in `vm.env`, looks up the
current lease, and `exec`s `nc`. Host keys change on every rebuild, so these hosts use
`UserKnownHostsFile /dev/null`.

`make -f lab-provision.mk ssh [ROLE=admin] [VM=...]` passes `-F` the generated file, so it works even
before the Include is added.

## Related
- [socket_vmnet Networking](/concepts/socket-vmnet-networking--01a1664337c7.md)
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)

## Source
- `ansible/roles/host/lab_ssh/`
- `terraform/modules/qemu-hvf-vm/scripts/vm-proxy.sh`
- `terraform/modules/qemu-hvf-vm/templates/user-data.tpl`
