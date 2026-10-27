"""The optional TLS-inspecting proxy's chain on every lab VM (ca_trust, TLS_INSPECTION_DIR).

vm-baseline.yml applies ca_trust a second time, on the sandbox and on the
upstream fixtures, for the CA chain of a TLS-inspecting proxy (Zscaler, ...)
in front of the host. With a chain, each VM holds exactly its anchors, trusts
them through the system bundle, and really is answered by the proxy. Without
one, none of its anchors is left. See the runbook Run the Lab Behind a
TLS-Inspecting Proxy.
"""

from urllib.parse import urlparse

import lab
import pytest
from lab import PROVISION

L = lab.lab()
FIX = f"run {PROVISION} ansible"
PARAMS = lab.role_params("vm-baseline.yml", "ca_trust", ca_trust_name="ai-sandbox-tls-inspection")
CONST = lab.role_vars("guest", "ca_trust")
ANCHOR_DIR = CONST["ca_trust_anchor_dir"]
BUNDLE = CONST["ca_trust_bundle"]
NAME = PARAMS["ca_trust_name"]
CHAIN = lab.certificates(L.tls_inspection_dir)
ANCHORS = {f"{ANCHOR_DIR}/{NAME}-{lab.sha256_fingerprint(pem)[:16]}.pem": pem for _, pem in CHAIN}
GATEWAY_HOSTS = {route["host"] for route in lab.vars_file("gateway.yml")["gateway_routes"]}

in_use = pytest.mark.skipif(not CHAIN, reason=f"no TLS-inspection chain in {L.tls_inspection_dir}")


def is_sandbox(vm: str) -> bool:
    return vm in lab.dev_ws_vms()


def probe_urls(vm: str) -> list[str]:
    """What ca_trust probed there: the sandbox's tunnel sites, or the upstream fixture's direct ones."""
    urls = [lab.render(url) for url in lab.play_vars("vm-baseline.yml", 0 if is_sandbox(vm) else 1)["trust_probe_urls"]]
    return [url for url in urls if urlparse(url).hostname not in GATEWAY_HOSTS]


def via(vm: str) -> str:
    """curl's route out: the sandbox has only the gateway's CONNECT tunnel."""
    return f"--proxy {L.proxy_url} " if is_sandbox(vm) else ""


def squash(pem: str) -> str:
    return "".join(pem.split())


def test_anchor_set_is_the_chain(lab_vm, lab_vm_admin):
    """Exactly the chain's anchors; none when there is no chain (it was removed, or never used)."""
    on_guest = set(lab_vm_admin.check_output("ls -1 %s", ANCHOR_DIR).split())
    ours = {name for name in on_guest if name.startswith(f"{NAME}-")}
    expected = {path.rsplit("/", 1)[1] for path in ANCHORS}
    assert ours == expected, (
        f"{lab_vm}: {NAME} anchors differ from {L.tls_inspection_dir}: missing {sorted(expected - ours)}, "
        f"stale {sorted(ours - expected)}: {FIX}"
    )


@in_use
def test_anchors_hold_the_chain(lab_vm, lab_vm_admin):
    for path, pem in ANCHORS.items():
        assert squash(lab_vm_admin.file(path).content_string) == squash(pem), f"{lab_vm}: {path} differs: {FIX}"


@in_use
def test_bundle_trusts_every_anchor(lab_vm, lab_vm_admin):
    for path in ANCHORS:
        result = lab_vm_admin.run("openssl verify -partial_chain -CAfile %s %s", BUNDLE, path)
        assert result.rc == 0, f"{lab_vm}: {path} is not trusted through {BUNDLE}: {result.stdout} {FIX}"


@in_use
def test_vm_reaches_its_sites_over_verified_tls(lab_vm, lab_vm_admin):
    for url in probe_urls(lab_vm):
        result = lab_vm_admin.run(
            f"curl {via(lab_vm)}--head --silent --show-error --output /dev/null --max-time 30 %s", url
        )
        assert result.rc == 0, f"{lab_vm}: {url}: {result.stderr.strip()}: {FIX}"


@in_use
def test_the_proxy_really_signs_what_the_vm_reaches(lab_vm, lab_vm_admin):
    """The first probe site verifies with the chain's anchors ALONE: the traffic is inspected by this chain."""
    host = urlparse(probe_urls(lab_vm)[0]).hostname
    proxy = f"-proxy {L.gateway_ip}:{L.proxy_port} " if is_sandbox(lab_vm) else ""
    anchors = " ".join(ANCHORS)
    script = (
        f"openssl s_client {proxy}-connect {host}:443 -servername {host} -brief -partial_chain "
        f"-verify_return_error -CAfile <(cat {anchors}) </dev/null"
    )
    result = lab_vm_admin.run("bash -c %s", script)
    assert result.rc == 0, (
        f"{lab_vm}: {host} does not verify with the {NAME} anchors alone, so the proxy is not signing this "
        f"VM's traffic with that chain: {result.stderr.strip().splitlines()[-1:]}"
    )
