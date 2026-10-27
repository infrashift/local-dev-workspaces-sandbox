---
id: UAT-PY-01
title: The developer starts a uv project and adds a dependency from PyPI
suite: 04-python-project
stack: python-stack
features:
- SBX-PY-01
- SBX-PY-02
personas:
- dev
priority: P1
disruptive: false
automated: tests/guest/sandbox/test_scenarios.py::test_pip_installs_through_the_tunnel
leaves: The project ~/uat-py on fedora-dev-1. Later tests use it. See "After the run" in uat/README.md.
---

# UAT-PY-01 The developer starts a uv project and adds a dependency from PyPI

## Story

As the developer, I want to start a Python project and add packages from PyPI with uv, so that I
work in the sandbox as I would on my own machine.

## Preconditions

1. UAT-SESS-01 passes.
2. `~/uat-py` does not exist on fedora-dev-1.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~ && uv init --app uat-py && cd uat-py`. | `Initialized project uat-py at /home/dev/uat-py`. The directory holds `pyproject.toml`, `README.md`, `.python-version`, `src/` and a new git repository. |
| 2 | dev | Run `grep requires-python pyproject.toml`. | `requires-python = ">=3.14"`. uv uses Fedora's Python 3.14 and downloads no interpreter. |
| 3 | dev | Run `uv add httpx`. | uv resolves and installs `httpx` and its dependencies (`anyio`, `certifi`, `h11`, `httpcore`, `idna`). No proxy or certificate error. |
| 4 | dev | Run `uv run python -c 'import httpx; print(httpx.__version__)'`. | The version that `uv add` installed, for example `0.28.1`. |
| 5 | dev | Run `uv run uat-py`. | `Hello from uat-py!`. |
| 6 | dev | Run `python3 -m pip download --no-deps --dest /tmp/uat-pip six && rm -r /tmp/uat-pip`. | pip downloads `six` too. pip and uv both use the proxy settings of the login shell. |
| 7 | dev | Run `grep -c '^name = ' uv.lock`. | A number of six or more: `uv.lock` records each package. |

## Evidence left behind

The project `~/uat-py` with its `.venv` and `uv.lock`.

## Notes

The packages come from `pypi.org` and `files.pythonhosted.org` through the CONNECT tunnel. Both are in
the `python` category of the egress catalog. The tunnel does not open TLS, so the packages are
verified against PyPI's own certificates.

The automated test runs a pip dry run of one package. It does not run uv or make a project.
