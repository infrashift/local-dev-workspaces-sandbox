---
id: UAT-LIFE-02
title: The developer's files survive a stop and start of the lab
suite: 01-lab-lifecycle
stack: python-stack
features:
- SBX-LIFE-01
personas:
- operator
- dev
priority: P1
disruptive: true
automated: none
leaves: The file ~/uat-life-02.txt on fedora-dev-1, unless step 7 removes it.
---

# UAT-LIFE-02 The developer's files survive a stop and start of the lab

## Story

As the operator, I want to stop the lab at the end of the day and start it again the next morning,
so that the host's resources are free overnight and the developer loses no work.

## Preconditions

1. UAT-LIFE-01 passes.
2. No one else uses the lab now. This test stops both lab VMs.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the shell pane, run `date > ~/uat-life-02.txt`. Detach with `Ctrl-b d`. | The ssh session ends. |
| 2 | operator | Run `make -f lab-provision.mk stop`. | The command returns within about one minute for each VM, with no message. |
| 3 | operator | Run `make -f lab-provision.mk status`. | Both VMs are `shut off`, and their IP is `-`. |
| 4 | operator | Run `make -f lab-provision.mk start`. | The command checks the host and the gateway first (they have nothing to change), then starts each VM and waits for its address. It ends with no error. |
| 5 | operator | Run `make -f lab-provision.mk status`. | Both VMs are `running` at their usual addresses. |
| 6 | dev | Connect with `make -f lab-provision.mk ssh`. Run `cat ~/uat-life-02.txt`. | The date from step 1. The tmux session is new: the session from step 1 ended when the VM stopped. |
| 7 | dev | Run `rm ~/uat-life-02.txt`. Detach. | The file is gone. |

## Evidence left behind

None, if step 7 is done.

## Notes

`stop` sends an ACPI shutdown and waits up to 60 seconds. If a VM ignores it, the command prints
`<vm> ignored ACPI; destroying` and turns the VM off. That is a fail for this test: the guest did not
shut down cleanly.

`start` stops with `Host not ready` or `Gateway not ready` if the host or the gateway has pending
changes. Run the command that the message gives, then do step 4 again.

`start` and `stop` use virsh, not Terraform, so the Terraform state does not change.
