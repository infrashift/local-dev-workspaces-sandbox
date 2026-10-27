"""The host suite: the Linux x86_64 machine that lab-bootstrap.mk prepared.

Tests use pytest-testinfra's `host` fixture, which is the local machine here.
Nothing needs sudo: root-only state is checked through what the operator can
see (unit state, file modes, the loopback APIs with the operator tokens).
"""

import platform
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if (platform.system(), platform.machine()) == ("Linux", "x86_64"):
        return
    skip = pytest.mark.skip(reason=f"the host suite needs a Linux x86_64 host, not {platform.platform()}")
    for item in items:
        if item.path.is_relative_to(HERE):
            item.add_marker(skip)
