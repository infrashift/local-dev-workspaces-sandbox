---
id: "01a17e52-1725-73df-be18-fe80572f69f7"
title: "upstream_github_mcp failed on its first apply: ansible_managed in copy, and SELinux denied stunnel its credentials"
type: "issue"
tags:
  - "issue"
  - "upstream_github_mcp"
  - "selinux"
  - "stunnel"
  - "ansible"
created: "2026-10-27T12:04:31-05:00"
timestamp: "2026-10-27T12:04:31-05:00"
description: "The new role's first real run failed twice: a copy task used ansible_managed (defined only for template), and SELinux's stunnel_t may not read systemd credential files, so stunnel could not open its LoadCredential configuration."
x:
  severity: "medium"
  priority: "P1"
  state: "fixed"
  origin: "new code (upstream_github_mcp, this change)"
  found: "2026-10-27, first make -f lab-provision.mk apply"
---

# upstream_github_mcp failed on its first apply: ansible_managed in copy, and SELinux denied stunnel its credentials

# upstream_github_mcp failed on its first apply: ansible_managed in copy, and SELinux denied stunnel its credentials

**Severity medium, P1, fixed.** New code (the self-hosted GitHub MCP server on upstream-1). Both faults first showed on `make -f lab-provision.mk apply`, because lint and dry runs cannot reach a VM's SELinux policy.

## What happens
1. `Write stunnel's configuration` was a `copy` with inline `content` that opened with `{{ ansible_managed }}`. That variable exists only while the `template` module renders, so the task failed: `'ansible_managed' is undefined`.
2. The stunnel unit used `DynamicUser=` and `LoadCredential=`, like the old mock server's. Fedora confines `/usr/bin/stunnel` (`stunnel_exec_t`) to `stunnel_t`, which may not read the credential files (`init_var_run_t`). The journal showed `Cannot open configuration file`, and `AVC ... denied { read } ... scontext=stunnel_t tcontext=init_var_run_t`.

## Fix
1. `templates/stunnel.conf.j2`. `scripts/check-role-contract.sh` now fails on `ansible_managed` in a role's `tasks/` or `vars/`.
2. stunnel's files live under `/etc/stunnel/` (labelled `stunnel_etc_t`). stunnel starts as root to read the key, then drops to `nobody` with `setuid`/`setgid`. The unit keeps `CapabilityBoundingSet=CAP_SETUID CAP_SETGID` and its other hardening. The GitHub MCP server itself keeps `DynamicUser`. The stale `/etc/ai-sandbox-github-mcp/` from the failed run, which held a copy of the test key, was removed by hand.

## Verified
2026-10-27, upstream-1: both units active, stunnel running as `nobody`, no new AVC after the fix, and the role's own check passed: a request without a token through TLS gets the server's Bearer 401. A re-run changed nothing.

## Related
- [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md), [Guest Roles](/tooling/guest-roles--01a166e751e0.md)
