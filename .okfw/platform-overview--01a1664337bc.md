---
id: "01a16643-37bc-7d1b-9981-46d591b9a02d"
title: "Platform Overview"
type: "overview"
tags:
  - "overview"
  - "linux"
  - "kvm"
  - "ai-sandbox"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-27T17:00:00-05:00"
description: "Orientation to local-dev-workspaces-sandbox (formerly tf-labs): Terraform-provisioned Fedora VMs under KVM/libvirt on a Pop!_OS or Ubuntu x86_64 host, an AI-agent sandbox behind a zero-trust gateway, and a map of this wiki."
---

# Platform Overview

**local-dev-workspaces-sandbox** (formerly tf-labs) provisions disposable **Linux VMs under KVM/libvirt on a Linux x86_64 host** for
AI-augmented software development. Terraform creates the VMs, cloud-init sets their identity,
Terraform writes an Ansible inventory, and Ansible configures the host, the gateway and the guests.
The sandbox VM, where the AI agent works, has no route out: its only way to the internet is the
[Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md) on the host,
which holds every real credential.

## Supported hosts
**The host bootstrap and the gateway automation are tested only on Pop!_OS and Ubuntu 24.04 LTS.**
They install with `apt` and assume Debian/Ubuntu package names, the `/usr/share/OVMF/` firmware, the
`libvirt-qemu` user and AppArmor. Any other Linux distribution probably needs changes to the host
automation first, and must pass the verify suites before anyone relies on the gateway there. See
[Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md) and the lab README's
"Supported hosts" section. The guests are Fedora cloud images and do not depend on the host
distribution.

The project began on an Apple Silicon Mac (QEMU/HVF, socket_vmnet). The Linux x86_64 host replaced
that port; its pages below are kept for history and marked deprecated.

## How a lab is used

Each lab (`labs/<lab>/`) has three makefiles, each with a read-only `-verify.mk` partner, and all
include a shared `lab-config.mk`:

1. `lab-bootstrap.mk`: one-time host setup. It installs uv, the hashed Ansible venv and pinned
   collections, then runs the host playbook, always as a dry run first that you confirm by typing `yes`.
2. `lab-gateway.mk`: the gateway (Vault, Consul, Envoy, the sandbox firewall and ssh-agent), its
   credentials, the egress allow list and break-glass.
3. `lab-provision.mk`: the VMs: `apply`, `status`, `start`, `stop`, `ssh`, `destroy`, and `play` for a
   stack such as `python-stack`.

The test suites are pytest ([Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)),
and the manual acceptance tests are stories ([Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)).
The lab README gives the procedures, and `security-controls.md` beside it the security model.

## Map

- Gateway: [Zero-Trust Surrogate Gateway](/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md),
  [Surrogate Credential Model](/concepts/surrogate-credential-model--01a17ecc92e2.md),
  [Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md),
  [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md),
  [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md),
  [Egress Allow List in Consul KV](/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md),
  [Egress Baseline Catalog](/concepts/egress-baseline-catalog--01a17f01fd6d.md),
  [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md),
  [SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md),
  [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md),
  [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)
- Concepts: [Role Contract](/concepts/role-contract--01a166e751ce.md),
  [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md),
  [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md),
  [Base Images and Machine Overlays](/concepts/base-images-and-machine-overlays--01a1664337cc.md)
- Tooling: [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md),
  [Guest Roles](/tooling/guest-roles--01a166e751e0.md),
  [ansible-inventory Module](/tooling/ansible-inventory-module--01a1664337dc.md),
  [Python Toolchain](/tooling/python-toolchain--01a1664337e8.md)
- Runbooks: [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md),
  [Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md),
  [Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md),
  [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md),
  [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md)
- Issues: `issues/` (state, severity and priority under `x:`)
- Deprecated, from the macOS port: [Lab fedora44min-aarch64-dev-ws](/labs/lab-fedora44min-aarch64-dev-ws--01a1664337f7.md),
  [QEMU HVF on Apple Silicon](/concepts/qemu-hvf-on-apple-silicon--01a1664337c1.md),
  [socket_vmnet Networking](/concepts/socket-vmnet-networking--01a1664337c7.md),
  [qemu-hvf-vm Module](/tooling/qemu-hvf-vm-module--01a1664337d6.md),
  [Bootstrap the macOS Host](/runbooks/bootstrap-the-macos-host--01a1664337ef.md)

## Source
- `labs/` (one directory per lab), `terraform/modules/`, `ansible/roles/{host,gateway,guest}/`, `scripts/`
