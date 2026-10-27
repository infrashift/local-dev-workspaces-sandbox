"""The gateway suite: the zero-trust gateway lab-gateway.mk installed on this host.

Nothing needs sudo: root-only state is checked through what the operator can
see (unit state, file modes, listeners, and the loopback Vault, Consul and
Envoy admin APIs with the operator tokens). See gateway_lab.py.
"""

import platform
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if (platform.system(), platform.machine()) == ("Linux", "x86_64"):
        return
    skip = pytest.mark.skip(reason=f"the gateway suite needs a Linux x86_64 host, not {platform.platform()}")
    for item in items:
        if item.path.is_relative_to(HERE):
            item.add_marker(skip)
