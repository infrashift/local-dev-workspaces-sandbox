---
id: "01a17ebd-ba31-787b-8c3f-cf3111dc4413"
title: "Operator Interfaces"
type: "concept"
tags:
  - "gateway"
  - "operator"
  - "cli"
  - "vault"
  - "consul"
  - "decision"
created: "2026-10-27T14:02:05-05:00"
timestamp: "2026-10-27T14:02:05-05:00"
status: "draft"
description: "Changes go through make -f lab-gateway.mk and its wrappers; the vault and consul CLIs are for read-only inspection through OPERATOR_DIR/env.sh (unix sockets, operator tokens, no vault login); break-glass is a short-lived, audited token."
---

# Operator Interfaces

How the operator works the gateway's tools: when to use the make targets, when the `vault` and
`consul` command lines, and how break-glass access to the real credentials works (decided
2026-10-27).

## The rule
- **Changes go through `make -f lab-gateway.mk`.** The make targets and their wrapper scripts:
  - validate input (host patterns, no gateway host, no quote in a reason);
  - keep tokens out of argv and logs (headers read from a file descriptor);
  - use scoped tokens, never the root or bootstrap token;
  - leave Ansible the owner of the declarative state.

  A change made by hand to a policy, the AppRole, a surrogate record or the baseline is drift: the
  next `make -f lab-gateway.mk` reverts it, and deletes any surrogate record no surrogate names.
- **The CLIs are for read-only inspection.** `vault` and `consul` work against the unix sockets
  with the operator tokens, and those tokens limit what they can do.
- **Root and bootstrap tokens are for Ansible only.** They stay root-only in `/etc/ai-sandbox/`.

| Task | Interface |
|---|---|
| Install, change or repair the gateway | `make -f lab-gateway.mk` (dry run, then `yes`) |
| Load or rotate a real credential | `make -f lab-gateway.mk secrets [NAME=…]` |
| List, allow or remove an egress entry | `make -f lab-gateway.mk allowlist`, `allow HOST=… REASON=…`, `deny HOST=…` |
| Renew the sandbox agent's certificate | `make -f lab-gateway.mk agent-cert` |
| Look around in Vault or Consul | `eval "$(make -s -f lab-gateway.mk cli)"`, then `vault …` / `consul …` |
| Envoy's state | `curl --unix-socket /run/envoy/admin-readonly.sock http://localhost/stats` (GET only) |
| Read a real credential (an emergency) | `make -f lab-gateway.mk break-glass REASON="why" [CMD="vault kv get …"]` |

## The CLI environment
`vault_gateway` and `consul_egress` write it into `OPERATOR_DIR` (`~/.config/ai-sandbox`).
`env.sh` sources each `env.d/*.sh`:

| Variable | Value |
|---|---|
| `VAULT_ADDR` | `unix:///run/vault/vault.sock` |
| `VAULT_CONFIG_PATH` | `vault-cli.hcl`: `token_helper = bin/vault-token-helper`. `get` hands the CLI the operator token; `store` refuses, so `vault login` cannot leave another token in a file |
| `CONSUL_HTTP_ADDR` | `unix:///run/consul/consul.sock` |
| `CONSUL_HTTP_TOKEN_FILE` | `consul-operator.token` |

No certificates are involved: the sockets open for the operator by ACL, with no TLS and no
re-login ([Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)).
`tests/gateway/test_operator_cli.py` checks:
- `vault token lookup` carries the operator policy;
- the token helper refuses `store`;
- `consul kv get -keys` sees every allow-list key.

## Break-glass
The operator token reads no real credential. Its policy, `ai-sandbox-operator`, covers the records'
metadata only ([Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)).
For the rare time one has to be read (debugging a swap, or checking a rotation), run:

```sh
make -f lab-gateway.mk break-glass REASON="why"                       # a shell
make -f lab-gateway.mk break-glass REASON="why" CMD="vault kv get …"  # one command
```

1. `break-glass.yml` reads the root token with the become vault, like every privileged run here. It
   mints an orphan token with policy `ai-sandbox-break-glass`: 15 minutes, `explicit_max_ttl` equal,
   not renewable, display name `break-glass-<user>`, and metadata `{user, reason}`.
2. The token is **response-wrapped** (120 s). Only the single-use wrapping token is written, 0600 on
   the operator's tmpfs (`/run/user/<uid>/`).
3. `scripts/gateway/break-glass.sh` reads and deletes that file, unwraps it, and runs the command or
   an interactive shell (prompt `(break-glass)`) with `VAULT_TOKEN` in its environment only. On exit
   it revokes the token.
4. If someone used the wrapping token first, the unwrap fails and the script stops, pointing at the
   audit log.

Every step lands in Vault's audit log, `/var/log/vault/audit.log`, root-readable: the reason, the
unwrap and every read.

Why not a standing admin token: one in `OPERATOR_DIR` would undo the narrowed operator policy, and
every process running as the operator could use it. Why the become vault and not a `sudo` prompt: the
operator account already reaches root through the become vault, so a password prompt would add
ceremony, not a boundary. The time box, the wrap and the audit trail are the controls.

## Related
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)
