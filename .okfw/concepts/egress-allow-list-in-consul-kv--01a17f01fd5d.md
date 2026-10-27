---
id: "01a17f01-fd5d-7196-9acc-ba247743ae3f"
title: "Egress Allow List in Consul KV"
type: "concept"
tags:
  - "gateway"
  - "egress"
  - "consul"
  - "envoy"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:16:39-05:00"
status: "draft"
description: "The CONNECT tunnel's allow list: baseline/ (Ansible, from the catalog) and allow/ (the operator) in Consul K/V, rendered by consul-template into Envoy's file-based RDS route table with rules that never let a bad key widen it."
---

# Egress Allow List in Consul KV

What the sandbox may reach through Envoy's CONNECT tunnel, kept in Consul K/V and applied live.

## Layout
Under `ai-sandbox/egress/` in Consul:

| Key | Owner | Written by |
|---|---|---|
| `baseline/<category>/<host>:<port>` | Ansible | `consul_egress` seeds the enabled categories of the [Egress Baseline Catalog](/concepts/egress-baseline-catalog--01a17f01fd6d.md) and prunes what the catalog no longer names |
| `allow/<host>:<port>` | the operator | `make -f lab-gateway.mk allow HOST=… REASON=…` / `deny HOST=…` (`scripts/gateway/egress-allowlist.sh`) |

Values are JSON: `{reason, added, source}`. The operator's Consul token writes `allow/` only, and
reads `baseline/`.

## From Consul to Envoy
consul-template runs as its own user, with a read-only token, over Consul's unix socket
([Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)). It renders
`connect-routes.ctmpl` into `/var/lib/envoy/rds/connect.yaml`, which Envoy watches (file-based RDS),
so an edit applies in seconds with no restart. The template's rules mean a bad key can never break
or widen the table:
- a key that is not `<host>:<port>` or `*.<suffix>:<port>`, lower case, is skipped;
- duplicates collapse (Envoy rejects repeated domains);
- a gateway host is never tunnelled. Its exact names are skipped, and an exact deny for every
  allowed port outranks any wildcard that would cover it. A tunnel to a gateway host would bypass
  the surrogate swap.
- everything else falls through to `*`: 403 "not on the allow list". The route table is CONNECT-only.

Before consul-template's first render, Envoy loads `connect-routes.empty.yaml`, which denies all.

## Checked by
- `tests/gateway/test_allowlist.py`:
  - Consul's baseline equals the enabled catalog;
  - Envoy's table equals baseline ∪ allow minus the gateway hosts;
  - gateway hosts are denied on every port, `*` is last, and no RDS update was rejected.
- `tests/guest/sandbox`: an entry added and removed end to end, through the guest.

## Related
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
