"""The lab's SSH key pairs and host configs (lab_ssh): see the Lab SSH Identities concept."""

import os

import lab
import pytest
from lab import BOOTSTRAP

L = lab.lab()
FIX = f"run {BOOTSTRAP} host TAGS=ssh"
ROLES = lab.role_params("bootstrap-host.yml", "lab_ssh")["lab_ssh_roles"]
VM_PROXY = L.vm_scripts / "vm-proxy.sh"


@pytest.mark.parametrize("role", ROLES)
def test_private_key_is_private(host, role):
    key = host.file(str(L.ssh_key(role)))
    assert key.is_file, f"{L.ssh_key(role)} is missing: {FIX}"
    assert key.mode == 0o600, f"{L.ssh_key(role)} is mode {key.mode:o}, not 600: chmod 600 it"
    assert key.uid == os.getuid(), f"{L.ssh_key(role)} is not owned by you"


@pytest.mark.parametrize("role", ROLES)
def test_public_key_matches_private_key(host, role):
    pub_path = L.ssh_key(role).with_name(L.ssh_key(role).name + ".pub")
    assert pub_path.is_file(), f"{pub_path} is missing (Terraform reads it): {FIX}"
    pub = pub_path.read_text().split()
    assert pub[0] == "ssh-ed25519", f"{pub_path} is a {pub[0]} key, not ed25519"
    derived = host.check_output("ssh-keygen -y -f %s", str(L.ssh_key(role))).split()
    assert derived[:2] == pub[:2], f"{pub_path} is not the public half of {L.ssh_key(role)}"


def resolve(host, role: str, alias: str) -> dict[str, list[str]]:
    """`ssh -G` evaluates the generated config exactly as a connection would."""
    config = L.ssh_config(role)
    assert config.is_file(), f"{config} is missing: {FIX}"
    out = host.check_output("ssh -G -F %s %s", str(config), alias)
    resolved: dict[str, list[str]] = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        resolved.setdefault(key, []).append(value)
    return resolved


@pytest.mark.parametrize("role", ROLES)
def test_host_config_resolves(host, role):
    config = L.ssh_config(role)
    resolved = resolve(host, role, L.ssh_alias(role))
    assert resolved.get("user") == [role], f"{config}: User is {resolved.get('user')}, expected {role}"
    assert resolved.get("identityfile") == [str(L.ssh_key(role))], (
        f"{config}: IdentityFile is {resolved.get('identityfile')}, expected {L.ssh_key(role)}"
    )
    assert resolved.get("identitiesonly") == ["yes"], f"{config}: IdentitiesOnly is not yes"
    proxy = " ".join(resolved.get("proxycommand", []))
    assert str(VM_PROXY) in proxy and L.sandbox_vm in proxy, (
        f"{config}: ProxyCommand '{proxy}' does not run {VM_PROXY} defaulting to {L.sandbox_vm}: {FIX}"
    )


@pytest.mark.parametrize(
    ("role", "vm", "forwards"),
    [("dev", None, True), ("dev", "sandbox", True), ("dev", "other-vm", False), ("admin", None, False)],
    ids=["dev", "dev.sandbox-vm", "dev.other-vm", "admin"],
)
def test_only_the_dev_sandbox_session_forwards_the_sandbox_agent(host, role, vm, forwards):
    """The dedicated sandbox agent reaches the sandbox VM's dev session, and nothing else."""
    if role not in ROLES:
        pytest.skip(f"lab_ssh_roles has no {role}")
    alias = L.ssh_alias(role, L.sandbox_vm if vm == "sandbox" else vm)
    resolved = resolve(host, role, alias)
    assert resolved.get("forwardagent") == (["yes"] if forwards else ["no"]), (
        f"{alias}: ForwardAgent is {resolved.get('forwardagent')}, expected {'yes' if forwards else 'no'}: {FIX}"
    )
    if forwards:
        assert resolved.get("identityagent") == [str(L.sandbox_agent_sock)], (
            f"{alias}: IdentityAgent is {resolved.get('identityagent')}, expected the sandbox agent "
            f"{L.sandbox_agent_sock}, never your own: {FIX}"
        )


def test_vm_proxy_is_executable():
    assert os.access(VM_PROXY, os.X_OK), f"{VM_PROXY} is not executable; every lab ssh connection runs it"
