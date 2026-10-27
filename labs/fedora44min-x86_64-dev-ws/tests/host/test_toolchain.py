"""uv, the Ansible venv and collections, ruff and Terraform: the pinned versions, exactly."""

import json
import re

import lab
from lab import BOOTSTRAP

L = lab.lab()
PINS = lab.play_vars("bootstrap-host.yml")


def test_uv_is_the_pinned_version(host):
    out = host.check_output("%s --version", str(L.uv))
    assert re.match(rf"^uv {re.escape(L.uv_version)}( |$)", out), (
        f"{L.uv} reports '{out}', expected uv {L.uv_version}: run {BOOTSTRAP} uv"
    )


def test_ansible_venv_runs_the_pinned_python(host):
    python = L.venv / "bin" / "python"
    out = host.check_output("%s -c %s", str(python), "import sys; print('%d.%d' % sys.version_info[:2])")
    assert out == L.python_version, f"{python} is Python {out}, expected {L.python_version}: run {BOOTSTRAP} venv"


def test_ansible_venv_matches_requirements_lock(host):
    """Exactly the locked packages: nothing missing, nothing extra, no other version."""
    freeze = host.check_output("%s pip freeze --python %s", str(L.uv), str(L.venv / "bin" / "python"))
    installed = {lab.normalize(n): v for n, v in re.findall(r"(?m)^([^\s=]+)==(\S+)$", freeze)}
    locked = lab.pinned_packages(L.project_root / "requirements.lock")
    assert installed == locked, (
        f"{L.venv} differs from requirements.lock: "
        f"missing {sorted(locked.keys() - installed.keys())}, extra {sorted(installed.keys() - locked.keys())}, "
        f"other version {sorted(n for n in locked.keys() & installed.keys() if locked[n] != installed[n])}: "
        f"run {BOOTSTRAP} venv"
    )


def test_collections_are_the_pinned_versions():
    for name, version in lab.pinned_collections().items():
        manifest = L.collections_dir / "ansible_collections" / name.replace(".", "/") / "MANIFEST.json"
        assert manifest.is_file(), f"collection {name} is not installed in {L.collections_dir}: run {BOOTSTRAP} collections"
        installed = json.loads(manifest.read_text())["collection_info"]["version"]
        assert installed == version, (
            f"collection {name} is {installed}, requirements.yml pins {version}: run {BOOTSTRAP} collections"
        )


def test_ruff_is_the_pinned_version(host):
    ruff = L.tools_bin / "ruff"
    out = host.check_output("%s --version", str(ruff))
    assert re.search(rf"(^|\s)v?{re.escape(PINS['ruff_version'])}(\s|$)", out), (
        f"{ruff} reports '{out}', expected ruff {PINS['ruff_version']}: run {BOOTSTRAP} host TAGS=ruff"
    )


def test_terraform_is_the_pinned_version(host):
    out = host.check_output("CHECKPOINT_DISABLE=1 %s version", str(L.terraform)).splitlines()[0]
    assert re.search(rf"(^|\s)v{re.escape(PINS['terraform_version'])}(\s|$)", out), (
        f"{L.terraform} reports '{out}', expected v{PINS['terraform_version']}: run {BOOTSTRAP} terraform"
    )


def test_tools_stay_out_of_the_operators_bin():
    """The project's pins never replace the operator's own uv or Terraform."""
    assert L.tools_bin.is_relative_to(L.project_root), (
        f"TOOLS_BIN {L.tools_bin} is outside the project; it would shadow your own tools"
    )
