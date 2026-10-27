---
id: UAT-AI-01
title: The developer starts Claude Code with the surrogate key and gets an answer
suite: 07-claude-code
stack: python-stack
features:
- SBX-AI-01
- SBX-ISO-02
personas:
- dev
- claude
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_scenarios.py::test_anthropic_api_accepts_the_surrogate_key
- tests/guest/sandbox/test_scenarios.py::test_anthropic_without_a_key_is_refused_by_the_gateway
leaves: Claude Code's onboarding state in ~/.claude.json, and the project ~/uat-py marked as trusted.
---

# UAT-AI-01 The developer starts Claude Code with the surrogate key and gets an answer

## Story

As the developer, I want to use Claude Code in the sandbox as I do on my own machine, so that the
agent works on the code while the real API key stays on the host.

## Preconditions

1. UAT-PY-01 passes. The project `~/uat-py` exists.
2. README procedure 4 is done: the Anthropic API key is in Vault.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `echo $ANTHROPIC_API_KEY`. | `sk-ant-surrogate-claude-code`, the surrogate. |
| 2 | dev | Run `cd ~/uat-py && claude`. | Claude Code starts. On the first start it asks for a theme, asks whether to use the API key from the environment, and asks whether you trust the folder. Choose a theme, **Yes** for the key, and **Yes** to trust `~/uat-py`. |
| 3 | dev | Type `/status`. | The status shows the API key from `ANTHROPIC_API_KEY` as the authentication, and version 2.1.308. Press `Esc`. |
| 4 | claude | Type the prompt `In one sentence, what does this project do?` | Within a few seconds, an answer that names the project `uat-py` and its `main` function, which prints a greeting. No error about the API key, the network or a certificate. |
| 5 | dev | Type `/exit`. | Claude Code ends. |
| 6 | dev | Run `curl -sS -o /dev/null -w '%{http_code}\n' https://api.anthropic.com/v1/models`. | `401`. Without a key, the gateway itself refuses. |

## Evidence left behind

Claude Code's onboarding state in `~/.claude.json`, and `~/uat-py` as a trusted folder. The next
start does not ask again.

## Notes

If step 4 gives no answer, run `claude -p hi --debug` and read the newest file in
`~/.claude/debug/`. A TLS error such as `unsupported name constraint type` means that Claude Code's
runtime refuses the gateway's certificate chain, although curl and Python accept it. See the fixed
issue [Claude Code refuses the gateway CA's name constraints](../../../../.okfw/issues/claude-code-refuses-the-gateway-cas-name-constraints--01a17f21b808.md).

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` keeps Claude Code from calling hosts that are not on
the allow list (telemetry, error reports, the update check).
