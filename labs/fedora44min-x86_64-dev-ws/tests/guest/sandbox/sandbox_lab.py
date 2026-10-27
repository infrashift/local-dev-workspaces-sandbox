"""The sandbox as its suite sees it: the gateway's routes and surrogates, and a dev login on the guest.

Every command runs in dev's LOGIN shell, so it gets what an agent there gets:
the proxy environment (sandbox_egress), the CA bundle variables (ca_trust) and
~/.bashrc.d (the surrogates, Claude Code's environment). Expectations come
from vars/gateway.yml and vars/github-mcp.yml; no test restates a host or a
surrogate.
"""

from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path
from typing import Any

import lab

L = lab.lab()
GATEWAY_VARS = lab.vars_file("gateway.yml")
ROUTES = GATEWAY_VARS["gateway_routes"]
GATEWAY_HOSTS = [route["host"] for route in ROUTES]
SURROGATES = GATEWAY_VARS["surrogates"]
REPOS = GATEWAY_VARS["github_repos"]
GITHUB_MCP = lab.vars_file("github-mcp.yml")
UPSTREAM_ROUTE = next(route for route in ROUTES if route["upstream"]["ca"] == "upstream")
# Envoy's Lua filter prefixes every answer it gives itself.
GATEWAY_SAYS = "ai-sandbox gateway: "
SECRETS = f"run {lab.GATEWAY} secrets"
# The probe travels as base64 on the command line: nothing is written to the guest.
PROBE = base64.b64encode((Path(__file__).parent / "mcp_probe.py").read_bytes()).decode()


def login(host, command: str):
    """Run a command in the account's login shell on the guest."""
    return host.run("bash -lc %s", command)


def curl(host, url: str, *options: str) -> tuple[int, str]:
    """(HTTP status, body) of a request from the guest; status 0 when curl itself failed."""
    argv = " ".join(shlex.quote(o) for o in options)
    result = login(host, f"curl --silent --show-error --max-time 60 --output - --write-out '\\n%{{http_code}}' {argv} "
                         f"{shlex.quote(url)}")
    body, _, status = result.stdout.rpartition("\n")
    return (int(status) if status.isdigit() else 0), body or result.stderr


def surrogate(repo_key: str, use: str) -> str:
    """The name of a repository's surrogate for one use (git, api, mcp)."""
    repo = REPOS[repo_key]["repo"]
    return next(name for name, s in SURROGATES.items() if s.get("repo") == repo and s["use"] == use)


def bearer(name: str) -> str:
    return f"Authorization: Bearer {SURROGATES[name]['credential']}"


def mcp(host, transport: str, tool: str, arguments: dict[str, Any], target: str, *rest: str) -> dict[str, Any]:
    """Call one tool on an MCP server from the guest (mcp_probe.py) and return its outcome."""
    argv = " ".join(shlex.quote(a) for a in [transport, tool, json.dumps(arguments), target, *rest])
    result = login(host, f'python3 -I -c "$(printf %s {PROBE} | base64 -d)" {argv}')
    assert result.rc == 0, f"mcp_probe.py {transport} {tool} {target}: {result.stderr.strip()[-500:]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def tool_text(outcome: dict[str, Any]) -> str:
    """The text a tools/call returned, after asserting it succeeded."""
    assert "result" in outcome, f"the MCP server refused the session or the call: {outcome}"
    text = " ".join(c.get("text", "") for c in outcome["result"].get("content", []))
    assert not outcome["result"].get("isError"), f"the tool failed: {text[:500]}"
    return text + json.dumps(outcome["result"].get("structuredContent", {}))
