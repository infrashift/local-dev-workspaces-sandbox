# x86_64 KVM guests under libvirt (qemu:///system): a qcow2 overlay on a
# read-only base image, a cloud-init seed, explicit non-Secure-Boot OVMF, and
# a fixed MAC whose DHCP reservation (libvirt-network) gives the VM a fixed
# address. Ported from libvirt-qemu-kvm's provider modules; its documented
# 0.9.x caveats apply (tooling/libvirt-vm Module).
terraform {
  required_providers {
    libvirt = {
      source = "dmacvicar/libvirt"
    }
  }
}

locals {
  users = [for u in var.users : merge(u, { ssh_key = trimspace(file(pathexpand(u.ssh_key_path))) })]
}

resource "libvirt_volume" "os" {
  for_each = var.vms

  name     = "${each.key}.qcow2"
  pool     = var.pool_name
  capacity = each.value.disk_gib * 1073741824 # bytes

  target = {
    format = { type = "qcow2" }
  }

  # The overlay backs onto the base image in place; libvirt never writes to
  # the backing file. Deleting or renaming the base breaks the overlay.
  backing_store = {
    path   = "${var.images_dir}/${each.value.base_image}"
    format = { type = "qcow2" }
  }
}

resource "libvirt_cloudinit_disk" "seed" {
  for_each = var.vms

  name = "${each.key}-init"
  user_data = templatefile("${path.module}/templates/user-data.tpl", {
    vm_name  = each.key
    users    = local.users
    packages = var.cloud_init_packages
  })
  meta_data = templatefile("${path.module}/templates/meta-data.tpl", {
    vm_name = each.key
  })
  network_config = templatefile("${path.module}/templates/network-config.tpl", {
    mac = each.value.mac
  })
}

# The generated ISO is uploaded into the pool as a volume and attached as a
# cdrom (the 0.9.x provider has no direct domain<->cloudinit link).
resource "libvirt_volume" "seed" {
  for_each = var.vms

  name = "${each.key}-seed.iso"
  pool = var.pool_name

  create = {
    content = { url = libvirt_cloudinit_disk.seed[each.key].path }
  }
}

resource "libvirt_domain" "this" {
  for_each = var.vms

  name = each.key
  type = "kvm"

  vcpu        = each.value.vcpu
  memory      = each.value.memory_mib
  memory_unit = "MiB" # provider default unit is KiB

  running   = true
  autostart = false

  # The provider's default qemu64 model lacks x86-64-v2, which Fedora and EL
  # need.
  cpu = { mode = "host-passthrough" }

  os = {
    type         = "hvm"
    type_arch    = "x86_64"
    type_machine = "q35"

    # Explicit non-Secure-Boot OVMF: firmware auto-selection picks the
    # enrolled-keys .ms.fd loader.
    loader          = var.uefi_loader
    loader_type     = "pflash"
    loader_readonly = "yes"

    nv_ram = {
      nv_ram   = "/var/lib/libvirt/qemu/nvram/${each.key}_VARS.fd"
      template = var.uefi_nvram_template
    }

    boot_devices = [{ dev = "hd" }]
  }

  features = {
    acpi = true # UEFI requires ACPI on x86_64
    apic = {}
  }

  devices = {
    # file-type sources (not volume refs): virt-aa-helper does not resolve
    # type='volume' disks, leaving the AppArmor profile empty and QEMU unable
    # to open the images.
    disks = [
      {
        source = {
          file = { file = libvirt_volume.os[each.key].path }
        }
        target = { dev = "vda", bus = "virtio" }
        driver = { type = "qcow2" }
      },
      {
        device = "cdrom"
        source = {
          file = { file = libvirt_volume.seed[each.key].path }
        }
        target = { dev = "sda", bus = "sata" }
      },
    ]

    interfaces = [{
      model       = { type = "virtio" }
      source      = { network = { network = each.value.network } }
      mac         = { address = each.value.mac }
      wait_for_ip = { source = "lease", timeout = var.ip_timeout }
    }]

    consoles = [{
      target = { type = "serial", port = 0 }
    }]
  }

  # No `destroy` block: the provider force-stops, then undefines with nvram.
  # A graceful shutdown wait here times out and strands the domain defined.
}

# Safety net: each domain is undefined (with its UEFI nvram) on destroy, even
# if a guest ignores ACPI or the pool is gone. depends_on makes this destroy
# provisioner run before the domain is deleted; the provider's own Delete then
# finds the domain gone and no-ops.
resource "terraform_data" "domain_reaper" {
  for_each = var.vms

  input = { name = each.key, uri = var.libvirt_uri }

  provisioner "local-exec" {
    when    = destroy
    command = "virsh -c ${self.input.uri} destroy ${self.input.name} 2>/dev/null || true; virsh -c ${self.input.uri} undefine ${self.input.name} --nvram --managed-save --snapshots-metadata 2>/dev/null || true"
  }

  depends_on = [libvirt_domain.this]
}
