# fedora44min-x86_64-dev-ws

This lab makes a Fedora 44 x86_64 developer workstation for an AI agent on a Linux x86_64 host. KVM
runs the virtual machines under libvirt. The sandbox VM has no route out: its only way to the
internet is the zero-trust gateway on the host, which holds every real credential so that the VM
never does. Ansible configures the host, the gateway and the virtual machines.

> **Warning:** The host automation is tested only on Pop!_OS and Ubuntu (24.04 LTS). Another Linux
> distribution probably needs changes to it first. See [Supported hosts](#supported-hosts).

This file gives the procedures for the operator. For the design and the reasons for it, read these
wiki pages:

| Page | For |
|---|---|
| [Zero-Trust Surrogate Gateway](../../.okfw/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md) | What the gateway is made of, with a link to each part |
| [Vault and Consul Host Trust](../../.okfw/concepts/vault-and-consul-host-trust--01a17ebdba27.md) | The threat model, and why unix sockets instead of TLS or mTLS |
| [Operator Interfaces](../../.okfw/concepts/operator-interfaces--01a17ebdba31.md) | Make targets for changes, read-only CLIs, break-glass |
| [Gateway Separated from the Host Bootstrap](../../.okfw/concepts/gateway-separated-from-the-host-bootstrap--01a17000956a.md) | Why the gateway is a stage of its own |
| [Provision and Verify the Gateway](../../.okfw/runbooks/provision-and-verify-the-gateway--01a170011e5c.md) | The gateway procedure and its tests in detail |
| [Gateway Credentials in the Host Inventory](../../.okfw/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md) | Where the real credentials live, one fine-grained PAT per repository |
| [GitHub MCP Servers Behind the Gateway](../../.okfw/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md) | The local, self-hosted and hosted GitHub MCP servers, and their surrogates |
| [Run the Lab Behind a TLS-Inspecting Proxy](../../.okfw/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md) | The extra configuration behind Zscaler or a similar proxy |
| [Corporate TLS Interception (ZScaler)](../../.okfw/concepts/corporate-tls-interception-zscaler--01a166e751d7.md) | Why that configuration is needed, and what it does not cover |
| [Verify the Host and the Lab](../../.okfw/runbooks/verify-the-host-and-the-lab--01a16926b47d.md) | What each test suite checks |

## Terms

| Term | Meaning |
|---|---|
| Host | The Linux x86_64 machine that runs the lab: Pop!_OS or Ubuntu 24.04 LTS ([Supported hosts](#supported-hosts)). |
| Gateway | Vault, Vault Proxy, Consul, consul-template and Envoy on the host, with the sandbox firewall and the sandbox ssh-agent. |
| Lab VM | A virtual machine that this lab makes. `terraform/terraform.tfvars` gives the list: the sandbox `fedora-dev-1` and the test fixture `upstream-1`. |
| Lab directory | `labs/fedora44min-x86_64-dev-ws`. Run all the commands in this file from this directory. |

## Order of operations

```sh
make -f lab-bootstrap.mk become-vault      # once
make -f lab-bootstrap.mk all               # Procedure 1
make -f lab-bootstrap-verify.mk            # Procedure 2
make -f lab-gateway.mk                     # Procedure 3
make -f lab-gateway.mk secrets             # Procedure 4 (once)
make -f lab-gateway-verify.mk              # Procedure 5
make -f lab-provision.mk apply             # Procedure 6
make -f lab-provision-verify.mk            # Procedure 7
make -f lab-provision.mk play PLAYBOOK=python-stack   # Procedure 8 (optional)
make -f lab-provision-verify.mk STACK=sandbox         # Procedure 9: the gateway end to end
```

Do each step only after the step before it passes.

## Supported hosts

> **Warning:** The host bootstrap (`lab-bootstrap.mk`) and the gateway automation (`lab-gateway.mk`)
> are tested only on **Pop!_OS and Ubuntu (24.04 LTS)**. On any other Linux distribution, expect to
> change the host automation before it works. Do not run it on another distribution and assume that
> a clean run means a secure gateway: the verify suites check the result on the tested hosts only.

The host automation depends on Debian/Ubuntu in these places:

| What | Where | On another distribution |
|---|---|---|
| Packages install with `apt`, and the role asserts `os_family == Debian` | `ansible/roles/host/linux_host_packages` (the first host role stops here) | A package-manager task, and the distribution's own package names |
| Debian/Ubuntu package names: `qemu-system-x86`, `libvirt-daemon-system`, `ovmf`, `netcat-openbsd` and others | `ansible/playbooks/bootstrap-host.yml` (`apt_packages`) | Other names (Fedora, for example: `qemu-kvm`, `libvirt-daemon-kvm`, `edk2-ovmf`) |
| The gateway installs `acl` and `nftables` with `apt` | `ansible/roles/gateway/vault_server`, `consul_server`, `sandbox_firewall` | The same packages through the distribution's package manager |
| The UEFI firmware is `/usr/share/OVMF/OVMF_CODE_4M.fd` and `OVMF_VARS_4M.fd` | `bootstrap-host.yml`, `terraform/modules/libvirt-vm/variables.tf` | Other paths (Fedora: `/usr/share/edk2/ovmf/`) |
| QEMU runs as the `libvirt-qemu` user, which sets the permissions of the VM storage | `ansible/roles/host/vm_storage` | Another user (Fedora and RHEL: `qemu`) |
| libvirt confines QEMU with AppArmor; the disks are file sources so that `virt-aa-helper` can label them | `terraform/modules/libvirt-vm/main.tf` | SELinux (sVirt) labels instead, on Fedora and RHEL; check the image and pool contexts |
| The host tests check packages with `dpkg-query` | `tests/host/test_packages.py` | The distribution's package query |

The gateway's own security rests on Linux features that every current distribution has (systemd,
nftables, unix-socket permissions and ACLs). The guest VMs are Fedora 44 cloud images and do not
depend on the host distribution.

## Before you start

Make sure that you have these items:

- A Pop!_OS or Ubuntu 24.04 LTS x86_64 host with KVM (`/dev/kvm`) and sudo. See
  [Supported hosts](#supported-hosts).
- Membership in the `libvirt` and `kvm` groups. The bootstrap adds you; log in again after it does.
- For the GitHub scenarios: the private repositories in `ansible/vars/gateway.yml` `github_repos`
  (`infrashift/private-scratch-1`, `-2` and `-3`), each holding at least one file (a README). For
  **each** repository, a fine-grained PAT limited to it alone: Repository access "Only select
  repositories" with just that one, and the permissions Contents and Metadata, read-only. The resource
  owner is the organisation, which may have to approve the PAT. For GitHub's hosted MCP server, the
  organisation must also allow it.
- For the Claude scenario: an Anthropic API key.
- **Only if the host is behind a TLS-inspecting proxy** (Zscaler, for example): the proxy's CA chain.
  Do [Run the Lab Behind a TLS-Inspecting Proxy](../../.okfw/runbooks/run-the-lab-behind-a-tls-inspecting-proxy--01a17ddfc607.md)
  before procedure 1. Without such a proxy, do nothing: `TLS_INSPECTION_DIR` stays empty.

## Procedure 1: Bootstrap the host

1. Store your sudo password for Ansible. This is needed once. The password is encrypted with
   ansible-vault, and Git records neither the encrypted file nor its key:

   ```sh
   make -f lab-bootstrap.mk become-vault
   ```

2. Start the bootstrap:

   ```sh
   make -f lab-bootstrap.mk all
   ```

3. Read the list of pending changes. The dry run shows this list.
4. To apply the changes, type `yes`. To stop with no changes, type a different answer.
5. If the output tells you to add `Include config.d/*` to `~/.ssh/config`, add this line near the top
   of that file.

   > **Note:** Put the line before all `Host` and `Match` blocks. If you put it after a block, ssh uses
   > it only in that block.

## Procedure 2: Verify the host

> **Note:** The tests do not change the host. They compare the host with the pinned versions in the
> playbooks, the lock files and `terraform/terraform.tfvars`.

1. Run the host tests:

   ```sh
   make -f lab-bootstrap-verify.mk
   ```

2. Make sure that all the tests pass.
3. If a test fails, read its failure message. The message gives the command that repairs the fault.
4. Do the repair.
5. Do step 1 again.

## Procedure 3: Install the gateway

> **Caution:** Do not install the gateway until all the host tests pass.

1. Start the gateway playbook:

   ```sh
   make -f lab-gateway.mk
   ```

2. Read the list of pending changes, then type `yes` to apply them.
3. Make sure that a second dry run finds nothing to change:

   ```sh
   make -f lab-gateway.mk check
   ```

## Procedure 4: Load the real credentials

Do this once, and again to rotate a credential. The credentials are kept ansible-vault encrypted in
`ansible/inventory-host/host_vars/localhost/vault.yml`, which Git ignores, and the gateway playbook
writes them into Vault. See [Gateway Credentials in the Host Inventory](../../.okfw/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md).

1. Run this command, and type each value at its prompt: each repository's PAT, then the Anthropic API
   key. The terminal does not show what you type:

   ```sh
   make -f lab-gateway.mk secrets
   ```

   > **Note:** To set or rotate only one, add `NAME=private-scratch-2` (a key of `github_repos`) or
   > `NAME=anthropic`.

2. The command then runs the gateway playbook for Vault. Read the dry run and type `yes`. The playbook
   checks that each PAT reads its private repository and that the Anthropic key works. If one does not,
   it names it and says why.

## Procedure 5: Verify the gateway

> **Note:** The tests do not change the host. They read Vault and Consul through their unix
> sockets, which open for you by ACL, with your operator tokens, and Envoy through its read-only
> admin view. To look around yourself, run `eval "$(make -s -f lab-gateway.mk cli)"`, then use
> `vault` or `consul`. To read a real credential in an emergency, run
> `make -f lab-gateway.mk break-glass REASON="why"`: a 15-minute token, written to the audit log.
> See [Operator Interfaces](../../.okfw/concepts/operator-interfaces--01a17ebdba31.md).

1. Run the gateway tests:

   ```sh
   make -f lab-gateway-verify.mk
   ```

2. Make sure that all the tests pass. If a test fails, use steps 3 to 5 of procedure 2.

## Procedure 6: Provision the lab

> **Caution:** Do not provision the lab until all the gateway tests pass. The provisioning checks the
> host and the gateway first, and stops if either has pending changes.

1. Create the lab VMs and configure them:

   ```sh
   make -f lab-provision.mk apply
   ```

2. Read the Terraform plan.
3. To apply the plan, type `yes`.

   > **Note:** Terraform waits until each lab VM accepts SSH connections. Then it applies the
   > `site.yml` playbook.

## Procedure 7: Verify the lab

> **Note:** The tests connect to each lab VM as `admin` and as `dev`. They do not change the lab VMs.
> They also make sure that Terraform has no pending changes.

1. Run the lab tests:

   ```sh
   make -f lab-provision-verify.mk
   ```

2. Make sure that all the tests pass. If a test fails, use steps 3 to 5 of procedure 2.

## Procedure 8: Add the Python stack (optional)

1. Apply the stack to the lab VMs:

   ```sh
   make -f lab-provision.mk play PLAYBOOK=python-stack
   ```

2. Read the list of pending changes.
3. To apply the changes, type `yes`.
4. Run the lab tests and the stack tests:

   ```sh
   make -f lab-provision-verify.mk STACK=python-stack
   ```

5. Make sure that all the tests pass. If a test fails, use steps 3 to 5 of procedure 2.

## Procedure 9: Verify the gateway end to end (the sandbox suite)

> **Note:** Do this after procedure 8 and procedure 4. The tests run on the sandbox VM as `dev`, with
> the surrogate credentials only, and change nothing.

1. For the SCP scenario, allow the SCP target through the tunnel, and renew the agent certificate if it
   is older than 8 hours:

   ```sh
   make -f lab-gateway.mk allow HOST=192.168.151.10:22 REASON="scenario 4: scp to upstream-1"
   make -f lab-gateway.mk agent-cert
   ```

2. Run the lab tests and the sandbox tests:

   ```sh
   make -f lab-provision-verify.mk STACK=sandbox
   ```

3. Make sure that all the tests pass. The tests cover isolation, the absence of real secrets on the
   guest, and, for each repository, git, the GitHub API and the three GitHub MCP servers. They also
   cover SCP, Anthropic, and anti-replay across hosts and across repositories. If a
   test fails, use steps 3 to 5 of procedure 2.

## Daily operation

| Task | Command |
|---|---|
| Show the state and the IP address of each lab VM. | `make -f lab-provision.mk status` |
| Connect to a lab VM as `dev`. | `make -f lab-provision.mk ssh` |
| Connect to a lab VM as `admin`, the user with sudo. | `make -f lab-provision.mk ssh ROLE=admin` |
| Stop the lab VMs. | `make -f lab-provision.mk stop` |
| Start the lab VMs, for example after the host restarts. | `make -f lab-provision.mk start` |
| Apply the guest playbooks again. | `make -f lab-provision.mk ansible` |
| Delete the lab VMs. The base images stay in `/var/lib/ai-sandbox/images`. | `make -f lab-provision.mk destroy` |
| List the egress allow list. | `make -f lab-gateway.mk allowlist` |
| Allow a site for the sandbox. | `make -f lab-gateway.mk allow HOST=example.com:443 REASON="why"` |
| Remove a site that you allowed. | `make -f lab-gateway.mk deny HOST=example.com:443` |
| Renew the sandbox ssh-agent's certificate (it lasts 8 hours). | `make -f lab-gateway.mk agent-cert` |

To operate on one lab VM only, add `VM=<name>`, for example `VM=fedora-dev-1`.

To see all the targets of each makefile, run these commands:

```sh
make -f lab-bootstrap.mk help
make -f lab-bootstrap-verify.mk help
make -f lab-gateway.mk help
make -f lab-gateway-verify.mk help
make -f lab-provision.mk help
make -f lab-provision-verify.mk help
```

## More information

- [security-controls.md](security-controls.md) gives the security controls at a high level, and how
  developers and the operator work safely with the AI agent.
- [Provision and Verify the Gateway](../../.okfw/runbooks/provision-and-verify-the-gateway--01a170011e5c.md)
  explains the gateway procedures and its tests.
- [Verify the Host and the Lab](../../.okfw/runbooks/verify-the-host-and-the-lab--01a16926b47d.md)
  explains the tests and how to add tests for a new stack.
- [Provision the Python Stack](../../.okfw/runbooks/provision-the-python-stack--01a166e751e9.md)
  explains the Python stack.
- [uat/README.md](uat/README.md) gives the manual acceptance tests: the developer's and the
  operator's daily work, as stories, on the Python stack.
  [Run the UAT Suites](../../.okfw/runbooks/run-the-uat-suites--01a17f21b82c.md) explains them.
