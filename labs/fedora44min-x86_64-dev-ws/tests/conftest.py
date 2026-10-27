"""Refuse to run outside Make, which passes the lab's paths (lab-config.mk PYTEST_ENV)."""

import lab
import pytest


def pytest_configure(config: pytest.Config) -> None:
    missing = lab.missing_env()
    if missing:
        pytest.exit(
            "Run the suites through make: make -f lab-bootstrap-verify.mk, "
            "make -f lab-gateway-verify.mk or "
            f"make -f lab-provision-verify.mk (missing: {', '.join(missing)})",
            returncode=4,
        )
