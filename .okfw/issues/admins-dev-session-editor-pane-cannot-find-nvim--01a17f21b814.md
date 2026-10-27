---
id: "01a17f21-b814-7e6c-b594-56da8415c54a"
title: "admin's dev-session editor pane cannot find nvim"
type: "issue"
tags:
  - "issue"
  - "tmux"
  - "python-stack"
  - "uat"
created: "2026-10-27T15:51:18-05:00"
timestamp: "2026-10-27T15:51:18-05:00"
description: "The tmux login hook is system-wide, so admin's ssh login also starts dev-session, whose editor pane runs nvim, which is only on dev's PATH."
x:
  severity: "low"
  priority: "P3"
  state: "open"
  origin: "pre-existing (tmux and neovim roles in python-stack.yml)"
  found: "2026-10-27, writing the UAT specs (UAT-LIFE-01)"
---

# admin's dev-session editor pane cannot find nvim

**Severity low, P3, open.** admin gets a working shell, but the first thing it sees is an error.

## What happens
`make -f lab-provision.mk ssh ROLE=admin` opens the tmux layout too. The left pane shows
`bash: line 1: nvim: command not found`, then a login shell.

The tmux role writes its login hook to `/etc/profile.d/dev-session.sh`, for every account. The editor
pane runs `tmux_editor_pane_command` (`nvim`). The neovim role runs in the user lane and installs
Neovim in dev's `~/.local/bin` only.

## Options
- A `tmux_autostart_users` parameter (python-stack.yml: `[dev]`), checked in the hook.
- Fall back to a shell in `dev-session` when the editor command is not on PATH, without an error.

## Acceptance
- UAT-LIFE-01 step 7 opens a plain shell, or a layout with no error, for admin.

## Related
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
