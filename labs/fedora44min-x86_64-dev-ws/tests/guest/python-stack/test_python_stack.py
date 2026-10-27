"""python-stack.yml, on top of the baseline: run with STACK=python-stack.

Every version is read from the role parameters in python-stack.yml. The user
lane is checked as dev in a login shell, so each tool must also be the one on
dev's PATH, not merely present in ~/.local/bin.
"""

import json
import re
import shlex

import lab
import pytest
from lab import PROVISION

PLAYBOOK = "python-stack.yml"
FIX = f"run {PROVISION} play PLAYBOOK=python-stack"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def pin(role: str, key: str) -> str:
    return re.escape(str(lab.role_params(PLAYBOOK, role)[key]))


# tool -> (version arguments, pattern its output must match), as each role's VERIFICATION expects.
TOOLS = {
    "uv": ("--version", rf"^uv {pin('uv', 'uv_version')}( |$)"),
    "ruff": ("--version", rf"^ruff {pin('ruff', 'ruff_version')}$"),
    "jq": ("--version", rf"^jq-{pin('jq', 'jq_version')}$"),
    "grype": ("version", rf"(?m)^Version:\s+{pin('grype', 'grype_version')}$"),
    "syft": ("version", rf"(?m)^Version:\s+{pin('syft', 'syft_version')}$"),
    "nvim": ("--version", rf"^NVIM v{pin('neovim', 'neovim_version')}$"),
    "pyrefly": ("--version", rf"(?m)^pyrefly {pin('pyrefly', 'pyrefly_version')}(\s|$)"),
    "basedpyright": ("--version", rf"(?m)^basedpyright {pin('python_tools', 'python_tools_basedpyright_version')}(\s|$)"),
    "ansible-lint": ("--version", rf"(?m)^ansible-lint {pin('ansible_tools', 'ansible_tools_ansible_lint_version')}(\s|$)"),
    "tree-sitter": ("--version", rf"^tree-sitter {pin('lazyvim', 'lazyvim_tree_sitter_version')}(\s|$)"),
    "stylua": ("--version", rf"^stylua {pin('lazyvim', 'lazyvim_stylua_version')}$"),
    "shfmt": ("--version", rf"^v{pin('lazyvim', 'lazyvim_shfmt_version')}$"),
}
CLAUDE_VERSION = str(lab.role_params(PLAYBOOK, "claude_code")["claude_code_version"])
CLAUDE_PINNED = re.fullmatch(r"\d+\.\d+\.\d+", CLAUDE_VERSION) is not None
if CLAUDE_PINNED:
    TOOLS["claude"] = ("--version", rf"^{re.escape(CLAUDE_VERSION)} ")


def login(dev, script: str):
    """Run a script in dev's login shell, the environment ssh sessions get."""
    return dev.run("NO_COLOR=1 bash -lc %s", script)


# ---------------------------------------------------------------------------
# User lane (dev)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_tool_is_the_pinned_version(dev, tool):
    args, pattern = TOOLS[tool]
    found = login(dev, f"command -v {tool}").stdout.strip()
    expected = f"{dev.user().home}/.local/bin/{tool}"
    assert found == expected, f"{tool} on dev's PATH is '{found}', not {expected}: {FIX}"
    result = login(dev, f"{tool} {args}")
    out = ANSI.sub("", result.stdout).strip()
    # nvim prints its build details after the first line.
    out = out.splitlines()[0] if tool == "nvim" and out else out
    assert result.rc == 0 and re.search(pattern, out), f"{tool} {args} said '{out}': {FIX}"


def test_claude_code_auto_updater_is_off(dev):
    if not CLAUDE_PINNED:
        pytest.skip(f"claude_code_version is the {CLAUDE_VERSION} channel, which keeps its updater")
    assert login(dev, 'echo "$DISABLE_AUTOUPDATER"').stdout.strip() == "1", (
        f"DISABLE_AUTOUPDATER is not set in dev's login shell; the updater would replace the pinned "
        f"{CLAUDE_VERSION}: {FIX}"
    )


def test_lazyvim_plugins_are_at_their_locked_commits(dev):
    """The lockfile is the role's, and every plugin the spec names is checked out at its commit.

    The lockfile covers every supported extra, but lazy.nvim installs only what this image's
    spec names (a lang.java plugin is absent from a Python image by design), so the plugins
    checked are the ones the role itself restores: the spec's, asked of lazy.nvim with the
    role's own query.
    """
    shipped = json.loads((lab.lab().roles_dir("guest") / "lazyvim" / "files" / "nvim" / "lazy-lock.json").read_text())
    home = dev.user().home
    installed = json.loads(dev.file(f"{home}/.config/nvim/lazy-lock.json").content_string)
    assert installed == shipped, f"~/.config/nvim/lazy-lock.json differs from the role's: {FIX}"
    query = lab.role_vars("guest", "lazyvim")["lazyvim_lua_spec_plugins"]
    asked = dev.run(f"{home}/.local/bin/nvim --headless %s +qa", f"+lua {query}")
    found = re.findall(r"SPEC_PLUGINS=(.*)", asked.stdout + asked.stderr)
    assert found, f"lazy.nvim did not report its spec (rc {asked.rc}): {asked.stderr.strip()}: {FIX}"
    spec = set(json.loads(found[0])) & set(shipped)
    assert {"lazy.nvim", "LazyVim"} <= spec, f"the spec lacks lazy.nvim or LazyVim: {sorted(spec)}: {FIX}"
    script = "; ".join(
        f"printf '%s %s\\n' {shlex.quote(name)} \"$(git -C {shlex.quote(f'{home}/.local/share/nvim/lazy/{name}')}"
        " rev-parse HEAD 2>/dev/null)\""
        for name in sorted(spec)
    )
    heads = dict((line.split(" ", 1) + [""])[:2] for line in dev.check_output(script).splitlines())
    off = {name: heads.get(name) for name in spec if heads.get(name) != shipped[name]["commit"]}
    assert not off, f"plugins not at their locked commit (name: HEAD): {off}: {FIX}"


# ---------------------------------------------------------------------------
# System lane
# ---------------------------------------------------------------------------
def test_podman_runs_rootless_for_dev(admin, dev):
    user = lab.role_params(PLAYBOOK, "podman")["podman_rootless_user"]
    if user == "{{ guest_user }}":
        user = lab.group_vars()["guest_user"]
    assert user == "dev", f"python-stack.yml runs podman for {user}; these tests connect as dev"
    info = json.loads(dev.check_output("podman info --format json"))
    assert info["host"]["security"]["rootless"], f"podman is not rootless for dev: {FIX}"
    assert info["store"]["graphDriverName"] == "overlay", f"podman's storage driver is {info['store']['graphDriverName']}"
    assert admin.file(f"/var/lib/systemd/linger/{user}").exists, f"{user} has no lingering user manager: {FIX}"


def test_podman_api_socket_is_the_users(admin, dev):
    assert dev.run("systemctl --user is-active podman.socket").stdout.strip() == "active", (
        f"dev's podman.socket is not active: {FIX}"
    )
    assert admin.run("systemctl is-active podman.socket").stdout.strip() != "active", (
        f"root's podman.socket is active in rootless mode: {FIX}"
    )


def test_tmux_config_loads(dev):
    const = lab.role_vars("guest", "tmux")
    # A private server (-L), so a running dev session is never touched.
    result = dev.run(
        "tmux -L ai-sandbox-verify -f /dev/null start-server \\; source-file -n %s \\; kill-server",
        const["tmux_conf_path"],
    )
    assert result.rc == 0, f"{const['tmux_conf_path']} does not load: {result.stderr.strip()}: {FIX}"
    assert dev.file(const["tmux_session_bin"]).mode & 0o111, f"{const['tmux_session_bin']} is not executable: {FIX}"
    assert dev.file(const["tmux_profile_hook"]).is_file, f"{const['tmux_profile_hook']} is missing: {FIX}"
