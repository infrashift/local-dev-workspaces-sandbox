"""The guest OS, cloud-init's first boot, and the resources terraform.tfvars gave the VM."""

import lab
from lab import PROVISION

GIB = 1 << 30


# The lab's architecture, as lab-config.mk's PYTHON_PLATFORM names it.
ARCH = lab.lab().python_platform.split("-", 1)[0]


def test_is_fedora_44_of_the_lab_architecture(admin):
    info = admin.system_info
    got = (info.distribution, info.release, info.arch)
    assert got == ("fedora", "44", ARCH), f"expected Fedora 44 {ARCH}, got {got}"


def test_hostname_is_the_vm_name(admin, vm):
    """The short name: cloud-init gives the guest a .local domain."""
    assert admin.check_output("hostname -s") == vm


def test_cloud_init_finished(admin):
    # rc 2 is "done with recoverable errors" (an early hostnamectl call on
    # Fedora 44), which vm-baseline.yml also accepts; rc 1 is a failure.
    # Root only: cloud-init's runtime state is not world-readable.
    result = admin.run("sudo cloud-init status --long")
    assert result.rc in (0, 2) and "status: done" in result.stdout, (
        f"cloud-init did not finish: rc={result.rc} {result.stdout}"
    )


def test_vcpus_match_tfvars(admin, spec):
    assert int(admin.check_output("nproc")) == spec["vcpu"]


def test_memory_matches_tfvars(admin, spec):
    """MemTotal is the RAM less what firmware and the kernel reserve: allow 15%."""
    mem_kib = int(admin.check_output("awk '/^MemTotal:/ { print $2 }' /proc/meminfo"))
    expected_kib = spec["memory_mib"] * 1024
    assert 0.85 * expected_kib <= mem_kib <= expected_kib, (
        f"MemTotal is {mem_kib} KiB; terraform.tfvars gives {spec['memory_mib']} MiB"
    )


def test_root_filesystem_was_grown(admin, spec):
    """growpart grows the ~5 GiB image's root into the overlay; the boot partitions take the rest."""
    size = int(admin.check_output("df --block-size=1 --output=size / | tail -n 1"))
    assert size >= 0.9 * spec["disk_gib"] * GIB, (
        f"/ is {size / GIB:.1f} GiB of a {spec['disk_gib']} GiB disk: growpart did not run "
        f"(see {PROVISION} console)"
    )


def test_inventory_lists_the_vm(vm):
    """vm-baseline.yml and the stacks reach the VM through this file."""
    inventory = lab.lab().tf_dir / "output-data" / "terraform-hosts.yml"
    assert f"    {vm}:" in inventory.read_text(), f"{inventory} has no host {vm}: run {PROVISION} apply"
