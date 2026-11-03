"""Read-only Day 2 reports on the gateway (concepts/Operator Interfaces). Each reads its input on
stdin, so the make targets choose how it is fetched (journalctl, sudo, ssh-keygen):

    gateway_report.py denied <gateway.yml>           < journalctl -u envoy -o cat
    gateway_report.py audit <since>                  < /var/log/vault/audit.log
    gateway_report.py agent <min-seconds>            < ssh-keygen -L -f <certificate>

denied  the CONNECTs the tunnel refused (403), by host:port, with how often and when last;
        gateway hosts are marked, since they go through the TLS gateway instead.
audit   break-glass activity in Vault's audit log since <since> (e.g. 24h, 7d): the token
        mints (who, why), the unwraps, and every request a break-glass token made.
agent   the sandbox agent certificate's principals and validity. Exits 1 when it is missing
        or expired, 3 when fewer than <min-seconds> remain (lab-sandbox-ops.mk ssh renews it).
"""

from __future__ import annotations

import collections
import datetime
import json
import re
import sys
from pathlib import Path

import yaml


def cmd_denied(gateway_yml: Path) -> int:
    gateways = [r["host"] for r in yaml.safe_load(gateway_yml.read_text())["gateway_routes"]]
    count: collections.Counter[str] = collections.Counter()
    for line in sys.stdin:
        # tunnel <client> CONNECT <authority> <code> <flags> <bytes> <duration>
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "tunnel" and parts[2] == "CONNECT" and parts[4] == "403":
            count[parts[3]] += 1
    if not count:
        print("The tunnel refused nothing in this window.")
        return 0
    width = max(len(k) for k in count)
    for entry, n in count.most_common():
        host = entry.rsplit(":", 1)[0]
        note = ""
        if any(host == g or host.endswith("." + g) for g in gateways):
            note = "gateway host: reach it through the TLS gateway, never the tunnel"
        print(f"{n:>6}  {entry:<{width}}  {note}".rstrip())
    print(
        f"{sum(count.values())} refused CONNECTs to {len(count)} host:port(s). To allow one:\n"
        '  make -f lab-gateway.mk allow HOST=<host:port> REASON="why"',
        file=sys.stderr,
    )
    return 0


def since_cutoff(since: str) -> datetime.datetime:
    m = re.fullmatch(r"(\d+)([mhd])", since)
    if not m:
        raise SystemExit(f"SINCE must be <n>m, <n>h or <n>d (got {since})")
    seconds = int(m[1]) * {"m": 60, "h": 3600, "d": 86400}[m[2]]
    return datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=seconds)


def cmd_audit(since: str) -> int:
    cutoff = since_cutoff(since)
    rows = []
    for line in sys.stdin:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "response":
            continue
        when = datetime.datetime.fromisoformat(entry["time"])
        if when < cutoff:
            continue
        auth = entry.get("auth") or {}
        request = entry.get("request") or {}
        path = request.get("path", "")
        name = auth.get("display_name", "")
        if "break-glass" in name:
            meta = auth.get("metadata") or {}
            who = meta.get("user", name)
            rows.append((when, who, f"{request.get('operation', '')} {path}"))
        elif path == "sys/wrapping/unwrap":
            rows.append((when, name or "?", "unwrap (a break-glass token, or another wrapped response)"))
        elif path.startswith("auth/token/create") and "break-glass" in json.dumps(entry.get("response") or {}):
            meta = ((entry.get("response") or {}).get("auth") or {}).get("metadata") or {}
            rows.append((when, meta.get("user", "?"), f"break-glass token minted: {meta.get('reason', '')}"))
    if not rows:
        print(f"No break-glass activity in the last {since}.")
        return 0
    for when, who, what in sorted(rows):
        print(f"{when:%Y-%m-%d %H:%M:%S}Z  {who:<20}  {what}")
    print(f"{len(rows)} event(s) in the last {since} (values in the log are HMACed).", file=sys.stderr)
    return 0


def cmd_agent(min_seconds: str) -> int:
    text = sys.stdin.read()
    principals = re.search(r"Principals:\s*\n((?:[ \t]+\S+\n)*?)[ \t]*Critical", text)
    valid = re.search(r"Valid: from (\S+) to (\S+)", text)
    if not valid:
        print("The sandbox agent has no certificate: make -f lab-gateway.mk agent-cert")
        return 1
    until = datetime.datetime.fromisoformat(valid[2])
    left = int((until - datetime.datetime.now()).total_seconds())
    names = ", ".join(principals[1].split()) if principals else "none"
    state = "EXPIRED" if left <= 0 else f"{left // 3600}h{left % 3600 // 60:02d}m left"
    print(f"principals {names}; valid until {valid[2]} ({state})")
    if left <= 0:
        return 1
    return 3 if left < int(min_seconds) else 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "denied":
        return cmd_denied(Path(argv[2]))
    if len(argv) == 3 and argv[1] == "audit":
        return cmd_audit(argv[2])
    if len(argv) == 3 and argv[1] == "agent":
        return cmd_agent(argv[2])
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
