---
id: "01a168e0-c882-757b-a473-aca26d72df12"
title: "A missing role parameter fails in success_msg, not the named fail_msg"
type: "issue"
tags:
  - "issue"
  - "role-contract"
  - "host-roles"
  - "guest-roles"
created: "2026-10-23T08:08:44-05:00"
timestamp: "2026-10-23T08:08:44-05:00"
description: "ansible-core 2.21 templates an assert's success_msg before evaluating it, so a parameter-bracket assert whose success_msg names an input fails with \"'x' is undefined\" instead of its fail_msg listing every parameter and its form."
x:
  severity: "low"
  priority: "P2"
  state: "fixed"
  origin: "new code (every role's parameter bracket, 2026-10-22 rewrite)"
  found: "2026-10-23, negative test of the new hashicorp_release role with hashicorp_release_key_fpr removed"
---

# A missing role parameter fails in success_msg, not the named fail_msg

**Severity low, P2, fixed.** The run still stops before doing any work and names the variable, but the message the contract promises (every parameter, its expected form, why there are no defaults) never appears.

## What happens
Every role that takes parameters (22 of 23) opens its parameter bracket with one `assert` that also sets `success_msg:` to a summary built from its inputs (`{{ release_binary_label }} -> {{ release_binary_dest }}`). ansible-core finalizes all task arguments before the module runs. When an input is missing, the task dies while templating `success_msg`:

```
Task failed: Finalization of task args for 'ansible.builtin.assert' failed:
Error while resolving value for 'success_msg': 'hashicorp_release_key_fpr' is undefined
```

The `fail_msg` is never shown. A malformed but *defined* input is unaffected: there the bracket fails with its full message, as tested.

## Fix
- The parameter-bracket assert keeps only `fail_msg` and goes `quiet: true`. The summary moves to a following `debug` task ("Show the requested parameters"), which runs only once every input is known to exist.
- `scripts/check-role-contract.sh` rejects a `success_msg:` inside the parameter-bracket assert.

## Acceptance
- Removing any one parameter fails with the bracket's `fail_msg` ("A required role parameter was not supplied ...").
- The checker flags a reintroduced `success_msg:` (negative-tested).

## Verified
2026-10-23: removing each of hashicorp_release's five parameters now fails with the bracket's fail_msg. All 22 roles were moved to a quiet assert plus a 'Show the requested parameters' debug task. The new checker rule passes on the tree and flags a reintroduced success_msg (negative-tested on a copy of release_binary). yamllint -s, ansible-lint (production profile) and the syntax check of all three playbooks pass. The guest roles were not re-run on a VM for this change: it is mechanical, and the test VM was torn down.

## Related
- [Role Contract](/concepts/role-contract--01a166e751ce.md)
