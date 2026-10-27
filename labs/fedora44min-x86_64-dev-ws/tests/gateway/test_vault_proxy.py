"""Vault Proxy: Envoy's only way to Vault, a unix socket only the envoy group can open.

The proxy authenticates with the envoy-gateway AppRole and attaches its token
to every request (use_auto_auth_token = force), so whoever can open the
socket reads surrogate records. That must be Envoy alone -- not the operator,
and never a guest.
"""

import os
import socket
import stat

import gateway_lab as gw
import lab
from lab import GATEWAY

FIX = f"run {GATEWAY} gateway TAGS=vault"
SOCKET = gw.PINS["vault_proxy_socket_path"]
PARAMS = lab.role_params(gw.PLAYBOOK, "vault_proxy")
GROUP = PARAMS["vault_proxy_socket_group"]
OWNER = gw.role_vars("vault_proxy")["vault_proxy_user"]


def test_unit_is_active_and_enabled():
    assert gw.systemctl("is-active", "vault-proxy") == "active", f"vault-proxy.service is not active: {FIX}"
    assert gw.systemctl("is-enabled", "vault-proxy") == "enabled", f"vault-proxy.service is not enabled: {FIX}"


def test_socket_is_owned_and_moded_for_envoy_only(host):
    sock = host.file(SOCKET)
    assert sock.exists and stat.S_ISSOCK(os.stat(SOCKET).st_mode), f"{SOCKET} is not a socket: {FIX}"
    assert (sock.user, sock.group, sock.mode) == (OWNER, GROUP, 0o660), (
        f"{SOCKET} is {sock.user}:{sock.group} {sock.mode:o}, expected {OWNER}:{GROUP} 660: {FIX}"
    )


def test_operator_cannot_open_the_socket(host):
    """The operator has their own token; the proxy's AppRole token is Envoy's alone."""
    assert GROUP not in host.user().groups, (
        f"you are in group {GROUP}, so you can read surrogate records through {SOCKET} without a token: "
        f"sudo gpasswd -d $USER {GROUP}"
    )
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET)
    except PermissionError:
        return
    finally:
        client.close()
    raise AssertionError(f"the operator could connect to {SOCKET}: it must be {GROUP}-only")
