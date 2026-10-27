"""The gateway PKI: the CA the sandbox guests trust (CA_TRUST_DIR), checked before `apply` needs it.

gateway_pki writes the CA's public certificate here, and the ca_trust role
installs every certificate in this directory on each sandbox guest; see the
Zero-Trust Surrogate Gateway concept. Only the certificate leaves the host:
the CA key stays root-only under /etc/ai-sandbox/pki.
"""

import re

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} gateway TAGS=pki"
FILES = sorted([*L.ca_trust_dir.glob("*.pem"), *L.ca_trust_dir.glob("*.crt")])


def certificates() -> list[tuple[str, str]]:
    """(file:index, PEM) for every certificate in every file."""
    pems = []
    for path in FILES:
        blocks = re.findall(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", path.read_text(), re.DOTALL)
        pems += [(f"{path.name}:{i + 1}", pem) for i, pem in enumerate(blocks)]
    return pems


def test_gateway_ca_is_exported():
    assert certificates(), f"no certificate in {L.ca_trust_dir}/*.pem or *.crt: {FIX}"


def test_no_private_key_is_exported():
    """The directory is copied to every guest; a key there would hand the guest the CA."""
    for path in FILES:
        assert "PRIVATE KEY" not in path.read_text(), f"{path} holds a private key; delete it and {FIX}"


@pytest.mark.parametrize(("label", "pem"), certificates(), ids=[c[0] for c in certificates()])
def test_certificate_is_an_unexpired_ca(label, pem):
    expiry = lab.run(["openssl", "x509", "-noout", "-checkend", "0"], input=pem + "\n")
    assert expiry.returncode == 0, f"{label} is expired or unreadable: {expiry.stdout} {expiry.stderr}: {FIX}"
    ext = lab.run(["openssl", "x509", "-noout", "-ext", "basicConstraints"], input=pem + "\n").stdout
    assert "CA:TRUE" in ext, f"{label} is not a CA certificate; only CAs belong in {L.ca_trust_dir}"


def test_gateway_ca_may_vouch_for_the_gateway_only():
    """Critical name constraints: the CA the guests trust can sign for the gateway hosts, and for no IP address.

    No IP subtree is permitted: Bun (Claude Code) refuses an IP SAN matched against one
    (issues/Claude Code refuses the gateway CA's name constraints).
    """
    ca = L.ca_trust_dir / "ai-sandbox-gateway-ca.pem"
    assert ca.is_file(), f"{ca} is missing: {FIX}"
    ext = lab.run(["openssl", "x509", "-noout", "-ext", "nameConstraints"], input=ca.read_text()).stdout
    assert ext and "critical" in ext.splitlines()[0], f"{ca} has no critical name constraints: {FIX}"
    permitted, _, excluded = ext.partition("Excluded:")
    names = set(re.findall(r"(?m)^\s+(DNS:\S+|IP:\S+)$", permitted))
    expected = {f"DNS:{host}" for host in gw.GATEWAY_HOSTS}
    assert names == expected, f"{ca} permits {sorted(names)}, expected {sorted(expected)}: {FIX}"
    excluded_ips = set(re.findall(r"(?m)^\s+(IP:\S+)$", excluded))
    every_ip = {"IP:0.0.0.0/0.0.0.0", "IP:0:0:0:0:0:0:0:0/0:0:0:0:0:0:0:0"}
    assert excluded_ips == every_ip, f"{ca} excludes {sorted(excluded_ips)}, not every IP: {FIX}"
