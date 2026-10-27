---
id: UAT-SESS-02
title: After a dropped connection, the next login reattaches to the same session with the work in it
suite: 02-dev-session
stack: python-stack
features:
- SBX-SESS-01
personas:
- dev
priority: P1
disruptive: false
automated: none
leaves: The tmux session dev on fedora-dev-1. The scratch buffer is discarded in step 6.
---

# UAT-SESS-02 After a dropped connection, the next login reattaches to the same session with the work in it

## Story

As the developer, I want a dropped connection to leave my editor and my shell running, so that a
network fault or a closed laptop does not lose unsaved work or a running command.

## Preconditions

1. UAT-SESS-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Run `make -f lab-provision.mk ssh`. | The session from UAT-SESS-01 opens, not a new one. |
| 2 | dev | In the left pane, run `nvim` if the pane is a shell. Run `:enew`, type `unsaved work`, and do not save. | The buffer shows `unsaved work` and is marked as modified. |
| 3 | dev | In the right pane, run `sleep 600`. | The command runs. |
| 4 | dev | Drop the connection: press `Enter`, then `~` and `.`. | ssh prints `Connection to … closed.` You are back on the host. |
| 5 | dev | Run `make -f lab-provision.mk ssh`. | The same two panes. The left pane still shows `unsaved work`. The right pane still runs `sleep 600`. |
| 6 | dev | In the right pane, press `Ctrl-c`. In the left pane, run `:bd!`. Press `Ctrl-b d`. | The sleep stops, the buffer is discarded, and the session ends. |

## Evidence left behind

The tmux session `dev`, detached.

## Notes

The tmux server runs on the guest, so the session lives as long as the VM runs. UAT-LIFE-02 shows that
a stop of the VM ends it.
