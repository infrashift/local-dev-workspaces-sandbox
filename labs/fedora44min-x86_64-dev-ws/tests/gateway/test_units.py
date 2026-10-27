"""The gateway's services: each sandboxed by systemd, and none holding what another needs.

systemd-analyze security scores a unit's sandboxing from 0 (best) to 10. Each
role records the score its unit had when the sandboxing was set; a weaker
unit fails here. consul-template runs as its own user: it holds the Consul
read token and writes the route table, and cannot reach Vault Proxy's socket
or the gateway key, which are Envoy's.
"""

import grp
import os
import pwd
import re
import stat
import subprocess

import gateway_lab as gw
import pytest
from lab import GATEWAY

FIX = f"run {GATEWAY} gateway"
CEILINGS = {
    "vault": gw.role_vars("vault_server")["vault_server_max_exposure"],
    "vault-proxy": gw.role_vars("vault_proxy")["vault_proxy_max_exposure"],
    "consul": gw.role_vars("consul_server")["consul_server_max_exposure"],
    **gw.ENVOY_VARS["envoy_gateway_max_exposure"],
}
CT_USER = gw.ENVOY_VARS["envoy_gateway_ct_user"]
ENVOY_USER = gw.ENVOY_VARS["envoy_gateway_user"]


def exposure(unit: str) -> float:
    out = subprocess.run(["systemd-analyze", "security", "--no-pager", f"{unit}.service"],
                         capture_output=True, text=True, check=False).stdout
    match = re.search(r"exposure level for \S+: ([0-9.]+)", out)
    assert match, f"systemd-analyze security {unit}.service printed no score"
    return float(match.group(1))


@pytest.mark.parametrize("unit", sorted(CEILINGS))
def test_unit_sandboxing_has_not_weakened(unit):
    score = exposure(unit)
    assert score <= CEILINGS[unit], f"{unit}.service exposure {score}, at most {CEILINGS[unit]}: {FIX}"


def unit_groups(unit: str, user: str) -> set[str]:
    """Every group a unit's process has: its user's, and its SupplementaryGroups."""
    shown = gw.systemctl("show", "-p", "SupplementaryGroups", "--value", f"{unit}.service").split()
    member = {g.gr_name for g in grp.getgrall() if user in g.gr_mem}
    return {grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name, *member, *shown}


def test_consul_template_runs_apart_from_envoy():
    unit = "ai-sandbox-consul-template"
    assert gw.systemctl("show", "-p", "User", "--value", f"{unit}.service") == CT_USER, f"{unit} is not {CT_USER}: {FIX}"
    groups = unit_groups(unit, CT_USER)
    # envoy opens Vault Proxy's socket and reads the gateway key; vault-clients opens Vault's.
    forbidden = {ENVOY_USER, gw.PINS["vault_socket_group"]} & groups
    assert not forbidden, f"consul-template is in {sorted(forbidden)}: it could reach Envoy's or Vault's sockets: {FIX}"


def test_envoy_cannot_reach_consul():
    groups = unit_groups("envoy", ENVOY_USER)
    assert gw.PINS["consul_socket_group"] not in groups, f"Envoy is in {gw.PINS['consul_socket_group']}: {FIX}"


def test_route_table_is_consul_templates_and_readable_by_envoy_only():
    rds_dir = gw.ENVOY_VARS["envoy_gateway_rds_dir"]
    info = os.stat(rds_dir)
    owner, group, mode = pwd.getpwuid(info.st_uid).pw_name, grp.getgrgid(info.st_gid).gr_name, stat.S_IMODE(info.st_mode)
    assert (owner, group, mode) == (CT_USER, ENVOY_USER, 0o2750), (
        f"{rds_dir} is {owner}:{group} {mode:o}, expected {CT_USER}:{ENVOY_USER} 2750: {FIX}"
    )
