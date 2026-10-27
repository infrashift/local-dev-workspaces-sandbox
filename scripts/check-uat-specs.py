"""Check a lab's UAT specifications (labs/<lab>/uat/) against their schema. Read-only; exit 1 on any violation.

    check-uat-specs.py <lab-dir>

What it enforces (the schema is in uat/README.md):
  * each spec under uat/<NN-suite>/ has exactly the frontmatter keys of the
    schema, a well-formed id, a file name that starts with that id, and
    `suite` equal to its directory;
  * ids are unique, and each id prefix belongs to one suite only;
  * `stack` names a playbook in ansible/playbooks/;
  * every feature is in uat/features.md and every persona in uat/personas.md,
    and every feature in the catalog is accepted by at least one spec;
  * each `automated` entry is `none`, or a test file or directory under the
    lab directory, optionally `::<function>` naming a test defined in it;
  * the body has the heading `# <id> <title>` and the five sections in order,
    and every UAT id it mentions exists.

Run by `make -f lab-provision.mk lint` with the Ansible venv's Python (PyYAML).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

KEYS = ["id", "title", "suite", "stack", "features", "personas", "priority", "disruptive", "automated", "leaves"]
SECTIONS = ["## Story", "## Preconditions", "## Steps", "## Evidence left behind", "## Notes"]
ID = re.compile(r"^UAT-([A-Z]+)-\d{2}$")
SUITE = re.compile(r"^\d{2}-[a-z0-9-]+$")
# The first column of a catalog table: | SBX-PY-01 | ... or | dev | ...
FEATURE_ROW = re.compile(r"^\| (SBX-[A-Z]+-\d{2}) \|", re.MULTILINE)
PERSONA_ROW = re.compile(r"^\| ([a-z]+) \|", re.MULTILINE)
MENTION = re.compile(r"\bUAT-[A-Z]+-\d{2}\b")


def split(path: Path) -> tuple[dict, str]:
    """(frontmatter, body) of a markdown file that opens with a --- block."""
    text = path.read_text()
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(head) or {}, body


def check_automated(lab: Path, entry: str) -> str | None:
    """None when the entry resolves, else what is wrong with it."""
    target, _, function = entry.partition("::")
    path = lab / target
    if not path.exists():
        return f"{target} does not exist"
    if function and (not path.is_file() or not re.search(rf"^def {re.escape(function)}\(", path.read_text(), re.MULTILINE)):
        return f"{target} defines no test {function}"
    return None


def main(lab: Path) -> int:
    uat = lab / "uat"
    errors: list[str] = []
    features = set(FEATURE_ROW.findall((uat / "features.md").read_text()))
    personas = set(PERSONA_ROW.findall((uat / "personas.md").read_text()))
    playbooks = {p.stem for p in (lab / "ansible" / "playbooks").glob("*.yml")}

    specs: dict[str, tuple[Path, dict, str]] = {}
    prefix_suites: dict[str, set[str]] = {}
    for path in sorted(uat.glob("*/*.md")):
        where = path.relative_to(lab)
        if not SUITE.match(path.parent.name):
            errors.append(f"{where}: {path.parent.name} is not an <NN>-<name> suite directory")
            continue
        meta, body = split(path)
        if list(meta) != KEYS:
            errors.append(f"{where}: frontmatter keys are {list(meta)}, expected {KEYS}")
            continue
        spec_id = str(meta["id"])
        match = ID.match(spec_id)
        if not match:
            errors.append(f"{where}: id {spec_id!r} is not UAT-<PREFIX>-<NN>")
            continue
        if spec_id in specs:
            errors.append(f"{where}: id {spec_id} is also {specs[spec_id][0].relative_to(lab)}")
        specs[spec_id] = (path, meta, body)
        prefix_suites.setdefault(match.group(1), set()).add(path.parent.name)
        if not path.name.startswith(f"{spec_id}-"):
            errors.append(f"{where}: the file name does not start with {spec_id}-")
        if meta["suite"] != path.parent.name:
            errors.append(f"{where}: suite {meta['suite']!r} is not its directory {path.parent.name!r}")
        if meta["stack"] not in playbooks:
            errors.append(f"{where}: stack {meta['stack']!r} is not a playbook in ansible/playbooks/")
        if meta["priority"] not in ("P1", "P2", "P3"):
            errors.append(f"{where}: priority {meta['priority']!r} is not P1, P2 or P3")
        if not isinstance(meta["disruptive"], bool):
            errors.append(f"{where}: disruptive must be true or false")
        for name in set(meta["features"] or []) - features:
            errors.append(f"{where}: feature {name} is not in uat/features.md")
        for name in set(meta["personas"] or []) - personas:
            errors.append(f"{where}: persona {name} is not in uat/personas.md")
        automated = meta["automated"]
        entries = automated if isinstance(automated, list) else [automated]
        if automated != "none":
            for entry in entries:
                problem = check_automated(lab, str(entry))
                if problem:
                    errors.append(f"{where}: automated: {problem}")
        heading = f"# {spec_id} {meta['title']}"
        if heading not in body.splitlines():
            errors.append(f"{where}: the body has no heading {heading!r}")
        found = [line for line in body.splitlines() if line in SECTIONS]
        if found != SECTIONS:
            errors.append(f"{where}: sections are {found}, expected {SECTIONS}")

    for prefix, suites in sorted(prefix_suites.items()):
        if len(suites) > 1:
            errors.append(f"uat/: the prefix UAT-{prefix} is in several suites: {sorted(suites)}")
    for spec_id, (path, _, body) in sorted(specs.items()):
        for mention in sorted(set(MENTION.findall(body)) - set(specs)):
            errors.append(f"{path.relative_to(lab)}: mentions {mention}, which no spec defines")
    accepted = {name for _, meta, _ in specs.values() for name in meta["features"] or []}
    for name in sorted(features - accepted):
        errors.append(f"uat/features.md: no spec accepts {name}")

    for error in errors:
        print(error)
    print(f"{len(specs)} UAT specs, {len(errors)} problems", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} <lab-dir>")
    sys.exit(main(Path(sys.argv[1]).resolve()))
