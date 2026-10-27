"""Envoy: the pinned build, live, listening only where the sandbox reaches it.

Its two listeners sit on the sandbox bridge's host address (GATEWAY_IP): the
CONNECT tunnel on PROXY_PORT and the TLS gateway on GATEWAY_PORT. The admin
API, which can rewrite Envoy at runtime (and raise the log level until the
router logs the injected credentials), is a unix socket only envoy opens; the
operator reads through a GET-only view of it.
"""

import os
import pwd
import socket
import stat

import gateway_lab as gw
import lab
import pytest
from lab import GATEWAY

L = lab.lab()
FIX = f"run {GATEWAY} gateway TAGS=envoy"


@pytest.mark.parametrize("unit", ["envoy", "ai-sandbox-consul-template"])
def test_unit_is_active_and_enabled(unit):
    assert gw.systemctl("is-active", unit) == "active", f"{unit}.service is not active: {FIX}"
    assert gw.systemctl("is-enabled", unit) == "enabled", f"{unit}.service is not enabled at boot: {FIX}"


def test_envoy_is_live_and_the_pinned_build():
    resp = gw.envoy().get("/server_info")
    assert resp.status == 200, f"Envoy's read-only admin view {gw.ENVOY_ADMIN_READONLY_SOCKET} did not answer: {FIX}"
    info = resp.json()
    assert info["state"] == "LIVE", f"Envoy is {info['state']}, not LIVE: journalctl -u envoy"
    assert f"/{gw.PINS['envoy_version']}/" in info["version"], (
        f"Envoy {info['version']} is running, the pin is {gw.PINS['envoy_version']}: {FIX}"
    )


def test_listeners_are_exactly_the_tunnel_and_the_gateway():
    statuses = gw.envoy().get("/listeners?format=json").json()["listener_statuses"]
    addresses = [s["local_address"] for s in statuses]
    bound = {(a["socket_address"]["address"], a["socket_address"]["port_value"]) for a in addresses if "socket_address" in a}
    expected = {(L.gateway_ip, L.proxy_port), (L.gateway_ip, L.gateway_port)}
    assert bound == expected, f"Envoy listens on {sorted(bound)}, expected {sorted(expected)}: {FIX}"
    pipes = [a["pipe"]["path"] for a in addresses if "pipe" in a]
    assert pipes == [gw.ENVOY_ADMIN_READONLY_SOCKET], f"Envoy's unix-socket listeners are {pipes}: {FIX}"


def test_listeners_serve_only_the_sandbox_network():
    """A connection from outside SANDBOX_CIDR matches no filter chain, even without the host firewall."""
    dump = gw.envoy().get("/config_dump?resource=static_listeners").json()
    for config in dump["configs"]:
        listener = config["listener"]
        if "socket_address" not in listener["address"]:
            continue
        ranges = [
            f"{r['address_prefix']}/{r['prefix_len']}"
            for chain in listener["filter_chains"]
            for r in chain.get("filter_chain_match", {}).get("source_prefix_ranges", [])
        ]
        assert len(ranges) == len(listener["filter_chains"]) and set(ranges) == {L.sandbox_cidr}, (
            f"listener {listener['name']} serves sources {ranges}, expected {L.sandbox_cidr} on every chain: {FIX}"
        )


def test_admin_api_is_off_the_network():
    owner = gw.role_vars("envoy_gateway")["envoy_gateway_user"]
    sock = gw.ENVOY_ADMIN_SOCKET
    info = os.stat(sock)
    assert stat.S_ISSOCK(info.st_mode), f"{sock} is not a socket: {FIX}"
    assert (info.st_uid, stat.S_IMODE(info.st_mode)) == (pwd.getpwnam(owner).pw_uid, 0o600), (
        f"{sock} is uid {info.st_uid} mode {stat.S_IMODE(info.st_mode):o}, expected {owner} 600: {FIX}"
    )
    assert not gw.listeners(9901), "something still listens on Envoy's former admin port :9901"


def test_operator_cannot_open_the_admin_socket():
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(gw.ENVOY_ADMIN_SOCKET)
    except PermissionError:
        return
    finally:
        client.close()
    raise AssertionError(f"the operator could open {gw.ENVOY_ADMIN_SOCKET}: it must be envoy-only")


def test_readonly_admin_view_refuses_changes():
    """Raising the log level would make the router log the injected credentials."""
    resp = gw.envoy().request("POST", "/logging?level=debug")
    assert resp.status == 403, f"POST /logging through {gw.ENVOY_ADMIN_READONLY_SOCKET} answered {resp.status}: {FIX}"


def test_tls_gateway_serves_every_gateway_host():
    """The static route table on GATEWAY_PORT has one virtual host per gateway route."""
    dump = gw.envoy().get("/config_dump?resource=static_route_configs").json()
    domains = {d for c in dump["configs"] for vh in c["route_config"]["virtual_hosts"] for d in vh["domains"]}
    missing = set(gw.GATEWAY_HOSTS) - domains
    assert not missing, f"the TLS gateway has no route for {sorted(missing)} (vars/gateway.yml): {FIX}"


def test_tunnel_resolves_ipv4_only():
    """No tunnel host is cached at an IPv6 address: the host has no IPv6 route, so one would fail with 503 UF."""
    family = gw.role_vars("envoy_gateway")["envoy_gateway_dns_lookup_family"]
    assert family == "V4_ONLY", f"envoy_gateway resolves with {family}, not V4_ONLY"
    clusters = gw.envoy().get("/clusters").body.splitlines()
    ipv6 = sorted({line.split("::")[1] for line in clusters
                   if line.startswith("connect_dynamic_forward_proxy::[") and "::hostname::" in line})
    assert not ipv6, f"the CONNECT tunnel cached IPv6 addresses {ipv6}: {FIX}"


def test_surrogate_filter_has_raised_no_error():
    """A raising Lua script let requests through unswapped before it failed closed; any error is a bug.

    The counter runs since Envoy started: after a fix, the restart that loads it resets it.
    """
    errors = int(gw.envoy_stats("http.tls_gateway.lua.errors").get("http.tls_gateway.lua.errors", "0"))
    assert errors == 0, f"Envoy's surrogate filter raised {errors} time(s): journalctl -u envoy | grep 'script log'"


def tls_gateway_manager() -> dict:
    dump = gw.envoy().get("/config_dump?resource=static_listeners").json()
    listener = next(c["listener"] for c in dump["configs"] if c["listener"]["name"] == "tls_gateway")
    return listener["filter_chains"][0]["filters"][0]["typed_config"]


def test_tls_gateway_normalizes_the_path_before_the_surrogate_filter():
    """The repository check must read the path the upstream serves: no dot segments, no '//'."""
    manager = tls_gateway_manager()
    assert (manager.get("normalize_path"), manager.get("merge_slashes")) == (True, True), (
        f"tls_gateway: normalize_path={manager.get('normalize_path')}, merge_slashes={manager.get('merge_slashes')}: {FIX}"
    )


def test_every_gateway_host_is_rate_limited_before_the_surrogate_filter():
    manager = tls_gateway_manager()
    filters = [f["name"] for f in manager["http_filters"]]
    assert filters.index("envoy.filters.http.local_ratelimit") < filters.index("envoy.filters.http.lua"), (
        f"tls_gateway's filters run {filters}: the rate limit must come before the surrogate filter: {FIX}"
    )
    limit = gw.ENVOY_VARS["envoy_gateway_rate_limit"]
    unlimited = []
    for vhost in manager["route_config"]["virtual_hosts"]:
        if vhost["name"] not in gw.GATEWAY_HOSTS:
            continue
        bucket = vhost.get("typed_per_filter_config", {}).get("envoy.filters.http.local_ratelimit", {}).get("token_bucket", {})
        if (bucket.get("max_tokens"), bucket.get("tokens_per_fill")) != (limit["burst"], limit["per_second"]):
            unlimited.append(vhost["name"])
    assert not unlimited, f"gateway hosts without the {limit} rate limit: {unlimited}: {FIX}"
