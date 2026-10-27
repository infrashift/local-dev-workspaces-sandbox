---
id: "01a17ed1-b9f6-72dd-812d-e8710c9dbac7"
title: "Path tricks slipped past the repository binding"
type: "issue"
tags:
  - "issue"
  - "envoy"
  - "gateway"
  - "security"
  - "lua"
created: "2026-10-27T14:23:56-05:00"
timestamp: "2026-10-27T14:23:56-05:00"
description: "Without path normalization, dot segments or a doubled slash let a repository-bound surrogate reach another repository with the real PAT injected (only the PAT's scope refused it); the TLS gateway now normalizes and merges slashes before the filter, and rate-limits each host."
x:
  severity: "low-medium"
  priority: "P2"
  state: "fixed"
  origin: "since the repository binding was added"
  found: "2026-10-27, hardening review"
---

# Path tricks slipped past the repository binding

**Severity low-medium, P2, fixed.** It had been there since the repository binding was added. Found
in the 2026-10-27 hardening review, and confirmed live before the fix.

## What happens
1. The surrogate filter finds the repository with the route's `repo_path` pattern, applied to the
   raw `:path`. Envoy's HTTP connection manager does not normalize paths by default.
2. Three paths passed the check, and Envoy injected the real PAT, although each named another
   repository:
   - `/<own-repo>/../../<other-repo>.git/info/refs`: the filter read `<own-repo>`;
   - `//<other-repo>.git/info/refs`: the pattern did not match at all, so the filter treated it as
     "no repository in the path";
   - `/repos/<own-repo>/../../<other-repo>/commits` on api.github.com.
3. GitHub resolved them to `<other-repo>`, and the PAT's own single-repository scope refused them
   (404, or 403 "Write access to repository not granted"). The binding had been bypassed, and only
   the PAT's scoping held.

## Fix
- `tls_gateway`'s connection manager sets `normalize_path: true` (RFC 3986: dot segments resolved)
  and `merge_slashes: true`, so every filter reads the path the upstream serves.
- `path_with_escaped_slashes_action` stays at its default. GitHub's API takes `%2F` in branch names,
  and an owner or repository segment cannot hold one.
- `tests/guest/sandbox/test_anti_replay.py::test_path_tricks_cannot_hide_another_repository` sends
  the three paths with `--path-as-is`. It failed on all nine (3 per repository) before the apply,
  and passes after: 403 "surrogate repository mismatch", answered by the gateway.
  `tests/gateway/test_envoy.py` checks both settings in the loaded config.

Shipped with it: a per-gateway-host token bucket, `local_ratelimit`, ahead of the surrogate filter
(`envoy_gateway_rate_limit`: 200 burst, 50/s, then 429). It bounds what a compromised guest can do
with the real credentials, and keeps a flood from reaching Vault.

## Related
- [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md)
