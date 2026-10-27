"""The egress allow list end to end on the host: catalog -> Consul K/V -> Envoy's route table.

consul_egress seeds <prefix>/baseline/<category>/<host>:<port> from the
enabled catalog categories (egress-baseline.yml) and prunes the rest; the
operator adds <prefix>/allow/<host>:<port>; consul-template renders both into
the CONNECT tunnel's route table, which Envoy loads live. Gateway hosts are
never tunnelled: they have exact 403 entries instead (concepts/Egress Allow
List in Consul KV).
"""

import gateway_lab as gw
import pytest
from lab import GATEWAY

FIX = f"run {GATEWAY} gateway TAGS=consul"
BASELINE = f"{gw.KV_PREFIX}/baseline/"
ALLOW = f"{gw.KV_PREFIX}/allow/"
# Clouds that serve many tenants: a wildcard under one of them would admit
# anyone's bucket or distribution (egress-baseline.yml's rules).
SHARED_CLOUDS = (
    "amazonaws.com",
    "cloudfront.net",
    "googleapis.com",
    "googleusercontent.com",
    "storage.googleapis.com",
    "azureedge.net",
    "blob.core.windows.net",
    "windows.net",
    "akamaized.net",
    "akamaihd.net",
    "fastly.net",
    "fastlylb.net",
    "cloudflare.net",
    "r2.dev",
    "digitaloceanspaces.com",
)


def kv() -> tuple[set[str], set[str]]:
    """(baseline <category>/<host>:<port>, operator <host>:<port>) as they are in Consul now."""
    keys = gw.kv_keys()
    baseline = {k.removeprefix(BASELINE) for k in keys if k.startswith(BASELINE)}
    allow = {k.removeprefix(ALLOW) for k in keys if k.startswith(ALLOW)}
    return baseline, allow


def tunnel_routes() -> dict[str, list[str]]:
    """virtual host name -> domains of the CONNECT tunnel's loaded (dynamic) route table, in order."""
    dump = gw.envoy().get("/config_dump?resource=dynamic_route_configs").json()
    configs = [c["route_config"] for c in dump["configs"] if c["route_config"]["name"] == "connect_routes"]
    assert configs, f"Envoy has loaded no connect_routes table: {GATEWAY} gateway TAGS=envoy"
    return {vh["name"]: vh["domains"] for vh in configs[0]["virtual_hosts"]}


def test_baseline_in_consul_is_exactly_the_enabled_catalog():
    baseline, _ = kv()
    desired = gw.desired_baseline()
    assert baseline == desired, (
        f"Consul's baseline differs from egress-baseline.yml's enabled categories: "
        f"missing {sorted(desired - baseline)}, stale {sorted(baseline - desired)}: {FIX}"
    )


def test_route_table_is_the_allow_list_minus_gateway_hosts():
    baseline, allow = kv()
    entries = {key.rsplit("/", 1)[1] for key in baseline} | allow
    usable = {e for e in entries if gw.ENTRY_RE.match(e)}
    expected = {e for e in usable if e.rsplit(":", 1)[0] not in gw.GATEWAY_HOSTS}
    routes = tunnel_routes()
    loaded = set(routes.get("allow", []))
    assert loaded == expected, (
        f"Envoy's tunnel allows {len(loaded)} entries, Consul holds {len(expected)}: "
        f"not loaded {sorted(expected - loaded)}, extra {sorted(loaded - expected)}: "
        "journalctl -u ai-sandbox-consul-template -u envoy"
    )


def test_gateway_hosts_are_denied_on_every_tunnel_port():
    baseline, allow = kv()
    ports = {e.rsplit(":", 1)[1] for e in {k.rsplit("/", 1)[1] for k in baseline} | allow if gw.ENTRY_RE.match(e)}
    routes = tunnel_routes()
    expected = {f"{host}:{port}" for host in gw.GATEWAY_HOSTS for port in ports}
    assert set(routes.get("gateway_hosts", [])) == expected, (
        f"the tunnel's exact gateway-host denials are {routes.get('gateway_hosts')}, expected {sorted(expected)}: "
        "a wildcard could tunnel around the surrogate swap"
    )


def test_everything_else_is_denied():
    routes = tunnel_routes()
    assert list(routes)[-1] == "deny" and routes["deny"] == ["*"], (
        f"the tunnel's last virtual host is {list(routes)[-1]} {routes[list(routes)[-1]]}, expected deny ['*']"
    )


def test_envoy_accepted_every_route_table_update():
    stats = gw.envoy_stats("http.connect_tunnel.rds.connect_routes.")
    prefix = "http.connect_tunnel.rds.connect_routes."
    assert int(stats.get(prefix + "update_success", 0)) >= 1, "Envoy has loaded no route table update"
    assert int(stats.get(prefix + "update_rejected", 0)) == 0, (
        "Envoy rejected a rendered route table (it keeps the last good one): journalctl -u envoy"
    )


@pytest.mark.parametrize(
    ("category", "entry"), gw.catalog_entries(), ids=[f"{c}/{e['host']}" for c, e in gw.catalog_entries()]
)
def test_catalog_entry_is_well_formed(category, entry):
    name = f"{entry['host']}:{entry.get('port', 443)}"
    assert gw.ENTRY_RE.match(name), f"{category}/{name} is not <host>:<port>; the template would skip it"
    assert entry.get("reason"), f"{category}/{name} has no reason"
    assert str(entry.get("probe", "")).startswith("https://"), f"{category}/{name} has no https:// probe URL"
    assert entry["host"] not in gw.GATEWAY_HOSTS, (
        f"{category}/{name} is a gateway host; tunnelling it would bypass the surrogate swap"
    )
    if entry["host"].startswith("*."):
        suffix = entry["host"][2:]
        assert not any(suffix == cloud or suffix.endswith("." + cloud) for cloud in SHARED_CLOUDS), (
            f"{category}/{name} wildcards a shared cloud; name the vendor's own host instead"
        )
        assert suffix.count(".") >= 2, f"{category}/{name} wildcards a whole registrable domain"


@pytest.mark.parametrize(("category", "entry"), gw.catalog_entries(), ids=[e["host"] for _, e in gw.catalog_entries()])
def test_catalog_entry_is_not_under_a_gateway_host(category, entry):
    """The guests' NO_PROXY names every gateway host, and curl, Python and Go match it as a domain suffix.

    A catalog host under one (codeload.github.com under github.com) would skip the tunnel,
    go direct and fail: the sandbox has no DNS. Make it a gateway route instead.
    """
    host = entry["host"].removeprefix("*.")
    under = [g for g in gw.GATEWAY_HOSTS if host.endswith("." + g)]
    assert not under, f"{category}/{entry['host']} is under the gateway host(s) {under}: make it a route in vars/gateway.yml"
