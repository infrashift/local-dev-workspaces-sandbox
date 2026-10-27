#!/usr/bin/env bash
# ssh ProxyCommand for lab VMs (written into ~/.ssh/config.d by lab_ssh):
#
#   vm-proxy.sh <default-vm> <alias> <port>
#
# local.<lab>.<role>       -> <default-vm> (the sandbox VM)
# local.<lab>.<role>.<vm>  -> <vm>
# The address comes from the VM's libvirt DHCP lease, so the config never
# goes stale when a reservation changes.
set -euo pipefail

[ $# -eq 3 ] || { echo "Usage: $0 <default-vm> <alias> <port>" >&2; exit 2; }
DEFAULT_VM="$1"
ALIAS="$2"
PORT="$3"

case "$ALIAS" in
  *.admin | *.dev) vm="$DEFAULT_VM" ;;
  *) vm="${ALIAS##*.}" ;;
esac

ip="$("$(dirname "$0")/vm-ip.sh" "$vm")"
exec nc "$ip" "$PORT"
