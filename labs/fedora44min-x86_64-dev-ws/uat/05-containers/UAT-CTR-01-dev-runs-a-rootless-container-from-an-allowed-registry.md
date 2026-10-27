---
id: UAT-CTR-01
title: The developer pulls an image from an allowed registry and runs it rootless
suite: 05-containers
stack: python-stack
features:
- SBX-CTR-01
- SBX-EGR-01
personas:
- dev
priority: P1
disruptive: false
automated:
- tests/guest/python-stack/test_python_stack.py::test_podman_runs_rootless_for_dev
- tests/guest/python-stack/test_python_stack.py::test_podman_api_socket_is_the_users
leaves: The image registry.fedoraproject.org/fedora:44 in dev's container storage, unless step 6 removes it.
---

# UAT-CTR-01 The developer pulls an image from an allowed registry and runs it rootless

## Story

As the developer, I want to run containers without root, so that I can use container tools in the
sandbox and a container cannot become root on the VM.

## Preconditions

1. UAT-LIFE-01 passes.

## Steps

| Step | Persona | Action | Expected result |
|---|---|---|---|
| 1 | dev | Connect with `make -f lab-provision.mk ssh`. In the right pane, run `podman info --format '{{.Host.Security.Rootless}} {{.Store.GraphDriverName}}'`. | `true overlay`. |
| 2 | dev | Run `podman run --rm registry.fedoraproject.org/fedora:44 cat /etc/os-release \| grep PRETTY`. | podman pulls the image, then prints `PRETTY_NAME="Fedora Linux 44 (Container Image)"`. |
| 3 | dev | Run `podman run --rm registry.fedoraproject.org/fedora:44 id -u`. | `0`: root inside the container. |
| 4 | dev | Run `podman run -d --name uat-sleep registry.fedoraproject.org/fedora:44 sleep 60`, then `ps -o user= -C sleep`. | `dev`. On the VM, the container's root is dev. |
| 5 | dev | Run `podman rm -f uat-sleep`. Run `systemctl --user is-active podman.socket`. | `active`. dev's own podman API socket runs. |
| 6 | dev | Run `podman rmi registry.fedoraproject.org/fedora:44`. | The image is removed. |

## Evidence left behind

None, if step 6 is done.

## Notes

The pull goes through the CONNECT tunnel to `registry.fedoraproject.org` and
`cdn.registry.fedoraproject.org`, which are in the `oci-registries` category of the egress catalog.
podman verifies the registry's TLS with the guest's trust store.

Images from Docker Hub do not pull now: see the issue
[Docker Hub pulls fail: blobs come from production.cloudfront.docker.com](../../../../.okfw/issues/docker-hub-pulls-fail-blobs-come-from-production-cloudfront-docker-com--01a17f2bba31.md).
The Fedora registry and ghcr.io work (UAT-CTR-02 builds from ghcr.io).
