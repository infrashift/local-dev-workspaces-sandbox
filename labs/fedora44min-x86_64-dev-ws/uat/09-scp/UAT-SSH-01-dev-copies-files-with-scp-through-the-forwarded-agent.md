---
id: UAT-SSH-01
title: The developer copies files to and from an SSH server with the forwarded sandbox agent
suite: 09-scp
stack: python-stack
features:
- SBX-SSH-01
- SBX-EGR-02
personas:
- operator
- dev
- admin
priority: P2
disruptive: false
automated:
- tests/guest/sandbox/test_scenarios.py::test_scp_reaches_the_target_with_the_forwarded_agent
- tests/gateway/test_ssh_agent.py::test_certificate_is_for_the_allow_files_ssh_users_and_still_valid
leaves: A new agent certificate, and upstream-1's host key in dev's ~/.ssh/known_hosts.
---

# UAT-SSH-01 The developer copies files to and from an SSH server with the forwarded sandbox agent

## Story

As the developer, I want to copy files to a server with scp, so that I can move build output where it
is needed. As the security officer, I want the sandbox to sign in with a short-lived certificate that
it can use but never read.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-gateway.mk allow-list \| grep 192.168.151.10`. | `192.168.151.10:22  ssh:scp-target  operator  scenario 4: scp to upstream-1`: the `ssh` entry of `ansible/vars/egress-allow.yml`. If it is missing, run `make -f lab-gateway.mk allow HOST=192.168.151.10:22 USER=scp-target REASON="scenario 4: scp to upstream-1"`. |
| 2 | operator | Run `make -f lab-gateway.mk agent-cert`. | The output ends with `valid from <now> to <now + 8 hours>`. |
| 3 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `ssh-add -l`. | Two lines for the key `ai-sandbox egress`: `(ED25519)` and `(ED25519-CERT)`. The agent on the host answers through the forwarded socket. |
| 4 | dev | Run `ssh-add -L \| ssh-keygen -L -f - \| grep -A1 -E 'Valid\|Principals'`. | The certificate is valid for 8 hours, for the principals of the file's `ssh` entries: `scp-target`. |
| 5 | dev | Run `echo uat > /tmp/uat-ssh-01.txt && scp /tmp/uat-ssh-01.txt scp-target@192.168.151.10:`. | On the first connection, ssh asks to accept upstream-1's host key. Type `yes`. The copy ends with no password prompt. |
| 6 | dev | Run `scp scp-target@192.168.151.10:uat-ssh-01.txt /tmp/uat-back.txt && cat /tmp/uat-back.txt`. | `uat`. |
| 7 | dev | Run `ssh scp-target@192.168.151.10 rm uat-ssh-01.txt; rm /tmp/uat-ssh-01.txt /tmp/uat-back.txt`. | The files are gone. Press `Ctrl-b d`. |
| 8 | admin | Run `make -f lab-provision.mk ssh ROLE=admin`. Run `ssh-add -l`. | `Could not open a connection to your authentication agent.` Only the dev session forwards the agent. |

## Evidence left behind

The new certificate in the host's sandbox agent, and upstream-1's host key in dev's
`~/.ssh/known_hosts`. The allow-list entry `192.168.151.10:22` is part of the committed file.

## Notes

The guest's ssh goes through the CONNECT tunnel (`ProxyCommand ncat --proxy 192.168.150.1:8080` in
`/etc/ssh/ssh_config.d/50-ai-sandbox-proxy.conf`), so each SSH target needs a `kind: ssh` entry in
`ansible/vars/egress-allow.yml`, with the login it uses (`user`). The ssh users of the file are the
certificate's principals: an entry with a new user makes `allow` re-run the gateway for Vault's SSH
role and the agent (`TAGS=vault,ssh_agent`), and a fresh certificate names it.

The certificate lasts 8 hours. After that, scp fails with `Permission denied (publickey)` until the
operator runs `make -f lab-gateway.mk agent-cert` again. The agent loses the key and the certificate
when the host restarts (UAT-LIFE-03).

The guest asks the agent to sign. It cannot read the key. See
[SSH Agent Forwarding](../../../../.okfw/concepts/ssh-agent-forwarding--01a17f01fd23.md).
