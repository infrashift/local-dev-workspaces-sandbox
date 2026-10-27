---
id: UAT-CRED-02
title: The operator rotates a repository's PAT, and the sandbox keeps working with no change on the guest
suite: 10-credentials
stack: python-stack
features:
- SBX-CRED-01
- SBX-GIT-01
personas:
- operator
- dev
priority: P1
disruptive: true
automated: none
leaves: A new PAT for private-scratch-1 in vault.yml and in Vault. The old PAT is revoked on GitHub.
---

# UAT-CRED-02 The operator rotates a repository's PAT, and the sandbox keeps working with no change on the guest

## Story

As the operator, I want to replace a PAT before it expires, or at once after a leak, so that the
sandbox keeps working and no file on the guest changes.

## Preconditions

1. UAT-GIT-01 passes.
2. On GitHub, make a new fine-grained PAT for `infrashift/private-scratch-1` alone: Contents and
   Metadata, read-only (lab README, "Before you start"). Keep the old PAT for now.
3. No one else uses private-scratch-1 in the sandbox now. Between steps 3 and 5 it can fail.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `sha256sum ~/.config/ai-sandbox/git-surrogates ~/.bashrc.d/ai-sandbox-surrogates.sh ~/.claude.json \| tee /tmp/uat-cred-02.sum`. | Three checksums. |
| 2 | operator | Run `make -f lab-gateway.mk secrets NAME=private-scratch-1`. Paste the new PAT at the prompt. The terminal does not show it. | The command encrypts it into `vault.yml`, then runs the gateway playbook for Vault: a dry run, then `Enter a value:`. |
| 3 | operator | Read the dry run. Type `yes`. | The playbook writes the new PAT into Vault, checks that it reads `infrashift/private-scratch-1`, and ends with `failed=0`. |
| 4 | dev | Run `GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/infrashift/private-scratch-1 HEAD`. | A commit SHA and `HEAD`. |
| 5 | operator | On GitHub, revoke the old PAT. | GitHub shows it as revoked. |
| 6 | dev | Do step 4 again. | It still works: the gateway uses the new PAT. |
| 7 | dev | Run `sha256sum -c /tmp/uat-cred-02.sum && rm /tmp/uat-cred-02.sum`. | `OK` three times. No file on the guest changed. |
| 8 | operator | Run `make -f lab-gateway-verify.mk`. | All the tests pass. |

## Evidence left behind

The new PAT in `ansible/inventory-host/host_vars/localhost/vault.yml` and in Vault. The old PAT is
revoked.

## Notes

The surrogate stays the same. Only the record in Vault behind it changes. That is the point of the
surrogate model: see [Gateway Credentials in the Host Inventory](../../../../.okfw/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md).

For the Anthropic key, use `NAME=anthropic` and check with UAT-AI-01 step 4.

If step 3 says that the PAT cannot read the repository, the PAT has the wrong repository or
permissions, or the organisation has not approved it yet. The old PAT is still in use until a good
one is loaded.
