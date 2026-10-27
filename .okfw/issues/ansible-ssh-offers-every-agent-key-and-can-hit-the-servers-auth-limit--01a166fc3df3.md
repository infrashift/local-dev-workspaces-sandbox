---
id: "01a166fc-3df3-7442-bfc2-7987c53bd841"
title: "Ansible SSH offers every agent key and can hit the server's auth limit"
type: "issue"
tags:
  - "issue"
  - "ssh"
  - "ansible"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "Guest connections did not set IdentitiesOnly, so with several keys in ssh-agent sshd can reject the connection with 'Too many authentication failures' before the lab key is tried."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (group_vars ansible_ssh_common_args)"
  found: "2026-10-22, KVM test VM"
---

# Ansible SSH offers every agent key and can hit the server's auth limit

**Severity medium, P2, fixed.** It intermittently breaks every guest playbook on a workstation with a loaded agent.

## What happens
Ansible connects by IP with `ansible_ssh_common_args`, not through the lab's `~/.ssh/config.d` host entries (which do set `IdentitiesOnly yes`). ssh offers agent keys first. sshd's `MaxAuthTries` (6) can run out before the lab key is offered.

## Fix
`-o IdentitiesOnly=yes` in `inventory/group_vars/all/vars.yml`.

## Verified
2026-10-23: every playbook run against the KVM test VM connected from a workstation whose agent holds several keys.

## Related
- [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md)
