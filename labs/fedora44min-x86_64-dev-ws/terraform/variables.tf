variable "vms" {
  description = "Map of VMs to create. Key is the hostname (and libvirt domain name)."
  type = map(object({
    vcpu       = number
    memory_mib = number
    disk_gib   = number # overlay capacity; must be >= the base image VIRTUAL size
    base_image = string # filename inside images_dir
    network    = string # a key of var.networks
    ip         = string # the VM's DHCP reservation on that network
    roles      = list(string)
  }))

  validation {
    condition     = length(var.vms) > 0
    error_message = "Declare at least one VM."
  }

  validation {
    condition     = alltrue([for v in var.vms : v.vcpu >= 1 && v.memory_mib >= 512 && v.disk_gib >= 1])
    error_message = "Each VM needs vcpu >= 1, memory_mib >= 512 and disk_gib >= 1."
  }

  validation {
    condition     = alltrue([for v in var.vms : length(v.roles) > 0])
    error_message = "Each VM needs at least one role (it becomes an Ansible inventory group)."
  }

  validation {
    condition     = alltrue([for v in var.vms : can(regex("^(\\d{1,3}\\.){3}\\d{1,3}$", v.ip))])
    error_message = "Each VM's ip is a dotted-quad IPv4 address."
  }

  validation {
    condition     = length(distinct([for v in var.vms : v.ip])) == length(var.vms)
    error_message = "Each VM needs its own ip."
  }
}

# lab-config.mk exports TF_VAR_networks: the sandbox (isolated) and upstream
# (nat) networks, defined once for Terraform, Ansible and the tests.
variable "networks" {
  description = "Lab networks keyed by id: libvirt name, bridge, /24 CIDR and mode (isolated or nat)."
  type = map(object({
    name   = string
    bridge = string
    cidr   = string
    mode   = string
  }))

  validation {
    condition     = contains(keys(var.networks), "sandbox") && try(var.networks["sandbox"].mode, "") == "isolated"
    error_message = "The lab needs a network with id \"sandbox\" in isolated mode: the zero-trust gateway is its only way out."
  }
}

variable "images_dir" {
  description = "Downloaded, read-only base images (populated by lab-bootstrap.mk)."
  type        = string
}

variable "pool_dir" {
  description = "Directory of this lab's libvirt storage pool (VM overlays and seed ISOs), created by lab-bootstrap.mk."
  type        = string
}

variable "libvirt_uri" {
  description = "libvirt connection URI."
  type        = string
  default     = "qemu:///system"
}

# Keys created by lab-bootstrap.mk (ssh role): ~/.ssh/key.d/local.<lab>@<role>
variable "admin_ssh_key_path" {
  description = "Public key for the guest 'admin' user (passwordless sudo; Ansible connects as it)."
  type        = string
}

variable "dev_ssh_key_path" {
  description = "Public key for the guest 'dev' user (day-to-day work, no sudo)."
  type        = string
}

variable "cloud_init_packages" {
  description = "Packages cloud-init installs on first boot."
  type        = list(string)
  # Empty on purpose: a sandbox guest has no route to any repository until
  # vm-baseline.yml points dnf at the gateway's CONNECT proxy.
  default = []
}

# lab-config.mk exports TF_VAR_ca_trust_dir (CA_TRUST_DIR).
variable "ca_trust_dir" {
  description = "Directory of the gateway CA certificate the sandbox guests trust; passed to the guest playbooks."
  type        = string

  validation {
    condition     = length(var.ca_trust_dir) > 0
    error_message = "Set ca_trust_dir (lab-provision.mk passes lab-config.mk's CA_TRUST_DIR)."
  }
}

# lab-config.mk exports TF_VAR_tls_inspection_dir (TLS_INSPECTION_DIR). The
# directory may be empty or missing: there is no TLS-inspecting proxy.
variable "tls_inspection_dir" {
  description = "Directory of a TLS-inspecting proxy's CA chain that every lab VM trusts (may be empty); passed to the guest playbooks."
  type        = string

  validation {
    condition     = length(var.tls_inspection_dir) > 0
    error_message = "Set tls_inspection_dir (lab-provision.mk passes lab-config.mk's TLS_INSPECTION_DIR)."
  }
}

# lab-config.mk exports TF_VAR_lab_vars (LAB_VARS): the JSON extra-vars
# document every playbook gets.
variable "lab_vars" {
  description = "JSON extra vars for the guest playbooks (gateway address, ports, CA directory, ...)."
  type        = string

  validation {
    condition     = can(jsondecode(var.lab_vars).gateway_ip)
    error_message = "lab_vars must be the JSON document lab-config.mk builds (LAB_VARS)."
  }
}
