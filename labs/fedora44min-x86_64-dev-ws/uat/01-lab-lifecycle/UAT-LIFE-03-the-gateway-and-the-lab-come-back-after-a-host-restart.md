---
id: UAT-LIFE-03
title: After the host restarts, the gateway comes back by itself and the lab starts with one command
suite: 01-lab-lifecycle
stack: python-stack
features:
- SBX-LIFE-01
- SBX-LIFE-02
- SBX-PY-01
personas:
- operator
- dev
priority: P1
disruptive: true
automated: none
leaves: Nothing. The test restarts the host and reads the state.
---

# UAT-LIFE-03 After the host restarts, the gateway comes back by itself and the lab starts with one command

## Story

As the operator, I want the gateway to come back by itself after the host restarts, so that a kernel
update or a power cut does not need a gateway repair before the developer can work again.

## Preconditions

1. UAT-LIFE-02 passes.
2. No one else uses the host now. This test restarts it.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Restart the host (`sudo systemctl reboot`). Log in again. | The host is up. |
| 2 | operator | Run `systemctl is-active vault vault-proxy consul envoy ai-sandbox-consul-template ai-sandbox-firewall ai-sandbox-vault-unseal`, then `systemctl --user is-active ai-sandbox-ssh-agent`. | `active` eight times. |
| 3 | operator | Run `eval "$(make -s -f lab-gateway.mk cli)"`, then `vault status`. | `Sealed false`. The unseal service unsealed Vault at boot. |
| 4 | operator | Run `make -f lab-provision.mk status`. | Both VMs are `shut off`. libvirt autostart is off for the lab VMs. |
| 5 | operator | Run `make -f lab-provision.mk start`. | The command ends with no error. |
| 6 | operator | Run `make -f lab-gateway.mk agent-cert`. | The sandbox ssh-agent has a new certificate. The agent lost its key at the restart. |
| 7 | dev | Connect with `make -f lab-provision.mk ssh`. In the shell pane, run `python3 -m pip download --no-deps --dest /tmp/uat-life-03 six`. | pip downloads `six` through the CONNECT tunnel. |
| 8 | dev | Run `rm -r /tmp/uat-life-03`. Detach. | The directory is gone. |
| 9 | operator | Run `make -f lab-gateway-verify.mk`. | All the tests pass. |

## Evidence left behind

None.

## Notes

The test does not cover a restart while the VMs run under load. The VMs get an ACPI shutdown from
libvirt when the host stops.

If step 3 shows `Sealed true`, read `journalctl -u ai-sandbox-vault-unseal` for the cause.

Step 6 is in the test because SCP (UAT-SSH-01) needs the agent's certificate. The certificate is held
only in the agent's memory.
