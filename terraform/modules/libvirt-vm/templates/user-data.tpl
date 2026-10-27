#cloud-config
hostname: ${vm_name}
fqdn: ${vm_name}.local
preserve_hostname: false
users:
%{ for u in users ~}
  - name: ${u.name}
    lock_passwd: true
    ssh_authorized_keys:
      - ${u.ssh_key}
%{ if u.sudo ~}
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: [wheel]
%{ endif ~}
    shell: /bin/bash
%{ endfor ~}
ssh_pwauth: false
%{ if length(packages) > 0 ~}
packages:
%{ for p in packages ~}
  - ${p}
%{ endfor ~}
%{ endif ~}
