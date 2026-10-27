---
id: "01a16643-37cc-7711-a0ce-fbad468da916"
title: "Base Images and Machine Overlays"
type: "concept"
tags:
  - "storage"
  - "qcow2"
  - "images"
created: "2026-10-22T19:57:23-05:00"
timestamp: "2026-10-22T19:57:23-05:00"
description: "The two stores under ~/VMs: read-only downloaded base images, and per-VM directories with copy-on-write overlays."
---

# Base Images and Machine Overlays

```
~/VMs/images/                     images_dir: downloaded, read-only backing files
~/VMs/machines/<lab>/<vm>/        machines_dir: one directory per VM, owned by Terraform
  disk.qcow2   copy-on-write overlay, backing file = images_dir/<base_image>
  efivars.fd   private copy of the edk2 variable store
  cidata/      cloud-init sources; seed.iso is built from them (hdiutil)
  vm.env       launch parameters read by vm-ctl.sh
  qemu.pid  qmp.sock  console.log  qemu.log
```

Both stores live outside the repo (decided 2026-10-22), so multi-GB files stay out of git and the IDE.
The paths are set once in the lab's `lab-config.mk`: Ansible gets them as extra vars, and Terraform gets
them as `TF_VAR_*`.

## Rules
- **The base is never written to**, and every overlay depends on it. Moving, deleting or replacing it
  breaks them all. The `fedora_cloud_image` role writes images `0444`, and a new Fedora respin gets a new
  filename.
- Only the bootstrap playbook writes to `images_dir`. It verifies first and moves the image in last,
  atomically.
- `terraform destroy` removes only `<vm>/`.
- The overlay must be **at least the base's virtual size** (the module checks). Fedora Cloud is 5 GiB
  virtual; growpart grows the btrfs root into the rest on first boot.
- macOS caps unix socket paths at 104 bytes, and a variable validation checks
  `machines_dir/<lab>/<vm>/qmp.sock` against it.

## Related
- [qemu-hvf-vm Module](/tooling/qemu-hvf-vm-module--01a1664337d6.md)
- [Host Bootstrap Roles](/tooling/host-bootstrap-roles--01a1664337e2.md)
