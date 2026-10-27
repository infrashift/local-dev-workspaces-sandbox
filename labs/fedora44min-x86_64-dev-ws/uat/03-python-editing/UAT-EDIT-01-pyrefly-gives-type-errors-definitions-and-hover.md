---
id: UAT-EDIT-01
title: In a Python project, the editor shows pyrefly's type errors, definitions and hover
suite: 03-python-editing
stack: python-stack
features:
- SBX-EDIT-01
personas:
- dev
priority: P1
disruptive: false
automated: none
leaves: Nothing, if step 8 is done.
---

# UAT-EDIT-01 In a Python project, the editor shows pyrefly's type errors, definitions and hover

## Story

As the developer, I want the editor to show type errors as I type, so that I find a wrong type
before I run the code.

## Preconditions

1. UAT-SESS-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `mkdir ~/uat-edit && cd ~/uat-edit && printf '[project]\nname = "uat-edit"\nversion = "0.1.0"\nrequires-python = ">=3.14"\n\n[tool.pyrefly]\n' > pyproject.toml`. | The directory holds `pyproject.toml`. |
| 2 | dev | In the left pane, run `:cd ~/uat-edit`, then `:e app.py`. Type this and save with `:w`: <br>`def add(a: int, b: int) -> int:`<br>`    return a + b`<br><br><br>`total: str = add(1, 2)` | Within a few seconds, line 5 shows an error from Pyrefly: `int` is not assignable to `str`. |
| 3 | dev | Run `:checkhealth vim.lsp`. | Under "Active Clients", `pyrefly` and `ruff`. Close the health buffer with `:bd`. |
| 4 | dev | Put the cursor on `add` in line 5 and press `K`. | A float shows the signature `def add(a: int, b: int) -> int`. |
| 5 | dev | Press `gd`. | The cursor goes to line 1, the definition of `add`. |
| 6 | dev | Change line 5 to `total: int = add(1, 2)` and save. | The error goes away. |
| 7 | dev | In the right pane, run `pyrefly check`. | `INFO 0 errors`. |
| 8 | dev | In the left pane, run `:bd`. In the right pane, run `cd && rm -r ~/uat-edit`. | The directory is gone. |

## Evidence left behind

None.

## Notes

pyrefly shows type errors in the editor only in a project with a pyrefly configuration: a
`[tool.pyrefly]` table in `pyproject.toml`, or a `pyrefly.toml`. Without one, the editor shows only
hints such as `Import os may be unused`, and no type errors. The `pyrefly check` command reports
them either way. A project made by `uv init` (UAT-PY-01) has no `[tool.pyrefly]` table, so the
developer must add one.

The language server is pyrefly because python-stack.yml sets `lazyvim_python_lsp: pyrefly`.
basedpyright is installed too, for the command line (UAT-PY-02).
