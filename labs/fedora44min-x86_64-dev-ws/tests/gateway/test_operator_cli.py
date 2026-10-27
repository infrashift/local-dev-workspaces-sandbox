"""The operator's command lines work from their places (concepts/Operator Interfaces).

The allow-list CLI (scripts/gateway/egress-allowlist.sh), and the vault and
consul CLIs through OPERATOR_DIR/env.sh: on the unix sockets, with the
operator tokens, and no `vault login` that could leave another token in a file.

Read-only: `list` and lookups only. Adding and removing an entry is exercised
end to end, through a sandbox guest, by tests/guest/sandbox.
"""

import json
import re

import gateway_lab as gw
import lab
from lab import GATEWAY

L = lab.lab()
SCRIPT = L.project_root / "scripts" / "gateway" / "egress-allowlist.sh"


def test_list_shows_the_whole_allow_list():
    out = lab.run([str(SCRIPT), str(L.operator_dir), "list"])
    assert out.returncode == 0, f"{SCRIPT} list failed: {out.stderr.strip()}: run {GATEWAY} allowlist"
    # The count goes to stderr, so stdout stays one entry per line.
    count = re.search(r"^(\d+) entries$", out.stderr + out.stdout, re.MULTILINE)
    assert count, f"{SCRIPT} list printed no entry count: {out.stdout[:200]}"
    keys = gw.kv_keys()
    assert int(count.group(1)) == len(keys), (
        f"{SCRIPT} list reports {count.group(1)} entries, Consul holds {len(keys)} under {gw.KV_PREFIX}/"
    )


def cli(command: str):
    """Run a command in a shell that sourced the operator's CLI environment."""
    env_sh = L.operator_dir / "env.sh"
    assert env_sh.is_file(), f"{env_sh} is missing: run {GATEWAY} gateway"
    return lab.run(["bash", "-c", f'. "{env_sh}" && {command}'])


def test_vault_cli_uses_the_socket_and_the_operator_token():
    out = cli("vault token lookup -format=json")
    assert out.returncode == 0, f"vault token lookup through env.sh failed: {out.stderr.strip()}"
    policies = json.loads(out.stdout)["data"]["policies"]
    operator_policy = gw.role_vars("vault_gateway")["vault_gateway_operator_policy"]
    assert operator_policy in policies, f"the vault CLI carries {policies}, not the operator token: run {GATEWAY} gateway"


def test_vault_login_cannot_store_a_token():
    out = cli('printf probe | "$(dirname "$VAULT_CONFIG_PATH")/bin/vault-token-helper" store')
    assert out.returncode != 0, "the vault token helper stored a token: `vault login` would replace the operator token"


def test_consul_cli_uses_the_socket_and_the_operator_token():
    out = cli(f"consul kv get -keys -separator= {gw.KV_PREFIX}/")
    assert out.returncode == 0, f"consul kv get through env.sh failed: {out.stderr.strip()}"
    keys = [line for line in out.stdout.splitlines() if line.strip()]
    assert len(keys) == len(gw.kv_keys()), f"the consul CLI lists {len(keys)} keys, Consul holds {len(gw.kv_keys())}"
