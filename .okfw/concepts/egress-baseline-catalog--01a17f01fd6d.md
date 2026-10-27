---
id: "01a17f01-fd6d-7942-840d-3b6635e1242e"
title: "Egress Baseline Catalog"
type: "concept"
tags:
  - "gateway"
  - "egress"
  - "catalog"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:16:39-05:00"
status: "draft"
description: "egress-baseline.yml: the categories of sites the sandbox may tunnel to without an operator entry, and the rules each entry must satisfy (HTTPS only, vendor-only wildcards, no gateway host or subdomain, a reason and a probe)."
---

# Egress Baseline Catalog

`labs/<lab>/ansible/vars/egress-baseline.yml`: every site the sandbox may reach through the CONNECT
tunnel without an operator entry, by category. Its enabled categories (`gateway-host.yml`
`egress_baseline_categories`) are seeded into the
[Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md) under `baseline/`.

## Rules
`consul_egress` asserts them before any write:
- **HTTPS only.** The tunnel is CONNECT-only, so plain-http repositories are refused by design.
- **A wildcard only for one vendor's own CDN names,** never a shared cloud (`*.cloudfront.net`,
  `*.amazonaws.com`, `*.googleapis.com`): a shared cloud would let the guest reach anything hosted
  there.
- **No gateway host, and no subdomain of one.** A tunnel to one would bypass the surrogate swap.
  Clients match `NO_PROXY` as a domain suffix, so a subdomain would never use the tunnel anyway:
  make it a gateway route instead, as codeload.github.com is
  ([issue](/issues/a-tunnel-host-under-a-gateway-host-skipped-the-proxy-through-no-proxys-suffix-match--01a17e6c06da.md)).
- **Every entry has a `reason` and a `probe`:** a URL on that host (a concrete name for a
  wildcard) that `tests/guest/sandbox/test_egress_catalog.py` fetches through the tunnel. Redirect
  targets found while probing become entries of their own.

Changing the baseline means editing the file, then `make -f lab-gateway.mk TAGS=consul`. Entries no
longer in the catalog, or whose category was turned off, are pruned. Operator entries (`allow/`) are
never touched.

## Related
- [Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md)
- [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md)
