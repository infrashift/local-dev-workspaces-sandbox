---
id: "01a166fc-3e0c-7c00-a90a-7472a71e2f44"
title: "ca_trust verified anchors with openssl verify on stdin"
type: "issue"
tags:
  - "issue"
  - "ca_trust"
  - "pki"
  - "guest-roles"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "The ca_trust role's trust-store check fed each certificate to `openssl verify` on stdin, which OpenSSL 3 does not read, so every certificate looked untrusted."
x:
  severity: "low"
  priority: "P1"
  state: "fixed"
  origin: "new code (ca_trust role, this change)"
  found: "2026-10-22, KVM test VM, first real apply"
---

# ca_trust verified anchors with openssl verify on stdin

**Severity low, P1, fixed.** Caught by the role's own assert on the first real run; never shipped.

## Fix
Verify the installed anchor files (`openssl verify -partial_chain -CAfile <bundle> <anchor>`), which is also the thing that needs proving.

## Verified
2026-10-23, KVM test VM: ca_trust installed three anchors (a two-certificate chain plus mitmproxy's CA), all three passed openssl verify, and all six probe URLs answered over verified TLS.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
