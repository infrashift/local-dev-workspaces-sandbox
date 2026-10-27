---
id: "01a17de1-d1cd-7cf9-b08f-a422fd52ad70"
title: "test_ca_trust probed an unrendered Jinja URL"
type: "issue"
tags:
  - "issue"
  - "ca_trust"
  - "pytest"
  - "guest-tests"
created: "2026-10-27T10:01:53-05:00"
timestamp: "2026-10-27T10:01:53-05:00"
description: "tests/guest/baseline/test_ca_trust.py passed vm-baseline.yml's trust_probe_urls to curl as written, so it would have probed the literal '{{ sandbox_fedora_mirror }}/' and failed."
x:
  severity: "low"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (tests/guest/baseline)"
  found: "2026-10-27, code reading while adding test_tls_inspection"
---

# test_ca_trust probed an unrendered Jinja URL

# test_ca_trust probed an unrendered Jinja URL

**Severity low, P2, fixed.** Found by reading the code; the guest suite had not run on the Linux lab yet.

## What happens
`lab.play_vars()` returns a playbook's `vars:` as YAML, unrendered. One of `trust_probe_urls` is `"{{ sandbox_fedora_mirror }}/"`, a group_vars reference, which curl cannot fetch.

## Fix
`lab.render()` resolves plain `{{ name }}` references to group_vars (all, then the group). `test_ca_trust` and the new `test_tls_inspection` render each probe URL with it. In the same change, `lab.role_params()` gained a `key=value` match: `vm-baseline.yml` now applies `ca_trust` twice, and the first entry is the TLS-inspection one.

## Related
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
