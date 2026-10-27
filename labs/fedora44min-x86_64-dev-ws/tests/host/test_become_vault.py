"""The become vault: the operator's sudo password, ansible-vault encrypted, never in git.

Read-only: the file is checked for its shape, never decrypted.
"""

import os

import lab
import pytest
from lab import BOOTSTRAP

L = lab.lab()
FIX = f"run {BOOTSTRAP} become-vault"


@pytest.mark.parametrize("path", [L.vault_key, L.become_vault], ids=["vault_key", "become_vault"])
def test_file_is_private(path):
    assert path.is_file(), f"{path} is missing: {FIX}"
    assert path.stat().st_mode & 0o077 == 0, f"{path} is mode {path.stat().st_mode & 0o777:o}: chmod 600 it"
    assert path.stat().st_uid == os.getuid(), f"{path} is not yours"


def test_become_password_is_vault_encrypted():
    text = L.become_vault.read_text()
    assert "ansible_become_password: !vault |" in text and "$ANSIBLE_VAULT;1.1;AES256" in text, (
        f"{L.become_vault} does not hold an ansible-vault encrypted ansible_become_password: {FIX}"
    )


@pytest.mark.parametrize("path", [L.vault_key, L.become_vault], ids=["vault_key", "become_vault"])
def test_file_is_gitignored(host, path):
    """Not even the encrypted password goes to the remote: the vault key is the only thing between it and an offline guess."""
    result = host.run("git -C %s check-ignore -q %s", str(L.project_root), str(path))
    assert result.rc == 0, f"{path} is not gitignored: add it to {L.project_root}/.gitignore"
