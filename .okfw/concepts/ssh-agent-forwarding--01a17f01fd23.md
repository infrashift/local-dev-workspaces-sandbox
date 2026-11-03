---
id: "01a17f01-fd23-71f8-9f15-2cd534f84bd2"
title: "SSH Agent Forwarding"
type: "concept"
tags:
  - "gateway"
  - "ssh"
  - "ssh-agent"
  - "vault"
  - "scp"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:16:39-05:00"
status: "draft"
description: "How scenario 4 authenticates scp from the sandbox without a key in the guest: a dedicated host ssh-agent with a Vault-signed 8-hour certificate, forwarded into the dev session only; destination constraints were tried and are blocked by the host's OpenSSH 9.6."
---

# SSH Agent Forwarding

How scenario 4 (`scp` from the sandbox to a host on the network) authenticates without any key in
the guest: a dedicated ssh-agent on the host, forwarded into the dev session only.

## How it works
- **`sandbox_ssh_agent`** runs `ai-sandbox-ssh-agent.service`, a user unit of the operator on
  `/run/user/<uid>/ai-sandbox/ssh-agent.sock`, 0700. It is never the operator's own agent. The
  agent holds one key, `~/.ssh/key.d/ai-sandbox.egress`, which never leaves the host, and that
  key's certificate.
- **The certificate comes from Vault's SSH CA** (`ssh-sandbox/sign/sandbox-egress`). It is good for
  the principals named by the `kind: ssh` entries of `vars/egress-allow.yml` (today `scp-target`
  alone), for 8 h, and allows no extensions except `permit-pty`. Until 2026-11-03 the role was
  `ssh-sandbox/roles/scp-target` with the one fixed principal `scp_target_user`. `vault_gateway`
  now prunes any SSH role other than `sandbox-egress`.
  `ai-sandbox-agent-cert` (`make -f lab-gateway.mk agent-cert`) signs it with the operator token,
  over Vault's unix socket, and loads key and certificate with the same lifetime.
- **Only the dev session forwards it** (`lab_ssh`: `ForwardAgent yes` and `IdentityAgent` the
  sandbox socket, for `local.<lab>.dev` alone). Inside the guest, `scp` goes through the CONNECT
  tunnel (`ProxyCommand ncat`, which needs a `kind: ssh` allow entry for the target's `:22`). The agent on
  the host signs the challenge, and the guest never reads the key.
- **The target, upstream-1, trusts only the CA** (`upstream_ssh_target`: `TrustedUserCAKeys`, for
  user `scp-target`).

## Principals from the allow file
`gateway-host.yml` sets `ssh_principals` to the sorted, unique `user`s of the allow file's ssh entries,
and fails when there are none. `vault_gateway` makes them the `sandbox-egress` role's `allowed_users`,
and `sandbox_ssh_agent` signs `valid_principals` with them. The agent re-signs when the certificate's
principals differ from the file, as well as when it nears expiry. The role then records the list in
`OPERATOR_DIR/ssh-principals`. `egress-allowlist.sh principals-drift` compares the file with that
record, so `make -f lab-gateway.mk allow`, `deny` and `allow-sync` re-run the gateway for
`TAGS=vault,ssh_agent` when the users change. Verified live 2026-11-03: adding
`git.example.com:22 USER=git` issued a certificate for `git, scp-target`, and removing it went back to
`scp-target`.

Trade-off (analysis): every ssh user added widens what a process in the guest can ask the forwarded
agent to sign for (below). Add a user for a real target only, and give a temporary one an `expires`
date.

## What the guest can still do
While a dev session is open, the guest can ask the agent for *any* signature with the egress key:
- an SSH authentication to any host that trusts the CA or the key, as any of the certificate's
  principals (today only upstream-1, and only as `scp-target`);
- arbitrary data, `ssh-keygen -Y sign` (verified 2026-10-27).

The certificate's principal and lifetime, and the CA being trusted in one place, are what bound
this.

## Destination constraints: tried, blocked by the host's OpenSSH
OpenSSH 8.9+ can restrict a forwarded key to named hops. With
`ssh-add -h fedora-dev-1 -h "fedora-dev-1>scp-target@upstream-1"`, the agent would sign only that
login and refuse everything else. It was implemented and tested on 2026-10-27, then backed out:
the host's agent, OpenSSH 9.6 (Ubuntu noble), refuses to sign a **certificate** login under any
destination constraint
([issue](/issues/the-hosts-openssh-9-6-agent-cannot-use-a-destination-constrained-certificate--01a17f01fd3b.md)).
Dropping the certificate for a plain authorized key would trade a short-lived, CA-issued credential
for a standing one: a worse bargain. Revisit when the host's OpenSSH is newer. The parts that worked
are kept in the issue note:
- hop host keys from `ssh-keyscan` into a private known-hosts file;
- `-H`;
- one `-h` per hop;
- re-signing when a VM's host key changes.

## Related
- [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)
- [Lab SSH Identities](/concepts/lab-ssh-identities--01a1664337d1.md)
