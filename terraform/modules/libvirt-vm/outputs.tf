output "domains" {
  description = "VM name -> libvirt domain name."
  value       = { for name, d in libvirt_domain.this : name => d.name }
}

output "macs" {
  description = "VM name -> NIC MAC address."
  value       = { for name, vm in var.vms : name => vm.mac }
}
