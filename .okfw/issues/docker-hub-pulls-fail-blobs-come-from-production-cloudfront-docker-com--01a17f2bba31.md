---
id: "01a17f2b-ba31-7b50-993f-ce458bd15ebe"
title: "Docker Hub pulls fail: blobs come from production.cloudfront.docker.com"
type: "issue"
tags:
  - "issue"
  - "egress"
  - "podman"
  - "python-stack"
  - "uat"
created: "2026-10-27T16:02:14-05:00"
timestamp: "2026-10-27T16:02:14-05:00"
description: "Docker Hub now redirects image blobs to production.cloudfront.docker.com, which the oci-registries category does not list (it has production.cloudflare.docker.com), so a docker.io pull that gets a CloudFront redirect fails with Forbidden in the sandbox."
x:
  severity: "medium"
  priority: "P2"
  state: "open"
  origin: "pre-existing (egress baseline catalog, oci-registries)"
  found: "2026-10-27, writing the UAT specs (UAT-CTR-02)"
---

# Docker Hub pulls fail: blobs come from production.cloudfront.docker.com

**Severity medium, P2, open.** A developer cannot use a Docker Hub image, which many Containerfiles
start from.

## What happens
As dev on fedora-dev-1, `podman build` of `FROM docker.io/library/python:3.14-slim`:

```text
Error: creating build container: … parsing image configuration:
Get "https://production.cloudfront.docker.com/registry-v2/docker/registry/v2/blobs/sha256/…": Forbidden
```

The manifest comes from `registry-1.docker.io`, which is on the allow list. The registry then
redirects the blob to `production.cloudfront.docker.com`. The `oci-registries` category lists
`production.cloudflare.docker.com` only, so the tunnel refuses (403).

Docker Hub chooses the CDN per request, so a pull can work on one day and fail on the next. One pull
was seen to fail. It is not known whether every pull now uses CloudFront.

## Fix
Add `production.cloudfront.docker.com:443` to the `oci-registries` category, with a probe. It is
Docker's own name, not a shared `*.cloudfront.net` wildcard, so it meets the catalog's rule.

## Acceptance
- `podman pull docker.io/library/python:3.14-slim` works on the sandbox.
- UAT-CTR-01's note about Docker Hub can be removed.

## Related
- [Egress Baseline Catalog](/concepts/egress-baseline-catalog--01a17f01fd6d.md)
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
