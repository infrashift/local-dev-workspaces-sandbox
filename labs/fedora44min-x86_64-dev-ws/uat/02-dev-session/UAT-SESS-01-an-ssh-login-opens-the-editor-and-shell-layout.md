---
id: UAT-SESS-01
title: An ssh login opens the tmux session with the editor on the left and a shell on the right
suite: 02-dev-session
stack: python-stack
features:
- SBX-SESS-01
personas:
- dev
priority: P1
disruptive: false
automated: tests/guest/python-stack/test_python_stack.py::test_tmux_config_loads
leaves: The tmux session dev on fedora-dev-1.
---

# UAT-SESS-01 An ssh login opens the tmux session with the editor on the left and a shell on the right

## Story

As the developer, I want each login to open my editor and a shell side by side, so that I start
work at once and do not set up the layout each time.

## Preconditions

1. UAT-LIFE-01 passes.
2. dev has no tmux session now. If `tmux ls` shows one, run `tmux kill-server` first.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Run `make -f lab-provision.mk ssh`. | The terminal shows two panes. The left pane is Neovim with the LazyVim dashboard. The right pane, about a third of the width, is a bash prompt in `~`. The left pane is active. |
| 2 | dev | In the right pane (click it, or press `Ctrl-b Right`), run `tmux display -p '#S #{window_panes}'`. | `dev 2`. |
| 3 | dev | Run `echo $TERM`. | `tmux-256color`. |
| 4 | dev | In the left pane, quit Neovim with `:qa`. | The left pane becomes a bash prompt. The layout stays: the pane does not close. |
| 5 | dev | Click each pane with the mouse. | The active pane follows the click. The mouse is on. |
| 6 | dev | Press `Ctrl-b d`. | tmux detaches and the ssh session ends. You are back on the host. |

## Evidence left behind

The tmux session `dev`, detached. UAT-SESS-02 reuses it.

## Notes

The automated test loads `/etc/tmux.conf` and checks that `dev-session` and the login hook exist.
It does not open a terminal, so only this test sees the layout.

If the terminal emulator's TERM is unknown on the guest (for example `xterm-ghostty`), `dev-session`
uses `xterm-256color` for tmux. The layout must still open.
