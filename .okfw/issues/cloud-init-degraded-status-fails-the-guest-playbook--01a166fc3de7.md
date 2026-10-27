---
id: "01a166fc-3de7-750c-a20b-9a70a06903c9"
title: "cloud-init degraded status fails the guest playbook"
type: "issue"
tags:
  - "issue"
  - "cloud-init"
  - "vm-baseline"
  - "fedora"
created: "2026-10-22T23:19:29-05:00"
timestamp: "2026-10-22T23:19:29-05:00"
description: "`cloud-init status --wait` exits 2 (done, recoverable errors) on Fedora 44 because the early hostnamectl call fails before D-Bus, and the guest playbook treated that as fatal."
x:
  severity: "high"
  priority: "P1"
  state: "fixed"
  origin: "pre-existing (site.yml)"
  found: "2026-10-22, KVM test VM, first dry run"
---

# cloud-init degraded status fails the guest playbook

**Severity high, P1, fixed.** It stopped every provisioning run at its first task.

## What happens
cloud-init's `set_hostname` runs `hostnamectl set-hostname` before the system bus is up, logs `Failed to set the hostname` four times, and finishes `degraded done`. The hostname is set moments later anyway (`fedora-dev-1.local`). `cloud-init status --wait` then exits **2**, and `site.yml` ran it with no `failed_when`, so any non-zero exit was fatal. The lab's user-data template sets the same hostname/fqdn keys, so the Mac lab is expected to hit it too.

## Fix
`vm-baseline.yml` runs `cloud-init status --wait --long` and fails only on rc 1 (cloud-init failed). On rc 2 it prints the recoverable errors, so they stay visible.

## Verified
2026-10-23, KVM test VM (Fedora 44): every vm-baseline run since reports the four hostname warnings and continues.

## Related
- [Lab fedora44min-aarch64-dev-ws](/labs/lab-fedora44min-aarch64-dev-ws--01a1664337f7.md)
