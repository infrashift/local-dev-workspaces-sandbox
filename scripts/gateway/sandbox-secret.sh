#!/usr/bin/env bash
# Manage the gateway's REAL credentials (concepts/Gateway Credentials in the
# Host Inventory): the registry vars/gateway-secrets.yml names them, and the
# host inventory's ansible-vault file holds their values. A secret is read
# from the terminal without echo and travels only on stdin, into
# `ansible-vault encrypt_string`: never argv, never a plaintext file, never a
# log. The gateway playbook then writes it into Vault for the surrogates that
# name it; the sandbox guest only ever holds the surrogates.
#
#   sandbox-secret.sh <vars-dir> <vault.yml> <vault-key> <ansible-vault> <python> <operator-dir> <command> [args]
#
#   list                        name, kind, repository, held, loaded into Vault, rotated, expires
#   check                       the registry, the surrogates and vault.yml agree; nothing expired
#   set <name|all> [expires]    ask for a value (all: each one vault.yml lacks), record today as rotated
#   rotate <name> [expires]     the same for one held secret, asking for its new expiry date
#   add <name> <kind> [repo]    a new registry entry (kind github-pat or anthropic-api-key), then set it
#   remove <name>               the registry entry and its vault.yml variable (no surrogate may name it)
#
# The rules and the registry edits are in gateway_secrets.py beside this
# script; it never sees a value.
set -euo pipefail

usage() { sed -n '10,17p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 7 ] || usage
VARS_DIR="$1"
VAULT_YML="$2"
VAULT_KEY="$3"
ANSIBLE_VAULT="$4"
PYTHON="$5"
OPERATOR_DIR="$6"
cmd="$7"
shift 7
RULES="$(dirname "$0")/gateway_secrets.py"
rules() { "$PYTHON" -I "$RULES" "$@"; }
today() { date +%F; }

need_terminal() {
  [ -s "$VAULT_KEY" ] || { echo "No vault key at $VAULT_KEY: run make -f lab-bootstrap.mk become-vault" >&2; exit 1; }
  [ -t 0 ] || { echo "Run this on a terminal: it reads the secret without echo." >&2; exit 1; }
}

# The expiry date: the one given, or asked for (blank keeps none).
expiry() {
  local given="$1" asked
  if [ -n "$given" ]; then echo "$given"; return; fi
  read -rp "    Expiry date of the new value (YYYY-MM-DD, blank for none): " asked </dev/tty
  echo "${asked:--}"
}

store() {
  local name="$1" var="$2" label="$3" secret block
  read -rsp ">>> $name: $label: " secret </dev/tty; echo
  [ -n "$secret" ] || { echo "Empty secret; $name unchanged" >&2; return 1; }
  # Envoy's Lua filter reads the record's fields as [^"\\]*.
  case "$secret" in *'"'* | *\\* | *$'\n'* | *' '*) echo "The secret may not contain \", \\, a space or a newline" >&2; return 1 ;; esac
  block="$(printf '%s' "$secret" | "$ANSIBLE_VAULT" encrypt_string --vault-password-file "$VAULT_KEY" \
    --stdin-name "$var" 2>/dev/null)"
  unset secret
  # Replace this variable's block (its line and the indented lines below it),
  # or append it; written to a 0600 temporary file, then moved into place.
  printf '%s\n' "$block" | "$PYTHON" -I -c '
import os, re, sys
from pathlib import Path
path, var = Path(sys.argv[1]), sys.argv[2]
block = sys.stdin.read().rstrip("\n") + "\n"
text = path.read_text() if path.exists() else (
    "---\n# The gateway credentials, each ansible-vault encrypted (make -f lab-gateway.mk secret-set).\n"
    "# Gitignored; vars/gateway-secrets.yml names them.\n")
text = re.sub(rf"(?m)^{var}:.*\n(?:[ \t]+.*\n)*", "", text.replace("\n...\n", "\n"))
tmp = path.with_suffix(".yml.tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as out:
    out.write(text.rstrip("\n") + "\n" + block)
os.replace(tmp, path)' "$VAULT_YML" "$var"
  echo "    $var: encrypted in $VAULT_YML"
}

# set/rotate one or all: store each value, then record the dates in the registry.
set_secrets() {
  local which="$1" expires="$2" ask_expiry="$3" found=0 rows name var label held
  rows="$(rules rows "$VARS_DIR" "$VAULT_YML")"
  while IFS=$'\t' read -r name var label held; do
    if [ "$which" = all ]; then
      [ "$held" = 0 ] || { echo ">>> $name: held already (secret-rotate NAME=$name replaces it)"; found=1; continue; }
    elif [ "$which" != "$name" ]; then
      continue
    fi
    found=1
    store "$name" "$var" "$label"
    if [ "$ask_expiry" = 1 ]; then
      rules stamp "$VARS_DIR" "$name" "$(today)" "$(expiry "$expires")"
    else
      rules stamp "$VARS_DIR" "$name" "$(today)" "${expires:--}"
    fi
  done <<<"$rows"
  [ "$found" -eq 1 ] || { echo "No secret named $which in $VARS_DIR/gateway-secrets.yml" >&2; exit 1; }
}

case "$cmd" in
  list) rules list "$VARS_DIR" "$VAULT_YML" "$OPERATOR_DIR" ;;
  check) rules check "$VARS_DIR" "$VAULT_YML" ;;
  set)
    [ $# -ge 1 ] || usage
    need_terminal
    set_secrets "$1" "${2:-}" 0
    ;;
  rotate)
    [ $# -ge 1 ] && [ "$1" != all ] || usage
    need_terminal
    set_secrets "$1" "${2:-}" 1
    ;;
  add)
    [ $# -ge 2 ] || usage
    need_terminal
    rules add "$VARS_DIR" "$1" "$2" "${3:--}"
    set_secrets "$1" "" 1
    ;;
  remove)
    [ $# -eq 1 ] || usage
    rules remove "$VARS_DIR" "$VAULT_YML" "$1"
    ;;
  *) usage ;;
esac
