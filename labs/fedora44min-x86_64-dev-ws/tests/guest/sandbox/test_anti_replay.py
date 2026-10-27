"""Surrogates are bound to their hosts and repositories: anywhere else the gateway refuses them itself.

Each surrogate is presented to a gateway host outside its target_hosts (403
"surrogate host mismatch"); each repository's git and api surrogates to
ANOTHER repository's path on github.com, api.github.com and
raw.githubusercontent.com (403 "surrogate repository mismatch"); and
credentials Vault has no record of, including one shaped like a real PAT, get
403 "unknown or revoked surrogate". Envoy answers before any upstream sees the
request.
"""

import lab
import pytest
import sandbox_lab as sb

GATEWAY_HOSTS = set(sb.GATEWAY_HOSTS)


def presentation(name: str) -> list[str]:
    surrogate = sb.SURROGATES[name]
    if surrogate["scheme"] == "basic":
        return ["--user", surrogate["credential"]]
    if surrogate["scheme"] == "bearer":
        return ["--header", sb.bearer(name)]
    return ["--header", f"x-api-key: {surrogate['credential']}"]


# One host each surrogate is NOT bound to.
MISMATCHES = [
    (name, min(GATEWAY_HOSTS - set(spec["target_hosts"]))) for name, spec in sorted(sb.SURROGATES.items())
]


@pytest.mark.parametrize(("name", "host"), MISMATCHES, ids=[f"{n}@{h}" for n, h in MISMATCHES])
def test_surrogate_is_refused_off_its_hosts(dev, name, host):
    status, body = sb.curl(dev, f"https://{host}/", *presentation(name))
    assert (status, sb.GATEWAY_SAYS + "surrogate host mismatch" in body) == (403, True), (
        f"the {name} surrogate on {host} (bound to {sb.SURROGATES[name]['target_hosts']}): {status} {body[:200]}"
    )


@pytest.mark.parametrize(
    "credential",
    ["surrogate-nobody-issued", "github_pat_11ABCDEFG0aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789abcdefghijklmnopqrstu"],
    ids=["unknown", "real-looking"],
)
def test_unknown_credential_is_refused(dev, credential):
    status, body = sb.curl(dev, "https://api.github.com/user", "--header", f"Authorization: Bearer {credential}")
    assert (status, sb.GATEWAY_SAYS + "unknown or revoked surrogate" in body) == (403, True), (
        f"an unknown bearer token on api.github.com: {status} {body[:200]}"
    )


def other_repo(repo_key: str) -> str:
    """Another repository of github_repos (the next one, round the list)."""
    keys = sorted(sb.REPOS)
    return sb.REPOS[keys[(keys.index(repo_key) + 1) % len(keys)]]["repo"]


@pytest.mark.parametrize(
    ("use", "url"),
    [
        ("git", "https://github.com/{other}.git/info/refs?service=git-upload-pack"),
        ("git", "https://api.github.com/repos/{other}"),
        ("api", "https://api.github.com/repos/{other}/commits"),
        ("api", "https://raw.githubusercontent.com/{other}/HEAD/README.md"),
    ],
    ids=["git@github.com", "git@api", "api@api", "api@raw"],
)
def test_surrogate_is_refused_on_another_repository(dev, repo_key, use, url):
    if len(sb.REPOS) < 2:
        pytest.skip("one repository in github_repos: nothing to replay across")
    name = sb.surrogate(repo_key, use)
    status, body = sb.curl(dev, url.format(other=other_repo(repo_key)), *presentation(name))
    assert (status, sb.GATEWAY_SAYS + "surrogate repository mismatch" in body) == (403, True), (
        f"{name} (bound to {sb.SURROGATES[name]['repo']}) on {url.format(other=other_repo(repo_key))}: "
        f"{status} {body[:200]}"
    )


@pytest.mark.parametrize(
    ("use", "url"),
    [
        ("git", "https://github.com/{own}/../../{other}.git/info/refs?service=git-upload-pack"),
        ("git", "https://github.com//{other}.git/info/refs?service=git-upload-pack"),
        ("api", "https://api.github.com/repos/{own}/../../{other}/commits"),
    ],
    ids=["dot-segments@github.com", "double-slash@github.com", "dot-segments@api"],
)
def test_path_tricks_cannot_hide_another_repository(dev, repo_key, use, url):
    """Envoy normalizes the path before the filter reads it, so the repository it checks is the one the upstream serves.

    --path-as-is: curl would otherwise resolve the dot segments itself.
    """
    if len(sb.REPOS) < 2:
        pytest.skip("one repository in github_repos: nothing to replay across")
    name = sb.surrogate(repo_key, use)
    target = url.format(own=sb.REPOS[repo_key]["repo"], other=other_repo(repo_key))
    status, body = sb.curl(dev, target, "--path-as-is", *presentation(name))
    assert (status, sb.GATEWAY_SAYS + "surrogate repository mismatch" in body) == (403, True), (
        f"{name} (bound to {sb.SURROGATES[name]['repo']}) on {target}: {status} {body[:200]}"
    )


def test_a_burst_past_the_bucket_is_refused(dev):
    """Each gateway host has a token bucket ahead of the surrogate filter (envoy_gateway_rate_limit).

    The self-hosted MCP route needs a credential, so these credential-less requests
    end at the gateway (401) or its bucket (429): none reaches an upstream or Vault.
    """
    limit = lab.role_vars("gateway", "envoy_gateway")["envoy_gateway_rate_limit"]
    count = limit["burst"] + 2 * limit["per_second"] + 50
    url = f"https://{sb.UPSTREAM_ROUTE['host']}/[1-{count}]"
    result = sb.login(
        dev, f"curl --silent --parallel --parallel-max 100 --max-time 60 --output /dev/null --write-out '%{{http_code}}\\n' '{url}'"
    )
    codes = result.stdout.split()
    assert len(codes) == count, f"curl made {len(codes)} of {count} requests: {result.stderr[:200]}"
    assert set(codes) <= {"401", "429"}, f"unexpected answers {sorted(set(codes))} from {sb.UPSTREAM_ROUTE['host']}"
    assert "429" in codes, f"{count} requests in a burst to {sb.UPSTREAM_ROUTE['host']} all passed the {limit} rate limit"
