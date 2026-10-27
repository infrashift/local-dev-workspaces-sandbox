# PLAN: Zero-Trust Surrogate Secrets Injection Gateway (Linux KVM Host ↔ Fedora Sandbox Guest)

**Status: implemented** in `labs/fedora44min-x86_64-dev-ws`. This plan records the design and maps
each phase to the code that carries it out. The first version of this plan targeted an Apple Silicon
Mac (socket_vmnet, `pf`, Homebrew); that version is in the Git history.

An AI agent (Claude Code) works in the Fedora 44 guest `fedora-dev-1`. Every real credential lives in
HashiCorp Vault on the Linux host. Envoy reads it over a unix socket, and only Envoy injects it into
the requests that leave the host. The agent holds published **surrogate** credentials that are
worthless anywhere but the gateway, and has no network path except Envoy's two listeners.

> **Supported hosts:** the host automation is tested only on Pop!_OS and Ubuntu 24.04 LTS. Another
> distribution probably needs changes first. See the lab README, "Supported hosts".

---

## 1. Architectural & Security Boundary Overview

```text
+--------------------------------------------------------------------------------------------------+
| Linux x86_64 host (Pop!_OS / Ubuntu 24.04, KVM + libvirt)                                        |
|                                                                                                  |
|  [Vault]  /run/vault/vault.sock  <---  [Vault Proxy]  /run/vault-proxy/proxy.sock (group envoy)  |
|   real credentials (kv-v2 ai-sandbox/),       ^  AppRole envoy-gateway, read-only                |
|   SSH CA (ssh-sandbox/), audit log            |  (Lua httpCall over the unix socket)             |
|                                               |                                                  |
|  [Consul] /run/consul/consul.sock      [Envoy] on 192.168.150.1 (virbr50, sandbox bridge)        |
|   egress allow list (K/V)  --consul-template-->  :8080 CONNECT tunnel (no TLS termination)       |
|                                                  :443  TLS gateway + Lua surrogate swap          |
|  [sandbox ssh-agent] /run/user/<uid>/ai-sandbox/ssh-agent.sock  (Vault-signed 8 h certificate)   |
|  [nftables inet ai_sandbox] only the sandbox subnet reaches 192.168.150.1:8080 and :443          |
+----------|-----------------------------------------|---------------------------|---------------+
           | ssh ForwardAgent (dev session only)     | 192.168.150.0/24          | host uplink / NAT
           v                                         | isolated: no NAT, no DNS  v
+--------------------------------------------------+  |   +---------------------------------------+
| Sandbox VM fedora-dev-1  192.168.150.10           |<-+   | Upstreams                             |
|  Claude Code, uv, ruff, pyrefly, podman, git ...  |      |  1. PyPI and other allow-listed sites |
|  surrogates only; gateway hosts -> 192.168.150.1  |      |  2. github.com, api.github.com, ...   |
|  HTTPS_PROXY=http://192.168.150.1:8080            |      |  3. GitHub MCP: hosted, or upstream-1 |
+--------------------------------------------------+      |     192.168.151.10 (virbr51, NAT)     |
                                                          |  4. api.anthropic.com                 |
                                                          |  5. SSH target scp-target@upstream-1  |
                                                          +---------------------------------------+
```

### Security invariants

1. **No secret material in the guest.** `fedora-dev-1` holds only the surrogates of
   `ansible/vars/gateway.yml` (`claude:surrogate-github-git-scratch-1`,
   `sk-ant-surrogate-claude-code`, ...). The real GitHub PATs and the Anthropic key never leave the
   host. `tests/guest/sandbox/test_isolation.py` greps the guest for anything shaped like a real one.
2. **No network path from the guest to Vault or Consul.** Both listen on unix sockets only, opened by
   group membership and file ACLs. The guest is on an isolated libvirt network (no NAT, no route, no
   DNS), and its only reachable address is Envoy's.
3. **Bound surrogates (anti-replay).** Each surrogate is bound to its `target_hosts` and, for GitHub,
   to one repository. Envoy's Lua filter answers `403` for an unknown surrogate, a host mismatch or a
   repository mismatch, after Envoy normalizes the path. It fails closed.
4. **Firewall and listener lockdown.** The `inet ai_sandbox` nftables table lets the sandbox bridge
   reach only Envoy's two ports (plus DHCP), and refuses the gateway address on every other
   interface. Every Envoy filter chain also matches only the sandbox subnet, so neighbours on the
   LAN, upstream-1 or a container cannot use the gateway even if the firewall table is gone.
5. **Default-deny egress.** The CONNECT tunnel opens only hosts on the allow list in Consul, and never
   a gateway host (whose requests must pass the surrogate swap).
6. **Least privilege everywhere.** One fine-grained, read-only PAT per repository; read-only GitHub
   MCP servers; an operator token that reads metadata but no secret; a 15-minute, audited
   break-glass token for the rare real read.

---

## 2. How the use cases are implemented

| Use case | Guest request | Envoy listener | Credential and TLS action on the host | Egress |
| --- | --- | --- | --- | --- |
| **1. Unauthenticated package installs** (`pip`, `uv`, `dnf`, `podman pull`) | Reads `HTTPS_PROXY=http://192.168.150.1:8080` and sends `CONNECT pypi.org:443` | `:8080` CONNECT tunnel | No TLS termination, no Lua. The route table that consul-template renders from the allow list decides; anything else gets `403 ai-sandbox egress: not on the allow list`. The guest verifies the site's own certificate end to end. | Host uplink |
| **2. GitHub git and REST API**, one repository per PAT | `NO_PROXY` names `github.com`; `/etc/hosts` maps it to `192.168.150.1`. git sends `Basic` with the repository's surrogate from `~/.config/ai-sandbox/git-surrogates` (a get-only credential helper, by path) | `:443` TLS gateway | Envoy terminates TLS with the gateway certificate, looks up the surrogate's record through Vault Proxy, checks host and repository, replaces the header with `Basic base64(login:PAT)`, and opens verified TLS to GitHub | Host uplink |
| **3. GitHub MCP servers** (local, self-hosted, hosted) | Claude Code's MCP config holds `Bearer` surrogates: the local server calls `api.github.com` and `raw.githubusercontent.com`; the remote ones are `mcp.upstream.ai-sandbox.test` and `api.githubcopilot.com` | `:443` TLS gateway | As use case 2. For the self-hosted server on upstream-1, Envoy verifies it with the upstream-test CA and rewrites the Host header. The servers run read-only | Uplink; upstream-1 over virbr51 |
| **4. SCP to an SSH host** | `/etc/ssh/ssh_config.d/50-ai-sandbox-proxy.conf`: `ProxyCommand ncat --proxy 192.168.150.1:8080 --proxy-type http %h %p` | `:8080` CONNECT tunnel to `host:22` (needs an allow-list entry) | Transport: a raw TCP tunnel. Authentication: the dev ssh session forwards the dedicated sandbox ssh-agent, which holds only a Vault-signed certificate (8 hours, principal `scp-target`). The guest can ask it to sign and cannot read the key | upstream-1 over virbr51 |
| **5. Claude Code to Anthropic** | `ANTHROPIC_API_KEY=sk-ant-surrogate-claude-code`; `api.anthropic.com` maps to the gateway | `:443` TLS gateway | Envoy swaps the `x-api-key` surrogate for the real key. A request with no key gets `401` from the gateway itself | Host uplink |

The gateway's routes and every surrogate are declared once, in `ansible/vars/gateway.yml`. The
gateway playbook, the guest playbooks and the tests all read them from there.

---

## 3. Phase-by-phase implementation

Every phase runs through make, as a dry run first that applies only after you type `yes`. Every role
follows the role contract: no defaults, input checks first, and asserts on the result.

### Phase 0: Host bootstrap (`make -f lab-bootstrap.mk all`)

**Objective:** a Pop!_OS or Ubuntu 24.04 host ready for KVM, with the pinned tools.

- `linux_host_packages`: QEMU, libvirt, OVMF and the tools with `apt`; the operator joins `libvirt`
  and `kvm`. It asserts a Debian-family host.
- `vm_storage`: `/var/lib/ai-sandbox/{images,pools}`, readable by `libvirt-qemu`.
- `lab_ssh`: the lab's key pairs and `~/.ssh/config.d/` aliases (`local.<lab>.{dev,admin}`).
- `release_binary`, `hashicorp_release`: ruff by SHA-256; Terraform by GPG signature from the pinned
  HashiCorp key, then SHA-256.
- `fedora_cloud_image`: the Fedora Cloud Base qcow2, verified by GPG signature and SHA-256.
- The Ansible venv and Python requirements are hash-locked (`requirements.lock`).

Verify: `make -f lab-bootstrap-verify.mk`.

### Phase 1: PKI (`gateway_pki`, tag `pki`)

**Objective:** a private CA for Envoy's downstream TLS that the guests trust, and that can vouch for
nothing else.

- The gateway CA is ECDSA P-384, `pathlen:0`, with **critical name constraints**: the gateway hosts'
  DNS names are permitted, and every IPv4 and IPv6 address is excluded. Its key stays root-only in
  `/etc/ai-sandbox/pki`.
- Envoy's certificate names every gateway host and no IP. (An IP SAN under an IP name constraint made
  Claude Code's TLS stack refuse the chain.)
- The CA certificate goes to `CA_TRUST_DIR` (`.pki/gateway-ca/`), which the guests' `ca_trust` role
  installs.
- An upstream-test CA, constrained to the lab's upstream names, signs the self-hosted MCP server's
  certificate; only Envoy trusts it.
- **Behind a TLS-inspecting proxy** (Zscaler or similar), put its CA chain in `TLS_INSPECTION_DIR`:
  Envoy then verifies public upstreams with the host's roots plus that chain, and the guests trust it
  too. Without such a proxy, leave the directory empty.

### Phase 2: Vault, Vault Proxy and the real credentials (tag `vault`)

**Objective:** store each real credential under its surrogate's id, and expose it only to Envoy.

- `hashicorp_release` installs Vault and Consul, verified by signature.
- `vault_server`: Vault with `file` storage and **no TCP listener**; the socket
  `/run/vault/vault.sock` is group `vault-clients` plus an ACL for the operator. An unseal service
  unseals it at boot. The audit log `/var/log/vault/audit.log` fails closed.
- `vault_gateway`:
  - kv-v2 mount `ai-sandbox/`: a record per surrogate at `ai-sandbox/data/surrogates/<id>`, where
    `<id>` is the unpadded base64url of the surrogate credential. A record holds `target_hosts`,
    `repo`, the `header` to inject and its real `value`.
  - Policy `envoy-surrogate-reader` (read `data/surrogates/*` only) for the AppRole `envoy-gateway`.
  - Policy `ai-sandbox-operator` (metadata only, plus signing the sandbox agent's certificate) for
    the operator's periodic token, and `ai-sandbox-break-glass` for break-glass tokens.
  - SSH CA mount `ssh-sandbox/`, role for the principal `scp-target`.
- `vault_proxy`: auto-auth with the AppRole, listener `/run/vault-proxy/proxy.sock`, group `envoy`.
  Envoy never holds a Vault token.
- **Real credentials:** `make -f lab-gateway.mk secrets [NAME=<secret>]` prompts for each PAT and the
  Anthropic key, keeps them ansible-vault encrypted in
  `ansible/inventory-host/host_vars/localhost/vault.yml` (not in Git), and writes them into Vault. The
  playbook checks that each PAT reads its repository and that the Anthropic key works.

### Phase 3: Consul and the egress allow list (tag `consul`)

**Objective:** a default-deny allow list that the operator changes in seconds, with a reason.

- `consul_server`: one server, HTTP on `/run/consul/consul.sock` only, ACLs on, gossip encrypted.
- `consul_egress`: seeds `ai-sandbox/egress/baseline/<category>/<host>:<port>` from
  `ansible/vars/egress-baseline.yml` (PyPI, Fedora and Red Hat repositories, Go, npm, crates,
  Maven, Galaxy, Terraform registry, container registries, Claude Code downloads; HTTPS only, each
  with a probe), and prunes what the catalog no longer names. Operator entries live under
  `ai-sandbox/egress/allow/` and are never touched by Ansible.
- Operator commands: `make -f lab-gateway.mk allowlist`, `allow HOST=<host:port> REASON="…"`,
  `deny HOST=<host:port>`.

### Phase 4: Envoy (`envoy_release`, `envoy_gateway`, tags `binaries,envoy`)

**Objective:** the two listeners on `192.168.150.1`, the surrogate filter, and verified upstreams.

- Envoy is verified by the GPG signature on its checksums file, then SHA-256.
- **`:8080` CONNECT tunnel:** `upgrade_configs: CONNECT`, accepts HTTP/1.0 CONNECT (for ncat), and a
  route table that consul-template renders from Consul
  (`ansible/roles/gateway/envoy_gateway/templates/connect-routes.ctmpl.j2`). Gateway hosts are denied
  on every tunnel port; everything not listed gets `403`.
- **`:443` TLS gateway:** one virtual host per gateway route, path normalization, a token bucket per
  host, then `surrogate.lua` (`templates/surrogate.lua.j2`):
  1. no credential: pass on an `anonymous` route (public GitHub reads), else `401`;
  2. turn `Basic`, `Bearer`, `token` or `x-api-key` into the record id, and read the record through
     Vault Proxy's socket;
  3. `403` for an unknown surrogate, a host mismatch or a repository mismatch;
  4. drop `authorization` and `x-api-key`, set the record's header to its value;
  5. any Lua error answers `500` (fail closed).
- Upstream clusters re-originate TLS with SNI and name verification, using the host's public roots
  (plus the TLS-inspection chain when present), or the upstream-test CA for upstream-1.
- Every filter chain matches only the sandbox subnet. The admin API is an `envoy`-only socket; the
  operator gets a GET-only view (`/run/envoy/admin-readonly.sock`).
- systemd units for Envoy and consul-template run sandboxed, as their own users.

### Phase 5: The sandbox ssh-agent (`sandbox_ssh_agent`, tag `ssh_agent`)

**Objective:** SCP from the guest with no key in the guest.

- A dedicated user-level ssh-agent at `/run/user/<uid>/ai-sandbox/ssh-agent.sock` holds one egress
  key and its Vault-signed certificate (principal `scp-target`, 8 hours).
- `make -f lab-gateway.mk agent-cert` renews the certificate. Only the `local.<lab>.dev` ssh alias
  forwards this agent (`ForwardAgent yes`, `IdentityAgent` the agent's socket); the admin alias
  forwards nothing.
- upstream-1's sshd (`upstream_ssh_target`) trusts the Vault SSH CA for `scp-target`.

### Phase 6: Host firewall (`sandbox_firewall`, tag `firewall`)

**Objective:** the sandbox reaches Envoy's two ports and nothing else on the host, and no one else
reaches Envoy.

- Its own nftables table `inet ai_sandbox`, loaded by `ai-sandbox-firewall.service` (never
  `nftables.service`, whose `flush ruleset` would wipe libvirt's tables).
- Input: refuse the gateway address on every interface except the sandbox bridge and `lo`; from the
  bridge, allow replies, DHCP and the two Envoy ports, and reject everything else.
- Forward: reject the sandbox bridge both ways, so no route out exists even if the guest adds one.

Verify phases 1 to 6: `make -f lab-gateway.mk check` (nothing to change), then
`make -f lab-gateway-verify.mk`.

### Phase 7: Lab VMs and guest configuration (`make -f lab-provision.mk apply`)

**Objective:** the sandbox VM on the isolated network, routed through the gateway, holding surrogates
only.

- Terraform (`terraform/modules/libvirt-network`, `libvirt-vm`) makes the isolated network `ai-sandbox`
  (virbr50, `192.168.150.0/24`, no forward, no DNS), the NAT network `ai-sandbox-upstream` (virbr51),
  `fedora-dev-1` and `upstream-1`, then runs `site.yml`.
- `vm-baseline.yml` on the sandbox:
  - `ca_trust`: installs the gateway CA (and the TLS-inspection chain, if any) and sets
    `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS` and `PIP_CERT`.
  - `sandbox_egress`: `/etc/hosts` maps every gateway host to `192.168.150.1`; the proxy variables in
    `/etc/profile.d/` and systemd's environment; `NO_PROXY` names every gateway host; the ssh
    `ProxyCommand` through ncat; dnf pinned to one allow-listed mirror.
- `upstream.yml` on upstream-1: the self-hosted GitHub MCP server behind stunnel
  (`upstream_github_mcp`) and the SCP target (`upstream_ssh_target`).
- `make -f lab-provision.mk play PLAYBOOK=python-stack`, user lane:
  - `sandbox_user_egress`: proxy settings for the toolchains that ignore `HTTPS_PROXY`.
  - `sandbox_surrogates`: `~/.bashrc.d/ai-sandbox-surrogates.sh` and the get-only git credential
    helper over `~/.config/ai-sandbox/git-surrogates` (git cannot erase a surrogate after a `401`).
  - `claude_code`: the pinned Claude Code, auto-updater off, `ANTHROPIC_API_KEY` = the surrogate,
    `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, and nine MCP servers (local, self-hosted and hosted,
    for each of the three repositories), each with its repository's surrogate.
  - `github_mcp_server`: the pinned local GitHub MCP server, run with `--read-only`.

---

## 4. End-to-end verification

The plan's checks are automated and read-only; run them in this order.

| Check | Command | What it proves |
| --- | --- | --- |
| Host | `make -f lab-bootstrap-verify.mk` | Pinned tools and verified images, KVM, storage, ssh identities, the become vault |
| Gateway | `make -f lab-gateway-verify.mk` | Vault policies and audit, the operator CLI cannot read a secret, Consul, the allow list in Envoy, the firewall, listeners limited to the sandbox subnet, the PKI and its name constraints, the ssh-agent |
| Guest baseline and stack | `make -f lab-provision-verify.mk STACK=python-stack` | The guest configuration and the pinned tools |
| End to end | `make -f lab-provision-verify.mk STACK=sandbox` | See below |

The sandbox suite (`tests/guest/sandbox/`) runs on the guest as `dev`, with the surrogates only:

1. **Use case 1:** `pip` installs through the tunnel; a direct connection out fails; the tunnel refuses
   gateway hosts.
2. **Use case 2:** each repository refuses an anonymous clone and clones with its surrogate; the API
   reads it with the git and api surrogates; a `401` cannot erase the surrogate.
3. **Use case 3:** each MCP server (local, self-hosted, hosted) acts as the PAT's login and reads its
   repository; Claude Code itself connects to the self-hosted servers (`claude mcp list`).
4. **Use case 4:** `scp` to `scp-target@192.168.151.10` succeeds with the forwarded agent (needs the
   allow-list entry `192.168.151.10:22` and a fresh certificate).
5. **Use case 5:** the Anthropic API accepts the surrogate key; without a key the gateway answers
   `401` itself.
6. **Anti-replay:** each surrogate on a host outside its `target_hosts` gets `403 surrogate host
   mismatch`; each repository's surrogate on another repository, including through `../` and `//`
   path tricks, gets `403 surrogate repository mismatch`; an unknown or real-looking token gets
   `403 unknown or revoked surrogate`; a burst past the rate limit gets `429`.
7. **Isolation:** the guest holds exactly the surrogates and nothing shaped like a real credential;
   upstream-1 cannot reach the gateway.

For the manual, story-form acceptance tests of the same flows, see
`labs/fedora44min-x86_64-dev-ws/uat/`. For the security model at a high level, see
`labs/fedora44min-x86_64-dev-ws/security-controls.md`.

---

## 5. Changes from the macOS plan

| macOS plan | Fedora lab on Linux |
| --- | --- |
| QEMU under Hypervisor.framework, socket_vmnet `bridge100` (`192.168.105.0/24`) with shared NAT | KVM under libvirt, an isolated network virbr50 (`192.168.150.0/24`) with no NAT and no DNS |
| `pf` anchor on `bridge100` | nftables table `inet ai_sandbox`, plus Envoy filter chains limited to the sandbox subnet |
| Vault on `127.0.0.1:8200`; Vault Agent socket `/tmp/vault-agent.sock` | Vault with no TCP listener; sockets under `/run/vault/` and `/run/vault-proxy/`, by group and ACL |
| Hand-run `openssl` RSA CA with an IP SAN | `gateway_pki`: P-384, name-constrained CA, no IP SAN |
| Azure DevOps and an internal MCP server over Zscaler ZPA | GitHub (three private repositories, one PAT each), GitHub MCP servers, Anthropic; Zscaler optional through `TLS_INSPECTION_DIR` |
| Surrogates bound to one host | Surrogates bound to a set of hosts and to one repository; path normalization; rate limits |
| Any-site CONNECT tunnel (dynamic forward proxy for every host) | Default-deny allow list in Consul, rendered into Envoy by consul-template |
| macOS `ssh-agent` over virtio-serial and socat | A dedicated host ssh-agent with an 8-hour Vault-signed certificate, forwarded by the dev ssh session only |
| Shell commands run by hand | Ansible roles behind `make` targets, dry run then `yes`, with read-only pytest suites |
