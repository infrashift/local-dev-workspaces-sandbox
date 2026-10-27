---
id: UAT-CRED-04
title: The operator uses break-glass with a reason, and the auditor finds the reason and each read in the audit log
suite: 10-credentials
stack: python-stack
features:
- SBX-CRED-03
personas:
- operator
- auditor
priority: P2
disruptive: false
automated: none
leaves: Entries in /var/log/vault/audit.log. The break-glass token is revoked.
---

# UAT-CRED-04 The operator uses break-glass with a reason, and the auditor finds the reason and each read in the audit log

## Story

As the operator, I want a fast way to read a real credential in an emergency. As the auditor, I
want each such read to carry a person and a reason in the audit log, so that I can review every use.

## Preconditions

1. UAT-CRED-03 passes.
2. The operator's sudo password is in the become vault (`make -f lab-bootstrap.mk become-vault`).

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-gateway.mk break-glass REASON="UAT-CRED-04: audit test"`. | The playbook mints the token. Then `Break-glass shell: VAULT_TOKEN reads the real credentials for 15 minutes. Exit to revoke it.` The prompt starts with `(break-glass)`. |
| 2 | operator | Run `vault token lookup -format=json \| jq -c '.data \| {display_name, policies, ttl, renewable, meta}'`. | `display_name` is `token-break-glass-<your user>`, the policies include `ai-sandbox-break-glass`, `ttl` is 900 or less, `renewable` is `false`, and `meta` holds your user and the reason. |
| 3 | operator | Run `ID=$(vault kv list -format=json ai-sandbox/surrogates \| jq -r '.[0]')`, then `vault kv get -format=json ai-sandbox/surrogates/$ID \| jq -r '.data.data \| keys'`. | The field names of the record. The read works. (The command shows the names only, so the credential does not reach the terminal.) |
| 4 | operator | Run `exit`. | `Break-glass token revoked.` |
| 5 | operator | Run `make -f lab-gateway.mk break-glass` with no `REASON`. | `Usage: make -f lab-gateway.mk break-glass REASON="why" …`. No token is minted. |
| 6 | auditor | Run `sudo grep -c 'UAT-CRED-04: audit test' /var/log/vault/audit.log`. | A number greater than 0. |
| 7 | auditor | Run `sudo jq -c 'select((.auth.display_name // "") \| test("break-glass")) \| {time, type, path: .request.path, reason: .auth.metadata.reason}' /var/log/vault/audit.log \| tail -8`. | The requests of steps 2 and 3, each with the reason `UAT-CRED-04: audit test`, including a read of `ai-sandbox/data/surrogates/<id>`, and the revocation from step 4. |
| 8 | auditor | Run `sudo jq -c 'select(.request.path == "sys/wrapping/unwrap") \| {time, type}' /var/log/vault/audit.log \| tail -2`. | The unwrap of the wrapping token at step 1. |

## Evidence left behind

The audit log entries. The token is revoked. If step 4 is skipped, the token expires by itself in 15
minutes.

## Notes

The audit log hashes secret values (HMAC), so the credential is not in the log in clear text. The
reason and the user are token metadata, which the log records in clear text.

If the unwrap at step 1 fails, someone used the wrapping token first. The script stops and points
at the audit log. That is a security event, not a test fault.

See [Operator Interfaces](../../../../.okfw/concepts/operator-interfaces--01a17ebdba31.md),
"Break-glass".
