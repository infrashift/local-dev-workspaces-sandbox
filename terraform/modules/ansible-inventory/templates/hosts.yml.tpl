all:
  hosts:
%{ for hostname, ip in host_ips ~}
    ${hostname}:
      ansible_host: ${ip}
%{ endfor ~}
  children:
%{ for role in unique_roles ~}
    ${role}:
      hosts:
%{ for hostname, data in host_vars ~}
%{ if contains(lookup(data, "roles", []), role) ~}
        ${hostname}:
%{ endif ~}
%{ endfor ~}
%{ endfor ~}