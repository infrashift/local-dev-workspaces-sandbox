"""The guest suite: each lab VM that `make -f lab-provision.mk apply` built.

Every test that takes `vm` runs once per VM in the dev_ws group, as Terraform
evaluates var.vms; one that takes `lab_vm` runs once per lab VM, the upstream
fixtures included, and one that takes `upstream_vm` once per upstream fixture. The `admin` and `dev` fixtures connect through the ssh
configs lab_ssh wrote, exactly as `make -f lab-provision.mk ssh` does, so the
DHCP address is resolved by vm-proxy.sh and no IP is needed here.
"""

from typing import Any

import lab
import pytest
import testinfra

# Reuse one connection per user and VM: without it every command pays for a
# new handshake and a lease lookup. %C is a hash, so the path stays short
# (see the SSH ControlPath issue in the wiki); ~/.ssh is private. Passed as
# ssh_extra_args, which testinfra escapes: its controlpath option is
# %-formatted unescaped, and %C breaks it.
SSH_MULTIPLEX = "-o ControlMaster=auto -o ControlPersist=60s -o ControlPath=~/.ssh/ai-sandbox-verify-%C"


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "vm" in metafunc.fixturenames:
        metafunc.parametrize("vm", sorted(lab.dev_ws_vms()), scope="module")
    if "lab_vm" in metafunc.fixturenames:
        metafunc.parametrize("lab_vm", sorted(lab.tf_vms()), scope="module")
    if "upstream_vm" in metafunc.fixturenames:
        metafunc.parametrize("upstream_vm", sorted(lab.upstream_vms()), scope="module")


def guest(role: str, vm: str) -> testinfra.host.Host:
    L = lab.lab()
    return testinfra.get_host(
        f"ssh://{L.ssh_alias(role, vm)}", ssh_config=str(L.ssh_config(role)), ssh_extra_args=SSH_MULTIPLEX
    )


@pytest.fixture(scope="module")
def spec(vm: str) -> dict[str, Any]:
    """The VM's entry in var.vms: vcpu, memory_mib, disk_gib, base_image, roles."""
    return lab.dev_ws_vms()[vm]


@pytest.fixture(scope="module")
def admin(vm: str) -> testinfra.host.Host:
    """The VM as admin, the passwordless-sudo user Ansible connects as."""
    return guest("admin", vm)


@pytest.fixture(scope="module")
def lab_vm_admin(lab_vm: str) -> testinfra.host.Host:
    """Any lab VM, sandbox or upstream fixture, as admin."""
    return guest("admin", lab_vm)


@pytest.fixture(scope="module")
def upstream_admin(upstream_vm: str) -> testinfra.host.Host:
    """An upstream fixture VM as admin: a machine beside the host that is not the sandbox."""
    return guest("admin", upstream_vm)


@pytest.fixture(scope="module")
def dev(vm: str) -> testinfra.host.Host:
    """The VM as dev, the unprivileged day-to-day user."""
    return guest("dev", vm)
