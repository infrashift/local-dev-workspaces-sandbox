# local-dev-workspaces-sandbox

Terraform-provisioned **Linux VMs on a Linux x86_64 host** for AI-augmented software development:
KVM under libvirt, cloud-init identity, and Ansible configuration. The sandbox VM, where an AI coding
agent works, has no route out. Its only way to the internet is a zero-trust gateway on the host
(Vault, Consul, Envoy), which holds every real credential so that the VM never does.

> **Warning: supported hosts.** The host bootstrap and the gateway automation are tested only on
> **Pop!_OS and Ubuntu (24.04 LTS)**. They install with `apt`, and they assume Debian/Ubuntu package
> names, firmware paths, the `libvirt-qemu` user and AppArmor. On any other Linux distribution
> (Fedora, RHEL, Arch, openSUSE and others), expect to change the host roles before they work. The
> first host role stops with an error on a non-Debian host. See
> [Supported hosts](labs/fedora44min-x86_64-dev-ws/README.md#supported-hosts) for what would need to
> change. The guest VMs are independent of the host distribution.

Each lab lives in `labs/<lab>/` and is driven by makefiles, each followed by a read-only pytest
suite:

```sh
cd labs/fedora44min-x86_64-dev-ws
make -f lab-bootstrap.mk all          # one-time host setup (dry run first; type "yes" to apply)
make -f lab-bootstrap-verify.mk       # verify the host
make -f lab-gateway.mk                # the zero-trust gateway (Vault, Consul, Envoy) on the host
make -f lab-gateway-verify.mk         # verify the gateway
make -f lab-provision.mk apply        # then: apply, status, start, stop, ssh, destroy ...
make -f lab-provision-verify.mk       # verify the lab VMs
```

Each lab's `README.md` gives the full operator procedure. For the security model, read
[security-controls.md](labs/fedora44min-x86_64-dev-ws/security-controls.md).

**Documentation lives in the OKF wiki** in `.okfw/`. Start at
[Platform Overview](.okfw/platform-overview--01a1664337bc.md), or browse with `okfw search` /
`okfw root`.
