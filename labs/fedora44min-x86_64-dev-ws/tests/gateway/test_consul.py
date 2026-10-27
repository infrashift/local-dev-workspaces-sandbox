"""Consul on the host: running, its HTTP API a unix socket only, ACLs default-deny, and the operator's reach.

Consul holds the egress allow list (concepts/Egress Allow List in Consul KV).
Ansible owns <prefix>/baseline/; the operator token may write only
<prefix>/allow/. The write probes use `?cas=1` on a key that does not exist:
a permitted write then changes nothing (Consul answers false), and a refused
one is a 403, so the probes are read-only either way.
"""

import gateway_lab as gw
import pytest
from lab import GATEWAY

FIX = f"run {GATEWAY} gateway TAGS=consul"
OPERATOR_POLICY = gw.role_vars("consul_egress")["consul_egress_operator_policy"]
SOCKET = gw.PINS["consul_socket"]
SOCKET_GROUP = gw.PINS["consul_socket_group"]
# Consul's server RPC and LAN/WAN serf ports, and its DNS: loopback at most.
PORTS = [8300, 8301, 8302, 8600]
# The HTTP API's former TCP port: nothing listens there now.
FORMER_HTTP_PORT = 8500
PROBE_KEY = "zz-ai-sandbox-verify.invalid:443"


def test_unit_is_active_and_enabled():
    assert gw.systemctl("is-active", "consul") == "active", f"consul.service is not active: {FIX}"
    assert gw.systemctl("is-enabled", "consul") == "enabled", f"consul.service is not enabled: {FIX}"


@pytest.mark.parametrize("port", PORTS)
def test_consul_listens_on_loopback_only(port):
    addresses = gw.listeners(port)
    assert addresses <= {"127.0.0.1"}, f"Consul's :{port} is reachable on {sorted(addresses)}, not only 127.0.0.1"


def test_http_api_has_no_tcp_listener():
    addresses = gw.listeners(FORMER_HTTP_PORT)
    assert not addresses, f"something listens on Consul's former HTTP port :{FORMER_HTTP_PORT} ({sorted(addresses)}): {FIX}"


def test_socket_opens_for_its_group_and_the_operator():
    problems = gw.socket_problems(SOCKET, SOCKET_GROUP)
    assert not problems, f"Consul's socket: {'; '.join(problems)}: {FIX}"


def test_anonymous_requests_see_no_keys():
    resp = gw.consul().anonymous().get(f"/v1/kv/{gw.KV_PREFIX}/?keys")
    assert resp.status in (403, 404) and gw.KV_PREFIX not in resp.body, (
        f"an anonymous key listing returned {resp.status}: the ACL default policy is not deny: {FIX}"
    )


def test_anonymous_requests_cannot_write():
    resp = gw.consul().anonymous().request("PUT", f"/v1/kv/{gw.KV_PREFIX}/allow/{PROBE_KEY}?cas=1", b"{}")
    assert resp.status == 403, f"an anonymous allow-list write returned {resp.status}, expected 403: {FIX}"


def test_operator_token_has_only_the_operator_policy():
    resp = gw.consul().get("/v1/acl/token/self")
    assert resp.status == 200, f"the operator token is not valid ({resp.status}): {FIX}"
    policies = [policy["Name"] for policy in resp.json()["Policies"]]
    assert policies == [OPERATOR_POLICY], f"the operator token carries {policies}, expected [{OPERATOR_POLICY}]"


@pytest.mark.parametrize(
    ("subtree", "allowed"), [("allow", True), ("baseline/zz-verify", False)], ids=["allow", "baseline"]
)
def test_operator_may_write_only_the_allow_subtree(subtree, allowed):
    resp = gw.consul().request("PUT", f"/v1/kv/{gw.KV_PREFIX}/{subtree}/{PROBE_KEY}?cas=1", b"{}")
    if allowed:
        assert resp.status == 200, f"the operator cannot write {gw.KV_PREFIX}/{subtree}/ ({resp.status}): {FIX}"
        assert resp.body.strip() == "false", f"the probe {PROBE_KEY} exists in {gw.KV_PREFIX}/{subtree}/: delete it"
    else:
        assert resp.status == 403, (
            f"the operator token can write {gw.KV_PREFIX}/{subtree}/ ({resp.status}); the baseline is Ansible's"
        )
