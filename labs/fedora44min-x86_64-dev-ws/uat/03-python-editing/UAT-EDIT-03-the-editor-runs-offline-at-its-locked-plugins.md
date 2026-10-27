---
id: UAT-EDIT-03
title: The editor starts with its plugins at the locked commits and installs nothing at run time
suite: 03-python-editing
stack: python-stack
features:
- SBX-EDIT-03
personas:
- dev
priority: P2
disruptive: false
automated: tests/guest/python-stack/test_python_stack.py::test_lazyvim_plugins_are_at_their_locked_commits
leaves: Nothing. The scenario only reads the editor's state.
---

# UAT-EDIT-03 The editor starts with its plugins at the locked commits and installs nothing at run time

## Story

As the operator, I want the editor to run only the plugins and tools that the playbook pinned, so
that the sandbox runs no code that nobody reviewed or recorded.

## Preconditions

1. UAT-SESS-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the left pane, run `:Lazy`. | The list shows the installed plugins, with no plugin under "Missing" and no update notice. Press `q`. |
| 2 | dev | Run `:Mason`. | Nothing is installed, and nothing is installing. Press `q`. |
| 3 | dev | In the right pane, run `ls ~/.local/share/nvim/mason/bin`. | `No such file or directory`. Mason has installed no tool. |
| 4 | dev | Run `jq -r .LazyVim.commit ~/.config/nvim/lazy-lock.json; git -C ~/.local/share/nvim/lazy/LazyVim rev-parse HEAD`. | The same commit twice. |
| 5 | dev | Run `grep -nE 'checker|change_detection' ~/.config/nvim/lua/config/lazy.lua`. | `checker = { enabled = false }` and `change_detection = { enabled = false }`. |
| 6 | dev | In the left pane, open a Lua file: `:e ~/.config/nvim/init.lua`. | No error about `lua_ls`. LazyVim does not start a Lua language server, because none is installed. Run `:bd`. |

## Evidence left behind

None.

## Notes

The automated test checks each plugin's commit against the lockfile. Only this test checks that
the editor does not try to install anything when you use it.

The language servers and formatters come from the roles and are on `PATH`: pyrefly, ruff,
basedpyright, ansible-lint, stylua and shfmt. See `plugins/offline.lua` in the lazyvim role.
