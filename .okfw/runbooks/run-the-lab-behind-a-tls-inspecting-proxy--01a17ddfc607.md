---
id: "01a17ddf-c607-736c-b181-8b8c64308b23"
title: "Run the Lab Behind a TLS-Inspecting Proxy"
type: "runbook"
tags:
  - "runbook"
  - "tls"
  - "zscaler"
  - "pki"
  - "gateway"
created: "2026-10-27T09:59:39-05:00"
timestamp: "2026-10-27T10:00:15-05:00"
description: "Step-by-step: make the host, the gateway (Envoy) and every lab VM trust a TLS-inspecting proxy's CA chain (Zscaler as the example) through TLS_INSPECTION_DIR, verify it, rotate or remove it, and what is not covered."
status: "draft"
---

# Run the Lab Behind a TLS-Inspecting Proxy

# Run the Lab Behind a TLS-Inspecting Proxy

Do this when the host's internet traffic passes through a TLS-inspecting proxy. This page uses
Zscaler as the example; any proxy that re-signs each site's certificate with its own CA works the same
way. The background is in [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md).

The lab supports this **optionally**. Put the proxy's CA chain in `TLS_INSPECTION_DIR`
(`lab-config.mk`, default `<project>/.pki/tls-inspection/`, gitignored), and the gateway and every lab VM
trust it. Leave the directory empty or absent and nothing changes. Run every command from the lab
directory, `labs/fedora44min-x86_64-dev-ws`.

## Which connections the proxy re-signs

| Connection | Who must trust the proxy's chain | Done by |
|---|---|---|
| The sandbox's CONNECT-tunnel traffic (dnf, pip, uv, podman pulls, Claude Code's release downloads). TLS runs end to end from the guest, through Envoy, to the site. | The sandbox VM's system trust store | `ca_trust`, instance `ai-sandbox-tls-inspection`, first in `vm-baseline.yml` |
| Envoy's TLS-gateway upstreams with `ca: system`: github.com, api.github.com, raw.githubusercontent.com, api.anthropic.com, api.githubcopilot.com | Envoy | `envoy_gateway` builds `/etc/ai-sandbox/tls-inspection/public-upstream-ca.pem` (the host's roots, then the chain) and verifies those routes with it |
| upstream-1 over the NAT network: dnf, and its GitHub MCP server's calls to api.github.com | upstream-1's system trust store | `ca_trust`, the same instance, first in the upstream play of `vm-baseline.yml` |
| The host's own downloads: the bootstrap's releases, Terraform, the HashiCorp and Envoy releases | The host's system trust store | **You** (Procedure 1). The lab never changes the host's trust store. |
| Guest ↔ Envoy :443, Envoy ↔ upstream-1, Envoy ↔ Vault | — | Nothing needed: these never leave the host |

## Before you start

- You know the proxy's root CA, and its intermediate if it uses one. Your IT department publishes it,
  and the Zscaler Client Connector installs it on managed machines.
- The proxy inspects **transparently**: the client connects to the site, and the proxy intercepts. An
  explicit proxy (a PAC file, or a `host:port` that clients must be told about) is not supported. See
  "Not covered" below.

## Procedure 1: Make the host trust the proxy

The bootstrap downloads from GitHub, HashiCorp and Fedora, so do this first.

1. Check whether the host already trusts it. If `Verification: OK` is printed and the issuer is the
   proxy's CA, skip to Procedure 2:

   ```sh
   openssl s_client -connect github.com:443 -servername github.com -brief </dev/null 2>&1 | grep -E 'Verification|issuer'
   ```

2. Install the root CA in the host's store. On Debian, Ubuntu and Pop!_OS:

   ```sh
   sudo cp zscaler-root.pem /usr/local/share/ca-certificates/zscaler-root.crt
   sudo update-ca-certificates
   ```

   On Fedora or EL hosts, copy it to `/etc/pki/ca-trust/source/anchors/` and run `sudo update-ca-trust`.

## Procedure 2: Put the chain in TLS_INSPECTION_DIR

1. Export the chain as PEM, root and intermediate:
   - **From the host's store** (after Procedure 1): copy the file you installed.
   - **macOS:** `security find-certificate -a -c Zscaler -p /Library/Keychains/System.keychain`
   - **Windows:** certmgr.msc → Trusted Root Certification Authorities → the Zscaler root → Export,
     "Base-64 encoded X.509".
   - **From a live connection:** `openssl s_client -connect github.com:443 -servername github.com -showcerts </dev/null`
     prints the certificates the proxy sends. The root is often not among them, so prefer the other ways.
2. Save it in the directory as one or more `*.pem` or `*.crt` files:

   ```sh
   mkdir -p ../../.pki/tls-inspection
   cp zscaler-chain.pem ../../.pki/tls-inspection/
   ```

   > **Caution:** Only unexpired CA certificates belong here. The gateway playbook and `ca_trust` stop on
   > a private key, a leaf certificate or an expired CA, and name only the PEM headers they found.

3. Check that the chain is the one that signs your traffic. The site must verify with the chain alone:

   ```sh
   openssl s_client -connect github.com:443 -servername github.com -brief -partial_chain \
     -verify_return_error -CAfile ../../.pki/tls-inspection/zscaler-chain.pem </dev/null
   ```

## Procedure 3: Apply it to the gateway and the lab

1. Rebuild Envoy's public-upstream CA bundle. Envoy restarts with it:

   ```sh
   make -f lab-gateway.mk TAGS=envoy
   ```

2. Verify the gateway side:

   ```sh
   make -f lab-gateway-verify.mk PYTEST_ARGS="-k tls_inspection"
   ```

3. Install the chain on every lab VM. `make -f lab-provision.mk apply` also does it, because Terraform
   applies `vm-baseline.yml` again when a file in `TLS_INSPECTION_DIR` changes:

   ```sh
   make -f lab-provision.mk ansible
   ```

4. Verify the lab VMs:

   ```sh
   make -f lab-provision-verify.mk PYTEST_ARGS="-k tls_inspection"
   ```

## Rotate or remove the chain

- **Rotate:** replace the files in `TLS_INSPECTION_DIR` and do Procedure 3 again. The anchors are named
  by fingerprint, so the old ones are removed.
- **Remove** (the proxy is gone): empty the directory and do Procedure 3 again. Envoy goes back to the
  host's roots alone, and `ca_trust` removes its anchors from every VM. The tests check that nothing is
  left behind.
- **After the host's `ca-certificates` package updates**, run `make -f lab-gateway.mk TAGS=envoy`.
  Envoy's bundle is a copy of the host's roots, and `test_bundle_is_public_and_holds_the_host_roots_and_the_chain`
  fails until it is rebuilt.

## What the checks prove

| Test | With a chain | Without one |
|---|---|---|
| `tests/gateway/test_tls_inspection.py` | The chain holds only unexpired CA certificates and no key. Every `ca: system` route verifies with the public-upstream bundle, which is root-owned 0644 and holds the host's roots and the chain. github.com verifies from the host with the chain **alone**, which proves that the proxy really signs with it. | Every `ca: system` route verifies with the host's bundle, and no bundle is left over. |
| (both cases) | Live: an anonymous request through the TLS gateway to github.com, api.github.com and raw.githubusercontent.com gets past a verified upstream handshake. It is skipped until the sandbox bridge is up (`make -f lab-provision.mk apply`). | |
| `tests/guest/baseline/test_tls_inspection.py`, on every lab VM | Exactly the chain's anchors, trusted through the system bundle. The VM's sites answer over verified TLS, through the tunnel on the sandbox and directly on upstream-1. The first site verifies with the anchors alone. | None of the chain's anchors remains. |

## Not covered

- **An explicit proxy.** Envoy connects to upstreams and tunnel sites directly. It cannot chain through
  an upstream HTTP proxy, and upstream-1 has no `HTTPS_PROXY`. The symptom is a timeout, not a
  certificate error. Supporting this would need Envoy to tunnel its upstream connections through the
  proxy.
- **Destinations the proxy does not inspect** (SSL-inspection bypass lists, which are common for
  certificate-pinned apps). These work: Envoy's bundle and the VMs' system stores still hold the public
  roots.
- **Proxy policy.** A Zscaler policy that blocks or authenticates api.anthropic.com, api.githubcopilot.com
  or GitHub, for example with a 307 to a login page for unmanaged clients, shows up as a failed scenario
  test, not as a TLS error. Ask the proxy's administrators to allow the lab host's traffic to the gateway
  routes and the egress catalog.
- **Container builds on the guest.** See
  [Container builds on the guest do not trust ZScaler](/issues/container-builds-on-the-guest-do-not-trust-zscaler--01a1672ea58d.md).
- **Clients that pin certificates.** They fail behind any inspection.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
- [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/lab-config.mk` (`TLS_INSPECTION_DIR`), `ansible/playbooks/vm-baseline.yml`, `ansible/playbooks/gateway-host.yml`
- `ansible/roles/guest/ca_trust/`, `ansible/roles/gateway/envoy_gateway/`
- `labs/fedora44min-x86_64-dev-ws/tests/gateway/test_tls_inspection.py`, `tests/guest/baseline/test_tls_inspection.py`
