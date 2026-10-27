---
id: "01a17e78-784d-72dd-8387-cde038957ee5"
title: "The surrogate filter failed open when its Lua script raised"
type: "issue"
tags:
  - "issue"
  - "envoy"
  - "lua"
  - "security"
  - "gateway"
created: "2026-10-27T12:46:26-05:00"
timestamp: "2026-10-27T12:46:26-05:00"
description: "A Lua error in the surrogate filter (route metadata read after httpCall) let Envoy forward requests unchanged, surrogate and all; the filter now fails closed and a test watches its error counter."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "new code (repository binding); fail-open since the filter began"
  found: "2026-10-27, first sandbox suite run"
---

# The surrogate filter failed open when its Lua script raised

# The surrogate filter failed open when its Lua script raised

**Severity high, P1, fixed.** New code (the repository binding), but the fail-open behaviour was the
filter's from the start. For about 40 requests on 2026-10-27, Envoy forwarded the sandbox's surrogates
to GitHub unswapped. GitHub answered 401, and no real credential was exposed.

## What happens
1. The repository check called `meta:get("repo_path")` after `handle:httpCall()`. `httpCall` yields, and
   every object taken from the handle before it (the header map, the route metadata) is invalid after
   it. The script raised `object used outside of proper scope`.
2. When a Lua filter raises, Envoy logs the error and lets the request continue **unchanged**: the
   surrogate went upstream, with no swap and no host or repository binding checked. The sandbox suite
   showed it as 401s from GitHub, and the cross-repository refusals did not happen.
   `http.tls_gateway.lua.errors` was 40.

## Fix
- Everything the swap needs from the route metadata (`anonymous`, `repo_path`) is read before the
  Vault call.
- `envoy_on_request` runs the swap in `pcall`. Any error now answers 500 "gateway filter error" and is
  logged: the filter fails closed. Yielding inside `pcall` works under Envoy's LuaJIT; authenticated
  requests went through afterwards.
- `tests/gateway/test_envoy.py::test_surrogate_filter_has_raised_no_error` checks that
  `http.tls_gateway.lua.errors` is 0. It failed at 40 before the fix.

## Verified
2026-10-27: after the apply, an api surrogate read its own repository (200), was refused on another
(403 "surrogate repository mismatch"), and the error counter stayed 0.

## Related
- [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)
