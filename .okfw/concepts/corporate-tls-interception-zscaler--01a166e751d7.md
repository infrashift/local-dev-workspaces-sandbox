---
id: "01a166e7-51d7-7467-b9b3-31fd71d96823"
title: "Corporate TLS Interception (ZScaler)"
type: "concept"
tags:
  - "pki"
  - "zscaler"
  - "tls"
  - "proxy"
created: "2026-10-22T22:56:38-05:00"
timestamp: "2026-10-27T10:05:00-05:00"
description: "Why every lab VM and Envoy must trust a TLS-inspecting proxy's (ZScaler's) CA chain when there is one, where TLS_INSPECTION_DIR's chain is installed, what the system trust store covers, and what still is not covered."
---

# Corporate TLS Interception (ZScaler)

A TLS-inspecting proxy such as ZScaler terminates TLS and re-signs each site's certificate with its own
CA. A client that does not trust that CA cannot complete a single HTTPS handshake, including dnf's.
The original lab was a Mac behind ZScaler. The current lab runs on a Linux host that is **not** behind
one, so support is optional: it is on when `TLS_INSPECTION_DIR` holds a chain (decided 2026-10-27). The
procedure is [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md).

## Where the chain comes from and goes

- **The proxy's chain** goes into `TLS_INSPECTION_DIR` (`lab-config.mk`, default
  `<project>/.pki/tls-inspection/`, gitignored). Every `*.pem`/`*.crt` file there is trusted. An empty or
  missing directory means there is no proxy.
- `CA_TRUST_DIR` is **not** for the proxy any more. It holds the gateway CA that Envoy's TLS gateway signs
  with ([Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)).
  On the Mac lab it held the ZScaler chain.
- **On every lab VM** the `ca_trust` role ([Guest Roles](/tooling/guest-roles--01a166e751e0.md)) runs as a
  second instance, `ai-sandbox-tls-inspection` with `ca_trust_required: false`, **first** in each play of
  `vm-baseline.yml`. On the sandbox it runs before `sandbox_egress`, whose dnf install and mirror check go
  through the tunnel, where the proxy re-signs. Its probes use the play's proxy environment, and skip the
  gateway's own hosts, whose CA is not trusted yet.
  1. It checks on the controller that every PEM object is an unexpired CA certificate, and never a
     private key.
  2. It writes one anchor per certificate to
     `/etc/pki/ca-trust/source/anchors/ai-sandbox-tls-inspection-<sha256[:16]>.pem`, removes stale ones,
     and runs `update-ca-trust extract`. With no chain, it removes all of them.
  3. It proves the result: `openssl verify` of each anchor through the extracted bundle, then curl and
     Python probes of the URLs the VM needs.
- **On the gateway**, Envoy re-originates TLS to github.com, api.anthropic.com and the other `ca: system`
  routes from the host, through the proxy. `envoy_gateway` then verifies them with the host's roots
  *plus* the chain (`/etc/ai-sandbox/tls-inspection/public-upstream-ca.pem`). Roots alone would fail every
  inspected site, and the chain alone would fail every site the proxy bypasses.
- **The host itself** is the operator's: the lab never edits its trust store.
- Terraform re-runs the baseline when a file in either directory changes (a rotated chain).
- cloud-init installs **no packages** on first boot, because first boot comes before the CA is trusted.
  See [First-boot dnf install cannot reach repositories behind ZScaler](/issues/first-boot-dnf-install-cannot-reach-repositories-behind-zscaler--01a166fc3ded.md).

## Is the system trust store enough? Mostly.

`update-ca-trust` regenerates the OpenSSL/GnuTLS/NSS/p11-kit bundles and the Java `cacerts`. Anything
that uses them trusts ZScaler with no further step. Some tools carry **their own root store** and ignore
the system store, so `ca_trust` also points each of them at the system bundle. It writes the variables to
`/etc/profile.d/ca-trust.sh` (login and interactive shells) and `/etc/environment.d/50-ca-trust.conf`
(systemd user managers):

| Variable | For |
|---|---|
| `SSL_CERT_FILE` | uv (bundled webpki roots); generally anything OpenSSL-based |
| `REQUESTS_CA_BUNDLE` | Python requests (certifi's bundle) |
| `PIP_CERT` | pip (pip 26 already reads the system store; kept for older pips) |
| `NODE_EXTRA_CA_CERTS` | Node.js, bun, Claude Code |

Ansible commands do not source `profile.d`. The roles that run uv therefore set `SSL_CERT_FILE` in their
own `environment:`.

## Verified behind a real intercepting proxy

Tested 2026-10-23 on a Fedora 44 guest of the earlier Mac lab, after `ca_trust` had installed mitmproxy's
CA. The guest-side behaviour is unchanged by the gateway. Each client was
sent through mitmproxy, which re-signs every TLS connection exactly as ZScaler does. "Bare" means an
empty environment; "env" means with `/etc/profile.d/ca-trust.sh` sourced.

| Client | Bare | Env |
|---|---|---|
| curl, python3 `urllib`, git clone | pass | — |
| podman pull (rootless) | pass | — |
| pip 26 | pass (reads the system store) | pass |
| uv 0.13.5 | **fail**: `invalid peer certificate: UnknownIssuer` | pass |
| Node 24 (from basedpyright's wheel) | **fail**: `unable to verify the first certificate` | pass |

The two bare failures also prove the traffic really was intercepted. Not exercised: requests
(`REQUESTS_CA_BUNDLE`) and Claude Code's own network calls (`NODE_EXTRA_CA_CERTS`, per Anthropic's
documentation for custom CAs).

## Not covered

The runbook's "Not covered" has the current list. In short:

- **Inside containers.** An image carries its own trust store, so a `RUN dnf`/`pip`/`npm` in a
  `podman build` does not trust ZScaler. Registry pulls *are* fine: podman verifies them with the
  host's store. Options, none automated yet: mount
  `/etc/pki/ca-trust/extracted` into Fedora/UBI-based builds, or `COPY` the chain into the image and run
  its own trust update. Tracked as
  [Container builds on the guest do not trust ZScaler](/issues/container-builds-on-the-guest-do-not-trust-zscaler--01a1672ea58d.md).
- **Certificate pinning.** A client that pins a server certificate fails behind any interception.
- **An explicit proxy.** If ZScaler is configured as an explicit proxy (a PAC file or a local listener)
  rather than transparently, Envoy would have to tunnel its own upstream connections through it, which it
  does not, and upstream-1 would need `HTTPS_PROXY`. The probes then *time out*; they do not show
  certificate errors.

## Related
- [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md)
- [Role Contract](/concepts/role-contract--01a166e751ce.md), [socket_vmnet Networking](/concepts/socket-vmnet-networking--01a1664337c7.md),
  [Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md)
