---
id: "01a17e52-1712-7d95-99f4-0df78b40b14b"
title: "Envoy cached an IPv6 address for a tunnel host and refused it with 503 UF"
type: "issue"
tags:
  - "issue"
  - "envoy"
  - "dns"
  - "gateway"
  - "ipv6"
created: "2026-10-27T12:04:31-05:00"
timestamp: "2026-10-27T12:04:31-05:00"
description: "With dns_lookup_family V4_PREFERRED, one empty A lookup made Envoy's CONNECT-tunnel DNS cache hold mirrors.kernel.org's AAAA address; the host has no IPv6 route, so every request got 503 UF in 0 ms until the entry refreshed."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "pre-existing (envoy_gateway dns_lookup_family)"
  found: "2026-10-27, make -f lab-provision.mk apply"
---

# Envoy cached an IPv6 address for a tunnel host and refused it with 503 UF

# Envoy cached an IPv6 address for a tunnel host and refused it with 503 UF

**Severity high, P1, fixed.** It broke `make -f lab-provision.mk apply` partway: `sandbox_egress`'s mirror check through the tunnel failed, minutes after the same request had succeeded.

## What happens
`dns_lookup_family: V4_PREFERRED` means "IPv4, or IPv6 if there is no IPv4". One lookup of mirrors.kernel.org came back without an A record, so the dynamic-forward-proxy DNS cache stored `[2605:f480:58:1:0:1994:3:14]:443`. The lab host has no IPv6 default route, so each CONNECT failed at once: Envoy logged `503 UF 98/0 0ms`, `upstream_cx_connect_fail` rose and no new DNS query was made. The host's own curl, over IPv4, worked throughout.

Found 2026-10-27 by reading `/clusters`, which lists the cached address per host.

## Fix
`envoy_gateway_dns_lookup_family: V4_ONLY` (a role constant) for the tunnel's DNS cache and the gateway's `LOGICAL_DNS` clusters. The sandbox network is IPv4-only anyway. `tests/gateway/test_envoy.py::test_tunnel_resolves_ipv4_only` checks the setting and that no tunnel host is cached at an IPv6 address. It failed against the old Envoy and passes after the fix.

## Verified
2026-10-27: after `make -f lab-gateway.mk TAGS=envoy`, `tests/gateway` passed (171 passed, 4 skipped), and the interrupted `make -f lab-provision.mk apply` completed with nothing to change on either VM.

## Related
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
