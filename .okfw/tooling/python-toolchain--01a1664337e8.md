---
id: "01a16643-37e8-783f-9c58-13a87f113a88"
title: "Python Toolchain"
type: "reference"
tags:
  - "python"
  - "uv"
  - "ansible"
  - "supply-chain"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "uv, ruff, and the hash-locked .ansible-core-<version> virtual environment: what is pinned where, and how to re-pin."
---

# Python Toolchain

- **uv** goes into `~/.local/bin`. It is installed by `lab-bootstrap.mk` before Ansible exists, from the
  GitHub release tarball verified against its `.sha256`. **ruff** goes in the same place, installed by
  the `release_binary` role.
- **Venv:** `.ansible-core-<version>/` at the project root, built from uv-managed CPython 3.13 (no brew
  python). Its name comes from the `ansible-core==` pin in `requirements.txt`, the single source that
  `lab-config.mk` and the lab's `terraform/ansible.tf` (via `regex()`) both read.
- **`requirements.lock`** is compiled once **with hashes** for `aarch64-apple-darwin` and committed. The
  venv is built with `uv pip sync --require-hashes`.

  This deliberately departs from libvirt-qemu-kvm's `bootstrap.mk`, which recompiled the lock on every
  venv init and so never actually locked anything. Re-pin with `make -f lab-bootstrap.mk lock`.
- **Test venv:** `.pytest/` at the project root, also uv-managed CPython 3.13. It is built from its own
  hashed `requirements-pytest.lock` (pytest, pytest-testinfra, PyYAML), so the test tools never change the
  Ansible venv. Re-pin with `make -f lab-bootstrap-verify.mk lock`; see
  [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md).
- **Collections:** `requirements.yml` pins exact versions of community.general and community.crypto,
  installed into `.collections/` (gitignored). `ansible.cfg` sets `collections_scan_sys_path = False`,
  so nothing leaks in from the system.
- `passlib` was dropped: it is unmaintained, breaks on Python ≥ 3.13, and nothing here hashes
  passwords. `ansible-lint` and `yamllint` were added; `make -f lab-provision.mk lint` runs them with
  shellcheck, ruff and `scripts/check-role-contract.sh` ([Role Contract](/concepts/role-contract--01a166e751ce.md)).
  ansible-lint covers both `ansible/roles/host/` and `ansible/roles/guest/` and passes the `production`
  profile.

## Related
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)
