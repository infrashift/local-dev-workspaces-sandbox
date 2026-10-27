variable "vms" {
  description = "Virtual machines keyed by libvirt domain name."
  type = map(object({
    vcpu       = number
    memory_mib = number
    # Overlay capacity. Must be >= the base image's VIRTUAL size (check with
    # `qemu-img info`) -- a smaller overlay truncates the disk and severs the
    # backup GPT header, and the guest firmware will not boot.
    disk_gib = number
    # Filename of the backing image inside images_dir (not a path).
    base_image = string
    # libvirt network name, and the MAC its DHCP reservation is keyed on.
    network = string
    mac     = string
  }))

  validation {
    condition     = alltrue([for v in var.vms : v.vcpu >= 1 && v.memory_mib >= 512 && v.disk_gib >= 1])
    error_message = "Each VM needs vcpu >= 1, memory_mib >= 512 and disk_gib >= 1."
  }

  validation {
    condition     = alltrue([for v in var.vms : length(regexall("/", v.base_image)) == 0])
    error_message = "base_image is a filename inside images_dir, not a path."
  }

  validation {
    condition     = alltrue([for v in var.vms : can(regex("^52:54:00(:[0-9a-f]{2}){3}$", v.mac))])
    error_message = "mac is a lowercase 52:54:00:xx:xx:xx address (the QEMU/KVM OUI)."
  }
}

variable "pool_name" {
  description = "libvirt storage pool for the OS overlays and seed ISOs."
  type        = string
}

variable "images_dir" {
  description = "Directory holding downloaded, read-only base images (written only by lab-bootstrap.mk)."
  type        = string
}

variable "users" {
  description = "Guest users cloud-init creates, each with one authorized SSH public key; sudo = passwordless sudo via wheel."
  type = list(object({
    name         = string
    ssh_key_path = string
    sudo         = optional(bool, false)
  }))

  validation {
    condition     = length(var.users) > 0 && anytrue([for u in var.users : u.sudo])
    error_message = "Declare at least one user, and at least one with sudo = true (Ansible connects as it)."
  }
}

variable "cloud_init_packages" {
  description = "Packages cloud-init installs on first boot (empty for a sandbox guest: it has no route until Ansible configures the proxy)."
  type        = list(string)
  default     = []
}

variable "uefi_loader" {
  description = "OVMF code image; a non-Secure-Boot loader."
  type        = string
  default     = "/usr/share/OVMF/OVMF_CODE_4M.fd"
}

variable "uefi_nvram_template" {
  description = "OVMF variables template matching the loader."
  type        = string
  default     = "/usr/share/OVMF/OVMF_VARS_4M.fd"
}

variable "libvirt_uri" {
  description = "libvirt connection URI (the destroy-time reaper runs virsh against it)."
  type        = string
  default     = "qemu:///system"
}

variable "ip_timeout" {
  description = "Seconds to wait for a VM's DHCP lease."
  type        = number
  default     = 300
}
