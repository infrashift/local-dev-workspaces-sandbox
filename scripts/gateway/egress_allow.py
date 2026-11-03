"""The operator's egress allow file (labs/<lab>/ansible/vars/egress-allow.yml): validate it, edit it
line by line, and compare it with Consul's <prefix>/allow/ keys (concepts/Egress Allow List in
Consul KV). egress-allowlist.sh is the Consul client; this file holds the rules, so the shell never
parses YAML or JSON itself.

    egress_allow.py check      <vars-dir>
    egress_allow.py plan       <vars-dir>     < Consul's allow/ keys (?recurse JSON, or empty)
    egress_allow.py list       <vars-dir>     < Consul's whole prefix (?recurse JSON)
    egress_allow.py add        <vars-dir> <kind|-> <host:port> <user|-> <reason> <expires|->
    egress_allow.py remove     <vars-dir> <host:port>
    egress_allow.py principals <vars-dir>

plan writes the changes for a person to stderr and the actions to stdout, one per line:
    PUT <entry> <value JSON>      DELETE <entry>
EGRESS_TODAY=YYYY-MM-DD overrides today's date (to rehearse an expiry).
Run with the lab venv's python (it has PyYAML), isolated: python -I.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ALLOW_FILE = "egress-allow.yml"
HOST_RE = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
USER_RE = re.compile(r"^[a-z][a-z0-9-]*$")
KINDS = ("https", "tcp", "ssh")
DEFAULT_PORT = {"https": 443, "ssh": 22}
FIELDS = {"kind", "host", "port", "user", "reason", "added", "expires"}
# One flow-mapping entry per line: the line-based edits below rely on it.
LINE_RE = re.compile(r"^\s+-\s+\{.*\}\s*(#.*)?$")


class Invalid(Exception):
    pass


def today() -> datetime.date:
    override = os.environ.get("EGRESS_TODAY")
    return datetime.date.fromisoformat(override) if override else datetime.date.today()


def as_date(value: Any, what: str) -> datetime.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        raise Invalid(f"{what}: not a YYYY-MM-DD date: {value}") from None


def gateway_hosts(vars_dir: Path) -> list[str]:
    return [route["host"] for route in yaml.safe_load((vars_dir / "gateway.yml").read_text())["gateway_routes"]]


def catalog_entries(vars_dir: Path) -> set[str]:
    catalog = yaml.safe_load((vars_dir / "egress-baseline.yml").read_text())["egress_catalog"]
    return {f"{e['host']}:{e.get('port', 443)}" for spec in catalog.values() for e in spec["entries"]}


def under_gateway(host: str, gateways: list[str]) -> str | None:
    """The gateway host this host is, sits under, or (as a wildcard) covers; None if none."""
    if host.startswith("*."):
        suffix = host[2:]
        for g in gateways:
            if g == suffix or g.endswith("." + suffix) or suffix.endswith("." + g):
                return g
        return None
    for g in gateways:
        if host == g or host.endswith("." + g):
            return g
    return None


def normalise(raw: Any, gateways: list[str], where: str) -> dict[str, Any]:
    """One file entry, checked, with its defaults filled in."""
    if not isinstance(raw, dict):
        raise Invalid(f"{where}: not a mapping: {raw!r}")
    unknown = set(raw) - FIELDS
    if unknown:
        raise Invalid(f"{where}: unknown field(s) {sorted(unknown)}; allowed: {sorted(FIELDS)}")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise Invalid(f"{where}: kind must be one of {', '.join(KINDS)} (got {kind!r})")
    host = str(raw.get("host", ""))
    if not HOST_RE.match(host):
        raise Invalid(f"{where}: host is not a lower-case DNS name, IPv4 address or *.<suffix>: {host!r}")
    if host.startswith("*.") and kind != "https":
        raise Invalid(f"{where}: a wildcard host is for kind https only: {host}")
    gateway = under_gateway(host, gateways)
    if gateway:
        raise Invalid(
            f"{where}: {host} is, or is under, the gateway host {gateway}. The TLS gateway serves it "
            "(vars/gateway.yml), and the guests' NO_PROXY sends it there, never through the tunnel"
        )
    port = raw.get("port", DEFAULT_PORT.get(kind))
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise Invalid(f"{where}: port must be 1-65535" + (" (kind tcp has no default)" if port is None else f": {port!r}"))
    if kind == "tcp" and port in (22, 443):
        raise Invalid(f"{where}: {host}:{port} as kind tcp; use kind {'ssh' if port == 22 else 'https'}")
    user = raw.get("user")
    if kind == "ssh":
        if not isinstance(user, str) or not USER_RE.match(user):
            raise Invalid(f"{where}: kind ssh needs user, a login name (^[a-z][a-z0-9-]*$): {user!r}")
    elif user is not None:
        raise Invalid(f"{where}: user is for kind ssh only")
    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise Invalid(f"{where}: reason is required")
    if re.search(r'["\\]', reason):
        raise Invalid(f'{where}: the reason may not contain " or \\')
    entry = {"kind": kind, "host": host, "port": port, "reason": reason}
    if user:
        entry["user"] = user
    for field in ("added", "expires"):
        value = as_date(raw.get(field), f"{where}: {field}")
        if value:
            entry[field] = value
    return entry


def load(vars_dir: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """(the file's lines, its entries checked): raises Invalid on the first broken rule."""
    return parse(vars_dir, (vars_dir / ALLOW_FILE).read_text())


def parse(vars_dir: Path, text: str) -> tuple[list[str], list[dict[str, Any]]]:
    path = vars_dir / ALLOW_FILE
    doc = yaml.safe_load(text) or {}
    raw = doc.get("egress_allow")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise Invalid(f"{path}: egress_allow must be a list")
    lines = text.splitlines(keepends=True)
    flow = [line for line in lines if LINE_RE.match(line)]
    if len(flow) != len(raw):
        raise Invalid(f"{path}: write each egress_allow entry on one line, as {{ kind: ..., host: ..., ... }}")
    gateways = gateway_hosts(vars_dir)
    entries, seen = [], set()
    for n, item in enumerate(raw, 1):
        entry = normalise(item, gateways, f"{ALLOW_FILE} entry {n}")
        name = key(entry)
        if name in seen:
            raise Invalid(f"{ALLOW_FILE} entry {n}: {name} appears twice")
        seen.add(name)
        entries.append(entry)
    return lines, entries


def key(entry: dict[str, Any]) -> str:
    return f"{entry['host']}:{entry['port']}"


def expired(entry: dict[str, Any]) -> bool:
    return bool(entry.get("expires")) and entry["expires"] <= today()


def value(entry: dict[str, Any]) -> str:
    """The Consul value for an entry: what list shows, and what plan compares."""
    out = {k: (v.isoformat() if isinstance(v, datetime.date) else v) for k, v in entry.items() if k not in ("host", "port")}
    out["source"] = "file"
    return json.dumps(out, sort_keys=True, separators=(",", ":"))


def consul_kv(stdin: str, marker: str) -> dict[str, str]:
    """{<rest of the key after marker>: decoded value} from a Consul ?recurse response."""
    if not stdin.strip():
        return {}
    out = {}
    for kv in json.loads(stdin):
        if marker in kv["Key"]:
            rest = kv["Key"].split(marker, 1)[1]
            if rest and not rest.endswith("/"):
                out[rest] = base64.b64decode(kv["Value"] or "").decode()
    return out


def parse_entry(name: str) -> tuple[str, int]:
    host, _, port = name.rpartition(":")
    if not host or not port.isdigit():
        raise Invalid(f"Not <host>:<port> or *.<suffix>:<port>: {name}")
    return host, int(port)


def same_value(a: str, b: str) -> bool:
    try:
        return json.loads(a) == json.loads(b)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_check(vars_dir: Path) -> int:
    _, entries = load(vars_dir)
    baseline = catalog_entries(vars_dir)
    for entry in entries:
        if key(entry) in baseline:
            print(f"warning: {key(entry)} is in the baseline catalog already", file=sys.stderr)
        if expired(entry):
            print(f"warning: {key(entry)} expired on {entry['expires']}: remove its line (deny HOST={key(entry)})",
                  file=sys.stderr)
    print(f"{ALLOW_FILE}: {len(entries)} entries, valid", file=sys.stderr)
    return 0


def cmd_plan(vars_dir: Path, stdin: str) -> int:
    _, entries = load(vars_dir)
    desired = {key(e): value(e) for e in entries if not expired(e)}
    current = consul_kv(stdin, "/allow/")
    actions, changes = [], []
    for name in sorted(desired.keys() - current.keys()):
        changes.append(f"  + {name}")
        actions.append(f"PUT {name} {desired[name]}")
    for name in sorted(desired.keys() & current.keys()):
        if not same_value(desired[name], current[name]):
            changes.append(f"  ~ {name}  (metadata)")
            actions.append(f"PUT {name} {desired[name]}")
    for name in sorted(current.keys() - desired.keys()):
        why = "expired" if any(key(e) == name and expired(e) for e in entries) else "not in the file"
        changes.append(f"  - {name}  ({why})")
        actions.append(f"DELETE {name}")
    if changes:
        print(f"Consul allow/ -> {ALLOW_FILE}:", *changes, sep="\n", file=sys.stderr)
    for line in actions:
        print(line)
    return 0


def cmd_list(vars_dir: Path, stdin: str) -> int:
    _, entries = load(vars_dir)
    in_file = {key(e): e for e in entries}
    current = consul_kv(stdin, "/allow/")
    rows = []
    for kv in json.loads(stdin) if stdin.strip() else []:
        rel = kv["Key"].split("/baseline/", 1)
        if len(rel) == 2 and rel[1] and not rel[1].endswith("/"):
            category, entry = rel[1].split("/", 1)
            meta = json.loads(base64.b64decode(kv["Value"] or "") or "{}")
            rows.append((entry, "https", "baseline:" + category, "", meta.get("reason", "")))
    for name in sorted(in_file.keys() | current.keys()):
        entry = in_file.get(name)
        if entry is None:
            meta = json.loads(current[name] or "{}")
            rows.append((name, meta.get("kind", "?"), "operator", "drift: not in the file", meta.get("reason", "")))
            continue
        if expired(entry):
            state = f"expired {entry['expires']}" + (", still in Consul" if name in current else "")
        elif name not in current:
            state = "drift: not in Consul"
        elif not same_value(value(entry), current[name]):
            state = "drift: metadata"
        else:
            state = f"until {entry['expires']}" if entry.get("expires") else ""
        kind = entry["kind"] + (f":{entry['user']}" if entry.get("user") else "")
        rows.append((name, kind, "operator", state, entry["reason"]))
    widths = [max([len(r[i]) for r in rows] + [5]) for i in range(4)]
    for row in sorted(rows):
        print("  ".join(f"{c:<{widths[i]}}" for i, c in enumerate(row[:4])) + "  " + row[4])
    drift = sum(1 for r in rows if r[3].startswith("drift") or "still in Consul" in r[3])
    print(f"{len(rows)} entries" + (f", {drift} out of step: make -f lab-gateway.mk allow-sync" if drift else ""),
          file=sys.stderr)
    return 0


def cmd_add(vars_dir: Path, kind: str, name: str, user: str, reason: str, expires: str) -> int:
    lines, entries = load(vars_dir)
    host, port = parse_entry(name)
    if kind == "-":
        kind = {443: "https", 22: "ssh"}.get(port, "tcp")
    raw: dict[str, Any] = {"kind": kind, "host": host, "port": port, "reason": reason, "added": today()}
    if user != "-":
        raw["user"] = user
    if expires != "-":
        raw["expires"] = expires
    entry = normalise(raw, gateway_hosts(vars_dir), name)
    if entry.get("expires") and expired(entry):
        raise Invalid(f"{name}: expires {entry['expires']} is not in the future")
    if any(key(e) == name for e in entries):
        raise Invalid(f"{name} is in {ALLOW_FILE} already: deny it first to change it")
    if name in catalog_entries(vars_dir):
        print(f"warning: {name} is in the baseline catalog already", file=sys.stderr)
    fields = [f"kind: {entry['kind']}", f'host: "{host}"', f"port: {port}"]
    if entry.get("user"):
        fields.append(f"user: {entry['user']}")
    fields += [f'reason: "{reason}"', f"added: {entry['added']}"]
    if entry.get("expires"):
        fields.append(f"expires: {entry['expires']}")
    new = "  - { " + ", ".join(fields) + " }\n"
    # After the last entry, or straight after the egress_allow: line.
    flow = [i for i, line in enumerate(lines) if LINE_RE.match(line)]
    if flow:
        at = flow[-1] + 1
    else:
        at = next(i for i, line in enumerate(lines) if re.match(r"^egress_allow:", line))
        lines[at] = "egress_allow:\n"
        at += 1
    write(vars_dir, lines[:at] + [new] + lines[at:])
    print(f"{ALLOW_FILE}: added {name} ({entry['kind']})", file=sys.stderr)
    return 0


def cmd_remove(vars_dir: Path, name: str) -> int:
    lines, _ = load(vars_dir)
    host, port = parse_entry(name)
    keep, removed = [], 0
    for line in lines:
        if LINE_RE.match(line):
            entry = yaml.safe_load(line.split("-", 1)[1])
            if str(entry.get("host")) == host and entry.get("port", DEFAULT_PORT.get(entry.get("kind"))) == port:
                removed += 1
                continue
        keep.append(line)
    if not removed:
        hint = (" (a baseline entry: remove it from egress-baseline.yml)" if name in catalog_entries(vars_dir) else "")
        print(f"{name} is not on the operator allow list{hint}", file=sys.stderr)
        return 1
    if not any(LINE_RE.match(line) for line in keep):
        keep = [re.sub(r"^egress_allow:\s*$", "egress_allow: []", line) for line in keep]
    write(vars_dir, keep)
    print(f"{ALLOW_FILE}: removed {name}", file=sys.stderr)
    return 0


def cmd_principals(vars_dir: Path) -> int:
    _, entries = load(vars_dir)
    users = sorted({e["user"] for e in entries if e["kind"] == "ssh"})
    print(",".join(users))
    return 0


def write(vars_dir: Path, lines: list[str]) -> None:
    """Write the file atomically, once the new text passes every rule."""
    text = "".join(lines)
    parse(vars_dir, text)
    path = vars_dir / ALLOW_FILE
    tmp = path.with_suffix(".yml.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    cmd, vars_dir, args = argv[1], Path(argv[2]), argv[3:]
    try:
        if cmd == "check" and not args:
            return cmd_check(vars_dir)
        if cmd == "plan" and not args:
            return cmd_plan(vars_dir, sys.stdin.read())
        if cmd == "list" and not args:
            return cmd_list(vars_dir, sys.stdin.read())
        if cmd == "add" and len(args) == 5:
            return cmd_add(vars_dir, *args)
        if cmd == "remove" and len(args) == 1:
            return cmd_remove(vars_dir, args[0])
        if cmd == "principals" and not args:
            return cmd_principals(vars_dir)
    except Invalid as err:
        print(err, file=sys.stderr)
        return 1
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
