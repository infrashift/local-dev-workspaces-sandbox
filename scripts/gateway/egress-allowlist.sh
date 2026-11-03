#!/usr/bin/env bash
# Manage the operator's egress allow list (concepts/Egress Allow List in Consul
# KV). The file labs/<lab>/ansible/vars/egress-allow.yml is the source; Consul
# K/V under ai-sandbox/egress/allow/ is where Envoy reads it from:
# consul-template re-renders Envoy's CONNECT route table within seconds of a
# change, and nothing restarts.
#
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> list
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> plan
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> sync
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> add <host:port> <reason> [kind] [user] [expires]
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> remove <host:port>
#   egress-allowlist.sh <operator-dir> <vars-dir> <python> principals-drift
#
# plan shows what sync would change and exits 2 when Consul and the file
# differ. sync makes Consul match the file, after a typed "yes"
# (ANSIBLE_CONFIRM=yes answers for you); it removes keys the file does not
# name. add and remove edit the file and apply only that one entry.
# principals-drift exits 1 when the file's ssh users differ from the
# principals the gateway last issued the agent certificate for.
#
# The rules (kinds, gateway hosts, expiry) are in egress_allow.py beside this
# script. Entries under ai-sandbox/egress/baseline/ come from the catalog
# (egress-baseline.yml) and are Ansible's. The operator token can write
# allow/ only.
set -euo pipefail

CONSUL=http://localhost
PREFIX=ai-sandbox/egress

usage() { sed -n '8,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 4 ] || usage
OPERATOR_DIR="$1"
VARS_DIR="$2"
PYTHON="$3"
cmd="$4"
shift 4
RULES="$(dirname "$0")/egress_allow.py"
rules() { "$PYTHON" -I "$RULES" "$@"; }

ENV_FILE="$OPERATOR_DIR/env.d/consul.sh"
connect() {
  [ -r "$ENV_FILE" ] || { echo "No operator CLI environment at $ENV_FILE: run make -f lab-gateway.mk gateway" >&2; exit 1; }
  # CONSUL_HTTP_ADDR (unix://<socket>) and CONSUL_HTTP_TOKEN_FILE, as consul_egress wrote them.
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  SOCKET="${CONSUL_HTTP_ADDR#unix://}"
  TOKEN_FILE="$CONSUL_HTTP_TOKEN_FILE"
  [ -r "$TOKEN_FILE" ] || { echo "No operator token at $TOKEN_FILE: run make -f lab-gateway.mk gateway" >&2; exit 1; }
  consul -o /dev/null "$CONSUL/v1/status/leader" \
    || { echo "Consul does not answer on $SOCKET: systemctl status consul" >&2; exit 1; }
}

# Consul's HTTP API is a unix socket. The token travels in a header read from
# a file descriptor, never argv.
consul() { curl -sf --unix-socket "$SOCKET" -H @<(printf 'X-Consul-Token: %s' "$(cat "$TOKEN_FILE")") "$@"; }
# A prefix with no keys is a 404; that reads as an empty list.
consul_tree() { consul "$CONSUL/v1/kv/$PREFIX/$1?recurse=true" || true; }

# Apply plan actions (PUT <entry> <json> / DELETE <entry>) read on stdin.
apply() {
  local verb entry value n=0
  while read -r verb entry value; do
    [ -n "$verb" ] || continue
    case "$verb" in
      PUT) consul -o /dev/null -X PUT --data "$value" "$CONSUL/v1/kv/$PREFIX/allow/$entry" ;;
      DELETE) consul -o /dev/null -X DELETE "$CONSUL/v1/kv/$PREFIX/allow/$entry" ;;
      *) echo "Unknown action: $verb" >&2; exit 1 ;;
    esac
    n=$((n + 1))
  done
  echo "$n change(s) written to Consul (Envoy picks them up within seconds)"
}

# The plan's actions for one entry only.
only() { awk -v e="$1" '$2 == e'; }

case "$cmd" in
  list)
    connect
    consul_tree "" | rules list "$VARS_DIR"
    ;;
  plan)
    connect
    actions="$(consul_tree allow/ | rules plan "$VARS_DIR")"
    if [ -z "$actions" ]; then echo "Consul's allow list matches the file."; else exit 2; fi
    ;;
  sync)
    connect
    actions="$(consul_tree allow/ | rules plan "$VARS_DIR")"
    [ -n "$actions" ] || { echo "Consul's allow list matches the file; nothing to do."; exit 0; }
    if [ "${ANSIBLE_CONFIRM:-}" != yes ]; then
      [ -t 0 ] || { echo "Not a terminal: set ANSIBLE_CONFIRM=yes to apply without the prompt." >&2; exit 1; }
      read -rp "Apply these changes to Consul? Type yes: " answer
      [ "$answer" = yes ] || { echo "Nothing changed."; exit 1; }
    fi
    apply <<<"$actions"
    ;;
  add)
    [ $# -ge 2 ] || usage
    entry="$1"
    connect
    rules add "$VARS_DIR" "${3:--}" "$entry" "${4:--}" "$2" "${5:--}"
    consul_tree allow/ | rules plan "$VARS_DIR" 2>/dev/null | only "$entry" | apply >/dev/null
    echo "Allowed $entry (Envoy picks it up within seconds). Commit $VARS_DIR/egress-allow.yml."
    "$0" "$OPERATOR_DIR" "$VARS_DIR" "$PYTHON" plan >/dev/null 2>&1 \
      || echo "Other changes are pending between the file and Consul: make -f lab-gateway.mk allow-plan"
    ;;
  remove)
    [ $# -ge 1 ] || usage
    entry="$1"
    connect
    rules remove "$VARS_DIR" "$entry"
    consul_tree allow/ | rules plan "$VARS_DIR" 2>/dev/null | only "$entry" | apply >/dev/null
    echo "Removed $entry. Commit $VARS_DIR/egress-allow.yml."
    ;;
  principals-drift)
    want="$(rules principals "$VARS_DIR")"
    have="$(cat "$OPERATOR_DIR/ssh-principals" 2>/dev/null || true)"
    if [ "$want" != "$have" ]; then
      echo "SSH principals: the file names [$want], the agent certificate is issued for [${have:-unknown}]"
      exit 1
    fi
    ;;
  *) usage ;;
esac
