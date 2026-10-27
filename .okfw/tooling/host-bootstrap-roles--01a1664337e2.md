---
id: "01a16643-37e2-71d6-844d-a0cf0d7d6997"
title: "Host Bootstrap Roles"
type: "reference"
tags:
  - "ansible"
  - "bootstrap"
  - "macos"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "The localhost Ansible roles that prepare an Apple Silicon Mac, and the dry-run-then-type-yes policy every Ansible run follows."
---

# Host Bootstrap Roles

`ansible/roles/host/` holds the roles that a lab's `ansible/playbooks/bootstrap-host.yml` applies to
**localhost**. Make builds only what Ansible needs to run (uv, venv, collections), and everything else is
here (decided 2026-10-22). The roles for the VMs live beside them in `ansible/roles/guest/`
([Guest Roles](/tooling/guest-roles--01a166e751e0.md)).
The zero-trust gateway's roles are not host bootstrap roles: they live in `ansible/roles/gateway/`
and run from `lab-gateway.mk`, after the host checks pass
([Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)).
The macOS role table below is pending its Linux rewrite.

## Supported hosts
**The Linux host roles and the gateway roles are tested only on Pop!_OS and Ubuntu 24.04 LTS**
(decided 2026-10-27, before the repository went public). They are Debian/Ubuntu-specific:
`linux_host_packages` asserts `os_family == Debian` and installs with `apt`, `bootstrap-host.yml`
names Debian packages and the `/usr/share/OVMF/` firmware, `vm_storage` assumes QEMU runs as
`libvirt-qemu`, the libvirt-vm module relies on AppArmor's `virt-aa-helper`, and three gateway roles
install `acl` or `nftables` with `apt`. Another distribution probably needs changes to these roles,
and must pass the host, gateway and sandbox suites before anyone relies on the gateway there. The
lab README's "Supported hosts" section lists each place to change
(`labs/fedora44min-x86_64-dev-ws/README.md`).

The roles follow the [Role Contract](/concepts/role-contract--01a166e751ce.md) (since 2026-10-22):

- no defaults, so `bootstrap-host.yml` passes every parameter, and its pin block is the single source of
  truth;
- each opens by asserting it runs on macOS/arm64 locally, and checks the shape of every input;
- each ends by asserting the result (installed formula versions, key files at 0600, the requested ruff,
  Terraform and socket_vmnet versions, a read-only base image).

`socket_vmnet`'s prefix, socket and service id are constants in `vars/`: the upstream launchd plist
fixes them.

| Role (tag) | Does | Verification |
|---|---|---|
| `mac_host_packages` (packages) | Homebrew packages: qemu, gnupg, shellcheck. Asserts Darwin arm64, `hvf`, and an equal-size edk2 pair | — |
| `vm_storage` (storage) | `~/VMs/images`, `~/VMs/machines/<lab>` | — |
| `lab_ssh` (ssh) | key pairs + host configs; see [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md) | — |
| `release_binary` (ruff) | GitHub-release tool into `~/.local/bin` | `.sha256` sibling file, then the installed version |
| `hashicorp_release` (terraform) | A HashiCorp product (Terraform today) into `~/.local/bin`. Refuses while Homebrew also provides it | `SHA256SUMS` signature whose **primary key is the pinned fingerprint**, then SHA-256 from that file, then the installed version |
| `socket_vmnet` (socket_vmnet) | `/opt/socket_vmnet` + launchd (**sudo**) | `SHA256SUMS` (anchored lookup, digest asserted), path containment |
| `fedora_cloud_image` (image) | Fedora Cloud Base qcow2, read-only | GPG signature from the **pinned key fingerprint**, then SHA-256 from the *signed* text |

Prerequisite: Homebrew. Ansible drives `brew` but does not install Homebrew itself.

### Terraform (since 2026-10-23)

Terraform came from the `hashicorp/tap` formula until 2026-10-23. That copy was unpinned, checked only
against the tap's own SHA-256, and never version-asserted. See
[Host Terraform is unpinned and not signature-verified](/issues/host-terraform-is-unpinned-and-not-signature-verified--01a168da023a.md).
`hashicorp_release` replaced it:

- **Pins.** `terraform_version` and `hashicorp_key_fpr` sit in `bootstrap-host.yml`'s pin block. The
  fingerprint is HashiCorp's security key, `C874 011F … 72D7 468F`, which expires on 2030-03-01.
- **Primary key, not subkey.** HashiCorp signs with a subkey. gpgv's `VALIDSIG` line names that subkey
  first and the primary key last, and the role pins the last field.
- **Keyring format.** The keyring is published ASCII-armored, which gpgv cannot read. The role
  dearmors it with a throwaway `--homedir`, so `~/.gnupg` is never touched.
- **One copy only.** The role refuses while `<homebrew_prefix>/bin/terraform` exists.
  `lab-provision.mk` calls `$(TERRAFORM)` (`~/.local/bin/terraform`, from lab-config.mk) by path,
  because its PATH puts the Homebrew prefix first.
- **Other products.** Packer, Vault or Consul is another role entry with a different
  `hashicorp_release_product`: every product shares the release layout and the signing key.

## Dry run first, then type "yes"

`scripts/ansible-confirm.sh` wraps every interactive Ansible run (decided 2026-10-22):

1. It runs `--check --diff` and prints a "Pending changes" summary.
2. Only the exact answer `yes` applies; anything else, or no terminal, applies nothing.

With `CHECK_ONLY=1` it is a read-only readiness check, which `lab-bootstrap.mk check` and the
`lab-provision.mk` preflight use.

Check mode means a few patterns are deliberate:

- Downloads and installs sit in a `block` with `when: … and not ansible_check_mode`. A sibling
  "Would …" debug task with `changed_when: true` reports them, so a dry run never downloads anything and
  never needs sudo.
- Read-only probes use `check_mode: false`.
- `lab-bootstrap.mk` passes `--ask-become-pass` to the apply step only when socket_vmnet actually needs
  installing.

The Terraform-invoked guest playbook (`vm-baseline.yml` from `terraform/ansible.tf`) still runs
non-interactively. `terraform apply` has already asked for confirmation, and the VM is disposable.
`make -f lab-provision.mk ansible` re-runs it with the dry-run/confirm flow, and
`make -f lab-provision.mk play PLAYBOOK=<name>` does the same for a stack such as `python-stack`.

## Related
- [Bootstrap the macOS Host](/runbooks/bootstrap-the-macos-host--01a1664337ef.md), [Python Toolchain](/tooling/python-toolchain--01a1664337e8.md)
