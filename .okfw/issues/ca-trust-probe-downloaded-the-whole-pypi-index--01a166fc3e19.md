---
id: "01a166fc-3e19-7ce7-9b54-3f46098f20df"
title: "ca_trust probe downloaded the whole PyPI index"
type: "issue"
tags:
  - "issue"
  - "ca_trust"
  - "guest-roles"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "The ca_trust curl probe GET https://pypi.org/simple/, a 47 MB page, and timed out after 30 s."
x:
  severity: "low"
  priority: "P2"
  state: "fixed"
  origin: "new code (ca_trust role and vm-baseline.yml, this change)"
  found: "2026-10-22, KVM test VM"
---

# ca_trust probe downloaded the whole PyPI index

**Severity low, P2, fixed.** A false TLS failure from a probe that downloaded far more than it needed.

## Fix
curl now sends `--head`: the handshake and a status line are all the probe needs. The PyPI probe URL is `https://pypi.org/`.

## Verified
2026-10-23, KVM test VM: ca_trust installed three anchors (a two-certificate chain plus mitmproxy's CA), all three passed openssl verify, and all six probe URLs answered over verified TLS.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
