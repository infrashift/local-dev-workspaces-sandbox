---
id: "01a1a359-4f4a-75df-a063-b113e226a194"
title: "Operate the Sandbox (Day 2)"
type: "runbook"
tags:
  - "runbook"
  - "operator"
  - "gateway"
  - "egress"
  - "credentials"
created: "2026-11-03T15:38:21-06:00"
timestamp: "2026-11-03T15:38:35-06:00"
description: "Day 2 through lab-sandbox-ops.mk: up/status/ssh, the committed allow file (https, tcp, ssh, expiring entries) and the secrets registry, review with denied and audit, and what is left to the operator."
status: "draft"
---

# Operate the Sandbox (Day 2)

The recurring work once the lab is built and verified
([Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)). Run
every command from `labs/fedora44min-x86_64-dev-ws`.

`lab-sandbox-ops.mk` is the single entry point. It holds no logic: each target runs the one in
`lab-gateway.mk`, `lab-provision.mk` or a verify suite, which stay the owners. The gateway keeps its
own lane ([Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)).
`make -f lab-sandbox-ops.mk` lists the targets by section, and variables (`HOST=`, `NAME=`, `VM=`, …)
pass through.

## The operator's two files
Both are committed. The targets edit them, so commit after a change: the history is the review trail.

| File | Holds | Concept |
|---|---|---|
| `ansible/vars/egress-allow.yml` | the operator allow list: `https`, `tcp` and `ssh` entries, each with a reason, optionally an `expires` date | [Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md) |
| `ansible/vars/gateway-secrets.yml` | the registry of real credentials: names, kinds, repositories, dates; never a value | [Gateway Secrets Registry](/concepts/gateway-secrets-registry--01a1a358cacd.md) |

## Start of day, or after a host restart
```sh
make -f lab-sandbox-ops.mk up       # gateway services active? start the VMs, renew the agent certificate, status
make -f lab-sandbox-ops.mk ssh      # the dev session; renews the agent certificate when under 1 h is left
```
`status` alone gives one screen:
- the VMs;
- every gateway unit;
- the agent certificate's principals and time left;
- whether Consul's allow list matches the file;
- the secrets check, with expiry warnings.

## Egress
| Task | Command |
|---|---|
| Allow a site | `allow HOST=example.com:443 REASON="why" [EXPIRES=YYYY-MM-DD]` |
| Allow a TCP service | `allow HOST=db.example.com:5432 REASON="why"` (kind `tcp` from the port) |
| Allow an SSH target | `allow HOST=git.example.com:22 USER=git REASON="why"` |
| Remove one | `deny HOST=<host:port>` |
| Review | `allow-list` (kind, source, drift or expiry, reason); `denied [SINCE=24h]` for what the tunnel refused |
| After editing the file by hand, or a `git pull` | `allow-plan`, then `allow-sync` (typed `yes`) |

How the targets behave:
- `allow` refuses a gateway host, or a subdomain of one, and an entry without a port.
- A new SSH user re-runs the gateway for `TAGS=vault,ssh_agent`, so the certificate names it ([SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md)).
- A `tcp` entry only helps a client that speaks HTTP CONNECT, or one wrapped in `ncat --proxy <gateway>:8080 --proxy-type http`.
- Expired entries leave Consul at the next `allow-sync`; nothing runs on a timer.

## Credentials
| Task | Command |
|---|---|
| What is held, loaded, rotated, expiring | `secrets-list` |
| Rotate (before expiry, or at once after a leak) | `secret-rotate NAME=<name> [EXPIRES=…]`, then revoke the old PAT on GitHub |
| A new repository | `secret-add NAME=<name> KIND=github-pat REPO=<owner/name>`, paste the printed surrogates into `vars/gateway.yml`, then `gateway` and `play PLAYBOOK=python-stack` |
| Retire one | remove its surrogates, then `secret-remove NAME=<name>` |
| Consistency | `secrets-check` |
| Read a real value (an emergency) | `break-glass REASON="why"`; review afterwards with `audit [SINCE=7d]` (sudo: the audit log is root-only) |

## Verify after a change
`make -f lab-sandbox-ops.mk verify [STACK=sandbox]` runs the gateway suite, then the guest suite.
`lint` runs every linter.

## Not automated (advice)
- **Backups.** `.ansible_vault_key`, `become.vault.yml` and `vault.yml` are the only state that cannot be rebuilt. A backup that holds the key alongside the vault files is plaintext in effect, so keep it offline and separate.
- **Version bumps.** The pins in `gateway-host.yml` and the lock files: bump, `gateway` / `apply`, then `verify`.
- **Automatic certificate renewal.** `ssh` and `up` renew on demand; a user timer would cover a session longer than 8 hours.

## Related
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
