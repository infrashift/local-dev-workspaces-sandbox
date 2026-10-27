---
id: "01a17e9c-d3ae-7423-8673-791a16612d0b"
title: "The gateway answered machines beside the sandbox (weak host model)"
type: "issue"
tags:
  - "issue"
  - "gateway"
  - "firewall"
  - "nftables"
  - "security"
created: "2026-10-27T13:26:09-05:00"
timestamp: "2026-10-27T13:26:09-05:00"
description: "The host firewall filtered only the sandbox bridge, so a LAN peer, upstream-1 or a container could reach Envoy at the gateway address and have the published surrogates swapped for the real credentials; now refused by nft and by Envoy's source-range filter chains."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "since the gateway began (firewall filtered the bridge only)"
  found: "2026-10-27, hardening review"
---

# The gateway answered machines beside the sandbox (weak host model)

**Severity high, P1, fixed.** It had been there since the gateway began. Found in the 2026-10-27
hardening review, and confirmed live before the fix: `upstream-1` opened TCP connections to
`192.168.150.1:443` and `:8080`. No misuse was observed.

## What happens
1. `sandbox_firewall`'s nft table filtered only `iifname "virbr50"`, the sandbox bridge.
2. Linux uses the weak host model: a packet addressed to any of the host's addresses is accepted on
   any interface. This host also forwards (`ip_forward=1`) with loose reverse-path filtering
   (`rp_filter=2`).
3. So the gateway address took packets from three places:
   - from the Wi-Fi: any LAN peer that routes 192.168.150.1/32 via the host;
   - from virbr51: upstream-1;
   - from docker0: any container.

   They reached Envoy's CONNECT tunnel and TLS gateway, and Envoy itself accepted any source.
4. The surrogates are not secret: they are committed in `vars/gateway.yml`. A neighbour presenting
   one to the TLS gateway would have had the real GitHub PAT or Anthropic key injected. That is
   exactly what the gateway exists to prevent.
5. Separately, stopping `ai-sandbox-firewall.service` deletes its table (`ExecStop`). That removed
   the sandbox's own limits as well.

## Fix
- The input chain's first rule:
  `ip daddr GATEWAY_IP iifname != { "lo", SANDBOX_BRIDGE } counter reject`. `sandbox_firewall`
  asserts that the loaded table carries it.
- Envoy limits both listeners to `SANDBOX_CIDR` (`filter_chain_match.source_prefix_ranges`), so the
  gateway stays closed to other sources without the firewall too. This adds the new role parameter
  `envoy_gateway_sandbox_cidr`.
- `sandbox_firewall`'s dry run now skips its loaded-table assertion when the ruleset on disk would
  change, because the old table cannot pass a new check.

## Verified
2026-10-27: `test_gateway_refuses_a_machine_beside_the_sandbox` failed on both ports before the apply
and passed after it. The gateway suite and the sandbox suite passed.

## Related
- [Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)
