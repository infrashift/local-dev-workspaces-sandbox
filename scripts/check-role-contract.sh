#!/usr/bin/env bash
# Check every role under ansible/roles/{host,gateway,guest}/ against the role contract
# (wiki: concepts/Role Contract). Read-only; exit 1 on any violation.
#
#   check-role-contract.sh [roles-root]     (default: <project>/ansible/roles)
#
# What it enforces, per role:
#   * defaults/main.yml declares nothing -- every input comes from the playbook;
#   * vars/main.yml and meta/main.yml exist;
#   * tasks/main.yml opens with the CONTRACT BRACKET (host and gateway: the
#     Linux x86_64 assert; guest: the variant assert and the lane assert) and
#     has a PARAMETER BRACKET (or says it takes no parameters);
#   * every input the parameter bracket asserts is role-prefixed, and is not
#     also set in vars/main.yml, where it would silently become a constant;
#   * the parameter-bracket assert has no success_msg: Ansible templates it
#     before asserting, so a missing input would fail there, as "'x' is
#     undefined", instead of in the fail_msg that names every parameter;
#   * every get_url passes checksum:, except the tasks that fetch a checksums
#     file, manifest or keyring (which cannot verify themselves);
#   * no `| default(...)` masks a fact or guest_user;
#   * ansible_managed appears only in templates/ (it is undefined elsewhere);
#   * no Jinja '\n', and no doubled backslash, sits in a folded (> or >-)
#     scalar: YAML does no escape processing there and ansible-core's
#     templating keeps the backslashes, so '\n' stays the characters \ n
#     and a regex's \\s matches the letter s (wiki: issues/ca_trust wrote
#     anchors ending in a literal backslash-n);
#   * every command/shell task that reports `changed_when: true` without
#     creates:/removes: either names ansible_check_mode (it is gated, with a
#     "Would ..." task beside it) or carries a `# check-mode:` reason. The
#     command module is skipped in a dry run, so an unaccounted one would make
#     ansible-confirm.sh report "Nothing to change" while a real run changes.
#
# Plain bash + grep/sed/awk, so it runs anywhere `make lint` does.
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)/ansible/roles}"
fail=0
err() { echo "$lane/$role: $*"; fail=1; }

for dir in "$ROOT"/host/*/ "$ROOT"/gateway/*/ "$ROOT"/guest/*/; do
  [ -d "$dir" ] || continue
  role="$(basename "$dir")"
  lane="$(basename "$(dirname "$dir")")"
  tasks="$dir/tasks/main.yml"

  for f in defaults/main.yml vars/main.yml meta/main.yml tasks/main.yml; do
    [ -f "$dir/$f" ] || err "missing $f"
  done
  [ -f "$tasks" ] || continue

  # defaults/: only comments, blank lines and the document markers.
  if [ -f "$dir/defaults/main.yml" ] \
    && grep -vqE '^\s*(#.*)?$|^(---|\.\.\.)\s*$' "$dir/defaults/main.yml"; then
    err "defaults/main.yml declares values (this role must have NO defaults)"
  fi

  grep -q 'CONTRACT BRACKET' "$tasks" || err "tasks/main.yml has no CONTRACT BRACKET"
  if [ "$lane" != guest ]; then
    grep -q 'Assert this is the Linux x86_64 host' "$tasks" || err "contract bracket lacks the Linux x86_64 host assert"
  else
    grep -q "_variant in ${role}_compatibility_list" "$tasks" || err "contract bracket lacks the variant assert"
    grep -q 'Assert that the role runs in the' "$tasks" || err "contract bracket lacks the lane assert"
  fi
  grep -q 'PARAMETER BRACKET' "$tasks" || err "tasks/main.yml has no PARAMETER BRACKET"

  # The parameter-bracket assert, up to the next top-level task.
  bracket="$(awk '/name: Assert that every required role parameter was supplied/ { on = 1; next }
                  on && /^- name:/ { exit }
                  on { print }' "$tasks")"
  if grep -q 'success_msg:' <<<"$bracket"; then
    err "the parameter-bracket assert has a success_msg (a missing input would fail there, not in fail_msg)"
  fi

  # Inputs: the `<name> is defined` terms of the parameter-bracket assert.
  inputs="$(grep -oE '\b[a-z_][a-z0-9_]* is defined' <<<"$bracket" | awk '{ print $1 }' | sort -u || true)"
  if grep -q 'PARAMETER BRACKET' "$tasks" && ! grep -q 'takes no parameters' "$tasks" && [ -z "$inputs" ]; then
    err "the PARAMETER BRACKET asserts no inputs (say 'takes no parameters' if that is intended)"
  fi
  for v in $inputs; do
    case "$v" in "${role}_"*) ;; *) err "parameter '$v' is not prefixed ${role}_" ;; esac
    if [ -f "$dir/vars/main.yml" ] && grep -qE "^${v}:" "$dir/vars/main.yml"; then
      err "parameter '$v' is also set in vars/main.yml"
    fi
  done

  # get_url without checksum:. A task runs from one "- name:" to the next.
  awk -v id="$lane/$role" '
    function check() {
      if (geturl && !sum && name !~ /checksums file|SHA256SUMS|SHA-256 file|CHECKSUM file|keyring|manifest/) {
        printf "%s: get_url without checksum: in task \"%s\"\n", id, name
        bad = 1
      }
    }
    /^[[:space:]]*- name:/ { check(); name = $0; sub(/^[[:space:]]*- name:[[:space:]]*/, "", name); geturl = 0; sum = 0 }
    /ansible\.builtin\.get_url:/ { geturl = 1 }
    /^[[:space:]]+checksum:/ { sum = 1 }
    END { check(); exit bad }' "$tasks" || fail=1

  # command/shell changes a dry run cannot see. A "# check-mode:" comment just
  # above the task (or inside it) records why the dry run still reports it.
  awk -v id="$lane/$role" '
    function check() {
      if (cmd && changed && !guarded) {
        printf "%s: command task \"%s\" changes state but a dry run would not report it\n", id, name
        bad = 1
      }
    }
    /^[[:space:]]*#/ { if ($0 ~ /check-mode:/) note = 1; if (intask && $0 ~ /check-mode:/) guarded = 1; next }
    /^[[:space:]]*- name:/ { check(); name = $0; sub(/^[[:space:]]*- name:[[:space:]]*/, "", name)
                             intask = 1; cmd = 0; changed = 0; guarded = note; note = 0; next }
    { note = 0 }
    /ansible\.builtin\.(command|shell):/ { cmd = 1 }
    /changed_when: true/ { changed = 1 }
    /(creates|removes):|ansible_check_mode/ { guarded = 1 }
    END { check(); exit bad }' "$tasks" || fail=1

  # A folded scalar runs from a "key: >" / "key: >-" line to the next line
  # indented no deeper than that key.
  for f in "$dir"/tasks/*.yml "$dir"/vars/*.yml; do
    awk -v id="$lane/$role" -v file="${f##*/}" '
      { match($0, /^[[:space:]]*/); indent = RLENGTH }
      folded && $0 !~ /^[[:space:]]*$/ && indent <= key_indent { folded = 0 }
      folded && index($0, "\x27\\n\x27") > 0 {
        printf "%s: %s:%d: a Jinja \x27\\n\x27 in a folded scalar stays literal; use a double-quoted scalar\n", id, file, NR
        bad = 1
      }
      folded && index($0, "\\\\") > 0 {
        printf "%s: %s:%d: a doubled backslash in a folded scalar reaches Jinja as two; write one\n", id, file, NR
        bad = 1
      }
      /:[[:space:]]*>-?[[:space:]]*$/ { folded = 1; key_indent = indent }
      END { exit bad }' "$f" || fail=1
  done

  # ansible_managed exists only while the template module renders a file.
  if grep -n 'ansible_managed' "$dir"/tasks/*.yml "$dir"/vars/*.yml; then
    err "ansible_managed outside a template (above): it is undefined there; move the content to templates/"
  fi

  if grep -nE "(ansible_facts\[[^]]*\]|guest_user)[^}]*\|[[:space:]]*default\(" "$dir"/tasks/*.yml "$dir"/vars/*.yml; then
    err "| default(...) masks a fact or guest_user (above)"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "Role contract violations found." >&2
  exit 1
fi
echo "All roles satisfy the role contract."
