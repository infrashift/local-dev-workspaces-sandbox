---
id: UAT-LIFE-01
title: The operator sees the state of each lab VM and connects to it as dev and as admin
suite: 01-lab-lifecycle
stack: python-stack
features:
- SBX-LIFE-01
- SBX-SESS-01
personas:
- operator
- dev
- admin
priority: P1
disruptive: false
automated:
- tests/guest/baseline/test_vm.py
- tests/guest/baseline/test_users.py
leaves: Nothing. The scenario only reads the state and opens sessions.
---

# UAT-LIFE-01 The operator sees the state of each lab VM and connects to it as dev and as admin

## Story

As the operator, I want to see each lab VM's state and address and to open a session on it with one
command, so that I can start work without looking up addresses or keys.

## Preconditions

1. README procedures 1 to 8 are complete. The lab VMs are running.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | In the lab directory, run `make -f lab-provision.mk status`. | A table with the columns VM, STATE and IP. `fedora-dev-1` is `running` at `192.168.150.10`. `upstream-1` is `running` at `192.168.151.10`. |
| 2 | operator | Run `make -f lab-provision.mk ip`. | `192.168.150.10`, the sandbox VM's address. |
| 3 | dev | Run `make -f lab-provision.mk ssh`. | No password prompt and no host-key prompt. The session opens as `dev@fedora-dev-1` in the tmux session `dev` (UAT-SESS-01 checks the layout). |
| 4 | dev | In the shell pane, run `whoami; hostname`. | `dev` and `fedora-dev-1`. |
| 5 | dev | Run `sudo -n true`. | The command fails: `sudo: a password is required`. dev has no sudo. |
| 6 | dev | Run `tmux detach` (or press `Ctrl-b d`). | The ssh session ends. You are back on the host. |
| 7 | admin | Run `make -f lab-provision.mk ssh ROLE=admin`. | The session opens as `admin@fedora-dev-1` with no prompt. A tmux session starts here too (see Notes). |
| 8 | admin | In the shell pane, run `sudo -n true && echo ok`. | `ok`. admin has sudo without a password. |
| 9 | admin | Run `tmux kill-session`, then close the session. | The ssh session ends. |
| 10 | admin | Run `make -f lab-provision.mk ssh ROLE=admin VM=upstream-1`, then `hostname`. Close the session. | `upstream-1`. |

## Evidence left behind

None.

## Notes

The tmux login hook is in `/etc/profile.d/`, so it starts the editor and shell layout for admin too.
The editor pane of admin shows `bash: line 1: nvim: command not found`, then a shell: Neovim is
installed in dev's `~/.local/bin` only. The test accepts this. The wiki records it as an issue
([admin's dev-session editor pane cannot find nvim](../../../../.okfw/issues/admins-dev-session-editor-pane-cannot-find-nvim--01a17f21b814.md)).

The automated suites connect with the same keys and check the users and the VM, not the make targets
or the tmux session.
