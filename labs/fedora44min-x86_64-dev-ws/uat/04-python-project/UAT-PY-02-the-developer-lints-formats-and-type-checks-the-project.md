---
id: UAT-PY-02
title: The developer lints, formats and type-checks the project from the shell
suite: 04-python-project
stack: python-stack
features:
- SBX-PY-02
personas:
- dev
priority: P1
disruptive: false
automated: none
leaves: A [tool.pyrefly] table in ~/uat-py/pyproject.toml.
---

# UAT-PY-02 The developer lints, formats and type-checks the project from the shell

## Story

As the developer, I want to run the linter, the formatter and two type checkers from the shell, so
that I can check the whole project as the pipeline does, not only the open file.

## Preconditions

1. UAT-PY-01 passes. The project `~/uat-py` exists.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && ruff check . && ruff format --check .`. | `All checks passed!`, then `1 file already formatted`. |
| 2 | dev | Run `pyrefly init`. | `Config written to /home/dev/uat-py/pyproject.toml`, then `INFO 0 errors`. |
| 3 | dev | Run `basedpyright`. | `0 errors, 0 warnings, 0 notes`. |
| 4 | dev | Run `cp src/uat_py/__init__.py /tmp/uat-init.py`, then `printf 'import os\n\ndef f() -> int:\n    return "x"\n' >> src/uat_py/__init__.py`. | The file has a type error and an unused import. |
| 5 | dev | Run `ruff check .`. | Two findings in `src/uat_py/__init__.py`: `I001` (the import block is un-sorted or un-formatted) and `F401` (`os` imported but unused). `Found 2 errors.` |
| 6 | dev | Run `pyrefly check`. | One error at `return "x"`: the literal is not assignable to `int`. `INFO 1 error`. |
| 7 | dev | Run `basedpyright`. | One error: `"Literal['x']" is not assignable to "int" (reportReturnType)`. |
| 8 | dev | Run `mv /tmp/uat-init.py src/uat_py/__init__.py`. Run `ruff check . && pyrefly check`. | `All checks passed!` and `INFO 0 errors`. |

## Evidence left behind

The `[tool.pyrefly]` table that `pyrefly init` wrote in `pyproject.toml`. UAT-EDIT-01 explains why
the editor needs it.

## Notes

`ruff`, `pyrefly` and `basedpyright` are on dev's PATH from `~/.local/bin`, at the versions that
python-stack.yml pins (UAT-PY-04). The project does not need them as dependencies.
