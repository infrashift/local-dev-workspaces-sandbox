variable "inventory_path" {
  description = "Where to save the generated inventory file"
  type        = string
}

variable "host_ips" {
  description = "Map of Hostname -> IP Address (e.g. from module outputs)"
  type        = map(string)
}

variable "host_vars" {
  description = "Map containing host configuration. Must include a 'roles' attribute."
  # We use 'any' here to make it cloud-agnostic. 
  # It accepts a libvirt object, or an AWS object, etc as long as it has 'roles'.
  type = map(any)
}

variable "ssh_user" {
  type = string
}

variable "ssh_key_path" {
  type = string
}