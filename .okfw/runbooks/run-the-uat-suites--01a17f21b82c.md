---
id: "01a17f21-b82c-7949-89f1-f3c75991ccd5"
title: "Run the UAT Suites"
type: "runbook"
tags:
  - "runbook"
  - "uat"
  - "verification"
created: "2026-10-27T15:51:18-05:00"
timestamp: "2026-10-27T15:51:18-05:00"
description: "How to run the lab's manual, story-form acceptance tests in labs/<lab>/uat/: the suites, the personas, the relation to the pytest suites and how to record a run."
status: "draft"
---

# Run the UAT Suites

The UAT suites are manual acceptance tests in story form, one file per scenario, in
`labs/fedora44min-x86_64-dev-ws/uat/`. Each test is a task that a developer or the operator does
each week: log in to the tmux layout, edit Python with LazyVim, start a uv project, build a container,
clone a private repository with a surrogate, work with Claude Code and its GitHub MCP servers, ask for
a new site on the allow list, rotate a PAT, use break-glass. A person does the steps and compares
what they see with the expected result (decided 2026-10-27).

The procedure, the file schema and the run record are in `uat/README.md`. This page gives the
reasons.

## Why manual tests beside the pytest suites
The pytest suites ([Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md))
check the configuration with probes: curl, a Python MCP client, testinfra. They prove that each part
is configured. They do not prove that the tools a person uses work with those parts.

The first pass of writing the specs on the live lab showed the gap. Every sandbox test passed, and
yet:

- Claude Code could not reach api.anthropic.com or the remote MCP servers: its TLS stack refuses the
  gateway CA's name constraints, which curl and Python accept
  ([issue](/issues/claude-code-refuses-the-gateway-cas-name-constraints--01a17f21b808.md), fixed
  the same day; a sandbox test now runs `claude mcp list`).
- grype could not download its database
  ([issue](/issues/grype-cannot-download-its-vulnerability-database-in-the-sandbox--01a17f21b820.md)).
- A Docker Hub base image did not pull
  ([issue](/issues/docker-hub-pulls-fail-blobs-come-from-production-cloudfront-docker-com--01a17f2bba31.md)).
- The allow target accepted a gateway host, against the documentation
  ([issue](/issues/the-allow-target-accepts-a-gateway-host--01a17f2f9819.md)).
- admin's tmux layout opened with an error
  ([issue](/issues/admins-dev-session-editor-pane-cannot-find-nvim--01a17f21b814.md)).

## Design
- **The python-stack configuration is the basis.** Each test uses only what `python-stack.yml`
  installs, and says so in `stack: python-stack`. Another stack gets its own tests with its own
  `stack` value.
- **Personas are roles** (`uat/personas.md`): operator, dev, admin, claude, auditor. One tester can do
  all of them.
- **Features have IDs** (`uat/features.md`, `SBX-<AREA>-<NN>`), each with the roles or wiki pages
  that make it. Each test names the features it accepts, and each feature has at least one test.
- **`automated` maps each test onto the pytest suites.** It names the pytest tests that check the
  same behavior, or `none`. A test's Notes say what only the manual run covers. It is a map, not a
  promise to automate.
- **`disruptive: true`** marks the tests that stop the VMs, restart the host, rotate a credential or
  delete the lab. They run last.
- **A known defect does not change the expected result.** The test fails, and its Notes link the
  issue. When the issue is fixed, delete the note.
- **`scripts/check-uat-specs.py`**, in `make -f lab-provision.mk lint`, keeps the files consistent:
  ids, suites, catalogs, the `automated` targets and the sections.

## Suites
| Suite | Covers |
|---|---|
| 01-lab-lifecycle | status, ssh, stop and start, host restart, a no-op second run, rebuild |
| 02-dev-session | the tmux layout, reattach after a dropped connection, opt-out |
| 03-python-editing | pyrefly, ruff and ansible-lint in LazyVim; the offline, locked plugins |
| 04-python-project | uv, PyPI, ruff, pyrefly, basedpyright, pytest, the pinned versions |
| 05-containers | rootless podman, a build through the tunnel, syft, grype |
| 06-github | private clones with surrogates, a refused push, public reads, anti-replay, the REST API |
| 07-claude-code | Claude Code with the surrogate key, the nine MCP servers, read-only tools, the agent loop |
| 08-egress | the allow list (refuse, allow, deny, review) and the isolated network |
| 09-scp | scp with the forwarded sandbox agent |
| 10-credentials | surrogates only on the guest, PAT rotation, the operator CLI, break-glass and audit |

## What a pass needs that pytest does not
- An interactive terminal for the tmux, LazyVim and Claude Code tests.
- The operator's sudo password for the auditor steps (UAT-CRED-04).
- A new fine-grained PAT on GitHub for UAT-CRED-02.
- Time: about two hours for a full pass without the disruptive tests.

## Status
Draft. Written 2026-10-27 against the live lab. The non-interactive steps were checked on it as
they were written. The interactive steps (tmux, LazyVim, Claude Code) were checked headless where
possible. A first full pass by a person is still to do. When it passes except for the open issues
above, set this page to `stable`.

## Related
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
- [Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md)
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
- [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
