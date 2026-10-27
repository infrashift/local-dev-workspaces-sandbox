---
id: UAT-GIT-03
title: The developer reads public GitHub repositories and archives without a credential
suite: 06-github
stack: python-stack
features:
- SBX-GIT-02
personas:
- dev
priority: P2
disruptive: false
automated: none
leaves: Nothing, if step 4 is done.
---

# UAT-GIT-03 The developer reads public GitHub repositories and archives without a credential

## Story

As the developer, I want to clone open-source code and download release archives, so that I can
read and use public projects in the sandbox.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd /tmp && git clone https://github.com/octocat/Hello-World`. | git clones the repository with no prompt. |
| 2 | dev | Run `curl -sSL -o hw.tgz -w '%{http_code} %{url_effective}\n' https://github.com/octocat/Hello-World/archive/HEAD.tar.gz`. | `200 https://codeload.github.com/octocat/Hello-World/tar.gz/<commit>`. The redirect to codeload works. |
| 3 | dev | Run `tar tzf hw.tgz`. | The archive lists `Hello-World-<commit>/README`. |
| 4 | dev | Run `rm -rf /tmp/Hello-World /tmp/hw.tgz`. | |

## Evidence left behind

None.

## Notes

github.com and codeload.github.com are gateway hosts with `anonymous: true`: a request with no
credential passes through the TLS gateway unchanged. git sends no surrogate for a path that has none
in `~/.config/ai-sandbox/git-surrogates`.

The anonymous requests count against GitHub's rate limit for the host's public address.
