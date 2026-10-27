---
id: "01a17de1-d1d5-75a8-9266-c67d7868a7d5"
title: "A looped assert would have printed a private key from the TLS-inspection chain"
type: "issue"
tags:
  - "issue"
  - "envoy_gateway"
  - "pki"
  - "security"
  - "ansible"
created: "2026-10-27T10:01:53-05:00"
timestamp: "2026-10-27T10:01:53-05:00"
description: "envoy_gateway's first chain check looped over every PEM object of TLS_INSPECTION_DIR, and a failed loop item is printed whole, so a private key put there by mistake would have landed in the playbook output."
x:
  severity: "medium"
  priority: "P1"
  state: "fixed"
  origin: "new code (envoy_gateway TLS-inspection chain, this change)"
  found: "2026-10-27, dry run with a test chain holding a key"
---

# A looped assert would have printed a private key from the TLS-inspection chain

# A looped assert would have printed a private key from the TLS-inspection chain

**Severity medium, P1, fixed before it shipped.** Caught 2026-10-27 by dry-running `envoy_gateway` against a throwaway chain file with a key appended.

## What happens
Ansible prints a failed loop result in full, including `item`. The check looped over the PEM objects, so a private key was an item. Worse, the `success_msg` parsed each item as a certificate, so the key made the task error out instead of failing the assert.

## Fix
As `ca_trust` already did: one assert with no loop checks that every PEM object is a certificate, and reports only the PEM headers it found. Only then does a loop check each certificate (unexpired, `CA:TRUE`). A re-run with the key showed `found ['-----BEGIN CERTIFICATE-----', '-----BEGIN PRIVATE KEY-----']`, and the key's body appeared nowhere in the log.

## Lesson
Never loop over values that may be secret: validate the whole list first, and print only what is safe.

## Related
- [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md)
