"""The gateway CA on the sandbox guests (ca_trust): anchors, bundle, env vars, and verified TLS out.

The optional TLS-inspecting proxy's chain, ca_trust's second instance, is
test_tls_inspection.py's. See the Corporate TLS Interception (ZScaler) concept.
"""

import re

import lab
import pytest
from lab import PROVISION

L = lab.lab()
FIX = f"run {PROVISION} ansible"
PARAMS = lab.role_params("vm-baseline.yml", "ca_trust", ca_trust_name="ai-sandbox-gateway")
CONST = lab.role_vars("guest", "ca_trust")
BUNDLE = CONST["ca_trust_bundle"]
ENV_KEYS = sorted(CONST["ca_trust_env"])
PROBE_URLS = [lab.render(url) for url in lab.play_vars("vm-baseline.yml")["trust_probe_urls"]]


def host_certificates() -> dict[str, str]:
    """Anchor path -> PEM for every certificate in CA_TRUST_DIR, named as the role names them."""
    return {
        f"{CONST['ca_trust_anchor_dir']}/{PARAMS['ca_trust_name']}-{lab.sha256_fingerprint(pem)[:16]}.pem": pem
        for _, pem in lab.certificates(L.ca_trust_dir)
    }


@pytest.fixture(scope="module")
def anchors() -> dict[str, str]:
    found = host_certificates()
    assert found, f"no certificate in {L.ca_trust_dir}: see make -f lab-bootstrap-verify.mk"
    return found


def test_anchor_set_is_the_host_chain(admin, anchors):
    """One anchor per host certificate, and none left over from an older chain."""
    on_guest = set(admin.check_output("ls -1 %s", CONST["ca_trust_anchor_dir"]).split())
    expected = {path.rsplit("/", 1)[1] for path in anchors}
    ours = {name for name in on_guest if name.startswith(f"{PARAMS['ca_trust_name']}-")}
    assert ours == expected, f"anchors differ: missing {sorted(expected - ours)}, stale {sorted(ours - expected)}: {FIX}"


def test_anchors_hold_the_host_certificates(admin, anchors):
    def squash(pem: str) -> str:
        return "".join(pem.split())  # line endings and wrapping do not matter

    for path, pem in anchors.items():
        assert squash(admin.file(path).content_string) == squash(pem), f"{path} differs from the host's chain: {FIX}"


def test_bundle_trusts_every_anchor(admin, anchors):
    # -partial_chain: an intermediate that is itself an anchor verifies without its root.
    for path in anchors:
        result = admin.run("openssl verify -partial_chain -CAfile %s %s", BUNDLE, path)
        assert result.rc == 0, f"{path} is not trusted through {BUNDLE}: {result.stdout} {result.stderr}: {FIX}"


@pytest.mark.parametrize("path", [CONST["ca_trust_profile_hook"], CONST["ca_trust_environment_d"]])
def test_env_file_points_tools_at_the_bundle(admin, path):
    content = admin.file(path).content_string
    for key in ENV_KEYS:
        assert re.search(rf"(?m)^(export )?{key}=['\"]?{re.escape(BUNDLE)}['\"]?$", content), (
            f"{path} does not set {key}={BUNDLE}: {FIX}"
        )


def test_login_shell_has_the_env(dev):
    """What uv, pip, requests and Node actually see in a dev login."""
    out = dev.check_output("bash -lc %s", "; ".join(f'echo "{k}=${k}"' for k in ENV_KEYS))
    assert sorted(out.splitlines()) == [f"{k}={BUNDLE}" for k in ENV_KEYS], f"dev's login env: {out}: {FIX}"


@pytest.mark.parametrize("url", PROBE_URLS)
def test_url_is_reachable_over_verified_tls(dev, url):
    """As dev, the same probes as the role: curl (system store) and Python's ssl module.

    Each is tried three times, as the role does: a public site occasionally leaves a
    connection unanswered (Envoy's 5 s connect timeout, 503 UF).
    """
    curl = dev.run(
        "curl --head --silent --show-error --output /dev/null --max-time 30 --retry 2 --retry-delay 5 "
        "--retry-all-errors %s", url,
    )
    assert curl.rc == 0, f"curl {url}: {curl.stderr.strip()}"
    for _ in range(3):
        python = dev.run("python3 -c %s %s", CONST["ca_trust_python_probe"], url)
        if python.rc == 0:
            break
    assert python.rc == 0, f"python {url}: {python.stderr.strip()[-300:]}"
