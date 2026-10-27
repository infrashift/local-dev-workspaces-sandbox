output "inventory_file" {
  description = "The full path to the generated inventory file"
  value       = local_file.inventory.filename
}

# Useful for triggers
output "inventory_content_hash" {
  description = "SHA256 hash of the inventory content"
  value       = local_file.inventory.content_sha256
}

# Debug
output "debug_unique_roles" {
  value = local.unique_roles
}