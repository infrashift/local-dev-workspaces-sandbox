---
id: "01a17e78-7883-7f24-9f5f-28040216e557"
title: "The self-hosted GitHub MCP server refused the gateway's Host header"
type: "issue"
tags:
  - "issue"
  - "mcp"
  - "envoy"
  - "upstream_github_mcp"
created: "2026-10-27T12:46:26-05:00"
timestamp: "2026-10-27T12:46:26-05:00"
description: "The MCP Go SDK's DNS-rebinding protection refuses a non-localhost Host on a loopback listener; Envoy now rewrites Host to localhost for the upstream-1 route."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "new code (upstream_github_mcp)"
  found: "2026-10-27, first sandbox suite run"
---

# The self-hosted GitHub MCP server refused the gateway's Host header

# The self-hosted GitHub MCP server refused the gateway's Host header

**Severity medium, P2, fixed.** New code (upstream_github_mcp).

## What happens
The MCP Go SDK (v1.8.0, used by github-mcp-server 2.0.3) protects local servers from DNS rebinding.
When the listener is on loopback and the request's Host is not, it answers
`403 Forbidden: invalid Host header "mcp.upstream.ai-sandbox.test"`. The server listens on 127.0.0.1
behind stunnel, and stunnel passes the Host through. github-mcp-server exposes no switch for the SDK's
`DisableLocalhostProtection`.

## Fix
An optional `upstream.host_rewrite` on a gateway route: Envoy sends `Host: localhost` to upstream-1
(`host_rewrite_literal`). The Lua filter still binds surrogates to the guest's authority, because it
runs before the router rewrites it. The TLS name Envoy verifies stays `mcp.upstream.ai-sandbox.test`.

## Verified
2026-10-27: `get_me` through the gateway to the self-hosted server answered as the PAT's login.
