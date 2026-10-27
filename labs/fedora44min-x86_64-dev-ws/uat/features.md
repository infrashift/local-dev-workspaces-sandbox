# Features

The features that the UAT tests accept. A test names each feature that it accepts in its
`features` key. The last column names the roles, files or wiki pages that make the feature.

| Feature | Behavior | Made by |
|---|---|---|
| SBX-LIFE-01 | The operator shows, starts, stops and connects to the lab VMs with make targets. | `lab-provision.mk` (`status`, `start`, `stop`, `ssh`, `console`), `lab_ssh` |
| SBX-LIFE-02 | After the host restarts, the gateway comes back without the operator: Vault unseals itself, and Consul, Envoy and the firewall start. | `vault_server` (`ai-sandbox-vault-unseal`), `consul_server`, `envoy_gateway`, `sandbox_firewall` |
| SBX-LIFE-03 | A playbook shows its changes before it applies them, and a second run finds nothing to change. | `scripts/ansible-confirm.sh`, [Role Contract](../../../.okfw/concepts/role-contract--01a166e751ce.md) |
| SBX-LIFE-04 | The lab can be deleted and made again from the code. | `terraform/`, `site.yml`, `python-stack.yml` |
| SBX-SESS-01 | An ssh login starts the tmux session `dev`: the editor on the left, a shell on the right. | `tmux` (`dev-session`) |
| SBX-SESS-02 | The developer can turn off the tmux start for one login or for all logins. | `tmux` (`/etc/profile.d/dev-session.sh`) |
| SBX-EDIT-01 | The editor gives Python diagnostics, definitions and hover from pyrefly. | `lazyvim` (`lang.python`), `pyrefly` |
| SBX-EDIT-02 | The editor lints and formats Python with ruff. | `lazyvim` (`lang.python`), `ruff` |
| SBX-EDIT-03 | The editor plugins are at their locked commits, and the editor installs nothing at run time. | `lazyvim` (`lazy-lock.json`, `plugins/offline.lua`) |
| SBX-EDIT-04 | The editor shows ansible-lint findings in playbooks and role task files. | `lazyvim` (`infrashift.ansible_lint`), `ansible_tools` |
| SBX-PY-01 | Python packages install from PyPI through the CONNECT tunnel. | `sandbox_egress`, the `python` category of `ansible/vars/egress-baseline.yml` |
| SBX-PY-02 | uv, ruff, pyrefly, basedpyright and jq are on dev's PATH at their pinned versions. | `uv`, `ruff`, `pyrefly`, `python_tools`, `jq` |
| SBX-CTR-01 | dev runs rootless containers and pulls images from the allowed registries. | `podman`, the `oci-registries` category |
| SBX-CTR-02 | A container build downloads packages through the CONNECT tunnel. | `podman`, `sandbox_egress` |
| SBX-SCAN-01 | syft makes an SBOM of a project or an image. | `syft` |
| SBX-SCAN-02 | grype scans an SBOM for known vulnerabilities. | `grype` |
| SBX-GIT-01 | git reads each private repository with that repository's surrogate. git cannot erase the surrogate. | `sandbox_surrogates`, [Surrogate Credential Model](../../../.okfw/concepts/surrogate-credential-model--01a17ecc92e2.md) |
| SBX-GIT-02 | git reads public GitHub repositories without a credential. | `gateway_routes` (`anonymous: true`) in `ansible/vars/gateway.yml` |
| SBX-GIT-03 | A surrogate works only for its own repository and its own hosts. | `envoy_gateway` (`surrogate.lua`), [Zero-Trust Surrogate Gateway](../../../.okfw/concepts/zero-trust-surrogate-gateway--01a17f01fd4c.md) |
| SBX-GHAPI-01 | The GitHub REST API reads a private repository with the api surrogate. | `sandbox_surrogates`, `envoy_gateway` |
| SBX-MCP-01 | Claude Code has three GitHub MCP servers for each repository: local, self-hosted and hosted. | `claude_code`, `github_mcp_server`, `upstream_github_mcp`, [GitHub MCP Servers Behind the Gateway](../../../.okfw/concepts/github-mcp-servers-behind-the-gateway--01a17de05379.md) |
| SBX-MCP-02 | The GitHub MCP servers give read tools only. | `ansible/vars/github-mcp.yml` (`github_mcp_read_only`, `/readonly`) |
| SBX-AI-01 | Claude Code works with the surrogate Anthropic key. The gateway injects the real key. | `claude_code`, the `anthropic` surrogate |
| SBX-AI-02 | Claude Code is the pinned version and does not update itself. | `claude_code` (`DISABLE_AUTOUPDATER`) |
| SBX-EGR-01 | The sandbox reaches only the sites on the allow list. | `consul_egress`, `envoy_gateway`, [Egress Allow List in Consul KV](../../../.okfw/concepts/egress-allow-list-in-consul-kv--01a17f01fd5d.md) |
| SBX-EGR-02 | The operator lists, allows and removes sites, with a reason. The change takes effect in seconds. | `scripts/gateway/egress-allowlist.sh`, `lab-gateway.mk` (`allowlist`, `allow`, `deny`) |
| SBX-ISO-01 | The sandbox has no route and no DNS to the internet. Its only way out is the gateway. | `libvirt-network`, `sandbox_firewall`, [Isolated Sandbox Network](../../../.okfw/concepts/isolated-sandbox-network--01a17e9c824e.md) |
| SBX-ISO-02 | The guest holds the surrogate credentials only, never a real one. | `sandbox_surrogates`, `claude_code` |
| SBX-SSH-01 | scp from the sandbox signs in with the forwarded sandbox agent and its Vault-signed certificate. | `sandbox_ssh_agent`, `lab_ssh`, [SSH Agent Forwarding](../../../.okfw/concepts/ssh-agent-forwarding--01a17f01fd23.md) |
| SBX-CRED-01 | The operator loads and rotates a real credential without a change on the guest. | `lab-gateway.mk secrets`, `vault_gateway`, [Gateway Credentials in the Host Inventory](../../../.okfw/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md) |
| SBX-CRED-02 | The operator's vault and consul command lines can look, but cannot read a real credential. | `vault_gateway`, `consul_egress`, [Operator Interfaces](../../../.okfw/concepts/operator-interfaces--01a17ebdba31.md) |
| SBX-CRED-03 | Break-glass gives a 15-minute token to read the real credentials, and the audit log records the reason and each read. | `break-glass.yml`, `scripts/gateway/break-glass.sh` |
