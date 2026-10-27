"""VM storage directories (vm_storage): the operator's, and traversable by libvirt-qemu."""

import os
import stat

import lab
import pytest
from lab import BOOTSTRAP

L = lab.lab()


@pytest.mark.parametrize(
    "path", [L.images_dir, L.pools_dir, L.lab_pool], ids=["images_dir", "pools_dir", "lab_pool"]
)
def test_directory_is_writable_and_traversable(path):
    fix = f"run {BOOTSTRAP} host TAGS=storage"
    assert path.is_dir() and os.access(path, os.W_OK), f"{path} is not a writable directory: {fix}"
    mode = path.stat().st_mode
    assert mode & stat.S_IROTH and mode & stat.S_IXOTH, (
        f"{path} is mode {mode & 0o777:o}; QEMU runs as libvirt-qemu and must traverse it: {fix}"
    )
