---
id: "01a166fc-3df9-7638-9bb5-273cfbb5ea9c"
title: "socket_vmnet download could run with an empty checksum"
type: "issue"
tags:
  - "issue"
  - "socket_vmnet"
  - "supply-chain"
  - "host-roles"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "If SHA256SUMS lacked the tarball, the socket_vmnet role passed `sha256:` with no digest to get_url instead of failing; the lookup was also unanchored."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed-unverified"
  origin: "pre-existing (socket_vmnet role)"
  found: "2026-10-22, role contract rewrite"
---

# socket_vmnet download could run with an empty checksum

**Severity medium, P2, fixed-unverified.** The SHA-256 lookup could come back empty, and there was no check before the download used it.

## What happens
The digest was pulled from `SHA256SUMS` with an unanchored `regex_search` and `| default('')` straight into `checksum:`. A missing entry produced `checksum: "sha256:"`, and a sibling asset whose name extends the tarball's could match first (this fails closed, but with a confusing digest-mismatch error). ADR-006 in trusted-devcontainer-features records the same class of bug.

## Fix
The digest is resolved into a fact with the regex anchored to a whole line (`(?m)^<sha>\s+\*?<asset>$`), and the role asserts 64 hex characters before downloading. grype and syft use the same anchored lookup.

## Verified
Lint and the role-contract checker pass, and the anchored lookup was tested against the real v1.2.2 SHA256SUMS layout. The role itself runs only on macOS: still to run on the Mac (make -f lab-bootstrap.mk check).

## Related
- [Role Contract](/concepts/role-contract--01a166e751ce.md)
