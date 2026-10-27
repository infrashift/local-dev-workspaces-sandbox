#!/usr/bin/env bash
# Use a break-glass Vault token (concepts/Operator Interfaces): unwrap the
# single-use wrapping token break-glass.yml left, then run one command, or an
# interactive shell, with VAULT_TOKEN set; revoke the token when that exits.
# The token never touches a file. Run through lab-gateway.mk:
#
#   make -f lab-gateway.mk break-glass REASON="why" [CMD="vault kv get ..."]
#
#   break-glass.sh <operator-dir> <wrap-file> [command...]
set -euo pipefail

[ $# -ge 2 ] || { sed -n '9p' "$0" | sed 's/^# *//' >&2; exit 2; }
OPERATOR_DIR="$1"
WRAP_FILE="$2"
shift 2
ENV_FILE="$OPERATOR_DIR/env.d/vault.sh"
[ -r "$ENV_FILE" ] || { echo "No operator CLI environment at $ENV_FILE: run make -f lab-gateway.mk gateway" >&2; exit 1; }
# VAULT_ADDR (unix://<socket>) and VAULT_CONFIG_PATH, as vault_gateway wrote them.
# shellcheck source=/dev/null
. "$ENV_FILE"
SOCKET="${VAULT_ADDR#unix://}"
[ -r "$WRAP_FILE" ] || { echo "No wrapping token at $WRAP_FILE: run make -f lab-gateway.mk break-glass" >&2; exit 1; }
wrap="$(cat "$WRAP_FILE")"
rm -f "$WRAP_FILE"

# Tokens travel in a header read from a file descriptor, never argv.
vault_as() { local token="$1"; shift; curl -sf --unix-socket "$SOCKET" -H @<(printf 'X-Vault-Token: %s' "$token") "$@"; }

if ! token="$(vault_as "$wrap" -X POST http://localhost/v1/sys/wrapping/unwrap \
  | python3 -c 'import json, sys
try:
    print(json.load(sys.stdin)["auth"]["client_token"])
except (ValueError, KeyError, TypeError):
    sys.exit(1)')"; then
  echo "The wrapping token did not unwrap: it expired, or someone used it first." \
    "Vault's audit log shows who: sudo grep sys/wrapping/unwrap /var/log/vault/audit.log" >&2
  exit 1
fi
unset wrap

revoke() {
  if vault_as "$token" -o /dev/null -X POST http://localhost/v1/auth/token/revoke-self; then
    echo "Break-glass token revoked." >&2
  else
    echo "Could not revoke the break-glass token; it expires on its own within 15 minutes." >&2
  fi
}
trap revoke EXIT

if [ $# -gt 0 ]; then
  VAULT_TOKEN="$token" "$@"
else
  echo "Break-glass shell: VAULT_TOKEN reads the real credentials for 15 minutes. Exit to revoke it." >&2
  # The rc file's lines expand in the new shell, not here.
  # shellcheck disable=SC2016
  BREAK_GLASS_TOKEN="$token" bash --rcfile <(printf '%s\n' \
    ". \"$OPERATOR_DIR/env.sh\"" \
    'export VAULT_TOKEN="$BREAK_GLASS_TOKEN"; unset BREAK_GLASS_TOKEN' \
    'PS1="(break-glass) $PS1"') -i
fi
