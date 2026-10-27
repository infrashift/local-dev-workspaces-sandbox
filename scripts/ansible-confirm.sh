#!/usr/bin/env bash
# Run an ansible-playbook command as a dry run first, then apply it only if
# the user types "yes" (like `terraform apply`).
#
#   ansible-confirm.sh <ansible-playbook> [args...]
#
#   1. <ansible-playbook> --check --diff [args...]   (never prompts for sudo)
#   2. if nothing would change: done
#   3. otherwise show the summary and ask; only the exact answer "yes" applies
#   4. <ansible-playbook> [args...] $ANSIBLE_APPLY_ARGS
#
# ANSIBLE_APPLY_ARGS holds flags for the real run only, e.g. --ask-become-pass
# when a privileged role will act.
# CHECK_ONLY=1 stops after the dry run: exit 0 if nothing would change, 1
# otherwise (used as a read-only readiness check).
# ANSIBLE_CONFIRM=yes answers the prompt for an unattended run (an agent, CI):
# the full dry run is still shown first, so the log records what was applied.
set -euo pipefail

[ $# -ge 1 ] || { echo "Usage: $0 <ansible-playbook> [args...]" >&2; exit 2; }

LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

echo "=== Dry run (--check --diff): nothing is changed ==="
set +e
"$@" --check --diff 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -ne 0 ]; then
  echo "Dry run failed (exit $rc); nothing was applied." >&2
  exit "$rc"
fi

# On a terminal Ansible colors its output; parse an uncolored copy.
PLAIN="$(mktemp)"
trap 'rm -f "$LOG" "$PLAIN"' EXIT
sed $'s/\x1b\\[[0-9;]*m//g' "$LOG" >"$PLAIN"

# PLAY RECAP lines look like: "localhost : ok=12 changed=3 unreachable=0 ..."
if ! grep -qE 'changed=[1-9]' "$PLAIN"; then
  echo "=== Nothing to change. ==="
  exit 0
fi
if [ "${CHECK_ONLY:-0}" = "1" ]; then
  echo "=== The dry run above has pending changes. ===" >&2
  exit 1
fi

echo
echo "=== Pending changes ==="
# Task headers whose result was "changed", from Ansible's default output.
awk '/^TASK \[/ { task = $0 } /^changed: / { if (task != last) { print "  " task; last = task } }' "$PLAIN" \
  | sed -e 's/^  TASK \[/  - /' -e 's/\] \**$//'
echo
if [ "${ANSIBLE_CONFIRM:-}" = "yes" ]; then
  echo "=== ANSIBLE_CONFIRM=yes: applying the changes above ==="
  # shellcheck disable=SC2086 # ANSIBLE_APPLY_ARGS is a list of flags
  exec "$@" ${ANSIBLE_APPLY_ARGS:-}
fi
# -r /dev/tty is true even without a controlling terminal; try opening it.
if ! (exec </dev/tty) 2>/dev/null; then
  echo "No terminal to confirm on; nothing was applied. Re-run interactively." >&2
  exit 1
fi
printf 'Ansible will make the changes above.\n  Only "yes" will be accepted to apply.\n\nEnter a value: '
read -r answer </dev/tty
if [ "$answer" != "yes" ]; then
  echo "Apply cancelled."
  exit 1
fi

echo "=== Applying ==="
# shellcheck disable=SC2086 # ANSIBLE_APPLY_ARGS is a list of flags
exec "$@" ${ANSIBLE_APPLY_ARGS:-}
