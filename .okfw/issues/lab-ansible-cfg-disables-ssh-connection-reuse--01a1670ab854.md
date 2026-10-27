---
id: "01a1670a-b854-7bd5-a58d-38079a9a102d"
title: "Lab ansible.cfg disables SSH connection reuse"
type: "issue"
tags:
  - "issue"
  - "ansible"
  - "ssh"
  - "performance"
created: "2026-10-22T23:35:18-05:00"
timestamp: "2026-10-22T23:35:18-05:00"
description: "The lab's ansible.cfg sets ssh_args without ControlMaster/ControlPersist, which replaces Ansible's defaults; with pipelining off, every task opened several fresh SSH connections."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (labs/*/ansible/ansible.cfg)"
  found: "2026-10-22, KVM test VM: about 3 s per SSH connect, minutes per lazyvim task"
---

# Lab ansible.cfg disables SSH connection reuse

**Severity medium, P2, fixed.** Guest playbooks ran many times slower than they need to; nothing was incorrect.

## What happens
`[ssh_connection] ssh_args = -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no` *replaces* Ansible's default `-C -o ControlMaster=auto -o ControlPersist=60s` rather than adding to it. Without a control master, and with `pipelining` off, each task costs 3-4 full SSH connections (mkdir temp, put module, run, clean up), each with key exchange and authentication. On the test VM one connect took about 3 s, so a role like lazyvim spent most of its time connecting.

## Fix
Keep Ansible's multiplexing in `ssh_args` (`-C -o ControlMaster=auto -o ControlPersist=60s`), and set `pipelining = True`. Pipelining is safe here: Fedora's and EL's sudoers have no `requiretty`, and the user lane needs no become.

## Acceptance
- An idempotent re-run of python-stack is markedly faster.
- No change in results.

## Verified
2026-10-23, KVM test VM: before the fix the lazyvim role alone spent about a minute per task and the run was abandoned after more than an hour; with it, the full first python-stack apply took 827 s, and a converged re-run took 358 s.

## Related
- [Lab fedora44min-aarch64-dev-ws](/labs/lab-fedora44min-aarch64-dev-ws--01a1664337f7.md)
