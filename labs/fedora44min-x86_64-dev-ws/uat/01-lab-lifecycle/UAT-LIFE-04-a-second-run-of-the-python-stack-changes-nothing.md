---
id: UAT-LIFE-04
title: A second run of the python-stack playbook finds nothing to change
suite: 01-lab-lifecycle
stack: python-stack
features:
- SBX-LIFE-03
personas:
- operator
priority: P2
disruptive: false
automated: none
leaves: Nothing. The playbook runs as a dry run only.
---

# UAT-LIFE-04 A second run of the python-stack playbook finds nothing to change

## Story

As the operator, I want a second run of the stack to change nothing, so that I can run it again at
any time to repair drift, and a real change shows up clearly in the dry run.

## Preconditions

1. UAT-LIFE-01 passes.
2. No one changed the playbooks, the roles or the vars files since the last apply.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-provision.mk play PLAYBOOK=python-stack`. | The output starts with `=== Dry run (--check --diff): nothing is changed ===`. |
| 2 | operator | Read the PLAY RECAP at the end of the dry run. | Each host has `changed=0` and `failed=0`. |
| 3 | operator | Read the last line. | `=== Nothing to change. ===`. There is no `Enter a value:` prompt, and the command ends. |

## Evidence left behind

None.

## Notes

If the dry run shows changes, the command lists them under `=== Pending changes ===` and asks for
`yes`. Type `no`: the command prints `Apply cancelled.` and changes nothing. Then the test fails.
Record the task names that it listed.

A task that only reads the guest must report `ok`, not `changed`. A `changed` on a read-only task is a
role defect (see [Role Contract](../../../../.okfw/concepts/role-contract--01a166e751ce.md)).
