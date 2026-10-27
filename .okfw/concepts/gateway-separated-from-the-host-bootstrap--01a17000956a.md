---
id: "01a17000-956a-7340-b5c5-df04ac9fcb8b"
title: "Gateway Separated from the Host Bootstrap"
type: "concept"
tags:
  - "gateway"
  - "decision"
  - "makefiles"
  - "architecture"
created: "2026-10-24T17:20:48-05:00"
timestamp: "2026-10-24T17:20:48-05:00"
status: "draft"
description: "Why the zero-trust gateway is its own stage (lab-gateway.mk, lab-gateway-verify.mk, ansible/roles/gateway/) after the host bootstrap, and the boundary a later move to its own project would cut along."
---

# Gateway Separated from the Host Bootstrap

The zero-trust surrogate-credential gateway is its own stage, with its own makefiles, role lane,
scripts and test suite (decided 2026-10-24). It is no longer part of `lab-bootstrap.mk`.

```sh
make -f lab-bootstrap.mk all  ->  make -f lab-bootstrap-verify.mk     # the host
make -f lab-gateway.mk        ->  make -f lab-gateway-verify.mk       # the gateway
make -f lab-provision.mk apply  ->  make -f lab-provision-verify.mk   # the VMs
```

## Why

- **The gateway runs on a verified host.** It is installed only after the host bootstrap has
  passed its own checks, so a host fault shows up in `tests/host`, not halfway through a Vault or
  Envoy install.
- **It may become its own project.** Everything the gateway owns lives in a known set of paths. A
  later move is a `git filter-repo` over that set, plus copies of the few shared files below. Nothing
  is extracted yet.

The order is documented, not enforced: `lab-gateway.mk` refuses to start without the venv, the
collections and the become vault, but it does not
run the host suite itself (decided with the operator). `lab-provision.mk`'s preflight does check
both stages, with `lab-bootstrap.mk check` and `lab-gateway.mk check`.

## The extraction boundary

Owned by the gateway:

| Path | Holds |
|---|---|
| `ansible/roles/gateway/` | `envoy_release`, `gateway_pki`, `vault_server`, `vault_gateway`, `vault_proxy`, `consul_server`, `consul_egress`, `envoy_gateway`, `sandbox_firewall`, `sandbox_ssh_agent` |
| `scripts/gateway/` | `egress-allowlist.sh` (the allow-list CLI), `sandbox-secret.sh` (loads the real credentials) |
| `labs/<lab>/ansible/playbooks/gateway-host.yml` | the gateway's pin block and role order |
| `labs/<lab>/ansible/vars/gateway.yml`, `egress-baseline.yml` | the gateway routes and surrogates, and the egress catalog |
| `labs/<lab>/ansible/inventory-host/host_vars/localhost/vars.yml`, `vault.yml` | the gateway's real credentials: their names, and (gitignored) their ansible-vault encrypted values ([Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)) |
| `labs/<lab>/lab-gateway.mk`, `lab-gateway-verify.mk` | install, check, secrets, agent-cert, allow list; the gateway suite |
| `labs/<lab>/tests/gateway/` | the gateway suite, with its helper `gateway_lab.py` |

Shared, so an extraction must copy them or depend on them:

- `ansible/roles/host/hashicorp_release`. Terraform (host) and Vault, Consul and consul-template
  (gateway) are all installed with it.
- `scripts/ansible-confirm.sh`, the dry-run-then-type-yes wrapper.
- `tests/lab.py` (paths from `PYTEST_ENV`, playbook readers) and the shared `.pytest/` venv that
  `lab-bootstrap-verify.mk` builds.
- The **gateway interface** section of `lab-config.mk`: `GATEWAY_IP`, `PROXY_PORT`, `GATEWAY_PORT`,
  `CA_TRUST_DIR`, `OPERATOR_DIR`, `SANDBOX_AGENT_SOCK`. The gateway also reads `SANDBOX_BRIDGE` (its
  firewall) and the upstream network (its MCP route).

Consumed by the lab, so they stay on the lab side of the boundary:

- `vars/gateway.yml`'s route hosts, which the guest playbooks put in `/etc/hosts` and `NO_PROXY`.
- `CA_TRUST_DIR`, which the `ca_trust` guest role installs.
- `SANDBOX_AGENT_SOCK`, which `lab_ssh` names as the dev alias's `IdentityAgent`. A missing socket does
  not break the dev login, so `lab_ssh` stays in the host bootstrap.

## Consequences

- `scripts/check-role-contract.sh` checks three lanes. The gateway lane uses the host contract bracket
  ([Role Contract](/concepts/role-contract--01a166e751ce.md)).
- `nftables` moved from `bootstrap-host.yml`'s package list into `sandbox_firewall`, so the bootstrap
  installs no gateway-only package.
- Every repair hint for the gateway names `make -f lab-gateway.mk …`. The deployed `vault-unseal`,
  `surrogate.lua` and `ai-sandbox-agent-cert` changed only in that text.

## Related
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)

## Source
- `PLAN-zero-trust-surrogate-secrets-inject-gw.md` (the gateway's design)
- `labs/fedora44min-x86_64-dev-ws/lab-gateway.mk`, `lab-gateway-verify.mk`, `lab-config.mk`
