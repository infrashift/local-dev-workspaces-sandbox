---
id: "01a166fc-3ded-7569-8e05-0c715cb7f0df"
title: "First-boot dnf install cannot reach repositories behind ZScaler"
type: "issue"
tags:
  - "issue"
  - "cloud-init"
  - "zscaler"
  - "pki"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "cloud-init installed python3-libdnf5 on first boot, before any proxy CA was trusted, so behind ZScaler the install (and with it cloud-init and the playbook) failed."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "pre-existing (terraform cloud_init_packages default)"
  found: "2026-10-22, while planning the ZScaler work"
---

# First-boot dnf install cannot reach repositories behind ZScaler

**Severity high, P1, fixed.** Behind ZScaler a fresh VM could never finish cloud-init.

## What happens
`cloud_init_packages` defaulted to `["python3-libdnf5"]`. cloud-init runs dnf at first boot, before Ansible can install the ZScaler CA, so the TLS handshake to the mirrors fails.

While testing it turned out that the Fedora 44 Cloud Base image already ships `python3-libdnf5`, so the first-boot install was also redundant.

## Fix
The default is now `[]`. The `system_packages` role installs the bindings if they are missing, after `ca_trust` has run (`vm-baseline.yml`).

## Verified
2026-10-23, KVM test VM booted with no cloud-init packages: cloud-init finished, and system_packages found the bindings already installed. Not yet run behind the real ZScaler.

## Related
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
