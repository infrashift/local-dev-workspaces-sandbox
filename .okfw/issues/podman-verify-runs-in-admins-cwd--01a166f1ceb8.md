---
id: "01a166f1-ceb8-7948-ad9a-b9a6f0ff77ce"
title: "podman verify runs in admin's cwd"
type: "issue"
kind: "issue"
tags:
  - "issue"
  - "podman"
  - "guest-roles"
created: "2026-10-22T23:08:05-05:00"
timestamp: "2026-10-22T23:08:05-05:00"
description: "The podman role's rootless verification ran `podman info` as dev from admin's working directory and failed with 'cannot chdir to /home/admin'."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "new code (podman role, this change)"
  found: "2026-10-22, KVM test VM, first real python-stack apply"
---

# podman verify runs in admin's cwd

**Severity high, P1, fixed.** The role stops every python-stack apply in rootless mode, but only at its
final verification: the configuration itself was applied.

## What happens
`Run podman info as dev` runs `runuser -u dev -- env HOME=... XDG_RUNTIME_DIR=... podman info`. runuser
keeps the caller's working directory, which is admin's home (the system-lane play connects as admin and
becomes root). dev cannot enter `/home/admin` (mode 0700), so podman exits 125 with
`cannot chdir to /home/admin: Permission denied`.

## Fix
Run the probe with `chdir:` set to the rootless user's home.

## Acceptance
- python-stack applies past the podman verification.
- The assert reports rootless mode, overlay storage, a uid map above 65536 and the user's API socket.

## Verified
2026-10-23, KVM test VM: the python-stack apply passed the podman verification (`podman 5.8.9 rootless (overlay, network netavark), API at /run/user/1001/podman/podman.sock`).

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
