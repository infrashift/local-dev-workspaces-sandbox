"""The gateway's real credentials: encrypted in the host inventory, then loaded into Vault as configured.

inventory-host/host_vars/localhost/vars.yml (committed) maps each secret name
to the ansible-vault variable that holds it; vault.yml beside it (gitignored,
0600) holds each one encrypted with the lab's .ansible_vault_key. The gateway
playbook writes one Vault record per surrogate in vars/gateway.yml, bound to
its hosts and repository, and the same binding without the secret in the
record's metadata. The operator token reads only that metadata -- never a real
credential -- so these tests check the binding and a fingerprint of the value.
"""

import base64
import hashlib
import re
import subprocess

import gateway_lab as gw
import lab
import pytest
import yaml
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} secrets"
KV = gw.role_vars("vault_gateway")["vault_gateway_kv_mount"]
SURROGATES = gw.GATEWAY_VARS["surrogates"]
REPOS = gw.GATEWAY_VARS["github_repos"]
SECRETS = yaml.safe_load(L.credentials_vars.read_text())["gateway_secrets"]
VARIABLES = {name: re.fullmatch(r"\{\{\s*(\w+)\s*\}\}", ref).group(1) for name, ref in SECRETS.items()}


def record_id(credential: str) -> str:
    """The id vault_gateway and Envoy's Lua filter derive: base64url of the credential, unpadded."""
    return base64.urlsafe_b64encode(credential.encode()).decode().rstrip("=")


def vault_blocks() -> dict[str, str]:
    """Top-level variable -> its value's text, as vault.yml holds it."""
    assert L.credentials_vault.exists(), f"no {L.credentials_vault}: {FIX}"
    text = L.credentials_vault.read_text()
    return {m.group(1): m.group(2) for m in re.finditer(r"(?m)^(\w+):(.*\n(?:[ \t]+.*\n?)*)", text)}


def test_every_surrogate_names_a_secret():
    missing = {s["secret"] for s in SURROGATES.values()} - set(SECRETS)
    assert not missing, f"surrogates name secrets that {L.credentials_vars} lacks: {sorted(missing)}"


@pytest.mark.parametrize("key", sorted(REPOS))
def test_repository_has_its_pat_and_three_surrogates(key):
    assert key in SECRETS, f"{REPOS[key]['repo']} has no PAT in {L.credentials_vars} gateway_secrets"
    bound = [s for s in SURROGATES.values() if s.get("repo") == REPOS[key]["repo"]]
    assert sorted(s["use"] for s in bound) == ["api", "git", "mcp"], (
        f"{REPOS[key]['repo']} needs one git, one api and one mcp surrogate in vars/gateway.yml"
    )
    assert {s["secret"] for s in bound} == {key}, f"{REPOS[key]['repo']}'s surrogates must use secret {key}"


def test_vault_file_is_private_and_gitignored():
    st = L.credentials_vault.stat()
    assert oct(st.st_mode & 0o777) == "0o600", f"{L.credentials_vault} is {oct(st.st_mode & 0o777)}, not 0600"
    ignored = lab.run(["git", "-C", str(L.project_root), "check-ignore", "-q", str(L.credentials_vault)])
    assert ignored.returncode == 0, f"{L.credentials_vault} is not gitignored: it must never be committed"


@pytest.mark.parametrize("name", sorted(SECRETS))
def test_secret_is_encrypted_in_the_vault_file(name):
    block = vault_blocks().get(VARIABLES[name])
    assert block is not None, f"{L.credentials_vault} has no {VARIABLES[name]} ({name}): {FIX} NAME={name}"
    assert re.match(r"\s*!vault \|\s*\n\s+\$ANSIBLE_VAULT;", block), (
        f"{VARIABLES[name]} in {L.credentials_vault} is not ansible-vault encrypted: {FIX} NAME={name}"
    )
    payload = "\n".join(line.strip() for line in block.splitlines()[1:]) + "\n"
    decrypted = subprocess.run(
        [str(L.venv / "bin" / "ansible-vault"), "decrypt", "--vault-password-file", str(L.vault_key), "--output", "-"],
        input=payload, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
    )
    assert decrypted.returncode == 0, f"{VARIABLES[name]} does not decrypt with {L.vault_key}: {FIX} NAME={name}"


def test_vault_file_holds_nothing_in_plaintext():
    plain = [var for var, block in vault_blocks().items() if not re.match(r"\s*!vault \|", block)]
    assert not plain, f"{L.credentials_vault} holds unencrypted variables {plain}: {FIX}"


def surrogate_valued(surrogate: dict) -> str:
    """The header value a record would hold if it carried the surrogate itself instead of a real credential."""
    credential = surrogate["credential"]
    if surrogate["scheme"] == "basic":
        return "Basic " + base64.b64encode(credential.encode()).decode()
    return ("Bearer " + credential) if surrogate["scheme"] == "bearer" else credential


@pytest.mark.parametrize("name", sorted(SURROGATES))
def test_surrogate_record_is_bound_as_configured(name):
    """Read from the record's metadata: the operator token cannot read the record itself."""
    surrogate = SURROGATES[name]
    resp = gw.vault().get(f"/v1/{KV}/metadata/surrogates/{record_id(surrogate['credential'])}")
    assert resp.status == 200, f"no Vault record for the {name} surrogate ({resp.status}): {FIX}"
    meta = resp.json()["data"]["custom_metadata"] or {}
    assert meta.get("target_hosts") == ",".join(surrogate["target_hosts"]), f"{name} is bound to {meta.get('target_hosts')}"
    assert meta.get("repo", "") == surrogate.get("repo", ""), f"{name} is bound to repository {meta.get('repo')!r}"
    header = "x-api-key" if surrogate["scheme"] == "x-api-key" else "authorization"
    assert (meta.get("header"), meta.get("scheme")) == (header, surrogate["scheme"]), (
        f"{name}'s record is {meta.get('scheme')} in {meta.get('header')}, expected {surrogate['scheme']} in {header}"
    )
    fingerprint = meta.get("value_fingerprint", "")
    assert re.fullmatch(r"[0-9a-f]{16}", fingerprint), f"{name}'s record has no value fingerprint: run {GATEWAY} TAGS=vault"
    assert fingerprint != hashlib.sha256(surrogate_valued(surrogate).encode()).hexdigest()[:16], (
        f"{name}'s record holds the surrogate, not a secret"
    )


def test_operator_token_cannot_read_a_real_credential():
    """Only a break-glass token reads a record (make -f lab-gateway.mk break-glass)."""
    surrogate = next(iter(SURROGATES.values()))
    resp = gw.vault().get(f"/v1/{KV}/data/surrogates/{record_id(surrogate['credential'])}")
    assert resp.status == 403, f"the operator token read a surrogate record ({resp.status}): run {GATEWAY} TAGS=vault"


def test_no_record_outlives_its_surrogate():
    resp = gw.vault().request("LIST", f"/v1/{KV}/metadata/surrogates")
    keys = resp.json()["data"]["keys"] if resp.status == 200 else []
    stale = sorted(set(keys) - {record_id(s["credential"]) for s in SURROGATES.values()})
    assert not stale, f"Vault still honours {len(stale)} record(s) no surrogate names: run {GATEWAY} gateway TAGS=vault"
