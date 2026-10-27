---
id: UAT-PY-03
title: The developer adds pytest as a development dependency and runs the tests
suite: 04-python-project
stack: python-stack
features:
- SBX-PY-01
personas:
- dev
priority: P1
disruptive: false
automated: none
leaves: pytest in ~/uat-py's development dependencies, and ~/uat-py/tests/test_add.py.
---

# UAT-PY-03 The developer adds pytest as a development dependency and runs the tests

## Story

As the developer, I want to write and run unit tests in the sandbox, so that I can show that a change
works before I push it.

## Preconditions

1. UAT-PY-01 passes. The project `~/uat-py` exists.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && uv add --dev pytest`. | uv installs `pytest` and its dependencies. `pyproject.toml` has a `[dependency-groups]` table with `dev = ["pytest>=…"]`. |
| 2 | dev | Run `mkdir -p tests && printf 'def add(a: int, b: int) -> int:\n    return a + b\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n' > tests/test_add.py`. | The test file exists. |
| 3 | dev | Run `uv run pytest -q`. | `1 passed`. |
| 4 | dev | Change `== 5` to `== 6` in `tests/test_add.py`. Run `uv run pytest -q`. | `1 failed`. pytest shows `assert 5 == 6`. |
| 5 | dev | Change it back to `== 5`. Run `uv run pytest -q`. | `1 passed`. |

## Evidence left behind

pytest in the project's development dependencies, and `tests/test_add.py`. UAT-AI-02 uses them.

## Notes

`uv run` syncs the environment before it runs the command, so no separate install step is needed.
