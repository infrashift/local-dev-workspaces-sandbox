# tooling

<!-- okfw:generated — maintained by okfw; edits here are overwritten -->

## Concepts

* [Guest Roles](guest-roles--01a166e751e0.md) - The Ansible roles in ansible/roles/guest/ for Fedora/RHEL/Rocky lab VMs: lane, inputs, verification, and where each was ported from.
* [Host Bootstrap Roles](host-bootstrap-roles--01a1664337e2.md) - The localhost Ansible roles that prepare an Apple Silicon Mac, and the dry-run-then-type-yes policy every Ansible run follows.
* [Python Toolchain](python-toolchain--01a1664337e8.md) - uv, ruff, and the hash-locked .ansible-core-<version> virtual environment: what is pinned where, and how to re-pin.
* [ansible-inventory Module](ansible-inventory-module--01a1664337dc.md) - The host-agnostic module, copied verbatim from libvirt-qemu-kvm, that writes a role-grouped Ansible inventory from VM IPs.
* [qemu-hvf-vm Module](qemu-hvf-vm-module--01a1664337d6.md) - The Terraform module that creates overlay disks, cloud-init seeds and QEMU/HVF processes, and reports each VM's IP.

