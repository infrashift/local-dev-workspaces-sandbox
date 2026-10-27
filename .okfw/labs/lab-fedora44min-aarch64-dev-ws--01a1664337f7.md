---
id: "01a16643-37f7-7bd1-8120-7425c100a1b6"
title: "Lab fedora44min-aarch64-dev-ws"
type: "lab"
tags:
  - "lab"
  - "fedora"
  - "aarch64"
  - "dev-workstation"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "A Fedora 44 aarch64 dev workstation VM on an Apple Silicon Mac: QEMU/HVF, socket_vmnet, cloud-init admin/dev users, Ansible-configured toolchain."
status: "deprecated"
---

# Lab fedora44min-aarch64-dev-ws

> **Deprecated.** This page describes the original Apple Silicon Mac port, which the Linux x86_64 host replaced. It is kept for history. The current host is Pop!_OS or Ubuntu 24.04 LTS: see [Platform Overview](/platform-overview--01a1664337bc.md).

One VM, `fedora-dev-1`: 4 vCPU, 8 GiB, 60 GiB overlay. It is built on the **Fedora Cloud Base Generic 44
aarch64** qcow2 (respin 1.7).

Fedora publishes no "minimal cloud image". Cloud Base Generic is the cloud-init image; "Fedora Minimal"
for aarch64 is a raw SBC image without cloud-init. The lab name keeps "min" anyway.

## Use

```sh
make -f lab-bootstrap.mk all          # once: see the bootstrap runbook
make -f lab-bootstrap-verify.mk       # host test suite; must pass before apply
make -f lab-provision.mk apply        # create the VM, wait for SSH, run vm-baseline.yml
make -f lab-provision-verify.mk       # guest test suite (STACK=python-stack after that play)
make -f lab-provision.mk status       # state + IP per VM
make -f lab-provision.mk ssh          # as dev;  ROLE=admin for the sudo user
make -f lab-provision.mk stop|start   # also restores VMs after a Mac reboot
make -f lab-provision.mk ansible      # re-run vm-baseline.yml (dry run, then "yes")
make -f lab-provision.mk play PLAYBOOK=python-stack   # a stack on top (dry run, then "yes")
make -f lab-provision.mk destroy      # keeps ~/VMs/images
```

On apply:

- cloud-init creates `admin` (sudo) and `dev` and grows the disk. It installs **no packages**: behind
  ZScaler, dnf cannot reach a mirror until the proxy's CA is trusted.
- `vm-baseline.yml`:
  - waits for cloud-init (rc 2, "degraded done", is reported, not fatal);
  - asserts Fedora 44 aarch64;
  - trusts the chain in `CA_TRUST_DIR` (`ca_trust`) and probes the mirrors, GitHub, PyPI, the
    registries and Claude Code's releases over verified TLS;
  - upgrades every package and installs the editable `dev_packages` list from
    `ansible/inventory/group_vars/all/vars.yml` (`system_packages`).
- Stacks go on top: [Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md).
- `apply` and `play` refuse to start while `CA_TRUST_DIR` holds no certificate
  ([Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)).

## Layout
- `lab-config.mk`: shared paths and versions. `lab-bootstrap.mk` / `lab-provision.mk`: see
  [Platform Overview](/platform-overview--01a1664337bc.md).
- `lab-bootstrap-verify.mk` / `lab-provision-verify.mk` and `tests/`: the pytest suites; see
  [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md).
- `README.md`: the operator procedure, in Simplified Technical English.
- `terraform/`: `qemu-hvf-vm` + `ansible-inventory` modules and Terraform-invoked Ansible.
  `terraform.tfvars` names the base image; keep it in step with the playbook's `fedora_respin`.
- `ansible/playbooks/bootstrap-host.yml` (host); `vm-baseline.yml` (every guest, run by Terraform);
  `python-stack.yml` (an example stack that imports the baseline). Roles:
  [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md), [Guest Roles](/tooling/guest-roles--01a166e751e0.md).

## Related
- [Bootstrap the macOS Host](/runbooks/bootstrap-the-macos-host--01a1664337ef.md), [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md),
  [Base Images and Machine Overlays](/concepts/base-images-and-machine-overlays--01a1664337cc.md), [qemu-hvf-vm Module](/tooling/qemu-hvf-vm-module--01a1664337d6.md)

## Source
- `labs/fedora44min-aarch64-dev-ws/`
