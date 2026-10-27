---
id: "01a166e7-51e0-7623-a410-020ce7570d5c"
title: "Guest Roles"
type: "reference"
tags:
  - "ansible"
  - "roles"
  - "guest"
  - "fedora"
  - "rhel"
created: "2026-10-22T22:56:38-05:00"
timestamp: "2026-10-22T22:56:38-05:00"
description: "The Ansible roles in ansible/roles/guest/ for Fedora/RHEL/Rocky lab VMs: lane, inputs, verification, and where each was ported from."
---

# Guest Roles

`ansible/roles/guest/` holds roles for the lab **VMs**. They are separate from the localhost roles in
`ansible/roles/host/` ([Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)). Each
lab's `ansible.cfg` puts both directories on `roles_path`.

Every role follows the [Role Contract](/concepts/role-contract--01a166e751ce.md):

- no defaults;
- variant, lane and parameter asserts first;
- checksum-verified downloads;
- a final assert on the requested state.

The compatibility list is `fedora44`, `redhat9/10`, `rocky9/10`. **Only fedora44 is exercised by a lab**,
and EL prerequisites are asserted rather than assumed. The roles are a menu: a stack playbook picks the
ones it needs. `python-stack.yml` is the worked example
([Provision the Python Stack](/runbooks/provision-the-python-stack--01a166e751e9.md)).

## System lane (connect as admin, `become: true`)

| Role | Inputs | Installs / verifies | Ported from |
|---|---|---|---|
| `ca_trust` | `src_dir` (controller), `name`, `required`, `probe_urls` | Operator CA chain as anchors, `update-ca-trust`, env vars for tools with their own roots. Verifies `openssl verify` per anchor, then curl and python probes. `required: false` makes the chain optional: an empty directory removes that name's anchors. `vm-baseline.yml` applies it twice, for the gateway CA and for a TLS-inspecting proxy's chain. See [Corporate TLS Interception (ZScaler)](/concepts/corporate-tls-interception-zscaler--01a166e751d7.md) | new |
| `system_packages` | `list`, `upgrade` | dnf Python bindings, optional full upgrade, packages; verifies `rpm -q` | `site.yml` tasks |
| `podman` | `mode` (rootful/rootless), `rootless_user` | podman + passt. Rootless: subuid/subgid asserted, linger, user `podman.socket`, root socket off. Rootful: root socket. Verifies `podman info` (mode, overlay, uid map) and the socket | new |
| `tmux` | `session_name`, `editor_pane_command`, `shell_pane_percent`, `autostart` | `/etc/tmux.conf`, `dev-session`, login hook; verifies a config parse on a private socket | templates `tmux` |
| `lazyvim_system` | none | gcc, git, ripgrep, fd-find (EPEL asserted on EL) | templates `lazyvim/ansible-role-system` |

## User lane (connect as `guest_user`, no become)

| Role | Inputs | Source / verification | Ported from |
|---|---|---|---|
| `uv` | `version`, `checksum` | Release tarball, pinned SHA-256 map, `~/.local/share/uv-dist/<v>` | features `uv-ruff` |
| `ruff` | `version`, `checksum` | Release tarball, pinned SHA-256 map (not `uv tool`) | features `uv-ruff` |
| `jq` | `version`, `checksum` | Release binary, pinned map | features `jq` |
| `grype`, `syft` | `version`, `checksum` | Release tarball, the release's `checksums.txt` | features |
| `claude_code` | `version` (`X.Y.Z` / `stable` / `latest`), `environment`, `mcp_servers` | Native binary, SHA-256 from that release's `manifest.json`. A pinned version disables the auto-updater (`~/.bashrc.d/claude-code.sh`). `mcp_servers` are merged into `~/.claude.json`'s user-scope `mcpServers`, keeping everything else there, and read back | features `claude-code` (bun replaced) |
| `github_mcp_server` | `version`, `checksum` | github/github-mcp-server release tarball, SHA-256 from `vars/github-mcp.yml`, `~/.local/share/github-mcp-server/<v>`; verifies `--version`. See [GitHub MCP Servers Behind the Gateway](/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md) | new |
| `neovim` | `version`, `checksum` | Release tarball, pinned map, `~/.local/share/nvim-dist/<v>` | templates `neovim` |
| `pyrefly`, `python_tools` (basedpyright), `ansible_tools` (ansible-lint) | tool version, `python_version` | `uv tool install`, `UV_PYTHON_DOWNLOADS=never` (Fedora 44's system 3.14), `SSL_CERT_FILE` set. python_tools removes the npm bundled with basedpyright | templates |
| `lazyvim` | `extras`, `python_lsp`, tree-sitter/stylua/shfmt versions and checksums | Config + `lazy-lock.json` from the templates repo at 15f68d3. Plugins restored to the lock; parsers built; CLIs from pinned releases | templates `lazyvim` |

## Upstream fixtures (upstream-1, system lane)

| Role | Inputs | Installs / verifies |
|---|---|---|
| `upstream_github_mcp` | `version`, `checksum`, `port`, `cert_src`, `key_src`, `read_only` | github-mcp-server in `http` mode on 127.0.0.1:8082 (a `DynamicUser` service) and stunnel TLS on `port`, its files under `/etc/stunnel` (SELinux `stunnel_etc_t`), started as root and dropping to `nobody`; verifies that a token-less request through TLS gets the server's own `Bearer` 401. Replaced `upstream_mcp_mock` |
| `upstream_ssh_target` | `user`, `ca_key` | An SCP account that trusts only the Vault SSH CA |

Ordering matters within a lane: `uv` comes before the `uv tool` roles, and `neovim` (plus
`lazyvim_system`) before `lazyvim`. In a dry run, a role whose prerequisite is not installed yet reports
"Would install …" instead of failing.

## Source
- `ansible/roles/guest/`. The source commits are trusted-devcontainer-features `944b438` and
  trusted-devcontainer-templates `15f68d3`, recorded in each role's `meta/main.yml`.
