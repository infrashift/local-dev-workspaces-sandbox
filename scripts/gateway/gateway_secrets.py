"""The gateway's secrets registry (labs/<lab>/ansible/vars/gateway-secrets.yml): its rules, its
report, and its line-by-line edits. sandbox-secret.sh reads the secrets at the terminal and
encrypts them; this file never sees a value, only names, dates and which vault.yml variables
exist (concepts/Gateway Credentials in the Host Inventory).

    gateway_secrets.py rows   <vars-dir> <vault.yml>                   name, variable, prompt, held (TSV)
    gateway_secrets.py check  <vars-dir> <vault.yml>
    gateway_secrets.py list   <vars-dir> <vault.yml> <operator-dir>
    gateway_secrets.py stamp  <vars-dir> <name> <rotated> <expires|->
    gateway_secrets.py add    <vars-dir> <name> <kind> <repo|->
    gateway_secrets.py remove <vars-dir> <vault.yml> <name>

list reads each record's metadata from Vault (updated_time) with the operator token, which reads
metadata only, never a value. Run with the lab venv's python (it has PyYAML), isolated: python -I.
"""

from __future__ import annotations

import base64
import datetime
import http.client
import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any

import yaml

REGISTRY_FILE = "gateway-secrets.yml"
KINDS = {"github-pat": "Fine-grained PAT for {repo}", "anthropic-api-key": "Anthropic API key"}
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
VAR_RE = re.compile(r"^[a-z][a-z0-9_]*_secret$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# One registry entry per line: "  <name>: { ... }".
LINE_RE = re.compile(r"^  ([a-z][a-z0-9_-]*):\s*\{.*\}\s*(#.*)?$")
FIELDS = {"kind", "repo", "vault_var", "rotated", "expires"}
WARN_DAYS = 14
VAULT_SOCKET = "/run/vault/vault.sock"


class Invalid(Exception):
    pass


def registry(vars_dir: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    text = (vars_dir / REGISTRY_FILE).read_text()
    reg = (yaml.safe_load(text) or {}).get("gateway_secret_registry") or {}
    lines = text.splitlines(keepends=True)
    if len([line for line in lines if LINE_RE.match(line)]) != len(reg):
        raise Invalid(f"{REGISTRY_FILE}: write each gateway_secret_registry entry on one line, as <name>: {{ ... }}")
    return lines, reg


def surrogates(vars_dir: Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load((vars_dir / "gateway.yml").read_text())["surrogates"]


def vault_vars(vault_yml: Path) -> set[str]:
    """The top-level variables vault.yml defines (names only; the values stay encrypted)."""
    if not vault_yml.exists():
        return set()
    return set(re.findall(r"(?m)^([a-z][a-z0-9_]*):", vault_yml.read_text()))


def as_date(value: Any) -> datetime.date | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, datetime.date) else datetime.date.fromisoformat(str(value))


def problems(vars_dir: Path, vault_yml: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the registry, the surrogates and vault.yml together."""
    _, reg = registry(vars_dir)
    subs = surrogates(vars_dir)
    held = vault_vars(vault_yml)
    errors, warnings = [], []
    today = datetime.date.today()
    vars_seen: dict[str, str] = {}
    for name, spec in reg.items():
        where = f"{REGISTRY_FILE} {name}"
        if not NAME_RE.match(name):
            errors.append(f"{where}: the name must match {NAME_RE.pattern}")
        unknown = set(spec) - FIELDS
        if unknown:
            errors.append(f"{where}: unknown field(s) {sorted(unknown)}")
        if spec.get("kind") not in KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(KINDS)}")
        if spec.get("kind") == "github-pat" and not REPO_RE.match(str(spec.get("repo", ""))):
            errors.append(f"{where}: a github-pat needs repo: <owner>/<name>")
        if spec.get("kind") != "github-pat" and "repo" in spec:
            errors.append(f"{where}: repo is for kind github-pat only")
        var = str(spec.get("vault_var", ""))
        if not VAR_RE.match(var):
            errors.append(f"{where}: vault_var must match {VAR_RE.pattern}")
        elif var in vars_seen:
            errors.append(f"{where}: vault_var {var} is {vars_seen[var]}'s too")
        vars_seen[var] = name
        if var and var not in held:
            errors.append(f"{where}: vault.yml has no {var}: make -f lab-gateway.mk secret-set NAME={name}")
        try:
            expires = as_date(spec.get("expires"))
            as_date(spec.get("rotated"))
        except ValueError:
            errors.append(f"{where}: rotated and expires are YYYY-MM-DD dates")
            continue
        if expires and expires <= today:
            errors.append(f"{where}: expired on {expires}: make -f lab-gateway.mk secret-rotate NAME={name}")
        elif expires and (expires - today).days <= WARN_DAYS:
            warnings.append(f"{where}: expires in {(expires - today).days} days ({expires})")
        used = [s for s in subs.values() if s.get("secret") == name]
        if not used:
            errors.append(f"{where}: no surrogate in vars/gateway.yml names it (secret: {name})")
        if spec.get("kind") == "github-pat":
            uses = sorted(s.get("use", "") for s in used)
            if uses != ["api", "git", "mcp"]:
                warnings.append(f"{where}: its surrogates are {uses}; a repository usually has git, api and mcp")
    for sname, s in subs.items():
        secret = s.get("secret")
        if secret not in reg:
            errors.append(f"vars/gateway.yml surrogate {sname}: secret {secret} is not in {REGISTRY_FILE}")
        elif "repo" in s and s["repo"] != reg[secret].get("repo"):
            errors.append(
                f"vars/gateway.yml surrogate {sname}: repo {s['repo']} is not its secret's ({reg[secret].get('repo')})"
            )
    return errors, warnings


# ---------------------------------------------------------------------------
# Vault metadata (the operator token: metadata only)
# ---------------------------------------------------------------------------
class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path: str) -> None:
        super().__init__("localhost", timeout=10)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def record_updated(operator_dir: Path, credentials: list[str]) -> str:
    """The latest updated_time of these surrogates' Vault records, YYYY-MM-DD, or why there is none."""
    token_file = operator_dir / "vault-operator.token"
    if not token_file.is_file():
        return "no operator token"
    token = token_file.read_text().strip()
    latest = ""
    for credential in credentials:
        rid = base64.urlsafe_b64encode(credential.encode()).decode().rstrip("=")
        try:
            conn = UnixHTTPConnection(VAULT_SOCKET)
            conn.request("GET", f"/v1/ai-sandbox/metadata/surrogates/{rid}", headers={"X-Vault-Token": token})
            resp = conn.getresponse()
            body = resp.read()
        except OSError:
            return "Vault unreachable"
        if resp.status == 404:
            return "not loaded"
        if resp.status != 200:
            return f"Vault {resp.status}"
        latest = max(latest, json.loads(body)["data"]["updated_time"][:10])
    return latest or "no surrogate"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_rows(vars_dir: Path, vault_yml: Path) -> int:
    _, reg = registry(vars_dir)
    held = vault_vars(vault_yml)
    for name, spec in reg.items():
        label = KINDS.get(spec.get("kind"), name).format(repo=spec.get("repo", ""))
        print(name, spec["vault_var"], label, int(spec["vault_var"] in held), sep="\t")
    return 0


def cmd_check(vars_dir: Path, vault_yml: Path) -> int:
    errors, warnings = problems(vars_dir, vault_yml)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    _, reg = registry(vars_dir)
    print(f"{REGISTRY_FILE}: {len(reg)} secrets, {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
    return 1 if errors else 0


def cmd_list(vars_dir: Path, vault_yml: Path, operator_dir: Path) -> int:
    _, reg = registry(vars_dir)
    held = vault_vars(vault_yml)
    subs = surrogates(vars_dir)
    today = datetime.date.today()
    rows = [("NAME", "KIND", "REPO", "VAULT.YML", "IN VAULT", "ROTATED", "EXPIRES")]
    for name, spec in reg.items():
        expires = as_date(spec.get("expires"))
        if expires:
            days = (expires - today).days
            left = "EXPIRED" if days <= 0 else f"{days}d" + (" !" if days <= WARN_DAYS else "")
            exp = f"{expires} ({left})"
        else:
            exp = "-"
        creds = [s["credential"] for s in subs.values() if s.get("secret") == name]
        rows.append(
            (
                name,
                spec.get("kind", "?"),
                spec.get("repo", "-"),
                "held" if spec.get("vault_var") in held else "MISSING",
                record_updated(operator_dir, creds),
                str(spec.get("rotated") or "-"),
                exp,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(f"{c:<{widths[i]}}" for i, c in enumerate(row)).rstrip())
    return 0


def edit_line(lines: list[str], name: str, update: dict[str, Any]) -> list[str]:
    """The registry's lines with <name>'s entry re-written with these fields changed."""
    out, found = [], False
    for line in lines:
        m = LINE_RE.match(line)
        if m and m.group(1) == name:
            spec = yaml.safe_load(line.split(":", 1)[1])
            spec.update({k: v for k, v in update.items() if v is not None})
            for k in [k for k, v in update.items() if v is None]:
                spec.pop(k, None)
            line = render(name, spec)
            found = True
        out.append(line)
    if not found:
        raise Invalid(f"No secret named {name} in {REGISTRY_FILE}")
    return out


def render(name: str, spec: dict[str, Any]) -> str:
    order = ["kind", "repo", "vault_var", "rotated", "expires"]
    fields = ", ".join(f"{k}: {spec[k]}" for k in order if k in spec)
    return f"  {name}: {{ {fields} }}\n"


def write(vars_dir: Path, lines: list[str]) -> None:
    text = "".join(lines)
    reg = (yaml.safe_load(text) or {}).get("gateway_secret_registry") or {}
    if len([line for line in lines if LINE_RE.match(line)]) != len(reg):
        raise Invalid(f"{REGISTRY_FILE}: the edit would break the file; nothing written")
    path = vars_dir / REGISTRY_FILE
    tmp = path.with_suffix(".yml.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def cmd_stamp(vars_dir: Path, name: str, rotated: str, expires: str) -> int:
    lines, _ = registry(vars_dir)
    update: dict[str, Any] = {"rotated": datetime.date.fromisoformat(rotated)}
    if expires != "-":
        try:
            update["expires"] = datetime.date.fromisoformat(expires)
        except ValueError:
            raise Invalid(f"Not a YYYY-MM-DD date: {expires}") from None
    write(vars_dir, edit_line(lines, name, update))
    print(f"    {REGISTRY_FILE}: {name} rotated {rotated}" + (f", expires {expires}" if expires != "-" else ""))
    return 0


def cmd_add(vars_dir: Path, name: str, kind: str, repo: str) -> int:
    lines, reg = registry(vars_dir)
    if not NAME_RE.match(name):
        raise Invalid(f"The name must match {NAME_RE.pattern}: {name}")
    if name in reg:
        raise Invalid(f"{name} is in {REGISTRY_FILE} already: secret-rotate NAME={name} replaces its value")
    if kind not in KINDS:
        raise Invalid(f"KIND must be one of {', '.join(KINDS)}")
    under = name.replace("-", "_")
    spec: dict[str, Any] = {"kind": kind}
    if kind == "github-pat":
        if not REPO_RE.match(repo):
            raise Invalid("A github-pat needs REPO=<owner>/<name>")
        if any(s.get("repo") == repo for s in reg.values()):
            raise Invalid(f"{repo} has a secret in {REGISTRY_FILE} already")
        spec.update(repo=repo, vault_var=f"github_pat_{under}_secret")
    else:
        spec["vault_var"] = f"{under}_secret"
    at = max((i for i, line in enumerate(lines) if LINE_RE.match(line)), default=None)
    if at is None:
        at = next(i for i, line in enumerate(lines) if line.startswith("gateway_secret_registry:"))
        lines[at] = "gateway_secret_registry:\n"
    write(vars_dir, lines[: at + 1] + [render(name, spec)] + lines[at + 1 :])
    print(f"    {REGISTRY_FILE}: added {name} ({kind})")
    if kind == "github-pat":
        print(
            "\nAdd its surrogates to vars/gateway.yml (surrogates:), then run make -f lab-gateway.mk gateway\n"
            "and the guest playbook (make -f lab-provision.mk play PLAYBOOK=python-stack):\n"
        )
        for use, scheme, hosts, cred in (
            ("git", "basic", "[github.com, api.github.com]", f"claude:surrogate-github-git-{name}"),
            ("api", "bearer", "[api.github.com, raw.githubusercontent.com]", f"surrogate-github-api-{name}"),
            ("mcp", "bearer", "[mcp.upstream.ai-sandbox.test, api.githubcopilot.com]", f"surrogate-github-mcp-{name}"),
        ):
            print(
                f"  github_{use}_{under}:\n"
                f'    credential: "{cred}"\n'
                f"    scheme: {scheme}\n"
                f"    use: {use}\n"
                f"    target_hosts: {hosts}\n"
                f"    repo: {repo}\n"
                f"    secret: {name}"
            )
        print()
    return 0


def cmd_remove(vars_dir: Path, vault_yml: Path, name: str) -> int:
    lines, reg = registry(vars_dir)
    if name not in reg:
        raise Invalid(f"No secret named {name} in {REGISTRY_FILE}")
    users = sorted(k for k, s in surrogates(vars_dir).items() if s.get("secret") == name)
    if users:
        raise Invalid(f"{name} is still used by surrogate(s) {', '.join(users)}: remove them from vars/gateway.yml first")
    var = reg[name]["vault_var"]
    write(vars_dir, [line for line in lines if not (LINE_RE.match(line) and LINE_RE.match(line).group(1) == name)])
    if vault_yml.exists():
        text = re.sub(rf"(?m)^{var}:.*\n(?:[ \t]+.*\n)*", "", vault_yml.read_text())
        tmp = vault_yml.with_suffix(".yml.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(text)
        os.replace(tmp, vault_yml)
    print(f"    {REGISTRY_FILE}: removed {name}; {vault_yml.name}: removed {var}")
    return 0


def main(argv: list[str]) -> int:
    commands = {
        "rows": (cmd_rows, 2),
        "check": (cmd_check, 2),
        "list": (cmd_list, 3),
        "stamp": (cmd_stamp, 4),
        "add": (cmd_add, 4),
        "remove": (cmd_remove, 3),
    }
    if len(argv) < 2 or argv[1] not in commands or len(argv) - 2 != commands[argv[1]][1]:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    func, _ = commands[argv[1]]
    args: list[Any] = [Path(argv[2]), *argv[3:]]
    if argv[1] in ("rows", "check", "list", "remove"):
        args[1] = Path(args[1])
    if argv[1] == "list":
        args[2] = Path(args[2])
    try:
        return func(*args)
    except Invalid as err:
        print(err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
