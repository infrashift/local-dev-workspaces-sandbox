---
id: UAT-EDIT-02
title: The editor shows ruff's findings and formats Python with ruff
suite: 03-python-editing
stack: python-stack
features:
- SBX-EDIT-02
personas:
- dev
priority: P2
disruptive: false
automated: none
leaves: Nothing, if step 7 is done.
---

# UAT-EDIT-02 The editor shows ruff's findings and formats Python with ruff

## Story

As the developer, I want lint findings and formatting in the editor, so that the code is clean
before I commit it and a reviewer does not comment on style.

## Preconditions

1. UAT-EDIT-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `mkdir ~/uat-edit`. In the left pane, run `:e ~/uat-edit/style.py`. Type this and do not save: <br>`import os,sys`<br>`def add(a,b):`<br>`    return a+b`<br>`print( add(1,2) )` | Line 1 shows three findings from Ruff: `os` imported but unused, `sys` imported but unused, and the import block is un-sorted or un-formatted. |
| 2 | dev | Put the cursor on line 1 and press `<leader>ca` (`Space c a`). | The code actions include fixes from ruff, such as `Remove unused import`. |
| 3 | dev | Press `Esc`. Press `<leader>co`. | ruff organizes the imports. |
| 4 | dev | Save with `:w`. | Before the write, ruff formats the file: `a + b`, two blank lines before `def`, and `print(add(1, 2))`. |
| 5 | dev | Press `<leader>uf` (`Space u f`). Add `x=1` at the end and save. Press `<leader>uf` again. | With autoformat off, the line stays `x=1`. The second press turns autoformat back on. |
| 6 | dev | Press `<leader>cf` (`Space c f`). | ruff formats the buffer now: the line becomes `x = 1`. |
| 7 | dev | Run `:bd!`. In the right pane, run `rm -r ~/uat-edit`. | The directory is gone. |

## Evidence left behind

None.

## Notes

LazyVim uses ruff's language server (`vim.g.lazyvim_python_ruff = "ruff"`) for both the findings
and the formatting. No other Python formatter is installed.

`<leader>` is the space key (`lua/config/options.lua`).
