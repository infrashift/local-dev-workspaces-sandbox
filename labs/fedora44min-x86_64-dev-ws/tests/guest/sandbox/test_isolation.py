"""The sandbox's boundary: no way out but the gateway, and no real secret inside.

The gateway's names resolve to the gateway, the CONNECT tunnel refuses them
(a tunnel would bypass the surrogate swap), nothing is reachable directly, and
the guest holds the surrogates of vars/gateway.yml and nothing that looks like
a real GitHub or Anthropic credential.
"""

import lab
import pytest
import sandbox_lab as sb
from lab import PROVISION

L = lab.lab()
# What real credentials look like; a surrogate never does.
REAL_CREDENTIAL = r"github_pat_[A-Za-z0-9_]{40,}|gh[pousr]_[A-Za-z0-9]{36}|sk-ant-(api|admin)[0-9]{2}-[A-Za-z0-9_-]{20,}"


@pytest.mark.parametrize("host", sb.GATEWAY_HOSTS)
def test_gateway_host_resolves_to_the_gateway(dev, host):
    resolved = dev.check_output("getent hosts %s", host).split()[0]
    assert resolved == L.gateway_ip, f"{host} resolves to {resolved}, not the gateway: run {PROVISION} ansible"


@pytest.mark.parametrize("host", sb.GATEWAY_HOSTS)
def test_tunnel_refuses_a_gateway_host(dev, host):
    """Even an allow-list entry could not open a tunnel past the surrogate swap.

    --noproxy '': the login shell's NO_PROXY names every gateway host, so curl would
    otherwise go straight to the TLS gateway and never ask the tunnel.
    """
    result = sb.login(
        dev, f"curl --silent --show-error --max-time 30 --noproxy '' --proxy {L.proxy_url} https://{host}/ -o /dev/null"
    )
    assert result.rc != 0, f"the CONNECT tunnel opened {host}:443, bypassing the TLS gateway"


def test_nothing_is_reachable_directly(dev):
    result = dev.run("curl --silent --show-error --noproxy '*' --max-time 5 https://1.1.1.1/ -o /dev/null")
    assert result.rc != 0, "the sandbox reached 1.1.1.1 without the gateway: check the isolated network"


def test_guest_holds_exactly_the_surrogates(dev):
    """~/.bashrc.d's AI_SANDBOX_<NAME>_SURROGATE variables, in a login shell."""
    names = sorted(sb.SURROGATES)
    out = sb.login(dev, "; ".join(f'echo "$AI_SANDBOX_{n.upper()}_SURROGATE"' for n in names)).stdout.splitlines()
    assert out == [sb.SURROGATES[n]["credential"] for n in names], (
        f"dev's surrogates differ from vars/gateway.yml: run {PROVISION} play PLAYBOOK=python-stack"
    )


def test_no_real_credential_on_the_guest(admin):
    """Nothing in a home, /etc, /root or a temp directory looks like a real PAT or API key."""
    result = admin.run("sudo grep -rIlE %s /home /root /etc /tmp /var/tmp", REAL_CREDENTIAL)
    assert result.rc == 1, f"files that hold what looks like a real credential: {result.stdout.split()}"


@pytest.mark.parametrize("port", ["proxy_port", "gateway_port"])
def test_gateway_refuses_a_machine_beside_the_sandbox(upstream_vm, upstream_admin, port):
    """Only the sandbox network reaches the gateway.

    Linux accepts a packet for the gateway address on any interface (the weak host model), and the
    surrogates are published, so a neighbour that reached Envoy would get the real credentials swapped
    in. The host firewall refuses the connection itself; Envoy's filter chains (tests/gateway) would
    close it too.
    """
    target = f"{L.gateway_ip}:{getattr(L, port)}"
    result = upstream_admin.run("timeout 5 bash -c 'exec 3<>/dev/tcp/%s/%s' 2>&1", L.gateway_ip, str(getattr(L, port)))
    assert result.rc != 0, f"{upstream_vm} opened {target}: the gateway answers outside the sandbox network"
