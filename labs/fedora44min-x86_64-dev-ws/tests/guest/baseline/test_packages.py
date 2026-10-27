"""The lab's base packages (system_packages, from group_vars dev_packages).

Freshness is not tested: vm-baseline upgrades every package, but a test that
expects no pending update would fail as soon as Fedora publishes one.
"""

import lab
import pytest
from lab import PROVISION

PACKAGES = lab.group_vars()["dev_packages"]


@pytest.mark.parametrize("package", PACKAGES)
def test_package_is_installed(admin, package):
    result = admin.run("rpm -q --whatprovides %s", package)
    assert result.rc == 0, f"{package} is not installed: {result.stdout.strip()}: run {PROVISION} ansible"
