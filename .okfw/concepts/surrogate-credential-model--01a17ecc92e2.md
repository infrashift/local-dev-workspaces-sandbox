---
id: "01a17ecc-92e2-7ef2-9ca5-5c7c7ff406f6"
title: "Surrogate Credential Model"
type: "concept"
tags:
  - "gateway"
  - "surrogates"
  - "vault"
  - "envoy"
  - "security"
created: "2026-10-27T14:18:18-05:00"
timestamp: "2026-10-27T14:18:18-05:00"
status: "draft"
description: "What the guest holds (surrogates), what Vault keeps (a record per surrogate, plus its secret-free metadata), how Envoy's Lua filter swaps one for the other with host and repository binding, and who may read what."
---

# Surrogate Credential Model

How a surrogate stands in for a real credential: what the guest holds, what Vault keeps, how Envoy
swaps one for the other, and who can read what.

## The pieces
- **A surrogate** is a non-secret credential the guest holds. It is committed in `vars/gateway.yml`
  `surrogates`, and the guest gets it as `~/.git-credentials`, MCP configuration, or
  `ANTHROPIC_API_KEY`. Each one is bound to `target_hosts` (anti-replay) and, for GitHub, to one
  `repo`. Its scheme (`basic`, `bearer`, `x-api-key`) says how it is presented and what is injected.
- **A record** is `ai-sandbox/data/surrogates/<id>` in Vault (kv-v2), where `<id>` is the base64url
  of the surrogate credential, unpadded. Its fields:
  - `target_hosts`, `repo`;
  - `header`, the one to inject;
  - `value`, the real header value, for example `Basic base64(login:PAT)`.

  `vault_gateway` writes the records from the host inventory's encrypted secrets
  ([Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)),
  and deletes any record no surrogate names.
- **The record's metadata** is `custom_metadata` on `ai-sandbox/metadata/surrogates/<id>`. It holds
  the same binding without the secret:
  - `target_hosts`, `repo` (absent when there is none: Vault refuses an empty value);
  - `header`, `scheme`;
  - `value_fingerprint`, the first 16 hex digits of the value's SHA-256. That is enough to tell a
    rotation or a surrogate-valued record apart, and too short to test guesses against.

## The swap (`surrogate.lua`, on the TLS gateway)
Before the filter runs:
- the connection manager normalizes the path (`normalize_path`, `merge_slashes`), so the repository
  the filter checks is the one the upstream serves
  ([issue](/issues/path-tricks-slipped-past-the-repository-binding--01a17ed1b9f6.md));
- a per-host token bucket (`local_ratelimit`, 200 burst, 50/s) answers 429 to a flood.

1. If the route is not a gateway route, there is nothing to do. With no credential: an `anonymous`
   route passes the request through unchanged; any other route answers 401.
2. A credential (`Authorization: Basic|Bearer|Token`, or `x-api-key`) is turned into its `<id>`. The
   filter reads the record through Vault Proxy's socket, so Envoy holds no token.
   - **404**: answer 403. A real credential smuggled into the guest is refused too, because only
     surrogates have records.
   - **Host not in `target_hosts`**: answer 403, "surrogate host mismatch".
   - **The route's `repo_path` names another repository**: answer 403, "surrogate repository
     mismatch".
3. Drop `authorization` and `x-api-key`, then set the record's `header` to its `value`.
4. A Lua error answers 500. The filter fails closed
   ([issue](/issues/the-surrogate-filter-failed-open-when-its-lua-script-raised--01a17e78784d.md)).

## Who reads what

| Reader | Token | Reads |
|---|---|---|
| Envoy, through Vault Proxy | the AppRole `envoy-gateway`, policy `envoy-surrogate-reader` | `data/surrogates/*`, nothing else. The proxy's socket is group `envoy` only |
| The operator, through the CLI and the scripts | `vault-operator.token` (periodic), policy `ai-sandbox-operator` | the metadata only, plus signing the sandbox agent's SSH certificate. **No real credential** ([issue](/issues/the-operator-token-could-read-the-real-credentials--01a17ecc92f3.md)) |
| Break-glass | a 15-minute, non-renewable orphan token with policy `ai-sandbox-break-glass`; its metadata holds who and why | `data/surrogates/*` ([Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)) |
| Ansible | the root token (root-only file) | everything; it writes the records |
| The guest | none | nothing: no path to Vault ([Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)) |

Every request to Vault lands in its audit log, `/var/log/vault/audit.log`: a `file` device, vault
0600, rotated daily, with secrets HMAC'd. The device fails closed: if the log cannot be written,
Vault refuses requests, so a full disk stops the gateway.

## Checked by
- `tests/gateway/test_credentials.py`:
  - every surrogate's metadata matches `vars/gateway.yml` (hosts, repository, header, scheme);
  - its fingerprint is not that of a surrogate-valued header;
  - the operator token gets 403 on a record.
- `tests/gateway/test_vault.py`: the operator token's capabilities, path by path; the audit
  directory and its rotation; `break-glass.yml`'s socket and policy.
- `tests/guest/sandbox/test_anti_replay.py` and `test_scenarios.py`: the swap, end to end.

## Related
- [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)
- [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)
