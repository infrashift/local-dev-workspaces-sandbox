---
id: UAT-MCP-01
title: Claude Code lists the nine GitHub MCP servers, and each is connected
suite: 07-claude-code
stack: python-stack
features:
- SBX-MCP-01
personas:
- dev
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_scenarios.py::test_claude_code_registers_the_github_mcp_servers
- tests/guest/sandbox/test_scenarios.py::test_claude_code_connects_to_the_upstream_mcp_servers
- tests/guest/sandbox/test_scenarios.py::test_local_mcp_server_acts_as_the_pat_login
- tests/guest/sandbox/test_scenarios.py::test_remote_mcp_server_acts_as_the_pat_login
leaves: Nothing. The scenario only reads the server list.
---

# UAT-MCP-01 Claude Code lists the nine GitHub MCP servers, and each is connected

## Story

As the developer, I want Claude Code to have its GitHub tools ready when it starts, so that the agent
can read issues, commits and files without a setup step.

## Preconditions

1. UAT-AI-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && claude mcp list`. | `Checking MCP server health…`, then nine lines, all marked `✔ Connected`. |
| 2 | dev | Read the nine names. | For each of `private-scratch-1`, `-2` and `-3`: `github-local-<repository>` (`/home/dev/.local/bin/github-mcp-server stdio --read-only`), `github-upstream-<repository>` (`https://mcp.upstream.ai-sandbox.test/`) and `github-hosted-<repository>` (`https://api.githubcopilot.com/mcp/readonly`). |
| 3 | dev | Run `claude mcp get github-hosted-private-scratch-1`. | The server's URL, and an `Authorization` header of `Bearer surrogate-github-mcp-scratch-1`. A surrogate, not a real token. |
| 4 | dev | Run `claude`. Type `/mcp`. | The same nine servers, each connected, with their tools. Press `Esc`, then type `/exit`. |

## Evidence left behind

None.

## Notes

`test_claude_code_connects_to_the_upstream_mcp_servers` runs `claude mcp list` for the three
self-hosted servers, so Claude Code's own TLS stack is tested. The other tests call the servers with a
Python MCP client, which accepted a certificate chain that Claude Code refused (`UNSUPPORTED_CONSTRAINT_TYPE`,
fixed: [Claude Code refuses the gateway CA's name constraints](../../../../.okfw/issues/claude-code-refuses-the-gateway-cas-name-constraints--01a17f21b808.md)).

If a `github-hosted-*` server fails with 401 or 403, GitHub may not allow
the hosted MCP server for the organisation or for the PAT. See
[GitHub MCP Servers Behind the Gateway](../../../../.okfw/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md).
