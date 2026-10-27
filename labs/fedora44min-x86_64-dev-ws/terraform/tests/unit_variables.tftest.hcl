# Input-validation unit tests. Plan-only, against a mock libvirt provider: no
# network, pool or VM is created, and libvirtd is never contacted, so they run
# on any host: make -f lab-provision.mk test

mock_provider "libvirt" {}

variables {
  admin_ssh_key_path = "tests/fixtures/id_test.pub"
  dev_ssh_key_path   = "tests/fixtures/id_test.pub"
  images_dir         = "/tmp/ai-sandbox-test/images"
  pool_dir           = "/tmp/ai-sandbox-test/pools/lab"
  ca_trust_dir       = "tests/fixtures"
  tls_inspection_dir = "tests/fixtures/no-tls-inspection"
  lab_vars           = "{\"gateway_ip\":\"192.168.250.1\"}"
  networks = {
    sandbox  = { name = "t-sandbox", bridge = "virbr250", cidr = "192.168.250.0/24", mode = "isolated" }
    upstream = { name = "t-upstream", bridge = "virbr251", cidr = "192.168.251.0/24", mode = "nat" }
  }
  vms = {
    "test-vm" = {
      vcpu       = 1
      memory_mib = 1024
      disk_gib   = 10
      base_image = "base.qcow2"
      network    = "sandbox"
      ip         = "192.168.250.10"
      roles      = ["test"]
    }
  }
}

run "valid_config_plans" {
  command = plan

  assert {
    condition     = local.macs["test-vm"] == "52:54:00:a8:fa:0a"
    error_message = "The MAC must be 52:54:00 plus the reserved IP's last three octets."
  }

  assert {
    condition     = module.network.gateways["sandbox"] == "192.168.250.1"
    error_message = "The host's address on a network must be its .1."
  }

  assert {
    condition     = libvirt_pool.lab.target.path == "/tmp/ai-sandbox-test/pools/lab"
    error_message = "The lab's pool must live in pool_dir."
  }
}

run "zero_disk_rejected" {
  command = plan

  variables {
    vms = {
      "test-vm" = {
        vcpu       = 1
        memory_mib = 1024
        disk_gib   = 0
        base_image = "base.qcow2"
        network    = "sandbox"
        ip         = "192.168.250.10"
        roles      = ["test"]
      }
    }
  }

  expect_failures = [var.vms]
}

run "missing_roles_rejected" {
  command = plan

  variables {
    vms = {
      "test-vm" = {
        vcpu       = 1
        memory_mib = 1024
        disk_gib   = 10
        base_image = "base.qcow2"
        network    = "sandbox"
        ip         = "192.168.250.10"
        roles      = []
      }
    }
  }

  expect_failures = [var.vms]
}

run "duplicate_ip_rejected" {
  command = plan

  variables {
    vms = {
      "a" = { vcpu = 1, memory_mib = 1024, disk_gib = 10, base_image = "b.qcow2", network = "sandbox", ip = "192.168.250.10", roles = ["t"] }
      "b" = { vcpu = 1, memory_mib = 1024, disk_gib = 10, base_image = "b.qcow2", network = "sandbox", ip = "192.168.250.10", roles = ["t"] }
    }
  }

  expect_failures = [var.vms]
}

# The zero-trust design rests on the sandbox network having no route out.
run "nat_sandbox_rejected" {
  command = plan

  variables {
    networks = {
      sandbox = { name = "t-sandbox", bridge = "virbr250", cidr = "192.168.250.0/24", mode = "nat" }
    }
  }

  expect_failures = [var.networks]
}

run "malformed_lab_vars_rejected" {
  command = plan

  variables {
    lab_vars = "not json"
  }

  expect_failures = [var.lab_vars]
}

# The checks below live in the modules' own variable validations, so these
# runs plan the modules directly.
run "base_image_path_rejected" {
  command = plan

  module {
    source = "../../../terraform/modules/libvirt-vm"
  }

  variables {
    pool_name = "lab"
    users     = [{ name = "admin", ssh_key_path = "tests/fixtures/id_test.pub", sudo = true }]
    vms = {
      "test-vm" = {
        vcpu       = 1
        memory_mib = 1024
        disk_gib   = 10
        base_image = "/tmp/base.qcow2"
        network    = "t-sandbox"
        mac        = "52:54:00:a8:fa:0a"
      }
    }
  }

  expect_failures = [var.vms]
}

run "no_sudo_user_rejected" {
  command = plan

  module {
    source = "../../../terraform/modules/libvirt-vm"
  }

  variables {
    pool_name = "lab"
    users     = [{ name = "dev", ssh_key_path = "tests/fixtures/id_test.pub", sudo = false }]
    vms = {
      "test-vm" = {
        vcpu       = 1
        memory_mib = 1024
        disk_gib   = 10
        base_image = "base.qcow2"
        network    = "t-sandbox"
        mac        = "52:54:00:a8:fa:0a"
      }
    }
  }

  expect_failures = [var.users]
}

run "reservation_outside_network_rejected" {
  command = plan

  module {
    source = "../../../terraform/modules/libvirt-network"
  }

  variables {
    networks = {
      sandbox = {
        name   = "t-sandbox"
        bridge = "virbr250"
        cidr   = "192.168.250.0/24"
        mode   = "isolated"
        hosts  = [{ name = "x", mac = "52:54:00:a8:fb:0a", ip = "192.168.251.10" }]
      }
    }
  }

  expect_failures = [var.networks]
}
