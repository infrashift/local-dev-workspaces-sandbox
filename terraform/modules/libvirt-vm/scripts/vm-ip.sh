#!/usr/bin/env bash
# Print a lab VM's IPv4 address from its libvirt DHCP lease.
#
#   vm-ip.sh <vm> [libvirt-uri]      (default uri: qemu:///system)
set -euo pipefail

[ $# -ge 1 ] || { echo "Usage: $0 <vm> [libvirt-uri]" >&2; exit 2; }
VM="$1"
URI="${2:-qemu:///system}"

ip="$(virsh -c "$URI" domifaddr --source lease "$VM" 2>/dev/null \
  | awk '$3 == "ipv4" { sub(/\/.*/, "", $4); print $4; exit }')"
[ -n "$ip" ] || { echo "No DHCP lease for $VM (is it running? make -f lab-provision.mk status)" >&2; exit 1; }
echo "$ip"
