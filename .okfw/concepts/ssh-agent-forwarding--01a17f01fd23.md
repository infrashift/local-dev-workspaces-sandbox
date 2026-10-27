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
- **The certificate comes from Vault's SSH CA** (`ssh-sandbox/sign/scp-target`). It is good for
  principal `scp-target` only, for 8 h, and allows no extensions except `permit-pty`.
  `ai-sandbox-agent-cert` (`make -f lab-gateway.mk agent-cert`) signs it with the operator token,
  over Vault's unix socket, and loads key and certificate with the same lifetime.
- **Only the dev session forwards it** (`lab_ssh`: `ForwardAgent yes` and `IdentityAgent` the
  sandbox socket, for `local.<lab>.dev` alone). Inside the guest, `scp` goes through the CONNECT
  tunnel (`ProxyCommand ncat`, which needs an allow-list entry for the target's `:22`). The agent on
  the host signs the challenge, and the guest never reads the key.
- **The target, upstream-1, trusts only the CA** (`upstream_ssh_target`: `TrustedUserCAKeys`, for
  user `scp-target`).

## What the guest can still do
While a dev session is open, the guest can ask the agent for *any* signature with the egress key:
- an SSH authentication to any host that trusts the CA or the key (today only upstream-1, and only
  as `scp-target`);
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
