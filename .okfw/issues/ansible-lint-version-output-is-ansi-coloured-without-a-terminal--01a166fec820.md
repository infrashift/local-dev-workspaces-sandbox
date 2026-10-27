---
id: "01a166fe-c820-73a4-a630-65248dad1dcb"
title: "ansible-lint --version output is ANSI-coloured without a terminal"
type: "issue"
tags:
  - "issue"
  - "ansible_tools"
  - "guest-roles"
  - "idempotency"
created: "2026-10-22T23:22:15-05:00"
timestamp: "2026-10-22T23:22:15-05:00"
description: "ansible-lint colours its --version output even when stdout is not a TTY, so the ansible_tools role's anchored version regex never matched: the final assert failed and every run would have reinstalled."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "new code (ansible_tools role, this change)"
  found: "2026-10-22, KVM test VM, first full python-stack apply"
---

# ansible-lint --version output is ANSI-coloured without a terminal

**Severity high, P1, fixed.** It failed python-stack at its last role, and would make ansible_tools report a change on every run.

## What happens
`ansible-lint --version` printed `ansible-lint \u001b[1;36m26.10.1\u001b[0m using ...` under Ansible's `command` module (no TTY). The pattern `(?m)^ansible-lint 26\.10\.1(\s|$)` cannot match through the escape codes. The same probe gates the install, so the tool was reinstalled on every run, and the final "requested version" assert failed.

## Fix
Set `NO_COLOR=1` in the role's environment (which ansible-lint's rich output honours), and as a defence strip ANSI sequences before matching, in all three uv-tool roles.

## Acceptance
- The python-stack apply completes, and a re-run reports `changed=0` for ansible_tools.

## Verified
2026-10-23, KVM test VM: the final assert passed (`ansible-lint 26.10.1 using ansible-core:2.21.5 ...`), and the next full apply reported no change in ansible_tools.

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
