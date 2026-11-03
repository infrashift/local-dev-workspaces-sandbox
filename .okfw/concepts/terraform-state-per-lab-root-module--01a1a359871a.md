---
id: "01a1a359-871a-7037-8ecb-536969192e86"
title: "Terraform State per Lab Root Module"
type: "concept"
tags:
  - "terraform"
  - "labs"
  - "multi-lab"
  - "decision"
created: "2026-11-03T15:38:35-06:00"
timestamp: "2026-11-03T15:38:35-06:00"
description: "Each lab's terraform/ is its own root module with local state, so state is already isolated per lab without workspaces; a second lab would instead collide on host-wide libvirt names, networks and the single-tenant gateway."
status: "draft"
---

# Terraform State per Lab Root Module

Each lab is its own Terraform root module, `labs/<lab>/terraform/`, with the default local backend. So
each lab already keeps its own `terraform.tfstate`, and Terraform workspaces are not used, and not
needed, to isolate state. This was asked and answered on 2026-11-03, before a second lab exists.

## Why not workspaces (analysis, not a recorded decision)
Workspaces are for many instances of *one* configuration: they share the configuration, the providers
and the tfvars, and switch state underneath them. Labs differ in exactly those things. Separate root
modules isolate labs more strongly than workspaces would. Moving to workspaces would couple the labs,
not separate them.

## What would collide with a second lab: open work
The shared names are on the host, not in Terraform state:
- `lab-config.mk` fixes the libvirt network names (`ai-sandbox`, `ai-sandbox-upstream`), the bridges (`virbr50`, `virbr51`), the CIDRs and `GATEWAY_IP`.
- The libvirt domain names are bare tfvars keys (`fedora-dev-1`, `upstream-1`; `terraform/modules/libvirt-vm/main.tf` `name = each.key`), and domain names are global in `qemu:///system`. The storage pool is already per lab (`POOLS_DIR/<lab>`).
- The gateway serves one host and one tenant: one sandbox bridge and firewall, one Consul prefix (`ai-sandbox/egress`), one `OPERATOR_DIR`, one sandbox ssh-agent ([Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)).

Recommended before lab #2, as a change of its own:
1. prefix the domain names with the lab (or a short lab id);
2. move the network, bridge and CIDR values into per-lab settings, with a guard that refuses an overlap with the labs already defined;
3. optionally keep state outside the source tree (`$(VM_ROOT)/state/<lab>/`);
4. decide whether the gateway is shared (per-lab routes, prefixes and principals) or runs once per lab. That decision belongs to [Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md).

## Related
- [Base Images and Machine Overlays](/concepts/base-images-and-machine-overlays--01a1664337cc.md)
