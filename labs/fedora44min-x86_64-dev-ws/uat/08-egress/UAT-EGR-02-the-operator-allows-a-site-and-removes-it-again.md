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
automated:
- tests/gateway/test_allowlist.py::test_operator_allow_list_in_consul_is_exactly_the_file
- tests/gateway/test_allowlist.py::test_allow_file_keeps_every_rule
leaves: Nothing, if step 7 is done.
---

# UAT-EGR-02 The operator allows a site with a reason, the developer reaches it at once, and the operator removes it again

## Story

As the developer, I want the operator to allow a site I need within a minute, so that a missing
entry blocks me for minutes and not for days. As the operator, I want each entry to carry its reason,
and to live in a committed file, so that the list can be reviewed and rebuilt.

## Preconditions

1. UAT-EGR-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `curl -sS -o /dev/null -w '%{http_code}\n' https://example.com/`. | `CONNECT tunnel failed, response 403`. |
| 2 | operator | Run `make -f lab-gateway.mk allow HOST=example.com:443 REASON="UAT-EGR-02: docs for the developer"`. | `egress-allow.yml: added example.com:443 (https)`, then `Allowed example.com:443 (Envoy picks it up within seconds)`. |
| 3 | dev | Within 10 seconds, do step 1 again. | `200`. No restart of anything. |
| 4 | operator | Run `make -f lab-gateway.mk allow-list \| grep example.com`. | `example.com:443  https  operator  UAT-EGR-02: docs for the developer`. |
| 5 | operator | Run `git diff ansible/vars/egress-allow.yml`. | One added line: `{ kind: https, host: "example.com", port: 443, reason: "UAT-EGR-02: docs for the developer", added: <today> }`. |
| 6 | operator | Run `make -f lab-gateway.mk allow HOST=example.com REASON=x`. | `Not <host>:<port> or *.<suffix>:<port>: example.com`. The entry is refused: it needs a port (or `PORT=`). |
| 7 | operator | Run `make -f lab-gateway.mk deny HOST=example.com:443`. | `egress-allow.yml: removed example.com:443`, then `Removed example.com:443`. `git diff ansible/vars/egress-allow.yml` shows nothing. |
| 8 | dev | Within 10 seconds, do step 1 again. | `CONNECT tunnel failed, response 403`. |
| 9 | operator | Run `make -f lab-gateway.mk deny HOST=pypi.org:443`. | `pypi.org:443 is not on the operator allow list (a baseline entry: remove it from egress-baseline.yml)`. The operator cannot remove a baseline entry. |
| 10 | operator | Run `make -f lab-gateway.mk allow HOST=github.com:443 REASON="UAT-EGR-02"`. | `github.com:443: github.com is, or is under, the gateway host github.com. ...`. Nothing is written to the file or to Consul. |
| 11 | operator | Run `make -f lab-gateway.mk allow HOST=foo.codeload.github.com:443 REASON="UAT-EGR-02"`. | Refused the same way: a subdomain of a gateway host would skip the tunnel (NO_PROXY). |

## Evidence left behind

None.

## Notes

The file `ansible/vars/egress-allow.yml` is the source of the operator entries; `allow` and `deny` edit
it and then write the one key to Consul under `ai-sandbox/egress/allow/`. consul-template writes Envoy's
route table again when the key changes. Commit the file after a change: its history is the review
trail. See [Egress Allow List in Consul KV](../../../../.okfw/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md).

Step 10 used to write the entry (the issue
[The allow target accepts a gateway host](../../../../.okfw/issues/the-allow-target-accepts-a-gateway-host--01a17f2f9819.md),
fixed). The tunnel's route table refuses gateway hosts too, so the check is belt and braces.
