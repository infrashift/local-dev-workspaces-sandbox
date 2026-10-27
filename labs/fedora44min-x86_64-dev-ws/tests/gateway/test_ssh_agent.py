"""The dedicated sandbox ssh-agent (scenario 4): the only thing the sandbox's dev session forwards.

It holds the egress key and a short-lived certificate Vault's SSH CA signed
for the SCP target's principal -- nothing else, and never the operator's own
keys. The certificate expires on its own; `agent-cert` renews it.
"""

import os
import re
import stat
import time
from datetime import datetime
from pathlib import Path

import gateway_lab as gw
import lab
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} gateway TAGS=ssh_agent"
VARS = gw.role_vars("sandbox_ssh_agent")
UNIT = VARS["sandbox_ssh_agent_unit"]
KEY = Path(VARS["sandbox_ssh_agent_key"].replace("{{ sandbox_ssh_agent_home }}", str(Path.home())))
CERT = Path(str(KEY) + "-cert.pub")
PRINCIPAL = gw.GATEWAY_VARS["scp_target_user"]


def agent_identities() -> list[list[str]]:
    out = lab.run(["ssh-add", "-L"], env_extra={"SSH_AUTH_SOCK": str(L.sandbox_agent_sock)})
    assert out.returncode == 0, f"the sandbox agent lists no identities ({out.stdout.strip()}): run {GATEWAY} agent-cert"
    return [line.split() for line in out.stdout.splitlines() if line.strip()]


def test_agent_unit_is_active_and_enabled():
    assert gw.systemctl("is-active", UNIT, user=True) == "active", f"{UNIT} (user) is not active: {FIX}"
    assert gw.systemctl("is-enabled", UNIT, user=True) == "enabled", f"{UNIT} (user) is not enabled: {FIX}"


def test_agent_socket_is_private():
    sock = L.sandbox_agent_sock
    assert sock.exists() and stat.S_ISSOCK(sock.stat().st_mode), f"{sock} is not a socket: {FIX}"
    assert sock.stat().st_uid == os.getuid(), f"{sock} is not yours"
    assert sock.parent.stat().st_mode & 0o077 == 0, f"{sock.parent} is readable by others; it must be 0700"


def test_egress_key_is_private():
    assert KEY.is_file(), f"{KEY} is missing: {FIX}"
    assert KEY.stat().st_mode & 0o077 == 0, f"{KEY} is mode {KEY.stat().st_mode & 0o777:o}: chmod 600 it"


def test_agent_holds_only_the_egress_key_and_its_certificate():
    public = Path(str(KEY) + ".pub").read_text().split()[1]
    cert = CERT.read_text().split()[1] if CERT.is_file() else None
    held = agent_identities()
    others = [ident[0] for ident in held if ident[1] not in (public, cert)]
    assert not others, f"the sandbox agent holds other keys {others}: SSH_AUTH_SOCK={L.sandbox_agent_sock} ssh-add -D"
    certs = [ident for ident in held if ident[0].endswith("-cert-v01@openssh.com")]
    assert len(certs) == 1, f"the sandbox agent holds {len(certs)} certificates, expected 1: run {GATEWAY} agent-cert"


def test_certificate_is_for_the_scp_principal_and_still_valid():
    assert CERT.is_file(), f"{CERT} is missing: run {GATEWAY} agent-cert"
    text = lab.run(["ssh-keygen", "-L", "-f", str(CERT)]).stdout
    principals = re.search(r"Principals:\s*\n((?:\s{16}\S+\n)+)", text)
    assert principals and principals.group(1).split() == [PRINCIPAL], (
        f"{CERT} is for {principals.group(1).split() if principals else 'no principal'}, expected [{PRINCIPAL}]"
    )
    valid = re.search(r"Valid: from (\S+) to (\S+)", text)
    assert valid, f"{CERT} has no validity window ({text.strip()})"
    expires = datetime.fromisoformat(valid.group(2)).timestamp()
    assert expires > time.time(), f"{CERT} expired at {valid.group(2)}: run {GATEWAY} agent-cert"

