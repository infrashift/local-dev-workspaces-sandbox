---
id: UAT-AI-02
title: Claude adds a function with a test to the project and runs ruff, pyrefly and pytest itself
suite: 07-claude-code
stack: python-stack
features:
- SBX-AI-01
- SBX-PY-02
personas:
- dev
- claude
priority: P1
disruptive: false
automated: none
leaves: The function and the test that Claude wrote in ~/uat-py.
---

# UAT-AI-02 Claude adds a function with a test to the project and runs ruff, pyrefly and pytest itself

## Story

As the developer, I want Claude to change the code and check its own work with the project's tools,
so that I review a change that already passes the lint, the type check and the tests.

## Preconditions

1. UAT-AI-01 passes.
2. UAT-PY-02 and UAT-PY-03 pass. The project has a `[tool.pyrefly]` table and pytest.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && claude`. | Claude Code starts. |
| 2 | claude | Type the prompt `Add a function slugify(text: str) -> str to src/uat_py/__init__.py that lowercases the text and replaces each run of non-alphanumeric characters with one hyphen, without leading or trailing hyphens. Add tests in tests/test_slugify.py. Then run ruff check, pyrefly check and uv run pytest, and fix anything that fails.` | Claude shows each file edit and each command for approval. Allow them. |
| 3 | claude | Watch the commands that Claude runs. | Claude runs `ruff check`, `pyrefly check` and `uv run pytest`. The last results that it shows are `All checks passed!`, `0 errors` and all tests passed. |
| 4 | dev | Type `/exit`. In the right pane, run `ruff check . && pyrefly check && uv run pytest -q`. | All three pass. `pytest` runs the tests from UAT-PY-03 and the new tests. |
| 5 | dev | Run `uv run python -c 'from uat_py import slugify; print(slugify("  Hello, World!  "))'`. | `hello-world`. |

## Evidence left behind

`slugify` and `tests/test_slugify.py` in `~/uat-py`.

## Notes

This is the loop that the sandbox exists for: the agent edits and runs tools in the VM, with the
surrogates only. The tools that Claude runs are the ones on dev's PATH (UAT-PY-04).
