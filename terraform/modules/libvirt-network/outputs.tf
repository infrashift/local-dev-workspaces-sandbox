output "names" {
  description = "Network id -> libvirt network name."
  value       = { for id, n in libvirt_network.this : id => n.name }
}

output "gateways" {
  description = "Network id -> the host's address on it (where Envoy listens on the sandbox network)."
  value       = { for id, n in var.networks : id => cidrhost(n.cidr, 1) }
}
