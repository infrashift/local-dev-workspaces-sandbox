---
id: "01a166fc-3e13-735c-b537-50f6ea18c38e"
title: "ca_trust wrote anchors ending in a literal backslash-n"
type: "issue"
tags:
  - "issue"
  - "ca_trust"
  - "pki"
  - "guest-roles"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "A Jinja '\\n' inside a YAML folded scalar stayed a literal backslash-n, so every anchor file ended '-----END CERTIFICATE-----\\n' and OpenSSL could not decode it."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "new code (ca_trust role, this change)"
  found: "2026-10-22, KVM test VM, first real apply"
---

# ca_trust wrote anchors ending in a literal backslash-n

**Severity high, P1, fixed.** Shipped, it would have left the proxy CA untrusted while the files looked installed; the role's verify assert caught it.

## What happens
`'pem': item | trim ~ '\n'` sat in a `>-` folded scalar. YAML does no escape processing there, and ansible-core 2.21's templating did not unescape the Jinja literal either, so the PEM got the two characters `\` `n`. `update-ca-trust` skips a file it cannot parse, so the bundle silently lacked the certificates.

## Fix
Store the trimmed PEM, and add the newline in the copy task's double-quoted `content: "{{ item.pem }}\n"`, where YAML turns it into a real newline. Every other `'\n'` in the roles was checked: the only other one sits in a double-quoted scalar.

## Verified
2026-10-23, KVM test VM: ca_trust installed three anchors (a two-certificate chain plus mitmproxy's CA), all three passed openssl verify, and all six probe URLs answered over verified TLS.

## Recurred, and now linted
2026-10-27: the same construct came back four times in one change: the TLS-inspection chain split in
`ca_trust` and `envoy_gateway`, Envoy's public-upstream bundle, and `sandbox_surrogates`' git credential
request. None shipped. A render test in a scratch playbook showed the literal `\` `n`, and the fix was
double-quoted scalars again. `scripts/check-role-contract.sh` (part of `make -f lab-provision.mk lint`)
now fails on any Jinja `'\n'` inside a folded scalar in a role's `tasks/` or `vars/`.

The same day it bit a regex too. `vault_gateway`'s check for secrets Envoy's Lua filter cannot carry was
written `'[\\s"\\\\]|^$'` in a folded scalar. The backslashes reached Python as written, so `\\s` was a
backslash and the letter **s**: every secret containing an "s" was refused, and a real space was not.
The operator hit it on the first `make -f lab-gateway.mk secrets`. Fixed as `'[\s"\x5c]|^$'`, checked
against test values, and the guard now also fails on any doubled backslash in a folded scalar. A
backslash a regex needs is written `\x5c`.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
- [Role Contract](/concepts/role-contract--01a166e751ce.md)
