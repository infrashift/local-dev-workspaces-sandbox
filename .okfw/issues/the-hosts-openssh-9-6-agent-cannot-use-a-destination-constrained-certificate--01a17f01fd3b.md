---
id: "01a17f01-fd3b-7228-b6c9-6dd2b6543822"
title: "The host's OpenSSH 9.6 agent cannot use a destination-constrained certificate"
type: "issue"
tags:
  - "issue"
  - "ssh"
  - "ssh-agent"
  - "openssh"
  - "gateway"
created: "2026-10-27T15:16:39-05:00"
timestamp: "2026-10-27T15:16:39-05:00"
description: "With ssh-add -h constraints, the host's OpenSSH 9.6 ssh-agent refuses to sign a certificate login (unidentified signature), even on one hop, so the sandbox agent's destination constraint was backed out."
x:
  severity: "low"
  priority: "P3"
  state: "open"
  origin: "OpenSSH 9.6 (Ubuntu noble) ssh-agent"
  found: "2026-10-27, adding destination constraints to the sandbox agent"
---

# The host's OpenSSH 9.6 agent cannot use a destination-constrained certificate

**Severity low, P3, open (blocked upstream).** Found 2026-10-27 while adding destination constraints
to the sandbox ssh-agent ([SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md)).

## What happens
1. `ai-sandbox-agent-cert` loaded the egress key and its Vault-signed certificate with
   `ssh-add -H <hop host keys> -h fedora-dev-1 -h "fedora-dev-1>scp-target@upstream-1"`.
2. From the dev session, `scp scp-target@upstream-1` found both identities: the session-bind chain
   matched. upstream-1 accepted the certificate. Then the agent refused the signature:
   `sign_and_send_pubkey: signing failed ... agent refused operation`.
3. A debug agent (`ssh-agent -d`) said why:
   `process_sign_request2: refusing use of destination-constrained key to sign an unidentified signature`.
   It never parsed the request as an SSH userauth. Every hop had been permitted
   (`permitted_by_dest_constraints: allowed for hostname upstream-1`).
4. The same refusal came on a single hop from the host itself (`-h scp-target@upstream-1`, the
   host's own `ssh` 9.6), so neither the guest's OpenSSH 10.2 nor forwarding is the cause. It is
   the 9.6 agent with a certificate.

Note: `-h` needs the first hop on its own (`-h fedora-dev-1`) as well as the `A>B` hop.
Otherwise the forwarded agent lists no identities at all.

## What was kept
Nothing: the constraint, the host-key helper and its tests were backed out, and the agent loads the
key unconstrained, as before. The working parts, for a later attempt:
- `ssh-keyscan -t ed25519,ecdsa,rsa <hop>`, renamed to the hop's name, into a 0600 known-hosts file
  passed with `-H`;
- re-sign when a fresh scan differs, because rebuilt VMs get new host keys;
- when a hop is down, empty the agent rather than load the key unconstrained;
- the check: `echo probe | ssh-keygen -Y sign -n x -f <cert> -` must fail.

## Revisit
When the host has a newer OpenSSH (a later Ubuntu, or a backport). First repeat the one-hop test
with a throwaway `ssh-agent -d`.

## Related
- [SSH Agent Forwarding](/concepts/ssh-agent-forwarding--01a17f01fd23.md)
