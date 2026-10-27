version: 2
ethernets:
  primary:
    # Match by MAC, so the config holds whatever the NIC is named. DHCP hands
    # out the VM's reserved address (libvirt-network); on an isolated network
    # it sends no router and no DNS server.
    match:
      macaddress: "${mac}"
    dhcp4: true
