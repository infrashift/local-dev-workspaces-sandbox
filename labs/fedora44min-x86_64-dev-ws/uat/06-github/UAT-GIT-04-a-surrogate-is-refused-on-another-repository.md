---
id: UAT-GIT-04
title: A repository's surrogate is refused on another repository and on another host
suite: 06-github
stack: python-stack
features:
- SBX-GIT-03
personas:
- dev
priority: P1
disruptive: false
automated:
- tests/guest/sandbox/test_anti_replay.py::test_surrogate_is_refused_on_another_repository
- tests/guest/sandbox/test_anti_replay.py::test_surrogate_is_refused_off_its_hosts
- tests/guest/sandbox/test_anti_replay.py::test_path_tricks_cannot_hide_another_repository
leaves: Nothing. The scenario only sends refused requests.
---

# UAT-GIT-04 A repository's surrogate is refused on another repository and on another host

## Story

As the security officer, I want each surrogate to work for one repository and its hosts only, so
that a surrogate that leaks from one task cannot reach another repository or service.

## Preconditions

1. UAT-GIT-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://claude:surrogate-github-git-scratch-1@github.com/infrashift/private-scratch-2`. | `remote: ai-sandbox gateway: surrogate repository mismatch` and `The requested URL returned error: 403`. |
| 2 | dev | Run `curl -sS -H "Authorization: Bearer $AI_SANDBOX_GITHUB_API_SCRATCH_1_SURROGATE" https://api.github.com/repos/infrashift/private-scratch-2`. | `ai-sandbox gateway: surrogate repository mismatch`. |
| 3 | dev | Run `curl -sS --path-as-is -H "Authorization: Bearer $AI_SANDBOX_GITHUB_API_SCRATCH_1_SURROGATE" https://api.github.com/repos/infrashift/private-scratch-1/../../infrashift/private-scratch-2/commits`. | `ai-sandbox gateway: surrogate repository mismatch`. A path trick does not hide the other repository. |
| 4 | dev | Run `curl -sS -H "Authorization: Bearer $AI_SANDBOX_GITHUB_API_SCRATCH_1_SURROGATE" https://api.anthropic.com/v1/models`. | `ai-sandbox gateway: surrogate host mismatch`. |
| 5 | dev | Run `curl -sS -H 'Authorization: Bearer surrogate-nobody-issued' https://api.github.com/user`. | `ai-sandbox gateway: unknown or revoked surrogate`. |

## Evidence left behind

None.

## Notes

Each answer starts with `ai-sandbox gateway:`: Envoy answers itself, and no request reaches GitHub
or Anthropic. Each refusal is in Envoy's access log on the host (`journalctl -u envoy`), as a
`gateway` line with the status 403.

The remote MCP servers do not check the repository in the gateway. Their PAT limits them to their
repository. UAT-MCP-03 covers that case.
