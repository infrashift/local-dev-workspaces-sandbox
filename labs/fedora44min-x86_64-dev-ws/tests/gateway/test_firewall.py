"""The sandbox firewall: its own nft table, loaded by its own unit (concepts/Isolated Sandbox Network).

The loaded table needs root to list; sandbox_firewall asserts it on every
run. Here: the unit that loads it is up, the ruleset it loads names this
lab's bridge, address and ports, and nftables.service -- whose `flush
ruleset` would wipe libvirt's and docker's tables -- stays off.
"""

from pathlib import Path

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} gateway TAGS=firewall"
VARS = gw.role_vars("sandbox_firewall")
RULES = Path(VARS["sandbox_firewall_rules"])


def test_unit_is_active_and_enabled():
    assert gw.systemctl("is-active", "ai-sandbox-firewall") == "active", f"ai-sandbox-firewall is not active: {FIX}"
    assert gw.systemctl("is-enabled", "ai-sandbox-firewall") == "enabled", (
        f"ai-sandbox-firewall is not enabled at boot: {FIX}"
    )


def test_nftables_service_stays_disabled():
    state = gw.systemctl("is-enabled", "nftables")
    assert state != "enabled", (
        "nftables.service is enabled: at boot its `flush ruleset` wipes libvirt's and docker's tables "
        "(and this one). sudo systemctl disable nftables"
    )


@pytest.mark.parametrize(
    "expected",
    [
        f"table inet {VARS['sandbox_firewall_table']}",
        f'iifname "{L.sandbox_bridge}"',
        f"ip daddr {L.gateway_ip} tcp dport {{ {L.proxy_port}, {L.gateway_port} }}",
        f'oifname "{L.sandbox_bridge}" counter reject',
        f'ip daddr {L.gateway_ip} iifname != {{ "lo", "{L.sandbox_bridge}" }} counter reject',
    ],
    ids=["table", "bridge", "gateway-ports", "forward-reject", "gateway-from-bridge-only"],
)
def test_ruleset_names_this_lab(expected):
    assert RULES.is_file(), f"{RULES} is missing: {FIX}"
    assert expected in RULES.read_text(), f"{RULES} has no '{expected}' (lab-config.mk changed?): {FIX}"
