---
id: "01a166fc-3e06-76eb-a0b1-93e344c5ebf8"
title: "yamllint strict mode failed on existing role lines"
type: "issue"
tags:
  - "issue"
  - "lint"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "`make lint` runs yamllint -s, which fails on warnings, and fedora_cloud_image already had lines over the 120-character limit."
x:
  severity: "low"
  priority: "P3"
  state: "fixed"
  origin: "pre-existing (fedora_cloud_image role)"
  found: "2026-10-22, first lint run of this change"
---

# yamllint strict mode failed on existing role lines

**Severity low, P3, fixed.** `make lint` could not pass even before this change.

## Fix
The long lines are rewrapped (folded scalars, list-form argv). yamllint -s and ansible-lint (production profile) now pass over both role directories and the playbooks.

## Verified
2026-10-23: yamllint 1.38.0 -s and ansible-lint 26.10.1 (production profile) pass over both role directories and the playbooks.

## Related
- [Role Contract](/concepts/role-contract--01a166e751ce.md)
