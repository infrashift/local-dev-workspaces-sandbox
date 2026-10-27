"""The lab as the verification suites see it: paths, pins and expected state.

Make passes every path as an environment variable (lab-config.mk PYTEST_ENV).
Every expected value is read from its source -- the playbooks, group_vars, the
role constants in vars/main.yml, the requirements files, terraform.tfvars and
the egress baseline catalog --
so a test never restates a pin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ENV_VARS = (
    "LAB_NAME",
    "LAB_DIR",
    "PROJECT_ROOT",
    "TOOLS_BIN",
    "IMAGES_DIR",
    "POOLS_DIR",
    "CA_TRUST_DIR",
    "TLS_INSPECTION_DIR",
    "VENV",
    "PYTHON_VERSION",
    "COLLECTIONS_DIR",
    "UV",
    "UV_VERSION",
    "PYTHON_PLATFORM",
    "TERRAFORM",
    "TF_DIR",
    "VM_SCRIPTS",
    "LIBVIRT_URI",
    "SSH_KEY_DIR",
    "SSH_CONFIG_DIR",
    "SSH_ID",
    "SANDBOX_VM",
    "SANDBOX_AGENT_SOCK",
    "SANDBOX_NETWORK",
    "SANDBOX_BRIDGE",
    "SANDBOX_CIDR",
    "GATEWAY_IP",
    "PROXY_PORT",
    "GATEWAY_PORT",
    "UPSTREAM_NETWORK",
    "UPSTREAM_BRIDGE",
    "UPSTREAM_CIDR",
    "OPERATOR_DIR",
    "HOST_INVENTORY",
    "BECOME_VAULT",
    "VAULT_KEY",
    "CREDENTIALS_VARS",
    "CREDENTIALS_VAULT",
)

BOOTSTRAP = "make -f lab-bootstrap.mk"
GATEWAY = "make -f lab-gateway.mk"
PROVISION = "make -f lab-provision.mk"


def missing_env() -> list[str]:
    return [name for name in ENV_VARS if not os.environ.get(name)]


@dataclass(frozen=True)
class Lab:
    name: str
    lab_dir: Path
    project_root: Path
    tools_bin: Path
    images_dir: Path
    pools_dir: Path
    ca_trust_dir: Path
    tls_inspection_dir: Path
    venv: Path
    python_version: str
    collections_dir: Path
    uv: Path
    uv_version: str
    python_platform: str
    terraform: Path
    tf_dir: Path
    vm_scripts: Path
    libvirt_uri: str
    ssh_key_dir: Path
    ssh_config_dir: Path
    ssh_id: str
    sandbox_vm: str
    sandbox_agent_sock: Path
    sandbox_network: str
    sandbox_bridge: str
    sandbox_cidr: str
    gateway_ip: str
    proxy_port: int
    gateway_port: int
    upstream_network: str
    upstream_bridge: str
    upstream_cidr: str
    operator_dir: Path
    host_inventory: Path
    become_vault: Path
    vault_key: Path
    credentials_vars: Path
    credentials_vault: Path

    @property
    def playbooks(self) -> Path:
        return self.lab_dir / "ansible" / "playbooks"

    @property
    def lab_pool(self) -> Path:
        return self.pools_dir / self.name

    @property
    def tfvars(self) -> Path:
        return self.tf_dir / "terraform.tfvars"

    @property
    def proxy_url(self) -> str:
        return f"http://{self.gateway_ip}:{self.proxy_port}"

    def roles_dir(self, lane: str) -> Path:
        return self.project_root / "ansible" / "roles" / lane

    def ssh_key(self, role: str) -> Path:
        return self.ssh_key_dir / f"{self.ssh_id}@{role}"

    def ssh_config(self, role: str) -> Path:
        return self.ssh_config_dir / f"{self.ssh_id}@{role}"

    def ssh_alias(self, role: str, vm: str | None = None) -> str:
        return f"{self.ssh_id}.{role}" + (f".{vm}" if vm else "")


@cache
def lab() -> Lab:
    env = os.environ

    def path(name: str) -> Path:
        return Path(env[name])

    return Lab(
        name=env["LAB_NAME"],
        lab_dir=path("LAB_DIR"),
        project_root=path("PROJECT_ROOT"),
        tools_bin=path("TOOLS_BIN"),
        images_dir=path("IMAGES_DIR"),
        pools_dir=path("POOLS_DIR"),
        ca_trust_dir=path("CA_TRUST_DIR"),
        tls_inspection_dir=path("TLS_INSPECTION_DIR"),
        venv=path("VENV"),
        python_version=env["PYTHON_VERSION"],
        collections_dir=path("COLLECTIONS_DIR"),
        uv=path("UV"),
        uv_version=env["UV_VERSION"],
        python_platform=env["PYTHON_PLATFORM"],
        terraform=path("TERRAFORM"),
        tf_dir=path("TF_DIR"),
        vm_scripts=path("VM_SCRIPTS"),
        libvirt_uri=env["LIBVIRT_URI"],
        ssh_key_dir=path("SSH_KEY_DIR"),
        ssh_config_dir=path("SSH_CONFIG_DIR"),
        ssh_id=env["SSH_ID"],
        sandbox_vm=env["SANDBOX_VM"],
        sandbox_agent_sock=path("SANDBOX_AGENT_SOCK"),
        sandbox_network=env["SANDBOX_NETWORK"],
        sandbox_bridge=env["SANDBOX_BRIDGE"],
        sandbox_cidr=env["SANDBOX_CIDR"],
        gateway_ip=env["GATEWAY_IP"],
        proxy_port=int(env["PROXY_PORT"]),
        gateway_port=int(env["GATEWAY_PORT"]),
        upstream_network=env["UPSTREAM_NETWORK"],
        upstream_bridge=env["UPSTREAM_BRIDGE"],
        upstream_cidr=env["UPSTREAM_CIDR"],
        operator_dir=path("OPERATOR_DIR"),
        host_inventory=path("HOST_INVENTORY"),
        become_vault=path("BECOME_VAULT"),
        vault_key=path("VAULT_KEY"),
        credentials_vars=path("CREDENTIALS_VARS"),
        credentials_vault=path("CREDENTIALS_VAULT"),
    )


# ---------------------------------------------------------------------------
# Ansible sources: playbooks, role constants, group_vars
# ---------------------------------------------------------------------------
@cache
def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def play_vars(playbook: str, index: int = 0) -> dict[str, Any]:
    """The vars: block of one play in ansible/playbooks/<playbook>."""
    return _yaml(lab().playbooks / playbook)[index].get("vars", {})


def role_params(playbook: str, role: str, **match: Any) -> dict[str, Any]:
    """The parameters a playbook passes to a role (its roles: entry, less role/tags).

    The first entry for the role, or, when a playbook applies it more than
    once, the first whose parameters include every key=value in match.
    """
    for play in _yaml(lab().playbooks / playbook):
        for entry in play.get("roles", []):
            if entry.get("role") == role and all(entry.get(k) == v for k, v in match.items()):
                return {k: v for k, v in entry.items() if k not in ("role", "tags")}
    raise KeyError(f"{playbook} applies no role {role} with {match}")


def role_vars(lane: str, role: str) -> dict[str, Any]:
    """A role's constants (vars/main.yml). Only plain values are usable here, not Jinja."""
    return _yaml(lab().roles_dir(lane) / role / "vars" / "main.yml")


def group_vars(group: str = "all") -> dict[str, Any]:
    return _yaml(lab().lab_dir / "ansible" / "inventory" / "group_vars" / group / "vars.yml")


def render(value: str, group: str = "dev_ws") -> str:
    """Resolve the plain `{{ name }}` references a playbook value makes to group_vars (all, then group)."""
    known = {**group_vars(), **group_vars(group)}
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(known[m.group(1)]), value)


def vars_file(name: str) -> dict[str, Any]:
    """A playbook vars file, ansible/vars/<name> (gateway.yml, egress-baseline.yml)."""
    return _yaml(lab().lab_dir / "ansible" / "vars" / name)


# ---------------------------------------------------------------------------
# Certificates (the PEM chains ca_trust and the gateway read)
# ---------------------------------------------------------------------------
PEM_CERT_RE = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.DOTALL)


def chain_files(directory: Path) -> list[Path]:
    """Every *.pem / *.crt in a chain directory, as the roles glob them; none if it is missing."""
    return sorted([*directory.glob("*.pem"), *directory.glob("*.crt")])


def certificates(directory: Path) -> list[tuple[str, str]]:
    """(file:index, PEM) for every certificate in every chain file of a directory."""
    pems = []
    for path in chain_files(directory):
        pems += [(f"{path.name}:{i + 1}", pem) for i, pem in enumerate(PEM_CERT_RE.findall(path.read_text()))]
    return pems


def sha256_fingerprint(pem: str) -> str:
    """The certificate's SHA-256 fingerprint, lower-case hex without colons."""
    out = run(["openssl", "x509", "-noout", "-fingerprint", "-sha256"], input=pem + "\n").stdout
    return out.strip().split("=", 1)[1].replace(":", "").lower()


# ---------------------------------------------------------------------------
# Python and collection pins
# ---------------------------------------------------------------------------
def normalize(name: str) -> str:
    """PEP 503 name normalization, so lock and freeze names compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def pinned_packages(lock: Path) -> dict[str, str]:
    """name -> version from a `uv pip compile` lock (or `uv pip freeze` output)."""
    pins = re.findall(r"(?m)^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\;]+)", lock.read_text())
    return {normalize(name): version for name, version in pins}


def pinned_collections() -> dict[str, str]:
    return {c["name"]: c["version"] for c in _yaml(lab().project_root / "requirements.yml")["collections"]}


# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------
def tfvars_base_images() -> list[str]:
    """Every base_image in terraform.tfvars, read as lab-provision.mk's preflight reads it.

    Terraform cannot be asked before `terraform init`, which the host suite
    must not need.
    """
    text = lab().tfvars.read_text()
    return sorted(set(re.findall(r'(?m)^\s*base_image\s*=\s*"([^"]*)"', text)))


@cache
def tf_vms() -> dict[str, dict[str, Any]]:
    """var.vms as Terraform itself evaluates it (terraform.tfvars and defaults)."""
    result = run(
        [str(lab().terraform), f"-chdir={lab().tf_dir}", "console"],
        input="jsonencode(var.vms)\n",
        env_extra={"CHECKPOINT_DISABLE": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"terraform console failed (run {PROVISION} init): {result.stderr.strip()}")
    # console prints the JSON as an HCL string literal: decode twice.
    return json.loads(json.loads(result.stdout))


def vms_in(group: str) -> dict[str, dict[str, Any]]:
    """The VMs in one inventory group (a role in var.vms)."""
    return {name: spec for name, spec in tf_vms().items() if group in spec["roles"]}


def dev_ws_vms() -> dict[str, dict[str, Any]]:
    """The sandbox VMs the guest playbooks configure (inventory group dev_ws)."""
    return vms_in("dev_ws")


def upstream_vms() -> dict[str, dict[str, Any]]:
    """The trusted test fixtures (inventory group upstream)."""
    return vms_in("upstream")


# ---------------------------------------------------------------------------
# Processes on the host
# ---------------------------------------------------------------------------
def run(
    argv: list[str],
    *,
    input: str | None = None,
    env_extra: dict[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        argv, input=input, capture_output=True, text=True, env=env, timeout=timeout, check=False
    )
