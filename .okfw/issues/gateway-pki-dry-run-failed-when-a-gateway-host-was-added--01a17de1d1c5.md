---
id: "01a17de1-d1c5-71bc-8693-86af06554f54"
title: "gateway_pki dry run failed when a gateway host was added"
type: "issue"
tags:
  - "issue"
  - "gateway_pki"
  - "pki"
  - "check-mode"
created: "2026-10-27T10:01:53-05:00"
timestamp: "2026-10-27T10:01:53-05:00"
description: "Adding a host to vars/gateway.yml made make -f lab-gateway.mk's dry run fail: gateway_pki asserted the new SANs against the old certificate, which only the real run re-signs."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (gateway_pki verification)"
  found: "2026-10-27, adding the GitHub MCP gateway routes"
---

# gateway_pki dry run failed when a gateway host was added

# gateway_pki dry run failed when a gateway host was added

**Severity medium, P2, fixed.** Any new gateway route blocked the dry run, so `lab-gateway.mk` never got to the "yes" prompt.

## What happens
`community.crypto.x509_certificate` reports *changed* in check mode, but does not write the re-signed certificate. The verification block then read the old certificate and asserted that it names every gateway host. It did not, so the dry run stopped with "Assert the gateway certificate chains, names every gateway host…".

Found 2026-10-27 when raw.githubusercontent.com and api.githubcopilot.com were added ([GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)).

## Fix
The signing task registers `gateway_pki_leaf_signed`. The verification is skipped only in a dry run that would re-sign (`gateway_pki_verifiable`), as the [Role Contract](/concepts/role-contract--01a166e751ce.md) asks of verification ("skipped only in a dry run that would …").

## Verified
2026-10-27: the dry run listed the re-signing, the apply re-signed with the new SANs and passed the assert, and a second dry run found nothing to change.
