---
id: UAT-EGR-03
title: The operator reviews the allow list, with the source and the reason of each entry
suite: 08-egress
stack: python-stack
features:
- SBX-EGR-02
personas:
- operator
priority: P2
disruptive: false
automated: tests/gateway/test_operator_cli.py::test_list_shows_the_whole_allow_list
leaves: Nothing. The scenario only reads the list.
---

# UAT-EGR-03 The operator reviews the allow list, with the source and the reason of each entry

## Story

As the operator, I want one list of every site the sandbox can reach, with where each entry came from
and why, so that I can review the list and remove what is no longer needed.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-gateway.mk allowlist`. | Three columns: the entry (`host:port`), the source and the reason. The last line gives the number of entries. |
| 2 | operator | Run `make -f lab-gateway.mk allowlist \| grep baseline:python`. | `pypi.org:443`, `files.pythonhosted.org:443`, `astral.sh:443` and the other entries of the `python` category, each with its reason. |
| 3 | operator | Run `make -f lab-gateway.mk allowlist \| awk '{print $2}' \| sort \| uniq -c`. | One count for each `baseline:<category>` of `ansible/vars/egress-baseline.yml`, and one for `operator`. |
| 4 | operator | Run `make -f lab-gateway.mk allowlist \| grep -w operator`. | Only the entries that an operator added, each with its reason. After UAT-SSH-01, `192.168.151.10:22  operator  scenario 4: scp to upstream-1`. |
| 5 | operator | Run `make -f lab-gateway.mk allowlist \| grep -E '^(github\.com\|api\.github\.com\|api\.anthropic\.com):'`. | Nothing. A gateway host is never in the baseline. |

## Evidence left behind

None.

## Notes

The baseline entries come from `ansible/vars/egress-baseline.yml`. To change them, edit that file and
run `make -f lab-gateway.mk`. The operator entries are not in Git. This list is the only record of
them, with their reason and the date they were added.
