---
id: "01a17e13-3adc-7bfb-8b74-1b3bd44e3629"
title: "Gateway Credentials in the Host Inventory"
type: "concept"
tags:
  - "gateway"
  - "credentials"
  - "ansible-vault"
  - "github"
  - "decision"
created: "2026-10-27T10:55:51-05:00"
timestamp: "2026-10-27T10:56:18-05:00"
description: "Why the gateway's real credentials (one fine-grained PAT per GitHub repository, the Anthropic key) live ansible-vault encrypted in the host inventory, how each is bound to its repository and checked before use, and the trade-off."
status: "draft"
---

# Gateway Credentials in the Host Inventory

# Gateway Credentials in the Host Inventory

The gateway's real credentials live in the **host** Ansible inventory, encrypted with ansible-vault, and
the gateway playbook loads them into Vault (decided 2026-10-27, with the operator). Before this, the
operator typed them into `scripts/gateway/sandbox-secret.sh`, which wrote them straight to Vault, so they
never passed through Ansible.

| File | Holds | In Git |
|---|---|---|
| `inventory-host/host_vars/localhost/vars.yml` | `gateway_secrets`: secret name → `"{{ <name>_secret }}"` | yes (no secret) |
| `inventory-host/host_vars/localhost/vault.yml` | each `<name>_secret`, as its own `!vault` block (the lab's `.ansible_vault_key`) | no (gitignored, 0600) |
| `vars/gateway.yml` | `github_repos` (secret name → `owner/name`) and the surrogates, each naming its `secret` and, for GitHub, its `repo` | yes |

`make -f lab-gateway.mk secrets [NAME=<name>]` reads a secret at a hidden prompt and pipes it into
`ansible-vault encrypt_string`. It replaces that variable's block in `vault.yml`, then runs the gateway
playbook with `TAGS=vault`: a dry run, then "yes". With no `NAME`, it asks for each secret `vault.yml`
lacks.

## One fine-grained PAT per repository

Each repository in `github_repos` has its **own** fine-grained PAT, limited to that one repository, and
its own three surrogates (`use: git`, `api`, `mcp`), each bound to it with `repo:`. Envoy's Lua filter
refuses a repository-bound surrogate on another repository's path (403 "surrogate repository mismatch").
It finds the repository with the route's `repo_path` pattern: `/<owner>/<repo>` on github.com and
raw.githubusercontent.com, `/repos/<owner>/<repo>` on api.github.com. Paths without a repository, such
as `/user` or `/graphql`, pass, because the PAT behind the surrogate limits them itself. In the sandbox,
git picks the repository's surrogate by path (`credential.https://github.com.useHttpPath`), and Claude
Code gets three GitHub MCP servers per repository
([GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)).

Considered and rejected: **one surrogate, with the gateway choosing the PAT by path**. It is fewer MCP
servers, but calls with no repository in the path (GraphQL, search, `/user`) would need a default PAT.
The remote MCP servers would still need a surrogate per repository, because the repository is inside
the MCP call, which Envoy does not parse.

## What the gateway playbook checks

`vault_gateway` makes these read-only calls in the dry run too, and keeps only the outcome:

- Each PAT: `GET api.github.com/user` (200, and the login, which the Basic git record needs) and
  `GET /repos/<owner>/<name>` (200, `private: true`). A 401 means the PAT is wrong or expired. A 403 or
  404 means it is not limited to that repository with Contents and Metadata read, or the organisation has
  not approved it.
- The Anthropic key: `GET /v1/models` (200).
- Then one record per surrogate (hosts, repository, header, value), and the deletion of any record that
  no surrogate names. Every task that holds a value is `no_log`, and every message names secrets, never
  values.
- A missing variable stops the run first, by name: `'github_pat_private_scratch_2_secret' is undefined`.

The operator token is now **read-only** on the records. Only the playbook, with the root token, writes
them.

## Trade-off (analysis, not part of the recorded decision)

- **Gained:** the credentials are declarative. A Vault re-initialisation, a rebuilt host or a new
  repository is a playbook run, not a re-typing session. Each PAT is proved before it is used.
- **Given up:** a second copy at rest. `vault.yml` is only as safe as `.ansible_vault_key`, a 0600 file
  in the project that also guards the sudo password. The values now pass through Ansible's memory, kept
  out of its output by `no_log`. Vault's own unseal key is also on disk (root-only), so the at-rest
  protection is of the same kind.

## Verified

2026-10-27, without real PATs:
- The `make secrets` script, driven through a pseudo-terminal against scratch files: no echo, a 0600
  file, the plaintext nowhere in it, a rotation replaces only its block, and the value decrypts with the
  lab key.
- A dry run with fake secrets: each repository fails with GitHub's 401 and the hint, and the fake values
  appear nowhere in the output.
- A dry run with no `vault.yml`: it stops at the missing variable's name.
- With the real credentials (2026-10-27): the first `make -f lab-gateway.mk secrets` stopped on a bad
  regex in the safety check (see [ca_trust wrote anchors ending in a literal backslash-n](/issues/ca-trust-wrote-anchors-ending-in-a-literal-backslash-n--01a166fc3e13.md)).
  After the fix, the dry run proved all three PATs (one GitHub login, each reading its private
  `infrashift/private-scratch-*`) and the Anthropic key. The apply wrote the 10 records, a second dry run
  found nothing to change, and `tests/gateway` passed (167 passed, 7 skipped). The run's output held no
  credential-shaped string.
- Not yet: the sandbox suite, which needs the lab VMs.

## Related
- [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/ansible/inventory-host/host_vars/localhost/vars.yml`, `ansible/vars/gateway.yml`, `ansible/playbooks/gateway-host.yml`
- `scripts/gateway/sandbox-secret.sh`, `ansible/roles/gateway/vault_gateway/`, `ansible/roles/gateway/envoy_gateway/templates/surrogate.lua.j2`
- `labs/fedora44min-x86_64-dev-ws/tests/gateway/test_credentials.py`
