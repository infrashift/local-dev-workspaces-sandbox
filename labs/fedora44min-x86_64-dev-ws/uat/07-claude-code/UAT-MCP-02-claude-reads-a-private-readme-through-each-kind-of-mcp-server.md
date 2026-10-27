---
id: UAT-MCP-02
title: Claude reads a private repository's README through the local, the self-hosted and the hosted MCP server
suite: 07-claude-code
stack: python-stack
features:
- SBX-MCP-01
- SBX-AI-01
personas:
- dev
- claude
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_scenarios.py::test_local_mcp_server_reads_the_repository
- tests/guest/sandbox/test_scenarios.py::test_local_mcp_server_reads_a_file
- tests/guest/sandbox/test_scenarios.py::test_remote_mcp_server_reads_the_repository
leaves: Nothing. The scenario only reads GitHub.
---

# UAT-MCP-02 Claude reads a private repository's README through the local, the self-hosted and the hosted MCP server

## Story

As the developer, I want Claude to read a private repository through each kind of GitHub MCP server,
so that I can choose the server that fits the task and know that each one works.

## Preconditions

1. UAT-MCP-01 passes.
2. UAT-GIT-01 passes. The clones are in `~/uat-git`, for step 5.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && claude`. | Claude Code starts. |
| 2 | claude | Type the prompt `Use only the github-local-private-scratch-1 MCP server. Read README.md of infrashift/private-scratch-1 and quote its first line.` | Claude asks to use a `github-local-private-scratch-1` tool such as `get_file_contents`. Allow it. The answer quotes `# private-scratch-1`. |
| 3 | claude | Type the prompt `Do the same with the github-upstream-private-scratch-1 server.` | Claude uses a `github-upstream-private-scratch-1` tool and quotes the same line. |
| 4 | claude | Type the prompt `Do the same with the github-hosted-private-scratch-1 server.` | Claude uses a `github-hosted-private-scratch-1` tool and quotes the same line. |
| 5 | claude | Type the prompt `With github-local-private-scratch-2, list the last commit of infrashift/private-scratch-2.` | Claude gives the latest commit's SHA and message. It matches `git -C ~/uat-git/private-scratch-2 log -1 --oneline origin/HEAD` (UAT-GIT-01). |
| 6 | dev | Type `/exit`. | Claude Code ends. |

## Evidence left behind

None.

## Notes

Claude's wording varies. The test passes when Claude used the named server and the quoted line or
the SHA is correct.

The local server calls api.github.com and raw.githubusercontent.com with the api surrogate. The
remote servers get the repository's real PAT, which the gateway injects in place of the mcp surrogate.
