---
id: "01a1670c-fffb-740b-9369-492699322a80"
title: "SSH ControlPath can exceed the Unix socket path limit"
type: "issue"
tags:
  - "issue"
  - "ansible"
  - "ssh"
created: "2026-10-22T23:37:47-05:00"
timestamp: "2026-10-22T23:37:47-05:00"
description: "With connection reuse on, Ansible keeps each ControlMaster socket under $HOME/.ansible/cp/; a deeply nested HOME pushes that path past the 104/108-byte sun_path limit and every connection fails with 'unix_listener: path ... too long'."
x:
  severity: "low"
  priority: "P3"
  state: "mitigated"
  origin: "new code (ansible.cfg connection-reuse fix, this change)"
  found: "2026-10-22, KVM test bed whose HOME is a 66-character external-disk path"
---

# SSH ControlPath can exceed the Unix socket path limit

**Severity low, P3, mitigated.** Does not affect the lab Mac (the path is about 70 bytes there), only unusually long HOME paths.

## What happens
Ansible's socket is `<control_path_dir>/<40-hex hash>`, with `control_path_dir` defaulting to `~/.ansible/cp`. On the test bed that was 127 bytes. ssh refuses to listen on a path that long, so every task fails as "Data could not be sent to remote host" (or `wait_for_connection` times out).

## Mitigation
Not changed in `ansible.cfg`: moving the directory to a shared location such as `/tmp` trades a cosmetic limit for a predictable path other users could pre-create. If `HOME` is very long (CI runners), set `ANSIBLE_SSH_CONTROL_PATH_DIR` to a short private directory. The test bed does so.

## Related
- [Lab ansible.cfg disables SSH connection reuse](/issues/lab-ansible-cfg-disables-ssh-connection-reuse--01a1670ab854.md)
