#!/usr/bin/env bash
# Manage the operator's egress allow list in Consul K/V (concepts/Egress
# Allow List in Consul KV). consul-template re-renders Envoy's CONNECT route
# table within seconds of a change; nothing restarts.
#
#   egress-allowlist.sh <operator-dir> list
#   egress-allowlist.sh <operator-dir> add <host:port> [reason]
#   egress-allowlist.sh <operator-dir> remove <host:port>
#
# <host> is a DNS name or *.<suffix> (a suffix wildcard); <port> is 1-65535.
# Entries under ai-sandbox/egress/baseline/ come from the catalog
# (labs/<lab>/ansible/vars/egress-baseline.yml) and are Ansible's: edit that
# file and re-run `make -f lab-gateway.mk gateway TAGS=consul` to change
# them. The operator token can write allow/ only.
set -euo pipefail

CONSUL=http://localhost
PREFIX=ai-sandbox/egress
HOST_RE='^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+:[0-9]{1,5}$'

usage() { sed -n '5,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 2 ] || usage
ENV_FILE="$1/env.d/consul.sh"
cmd="$2"
shift 2
[ -r "$ENV_FILE" ] || { echo "No operator CLI environment at $ENV_FILE: run make -f lab-gateway.mk gateway" >&2; exit 1; }
# CONSUL_HTTP_ADDR (unix://<socket>) and CONSUL_HTTP_TOKEN_FILE, as consul_egress wrote them.
# shellcheck source=/dev/null
. "$ENV_FILE"
SOCKET="${CONSUL_HTTP_ADDR#unix://}"
TOKEN_FILE="$CONSUL_HTTP_TOKEN_FILE"
[ -r "$TOKEN_FILE" ] || { echo "No operator token at $TOKEN_FILE: run make -f lab-gateway.mk gateway" >&2; exit 1; }

# Consul's HTTP API is a unix socket. The token travels in a header read from
# a file descriptor, never argv.
consul() { curl -sf --unix-socket "$SOCKET" -H @<(printf 'X-Consul-Token: %s' "$(cat "$TOKEN_FILE")") "$@"; }

valid_entry() {
  local entry="$1" port
  [[ "$entry" =~ $HOST_RE ]] || { echo "Not <host>:<port> or *.<suffix>:<port>: $entry" >&2; return 1; }
  port="${entry##*:}"
  [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || { echo "Port out of range: $entry" >&2; return 1; }
}

case "$cmd" in
  list)
    consul "$CONSUL/v1/kv/$PREFIX/?recurse=true" | python3 -c '
import base64, json, sys
rows = []
for kv in json.load(sys.stdin):
    rel = kv["Key"].split("/", 2)[2]
    if not rel or rel.endswith("/"):
        continue
    value = json.loads(base64.b64decode(kv["Value"] or "e30=") or "{}")
    if rel.startswith("baseline/"):
        _, category, entry = rel.split("/", 2)
        rows.append((entry, "baseline:" + category, value.get("reason", "")))
    elif rel.startswith("allow/"):
        rows.append((rel.split("/", 1)[1], "operator", value.get("reason", "")))
width = max([len(r[0]) for r in rows] + [5])
for entry, source, reason in sorted(rows):
    print(f"{entry:<{width}}  {source:<28}  {reason}")
print(f"{len(rows)} entries", file=sys.stderr)'
    ;;
  add)
    [ $# -ge 1 ] || usage
    entry="$1"
    reason="${2:-added by $USER}"
    valid_entry "$entry"
    case "$reason" in *'"'* | *\\*) echo "The reason may not contain \" or \\" >&2; exit 1 ;; esac
    value="$(python3 -c 'import datetime, json, sys; print(json.dumps({"reason": sys.argv[1], "added": datetime.date.today().isoformat(), "source": "operator"}))' "$reason")"
    consul -o /dev/null -X PUT --data "$value" "$CONSUL/v1/kv/$PREFIX/allow/$entry"
    echo "Allowed $entry (Envoy picks it up within seconds)"
    ;;
  remove)
    [ $# -ge 1 ] || usage
    entry="$1"
    valid_entry "$entry"
    consul -o /dev/null "$CONSUL/v1/kv/$PREFIX/allow/$entry" \
      || { echo "$entry is not on the operator allow list (baseline entries are removed from the catalog)" >&2; exit 1; }
    consul -o /dev/null -X DELETE "$CONSUL/v1/kv/$PREFIX/allow/$entry"
    echo "Removed $entry"
    ;;
  *) usage ;;
esac
