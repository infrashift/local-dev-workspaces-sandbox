---
id: UAT-EDIT-04
title: The editor shows ansible-lint's findings in a playbook
suite: 03-python-editing
stack: python-stack
features:
- SBX-EDIT-04
personas:
- dev
priority: P3
disruptive: false
automated: none
leaves: Nothing, if step 4 is done.
---

# UAT-EDIT-04 The editor shows ansible-lint's findings in a playbook

## Story

As the developer, I want ansible-lint's findings in the editor when I edit a playbook, so that I fix
them before the lint step of the pipeline does.

## Preconditions

1. UAT-SESS-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `mkdir -p ~/uat-ansible/playbooks`. In the left pane, run `:e ~/uat-ansible/playbooks/demo.yml`. Type this and save with `:w`: <br>`---`<br>`- hosts: localhost`<br>`  tasks:`<br>`    - command: echo hi` | `:set filetype?` gives `filetype=yaml.ansible`. |
| 2 | dev | Wait a few seconds. | ansible-lint findings show: on line 2, `name[play]` (All plays should be named). On line 4, `fqcn[action-core]`, `name[missing]` and `no-changed-when`. |
| 3 | dev | Change the file to a named play and a named task that uses `ansible.builtin.command` with `changed_when: false`. Save. | The findings go away. |
| 4 | dev | Run `:bd`. In the right pane, run `rm -r ~/uat-ansible`. | The directory is gone. |

## Evidence left behind

None.

## Notes

The filetype `yaml.ansible` applies to YAML files under `playbooks/`, under `roles/*/tasks/` or
`roles/*/handlers/`, under `tasks/`, and to `site.yml`. Other YAML files get `yaml` and no
ansible-lint findings.

No YAML or Ansible language server is installed: they are npm packages and the stack has no Node.
The findings come from nvim-lint, which runs `ansible-lint` from the ansible_tools role.
