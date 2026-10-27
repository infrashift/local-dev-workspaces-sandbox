---
id: UAT-GIT-02
title: The developer commits, the push is refused because the PAT is read-only, and git keeps the surrogate
suite: 06-github
stack: python-stack
features:
- SBX-GIT-01
personas:
- dev
priority: P1
disruptive: false
automated: tests/guest/sandbox/test_scenarios.py::test_git_cannot_erase_the_surrogate
leaves: A local commit in ~/uat-git/private-scratch-1. Nothing reaches GitHub.
---

# UAT-GIT-02 The developer commits, the push is refused because the PAT is read-only, and git keeps the surrogate

## Story

As the security officer, I want the sandbox to read the repositories but not write to them, so that
an agent's mistake or a prompt injection cannot change the code on GitHub.

## Preconditions

1. UAT-GIT-01 passes. The clones are in `~/uat-git`.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-git/private-scratch-1 && git switch -c uat-git-02`. | `Switched to a new branch 'uat-git-02'`. |
| 2 | dev | Run `echo uat >> README.md && git -c user.name=uat -c user.email=uat@example.invalid commit -am 'UAT-GIT-02'`. | git makes the commit locally. |
| 3 | dev | Run `GIT_TERMINAL_PROMPT=0 git push -u origin uat-git-02`. | GitHub refuses the push with 403, for example `remote: Permission to infrashift/private-scratch-1.git denied to <login>.` and `The requested URL returned error: 403`. git asks for no password. |
| 4 | dev | Run `printf 'protocol=https\nhost=github.com\npath=infrashift/private-scratch-1\n\n' \| git credential fill`. | `username=claude` and `password=surrogate-github-git-scratch-1`. The failed push did not erase the surrogate. |
| 5 | dev | Run `git fetch`. | It works. Reads still work after the refused write. |
| 6 | dev | Run `git switch - && git branch -D uat-git-02 && git checkout README.md`. | The clone is back on its default branch with no local change. |

## Evidence left behind

None, if step 6 is done.

## Notes

The PAT behind each surrogate has the permissions Contents and Metadata, read-only (lab README,
"Before you start"). GitHub refuses the write, not the gateway.

After a refused request, git runs `credential reject`. A normal credential store would then delete
the credential. The sandbox's helper answers `get` only, so the surrogate stays. See the issue
[git's credential store erased the surrogates after a 401](../../../../.okfw/issues/gits-credential-store-erased-the-surrogates-after-a-401--01a17e787861.md).
