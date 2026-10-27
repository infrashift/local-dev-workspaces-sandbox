---
id: "01a17f01-fd4c-7b4f-b005-0339b6bee308"
title: "Zero-Trust Surrogate Gateway"
type: "concept"
tags:
  - "gateway"
  - "architecture"
  - "envoy"
  - "vault"
  - "consul"
  - "pki"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:16:39-05:00"
status: "draft"
description: "Overview of the host gateway that gives the sandbox VM what it needs without a real credential: the isolated network, Envoy's tunnel and TLS gateway, Vault/Vault Proxy/Consul, the agent, the operator's tools, and the name-constrained gateway CA."
---

# Zero-Trust Surrogate Gateway

The gateway on the Linux host that lets the sandbox VM, whose AI agent is assumed compromised, reach
what it needs without ever holding a real credential (`lab-gateway.mk`, `ansible/roles/gateway/`).
This is the overview; each part has its own concept.

| Part | What it does | Concept |
|---|---|---|
| The sandbox network | the guest reaches Envoy's two listeners and nothing else; neighbours reach neither | [Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md) |
| Envoy's CONNECT tunnel (`PROXY_PORT`) | raw TLS tunnels to the allow list only, for pip, dnf, npm and scp | [Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md), [Egress Baseline Catalog](/concepts/egress-baseline-catalog--01a17f01fd6d.md) |
| Envoy's TLS gateway (`GATEWAY_PORT`) | terminates TLS for the gateway hosts with the gateway CA's certificate, swaps surrogate for real credentials, re-originates verified TLS | [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md) |
| Vault, Vault Proxy, Consul | the real credentials, Envoy's only way to them, and the allow list, all on unix sockets | [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md) |
| The sandbox ssh-agent | scp without a key in the guest | [SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md) |
| The operator's tools | make targets for changes, read-only CLIs, break-glass | [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md) |

## The gateway CA
`gateway_pki` issues it. It is ECDSA P-384, `pathlen:0`, with key usage `keyCertSign` and `cRLSign`;
the key is root-only in `/etc/ai-sandbox/pki`. Every guest trusts it (`CA_TRUST_DIR` → `ca_trust`),
so its key is the most powerful secret the guests rely on. Since 2026-10-27 it carries **critical
name constraints**: it may vouch for the gateway hosts of `vars/gateway.yml`, nothing else. It
excludes every IPv4 and IPv6 address, and Envoy's certificate has no IP SAN. The guests reach the
gateway by name. A permitted IP subtree made Claude Code's runtime (Bun) refuse the chain
([issue](/issues/claude-code-refuses-the-gateway-cas-name-constraints--01a17f21b808.md)). A leaked key
could not impersonate any other site to a guest.
- Adding a gateway host changes the permitted set. `gateway_pki` re-issues the CA with the same key
  and subject, so Envoy's certificate keeps verifying. The guests then need the new CA:
  `make -f lab-provision.mk apply`, because Terraform re-runs vm-baseline when `CA_TRUST_DIR`
  changes. Adding a gateway host needs a guest re-provision anyway (`/etc/hosts`, `NO_PROXY`).
- The upstream-test CA, which Envoy alone trusts for the lab's own upstreams, is constrained to
  those upstream names the same way.
- `tests/gateway/test_pki.py::test_gateway_ca_may_vouch_for_the_gateway_only` checks the exported
  CA.

## History
- Designed for a macOS host (pf, Homebrew, a `/tmp` socket), then built on Linux.
  `PLAN-zero-trust-surrogate-secrets-inject-gw.md` (renamed from `…-credential-inject-gw.md` on
  2026-10-27) now records the Linux design, phase by phase, with a table of the changes from the
  macOS plan; the macOS version is in the Git history.
- Hardened 2026-10-27 (the threat model in
  [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)):
  - the gateway refuses neighbours ([issue](/issues/the-gateway-answered-machines-beside-the-sandbox-weak-host-model--01a17e9cd3ae.md));
  - Envoy's admin API is a socket ([issue](/issues/envoys-admin-api-could-log-the-injected-credentials--01a17e9cd3b8.md));
  - Vault and Consul are on unix sockets;
  - Vault is audited, and the operator token reads no real credential ([issue](/issues/the-operator-token-could-read-the-real-credentials--01a17ecc92f3.md));
  - paths are normalized and requests rate-limited;
  - consul-template is a separate user, and every unit is sandboxed;
  - the CAs are name-constrained.

## Related
- [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- `labs/fedora44min-x86_64-dev-ws/security-controls.md`: the controls at a high level, for developers, the operator and reviewers
