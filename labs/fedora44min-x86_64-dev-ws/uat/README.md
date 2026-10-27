# User acceptance tests

These are the manual acceptance tests of the lab. Each test is a story: a person does a task that a
developer or the operator does every week, and checks what they see. The pytest suites check the
configuration. These tests check that the people can do their work with it.

The tests use the **python-stack** configuration (`ansible/playbooks/python-stack.yml` on top of
`vm-baseline.yml`). Each test uses only the tools that this stack installs.

For the reasons and the relation to the pytest suites, read the wiki runbook
[Run the UAT Suites](../../../.okfw/runbooks/run-the-uat-suites--01a17f21b82c.md).

## Before you start

1. Do procedures 1 to 8 of the [lab README](../README.md). All the verify suites pass.
2. Do procedure 4: the real credentials are in Vault.
3. Read [personas.md](personas.md). Each step names the persona that does it.

## Suites

Do the suites in this order. A test can need an earlier test as a precondition.

| Suite | ID prefixes | What it covers |
|---|---|---|
| [01-lab-lifecycle](01-lab-lifecycle/) | LIFE | Status, connect, stop and start, host restart, rebuild |
| [02-dev-session](02-dev-session/) | SESS | The tmux editor and shell layout at login |
| [03-python-editing](03-python-editing/) | EDIT | LazyVim with pyrefly, ruff and ansible-lint |
| [04-python-project](04-python-project/) | PY | A uv project: dependencies, lint, type check, tests |
| [05-containers](05-containers/) | CTR, SCAN | Rootless podman, an SBOM and a vulnerability scan |
| [06-github](06-github/) | GIT, GHAPI | Private repositories with the surrogate credentials |
| [07-claude-code](07-claude-code/) | AI, MCP | Claude Code and its GitHub MCP servers |
| [08-egress](08-egress/) | EGR, ISO | The allow list and the isolated network |
| [09-scp](09-scp/) | SSH | SCP with the forwarded sandbox agent |
| [10-credentials](10-credentials/) | CRED | Surrogates on the guest, rotation, the operator CLI, break-glass |

> **Caution:** Tests with `disruptive: true` stop the lab VMs, restart the host, rotate a
> credential or delete the lab. Do them last, and not on a lab that someone else uses at the time.

## The test file

Each test is one file, `<suite>/<id>-<title>.md`. The frontmatter has these keys:

| Key | Value |
|---|---|
| `id` | `UAT-<PREFIX>-<NN>`. Each prefix is in one suite only. |
| `title` | One sentence: what is true when the test passes. |
| `suite` | The name of the directory that holds the file. |
| `stack` | The configuration the test uses: `python-stack`. |
| `features` | The features the test accepts, from [features.md](features.md). |
| `personas` | The personas that do the steps, from [personas.md](personas.md). |
| `priority` | P1 (a developer cannot work without it), P2 (a workaround exists), P3 (rare). |
| `disruptive` | `true` when the test stops, restarts or deletes something that other people use. |
| `automated` | The pytest tests that check the same behavior, from the lab directory: `<file>::<function>`, a whole `<file>`, or a test directory. A list when several tests each check a part. `none` when no test does. **Notes** says what only the manual test covers. |
| `leaves` | What the test leaves on the lab. |

The body has these sections: **Story**, **Preconditions**, **Steps** (a table: step, persona,
action, expected result), **Evidence left behind** and **Notes**.

`make -f lab-provision.mk lint` runs `scripts/check-uat-specs.py`. The script checks that each ID is
unique, each prefix is in one suite, each `suite` is its directory, each feature and persona is in
its catalog, and each `automated` test exists.

## Record a run

Copy this block into the place where your team keeps test results. Write one line for each test.

```text
UAT run
Date:      2026-MM-DD
Commit:    <git rev-parse --short HEAD>
Tester:    <name>
Behind a TLS-inspecting proxy: yes | no

ID            Result                 Note
UAT-LIFE-01   pass | fail | blocked
UAT-LIFE-02   ...
```

For each `fail`, give the step number and what you saw. For each `blocked`, give the test or the
precondition that stopped it.

A test whose **Notes** names a known defect or gap still gets `fail` while the defect is open. The
note links the wiki issue. Do not change the expected result to match the defect.

## After the run

Remove what the tests left on the lab, unless you want to keep it:

1. As dev: `rm -rf ~/uat-py ~/uat-git` and
   `podman rmi localhost/uat-py ghcr.io/astral-sh/uv:python3.14-trixie-slim`.
2. As the operator: if no one needs SCP now, `make -f lab-gateway.mk deny HOST=192.168.151.10:22`.
   Then `make -f lab-gateway.mk allowlist | grep -w operator` shows only the entries that someone
   needs.
3. As the operator: run `make -f lab-provision-verify.mk STACK=python-stack` and
   `make -f lab-gateway-verify.mk`. Both pass.
