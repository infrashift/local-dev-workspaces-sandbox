#!/usr/bin/env bash
# Set (or rotate) a REAL credential of the gateway in the host inventory's
# ansible-vault file (concepts/Surrogate Credential Model). The secret is read
# from the terminal without echo and travels only on stdin, into
# `ansible-vault encrypt_string`: never argv, never a plaintext file, never a
# log. The gateway playbook then writes it into Vault for the surrogates that
# name it; the sandbox guest only ever holds the surrogates.
#
#   sandbox-secret.sh <vars.yml> <vault.yml> <vault-key> <ansible-vault> <gateway.yml> <python> <name|all>
#
# <vars.yml>'s gateway_secrets maps each secret name to the variable that
# holds it ("{{ <name>_secret }}"); <vault.yml> holds those variables, each
# encrypted on its own (a !vault block), so one can be replaced alone.
#   a github_repos key  a fine-grained PAT limited to that one repository
#                       (contents and metadata: read)
#   anthropic           an Anthropic API key
# `all` asks for every secret that vault.yml does not hold yet.
set -euo pipefail

[ $# -eq 7 ] || { sed -n '9p' "$0" | sed 's/^# *//' >&2; exit 2; }
VARS_YML="$1"
VAULT_YML="$2"
VAULT_KEY="$3"
ANSIBLE_VAULT="$4"
GATEWAY_YML="$5"
PYTHON="$6"
WHICH="$7"
[ -s "$VAULT_KEY" ] || { echo "No vault key at $VAULT_KEY: run make -f lab-bootstrap.mk become-vault" >&2; exit 1; }
[ -t 0 ] || { echo "Run this on a terminal: it reads the secret without echo." >&2; exit 1; }

# name<TAB>variable<TAB>prompt<TAB>held (1 if vault.yml already has it).
rows="$("$PYTHON" -c '
import re, sys, yaml
from pathlib import Path
secrets = yaml.safe_load(open(sys.argv[1]))["gateway_secrets"]
repos = yaml.safe_load(open(sys.argv[3]))["github_repos"]
vault = Path(sys.argv[2]).read_text() if Path(sys.argv[2]).exists() else ""
for name, ref in secrets.items():
    var = re.fullmatch(r"\{\{\s*(\w+)\s*\}\}", ref).group(1)
    repo = repos.get(name, {}).get("repo")
    label = f"Fine-grained PAT for {repo}" if repo else "Anthropic API key" if name == "anthropic" else name
    held = int(re.search(rf"(?m)^{var}:", vault) is not None)
    print(name, var, label, held, sep="\t")' "$VARS_YML" "$VAULT_YML" "$GATEWAY_YML")"

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
  printf '%s\n' "$block" | "$PYTHON" -c '
import os, re, sys
from pathlib import Path
path, var = Path(sys.argv[1]), sys.argv[2]
block = sys.stdin.read().rstrip("\n") + "\n"
text = path.read_text() if path.exists() else (
    "---\n# The gateway credentials, each ansible-vault encrypted (make -f lab-gateway.mk secrets).\n"
    "# Gitignored; vars.yml beside it maps them to their secret names.\n")
text = re.sub(rf"(?m)^{var}:.*\n(?:[ \t]+.*\n)*", "", text.replace("\n...\n", "\n"))
tmp = path.with_suffix(".yml.tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as out:
    out.write(text.rstrip("\n") + "\n" + block)
os.replace(tmp, path)' "$VAULT_YML" "$var"
  echo "    $var: encrypted in $VAULT_YML"
}

found=0
while IFS=$'\t' read -r name var label held; do
  if [ "$WHICH" = all ]; then
    [ "$held" = 0 ] || { echo ">>> $name: held already (NAME=$name to rotate it)"; found=1; continue; }
  elif [ "$WHICH" != "$name" ]; then
    continue
  fi
  found=1
  store "$name" "$var" "$label"
done <<<"$rows"
[ "$found" -eq 1 ] || { echo "No secret named $WHICH in $VARS_YML gateway_secrets" >&2; exit 1; }
