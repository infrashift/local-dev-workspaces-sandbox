---
id: UAT-ISO-01
title: The sandbox has no route and no DNS to the internet, and its only way out is the gateway
suite: 08-egress
stack: python-stack
features:
- SBX-ISO-01
personas:
- dev
- admin
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_isolation.py::test_nothing_is_reachable_directly
- tests/guest/sandbox/test_isolation.py::test_gateway_host_resolves_to_the_gateway
- tests/guest/sandbox/test_isolation.py::test_gateway_refuses_a_machine_beside_the_sandbox
leaves: Nothing. The scenario only sends requests that fail.
---

# UAT-ISO-01 The sandbox has no route and no DNS to the internet, and its only way out is the gateway

## Story

As the security officer, I want the sandbox to have no way out except the gateway, so that a program
that ignores the proxy settings still cannot reach the internet.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `curl -sS --noproxy '*' --max-time 5 -o /dev/null https://1.1.1.1/`. | `curl: (7) Failed to connect to 1.1.1.1 port 443 … Could not connect to server`. |
| 2 | dev | Run `getent hosts example.com; echo $?`. | `2`. The sandbox has no DNS. |
| 3 | dev | Run `getent hosts github.com api.anthropic.com`. | Each line starts with `192.168.150.1`, the gateway. `/etc/hosts` maps every gateway host there. |
| 4 | dev | Run `ip route`. | One line: `192.168.150.0/24 dev enp1s0 …`. There is no default route. |
| 5 | admin | Connect with `make -f lab-provision.mk ssh ROLE=admin`. Run `sudo curl -sS --noproxy '*' --max-time 5 -o /dev/null https://1.1.1.1/`. | It fails as in step 1. root on the VM has no way out either. Close the session. |
| 6 | admin | Connect with `make -f lab-provision.mk ssh ROLE=admin VM=upstream-1`. Run `timeout 5 bash -c 'exec 3<>/dev/tcp/192.168.150.1/8080'; echo $?`. | `No route to host`, then `1`. A machine beside the sandbox cannot reach the gateway. Close the session. |

## Evidence left behind

None.

## Notes

The sandbox network is an isolated libvirt network with no forward and no DNS. The host's firewall
(`ai-sandbox-firewall`) lets the sandbox reach only the gateway's two ports. See
[Isolated Sandbox Network](../../../../.okfw/concepts/isolated-sandbox-network--01a17e9c824e.md).
