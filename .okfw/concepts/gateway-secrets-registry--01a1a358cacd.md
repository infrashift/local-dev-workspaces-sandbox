---
id: "01a1a358-cacd-7670-8339-5f1cdb93100d"
title: "Gateway Secrets Registry"
type: "concept"
tags:
  - "gateway"
  - "credentials"
  - "operator"
  - "decision"
created: "2026-11-03T15:37:47-06:00"
timestamp: "2026-11-03T15:38:02-06:00"
description: "vars/gateway-secrets.yml names every real credential of the gateway (kind, repository, vault.yml variable, rotated, expires) and never a value; github_repos and gateway_secrets derive from it, and the secret-* targets manage it."
status: "draft"
---

# Gateway Secrets Registry

`labs/<lab>/ansible/vars/gateway-secrets.yml` is the one list of the gateway's real credentials. It is
committed, and it holds names only, never values (decided 2026-11-03, with the operator). The values
stay where [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)
put them: in the host inventory's `vault.yml`, each one ansible-vault encrypted on its own.

## What it replaced
Before, one repository's PAT was described in three places:
- `github_repos` in `vars/gateway.yml`;
- `gateway_secrets` (name → `"{{ <var> }}"`) in `inventory-host/host_vars/localhost/vars.yml`;
- the three surrogates in `vars/gateway.yml`.

Nothing recorded when a value was set or when it expired.

## The file
Each entry is one line, `<name>: { kind, repo, vault_var, rotated, expires }`. The `secret-*` targets
rely on that format to edit it.
- `kind`: `github-pat`, a fine-grained PAT for `repo` alone, or `anthropic-api-key`.
- `vault_var`: the `vault.yml` variable that holds the value. The existing names were kept, so nothing needed migrating.
- `rotated` and `expires`: optional dates. `secret-set` and `secret-rotate` record `rotated`; `secret-rotate` asks for `expires`.

Two values are derived from it:
- `github_repos`, in the registry file itself: its `github-pat` entries. `gateway-host.yml` and `python-stack.yml` load the file.
- `gateway_secrets`, in `gateway-host.yml`: name → `query('ansible.builtin.vars', vault_var)`.

## Checks
`gateway-host.yml` pre_tasks, before anything is written:
- every surrogate names a registry entry;
- a GitHub surrogate's `repo` is its entry's;
- every entry is used by a surrogate;
- the kinds, repositories and variable names are well formed;
- `vault.yml` defines every `vault_var` (names only, through the `varnames` lookup);
- a past `expires` fails the run, and one within 14 days warns.

`scripts/gateway/gateway_secrets.py check` (`make -f lab-gateway.mk secrets-check`) applies the same
rules and says which one broke. `tests/gateway/test_credentials.py` reads the registry.

## Operations
| Task | Target |
|---|---|
| What is held, when it was loaded into Vault (record metadata, read with the operator token), rotated, expires | `secrets-list` |
| Set a value (all missing, or `NAME=`) | `secret-set` (alias `secrets`) |
| Replace a value and record the dates | `secret-rotate NAME=… [EXPIRES=…]` |
| A new repository | `secret-add NAME=… KIND=github-pat REPO=owner/name`: it adds the registry line, asks for the PAT, and prints the git/api/mcp surrogate stanza for `vars/gateway.yml` |
| Retire one | `secret-remove NAME=…`: it refuses while a surrogate names the entry, and removes the registry line and the `vault.yml` block |

## Considered and not done
- **Generating the three surrogates from the registry.** One line would then add a repository, but a dozen roles, templates and tests read `surrogates` directly. The surrogates stay explicit; `secret-add` prints them, and the checks make them agree with the registry.

## Verified
2026-11-03:
- The gateway dry run and apply ran with the registry; Vault's surrogate records were unchanged.
- A `python-stack` dry run found no change in the surrogates or the nine MCP servers.
- `tests/gateway`: 282 passed.
- The `add`, `stamp` and `remove` edits were run against scratch copies.
- Not run: an interactive `secret-rotate` with a real new PAT (UAT-CRED-02).

## Related
- [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/ansible/vars/gateway-secrets.yml`, `ansible/playbooks/gateway-host.yml`
- `scripts/gateway/sandbox-secret.sh`, `scripts/gateway/gateway_secrets.py`
