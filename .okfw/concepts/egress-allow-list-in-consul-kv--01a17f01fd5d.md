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
description: "The CONNECT tunnel's allow list: baseline/ (Ansible, from the catalog) and allow/ (the operator's committed egress-allow.yml, synced with the operator token) in Consul K/V, rendered by consul-template into Envoy's file-based RDS route table with rules that never let a bad key widen it."
---

# Egress Allow List in Consul KV

What the sandbox may reach through Envoy's CONNECT tunnel, kept in Consul K/V and applied live.

## Layout
Under `ai-sandbox/egress/` in Consul:

| Key | Owner | Written by |
|---|---|---|
| `baseline/<category>/<host>:<port>` | Ansible | `consul_egress` seeds the enabled categories of the [Egress Baseline Catalog](/concepts/egress-baseline-catalog--01a17f01fd6d.md) and prunes what the catalog no longer names |
| `allow/<host>:<port>` | the operator | synced from `labs/<lab>/ansible/vars/egress-allow.yml` by `scripts/gateway/egress-allowlist.sh` (`allow`, `deny`, `allow-sync`) |

Values are JSON. Baseline: `{reason, category, source}`. Operator:
`{kind, reason, added, expires?, user?, source: "file"}`. The operator's Consul token writes `allow/`
only, and reads `baseline/`.

## The operator's file (since 2026-11-03)
`allow/` used to exist only in Consul: an entry had no history, no review, and did not survive a
rebuild. It now has a committed source, `vars/egress-allow.yml` (decided 2026-11-03, with the operator),
one flow-mapping line per entry:

```yaml
- { kind: ssh, host: "192.168.151.10", port: 22, user: scp-target, reason: "scenario 4: scp to upstream-1", added: 2026-10-27 }
```

- **Kinds.** `https` (port 443 unless set; the only kind that may be a `*.<suffix>` wildcard), `tcp`
  (port required, not 22 or 443), and `ssh` (port 22 unless set, `user` required). To the tunnel they
  are all the same `host:port` key. The kind is metadata for review, and `ssh` users feed the agent
  certificate's principals ([SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md)).
- **Rules.** `scripts/gateway/egress_allow.py`:
  - checks the host pattern and the port range;
  - refuses a gateway host, a subdomain of one, or a wildcard covering one;
  - refuses duplicates;
  - requires a reason without `"` or `\`, and ISO dates;
  - warns when the catalog already holds the entry.
- **Expiry.** An entry whose `expires` date has come is left out of the desired set. The next `allow-sync`,
  or `allow`/`deny` of that entry, deletes its key. Nothing runs on a timer.
- **Reconcile.**
  - `allow-plan` prints `+`/`~`/`-` against Consul and exits 2 on drift.
  - `allow-sync` applies the plan after a typed `yes` (`ANSIBLE_CONFIRM=yes` answers it). It **prunes** keys the file does not name, so a key written by hand is drift, as in [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md).
  - `allow` and `deny` edit one line and apply only that key, then say if other drift is pending.
  - `make -f lab-gateway.mk check` fails on drift.
- **Why not Ansible.** The sync stays with the operator token and the wrapper, not `consul_egress`. It applies in seconds, with least privilege, and Ansible keeps owning `baseline/` alone.

Clients: a `tcp` entry helps only a client that speaks HTTP CONNECT, or one wrapped in
`ncat --proxy <gateway>:<port> --proxy-type http`; the guest's ssh already is (`ProxyCommand ncat`).
Day-to-day use: [Operate the Sandbox (Day 2)](/runbooks/operate-the-sandbox-day-2--01a1a3594f4a.md).

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
- `tests/gateway/test_allowlist.py`: also that every line of `egress-allow.yml` keeps the rules, and that Consul's `allow/` equals the file minus expired entries.
- `tests/guest/sandbox`: an entry added and removed end to end, through the guest.
- Live, 2026-11-03: allow (with an expiry) and deny of an https, a tcp and an ssh entry; refusals of `github.com:443` and of a missing port; a hand-written key reported as drift and pruned by `allow-sync`; an expiry rehearsed with `EGRESS_TODAY`; the file byte-identical afterwards.

## Related
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
- [Operate the Sandbox (Day 2)](/runbooks/operate-the-sandbox-day-2--01a1a3594f4a.md)
- [The allow target accepts a gateway host](/issues/the-allow-target-accepts-a-gateway-host--01a17f2f9819.md) (fixed by the file's rules)
