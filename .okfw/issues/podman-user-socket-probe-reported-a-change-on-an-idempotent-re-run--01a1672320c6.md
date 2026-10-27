---
id: "01a16723-20c6-71ee-94d4-411ab3adfa20"
title: "podman user-socket probe reported a change on an idempotent re-run"
type: "issue"
tags:
  - "issue"
  - "podman"
  - "guest-roles"
  - "idempotency"
created: "2026-10-23T00:01:57-05:00"
timestamp: "2026-10-23T00:01:57-05:00"
description: "On the second full python-stack apply the podman role ran 'Enable and start the rootless user's podman.socket' although the socket was active and enabled; three isolated runs of the role were idempotent."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "new code (podman role, this change)"
  found: "2026-10-23, KVM test VM, idempotency run (changed=1)"
---

# podman user-socket probe reported a change on an idempotent re-run

**Severity medium, P2, fixed.** Re-runs are not reliably changed=0, which defeats the dry run's 'nothing to change' signal.

## What happens
The role probes `systemctl --user --machine dev@ is-active podman.socket` and `is-enabled` with `failed_when: false`, and enables the socket when either output differs. The user manager did not restart (`journalctl -u user@1001`), so the socket was up the whole time. The likely cause is a probe that *failed* (the bus call to the user manager) and was read as "not active": a failed probe and a stopped socket look the same to the role.

## Fix
- Read both states in one `systemctl --user --machine <user>@ show podman.socket -p ActiveState -p UnitFileState` call.
- **Assert the probe itself succeeded**, so a bus failure fails by name instead of turning into a change.
- Retry the probe a few times first, since the bus call can fail transiently.

## Acceptance
- Two consecutive full python-stack applies after a converged one report `changed=0`.

## Verified
2026-10-23, KVM test VM: two consecutive full python-stack applies after a converged one both reported changed=0 (201 s and 203 s).

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
