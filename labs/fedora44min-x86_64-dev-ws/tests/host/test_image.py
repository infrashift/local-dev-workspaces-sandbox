"""The Fedora Cloud base image every overlay is built on (fedora_cloud_image).

The image must be the one terraform.tfvars names, read-only, and still the
file the signed CHECKSUM describes: an overlay breaks if its backing file
ever changes.
"""

import hashlib
import json
import re

import lab
import pytest
from lab import BOOTSTRAP

L = lab.lab()
FIX = f"run {BOOTSTRAP} host TAGS=image"
PINS = lab.play_vars("bootstrap-host.yml")
PARAMS = lab.role_params("bootstrap-host.yml", "fedora_cloud_image")
# The names follow Fedora's release layout, as in fedora_cloud_image/vars/main.yml.
RELEASE, RESPIN, ARCH = PINS["fedora_release"], PINS["fedora_respin"], PARAMS["fedora_cloud_image_arch"]
IMAGE = L.images_dir / f"Fedora-Cloud-Base-Generic-{RELEASE}-{RESPIN}.{ARCH}.qcow2"
CHECKSUM = L.images_dir / f"Fedora-Cloud-{RELEASE}-{RESPIN}-{ARCH}-CHECKSUM"
KEYRING = L.images_dir / "fedora.gpg"


def test_tfvars_names_the_bootstrapped_image():
    """terraform.tfvars and the playbook's fedora_respin are kept in step by hand."""
    assert lab.tfvars_base_images() == [IMAGE.name], (
        f"terraform.tfvars base_image {lab.tfvars_base_images()} differs from the playbook's "
        f"Fedora {RELEASE} respin {RESPIN} ({IMAGE.name}): change one to match the other"
    )


def test_image_is_present_and_read_only(host):
    image = host.file(str(IMAGE))
    assert image.is_file, f"{IMAGE} is missing: {FIX}"
    assert not image.mode & 0o222, f"{IMAGE} is mode {image.mode:o}; a base image must not be writable: chmod 0444 it"


def test_image_is_qcow2(host):
    # --force-share: a running VM holds the image open as its backing file.
    info = json.loads(host.check_output("/usr/bin/qemu-img info --force-share --output=json %s", str(IMAGE)))
    assert info["format"] == "qcow2", f"{IMAGE} is {info['format']}, not qcow2"


@pytest.fixture(scope="module")
def signed_checksum(host, tmp_path_factory) -> str:
    """The CHECKSUM text, accepted only with a valid signature from the pinned Fedora key."""
    assert CHECKSUM.is_file() and KEYRING.is_file(), f"{CHECKSUM} or {KEYRING} is missing: {FIX}"
    signed = tmp_path_factory.mktemp("checksum") / "CHECKSUM.signed"
    result = host.run("/usr/bin/gpgv --status-fd=1 --keyring=%s --output=%s %s",
                      str(KEYRING), str(signed), str(CHECKSUM))
    fpr = PINS["fedora_key_fpr"].upper()
    assert f"[GNUPG:] VALIDSIG {fpr} " in result.stdout, (
        f"{CHECKSUM} has no valid signature from the pinned key {fpr}: {result.stdout} {result.stderr}"
    )
    return signed.read_text()


def test_image_matches_the_signed_checksum(signed_checksum):
    match = re.search(rf"SHA256 \({re.escape(IMAGE.name)}\) = ([0-9a-f]{{64}})", signed_checksum)
    assert match, f"the signed {CHECKSUM.name} lists no SHA256 for {IMAGE.name}"
    digest = hashlib.sha256()
    with IMAGE.open("rb") as image:
        while chunk := image.read(1 << 20):
            digest.update(chunk)
    assert digest.hexdigest() == match[1], (
        f"{IMAGE} no longer matches its signed SHA-256; every overlay on it is suspect. "
        f"Delete it, then {FIX}"
    )
