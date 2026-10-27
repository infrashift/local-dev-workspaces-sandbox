---
id: "01a17001-1e5c-7ad9-a01a-d6bda87f5bcb"
title: "Provision and Verify the Gateway"
type: "runbook"
tags:
  - "runbook"
  - "gateway"
  - "verification"
created: "2026-10-24T17:21:23-05:00"
timestamp: "2026-10-27T10:10:00-05:00"
status: "draft"
description: "Step-by-step: install the zero-trust gateway with lab-gateway.mk after the host checks pass, load the real credentials, run lab-gateway-verify.mk, and manage the allow list."
---

# Provision and Verify the Gateway

Install the zero-trust surrogate-credential gateway on the host, load the real credentials, and
verify it, after the host bootstrap passes its checks
([Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)).
Run every command from the lab directory, `labs/fedora44min-x86_64-dev-ws`.

## Before you start

- `make -f lab-bootstrap.mk all` is done, and `make -f lab-bootstrap-verify.mk` passes.
  `lab-gateway.mk` uses the venv, the collections and the become vault that the bootstrap made.
- For the GitHub scenarios: for **each** repository in `vars/gateway.yml` `github_repos`, a private
  repository holding at least one file, and a fine-grained PAT limited to it alone (Repository access:
  only that repository; permissions Contents and Metadata, read-only). The resource owner is the
  repository's organisation, which may have to approve the PAT.
- For the Claude scenario: an Anthropic API key.
- If the host is behind a TLS-inspecting proxy (Zscaler, ...), first do
  [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md).

## Procedure 1: Install the gateway

1. Run the gateway playbook. It does a dry run first:

   ```sh
   make -f lab-gateway.mk
   ```

2. Read the pending changes, then type `yes` to apply them. `ANSIBLE_CONFIRM=yes` answers for you,
   after it shows the dry run.
3. To work on some roles only, add `TAGS=`: `binaries`, `pki`, `vault`, `consul`, `envoy`,
   `firewall` or `ssh_agent`.
4. Check that a second run finds nothing to change:

   ```sh
   make -f lab-gateway.mk check     # ends with "Gateway is ready."
   ```

## Procedure 2: Load the real credentials (once, and to rotate)

The credentials live ansible-vault encrypted in the host inventory, and the gateway playbook loads them
into Vault ([Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)).

1. Run:

   ```sh
   make -f lab-gateway.mk secrets          # every secret vault.yml lacks; NAME=private-scratch-2 for one
   ```

2. Type each value at its prompt: a repository's PAT, or the Anthropic key. The input is not echoed,
   and it travels only on stdin into `ansible-vault encrypt_string`. Each one is written to
   `inventory-host/host_vars/localhost/vault.yml` (gitignored, 0600) as the variable that `vars.yml`
   beside it names.
3. The target then runs `make -f lab-gateway.mk TAGS=vault`. Read the dry run and type `yes`. The
   playbook checks every PAT and the key against GitHub and Anthropic, then writes one Vault record per
   surrogate.

To add a repository: an entry in `vars/gateway.yml` `github_repos`, its three surrogates there
(`use: git`, `api`, `mcp`, with `repo:` and `secret:`), its line in `vars.yml` `gateway_secrets`, then
`make -f lab-gateway.mk secrets NAME=<key>`. `test_credentials` checks that the pieces agree.

## Procedure 3: Verify the gateway

1. Run the gateway suite:

   ```sh
   make -f lab-gateway-verify.mk          # PYTEST_ARGS="-k allowlist" for a subset
   ```

2. If a test fails, read its message. The message names the make target that repairs the fault. Do
   the repair, then run the suite again.

`tests/gateway` is read-only and needs no sudo. It checks:

| File | Checks |
|---|---|
| `test_binaries` | Vault, Consul, consul-template and Envoy are the pinned versions in `/usr/local/bin`, and nothing on PATH shadows them. |
| `test_pki` | `CA_TRUST_DIR` holds the gateway CA: unexpired, CA-only, and no private key. |
| `test_credentials` | Every surrogate names a secret, and each repository has its PAT and exactly one git, api and mcp surrogate bound to it. `vault.yml` is 0600 and gitignored, every secret in it is ansible-vault encrypted and decrypts with the lab key, and nothing in it is plaintext. Every surrogate's record metadata matches its hosts, repository, header and scheme, and its value fingerprint is not a surrogate's. The operator token cannot read a record (403), and no record outlives its surrogate. |
| `test_vault` | Vault and its unseal unit are active and enabled; Vault is initialised, unsealed and the pinned version. Nothing listens on its former TCP ports (8200/8201). `/run/vault/vault.sock` is `vault-clients` 0660 with `user:<you>:rw-` by ACL, and `upstream.yml` names the same socket. An anonymous read gets 403. The operator token carries only its policy, and `sys/capabilities-self` matches that policy path by path: metadata read and list only, the records themselves and `fixtures/` denied. `/var/log/vault` is vault 0700 and rotated, and `break-glass.yml` uses the gateway's socket and policy. |
| `test_vault_proxy` | The socket is `vault-proxy:envoy 0660`. The operator is not in group `envoy` and cannot connect. |
| `test_consul` | Server RPC and gossip on loopback only, and nothing on the former HTTP port 8500. `/run/consul/consul.sock` is `consul-clients` 0660 with `user:<you>:rw-` by ACL. Anonymous requests see and write nothing. The operator token can write `allow/`, not `baseline/`; the probe uses `?cas=1` on a missing key, so it changes nothing either way. |
| `test_envoy` | Envoy is LIVE and the pinned build. Its TCP listeners are exactly `GATEWAY_IP:{PROXY_PORT,GATEWAY_PORT}`, and every filter chain on them serves `SANDBOX_CIDR` only. The admin socket `/run/envoy/admin.sock` is `envoy` 0600: the operator cannot open it, and nothing listens on :9901. The GET-only view `/run/envoy/admin-readonly.sock` refuses a POST. Every gateway host has a TLS route. |
| `test_tls_inspection` | Every `ca: system` route verifies with the right bundle: the host's roots, or, when `TLS_INSPECTION_DIR` holds a chain, the public-upstream bundle (root-owned 0644, the host's roots plus the chain, which holds only unexpired CAs and is the chain that really signs the host's traffic). No bundle is left over without a chain. Live, once the sandbox bridge is up: anonymous requests through the TLS gateway pass a verified upstream handshake. See [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md). |
| `test_allowlist` | Consul's baseline equals the enabled catalog categories. Envoy's tunnel table equals baseline ∪ allow minus the gateway hosts. Each gateway host is denied on every tunnel port, `*` is denied last, and no update was rejected. Every catalog entry is well formed, and no wildcard sits on a shared cloud. |
| `test_firewall` | `ai-sandbox-firewall` is active and enabled, and `nftables.service` is not enabled. The ruleset names this lab's bridge, address and ports, and it refuses the gateway address on every interface but the bridge and `lo` ([Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)). |
| `test_units` | Each service's `systemd-analyze security` exposure is at most the score its role recorded (vault 1.0, vault-proxy 1.1, consul 1.4, envoy 1.7, consul-template 1.1). consul-template runs as its own user, outside `envoy` and `vault-clients`; Envoy is outside `consul-clients`; the route table directory is `consul-template:envoy 2750`. |
| `test_ssh_agent` | The sandbox agent is up and private. It holds only the egress key and one certificate, for `scp-target`, and the certificate has not expired. |
| `test_operator_cli` | `egress-allowlist.sh list` works and counts every key. Through `OPERATOR_DIR/env.sh`, `vault token lookup` carries the operator policy, the token helper refuses `store` (no `vault login`), and `consul kv get -keys` sees every key. |

## Daily operation

| Task | Command |
|---|---|
| List the egress allow list. | `make -f lab-gateway.mk allowlist` |
| Allow a site through the CONNECT tunnel. | `make -f lab-gateway.mk allow HOST=example.com:443 REASON="why"` |
| Remove an operator entry. | `make -f lab-gateway.mk deny HOST=example.com:443` |
| Renew the sandbox agent's certificate (8 h). | `make -f lab-gateway.mk agent-cert` |
| Rotate a real credential (every surrogate it backs). | `make -f lab-gateway.mk secrets NAME=private-scratch-1` |
| Read a real credential (an emergency; audited, 15 minutes). | `make -f lab-gateway.mk break-glass REASON="why" [CMD="vault kv get …"]` |
| Inspect Vault or Consul (read-only). | `eval "$(make -s -f lab-gateway.mk cli)"`, then `vault …` / `consul …` ([Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)) |

Allow-list changes apply live. consul-template renders the route table and Envoy reloads it, with no
restart. Baseline entries come from `vars/egress-baseline.yml`; to change them, edit that file and
run `make -f lab-gateway.mk TAGS=consul`.

Routes and surrogates come from `vars/gateway.yml`. After removing a surrogate there, run
`make -f lab-gateway.mk TAGS=vault`: `vault_gateway` deletes every `surrogates/<id>` record no surrogate
names (and anything under `fixtures/`), so Envoy stops honouring it.

## Status

2026-10-27, on the Linux x86_64 host: the gateway applied with the GitHub MCP routes, the optional
TLS-inspection support and the real credentials (three per-repository PATs and the Anthropic key), and a
second dry run found nothing to change. With the lab provisioned, and Envoy resolving IPv4 only
([Envoy cached an IPv6 address for a tunnel host](/issues/envoy-cached-an-ipv6-address-for-a-tunnel-host-and-refused-it-with-503-uf--01a17e521712.md)),
`tests/gateway` passed (171 passed; 4 skipped: no chain in `TLS_INSPECTION_DIR`). After the sandbox
suite's fixes (a fail-closed Lua filter, an HTTP/1.0 tunnel, codeload.github.com as a route), it passed
again (256 passed, 4 skipped), and so did `make -f lab-provision-verify.mk STACK=sandbox`.

2026-10-27, the hardening review ([Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)):
- the firewall and Envoy refuse every source but the sandbox network;
- Envoy's admin API is a socket;
- Vault (migrated from raft to file storage) and Consul are on unix sockets;
- Vault has an audit device, the operator token reads metadata only, and break-glass exists;
- the TLS gateway normalizes paths and rate-limits each host;
- consul-template has its own user, and every unit is sandboxed (exposure 1.0–1.7);
- the gateway and upstream-test CAs are name-constrained.

The SSH destination constraint was backed out
([issue](/issues/the-hosts-openssh-9-6-agent-cannot-use-a-destination-constrained-certificate--01a17f01fd3b.md)).
After it, every suite was green: `tests/gateway` (280 passed, 4 skipped), `STACK=sandbox` (139 passed,
8 skipped), `tests/host` (49) and the default guest suite (43). `STACK=python-stack` had one failure,
which predates the hardening and was a test bug, since fixed
([issue](/issues/the-lazyvim-lockfile-names-nvim-jdtls-which-the-spec-never-installs--01a17f01fd7d.md)).

## Related
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
- [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)
- [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
- [Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
- [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md)
- [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)
- [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)
- [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/lab-gateway.mk`, `lab-gateway-verify.mk`, `tests/gateway/`
- `scripts/gateway/egress-allowlist.sh`, `scripts/gateway/sandbox-secret.sh`
- `PLAN-zero-trust-surrogate-secrets-inject-gw.md`
