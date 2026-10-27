---
id: "01a17f01-fd7d-7d5d-ae4a-7258ea4abd42"
title: "The lazyvim lockfile names nvim-jdtls, which the spec never installs"
type: "issue"
tags:
  - "issue"
  - "lazyvim"
  - "neovim"
  - "python-stack"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:34:29-05:00"
description: "test_lazyvim_plugins_are_at_their_locked_commits failed because it checked every plugin in the role's lazy-lock.json, including the lang.java-only nvim-jdtls a Python image never installs; it now checks only the plugins the spec names, as the role does."
x:
  severity: "low"
  priority: "P3"
  state: "fixed"
  origin: "pre-existing (lazyvim role / python-stack test)"
  found: "2026-10-27, python-stack suite after the gateway hardening"
---

# The lazyvim lockfile names nvim-jdtls, which the spec never installs

**Severity low, P3, fixed.** It predates the 2026-10-27 gateway hardening, and is unrelated to it.
Found by running `make -f lab-provision-verify.mk STACK=python-stack` after that work.

## What happens
1. `tests/guest/python-stack/test_python_stack.py::test_lazyvim_plugins_are_at_their_locked_commits`
   expects every plugin named in the role's `lazy-lock.json` checked out at its commit.
2. The lockfile names `nvim-jdtls` (the Java extra), but LazyVim's spec on fedora-dev-1 does not:
   `require("lazy.core.config").spec.plugins["nvim-jdtls"]` is nil, and the plugin is not disabled
   either. So lazy.nvim never installs it. `~/.local/share/nvim/lazy/nvim-jdtls` does not exist, and
   the test reports `{'nvim-jdtls': ''}`.
3. `make -f lab-provision.mk play PLAYBOOK=python-stack` finds nothing to change: the role restores
   what the spec names.

At the time, the lazyvim role's files had uncommitted edits (`extras/java.lua`, `extras.lua.j2`,
`lazy.lua`, …). They turned out to be comment-only (the headers renamed from tf-labs to ai-sandbox),
not work on the Java extra.

The role was right and the test was wrong. The lockfile covers every supported extra by design, and
the role's restore already checks only the plugins the spec names (`lazyvim_lua_spec_plugins` in
`vars/main.yml`): see the comment above "Check each plugin's checked-out commit" in `tasks/main.yml`.

## Fix
The test asks lazy.nvim on the guest for its spec with the role's own query
(`lab.role_vars("guest", "lazyvim")["lazyvim_lua_spec_plugins"]`), and checks the commit of each
plugin in both the spec and the lockfile. It still requires the installed lockfile to equal the
role's, and it fails if the spec can't be read or lacks lazy.nvim or LazyVim, so a broken install
can't pass with an empty spec. The role is unchanged.

## Verified
2026-10-27: `make -f lab-provision.mk lint` is green, and `make -f lab-provision-verify.mk
STACK=python-stack` passed with 61 passed and 8 skipped. On fedora-dev-1 the spec covers 33 of the
34 locked plugins; `nvim-jdtls` is the only one left out.

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
