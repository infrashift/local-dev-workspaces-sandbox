---
id: UAT-SESS-03
title: The developer turns off the tmux start for one login or for all logins
suite: 02-dev-session
stack: python-stack
features:
- SBX-SESS-02
personas:
- dev
priority: P3
disruptive: false
automated: none
leaves: Nothing, if step 6 is done.
---

# UAT-SESS-03 The developer turns off the tmux start for one login or for all logins

## Story

As the developer, I want to log in to a plain shell when I need one, so that a file copy, a quick
check or a different terminal setup is not forced into the tmux layout.

## Preconditions

1. UAT-SESS-01 passes.
2. `Include config.d/*` is in the operator's `~/.ssh/config` (README procedure 1, step 5), so the
   host alias `local.fedora44min-x86_64-dev-ws.dev` works with plain `ssh`.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Run `ssh -t local.fedora44min-x86_64-dev-ws.dev 'DEV_SESSION=off exec bash -l'`. | A plain bash prompt, not tmux. |
| 2 | dev | Run `echo "${TMUX:-none}"`, then `exit`. | `none`. The session ends. |
| 3 | dev | Run `ssh local.fedora44min-x86_64-dev-ws.dev 'echo $TMUX; tty'`. | An empty line, then `not a tty`. A command without a terminal never starts tmux. |
| 4 | dev | Run `make -f lab-provision.mk ssh`. In the right pane, run `mkdir -p ~/.config/dev-session && touch ~/.config/dev-session/disabled`. Press `Ctrl-b d`. | The session ends. |
| 5 | dev | Run `make -f lab-provision.mk ssh`. | A plain bash prompt, not tmux. |
| 6 | dev | Run `rm ~/.config/dev-session/disabled`, then `exit`. Run `make -f lab-provision.mk ssh`, then press `Ctrl-b d`. | The second login opens the tmux layout again. |

## Evidence left behind

None.

## Notes

`DEV_SESSION=off` cannot be sent as an ssh environment variable: the guest's sshd accepts only
`COLORTERM` (`sudo sshd -T | grep acceptenv`). That is why step 1 sets it in the remote command.

The hook also skips VS Code's and JetBrains' integrated terminals. This test does not cover them.
