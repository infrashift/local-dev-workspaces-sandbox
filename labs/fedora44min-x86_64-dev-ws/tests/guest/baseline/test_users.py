"""The two cloud-init users: admin (passwordless sudo) and dev (none); key-only logins."""

import lab
import pytest

L = lab.lab()


def public_key(role: str) -> str:
    """'<type> <base64>' of the host-side public key; the comment may differ."""
    pub = L.ssh_key(role).with_name(L.ssh_key(role).name + ".pub")
    return " ".join(pub.read_text().split()[:2])


def test_admin_has_passwordless_sudo(admin):
    assert "wheel" in admin.user("admin").groups
    assert admin.run("sudo -n true").rc == 0, "admin cannot sudo without a password"


def test_dev_has_no_sudo(dev):
    assert "wheel" not in dev.user("dev").groups
    assert dev.run("sudo -n true").rc != 0, "dev can sudo; it must not"


@pytest.mark.parametrize("role", ["admin", "dev"])
def test_authorized_key_is_the_lab_key(admin, dev, role):
    guest = admin if role == "admin" else dev
    keys = guest.file(f"{guest.user(role).home}/.ssh/authorized_keys").content_string
    assert public_key(role) in keys, f"{role}'s authorized_keys does not hold {L.ssh_key(role)}.pub"


@pytest.mark.parametrize("role", ["admin", "dev"])
def test_password_is_locked(admin, role):
    shadow = admin.check_output("sudo -n getent shadow %s", role).split(":")
    assert shadow[1].startswith("!"), f"{role} has a usable password; cloud-init sets lock_passwd"


def test_sshd_refuses_passwords(admin):
    config = admin.check_output("sudo -n sshd -T").splitlines()
    assert "passwordauthentication no" in config, "sshd accepts passwords; cloud-init sets ssh_pwauth: false"
