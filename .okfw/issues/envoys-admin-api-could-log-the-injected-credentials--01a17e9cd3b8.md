---
id: "01a17e9c-d3b8-71bd-9fc9-4d963db13847"
title: "Envoy's admin API could log the injected credentials"
type: "issue"
tags:
  - "issue"
  - "envoy"
  - "gateway"
  - "security"
created: "2026-10-27T13:26:09-05:00"
timestamp: "2026-10-27T13:26:09-05:00"
description: "Envoy's unauthenticated admin API on 127.0.0.1:9901 let any local process raise the log level until the router logged the injected real credentials; it is now an envoy-only unix socket, with a GET-only view for the operator."
x:
  severity: "medium-high"
  priority: "P1"
  state: "fixed"
  origin: "since the gateway began (admin on loopback TCP)"
  found: "2026-10-27, hardening review"
---

# Envoy's admin API could log the injected credentials

**Severity medium-high, P1, fixed.** It had been there since the gateway began, and was found in the
2026-10-27 hardening review.

## What happens
1. Envoy's admin interface listened on `127.0.0.1:9901` with no authentication, like every Envoy
   admin interface.
2. Any process on the host could use it, as could any container sharing the host network:
   - `POST /logging?level=debug` makes the router log full request headers, and that includes the
     `authorization` / `x-api-key` the surrogate filter has just injected. The log goes to the
     journal, which the first Ubuntu user can read through group `adm`;
   - `POST /quitquitquit` stops the gateway;
   - `/drain_listeners` and `/runtime_modify` change it.

## Fix
- The admin interface is a unix socket, `/run/envoy/admin.sock`, mode 0600 and owned by `envoy`.
  Only Envoy and root open it, and `envoy_gateway` verifies through it with `become`.
- A third listener, `admin_readonly` on `/run/envoy/admin-readonly.sock` (0666), proxies to it. It
  serves only `GET` on `/ready`, `/server_info`, `/listeners`, `/clusters`, `/stats` and
  `/config_dump`, and answers 403 to anything else. Every admin endpoint that changes Envoy needs
  `POST`, so none of them is reachable there. Envoy redacts private keys from `/config_dump`.
- Checks:
  - `envoy_gateway` checks that a `POST /logging` through the read-only view gets 403;
  - `tests/gateway/test_envoy.py` checks that the admin socket is envoy-owned 0600, that the
    operator cannot open it, that the view refuses the POST, and that nothing listens on :9901;
  - the suite reads Envoy through the view (`gateway_lab.envoy()`).

## Related
- [Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)
- [The surrogate filter failed open when its Lua script raised](/issues/the-surrogate-filter-failed-open-when-its-lua-script-raised--01a17e78784d.md)
