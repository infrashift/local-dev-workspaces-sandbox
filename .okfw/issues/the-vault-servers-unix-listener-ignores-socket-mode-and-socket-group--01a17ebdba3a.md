---
id: "01a17ebd-ba3a-7ae2-ad0d-4082768139cd"
title: "The Vault server's unix listener ignores socket_mode and socket_group"
type: "issue"
tags:
  - "issue"
  - "vault"
  - "gateway"
  - "unix-socket"
created: "2026-10-27T14:02:05-05:00"
timestamp: "2026-10-27T14:02:05-05:00"
description: "Vault 2.2.1's server unix listener ignores socket_mode/socket_group (only Agent and Proxy apply them), so its socket came out vault:vault 0640 and the operator got EACCES; root's ExecStartPost now sets the group, mode and ACL."
x:
  severity: "medium"
  priority: "P2"
  state: "worked-around"
  origin: "Vault 2.2.1 server behaviour"
  found: "2026-10-27, moving Vault onto a unix socket"
---

# The Vault server's unix listener ignores socket_mode and socket_group

**Severity medium, P2, worked around.** Found 2026-10-27 while moving Vault onto a unix socket
([Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)).

## What happens
1. Vault's `listener "unix"` documents `socket_mode`, `socket_user` and `socket_group`, but the
   Vault *server* (2.2.1) ignores them. Only Vault Agent and Vault Proxy apply them; this lab's Vault
   Proxy socket does get `vault-proxy:envoy 0660`.
2. The server creates its socket owned by `vault:vault`, with the process umask's mode. On the
   first apply it came out `0640` with the group `vault`. The operator's connect, which needs write,
   got `EACCES`, and `vault_server`'s "Wait for the Vault API" failed after 30 tries.
   Vault itself had already migrated and unsealed correctly.

Reproduced in the scratchpad: with `socket_mode = "0660"` and `socket_group = "adm"`, the socket
came out `<operator>:<operator> 0775` (the operator's own user and group).

## Fix
- `vault.service` runs `ExecStartPost=+/usr/local/libexec/ai-sandbox/vault-socket <socket> <group>
  <operators...>` as root. It runs after Vault reports ready (`Type=notify`), waits for the socket,
  then does `chgrp vault-clients`, `chmod 0660` and `setfacl -m u:<operator>:rw`.
- `vault.hcl` no longer carries the two settings, so nobody is misled by them.
- `vault_server` asserts the result on every run: a socket, 0660, group `vault-clients`, and
  `user:<operator>:rw-`. `tests/gateway/test_vault.py::test_socket_opens_for_its_group_and_the_operator`
  checks the same.

Consul is different: its `unix_sockets { group, mode }` is honoured, though `group` must be a
number.

## Related
- [Vault and Consul Host Trust](/concepts/vault-and-consul-host-trust--01a17ebdba27.md)
