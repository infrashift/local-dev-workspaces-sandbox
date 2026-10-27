# libvirt networks for a lab, in one of two modes:
#   isolated  no <forward>: guests reach the host's bridge address and each
#             other, nothing else. DNS is off, so the only names a guest can
#             resolve are its /etc/hosts entries (no DNS exfiltration channel).
#   nat       the libvirt default: NAT to the host's uplink, with DNS.
# DHCP hands out fixed addresses: every VM has a reservation (MAC -> IP).
terraform {
  required_providers {
    libvirt = {
      source = "dmacvicar/libvirt"
    }
  }
}

resource "libvirt_network" "this" {
  for_each = var.networks

  name      = each.value.name
  autostart = true

  bridge = {
    name = each.value.bridge
    # libvirt XML string fields, not booleans/numbers
    stp   = "on"
    delay = "0"
  }

  forward = each.value.mode == "nat" ? {
    mode = "nat"
    nat = {
      ports = [{ start = 1024, end = 65535 }]
    }
  } : null

  dns = each.value.mode == "isolated" ? { enable = "no" } : null

  ips = [{
    address = cidrhost(each.value.cidr, 1)
    netmask = cidrnetmask(each.value.cidr)
    dhcp = {
      # Reservations sit below the range, so a stray lease never takes one.
      ranges = [{
        start = cidrhost(each.value.cidr, 200)
        end   = cidrhost(each.value.cidr, 250)
      }]
      hosts = [for h in each.value.hosts : { mac = h.mac, ip = h.ip, name = h.name }]
    }
  }]
}
