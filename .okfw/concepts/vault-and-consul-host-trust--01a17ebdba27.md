---
id: "01a17ebd-ba27-7c31-80eb-26225eeb0aab"
title: "Vault and Consul Host Trust"
type: "concept"
tags:
  - "gateway"
  - "vault"
  - "consul"
  - "security"
  - "decision"
  - "threat-model"
created: "2026-10-27T14:02:05-05:00"
timestamp: "2026-10-27T14:02:05-05:00"
status: "draft"
description: "The gateway's threat model on the host (the guest and its neighbours untrusted, root trusted) and why Vault, Consul, Vault Proxy and Envoy talk over permission-guarded unix sockets instead of TLS or mTLS, with when to revisit."
---

# Vault and Consul Host Trust

What the gateway trusts on the host, and why that means **no TLS and no mTLS** between Vault,
Consul, Vault Proxy, consul-template and Envoy (decided 2026-10-27, in the gateway hardening review).

## The threat model
- **The adversary is the sandbox guest.** It runs an AI agent and is assumed compromised. It must
  never hold, read or replay a real credential, and must reach nothing but Envoy's two listeners
  ([Isolated Sandbox Network](/concepts/isolated-sandbox-network--01a17e9c824e.md)).
- **Machines beside the host are adversaries too:** the LAN, upstream-1 and containers. They reach
  nothing of the gateway's.
- **Root on the host is trusted.** The unseal key and the root token sit root-only in
  `/etc/ai-sandbox/vault/`, so that `ai-sandbox-vault-unseal.service` can unseal after every start.
  Whoever is root can read every real credential. This is the lab's deliberate trade-off.
- **Other local users and processes are not trusted with the APIs.** Today that means
  host-network containers and anything not running as the operator. They get no Vault or Consul
  API at all, not even the unauthenticated endpoints (`sys/health`, `sys/unseal`, the SSH CA's
  public key).

## The decision: unix sockets, not TLS
Every hop stays on the host:

| Hop | Transport | Who can open it |
|---|---|---|
| Envoy → Vault Proxy | `/run/vault-proxy/proxy.sock` | group `envoy` (0660). The socket's permissions *are* the access control: Vault Proxy attaches the AppRole token to every request |
| Vault Proxy, operator, Ansible → Vault | `/run/vault/vault.sock` | group `vault-clients` (0660; services join through their units' `SupplementaryGroups`), and the operator by ACL `user:<operator>:rw-` |
| consul-template, operator, Ansible → Consul HTTP | `/run/consul/consul.sock` | group `consul-clients` (0660), and the operator by ACL |
| Envoy admin | `/run/envoy/admin.sock` | `envoy` only (0600); the operator reads a GET-only view |
| Consul server RPC and LAN gossip | `127.0.0.1:8300`, `:8301` | loopback; gossip encrypted (`encrypt.hcl`, key root-only); RPC needs ACL tokens |
| Envoy → upstreams | TLS, verified (SNI and SAN match) | — |

Why sockets beat TLS here:
- **Nothing to sniff.** Reading loopback or a socket takes root, and root is trusted (above).
  Encrypting the hop adds nothing.
- **Access is the kernel's file permissions,** by UID and group. TLS would need client
  certificates for every caller to say *who* may connect, with issuance, distribution and rotation
  for each one. A socket says it with `chmod` and an ACL, and nothing expires.
- **No TCP port means no reach** from host-network containers, other users or a mis-bound
  listener. Tokens are still required on top.
- **Client certificates in the guest would identify the VM, not the workload:** the agent could
  read them. Guest → Envoy stays server-authenticated TLS, and the surrogate is the credential.

### Revisit when
- Vault or Consul moves off this host (a VM, a cluster). Then use TLS with client verification:
  Vault `tls_require_and_verify_client_cert` or cert auth, Consul `tls.defaults.verify_incoming`
  with auto-encrypt. Issue the certificates from a CA of their own, never the gateway CA the guests
  trust.
- More than one sandbox shares the gateway and each needs its own surrogates. Then guest identity
  (per-network listeners, or client certificates) becomes the binding, rather than the transport.

## How the sockets are built
- **Vault has no TCP listener at all.** That rules out raft storage: raft refuses to unseal without
  a TCP cluster address ("cluster addresses not found"). So Vault uses the `file` backend with
  `disable_clustering = true`, which costs a single node nothing. A Vault that had raft data was
  migrated once by `vault_server` (`vault operator migrate`, with Vault stopped). That copies every
  key, so the unseal key and root token stay valid. The raft files stay in
  `/var/lib/vault/raft.migrated/` (barrier-encrypted, vault-only) until someone removes them.
- **Vault's server listener ignores `socket_mode` and `socket_group`**
  ([issue](/issues/the-vault-servers-unix-listener-ignores-socket-mode-and-socket-group--01a17ebdba3a.md)).
  Root's `ExecStartPost=+vault-socket` sets the group, the mode and the operators' ACL once Vault
  is ready.
- **Consul honours `unix_sockets { group, mode }`** (the group as a number). The operators' ACL
  comes from a default ACL on `/run/consul`, which `ExecStartPre=+setfacl` sets. Every entry is
  spelled out (`d:u::rw,d:g::rw,d:o::-`) because a socket inherits the directory's entries, and
  connecting needs write.
- **The operator gets an ACL, not a group,** so the first apply works in the session that ran it:
  a new group membership needs a fresh login. Services use groups through `SupplementaryGroups`,
  which needs no membership in `/etc/group`.

## One principal per service, each sandboxed
- **Each service runs as its own user and holds only its own secret:**
  - `vault` holds the storage;
  - `vault-proxy` holds the AppRole secret_id;
  - `envoy` holds the gateway key and is the Vault Proxy socket's group;
  - `consul-template` holds the Consul read token and writes the route table into
    `/var/lib/envoy/rds` (consul-template's, setgid `envoy`, 2750), which Envoy only reads;
  - `consul` holds its data.

  consul-template used to run as `envoy`, so a bug in it could have read the real credentials
  through Vault Proxy's socket. Now it cannot open that socket, and Envoy cannot open Consul's.
- **Every unit carries systemd's sandboxing:**
  - `ProtectSystem=strict`, `ProtectKernel*`, `ProtectProc=invisible`, `PrivateIPC`;
  - `RestrictNamespaces`, `SystemCallFilter=@system-service`, `CapabilityBoundingSet=` (Envoy keeps
    only `CAP_NET_BIND_SERVICE`), `UMask=0077`;
  - `MemoryDenyWriteExecute` everywhere but Envoy, whose LuaJIT needs W+X;
  - for the services that serve or use only unix sockets: `RestrictAddressFamilies=AF_UNIX` and
    `IPAddressDeny=any`.

  `systemd-analyze security` scored them 4.2–5.5 before and 1.0–1.7 after: vault 1.0, vault-proxy
  1.1, consul 1.4, envoy 1.7, consul-template 1.1. Each role records its unit's score as a ceiling
  (`*_max_exposure`) and asserts it on every real run.

## Checked by
- `tests/gateway/test_vault.py` and `test_consul.py`: nothing listens on the former TCP ports
  (8200/8201, 8500); each socket is its group's 0660 and carries `user:<you>:rw-`;
  `upstream.yml` names the same Vault socket.
- `tests/gateway/test_units.py`: each unit's exposure is at most its ceiling; consul-template is in
  neither `envoy` nor `vault-clients`; Envoy is not in `consul-clients`; the route table directory
  is `consul-template:envoy 2750`.
- `vault_server` and `consul_server` assert the same on every run: no TCP listener owned by
  `vault`, and Consul's TCP limited to 8300/8301.

## Related
- [Operator Interfaces](/concepts/operator-interfaces--01a17ebdba31.md)
- [Envoy's admin API could log the injected credentials](/issues/envoys-admin-api-could-log-the-injected-credentials--01a17e9cd3b8.md)
- [Gateway Credentials in the Host Inventory](/concepts/gateway-credentials-in-the-host-inventory--01a17e133adc.md)
