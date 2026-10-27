---
id: "01a17e78-7872-75e9-af61-780a132eb106"
title: "SCP through the tunnel got 426: Envoy refused ncat's HTTP/1.0 CONNECT"
type: "issue"
tags:
  - "issue"
  - "envoy"
  - "ssh"
  - "scp"
  - "tunnel"
created: "2026-10-27T12:46:26-05:00"
timestamp: "2026-10-27T12:46:26-05:00"
description: "The sandbox's ssh ProxyCommand (ncat) sends CONNECT as HTTP/1.0, which Envoy refused with 426 Upgrade Required; the tunnel listener now accepts HTTP/1.0."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed"
  origin: "pre-existing (sandbox_egress ProxyCommand, Envoy tunnel)"
  found: "2026-10-27, first sandbox suite run"
---

# SCP through the tunnel got 426: Envoy refused ncat's HTTP/1.0 CONNECT

# SCP through the tunnel got 426: Envoy refused ncat's HTTP/1.0 CONNECT

**Severity medium, P2, fixed.** Pre-existing: the sandbox's ssh `ProxyCommand` (`ncat --proxy-type http`,
from sandbox_egress) had never connected.

## What happens
ncat sends `CONNECT host:port HTTP/1.0`. Envoy's HTTP/1 codec refuses HTTP/1.0 unless it is allowed, and
answers `426 Upgrade Required`: `Ncat: Proxy returned status code 426`. Envoy logs no access line for
it.

## Fix
`http_protocol_options: { accept_http_10: true }` on the CONNECT tunnel's connection manager only.
