---
id: UAT-CRED-03
title: The operator's vault and consul command lines can look around, but cannot read a real credential or change the baseline
suite: 10-credentials
stack: python-stack
features:
- SBX-CRED-02
personas:
- operator
priority: P2
disruptive: false
automated:
- tests/gateway/test_operator_cli.py::test_vault_cli_uses_the_socket_and_the_operator_token
- tests/gateway/test_operator_cli.py::test_vault_login_cannot_store_a_token
- tests/gateway/test_operator_cli.py::test_consul_cli_uses_the_socket_and_the_operator_token
leaves: Nothing. The scenario only reads, and its writes are refused.
---

# UAT-CRED-03 The operator's vault and consul command lines can look around, but cannot read a real credential or change the baseline

## Story

As the operator, I want to inspect Vault and Consul with their own command lines, so that I can
debug the gateway. As the security officer, I want that daily access to exclude the real
credentials, so that a process running as the operator cannot read them.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `eval "$(make -s -f lab-gateway.mk cli)"`, then `vault token lookup -format=json \| jq -c '.data \| {policies, display_name}'`. | `{"policies":["ai-sandbox-operator","default"],"display_name":"token-ai-sandbox-operator"}`. No login was needed. |
| 2 | operator | Run `vault kv list ai-sandbox/surrogates`. | The record IDs, one per surrogate (base64url, such as `Y2xhdWRlOnN1cnJvZ2F0ZS1naXRodWItZ2l0LXNjcmF0Y2gtMQ`). |
| 3 | operator | Run `ID=$(vault kv list -format=json ai-sandbox/surrogates \| jq -r '.[0]')`, then `vault kv metadata get ai-sandbox/surrogates/$ID`. | The metadata: `custom_metadata` with the repository, the scheme, the target hosts and a `value_fingerprint`. No credential. |
| 4 | operator | Run `vault kv get ai-sandbox/surrogates/$ID`. | `Code: 403` and `permission denied`. The operator cannot read the real credential. |
| 5 | operator | Run `consul kv get -keys ai-sandbox/egress/`. | `ai-sandbox/egress/allow/` and `ai-sandbox/egress/baseline/`. |
| 6 | operator | Run `consul kv put ai-sandbox/egress/baseline/x/example.com:443 '{}'`. | `403 (Permission denied: token … lacks permission 'key:write' …)`. The baseline is Ansible's. |
| 7 | operator | Run `printf x \| "$(dirname "$VAULT_CONFIG_PATH")/bin/vault-token-helper" store; echo $?`. | `vault login is off here: the CLI uses the operator token (make -f lab-gateway.mk break-glass)`, then `1`. `vault login` cannot replace the operator token with another one in a file. |

## Evidence left behind

None.

## Notes

The sockets open for the operator by their file permissions and ACLs. No certificate and no TLS are
involved. See [Operator Interfaces](../../../../.okfw/concepts/operator-interfaces--01a17ebdba31.md)
and [Vault and Consul Host Trust](../../../../.okfw/concepts/vault-and-consul-host-trust--01a17ebdba27.md).

Each refused request is in Vault's audit log (UAT-CRED-04).
