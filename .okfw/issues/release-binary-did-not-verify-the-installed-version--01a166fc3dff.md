---
id: "01a166fc-3dff-7f1e-9f3c-909a9cdc7d2f"
title: "release_binary did not verify the installed version"
type: "issue"
tags:
  - "issue"
  - "host-roles"
  - "ruff"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "The release_binary host role never checked that the requested version was installed, and masked a missing files list with default([name])."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed-unverified"
  origin: "pre-existing (release_binary role)"
  found: "2026-10-22, role contract rewrite"
---

# release_binary did not verify the installed version

**Severity medium, P2, fixed-unverified.** A wrong or partial install went unnoticed until ruff was used.

## What happens
The role gated its install on `--version`, but asserted nothing afterwards. A tarball that held a different version, or no binary matching the pattern, would "succeed". `release_binary_files | default([release_binary_name], true)` meant an unset parameter silently became a guess.

## Fix
`release_binary_files` is now mandatory. The role asserts that the tarball holds exactly the requested binaries and that the published digest is 64 hex characters, and it finishes with an anchored assert on the installed version.

## Verified
Lint and the role-contract checker pass. The role runs only on macOS: still to run on the Mac (make -f lab-bootstrap.mk check).

## Related
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)
