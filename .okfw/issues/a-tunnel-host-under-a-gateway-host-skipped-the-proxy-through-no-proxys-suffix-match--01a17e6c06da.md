---
id: "01a17e6c-06da-70e5-9a8a-00f4e19b2a34"
title: "A tunnel host under a gateway host skipped the proxy through NO_PROXY's suffix match"
type: "issue"
tags:
  - "issue"
  - "gateway"
  - "no_proxy"
  - "egress"
  - "dns"
created: "2026-10-27T12:32:51-05:00"
timestamp: "2026-10-27T12:32:51-05:00"
description: "The guests' NO_PROXY names github.com, and curl, Python and Go match NO_PROXY entries as domain suffixes, so codeload.github.com (a tunnel host in the egress catalog) went direct and failed DNS; nvim-treesitter could not download a single parser."
x:
  severity: "medium"
  priority: "P1"
  state: "fixed"
  origin: "pre-existing (sandbox_egress NO_PROXY, egress catalog)"
  found: "2026-10-27, first python-stack apply on the Linux lab"
---

# A tunnel host under a gateway host skipped the proxy through NO_PROXY's suffix match

# A tunnel host under a gateway host skipped the proxy through NO_PROXY's suffix match

**Severity medium, P1, fixed.** Pre-existing design gap, found on the first `make -f lab-provision.mk play PLAYBOOK=python-stack` on the Linux lab. The lazyvim role's parser build failed for all 26 parsers: `curl: (6) Could not resolve host: codeload.github.com`.

## What happens
`sandbox_egress` puts every gateway host into `NO_PROXY`, so clients reach them directly at the gateway through `/etc/hosts`. But a `NO_PROXY` entry `github.com` also matches `codeload.github.com` in curl, Python and Go. codeload was in the egress catalog, meaning "through the CONNECT tunnel", so clients bypassed the proxy, found no DNS in the sandbox and failed. On the guest, `curl https://codeload.github.com/` gave 000, and with `--noproxy ''` it gave 301.

## Fix
- codeload.github.com is a gateway route (`anonymous: true`), out of the catalog. Public archives pass unchanged.
- The rule, in `vars/gateway.yml` and `egress-baseline.yml`: every subdomain of a gateway host that the sandbox uses must be a gateway route itself.
- `tests/gateway/test_allowlist.py::test_catalog_entry_is_not_under_a_gateway_host` checks every catalog entry.

## Verified
2026-10-27: `tests/gateway` passed (255 passed, 4 skipped) after the gateway was applied.

## Related
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md), [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)
