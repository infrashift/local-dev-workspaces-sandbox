---
id: "01a17f2f-9819-7575-a52f-29027556de1e"
title: "The allow target accepts a gateway host"
type: "issue"
tags:
  - "issue"
  - "egress"
  - "operator"
  - "gateway"
  - "uat"
created: "2026-10-27T16:06:27-05:00"
timestamp: "2026-10-27T16:06:27-05:00"
description: "make -f lab-gateway.mk allow HOST=github.com:443 writes the entry although Operator Interfaces says the wrapper refuses gateway hosts; the tunnel's route table still denies it, so the entry is inert but misleading."
x:
  severity: "low"
  priority: "P3"
  state: "open"
  origin: "pre-existing (scripts/gateway/egress-allowlist.sh)"
  found: "2026-10-27, writing the UAT specs (UAT-EGR-02)"
---

# The allow target accepts a gateway host

**Severity low, P3, open.** No security effect, but the documentation and the code disagree, and the
allow list then shows an entry that does nothing.

## What happens
```text
$ make -f lab-gateway.mk allow HOST=github.com:443 REASON=x
Allowed github.com:443 (Envoy picks it up within seconds)
```

[Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md) says that the make targets
validate their input, "no gateway host" included. `egress-allowlist.sh` checks the shape of the entry
only. The route table that consul-template renders leaves gateway hosts out and denies them on every
tunnel port, so the sandbox still gets no tunnel to github.com (`test_allowlist.py`,
`test_tunnel_refuses_a_gateway_host`). The entry stays in Consul and in `make -f lab-gateway.mk
allowlist`, where it looks as if it works.

## Fix
`egress-allowlist.sh add` refuses a host that is a gateway host or a subdomain of one, and names the
reason (the guests' NO_PROXY sends such a host to the TLS gateway). It reads the gateway hosts from
`ansible/vars/gateway.yml`, as the catalog check in `test_allowlist.py` does.

## Acceptance
- UAT-EGR-02 step 9 passes: the command refuses github.com:443 and writes nothing.

## Related
- [Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md)
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
