---
id: UAT-EGR-02
title: The operator allows a site with a reason, the developer reaches it at once, and the operator removes it again
suite: 08-egress
stack: python-stack
features:
- SBX-EGR-01
- SBX-EGR-02
personas:
- dev
- operator
priority: P1
disruptive: false
automated: none
leaves: Nothing, if step 6 is done.
---

# UAT-EGR-02 The operator allows a site with a reason, the developer reaches it at once, and the operator removes it again

## Story

As the developer, I want the operator to allow a site I need within a minute, so that a missing
entry blocks me for minutes and not for days. As the operator, I want each entry to carry its reason,
so that I can review the list later.

## Preconditions

1. UAT-EGR-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `curl -sS -o /dev/null -w '%{http_code}\n' https://example.com/`. | `CONNECT tunnel failed, response 403`. |
| 2 | operator | Run `make -f lab-gateway.mk allow HOST=example.com:443 REASON="UAT-EGR-02: docs for the developer"`. | `Allowed example.com:443 (Envoy picks it up within seconds)`. |
| 3 | dev | Within 10 seconds, do step 1 again. | `200`. No restart of anything. |
| 4 | operator | Run `make -f lab-gateway.mk allowlist \| grep example.com`. | `example.com:443  operator  UAT-EGR-02: docs for the developer`. |
| 5 | operator | Run `make -f lab-gateway.mk allow HOST=example.com REASON=x`. | `Not <host>:<port> or *.<suffix>:<port>: example.com`. The entry is refused: it needs a port. |
| 6 | operator | Run `make -f lab-gateway.mk deny HOST=example.com:443`. | `Removed example.com:443`. |
| 7 | dev | Within 10 seconds, do step 1 again. | `CONNECT tunnel failed, response 403`. |
| 8 | operator | Run `make -f lab-gateway.mk deny HOST=pypi.org:443`. | `pypi.org:443 is not on the operator allow list (baseline entries are removed from the catalog)`. The operator cannot remove a baseline entry. |
| 9 | operator | Run `make -f lab-gateway.mk allow HOST=github.com:443 REASON="UAT-EGR-02"`. | The command refuses: github.com is a gateway host. **Known gap:** see Notes. |

## Evidence left behind

None.

## Notes

Step 9 fails now: the command prints `Allowed github.com:443`. The tunnel still refuses github.com
(UAT-EGR-01, step 4), so the sandbox gets no tunnel past the gateway. But the
[Operator Interfaces](../../../../.okfw/concepts/operator-interfaces--01a17ebdba31.md) page says that
the make target refuses a gateway host, and it does not. Remove the entry with `make -f
lab-gateway.mk deny HOST=github.com:443`. See the issue
[The allow target accepts a gateway host](../../../../.okfw/issues/the-allow-target-accepts-a-gateway-host--01a17f2f9819.md).

The entry is a key under `ai-sandbox/egress/allow/` in Consul. consul-template writes Envoy's route
table again when the key changes. See
[Egress Allow List in Consul KV](../../../../.okfw/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md).
