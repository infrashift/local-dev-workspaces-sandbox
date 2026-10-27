---
id: "01a17f21-b808-7a60-a8f6-d9578fce6aca"
title: "Claude Code refuses the gateway CA's name constraints"
type: "issue"
tags:
  - "issue"
  - "gateway"
  - "pki"
  - "claude-code"
  - "uat"
created: "2026-10-27T15:51:18-05:00"
timestamp: "2026-10-27T16:40:00-05:00"
description: "Claude Code 2.1.308 fails every TLS connection to the gateway (api.anthropic.com and the remote MCP servers) with 'unsupported name constraint type'; curl and Python accept the CA, so the pytest suites passed. Bun refuses an IP SAN matched against an IP subtree; Envoy's certificate now has no IP SAN and the CA excludes every IP."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "pre-existing (gateway_pki role)"
  found: "2026-10-27, writing the UAT specs (UAT-AI-01, UAT-MCP-01)"
---

# Claude Code refuses the gateway CA's name constraints

**Severity high, P1, fixed.** Claude Code could not work in the sandbox, which is the lab's purpose.
The pytest suites passed because they use curl and Python, which accept the certificate.

## What happened
On fedora-dev-1, as dev:

- `claude mcp list`: the three `github-local-*` servers connected. The six remote servers showed
  `✘ Failed to connect — UNSUPPORTED_CONSTRAINT_TYPE: unsupported name constraint type`.
- `claude -p hi` printed nothing and did not end. `~/.claude/debug/<session>.txt` showed
  `Policy limits: fetch failed (http) from api.anthropic.com — unsupported name constraint type`,
  retried again and again.

The local servers worked because they are a Go binary that calls GitHub itself. Every connection that
Claude Code (a Bun binary) made to the TLS gateway failed.

## Cause (confirmed)
The gateway CA permitted `IP:192.168.150.1/255.255.255.255` beside the DNS names, and Envoy's
certificate carried the SAN `IP:192.168.150.1`. Bun's verifier refuses to match an IP SAN against an
IP subtree. Throwaway CAs on the guest, with `claude mcp list` against `openssl s_server`, isolated it:

| CA name constraints | Leaf SANs | Claude Code |
|---|---|---|
| permitted DNS + IP | DNS + IP | `UNSUPPORTED_CONSTRAINT_TYPE` |
| permitted DNS + IP | DNS | TLS works |
| permitted DNS | DNS + IP | TLS works |
| permitted DNS, excluded IP 0.0.0.0/0 | DNS | TLS works |
| permitted DNS (another name) | DNS | `PERMITTED_VIOLATION`: Bun enforces DNS constraints |

## Fix
`gateway_pki` (2026-10-27):

- Envoy's certificate names the gateway hosts only, with no IP SAN. Nothing reaches the TLS gateway
  by address: the guests map each gateway host to it in `/etc/hosts`.
- The CA permits the gateway hosts' DNS names and **excludes** `IP:0.0.0.0/0` and `IP:::/0`. It can
  vouch for no address at all, which is stricter than before.
- The unused role parameter `gateway_pki_gateway_ip` is gone. The role asserts that the certificate
  has no IP SAN.

The CA keeps its key and subject, so the old anchor on a guest also verifies the new certificate until
`ca_trust` replaces it.

## Verified
- `make -f lab-gateway.mk`: the CA re-issued, the certificate re-signed, and Envoy restarted. A
  second dry run found nothing to change.
- `make -f lab-provision.mk ansible`: the guests got the new anchor. Then `make -f lab-provision.mk
  apply` re-ran site.yml for the `ca_trust_change` trigger, with `changed=0`.
- On fedora-dev-1: `claude mcp list` shows all nine servers `✔ Connected`, and `claude -p` answers.
- New test `tests/guest/sandbox/test_scenarios.py::test_claude_code_connects_to_the_upstream_mcp_servers`
  runs `claude mcp list`, so Claude Code's own TLS stack is tested. It failed before the fix and passes after it.
  `test_pki.py::test_gateway_ca_may_vouch_for_the_gateway_only` checks the new constraints.
- `lab-gateway-verify.mk` 280 passed. `STACK=sandbox` 140 passed. `STACK=python-stack` 61 passed.

## Lesson
A probe proves only the client it uses. Where the real client has its own TLS stack (Bun, Go, Java),
test with that client.

## Related
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
- [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)
