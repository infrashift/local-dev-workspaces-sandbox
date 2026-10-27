"""Envoy's public upstreams behind an optional TLS-inspecting proxy (TLS_INSPECTION_DIR).

Behind a proxy such as Zscaler, every public upstream presents a certificate
the proxy re-signed. envoy_gateway then verifies the routes with ca: system
against the host's public roots plus the proxy's chain (the public-upstream
bundle). Without a chain it uses the host's roots alone and leaves no bundle
behind. Either way, Envoy must complete a verified handshake with every public
upstream: the live checks ask Envoy for an anonymous route.

See the Corporate TLS Interception (ZScaler) concept and the runbook Run the
Lab Behind a TLS-Inspecting Proxy.
"""

import os
import tempfile
from pathlib import Path

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} gateway TAGS=envoy"
CONST = gw.role_vars("envoy_gateway")
HOST_BUNDLE = CONST["envoy_gateway_host_ca_bundle"]
BUNDLE = Path(CONST["envoy_gateway_inspection_bundle"])
FILES = lab.chain_files(L.tls_inspection_dir)
CHAIN = lab.certificates(L.tls_inspection_dir)
INSPECTING = bool(FILES)
PUBLIC_ROUTES = [route for route in gw.ROUTES if route["upstream"]["ca"] == "system"]
ANONYMOUS_PUBLIC = [route["host"] for route in PUBLIC_ROUTES if route["anonymous"]]

in_use = pytest.mark.skipif(not INSPECTING, reason=f"no TLS-inspection chain in {L.tls_inspection_dir}")
not_in_use = pytest.mark.skipif(INSPECTING, reason=f"a TLS-inspection chain is in {L.tls_inspection_dir}")


def gateway_address_is_up() -> bool:
    """GATEWAY_IP is on a local interface: libvirt brings the sandbox bridge up with the lab."""
    out = lab.run(["ip", "-o", "-4", "addr", "show"]).stdout
    return f" {L.gateway_ip}/" in out


def squash(pem: str) -> str:
    return "".join(pem.split())  # line endings and wrapping do not matter


def trusted_ca_by_sni() -> dict[str, str]:
    """The CA file each upstream TLS cluster verifies with, by its SNI (Envoy's config dump)."""
    dump = gw.envoy().get("/config_dump?resource=static_clusters").json()
    cas = {}
    for config in dump["configs"]:
        tls = config["cluster"].get("transport_socket", {}).get("typed_config", {})
        ca = tls.get("common_tls_context", {}).get("validation_context", {}).get("trusted_ca", {}).get("filename")
        if ca and tls.get("sni"):
            cas[tls["sni"]] = ca
    return cas


@in_use
def test_chain_holds_no_private_key():
    for path in FILES:
        assert "PRIVATE KEY" not in path.read_text(), (
            f"{path} holds a private key: only the proxy's CA certificates belong in {L.tls_inspection_dir}"
        )


@in_use
@pytest.mark.parametrize(("label", "pem"), CHAIN, ids=[c[0] for c in CHAIN])
def test_chain_certificate_is_an_unexpired_ca(label, pem):
    expiry = lab.run(["openssl", "x509", "-noout", "-checkend", "0"], input=pem + "\n")
    assert expiry.returncode == 0, f"{label} is expired or unreadable: export the proxy's current chain"
    ext = lab.run(["openssl", "x509", "-noout", "-ext", "basicConstraints"], input=pem + "\n").stdout
    assert "CA:TRUE" in ext, f"{label} is not a CA certificate; only the proxy's CA chain belongs there"


@pytest.mark.parametrize("route", PUBLIC_ROUTES, ids=[r["host"] for r in PUBLIC_ROUTES])
def test_public_route_verifies_with_the_expected_bundle(route):
    expected = str(BUNDLE) if INSPECTING else HOST_BUNDLE
    actual = trusted_ca_by_sni().get(route["upstream"]["sni"])
    assert actual == expected, (
        f"Envoy verifies {route['host']} with {actual}, expected {expected} "
        f"({'a' if INSPECTING else 'no'} TLS-inspection chain): {FIX}"
    )


@in_use
def test_bundle_is_public_and_holds_the_host_roots_and_the_chain():
    st = BUNDLE.stat()
    assert (st.st_uid, oct(st.st_mode & 0o777)) == (0, "0o644"), f"{BUNDLE} is not root-owned 0644: {FIX}"
    bundle = squash(BUNDLE.read_text())
    for label, pem in CHAIN:
        assert squash(pem) in bundle, f"{BUNDLE} lacks {label} from {L.tls_inspection_dir}: {FIX}"
    roots = lab.PEM_CERT_RE.findall(Path(HOST_BUNDLE).read_text())
    missing = [pem for pem in roots if squash(pem) not in bundle]
    assert not missing, f"{BUNDLE} lacks {len(missing)} of the host's {len(roots)} roots (updated since?): {FIX}"


@not_in_use
def test_no_bundle_is_left_without_a_chain():
    assert not BUNDLE.parent.exists(), f"{BUNDLE.parent} is left over from an earlier chain: {FIX}"


@in_use
def test_the_proxy_really_signs_this_hosts_traffic():
    """The chain is the one intercepting: github.com verifies with it ALONE.

    Fails if there is no inspection after all, or the chain is not the one the
    proxy signs with (an old export, or another tenant's).
    """
    host = PUBLIC_ROUTES[0]["upstream"]["sni"]
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as chain:
        chain.write("\n".join(pem for _, pem in CHAIN) + "\n")
    try:
        result = lab.run(
            ["openssl", "s_client", "-connect", f"{host}:443", "-servername", host, "-brief",
             "-CAfile", chain.name, "-partial_chain", "-verify_return_error"],
            input="",
            timeout=30,
        )
    finally:
        os.unlink(chain.name)
    assert result.returncode == 0, (
        f"{host}'s certificate does not verify with {L.tls_inspection_dir} alone: this host's traffic is not "
        f"inspected by that chain ({result.stderr.strip().splitlines()[-1:]}). Export the proxy's current "
        "chain, or empty the directory if there is no proxy."
    )


@pytest.mark.skipif(
    not gateway_address_is_up(),
    reason=f"{L.gateway_ip} is not up yet: the sandbox bridge comes with make -f lab-provision.mk apply",
)
@pytest.mark.parametrize("host", ANONYMOUS_PUBLIC)
def test_envoy_completes_a_verified_upstream_handshake(host):
    """Live: an anonymous request through the TLS gateway reaches the upstream.

    Envoy answers 503 "upstream connect error ... TLS_error" when it cannot
    verify the upstream: behind an inspecting proxy, the chain is missing.
    """
    gateway_ca = lab.chain_files(L.ca_trust_dir)[0]
    result = lab.run(
        ["curl", "--silent", "--show-error", "--max-time", "30", "--output", "-", "--write-out", "\n%{http_code}",
         "--noproxy", "*", "--resolve", f"{host}:{L.gateway_port}:{L.gateway_ip}", "--cacert", str(gateway_ca),
         f"https://{host}:{L.gateway_port}/"],
        timeout=60,
    )
    assert result.returncode == 0, f"curl through the gateway to {host}: {result.stderr.strip()}"
    body, _, status = result.stdout.rpartition("\n")
    assert not (status == "503" and "upstream connect error" in body), (
        f"Envoy could not reach {host} over verified TLS: {body.strip()[:200]}. Behind a TLS-inspecting proxy, "
        f"put its chain in {L.tls_inspection_dir} and {FIX}"
    )
