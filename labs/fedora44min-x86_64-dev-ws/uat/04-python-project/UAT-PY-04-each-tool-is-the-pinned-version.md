---
id: UAT-PY-04
title: Each tool on dev's PATH is the version that python-stack.yml pins, and Claude Code does not update itself
suite: 04-python-project
stack: python-stack
features:
- SBX-PY-02
- SBX-AI-02
personas:
- dev
priority: P2
disruptive: false
automated:
- tests/guest/python-stack/test_python_stack.py::test_tool_is_the_pinned_version
- tests/guest/python-stack/test_python_stack.py::test_claude_code_auto_updater_is_off
leaves: Nothing. The scenario only reads versions.
---

# UAT-PY-04 Each tool on dev's PATH is the version that python-stack.yml pins, and Claude Code does not update itself

## Story

As the operator, I want each tool in the sandbox to be the version that the playbook pins, so that
every developer and every run of the pipeline uses the same tools.

## Preconditions

1. UAT-LIFE-01 passes.
2. You have `ansible/playbooks/python-stack.yml` open on the host, to compare the versions.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `for t in uv ruff jq nvim pyrefly basedpyright ansible-lint claude; do command -v $t; done`. | Each path is in `/home/dev/.local/bin/`. |
| 2 | dev | Run `uv --version; ruff --version; jq --version; nvim --version \| head -1; pyrefly --version; basedpyright --version; ansible-lint --version \| head -1; claude --version; grype version \| grep ^Version; syft version \| grep ^Version`. | The versions that python-stack.yml pins: uv 0.13.5, ruff 0.17.2, jq-1.8.2, NVIM v0.12.5, pyrefly 1.3.1, basedpyright 1.40.1, ansible-lint 26.10.1, 2.1.308 (Claude Code), grype 0.117.0 and syft 1.51.0. |
| 3 | dev | Run `echo $DISABLE_AUTOUPDATER`. | `1`. |
| 4 | dev | Run `cat ~/.bashrc.d/claude-code.sh`. | The file sets `DISABLE_AUTOUPDATER=1`, `ANTHROPIC_API_KEY` to the surrogate key and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. |

## Evidence left behind

None.

## Notes

The versions in step 2 are the pins when this test was written. If python-stack.yml pins another
version, the playbook's version is the expected result.

The automated test reads the pins from python-stack.yml itself, so it does not go stale. This test
is for a person who wants to see the versions.
