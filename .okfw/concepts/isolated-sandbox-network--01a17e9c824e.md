---
id: "01a17e9c-824e-7b11-916f-f8f994f02111"
title: "Isolated Sandbox Network"
type: "concept"
tags:
  - "gateway"
  - "network"
  - "firewall"
  - "security"
created: "2026-10-27T13:25:48-05:00"
timestamp: "2026-10-27T13:25:48-05:00"
status: "draft"
description: "The three layers that leave the sandbox VMs only Envoy's two listeners: the isolated libvirt network, the host's own nft table (including the weak-host rule), and Envoy's source-range filter chains."
---

# Isolated Sandbox Network

The sandbox VMs sit on an isolated libvirt network (`SANDBOX_NETWORK`, bridge `SANDBOX_BRIDGE`
virbr50, `SANDBOX_CIDR` 192.168.150.0/24). Their only way out is Envoy, on the host's address on that
bridge (`GATEWAY_IP` 192.168.150.1): the CONNECT tunnel on `PROXY_PORT` and the TLS gateway on
`GATEWAY_PORT`. Three layers enforce it, and each would hold alone.

## 1. The isolated network
libvirt's `isolated` mode gives the bridge no NAT and no route off the host. The guest has DHCP from
libvirt's dnsmasq and no DNS server: every name it resolves is a gateway host in `/etc/hosts`, or a
CONNECT target that Envoy resolves for it.

## 2. The host firewall (`sandbox_firewall`)
Its own nft table, `inet ai_sandbox`, loaded by `ai-sandbox-firewall.service` (never
`nftables.service`, whose `flush ruleset` would wipe libvirt's and docker's tables). The input chain:

| Rule | Why |
|---|---|
| `ip daddr GATEWAY_IP iifname != { "lo", SANDBOX_BRIDGE } reject` | The weak host model (below): only the sandbox and the host itself reach the gateway address. |
| from the bridge: replies, DHCP, the two gateway ports | What the guest needs. |
| from the bridge: everything else rejected | Vault, Consul, sshd and any other host service. |

The forward chain rejects the bridge both ways, so no route out exists even if one were added in the
guest.

### The weak host model
Linux accepts a packet addressed to *any* of its addresses on *any* interface. With only
`iifname SANDBOX_BRIDGE` rules, a packet for 192.168.150.1 that arrived on the Wi-Fi (a LAN peer
with a static route), on the upstream bridge (upstream-1) or on docker0 (any container) went straight
to Envoy. The surrogates are committed in `vars/gateway.yml`, so such a neighbour could have had the
real credentials swapped in. The first rule closes that
([The gateway answered machines beside the sandbox](/issues/the-gateway-answered-machines-beside-the-sandbox-weak-host-model--01a17e9cd3ae.md)).
`lo` stays open because the host's own probes of 192.168.150.1 (the gateway suite) arrive on it.

## 3. Envoy's filter chains (`envoy_gateway`)
Every filter chain on the two listeners carries `filter_chain_match.source_prefix_ranges` =
`SANDBOX_CIDR`. A connection from any other source matches no chain, and Envoy closes it before TLS
or HTTP. This holds even when the firewall's table is gone: `ai-sandbox-firewall.service`'s
`ExecStop` deletes it, so stopping that unit used to open the gateway to the LAN. The host's own
probes use 192.168.150.1 as their source, inside the range.

## Checked by
- `tests/gateway/test_firewall.py`: the ruleset on disk carries the source-interface rule
  (`gateway-from-bridge-only`). `sandbox_firewall` asserts the loaded table carries it too.
- `tests/gateway/test_envoy.py::test_listeners_serve_only_the_sandbox_network`: every chain of both
  listeners is limited to `SANDBOX_CIDR`.
- `tests/guest/sandbox/test_isolation.py::test_gateway_refuses_a_machine_beside_the_sandbox`: from
  each upstream VM, a TCP connect to both gateway ports is refused. It failed on both ports before the
  fix (2026-10-27).
- `tests/guest/sandbox/test_isolation.py`: from the sandbox, nothing is reachable directly, and the
  tunnel refuses the gateway hosts.

## Related
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Envoy's admin API could log the injected credentials](/issues/envoys-admin-api-could-log-the-injected-credentials--01a17e9cd3b8.md)
