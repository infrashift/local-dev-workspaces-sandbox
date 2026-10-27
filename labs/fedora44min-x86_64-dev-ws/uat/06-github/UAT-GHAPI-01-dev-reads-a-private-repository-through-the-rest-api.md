---
id: UAT-GHAPI-01
title: The developer reads a private repository and a file through the GitHub REST API
suite: 06-github
stack: python-stack
features:
- SBX-GHAPI-01
personas:
- dev
priority: P2
disruptive: false
automated: tests/guest/sandbox/test_scenarios.py::test_github_api_reads_the_repository
leaves: Nothing. The scenario only reads.
---

# UAT-GHAPI-01 The developer reads a private repository and a file through the GitHub REST API

## Story

As the developer, I want to script against the GitHub API with the token in my environment, so that
I can automate reads of issues, files and commits as I do with my own token.

## Preconditions

1. UAT-GIT-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `H="Authorization: Bearer $AI_SANDBOX_GITHUB_API_SCRATCH_1_SURROGATE"`. | |
| 2 | dev | Run `curl -sS -H "$H" https://api.github.com/repos/infrashift/private-scratch-1 \| jq -r '[.full_name, .private, .visibility] \| @tsv'`. | `infrashift/private-scratch-1  true  private`. |
| 3 | dev | Run `curl -sS -H "$H" https://api.github.com/repos/infrashift/private-scratch-1/commits?per_page=1 \| jq -r '.[0].sha'`. | A commit SHA, the same as `git -C ~/uat-git/private-scratch-1 rev-parse origin/HEAD`. |
| 4 | dev | Run `curl -sS -H "$H" https://raw.githubusercontent.com/infrashift/private-scratch-1/HEAD/README.md`. | The README, which starts with `# private-scratch-1`. |
| 5 | dev | Run `curl -sS -o /dev/null -w '%{http_code}\n' https://api.github.com/repos/infrashift/private-scratch-1`. | `404`. Without the surrogate, GitHub does not show the private repository. |
| 6 | dev | Run `echo $AI_SANDBOX_GITHUB_API_SCRATCH_1_SURROGATE`. | `surrogate-github-api-scratch-1`. The token in the environment is a surrogate. |

## Evidence left behind

None.

## Notes

The api surrogate is valid on `api.github.com` and `raw.githubusercontent.com`. The git surrogate
works on the API too (Basic authentication), as the automated test shows.
