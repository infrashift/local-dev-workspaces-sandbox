---
id: "01a17ecc-92f3-79c5-a2df-1aac14a5a6a9"
title: "The operator token could read the real credentials"
type: "issue"
tags:
  - "issue"
  - "vault"
  - "gateway"
  - "security"
  - "least-privilege"
created: "2026-10-27T14:18:18-05:00"
timestamp: "2026-10-27T14:18:18-05:00"
description: "The standing operator token's policy read every surrogate record (every real credential) and nothing was audited; it now reads only secret-free metadata, a break-glass policy on a 15-minute wrapped token reads the records, and a file audit device logs it all."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "since the gateway began (operator policy read data/surrogates)"
  found: "2026-10-27, hardening review"
---

# The operator token could read the real credentials

**Severity medium, P2, fixed.** It had been there since the gateway began, and was found in the
2026-10-27 hardening review.

## What happens
1. The operator token, `OPERATOR_DIR/vault-operator.token`, is a standing periodic token (768 h,
   renewed by use) in the operator's home directory.
2. Its policy, `ai-sandbox-operator`, granted `read` on `ai-sandbox/data/surrogates/*`, which is
   every real credential. Anything running as the operator could read them all: a script, a
   compromised tool, the gateway suite, or `vault kv get` typed by mistake.
3. Nothing recorded who read what. Vault had no audit device.

## Fix
- `ai-sandbox-operator` reads only the records' metadata. `vault_gateway` now writes the binding,
  without the secret, as `custom_metadata`, with a 16-hex-digit fingerprint of the value.
  `test_credentials` checks the binding from it. One snag: Vault refuses an empty `custom_metadata`
  value, so the Anthropic record, which has no repository, carries no `repo` key.
- A new policy, `ai-sandbox-break-glass`, reads the real credentials. No standing token carries it.
  `make -f lab-gateway.mk break-glass REASON=…` mints a 15-minute one:
  - it is non-renewable, and its metadata holds the user and the reason;
  - it is handed over response-wrapped;
  - `break-glass.sh` unwraps it into one shell's environment and revokes it on exit.

  A wrapping token someone else used first does not unwrap, and the script says so.
- A `file` audit device writes `/var/log/vault/audit.log` (vault 0600, logrotate daily, HUP to
  reopen).
- `tests/gateway/test_vault.py`: the operator gets `deny` on `data/surrogates/*` and `read` on the
  metadata. `test_credentials.py`: a record read with the operator token gets 403.

## Verified
2026-10-27:
- a break-glass token carried `ai-sandbox-break-glass` and `default`, a TTL of 899 s, was not
  renewable, held `{reason, user}`, read a record, and was revoked on exit;
- a wrapping token unwrapped by someone else first was refused;
- the audit log held the reason and every unwrap.

## Related
- [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
