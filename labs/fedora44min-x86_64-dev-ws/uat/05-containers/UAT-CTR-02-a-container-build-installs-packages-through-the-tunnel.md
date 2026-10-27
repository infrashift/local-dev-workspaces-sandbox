---
id: UAT-CTR-02
title: A container build installs Python packages from PyPI through the tunnel
suite: 05-containers
stack: python-stack
features:
- SBX-CTR-02
- SBX-PY-01
personas:
- dev
priority: P2
disruptive: false
automated: none
leaves: ~/uat-py/Containerfile, and the images localhost/uat-py and ghcr.io/astral-sh/uv:python3.14-trixie-slim. UAT-SCAN-01 uses the image.
---

# UAT-CTR-02 A container build installs Python packages from PyPI through the tunnel

## Story

As the developer, I want to build a container image of my project in the sandbox, so that I can test
the image that the pipeline will ship.

## Preconditions

1. UAT-CTR-01 passes.
2. UAT-PY-01 passes. The project `~/uat-py` exists.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py`. Write a `Containerfile` with these three lines: <br>`FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim`<br>`RUN pip install --no-cache-dir httpx`<br>`CMD ["python", "-c", "import httpx; print(httpx.__version__)"]` | The file exists. |
| 2 | dev | Run `podman build -t localhost/uat-py .`. | podman pulls the base image from ghcr.io. Step 2/3 prints `Successfully installed … httpx-…`. The build ends with `Successfully tagged localhost/uat-py:latest`. |
| 3 | dev | Run `podman run --rm localhost/uat-py`. | The httpx version, for example `0.28.1`. |

## Evidence left behind

The `Containerfile` and two images. UAT-SCAN-01 uses `localhost/uat-py`. "After the run" in
`uat/README.md` removes them.

## Notes

`podman build` passes the proxy variables of the login shell into each build step (`--http-proxy`
is on by default), so pip in the build uses the CONNECT tunnel. The tunnel does not open TLS, so the
image's own trust store verifies PyPI.

Behind a TLS-inspecting proxy, a build step that downloads fails until the image trusts the
proxy's CA chain. See the issue
[Container builds on the guest do not trust ZScaler](../../../../.okfw/issues/container-builds-on-the-guest-do-not-trust-zscaler--01a1672ea58d.md).

A Docker Hub base image (`docker.io/library/python`) does not work now. See UAT-CTR-01. The Fedora
image has no Python, and `dnf` in a container uses Fedora's mirror network, whose mirrors are not on
the allow list.
