---
id: UAT-LIFE-05
title: The operator deletes the lab and makes it again from the code, and all the verify suites pass
suite: 01-lab-lifecycle
stack: python-stack
features:
- SBX-LIFE-04
personas:
- operator
priority: P3
disruptive: true
automated:
- tests/guest/baseline
- tests/guest/python-stack
- tests/guest/sandbox
leaves: New lab VMs. Everything on the old VMs is gone. The base images and the gateway stay.
---

# UAT-LIFE-05 The operator deletes the lab and makes it again from the code, and all the verify suites pass

## Story

As the operator, I want to delete the lab and make it again from the code alone, so that a broken
or doubtful VM is never worth repairing by hand.

## Preconditions

1. UAT-LIFE-04 passes.
2. No one else uses the lab now. The developer has pushed or copied all work off the VMs: this test
   deletes them.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | operator | Run `make -f lab-provision.mk destroy`. Read the plan. Type `yes`. | Terraform destroys the VMs, their disks and their seed images. |
| 2 | operator | Run `make -f lab-provision.mk status`. | Both VMs are `not created`. |
| 3 | operator | Run `ls /var/lib/ai-sandbox/images`. | The Fedora base image is still there. |
| 4 | operator | Run `make -f lab-provision.mk apply`. Read the plan. Type `yes`. | Terraform makes the VMs, waits for SSH and applies `site.yml`. It ends with `Apply complete!`. |
| 5 | operator | Run `make -f lab-provision.mk play PLAYBOOK=python-stack`. Read the dry run. Type `yes`. | The playbook ends with `failed=0` for each host. |
| 6 | operator | Run `make -f lab-provision-verify.mk STACK=python-stack`. | All the tests pass. |
| 7 | operator | Run `make -f lab-gateway.mk agent-cert`, then `make -f lab-provision-verify.mk STACK=sandbox`. | All the tests pass. |
| 8 | operator | Run `make -f lab-provision.mk ssh`. | The session opens with no host-key warning, although the VM's host key is new. |

## Evidence left behind

New lab VMs. dev's home directory is empty except for what the playbooks write.

## Notes

The operator's allow-list entries in Consul stay: they belong to the gateway, not to the lab.

Step 8 passes because the lab's ssh configuration does not keep host keys (`UserKnownHostsFile
/dev/null`). The lab VMs are disposable.

The time for steps 4 to 7 is a useful number for the run record.
