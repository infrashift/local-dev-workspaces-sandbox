---
id: UAT-SCAN-02
title: grype downloads its database and scans the SBOM for known vulnerabilities
suite: 05-containers
stack: python-stack
features:
- SBX-SCAN-02
- SBX-EGR-02
personas:
- operator
- dev
priority: P2
disruptive: false
automated: none
leaves: grype's database in ~/.cache/grype. The operator's allow-list entry is removed in step 6.
---

# UAT-SCAN-02 grype downloads its database and scans the SBOM for known vulnerabilities

## Story

As the developer, I want to scan my image for known vulnerabilities before I push it, so that I fix
them before review and not after release.

## Preconditions

1. UAT-SCAN-01 passes. `~/uat-py/sbom.spdx.json` exists.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `cd ~/uat-py && grype db update`. | **Known gap:** the download fails with `Get "https://grype.anchore.io/databases/v6/latest.json": Forbidden`. The host is not on the allow list. Go on with step 2. |
| 2 | operator | Run `make -f lab-gateway.mk allow HOST=grype.anchore.io:443 REASON="UAT-SCAN-02: grype database"`. | `Allowed grype.anchore.io:443 (Envoy picks it up within seconds)`. |
| 3 | dev | Run `grype db update`. | grype downloads and installs the database. |
| 4 | dev | Run `grype sbom:sbom.spdx.json`. | A table of vulnerabilities (NAME, INSTALLED, FIXED IN, TYPE, VULNERABILITY, SEVERITY), or `No vulnerabilities found`. No error. |
| 5 | dev | Run `grype sbom:sbom.spdx.json --fail-on critical; echo $?`. | `0` if the table has no Critical entry, otherwise `1`. |
| 6 | operator | Run `make -f lab-gateway.mk deny HOST=grype.anchore.io:443`. | `Removed grype.anchore.io:443`. |

## Evidence left behind

grype's database in `~/.cache/grype/db`. A later scan uses it until it is too old. Then grype must
download it again and needs the entry from step 2 again.

## Notes

The test passes when steps 3 to 5 pass. Step 1 records the gap: the egress catalog has no entry for
grype's database, so grype cannot work in the sandbox without an operator entry. See the issue
[grype cannot download its vulnerability database in the sandbox](../../../../.okfw/issues/grype-cannot-download-its-vulnerability-database-in-the-sandbox--01a17f21b820.md).
When the catalog has the entry, delete steps 1, 2 and 6.

grype's database moves from time to time. If step 3 names a different host, allow that host and
record it in the issue.
