"""Vault on the host: running, unsealed, on its unix socket only, and the operator token's reach.

The real credentials live here and nowhere else (concepts/Surrogate Credential
Model). The guest never reaches Vault; Envoy reads it through Vault Proxy, and
the operator writes it with a token limited to the surrogates, the lab's
fixtures and SSH signing.
"""

import json
import pwd
import stat
from pathlib import Path

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

FIX = f"run {GATEWAY} gateway TAGS=vault"
KV = gw.role_vars("vault_gateway")["vault_gateway_kv_mount"]
SSH = gw.role_vars("vault_gateway")["vault_gateway_ssh_mount"]
APPROLE = gw.role_vars("vault_gateway")["vault_gateway_approle"]
OPERATOR_POLICY = gw.role_vars("vault_gateway")["vault_gateway_operator_policy"]
SCP_USER = gw.GATEWAY_VARS["scp_target_user"]
SOCKET = gw.PINS["vault_socket"]
SOCKET_GROUP = gw.PINS["vault_socket_group"]
# Where Vault listened before the unix-socket change: its API and cluster ports.
FORMER_PORTS = [8200, 8201]


@pytest.mark.parametrize("unit", ["vault", "ai-sandbox-vault-unseal"])
def test_unit_is_active_and_enabled(unit):
    assert gw.systemctl("is-active", unit) == "active", f"{unit}.service is not active: {FIX}"
    assert gw.systemctl("is-enabled", unit) == "enabled", f"{unit}.service is not enabled at boot: {FIX}"


def test_vault_is_initialised_and_unsealed():
    status = gw.vault().anonymous().get("/v1/sys/seal-status").json()
    assert status["initialized"], f"Vault is not initialised: {FIX}"
    assert not status["sealed"], "Vault is sealed: sudo systemctl restart ai-sandbox-vault-unseal"
    assert status["version"] == gw.PINS["vault_version"], (
        f"Vault {status['version']} is running, the pin is {gw.PINS['vault_version']}: {FIX}"
    )


@pytest.mark.parametrize("port", FORMER_PORTS)
def test_vault_has_no_tcp_listener(port):
    """Nothing reaches Vault over TCP -- no process or container on the host either (concepts/Vault and Consul Host Trust)."""
    addresses = gw.listeners(port)
    assert not addresses, f"something listens on Vault's former port :{port} ({sorted(addresses)}): {FIX}"


def test_socket_opens_for_its_group_and_the_operator():
    problems = gw.socket_problems(SOCKET, SOCKET_GROUP)
    assert not problems, f"Vault's socket: {'; '.join(problems)}: {FIX}"


def test_anonymous_requests_read_nothing():
    resp = gw.vault().anonymous().get(f"/v1/{KV}/data/surrogates/probe")
    assert resp.status == 403, f"an anonymous surrogate read returned {resp.status}, expected 403"


def test_operator_token_has_only_the_operator_policy():
    resp = gw.vault().get("/v1/auth/token/lookup-self")
    assert resp.status == 200, f"the operator token is not valid ({resp.status}): {FIX}"
    data = resp.json()["data"]
    assert sorted(data["policies"]) == sorted([OPERATOR_POLICY, "default"]), (
        f"the operator token carries {data['policies']}, expected {OPERATOR_POLICY} and default"
    )
    assert data["period"], f"the operator token is not periodic (it would expire for good): {FIX}"


# What the operator policy grants, path by path; anything else is denied.
CAPABILITIES = {
    # Metadata only: a real credential takes a break-glass token.
    f"{KV}/data/surrogates/probe": ["deny"],
    f"{KV}/metadata/surrogates/probe": ["read"],
    f"{KV}/metadata/surrogates": ["list"],
    f"{KV}/data/fixtures/probe": ["deny"],
    f"{SSH}/sign/{SCP_USER}": ["update"],
    f"{SSH}/sign/root": ["deny"],
    f"{KV}/data/other": ["deny"],
    "sys/policy/probe": ["deny"],
    "sys/mounts/probe": ["deny"],
    f"auth/approle/role/{APPROLE}/secret-id": ["deny"],
}


def test_operator_token_reaches_only_what_its_policy_grants():
    resp = gw.vault().request("POST", "/v1/sys/capabilities-self", json.dumps({"paths": list(CAPABILITIES)}).encode())
    assert resp.status == 200, f"sys/capabilities-self returned {resp.status}"
    granted = resp.json()
    wrong = {path: granted.get(path) for path, caps in CAPABILITIES.items() if sorted(granted.get(path, [])) != caps}
    assert not wrong, f"the operator token's capabilities differ from {OPERATOR_POLICY}: {wrong}: {FIX}"


def test_upstream_playbook_reads_the_same_socket():
    """upstream.yml reads the SSH CA's public key from Vault; it must name gateway-host.yml's socket."""
    upstream = lab.play_vars("upstream.yml")["vault_socket"]
    assert upstream == SOCKET, f"upstream.yml reads Vault at {upstream}, gateway-host.yml serves it at {SOCKET}"


def test_break_glass_playbook_matches_the_gateway():
    """break-glass.yml mints its token on gateway-host.yml's socket, with vault_gateway's break-glass policy."""
    play = lab.play_vars("break-glass.yml")
    policy = gw.role_vars("vault_gateway")["vault_gateway_break_glass_policy"]
    assert (play["vault_socket"], play["break_glass_policy"]) == (SOCKET, policy), (
        f"break-glass.yml uses {play['vault_socket']} and {play['break_glass_policy']}, "
        f"the gateway serves {SOCKET} and defines {policy}"
    )


def test_audit_log_directory_is_vaults_alone():
    """vault_gateway's file audit device writes here; the role checks the device itself (sys/audit needs root)."""
    audit_dir = Path(gw.PINS["vault_audit_dir"])
    assert audit_dir.is_dir(), f"{audit_dir} is missing: {FIX}"
    info = audit_dir.stat()
    assert (pwd.getpwuid(info.st_uid).pw_name, stat.S_IMODE(info.st_mode)) == ("vault", 0o700), (
        f"{audit_dir} is {pwd.getpwuid(info.st_uid).pw_name} {stat.S_IMODE(info.st_mode):o}, expected vault 700: {FIX}"
    )
    rotate = Path("/etc/logrotate.d/vault-audit")
    assert rotate.is_file() and str(audit_dir) in rotate.read_text(), f"{rotate} does not rotate {audit_dir}: {FIX}"
