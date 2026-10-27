terraform {
  required_version = ">= 1.13.0"

  required_providers {
    libvirt = {
      source = "dmacvicar/libvirt"
      # >= 0.9.8 for `running = true` drift reconciliation; 0.10 may change
      # the XML-mirroring schema again.
      version = ">= 0.9.8, < 0.10.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "libvirt" {
  uri = var.libvirt_uri
}
