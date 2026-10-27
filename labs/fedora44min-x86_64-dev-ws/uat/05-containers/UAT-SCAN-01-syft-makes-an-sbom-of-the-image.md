---
id: UAT-SCAN-01
title: syft makes an SBOM of the project's image
suite: 05-containers
stack: python-stack
features:
- SBX-SCAN-01
personas:
- dev
priority: P2
disruptive: false
automated: none
leaves: ~/uat-py/sbom.spdx.json. UAT-SCAN-02 uses it.
---

# UAT-SCAN-01 syft makes an SBOM of the project's image

## Story

As the developer, I want an SBOM of each image I build, so that the security team knows what ships
in it.

## Preconditions

1. UAT-CTR-02 passes. The image `localhost/uat-py` exists.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && SYFT_CHECK_FOR_APP_UPDATE=false syft podman:localhost/uat-py:latest -o spdx-json=sbom.spdx.json`. | syft catalogs the image through dev's podman socket and writes the file. No error. |
| 2 | dev | Run `jq -r '.spdxVersion' sbom.spdx.json`. | `SPDX-2.3`. |
| 3 | dev | Run `jq -r '.packages[].name' sbom.spdx.json \| grep -xE 'httpx\|httpcore\|anyio'`. | `httpx`, `httpcore` and `anyio`, the packages that the build installed. |
| 4 | dev | Run `jq '.packages \| length' sbom.spdx.json`. | More than a thousand: the Debian packages of the base image, and the Python packages. |

## Evidence left behind

`~/uat-py/sbom.spdx.json`.

## Notes

Without `SYFT_CHECK_FOR_APP_UPDATE=false`, syft prints `ERROR failed to fetch latest version: …
toolbox-data.anchore.io … Forbidden`. That host is not on the allow list. The SBOM is correct anyway.
The message looks like a fault and can confuse a developer, so the test turns the check off. To turn
it off for good, set the variable in dev's environment or in `~/.syft.yaml` (`check-for-app-update:
false`).
