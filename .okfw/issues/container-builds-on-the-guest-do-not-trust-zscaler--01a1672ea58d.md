---
id: "01a1672e-a58d-778d-a014-5ea806a1fc7f"
title: "Container builds on the guest do not trust ZScaler"
type: "issue"
tags:
  - "issue"
  - "podman"
  - "zscaler"
  - "pki"
  - "enhancement"
created: "2026-10-23T00:14:32-05:00"
timestamp: "2026-10-23T00:14:32-05:00"
description: "ca_trust makes the guest trust the proxy CA, but images carry their own trust store, so RUN dnf/pip/npm inside a podman build on the guest still fails behind ZScaler."
x:
  severity: "medium"
  priority: "P3"
  state: "open"
  origin: "known limitation (ca_trust scope)"
  found: "2026-10-22, while planning the ZScaler work"
---

# Container builds on the guest do not trust ZScaler

**Severity medium, P3, open.** Registry pulls work (tested); building an image that downloads anything does not, until the image trusts the chain too.

## What happens
podman verifies registry TLS with the guest's store, so pulls work in both modes, as tested behind mitmproxy. A build step runs inside the image, though, and Fedora/UBI/Debian/Alpine images ship only their distribution's roots.

## Options
- A podman role option that adds `/etc/pki/ca-trust/extracted:/etc/pki/ca-trust/extracted:ro` to `containers.conf` `[containers] volumes`. This works for Fedora/RHEL-family images only.
- Documented Containerfile snippets that `COPY` the chain and run each distribution's trust update (`update-ca-trust`, `update-ca-certificates`).
- `podman build --volume ...` per build.

## Acceptance
- `podman build` of a Containerfile with `RUN dnf -y install jq` succeeds on a guest behind the proxy.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
