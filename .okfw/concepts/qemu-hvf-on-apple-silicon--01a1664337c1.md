---
id: "01a16643-37c1-7a79-92fc-b0af0330113f"
title: "QEMU HVF on Apple Silicon"
type: "concept"
tags:
  - "qemu"
  - "hvf"
  - "macos"
  - "aarch64"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "Why tf-labs drives qemu-system-aarch64 with Hypervisor.framework directly instead of libvirt, and the machine/firmware choices that follow."
status: "deprecated"
---

# QEMU HVF on Apple Silicon

> **Deprecated.** This page describes the original Apple Silicon Mac port, which the Linux x86_64 host replaced. It is kept for history. The current host is Pop!_OS or Ubuntu 24.04 LTS: see [Platform Overview](/platform-overview--01a1664337bc.md).

Guests run as `qemu-system-aarch64 -machine virt -accel hvf -cpu host`. Homebrew's QEMU is already signed
with the `com.apple.security.hypervisor` entitlement, so no root and no re-signing are needed. The
`mac_host_packages` role checks that `-accel help` lists `hvf`.

## Why not libvirt (decided while planning, 2026-10)

Homebrew libvirt supports `type='hvf'` domains and the `dmacvicar/libvirt` provider ships darwin_arm64
builds, but neither gets you far:

- On macOS libvirt is a server for the QEMU driver only. There is **no network driver**: no
  `libvirt_network`, no dnsmasq, and no lease-based IP discovery.
- The provider cannot pass raw QEMU arguments, so it cannot attach Apple vmnet either.

So Terraform drives QEMU directly through `terraform_data` + `local-exec`, the same style as
libvirt-qemu-kvm's virt-install module; see [qemu-hvf-vm Module](/tooling/qemu-hvf-vm-module--01a1664337d6.md).

## Machine and firmware

- `virt` machine (not `q35`). Disks and the cloud-init seed are virtio block devices; there is no SATA/IDE.
- UEFI from Homebrew's edk2 pair: `share/qemu/edk2-aarch64-code.fd` (read-only pflash unit 0) and a
  per-VM copy of `edk2-arm-vars.fd` (unit 1). The two pflash images must be the same size. Secure Boot
  does not come into it.
- The NIC is `virtio-net-pci` and shows up as `enp0s1`. That is why cloud-init's network-config matches
  by MAC, not by a name glob like `ens*`.

## Limits

- **M1 has no nested virtualization**: a guest can run podman, but not KVM.
- Terraform does not see drift if QEMU exits or the Mac reboots; `lab-provision.mk start` restarts VMs
  from their directories.

## Related
- [socket_vmnet Networking](/concepts/socket-vmnet-networking--01a1664337c7.md)
- [Base Images and Machine Overlays](/concepts/base-images-and-machine-overlays--01a1664337cc.md)
