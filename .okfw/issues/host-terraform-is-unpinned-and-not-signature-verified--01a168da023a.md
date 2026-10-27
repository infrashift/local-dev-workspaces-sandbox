---
id: "01a168da-023a-75e4-a097-a82f4a60a9a3"
title: "Host Terraform is unpinned and not signature-verified"
type: "issue"
tags:
  - "issue"
  - "terraform"
  - "host-roles"
  - "supply-chain"
created: "2026-10-23T08:01:20-05:00"
timestamp: "2026-10-23T08:01:20-05:00"
description: "bootstrap-host installs Terraform from the hashicorp/tap Homebrew formula, which takes whatever version the tap holds, verifies it only against the tap's own SHA-256, and is never version-asserted."
x:
  severity: "medium"
  priority: "P2"
  state: "fixed-unverified"
  origin: "existing code (mac_host_packages package list)"
  found: "2026-10-23, while planning the host Terraform role"
---

# Host Terraform is unpinned and not signature-verified

**Severity medium, P2, fixed-unverified.** Every other host download is pinned and verified; Terraform, which drives every lab, was not.

## What happens
`bootstrap-host.yml` lists `hashicorp/tap/terraform` in `homebrew_packages`.
- **No pin.** Two Macs bootstrapped a week apart can run different Terraform versions, and `make check` cannot tell. The labs only require `>= 1.13.0`.
- **No signature.** Homebrew checks the zip against the SHA-256 in HashiCorp's tap, a git repository. HashiCorp also signs every release's `SHA256SUMS` with its security key; nothing checked that signature. The Fedora image, by contrast, needs a signature from a pinned key ([Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)).
- **Two copies on PATH.** `lab-provision.mk` runs a bare `terraform`, so a second install (tfenv, a manual download) silently wins or loses by PATH order.

## Fix
A `hashicorp_release` host role:
1. fetches `<product>_<v>_SHA256SUMS` and its `.sig`;
2. requires the signature to come from HashiCorp's pinned primary-key fingerprint;
3. installs the darwin_arm64 zip verified against the signed hash into `~/.local/bin`;
4. asserts the pinned version.

The tap and formula leave the Homebrew list. The role fails by name while Homebrew's terraform is still installed, and `lab-provision.mk` calls `$(LOCAL_BIN)/terraform`.

## Acceptance
- `make -f lab-bootstrap.mk terraform` installs the pinned version; a second run reports nothing to change.
- A tampered `SHA256SUMS`, a signature from another key, or a wrong pin each fail by name.

## Verified
2026-10-23, on Linux x86_64 with a copy of the role whose only changes were the OS/arch assert and the asset name (`linux_amd64`), against the real releases.hashicorp.com:
- A fresh dry run reported 1 pending change. The apply installed Terraform v1.17.0, with a good signature under the pinned key and the version assert passing. A re-run and a converged dry run were both `changed=0`.
- These failed by name, with nothing installed: a tampered SHA256SUMS with the real signature (BADSIG); an attacker keyring plus a valid attacker signature (gpgv rc 0, but VALIDSIG not under the pinned key); a wrong pinned fingerprint; a Homebrew copy present; the version `1.18.0-beta1`; and each of the five parameters removed in turn. An unpublished version (`9.9.9`) stopped at the SHA256SUMS download with HTTP 404.
- `lab-provision.mk validate test` passes through `$(TERRAFORM)` (6 tests).

**Not yet run on the Mac:** `/usr/bin/unzip`, Homebrew's gpg/gpgv, the darwin_arm64 asset, and `make -f lab-bootstrap.mk terraform` and `check`. The state stays fixed-unverified until then.

## Related
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md), [Role Contract](/concepts/role-contract--01a166e751ce.md)
