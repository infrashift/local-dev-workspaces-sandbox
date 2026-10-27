---
id: "01a16643-37ef-7a31-9cbe-9a008ebabdf3"
title: "Bootstrap the macOS Host"
type: "runbook"
tags:
  - "runbook"
  - "bootstrap"
  - "macos"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "Step-by-step: prepare an Apple Silicon Mac for a tf-labs lab with lab-bootstrap.mk."
status: "deprecated"
---

# Bootstrap the macOS Host

> **Deprecated.** This page describes the original Apple Silicon Mac port, which the Linux x86_64 host replaced. It is kept for history. The current host is Pop!_OS or Ubuntu 24.04 LTS: see [Platform Overview](/platform-overview--01a1664337bc.md).

**Prerequisite:** Homebrew (https://brew.sh) on an Apple Silicon Mac.

**Moving from a Homebrew Terraform** (bootstrapped before 2026-10-23): run `brew uninstall terraform`
first. The `hashicorp_release` role refuses to install while `/opt/homebrew/bin/terraform` exists,
because whichever copy came first on PATH would win. Run `brew untap hashicorp/tap` too, once nothing
else uses the tap.

```sh
cd labs/fedora44min-aarch64-dev-ws
make -f lab-bootstrap.mk all
```

`all` runs these steps in order; each is idempotent and can also be run on its own:

1. `uv`: installs the pinned uv into `~/.local/bin`, SHA-256 verified. Add `~/.local/bin` to `PATH` if
   the notice says so.
2. `venv`: uv installs CPython 3.13 and builds `.ansible-core-<version>` from the hashed lock.
3. `collections`: installs the pinned community.general and community.crypto into `.collections/`.
4. `host`: the bootstrap playbook.
   - It runs as a **dry run** and lists the pending changes. Type `yes` to apply.
   - If socket_vmnet needs installing, you are asked for your sudo password at apply time.
   - Use `TAGS=ssh,image` (or `packages`, `storage`, `ruff`, `terraform`, `socket_vmnet`) to run part
     of it. A `TAGS` list without `socket_vmnet` never asks for sudo.
   - `make -f lab-bootstrap.mk terraform` is shorthand for `host TAGS=terraform`: the pinned Terraform
     (`terraform_version` in `bootstrap-host.yml`) into `~/.local/bin`.

Then:

- If the run printed the Include notice, add `Include config.d/*` near the top of `~/.ssh/config`.
- `make -f lab-bootstrap.mk check` should end with "Host is ready." (the dry run finds nothing to change).
- `make -f lab-bootstrap-verify.mk` must pass before you provision. It runs the read-only host test
  suite; see [Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md).

Next: [Lab fedora44min-aarch64-dev-ws](/labs/lab-fedora44min-aarch64-dev-ws--01a1664337f7.md).

## Troubleshooting
- *"Homebrew not found"*: install Homebrew, then re-run.
- *"not signed by the pinned key"*: the Fedora CHECKSUM was signed by a different key. Check
  `fedora_key_fpr` in `bootstrap-host.yml` against https://fedoraproject.org/security/, and never just
  update it to make the error go away.
- *"…_SHA256SUMS is not validly signed under the pinned key"*: the same check for a HashiCorp release.
  Compare `hashicorp_key_fpr` with https://www.hashicorp.com/security. The key expires on 2030-03-01,
  so expect to re-pin before then.
- *"a Homebrew terraform would shadow the pinned one"*: `brew uninstall terraform`, then re-run.
- socket_vmnet logs are in `/var/log/socket_vmnet/`.

## Related
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md), [Python Toolchain](/tooling/python-toolchain--01a1664337e8.md)
