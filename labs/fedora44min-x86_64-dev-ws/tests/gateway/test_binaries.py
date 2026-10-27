"""Vault, Consul, consul-template and Envoy: the pinned versions, and the copies that run.

hashicorp_release and envoy_release install them in system_bin after verifying
their signatures; a copy earlier on PATH (an apt package, a manual install)
would run instead of the verified one.
"""

import os
import re
import shutil

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

BINARIES = [
    # name, pin, version argv, tag
    ("vault", gw.PINS["vault_version"], ["version"], "vault"),
    ("consul", gw.PINS["consul_version"], ["version"], "consul"),
    ("consul-template", gw.PINS["consul_template_version"], ["-version"], "consul"),
    ("envoy", gw.PINS["envoy_version"], ["--version"], "envoy"),
]


@pytest.mark.parametrize(("name", "pin", "argv", "tag"), BINARIES, ids=[b[0] for b in BINARIES])
def test_binary_is_the_pinned_version(name, pin, argv, tag):
    path = gw.SYSTEM_BIN / name
    assert os.access(path, os.X_OK), f"{path} is missing: run {GATEWAY} gateway TAGS={tag}"
    out = lab.run([str(path), *argv]).stdout
    assert re.search(rf"(^|[\sv/]){re.escape(pin)}([\s/(]|$)", out), (
        f"{path} reports '{out.strip()}', expected {pin}: run {GATEWAY} gateway TAGS={tag}"
    )


@pytest.mark.parametrize(("name", "pin", "argv", "tag"), BINARIES, ids=[b[0] for b in BINARIES])
def test_nothing_shadows_the_pinned_binary(name, pin, argv, tag):
    found = shutil.which(name)
    assert found == str(gw.SYSTEM_BIN / name), (
        f"`{name}` on PATH is {found}, not the verified {gw.SYSTEM_BIN / name}: remove the other copy"
    )
