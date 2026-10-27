---
id: UAT-EGR-01
title: A site that is not on the allow list is refused at the tunnel
suite: 08-egress
stack: python-stack
features:
- SBX-EGR-01
personas:
- dev
- operator
priority: P1
disruptive: false
automated:
- tests/gateway/test_allowlist.py::test_everything_else_is_denied
- tests/guest/sandbox/test_isolation.py::test_tunnel_refuses_a_gateway_host
leaves: Nothing. The scenario only sends refused requests.
---

# UAT-EGR-01 A site that is not on the allow list is refused at the tunnel

## Story

As the security officer, I want the sandbox to reach only the sites that someone approved, so that
an agent cannot send code or data to a site of its choice.

## Preconditions

1. UAT-LIFE-01 passes.
2. `example.com:443` is not on the allow list (`make -f lab-gateway.mk allowlist | grep example.com`
   prints nothing).

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `curl -sS -o /dev/null https://example.com/`. | `curl: (56) CONNECT tunnel failed, response 403`. |
| 2 | dev | Run `curl -sS -x http://192.168.150.1:8080 -o /dev/null -w '%{http_code}\n' http://example.com/`. | `404`. The tunnel serves CONNECT only, so plain HTTP through the proxy goes nowhere. |
| 3 | dev | Run `python3 -m pip download --no-deps --dest /tmp/uat-egr six --index-url https://example.com/simple --retries 0`. | `ERROR: No matching distribution found for six`. pip cannot reach the index. Then run `rm -rf /tmp/uat-egr`. |
| 4 | dev | Run `curl -sS --noproxy '' --proxy http://192.168.150.1:8080 -o /dev/null https://github.com/`. | `CONNECT tunnel failed, response 403`. A gateway host is never reachable through the tunnel, where the gateway could not swap the surrogate. |
| 5 | operator | On the host, run `journalctl -u envoy --since '-5 min' \| grep 'tunnel.*example.com'`. | A `tunnel 192.168.150.10 CONNECT example.com:443 403 …` line for each refused attempt. |

## Evidence left behind

None.

## Notes

The tunnel's answer to a refused site is `ai-sandbox egress: not on the allow list`. curl does not
show the body of a refused CONNECT. Use `curl -v` to see it.

The sandbox has no other way out. UAT-ISO-01 shows that a request around the proxy fails too.
