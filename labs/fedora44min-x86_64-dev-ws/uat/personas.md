# Personas

A persona is a role in the lab, not a named person. One tester can do the steps of all the
personas. Do each step as the persona that it names, in the place that the table gives.

| Persona | Who | Where and how |
|---|---|---|
| operator | The person who owns the host and the gateway. Runs every `make` target. | A shell on the host, in the lab directory `labs/fedora44min-x86_64-dev-ws`. |
| dev | The developer. The account `dev` on the sandbox VM `fedora-dev-1`. Holds the surrogate credentials only. | `make -f lab-provision.mk ssh` from the lab directory. |
| admin | The account with sudo on the lab VMs. | `make -f lab-provision.mk ssh ROLE=admin` from the lab directory. |
| claude | Claude Code, the AI agent. Runs as `dev` on the sandbox VM. | `claude` in the shell pane of dev's tmux session. The tester types the prompts. |
| auditor | The person who reviews access to the real credentials. Reads Vault's audit log. | A shell on the host, with sudo. |

## Notes

- The dev session forwards the sandbox ssh-agent to the guest. The admin session does not. See
  [SSH Agent Forwarding](../../../.okfw/concepts/ssh-agent-forwarding--01a17f01fd23.md).
- The claude persona has the permissions of `dev`. It holds the same surrogates and nothing more.
- The operator and the auditor can be the same person. The auditor steps are separate so that a
  review of access is a step of its own.
