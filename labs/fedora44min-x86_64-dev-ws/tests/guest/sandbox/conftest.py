"""The sandbox suite: the zero-trust gateway end to end, from the sandbox guest.

Run it after the python-stack (which installs Claude Code, the surrogates and
the local GitHub MCP server), with the real credentials loaded:

    make -f lab-gateway.mk secrets
    make -f lab-provision.mk play PLAYBOOK=python-stack
    make -f lab-provision-verify.mk STACK=sandbox

The GitHub tests run once per repository in vars/gateway.yml github_repos,
each with that repository's surrogates. Every test is read-only; the `vm`,
`admin` and `dev` fixtures come from tests/guest/conftest.py.
"""

import json

import pytest
import sandbox_lab as sb


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "repo_key" in metafunc.fixturenames:
        metafunc.parametrize("repo_key", sorted(sb.REPOS), scope="module")


@pytest.fixture(scope="module")
def pat_login(dev, repo_key) -> str:
    """The login GitHub reports for the repository's PAT, asked through the gateway with its api surrogate."""
    status, body = sb.curl(dev, "https://api.github.com/user", "--header", sb.bearer(sb.surrogate(repo_key, "api")))
    assert status == 200, f"api.github.com/user with {repo_key}'s api surrogate: {status} {body[:200]}: {sb.SECRETS}"
    return json.loads(body)["login"]
