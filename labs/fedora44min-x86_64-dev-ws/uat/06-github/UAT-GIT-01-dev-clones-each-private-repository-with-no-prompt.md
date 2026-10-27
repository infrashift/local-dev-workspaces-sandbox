---
id: UAT-GIT-01
title: The developer clones each private repository with no prompt and no real credential
suite: 06-github
stack: python-stack
features:
- SBX-GIT-01
- SBX-ISO-02
personas:
- dev
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_scenarios.py::test_repository_refuses_an_anonymous_clone
- tests/guest/sandbox/test_scenarios.py::test_repository_clones_with_its_surrogate
leaves: The clones in ~/uat-git on fedora-dev-1. UAT-GIT-02 uses them.
---

# UAT-GIT-01 The developer clones each private repository with no prompt and no real credential

## Story

As the developer, I want git to work with the private repositories as it does on my own machine, so
that I can work on the code although the sandbox never holds a real token.

## Preconditions

1. UAT-LIFE-01 passes.
2. README procedure 4 is done: each repository's PAT is in Vault.
3. `~/uat-git` does not exist on fedora-dev-1.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `mkdir ~/uat-git && cd ~/uat-git`. | |
| 2 | dev | Run `git clone https://github.com/infrashift/private-scratch-1`. | git clones the repository. It asks for no user name and no password. |
| 3 | dev | Do step 2 for `private-scratch-2` and `private-scratch-3`. | Both clone with no prompt. |
| 4 | dev | Run `ls */README.md`. | A `README.md` in each of the three clones. |
| 5 | dev | Run `git -C private-scratch-1 remote -v`. | `https://github.com/infrashift/private-scratch-1`. The URL holds no credential. |
| 6 | dev | Run `cat ~/.config/ai-sandbox/git-surrogates`. | Lines like `https://claude:surrogate-github-git-scratch-1@github.com/infrashift/private-scratch-1`, one per repository and host. Each password starts with `surrogate-`. |
| 7 | dev | Run `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/infrashift/private-scratch-1`. | git fails with no credential. The repository is private, so the clones in steps 2 and 3 used the surrogates. |

## Evidence left behind

The three clones in `~/uat-git`.

## Notes

git sends the surrogate of the repository in the URL path (`credential.https://github.com.useHttpPath`).
The gateway swaps it for the real PAT of that one repository. See
[Surrogate Credential Model](../../../../.okfw/concepts/surrogate-credential-model--01a17ecc92e2.md).

If step 2 fails with 401, the PAT in Vault is wrong or missing: the operator runs `make -f
lab-gateway.mk secrets NAME=private-scratch-1`.
