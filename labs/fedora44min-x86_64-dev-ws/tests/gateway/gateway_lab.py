"""The gateway as its suite sees it: the playbook's pins, its vars files, and the
operator's view of Vault, Consul and Envoy.

Everything here reads its expectation from a source -- gateway-host.yml's pin
block, vars/gateway.yml, vars/egress-baseline.yml, the gateway roles'
vars/main.yml -- and talks to the services only on loopback or their unix
sockets (Envoy: its GET-only admin view), with the operator tokens the
gateway playbook wrote. A token is read from its file and
sent in a header; it never appears in a test id, a message or a log.
"""

from __future__ import annotations

import getpass
import grp
import http.client
import json
import os
import re
import socket
import stat
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import lab

L = lab.lab()
PLAYBOOK = "gateway-host.yml"
PINS = lab.play_vars(PLAYBOOK)
GATEWAY_VARS = lab.vars_file("gateway.yml")
CATALOG = lab.vars_file("egress-baseline.yml")["egress_catalog"]
ROUTES = GATEWAY_VARS["gateway_routes"]
GATEWAY_HOSTS = [route["host"] for route in ROUTES]
SYSTEM_BIN = Path(PINS["system_bin"])
KV_PREFIX = PINS["egress_kv_prefix"]
ENVOY_VARS = lab.role_vars("gateway", "envoy_gateway")
ENVOY_ADMIN_SOCKET = ENVOY_VARS["envoy_gateway_admin_socket"]
ENVOY_ADMIN_READONLY_SOCKET = ENVOY_VARS["envoy_gateway_admin_readonly_socket"]

# The template's rule for a usable allow-list key (envoy_gateway's
# connect-routes.ctmpl.j2): <host>:<port> or *.<suffix>:<port>, lower case.
ENTRY_RE = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*:[0-9]{1,5}$")


def role_vars(role: str) -> dict[str, Any]:
    return lab.role_vars("gateway", role)


def catalog_entries() -> list[tuple[str, dict[str, Any]]]:
    """(category, entry) for every entry in the catalog, enabled or not."""
    return [(category, entry) for category, spec in CATALOG.items() for entry in spec["entries"]]


def desired_baseline() -> set[str]:
    """<category>/<host>:<port> for every entry of every enabled category: what consul_egress seeds."""
    return {
        f"{category}/{entry['host']}:{entry.get('port', 443)}"
        for category in PINS["egress_baseline_categories"]
        for entry in CATALOG[category]["entries"]
    }


# ---------------------------------------------------------------------------
# Loopback and unix-socket APIs
# ---------------------------------------------------------------------------
class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over a unix socket (the Host header says localhost)."""

    def __init__(self, path: str, timeout: float = 10) -> None:
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


@dataclass(frozen=True)
class Response:
    status: int
    body: str

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass(frozen=True)
class Api:
    """One local HTTP API -- a loopback URL, or a unix socket -- optionally authenticated by a token file."""

    base: str
    token_header: str | None = None
    token_file: Path | None = None
    unix_socket: str | None = None

    def request(self, method: str, path: str, data: bytes | None = None) -> Response:
        headers = {}
        if self.token_header and self.token_file:
            headers[self.token_header] = self.token_file.read_text().strip()
        if self.unix_socket:
            conn = UnixHTTPConnection(self.unix_socket)
            try:
                conn.request(method, path, body=data, headers=headers)
                resp = conn.getresponse()
                return Response(resp.status, resp.read().decode())
            finally:
                conn.close()
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return Response(resp.status, resp.read().decode())
        except urllib.error.HTTPError as err:
            return Response(err.code, err.read().decode())

    def get(self, path: str) -> Response:
        return self.request("GET", path)

    def anonymous(self) -> Api:
        return Api(self.base, unix_socket=self.unix_socket)


@cache
def vault() -> Api:
    return Api("http://localhost", "X-Vault-Token", L.operator_dir / "vault-operator.token", PINS["vault_socket"])


@cache
def consul() -> Api:
    return Api("http://localhost", "X-Consul-Token", L.operator_dir / "consul-operator.token", PINS["consul_socket"])


@cache
def envoy() -> Api:
    """Envoy's GET-only admin view: the admin socket itself is envoy's alone."""
    return Api("http://localhost", unix_socket=ENVOY_ADMIN_READONLY_SOCKET)


def kv_keys() -> list[str]:
    """Every key under the egress prefix, read with the operator token."""
    resp = consul().get(f"/v1/kv/{KV_PREFIX}/?keys")
    assert resp.status == 200, f"Consul refused the operator's key listing ({resp.status}): run {lab.GATEWAY} TAGS=consul"
    return resp.json()


def envoy_stats(prefix: str) -> dict[str, str]:
    body = envoy().get(f"/stats?filter=^{re.escape(prefix)}").body
    return dict(line.split(": ", 1) for line in body.splitlines() if ": " in line)


# ---------------------------------------------------------------------------
# The host
# ---------------------------------------------------------------------------
def listeners(port: int) -> set[str]:
    """The addresses with a TCP listener on this port (ss sees every user's sockets)."""
    out = subprocess.run(["ss", "-Hltn", f"sport = :{port}"], capture_output=True, text=True, check=True).stdout
    return {line.split()[3].rsplit(":", 1)[0].strip("[]") for line in out.splitlines() if line.strip()}


def socket_problems(path: str, group: str) -> list[str]:
    """What is wrong with a server's API socket: it must be 0660 for its group, and rw for the operator by ACL."""
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return [f"{path} is missing"]
    problems = []
    if not stat.S_ISSOCK(info.st_mode):
        problems.append(f"{path} is not a socket")
    owner_group = grp.getgrgid(info.st_gid).gr_name
    if (owner_group, stat.S_IMODE(info.st_mode)) != (group, 0o660):
        problems.append(f"{path} is group {owner_group} mode {stat.S_IMODE(info.st_mode):o}, expected {group} 660")
    acl = subprocess.run(["getfacl", "-cp", path], capture_output=True, text=True, check=False).stdout.split()
    if f"user:{getpass.getuser()}:rw-" not in acl:
        problems.append(f"{path} has no ACL entry user:{getpass.getuser()}:rw- (its ACL: {acl})")
    return problems


def systemctl(*args: str, user: bool = False) -> str:
    argv = ["systemctl", *(["--user"] if user else []), *args]
    return subprocess.run(argv, capture_output=True, text=True, check=False).stdout.strip()
