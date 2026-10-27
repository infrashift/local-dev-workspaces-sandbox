"""apt packages, KVM, the libvirt groups and the OVMF pair VMs boot from (linux_host_packages)."""

import os
import stat

import lab
import pytest
from lab import BOOTSTRAP

L = lab.lab()
FIX = f"run {BOOTSTRAP} host TAGS=packages"
PINS = lab.play_vars("bootstrap-host.yml")


@pytest.mark.parametrize("package", PINS["apt_packages"])
def test_package_is_installed(host, package):
    assert host.package(package).is_installed, f"{package} is not installed: {FIX}"


def test_kvm_is_available():
    assert os.path.exists("/dev/kvm") and stat.S_ISCHR(os.stat("/dev/kvm").st_mode), (
        "/dev/kvm is missing: enable VT-x/AMD-V and load kvm_intel/kvm_amd"
    )
    assert os.access("/dev/kvm", os.R_OK | os.W_OK), "/dev/kvm is not usable by you: join the kvm group"


@pytest.mark.parametrize("group", PINS["operator_groups"])
def test_operator_is_in_group(host, group):
    groups = host.check_output("id -nG").split()
    assert group in groups, f"you are not in {group}: sudo usermod -aG {group} $USER, then log in again"


def test_libvirt_system_is_reachable(host):
    """lab-provision.mk drives qemu:///system without sudo."""
    result = host.run("virsh -c %s uri", L.libvirt_uri)
    assert result.rc == 0 and result.stdout.strip() == L.libvirt_uri, (
        f"virsh cannot reach {L.libvirt_uri}: {result.stderr.strip()} (is libvirtd running? are you in libvirt?)"
    )


@pytest.mark.parametrize("path", PINS["ovmf_firmware"])
def test_ovmf_firmware_exists(path):
    assert os.path.isfile(path), f"{path} is missing: {FIX}"


def test_gpgv_is_available():
    """hashicorp_release and fedora_cloud_image verify signatures with it (envoy_release too), and so does test_image.py."""
    assert os.access("/usr/bin/gpgv", os.X_OK), f"/usr/bin/gpgv is missing: {FIX}"
