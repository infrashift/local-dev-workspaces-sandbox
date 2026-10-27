---
id: "01a17e78-7861-70b2-9353-b0890be9fa82"
title: "git's credential store erased the surrogates after a 401"
type: "issue"
tags:
  - "issue"
  - "git"
  - "surrogates"
  - "sandbox"
created: "2026-10-27T12:46:26-05:00"
timestamp: "2026-10-27T12:46:26-05:00"
description: "git's credential-store deletes an entry when the upstream refuses it, so one 401 removed a repository's surrogate from the sandbox; git now reads the surrogates through a get-only helper."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (sandbox_surrogates credential.helper=store)"
  found: "2026-10-27, first sandbox suite run"
---

# git's credential store erased the surrogates after a 401

# git's credential store erased the surrogates after a 401

**Severity medium, P2, fixed.** Pre-existing (sandbox_surrogates used `credential.helper=store`).

## What happens
When the upstream refuses a credential, git runs `credential reject`, and `credential-store` deletes the
matching line. During the fail-open Lua bug ([The surrogate filter failed open when its Lua script raised](/issues/the-surrogate-filter-failed-open-when-its-lua-script-raised--01a17e78784d.md))
GitHub answered 401 to the unswapped surrogates, and each repository's bare-path entry vanished from
`~/.git-credentials`: `could not read Username ... terminal prompts disabled`. The same would follow
any 401, for example an expired PAT, until the playbook ran again.

## Fix
The surrogates live in `~/.config/ai-sandbox/git-surrogates`. git's helper is get-only:
`!f() { if [ "$1" = get ]; then git credential-store --file=<that file> get; fi; }; f`, so `store` and
`erase` are no-ops. The former `~/.git-credentials` (written whole by the role) is removed.
`tests/guest/sandbox/test_scenarios.py::test_git_cannot_erase_the_surrogate` runs a `reject` and checks
that the surrogate still fills. A local test, in a throwaway HOME with askpass off, checked that `get`
answers, `reject` keeps the entry and `approve` writes nothing.
