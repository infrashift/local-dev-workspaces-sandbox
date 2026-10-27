---
id: UAT-CRED-01
title: The sandbox holds only surrogate credentials, in each place a tool reads them
suite: 10-credentials
stack: python-stack
features:
- SBX-ISO-02
personas:
- dev
- admin
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_isolation.py::test_guest_holds_exactly_the_surrogates
- tests/guest/sandbox/test_isolation.py::test_no_real_credential_on_the_guest
leaves: Nothing. The scenario only reads files.
---

# UAT-CRED-01 The sandbox holds only surrogate credentials, in each place a tool reads them

## Story

As the security officer, I want no real credential on the sandbox VM, so that an agent or a program
that reads every file on it still learns nothing that works outside the gateway.

## Preconditions

1. UAT-LIFE-01 passes.
2. UAT-AI-01 has run at least once, so that Claude Code has written its state.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `env \| grep -E '_SURROGATE=\|ANTHROPIC_API_KEY' \| sort`. | Ten `AI_SANDBOX_<NAME>_SURROGATE` variables (three each for private-scratch-1, -2 and -3, and `AI_SANDBOX_ANTHROPIC_SURROGATE`), and `ANTHROPIC_API_KEY=sk-ant-surrogate-claude-code`. Each value contains `surrogate`. |
| 2 | dev | Run `cut -d@ -f1 ~/.config/ai-sandbox/git-surrogates \| sort -u`. | `https://claude:surrogate-github-git-scratch-1`, `-2` and `-3`. |
| 3 | dev | Run `jq -r '.mcpServers[] \| (.env.GITHUB_PERSONAL_ACCESS_TOKEN // .headers.Authorization)' ~/.claude.json \| sort -u`. | `surrogate-github-api-scratch-<n>` and `Bearer surrogate-github-mcp-scratch-<n>` for n = 1 to 3. Nothing else. |
| 4 | dev | Run `ls ~/.git-credentials`. | `No such file or directory`. |
| 5 | admin | Run `make -f lab-provision.mk ssh ROLE=admin`. Run `sudo grep -rIlE 'github_pat_[A-Za-z0-9_]{40,}\|gh[pousr]_[A-Za-z0-9]{36}\|sk-ant-(api\|admin)[0-9]{2}-' /home /root /etc /tmp /var/tmp; echo $?`. | Only `1`: no file holds a string shaped like a real GitHub token or Anthropic key. |
| 6 | admin | Run `sudo grep -rIl 'sk-ant-' /home/dev/.claude* 2>/dev/null \| xargs -r sudo grep -ho 'sk-ant-[a-z0-9-]*' \| sort -u`. | Only `sk-ant-surrogate-claude-code`. Close the session. |

## Evidence left behind

None.

## Notes

A surrogate is not a secret: `ansible/vars/gateway.yml` publishes them all. Each works only through
the gateway, only on its hosts and, for GitHub, only on its repository (UAT-GIT-04).

Step 5 uses the same patterns as the automated test. Run it again after UAT-AI-02, when Claude Code
has written more state.
