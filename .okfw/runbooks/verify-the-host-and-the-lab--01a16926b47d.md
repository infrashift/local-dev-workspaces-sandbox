---
id: "01a16926-b47d-7451-80e6-199bab3f32a7"
title: "Verify the Host and the Lab"
type: "runbook"
tags:
  - "runbook"
  - "verification"
  - "pytest"
  - "testinfra"
created: "2026-10-23T09:25:06-05:00"
timestamp: "2026-10-27T10:15:00-05:00"
description: "Step-by-step: verify the host after lab-bootstrap.mk, the gateway after lab-gateway.mk and the lab VMs after lab-provision.mk with the read-only pytest suites."
status: "draft"
---

# Verify the Host and the Lab

Three pytest suites verify the state of the lab. They do not configure anything. The bootstrap
playbook and the guest playbooks configure the host and the lab VMs, and each role asserts its own
result ([Role Contract](/concepts/role-contract--01a166e751ce.md)). The suites are a second, independent
check of the full result (decided 2026-10-23).

## Order of operations

```sh
make -f lab-bootstrap.mk all          # configure the host
make -f lab-bootstrap-verify.mk       # verify the host: tests/host
make -f lab-gateway.mk                # install the zero-trust gateway
make -f lab-gateway-verify.mk         # verify the gateway: tests/gateway
make -f lab-provision.mk apply        # create and configure the lab VMs
make -f lab-provision-verify.mk       # verify the lab VMs: tests/guest/baseline
make -f lab-provision-verify.mk STACK=python-stack   # after: lab-provision.mk play PLAYBOOK=python-stack
make -f lab-provision-verify.mk STACK=sandbox        # the gateway end to end, after python-stack and secrets
```

Do not install the gateway until all the host tests pass, and do not provision the lab until all
the gateway tests pass. The gateway is a stage of its own
([Gateway Separated from the Host Bootstrap](/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md));
its suite is described in [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md).
The operator procedure is in the lab's `README.md`.

## Rules for the tests

- **The tests are read-only.** They do not change the host or a lab VM. They write only to a pytest
  temporary directory and to the SSH control sockets in `~/.ssh/ai-sandbox-verify-*`.
- **Each expected value comes from its source.** A test does not write a pin or a path again. The
  sources are:
  - `lab-config.mk`: Make gives each path to pytest as an environment variable (`PYTEST_ENV`).
  - The `vars:` block and the role parameters of each playbook.
  - The constants in each role's `vars/main.yml`.
  - `inventory/group_vars/all/vars.yml`.
  - `requirements.lock` and `requirements.yml`.
  - `terraform.tfvars`. The guest suite reads `var.vms` through `terraform console`, so Terraform itself
    parses the file.
- **Each failure message gives the repair.** The message names the make target that repairs the fault,
  for example `make -f lab-bootstrap.mk host TAGS=ssh`.
- **The tests run outside Make only with the environment.** Without the `PYTEST_ENV` variables, pytest
  stops at once and tells you to use Make.

## What the suites check

| Suite | Checks |
|---|---|
| `tests/host` | The versions of uv, ruff and Terraform in `.tools/bin`. The Ansible venv against `requirements.lock`, exactly. The collections against `requirements.yml`. The apt packages, `/dev/kvm`, the `libvirt`/`kvm` groups, `virsh`, and the OVMF 4M pair. The storage directories. The SSH key pairs (mode 0600, matched halves) and the host configs, through `ssh -G`, including that only the dev session forwards the sandbox agent. The base image: its name agrees with `terraform.tfvars`, and it is read-only and qcow2. Its SHA-256 agrees with the CHECKSUM, which has a valid signature from the pinned Fedora key. The become vault is private and encrypted. |
| `tests/gateway` | Vault, Vault Proxy, Consul, Envoy, the allow list from catalog to Envoy's route table, the gateway CA in `CA_TRUST_DIR`, the sandbox firewall and the sandbox ssh-agent. See [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md). |
| `tests/guest/baseline` | Each lab VM runs and has a DHCP lease. `terraform plan` has no pending changes. Fedora 44 aarch64, the hostname, and cloud-init done. The vCPUs, the memory and the root file system size agree with `terraform.tfvars`. `admin` has sudo and `dev` does not, both keys are the lab keys, the passwords are locked, and sshd refuses passwords. The gateway CA anchors, the bundle, the environment files, and TLS to each `trust_probe_urls` address as `dev`. On **every** lab VM, upstream-1 included: the TLS-inspecting proxy's anchors are exactly `TLS_INSPECTION_DIR`'s chain (none without one), trusted, and really signing what the VM reaches ([Run the Lab Behind a TLS-Inspecting Proxy](/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md)). Each package in `dev_packages`. |
| `tests/guest/sandbox` | From the sandbox, as `dev` in a login shell. Isolation: the gateway's names resolve to it, the tunnel refuses them, nothing is reachable directly, the guest holds exactly the surrogates and nothing shaped like a real PAT or API key. Scenarios: pip through the tunnel; then for **each** repository in `github_repos`: it refuses an anonymous clone and clones with its git surrogate (by path), the API reads it with its git and api surrogates, and its three GitHub MCP servers (local, upstream-1, hosted) act as the PAT's login (asked through the gateway) and read it; Claude Code registers every server ([GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md)); scp to the SCP target through the tunnel with the forwarded agent; api.anthropic.com accepts the surrogate key. Anti-replay: each surrogate gets 403 "surrogate host mismatch" off its hosts; each repository's git and api surrogates get 403 "surrogate repository mismatch" on another repository's path (github.com, api.github.com, raw.githubusercontent.com); unknown or real-looking credentials get 403 "unknown or revoked surrogate". |
| `tests/guest/python-stack` | Each user-lane tool is the pinned version and is the one on the `dev` PATH. The Claude Code auto-updater is off when the version is pinned. Each LazyVim plugin is at its locked commit. Podman is rootless for `dev`, with lingering and the user API socket. The tmux configuration loads. |

The baseline suite does not examine whether packages are current. A test for no pending update would
fail each time that Fedora releases an update.

## The test environment

- The suites run in their own venv, `.pytest/` at the project root. This venv is separate from the
  Ansible venv, so the test tools never change it.
- `requirements-pytest.txt` pins pytest, pytest-testinfra and PyYAML. `requirements-pytest.lock` holds
  the hashes for `x86_64-unknown-linux-gnu`, and `uv pip sync --require-hashes` builds the venv from it.
- To change a pin, edit `requirements-pytest.txt`. Then run `make -f lab-bootstrap-verify.mk lock`, and
  commit the two files.
- `PYTEST_ARGS` gives more arguments to pytest, for example `PYTEST_ARGS="-k ssh -x"`.

## Add tests for a new stack

1. Make a directory `tests/guest/<stack>/`. Use the name of the playbook, without `.yml`.
2. Add the test modules. Read each pin with `lab.role_params("<stack>.yml", "<role>")`.
3. Use the `admin` and `dev` fixtures to connect to each lab VM.
4. Run `make -f lab-provision-verify.mk STACK=<stack>`.

## Decisions

- **pytest-testinfra.** The `host` fixture is the Linux host. The `admin` and `dev` fixtures connect with
  the configs that the lab_ssh role writes. Thus `vm-proxy.sh` finds the address of each lab VM
  ([Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md)).
- **SSH multiplexing goes in `ssh_extra_args`.** testinfra's `controlpath` option is put into a
  `%`-formatted command without escapes, so the `%C` token causes an error. `ssh_extra_args` is
  escaped. `%C` is a hash, so the socket path stays short
  ([SSH ControlPath can exceed the Unix socket path limit](/issues/ssh-controlpath-can-exceed-the-unix-socket-path-limit--01a1670cfffb.md)).
- **The drift test uses `terraform plan -detailed-exitcode`.** `terraform/ansible.tf` applies
  `vm-baseline.yml` again when a file under `ansible/`, a guest role or the CA chain changes. Thus an
  edit that is not applied yet also fails this test.
- **`--import-mode=importlib`.** The host and guest suites both have a `test_packages.py`.
- **`pythonpath = . gateway guest/sandbox`.** The gateway suite's helpers, `tests/gateway/gateway_lab.py`,
  stay inside its own directory, so a later move of the gateway takes them along; the sandbox suite's
  `sandbox_lab.py` likewise.
- **The sandbox suite writes nothing to the guest.** Its MCP client, `mcp_probe.py`, travels base64-encoded
  on the command line and runs with `python3 -I`.
- **`lab_vm` covers every lab VM.** `vm` (and `admin`, `dev`) stay the dev_ws group; `lab_vm` and
  `lab_vm_admin` add the upstream fixtures, for checks that apply to both.

## Status

On 2026-10-24, on the Linux x86_64 host, `tests/host` passed (49 tests) and `tests/gateway` passed
(141 tests). On 2026-10-27 `tests/gateway` passed again (146 passed, 7 skipped) after the GitHub MCP and
TLS-inspection changes, and the guest suites collect. On 2026-10-27, with the lab provisioned,
`tests/guest/baseline` passed (43 passed, 8 skipped: no TLS-inspection chain) once its aarch64-era tests
were ported ([Baseline guest tests were never ported from the aarch64 Mac lab](/issues/baseline-guest-tests-were-never-ported-from-the-aarch64-mac-lab--01a17e521736.md)),
and `tests/gateway` passed (171 passed, 4 skipped). Later that day, after the python-stack and the fixes
the first sandbox runs found (see the issues of 2026-10-27), `make -f lab-provision-verify.mk STACK=sandbox`
passed (127 passed, 8 skipped: no TLS-inspection chain), with `tests/gateway` at 256 passed, 4 skipped.
`tests/guest/python-stack` has not run yet. When it passes too, set this page to `stable`.

## Related
- [Run the UAT Suites](/runbooks/run-the-uat-suites--01a17f21b82c.md): the manual acceptance tests that each name the tests here that cover the same behavior
- [Provision and Verify the Gateway](/runbooks/provision-and-verify-the-gateway--01a170011e5c.md), [Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md)
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md), [Guest Roles](/tooling/guest-roles--01a166e751e0.md), [Python Toolchain](/tooling/python-toolchain--01a1664337e8.md)
- [Lab fedora44min-aarch64-dev-ws](/labs/lab-fedora44min-aarch64-dev-ws--01a1664337f7.md)

## Source
- `labs/fedora44min-x86_64-dev-ws/lab-bootstrap-verify.mk`, `lab-gateway-verify.mk`, `lab-provision-verify.mk`, `tests/`
- `requirements-pytest.txt`, `requirements-pytest.lock`
