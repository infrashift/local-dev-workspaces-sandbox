# labs/fedora44min-x86_64-dev-ws -- a Fedora 44 x86_64 AI sandbox on a Linux
# KVM host (libvirt), behind the zero-trust surrogate-credential gateway.
#
#   fedora-dev-1  the sandbox: Claude Code and the dev toolchains, on the
#                 isolated network; it holds surrogate credentials only
#   upstream-1    trusted test fixtures on the NAT network: the self-hosted
#                 GitHub MCP server (scenario 3) and the SCP target (scenario 4)
#
# The base image is the Fedora Cloud Base Generic qcow2 that
# `make -f lab-bootstrap.mk host TAGS=image` downloads and verifies into
# images_dir. It is ~5 GiB virtual; growpart grows the btrfs root into the
# rest of the overlay on first boot. A new respin gets a new filename: never
# replace a base image in place, every overlay depends on it.
#
# Networks, storage paths and keys come from lab-config.mk (TF_VAR_*); each
# ip is a DHCP reservation inside its network (.2-.199).
vms = {
  "fedora-dev-1" = {
    vcpu       = 4
    memory_mib = 8192
    disk_gib   = 60
    base_image = "Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
    network    = "sandbox"
    ip         = "192.168.150.10"
    roles      = ["dev_ws"]
  }
  "upstream-1" = {
    vcpu       = 1
    memory_mib = 2048
    disk_gib   = 10
    base_image = "Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
    network    = "upstream"
    ip         = "192.168.151.10"
    roles      = ["upstream"]
  }
}
