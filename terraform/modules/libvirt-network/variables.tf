variable "networks" {
  description = "Networks keyed by an id the VMs refer to: libvirt name, bridge, a /24 CIDR, mode and DHCP reservations."
  type = map(object({
    name   = string
    bridge = string
    cidr   = string
    mode   = string
    hosts = list(object({
      name = string
      mac  = string
      ip   = string
    }))
  }))

  validation {
    condition     = alltrue([for n in var.networks : contains(["isolated", "nat"], n.mode)])
    error_message = "Each network's mode is isolated or nat."
  }

  validation {
    condition     = alltrue([for n in var.networks : can(cidrnetmask(n.cidr)) && endswith(n.cidr, "/24")])
    error_message = "Each network's cidr is an IPv4 /24 (the DHCP layout assumes it)."
  }

  # .1 is the host, .200-.250 the dynamic range.
  validation {
    condition = alltrue(flatten([for n in var.networks : [
      for h in n.hosts : (
        cidrhost(n.cidr, tonumber(split(".", h.ip)[3])) == h.ip
        && tonumber(split(".", h.ip)[3]) >= 2 && tonumber(split(".", h.ip)[3]) < 200
      )
    ]]))
    error_message = "Each reserved IP must be inside its network, between .2 and .199."
  }
}
