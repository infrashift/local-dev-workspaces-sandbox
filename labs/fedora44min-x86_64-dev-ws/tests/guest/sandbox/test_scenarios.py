"""The gateway's scenarios, end to end from the sandbox: each with the surrogate the guest holds.

1. pip through the CONNECT tunnel (no credential, no TLS termination).
2. GitHub, per repository in github_repos: it refuses an anonymous clone and
   clones with its git surrogate; the API reads it with its git and api
   surrogates, through the repository's own fine-grained PAT.
3. The GitHub MCP servers, per repository (concepts/GitHub MCP Servers Behind
   the Gateway): local (stdio, on this guest), self-hosted remote (upstream-1)
   and GitHub's hosted one each act as the PAT's login and read the
   repository; Claude Code registers all of them.
4. SCP to the target through the tunnel, signed by the forwarded sandbox agent.
5. Anthropic: the API accepts the surrogate key; without one the gateway
   answers itself.
A 401 from GitHub or Anthropic means the real credential is wrong or missing:
make -f lab-gateway.mk secrets.
"""

import json

import lab
import pytest
import sandbox_lab as sb
from lab import GATEWAY, PROVISION

L = lab.lab()
STACK = f"run {PROVISION} play PLAYBOOK=python-stack"
HOME = f"/home/{lab.group_vars()['guest_user']}"
MCP_BIN = f"{HOME}/.local/bin/github-mcp-server"
MCP_ARGS = ["stdio", *(["--read-only"] if sb.GITHUB_MCP["github_mcp_read_only"] else [])]
REMOTE_MCP = {
    "upstream": f"https://{sb.UPSTREAM_ROUTE['host']}/",
    "hosted": sb.GITHUB_MCP["github_mcp_hosted_url"],
}


def owner_repo(repo_key: str) -> dict[str, str]:
    owner, repo = sb.REPOS[repo_key]["repo"].split("/", 1)
    return {"owner": owner, "repo": repo}


def test_pip_installs_through_the_tunnel(dev):
    result = sb.login(dev, "python3 -m pip install --dry-run --no-deps --ignore-installed --quiet six")
    assert result.rc == 0, f"pip through the CONNECT tunnel: {result.stderr.strip()[-300:]}"


# ---------------------------------------------------------------------------
# GitHub, per repository
# ---------------------------------------------------------------------------
def test_repository_refuses_an_anonymous_clone(dev, repo_key):
    """Each repository must be private: otherwise a clone proves nothing about injection."""
    repo = sb.REPOS[repo_key]["repo"]
    result = sb.login(dev, f"GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/{repo}")
    assert result.rc != 0, f"{repo} answers anonymously: it must be a PRIVATE repository"


def test_repository_clones_with_its_surrogate(dev, repo_key):
    repo = sb.REPOS[repo_key]["repo"]
    for url in (f"https://github.com/{repo}", f"https://github.com/{repo}.git"):
        result = sb.login(dev, f"GIT_TERMINAL_PROMPT=0 git ls-remote {url} HEAD")
        assert result.rc == 0 and "HEAD" in result.stdout, (
            f"git with {repo}'s surrogate (~/.git-credentials, by path) could not read {url}: "
            f"{result.stderr.strip()[-300:]}: {sb.SECRETS} NAME={repo_key}, or {STACK}"
        )


def test_git_cannot_erase_the_surrogate(dev, repo_key):
    """A 401 makes git `reject` the credential; the get-only helper must keep the surrogate anyway."""
    surrogate = sb.SURROGATES[sb.surrogate(repo_key, "git")]
    user, password = surrogate["credential"].split(":", 1)
    query = f"protocol=https\\nhost=github.com\\npath={surrogate['repo']}\\n"
    sb.login(dev, f"printf '{query}username={user}\\npassword={password}\\n\\n' | git credential reject")
    filled = sb.login(dev, f"printf '{query}\\n' | GIT_TERMINAL_PROMPT=0 git credential fill")
    assert f"password={password}" in filled.stdout, f"git reject erased {surrogate['repo']}'s surrogate: {STACK}"


@pytest.mark.parametrize("use", ["git", "api"])
def test_github_api_reads_the_repository(dev, repo_key, use):
    name = sb.surrogate(repo_key, use)
    surrogate = sb.SURROGATES[name]
    auth = ["--user", surrogate["credential"]] if surrogate["scheme"] == "basic" else ["--header", sb.bearer(name)]
    status, body = sb.curl(dev, f"https://api.github.com/repos/{surrogate['repo']}", *auth)
    assert status == 200, f"api.github.com/repos/{surrogate['repo']} with {name}: {status} {body[:300]}: {sb.SECRETS}"
    assert json.loads(body)["private"], f"{surrogate['repo']} is not private"


# ---------------------------------------------------------------------------
# The GitHub MCP servers, per repository
# ---------------------------------------------------------------------------
def local_mcp(dev, repo_key, tool, arguments):
    token = sb.SURROGATES[sb.surrogate(repo_key, "api")]["credential"]
    return sb.mcp(dev, "stdio", tool, arguments, "env", f"GITHUB_PERSONAL_ACCESS_TOKEN={token}", MCP_BIN, *MCP_ARGS)


def remote_mcp(dev, repo_key, which, tool, arguments):
    token = sb.SURROGATES[sb.surrogate(repo_key, "mcp")]["credential"]
    return sb.mcp(dev, "http", tool, arguments, REMOTE_MCP[which], f"Authorization=Bearer {token}")


def test_claude_code_registers_the_github_mcp_servers(dev):
    servers = json.loads(dev.file(f"{HOME}/.claude.json").content_string)["mcpServers"]
    expected = {f"github-{kind}-{key}" for key in sb.REPOS for kind in ("local", "upstream", "hosted")}
    missing = expected - set(servers)
    assert not missing, f"~/.claude.json lacks the MCP servers {sorted(missing)}: {STACK}"


def test_claude_code_connects_to_the_upstream_mcp_servers(dev):
    """Claude Code's own TLS stack (Bun) accepts the gateway's certificate chain.

    The probes here are Python and curl, which accepted a chain that Bun refused
    (UNSUPPORTED_CONSTRAINT_TYPE): issues/Claude Code refuses the gateway CA's name
    constraints. The self-hosted servers are the lab's own, so their health check
    depends on nothing outside it.
    """
    out = sb.login(dev, "cd /tmp && claude mcp list").stdout
    lines = {line.split(":", 1)[0]: line for line in out.splitlines() if line.startswith("github-upstream-")}
    expected = {f"github-upstream-{key}" for key in sb.REPOS}
    assert set(lines) == expected, f"claude mcp list shows {sorted(lines)}, expected {sorted(expected)}: {STACK}"
    failed = {name: line.rsplit(" - ", 1)[-1] for name, line in lines.items() if "Connected" not in line}
    assert not failed, f"Claude Code could not connect through the gateway: {failed}"


def test_local_mcp_server_is_the_pinned_build(dev):
    out = dev.check_output(f"{MCP_BIN} --version")
    assert f"Version: {sb.GITHUB_MCP['github_mcp_version']}" in out, f"github-mcp-server reports {out!r}: {STACK}"


def test_local_mcp_server_acts_as_the_pat_login(dev, repo_key, pat_login):
    text = sb.tool_text(local_mcp(dev, repo_key, "get_me", {}))
    assert f'"{pat_login}"' in text, f"get_me through the gateway is not {pat_login}: {text[:300]}"


def test_local_mcp_server_reads_the_repository(dev, repo_key):
    sb.tool_text(local_mcp(dev, repo_key, "list_commits", {**owner_repo(repo_key), "perPage": 1}))


def test_local_mcp_server_reads_a_file(dev, repo_key):
    """A file's contents come from raw.githubusercontent.com: the gateway injects there too."""
    outcome = local_mcp(dev, repo_key, "get_file_contents", {**owner_repo(repo_key), "path": "/"})
    sb.tool_text(outcome)
    entries = json.loads(outcome["result"]["content"][0]["text"])
    files = [entry["path"] for entry in entries if entry.get("type") == "file"]
    assert files, f"{sb.REPOS[repo_key]['repo']} has no file at its root to read: add one (a README.md)"
    sb.tool_text(local_mcp(dev, repo_key, "get_file_contents", {**owner_repo(repo_key), "path": files[0]}))


@pytest.mark.parametrize("which", sorted(REMOTE_MCP))
def test_remote_mcp_server_acts_as_the_pat_login(dev, repo_key, pat_login, which):
    outcome = remote_mcp(dev, repo_key, which, "get_me", {})
    if which == "hosted" and outcome.get("status") in (401, 403) and sb.GATEWAY_SAYS not in outcome.get("body", ""):
        pytest.fail(
            f"api.githubcopilot.com refused {repo_key}'s injected PAT ({outcome['status']}): the account or its "
            "organisation may not allow the hosted MCP server, or the PAT type: see the GitHub MCP concept"
        )
    text = sb.tool_text(outcome)
    assert f'"{pat_login}"' in text, f"the {which} MCP server is not acting as {pat_login}: {text[:300]}"


@pytest.mark.parametrize("which", sorted(REMOTE_MCP))
def test_remote_mcp_server_reads_the_repository(dev, repo_key, which):
    sb.tool_text(remote_mcp(dev, repo_key, which, "list_commits", {**owner_repo(repo_key), "perPage": 1}))


def test_upstream_route_is_upstream_1(dev):
    """vars/gateway.yml's MCP upstream address is the upstream VM's reservation in terraform.tfvars."""
    addresses = {spec["ip"] for spec in lab.upstream_vms().values()}
    assert sb.UPSTREAM_ROUTE["upstream"]["address"] in addresses, (
        f"the MCP route goes to {sb.UPSTREAM_ROUTE['upstream']['address']}, the upstream VMs are {sorted(addresses)}"
    )


# ---------------------------------------------------------------------------
# SCP and Anthropic
# ---------------------------------------------------------------------------
def test_scp_reaches_the_target_with_the_forwarded_agent(dev):
    target = sb.UPSTREAM_ROUTE["upstream"]["address"]
    user = sb.GATEWAY_VARS["scp_target_user"]
    result = sb.login(
        dev,
        f"scp -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"{user}@{target}:/etc/hostname /dev/null",
    )
    assert result.rc == 0, (
        f"scp from {user}@{target}: {result.stderr.strip()[-300:]}. The tunnel needs an allow-list entry "
        f'({GATEWAY} allow HOST={target}:22 REASON="scenario 4") and a fresh agent certificate ({GATEWAY} agent-cert)'
    )


def test_anthropic_api_accepts_the_surrogate_key(dev):
    status, body = sb.curl(
        dev, "https://api.anthropic.com/v1/models", "--header", f"x-api-key: {sb.SURROGATES['anthropic']['credential']}",
        "--header", "anthropic-version: 2023-06-01",
    )
    assert status == 200, f"api.anthropic.com/v1/models with the surrogate: {status} {body[:300]}: {sb.SECRETS}"


def test_anthropic_without_a_key_is_refused_by_the_gateway(dev):
    status, body = sb.curl(dev, "https://api.anthropic.com/v1/models")
    assert status == 401 and sb.GATEWAY_SAYS in body, f"no-credential request: {status} {body[:200]}"

