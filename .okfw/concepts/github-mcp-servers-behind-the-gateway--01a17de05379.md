---
id: "01a17de0-5379-7414-9832-286c4d2f1336"
title: "GitHub MCP Servers Behind the Gateway"
type: "concept"
tags:
  - "gateway"
  - "mcp"
  - "github"
  - "surrogates"
  - "decision"
created: "2026-10-27T10:00:15-05:00"
timestamp: "2026-10-27T10:00:41-05:00"
description: "Why the sandbox uses github-mcp-server three ways (local stdio, self-hosted on upstream-1 behind stunnel, GitHub-hosted), each with a bearer surrogate the gateway swaps for the real PAT, and what that implies."
status: "draft"
---

# GitHub MCP Servers Behind the Gateway

The sandbox reaches GitHub through `github/github-mcp-server`, deployed three ways for **each** private
repository in `vars/gateway.yml` `github_repos` (decided 2026-10-27). Each repository has its own
fine-grained PAT, limited to that repository, and its own surrogates. The TLS gateway swaps a surrogate
for that repository's PAT, which only Vault holds ([Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)).

| Server (per repository `<key>`) | Where it runs | What the sandbox sends | What the gateway injects |
|---|---|---|---|
| `github-local-<key>` | On the sandbox, over stdio, started by Claude Code | `GITHUB_PERSONAL_ACCESS_TOKEN=<api surrogate>`. The server calls api.github.com and raw.githubusercontent.com with it as `Authorization: Bearer` | `Authorization: Bearer <the repository's PAT>` |
| `github-upstream-<key>` | upstream-1: `github-mcp-server http` on 127.0.0.1:8082, behind stunnel TLS on :8443 (`upstream_github_mcp`). The route is `mcp.upstream.ai-sandbox.test` | `Authorization: Bearer <mcp surrogate>` | `Authorization: Bearer <PAT>`. upstream-1 calls GitHub with it over the NAT network |
| `github-hosted-<key>` | GitHub's hosted server, `https://api.githubcopilot.com/mcp/readonly` | the same mcp surrogate | `Authorization: Bearer <PAT>` |

`python-stack.yml` builds the servers from `github_repos` (`github_mcp_servers`) and registers them at
user scope in `~/.claude.json`. With the three `private-scratch-*` repositories that is nine servers.
`vars/github-mcp.yml` pins one version and SHA-256 for both installs, and turns on read-only tools for
both.

## Why it is built this way

- **One server, three deployments.** The local, self-hosted and hosted cases all exercise the same tool
  code, so a failure points at the path, not the server. The self-hosted server replaced the lab's mock
  MCP server, which tested Basic-auth injection only.
- **Bearer surrogates, not Basic.** `github-mcp-server` authenticates with `Authorization: Bearer`
  (go-github). In `http` mode it also *parses* the incoming header and accepts only tokens with a GitHub
  prefix (`github_pat_`, `ghp_`, ...), so the gateway must inject `Bearer <PAT>`. The Basic git
  surrogates stay for git over HTTPS, which needs Basic auth; their record carries the PAT's login.
- **Separate surrogates per use and per repository.** A repository's api surrogate is bound to
  api.github.com and raw.githubusercontent.com, and its mcp surrogate only to the two remote MCP hosts, so
  a leaked remote-MCP surrogate cannot call the API directly. Each surrogate is also bound to its
  repository: on another repository's path the gateway answers 403 "surrogate repository mismatch". The
  remote servers get the PAT itself and are limited only by its own scope, which is that one repository.
- **raw.githubusercontent.com is a gateway route.** The server reads file contents from it with the same
  token. Through the CONNECT tunnel the surrogate would reach GitHub unswapped, and private files would
  404. Making it a route took it out of the egress catalog: a gateway host never goes through the tunnel.
  It is `anonymous: true`, so public raw downloads still work.
- **stunnel in front of the self-hosted server.** `http` mode speaks plain HTTP. stunnel adds TLS with
  the upstream-test CA's certificate, which Envoy verifies (`ca: upstream`). The server listens on
  loopback only. stunnel keeps its files under `/etc/stunnel` and drops to `nobody` itself: SELinux's
  `stunnel_t` may not read systemd credentials
  ([upstream_github_mcp failed on its first apply](/issues/upstream-github-mcp-failed-on-its-first-apply-ansible-managed-in-copy-and-selinux-denied-stunnel-its-credentials--01a17e521725.md)).
- **The binary, not the container image.** A container on the guest does not trust the gateway CA (see
  [Container builds on the guest do not trust ZScaler](/issues/container-builds-on-the-guest-do-not-trust-zscaler--01a1672ea58d.md)).
  The release tarball also verifies against the release's own SHA-256.

## Consequences

- **The real PAT reaches upstream-1.** That is what a remote MCP server is: it acts for the caller with
  the caller's token. upstream-1 plays the trusted corporate server. The sandbox still never sees the
  PAT.
- **GitHub hands the guest short-lived raw tokens.** For a private repository, the contents API's
  `download_url` (and so `get_file_contents`' listing) carries `?token=...`, a time-limited token for
  that one file that GitHub derives from the PAT. The gateway does not rewrite response bodies, so it
  reaches the sandbox. It is scoped to one file and expires quickly, but it is real GitHub access the
  sandbox holds, and it works without the gateway. Seen 2026-10-27 in the sandbox suite.
- **The hosted server depends on GitHub's policy.** The account, or its organisation, must allow the
  remote MCP server and the PAT type. When GitHub refuses the injected PAT, the sandbox suite says so
  rather than blaming the gateway.
- **Vault prunes records of removed surrogates.** `vault_gateway` deletes any `surrogates/<id>` no
  surrogate names, and everything under `fixtures/`. Otherwise Envoy would go on honouring the mock's
  old surrogate.

## Verified

- 2026-10-27, on the host: the gateway applied, and a second dry run found nothing to change.
  `tests/gateway` passed (146 passed, 7 skipped: no chain, no sandbox bridge yet). The probe the sandbox
  suite uses (`tests/guest/sandbox/mcp_probe.py`) completed a session and a `get_me`/`list_commits` call
  against the real 2.0.3 binary over stdio and over `http`, where GitHub refused the surrogate as
  expected without the gateway in the path.
- Not yet: `tests/guest/sandbox`, which needs the lab VMs, the python-stack and the real PAT.

## Related
- [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)
- [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/ansible/vars/gateway.yml`, `vars/github-mcp.yml`, `playbooks/python-stack.yml`, `playbooks/upstream.yml`
- `ansible/roles/guest/github_mcp_server/`, `ansible/roles/guest/upstream_github_mcp/`, `ansible/roles/guest/claude_code/`
- `scripts/gateway/sandbox-secret.sh`, `ansible/roles/gateway/vault_gateway/`
- github/github-mcp-server v2.0.3: `pkg/utils/token.go` (token prefixes), `pkg/http/transport/bearer.go`, `pkg/raw/raw.go`
