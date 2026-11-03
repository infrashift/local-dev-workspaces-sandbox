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
| 1 | operator | Run `make -f lab-gateway.mk allow-list`. | Columns: the entry (`host:port`), the kind (`https`, `tcp`, `ssh:<user>`), the source, a state (blank when in step, `until <date>`, `drift: ...`, `expired ...`) and the reason. The last line gives the number of entries. |
| 2 | operator | Run `make -f lab-gateway.mk allow-list \| grep baseline:python`. | `pypi.org:443`, `files.pythonhosted.org:443`, `astral.sh:443` and the other entries of the `python` category, each with its reason. |
| 3 | operator | Run `make -f lab-gateway.mk allow-list \| awk '{print $3}' \| sort \| uniq -c`. | One count for each `baseline:<category>` of `ansible/vars/egress-baseline.yml`, and one for `operator`. |
| 4 | operator | Run `make -f lab-gateway.mk allow-list \| grep -w operator`. | Only the entries of `ansible/vars/egress-allow.yml`, each with its reason: `192.168.151.10:22  ssh:scp-target  operator  scenario 4: scp to upstream-1`. |
| 5 | operator | Run `make -f lab-gateway.mk allow-list \| grep -E '^(github\.com\|api\.github\.com\|api\.anthropic\.com):'`. | Nothing. A gateway host is never on the list. |
| 6 | operator | Run `make -f lab-gateway.mk allow-plan`. | `Consul's allow list matches the file.` |
| 7 | operator | Run `make -f lab-gateway.mk denied SINCE=7d`. | The CONNECTs the tunnel refused, by `host:port` with a count; gateway hosts are marked. Each line is a candidate for `allow`, or a sign that a client skipped the TLS gateway. |

## Evidence left behind

None.

## Notes

The baseline entries come from `ansible/vars/egress-baseline.yml`. To change them, edit that file and
run `make -f lab-gateway.mk`. The operator entries come from `ansible/vars/egress-allow.yml`, in Git:
`git log -p ansible/vars/egress-allow.yml` shows who added what, and why. A `drift` state means Consul
and the file disagree (a key written by hand, or a file pulled but not synced): `make -f
lab-gateway.mk allow-plan` shows the difference and `allow-sync` resolves it in favour of the file.
