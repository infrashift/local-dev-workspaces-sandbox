---
id: "01a16725-2342-7310-83b5-04c3e249a061"
title: "Dry run hides changes made by command tasks"
type: "issue"
tags:
  - "issue"
  - "check-mode"
  - "guest-roles"
  - "ansible-confirm"
created: "2026-10-23T00:04:09-05:00"
timestamp: "2026-10-23T00:04:09-05:00"
description: "A state-changing command task without creates: is skipped in check mode and reported as skipped, not changed, so the dry run can say 'Nothing to change' while the real run would change something."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "new code (podman role); audited across all roles"
  found: "2026-10-23, KVM test VM: podman.socket disabled, dry run reported changed=0"
---

# Dry run hides changes made by command tasks

**Severity high, P1, fixed.** ansible-confirm.sh trusts the dry run's changed count, so a hidden change is never applied: the operator is told there is nothing to do.

## What happens
`ansible.builtin.command` does not support check mode: unless it has `creates:`/`removes:`, Ansible skips it in a dry run and reports it as *skipped*. The podman role's `Enable and start the rootless user's podman.socket` is such a task. With the socket disabled, `--check` reported `changed=0`. `ansible-confirm.sh` then printed "Nothing to change" and exited, so the socket was never re-enabled unless the playbook was run without the wrapper.

The [Role Contract](/concepts/role-contract--01a166e751ce.md) already requires a "Would …" debug (`changed_when: true`) beside install blocks. This task, and any like it, must follow the same rule.

## Fix
- Pair every state-changing `command` that lacks `creates:`/`removes:` with a check-mode "Would …" debug, and gate the command itself on `not ansible_check_mode`.
- Audit all roles. `scripts/check-role-contract.sh` gains a check: a `command`/`shell` task with `changed_when: true` must have `creates:`/`removes:`, run only outside check mode, or carry a reason.

## Acceptance
- With the socket disabled, the dry run reports the pending enable (`changed=1`), and the apply then converges.

## Verified
2026-10-23, KVM test VM: with dev's podman.socket disabled, the dry run reported 'Would enable and start the rootless user's podman.socket' (changed=1); the apply converged, and the next dry run reported changed=0. The checker flags the old ungated task in a scratch copy.

## Related
- [Role Contract](/concepts/role-contract--01a166e751ce.md), [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)
