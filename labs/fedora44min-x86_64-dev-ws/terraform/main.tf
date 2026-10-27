locals {
  # abspath() so Terraform logs show full paths, not "../../..".
  repo_root        = abspath("${path.module}/../../..")
  lab_root         = abspath("${path.module}/..")
  lab_name         = basename(local.lab_root)
  output_data_path = "${path.module}/output-data"
  inventory_file   = "${local.output_data_path}/terraform-hosts.yml"

  # Each VM's MAC is derived from its reserved IP (52:54:00 + the last three
  # octets), so the network's DHCP reservation and the domain's NIC agree
  # without either depending on the other.
  macs = {
    for name, vm in var.vms : name => format("52:54:00:%02x:%02x:%02x",
    tonumber(split(".", vm.ip)[1]), tonumber(split(".", vm.ip)[2]), tonumber(split(".", vm.ip)[3]))
  }
}

resource "libvirt_pool" "lab" {
  name = local.lab_name
  type = "dir"

  target = {
    path = var.pool_dir
  }
}

module "network" {
  source = "../../../terraform/modules/libvirt-network"

  networks = {
    for id, net in var.networks : id => merge(net, {
      hosts = [for name, vm in var.vms : { name = name, mac = local.macs[name], ip = vm.ip } if vm.network == id]
    })
  }
}

module "vm" {
  source = "../../../terraform/modules/libvirt-vm"

  vms = {
    for name, vm in var.vms : name => {
      vcpu       = vm.vcpu
      memory_mib = vm.memory_mib
      disk_gib   = vm.disk_gib
      base_image = vm.base_image
      network    = module.network.names[vm.network]
      mac        = local.macs[name]
    }
  }
  pool_name   = libvirt_pool.lab.name
  images_dir  = var.images_dir
  libvirt_uri = var.libvirt_uri
  users = [
    { name = "admin", ssh_key_path = var.admin_ssh_key_path, sudo = true },
    { name = "dev", ssh_key_path = var.dev_ssh_key_path, sudo = false },
  ]
  cloud_init_packages = var.cloud_init_packages
}

output "provisioned_vms" {
  description = "IPv4 address of each VM (its DHCP reservation)"
  value       = { for name, vm in var.vms : name => vm.ip }
}

output "domains" {
  description = "libvirt domain of each VM (lab-provision.mk status/start/stop drive them with virsh)"
  value       = module.vm.domains
}

# Cloud-Agnostic Inventory Module
module "ansible_inventory" {
  source = "../../../terraform/modules/ansible-inventory"

  # The static config (roles) and the addresses; the module writes one group
  # per role.
  host_vars = var.vms
  host_ips  = { for name, vm in var.vms : name => vm.ip }

  inventory_path = local.inventory_file
  ssh_user       = "admin"
  ssh_key_path   = var.admin_ssh_key_path

  # The domains must exist (and have their leases) before Ansible connects.
  depends_on = [module.vm]
}
