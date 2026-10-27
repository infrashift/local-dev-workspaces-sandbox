---
id: "01a166e7-51e9-7015-9b6b-f7976ce24d27"
title: "Provision the Python Stack"
type: "runbook"
tags:
  - "runbook"
  - "python-stack"
  - "ansible"
created: "2026-10-22T22:56:38-05:00"
timestamp: "2026-10-22T22:56:38-05:00"
description: "Step-by-step: export the ZScaler chain, bring up the lab VM, and apply the python-stack playbook with its dry run and an idempotency re-run."
---

# Provision the Python Stack

**Prerequisite:** a bootstrapped host ([Bootstrap the macOS Host](/runbooks/bootstrap-the-macos-host--01a1664337ef.md)).

```sh
cd labs/fedora44min-aarch64-dev-ws
```

1. **Export the proxy's CA chain** (once, and again whenever ZScaler rotates it). The chain goes into
   `CA_TRUST_DIR` (`<project>/.pki/ca-trust/`, gitignored):

   ```sh
   mkdir -p ../../.pki/ca-trust
   security find-certificate -a -c Zscaler -p /Library/Keychains/System.keychain > ../../.pki/ca-trust/zscaler.pem
   ```

   Every `*.pem`/`*.crt` there is trusted. The `ca_trust` role refuses anything that is not an
   unexpired CA certificate, and refuses a file holding a private key. `apply` and `play` stop early
   (`ca-trust-check`) if the directory is empty.
2. **Create the VM**: `make -f lab-provision.mk apply`. Terraform runs `vm-baseline.yml`, which
   installs the chain, prints each certificate's subject and SHA-256, and probes Fedora's mirrors,
   GitHub, PyPI, the registries and Claude Code's releases over verified TLS.
3. **Apply the stack**: `make -f lab-provision.mk play PLAYBOOK=python-stack`. Then verify it:
   `make -f lab-provision-verify.mk STACK=python-stack` ([Verify the Host and the Lab](/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)).
   - The dry run lists what it would install. Type `yes` to apply.
   - A first apply downloads about 1 GB, mostly the dnf upgrade, Claude Code and the uv-installed
     language servers.
4. **Re-run it.** The dry run must report nothing to change. A change on a re-run is a bug: record it
   under `issues/`.
5. **Use it**:
   - `make -f lab-provision.mk ssh` starts the `dev-session` tmux layout (nvim | shell).
   - Rootless podman runs as dev: `podman run --rm registry.fedoraproject.org/fedora:44 true`.

## Changing the stack

Copy `ansible/playbooks/python-stack.yml` and keep the roles you need. Every role entry states every
parameter, because there are no defaults. Bump a version by editing it there. A version outside a role's
pinned checksum map also needs its `*_checksum`; the role says so by name.

## Troubleshooting

- *"is not trusted through …tls-ca-bundle.pem"* or a curl probe certificate error: the exported chain is
  not the one intercepting this guest. Re-export it from the keychain.
- *A probe times out*: the network may need an explicit proxy (`HTTPS_PROXY`), which trust alone
  cannot fix.
- *"cloud-init … rc 1"*: cloud-init itself failed; see `make -f lab-provision.mk console`. rc 2 (the
  Fedora 44 hostname warning) is reported, not fatal.
- *A user-lane role says "must run as that account"*: it was applied from the system-lane play.

## Related
- [Guest Roles](/tooling/guest-roles--01a166e751e0.md), [Role Contract](/concepts/role-contract--01a166e751ce.md),
  [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md)
