---
id: "01a16643-37c7-7aac-9f76-5de04068e25a"
title: "socket_vmnet Networking"
type: "concept"
tags:
  - "networking"
  - "vmnet"
  - "socket_vmnet"
  - "macos"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "How lab VMs get host-reachable addresses through Apple vmnet via the socket_vmnet launchd daemon, and how their IPs are discovered."
status: "deprecated"
---

# socket_vmnet Networking

> **Deprecated.** This page describes the original Apple Silicon Mac port, which the Linux x86_64 host replaced. It is kept for history. The current host is Pop!_OS or Ubuntu 24.04 LTS: see [Platform Overview](/platform-overview--01a1664337bc.md).

Apple's vmnet framework needs root (or an entitlement Homebrew's QEMU lacks). **socket_vmnet** is a small
root launchd daemon that owns the vmnet interface and serves it on `/var/run/socket_vmnet`. QEMU stays
unprivileged: `socket_vmnet_client` connects to the socket and execs QEMU with the connection on fd 3
(`-netdev socket,id=net0,fd=3`).

- Shared mode, gateway `192.168.105.1`. Guests get `192.168.105.x` from **macOS bootpd**, have internet
  egress, and are reachable from the Mac. That last point is why the generated Ansible inventory can use
  plain `ansible_host: <ip>`.
- It is installed from the **upstream binary release** into root-owned `/opt/socket_vmnet`. Lima advises
  against the Homebrew formula, which leaves a root daemon in a user-writable prefix. The `socket_vmnet`
  role verifies the tarball against `SHA256SUMS`, and checks that it only contains `opt/socket_vmnet`
  before extracting it as root into `/`. It is the only privileged step in the bootstrap.

## IP discovery

There are no libvirt leases. `vm-ip.sh` reads `/var/db/dhcpd_leases` instead.

**Gotcha:** bootpd strips leading zeros from MAC octets: `52:54:00:0a:1b:02` is stored as
`hw_address=1,52:54:0:a:1b:2`. The script normalizes the MAC before matching, and the newest lease wins.
MACs are stable per VM (`random_id` keyed on the VM name), so stale leases are harmless.

## Related
- [QEMU HVF on Apple Silicon](/concepts/qemu-hvf-on-apple-silicon--01a1664337c1.md)
- [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md): the ProxyCommand resolves IPs the same way

## Source
- `ansible/roles/host/socket_vmnet/`
- `terraform/modules/qemu-hvf-vm/scripts/vm-ip.sh`
