---
id: UAT-EGR-04
title: The operator allows a site until a date, and the next sync removes it after that date
suite: 08-egress
stack: python-stack
features:
- SBX-EGR-02
personas:
- operator
- dev
priority: P3
disruptive: false
automated:
- tests/gateway/test_allowlist.py::test_operator_allow_list_in_consul_is_exactly_the_file
leaves: Nothing, if step 7 is done.
---

# UAT-EGR-04 The operator allows a site until a date, and the next sync removes it after that date

## Story

As the operator, I want to allow a site for a short task only, so that a temporary need does not
leave a standing hole in the allow list.

## Preconditions

1. UAT-EGR-02 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-gateway.mk allow HOST=example.com:443 REASON="UAT-EGR-04" EXPIRES=<tomorrow, YYYY-MM-DD>`. | `Allowed example.com:443 ...`. |
| 2 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `curl -sS -o /dev/null -w '%{http_code}\n' https://example.com/`. | `200`. |
| 3 | operator | Run `make -f lab-gateway.mk allow-list \| grep example.com`. | `example.com:443  https  operator  until <tomorrow>  UAT-EGR-04`. |
| 4 | operator | Rehearse the day after: run `EGRESS_TODAY=<the day after tomorrow> make -f lab-gateway.mk allow-plan`. | `- example.com:443  (expired)`, and exit status 2. |
| 5 | operator | Run `EGRESS_TODAY=<the day after tomorrow> make -f lab-gateway.mk allow-sync`. Type `yes`. | `1 change(s) written to Consul`. |
| 6 | dev | Within 10 seconds, do step 2 again. | `CONNECT tunnel failed, response 403`. |
| 7 | operator | Run `make -f lab-gateway.mk deny HOST=example.com:443`. | `egress-allow.yml: removed example.com:443`. The file is as it was. |

## Evidence left behind

None.

## Notes

An expired entry stays in `ansible/vars/egress-allow.yml` until someone removes its line, and
`allow-list` marks it `expired`. Consul drops it at the next `allow-sync`, or at the next `allow` or
`deny` of that entry; nothing runs on a timer. `make -f lab-sandbox-ops.mk status` reports the allow
list out of step while an expired entry is still in Consul. `EGRESS_TODAY` only exists to rehearse
an expiry; leave it unset in normal use.
