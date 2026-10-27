---
id: "01a166e7-51ce-7289-9e1a-49982deffd09"
title: "Role Contract"
type: "concept"
tags:
  - "ansible"
  - "roles"
  - "contract"
created: "2026-10-22T22:56:38-05:00"
timestamp: "2026-10-22T22:56:38-05:00"
description: "Every Ansible role in this project has no defaults, opens with fail-fast contract and parameter asserts, and ends by asserting the requested state; what that means, and where it departs from the trusted-devcontainer roles it came from."
---

# Role Contract

Every role under `ansible/roles/host/`, `ansible/roles/gateway/` and `ansible/roles/guest/` follows one
contract (decided 2026-10-22; the gateway lane since 2026-10-24, with the host bracket,
[Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md)). It was adopted from `trusted-devcontainer-features` (ADR-012, its *Feature Role Contract*) so that an
operator can trust what a role did: it either did exactly what was asked or stopped and said why.

## No defaults

`defaults/main.yml` is empty in every role. The **playbook passes every parameter**, so its role
entries (and pin block) are the single source of truth. A default would be a second source that quietly
wins whenever the wiring is broken: a typo'd parameter name would install the default version instead of
failing. Derived values (URLs, asset names, arch maps) and constants (pinned checksum maps) live in
`vars/main.yml`. They are not inputs.

## Brackets: fail before doing anything

`tasks/main.yml` opens with two groups of asserts:

1. **Contract bracket**: *where* the role is running.
   - Host roles: macOS on Apple Silicon over a local connection.
   - Guest roles:
     - facts were gathered;
     - the variant (`distribution|lower` + major version: `fedora44`, `redhat9`, `rocky10`, …) is in the
       role's compatibility list;
     - the arch is aarch64 or x86_64;
     - the **lane** (below).
2. **Parameter bracket**: *what* it was asked. Every input is checked for presence **and shape**
   (versions `X.Y.Z`, checksums 64 hex characters, enumerations by membership). The failure message names
   the parameter and the form it expects.
   - Mandatory inputs must be non-empty.
   - Pass-through inputs (`*_checksum`) must be *defined* but may be `''`, which means "use the pinned map
     or the release's checksums file".
   - The assert is `quiet: true` and has **no `success_msg`**. Ansible templates every task argument
     before the assert runs, so a `success_msg` that names a missing input fails as
     `'x' is undefined`, and the `fail_msg` never appears. The summary of what was requested is a
     separate "Show the requested parameters" debug task right after the assert. See
     [A missing role parameter fails in success_msg, not the named fail_msg](/issues/a-missing-role-parameter-fails-in-success-msg-not-the-named-fail-msg--01a168e0c882.md).

## Lanes (guest roles)

- **System lane**: the play connects as `admin` with `become: true`. The role asserts `id -un` is `root`.
  It covers packages, `/etc` and systemd: `ca_trust`, `system_packages`, `podman`, `tmux`,
  `lazyvim_system`.
- **User lane**: the play connects *as* `guest_user` (dev) with its own key and no become. The role
  asserts it runs as `guest_user` and reads the home directory from facts gathered as that account.
  Everything lands in that home and is owned correctly by construction, with no owner/group or chown.

This mirrors the userland/`--privileged` lanes of the devcontainer runner (`run-feature.sh`). The two
plays of `python-stack.yml` are the lanes. Connecting as dev also avoids Ansible's "become an
unprivileged user" temp-file problem, which would need ACLs on the guest.

## Downloads and verification

- Every `get_url` passes `checksum:`. The only exceptions are the tasks that fetch a checksums file,
  release manifest or keyring, which cannot verify themselves.
- Before every download, the role asserts that a checksum *resolved*: an empty `checksum:` makes
  `get_url` skip verification, not fail it.
- Checksums-file lookups are anchored to the whole asset name, so `…tar.gz.sbom` cannot answer for
  `…tar.gz`.
- The last assert checks that the **requested version** is what is installed, matched against the tool's
  real output (anchored, so `1.7` cannot pass for `1.7.1`), not merely that a binary runs.

## Dry runs

This project always runs Ansible as `--check --diff` first ([Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)).
The source roles never had to. So here:

- probes use `check_mode: false`;
- install work sits in a block gated on `<role>_install_required and not ansible_check_mode`, with a
  "Would …" debug that reports it;
- prerequisite asserts (uv, nvim present) and final verifications are skipped **only** in a dry run in
  which an earlier role would provide the prerequisite;
- **a `command`/`shell` task is invisible to a dry run.** Ansible skips it and reports it as skipped,
  not changed, unless it has `creates:`/`removes:`. `ansible-confirm.sh` trusts the changed count, so
  such a task must either be gated on `not ansible_check_mode` with a "Would …" task beside it, or carry
  a `# check-mode:` comment naming the task that does report the change. See
  [Dry run hides changes made by command tasks](/issues/dry-run-hides-changes-made-by-command-tasks--01a167252342.md).
- probes that ask another process (a systemd user manager over D-Bus) retry, then **fail by name**.
  A probe that could not ask must never read as "not configured" and turn into a change on every run.

`lazyvim` stops its dry run before the plugin and parser steps. Starting Neovim at all lets lazy.nvim
install plugins, so it cannot be probed read-only. A lockfile change still shows in the config diff.

## Enforcement

`scripts/check-role-contract.sh` runs in `make -f lab-provision.mk lint`. It checks:

- `defaults/` declares nothing;
- both brackets exist, including the lane assert;
- every asserted input is `<role>_`-prefixed and not also set in `vars/`;
- the parameter-bracket assert has no `success_msg`;
- every `get_url` has `checksum:`;
- no `| default(...)` masks a fact or `guest_user`;
- every `command`/`shell` task that reports a change is visible to a dry run (above).

## Deviations from the source roles, and why

| Source | Here | Why |
|---|---|---|
| `_name` variables | `<role>_name` | ansible-lint `var-naming[no-role-prefix]`, which `make lint` enforces |
| `run-feature.sh` injects `_target_*` | facts plus `guest_user` | No runner on a VM; facts gathered as the lane's account are the truth |
| `dnf5` shell-out (`install-packages.yml`) | `ansible.builtin.package` | The source venv could not import libdnf5; the guest's system Python can, and the module is check-mode aware |
| fixed `/tmp/*-feature-install` | `tempfile` plus `always:` cleanup | this project's existing pattern |
| ruff via `uv tool install` | release tarball plus pinned SHA-256 | Hash-pinned like uv, and needs no uv |
| Claude Code via bun | native binary plus manifest SHA-256 | No bun/Node runtime; same trust path as `install.sh` |
| `_securedevcontainer_variant` from an inventory file | derived from facts | Covers `fedora44`, `redhat9/10`, `rocky9/10`; only fedora44 is lab-verified |

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md), [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)
- [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
