# ==========================================
# lab-config.mk -- settings shared by lab-bootstrap.mk, lab-gateway.mk,
# lab-provision.mk and their -verify.mk suites (included by all six, so paths
# and versions cannot drift between them).
# ==========================================
SHELL := /bin/bash

LAB_DIR      := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(LAB_DIR)/../..)
LAB_NAME     := $(notdir $(LAB_DIR))
SCRIPTS      := $(PROJECT_ROOT)/scripts
VM_SCRIPTS   := $(PROJECT_ROOT)/terraform/modules/libvirt-vm/scripts
TF_DIR       := $(LAB_DIR)/terraform
TFVARS       := $(TF_DIR)/terraform.tfvars

# --- Storage ----------------------------------------------------------------
# images: downloaded, read-only base images (written only by fedora-image)
# pools:  one libvirt storage pool per lab (VM overlays and seed ISOs)
# Outside $HOME: QEMU runs as libvirt-qemu, which cannot traverse a 0750 home.
VM_ROOT    ?= /var/lib/ai-sandbox
IMAGES_DIR ?= $(VM_ROOT)/images
POOLS_DIR  ?= $(VM_ROOT)/pools
LAB_POOL   := $(POOLS_DIR)/$(LAB_NAME)

# --- Host -------------------------------------------------------------------
# The project's pinned tools (uv, ruff, Terraform) live in a project-local bin,
# so they never replace the operator's own copies in ~/.local/bin.
TOOLS_BIN   ?= $(PROJECT_ROOT)/.tools/bin
# Installed by the bootstrap playbook's hashicorp_release role (TAGS=terraform).
TERRAFORM   ?= $(TOOLS_BIN)/terraform
LIBVIRT_URI := qemu:///system
# The sandbox guest is the VM the gateway serves and the dev alias forwards
# the sandbox ssh-agent to.
SANDBOX_VM  := fedora-dev-1

# --- Networks (one definition for Terraform, Ansible and the tests) ----------
# sandbox:  ISOLATED (no forward, no DNS). The guest's only reachable address
#           is the host's, where Envoy listens; see concepts/Isolated Sandbox
#           Network.
# upstream: NAT. Trusted test fixtures (GitHub MCP server, SCP target) that the
#           gateway reaches and the sandbox cannot.
SANDBOX_NETWORK   := ai-sandbox
SANDBOX_BRIDGE    := virbr50
SANDBOX_CIDR      := 192.168.150.0/24
UPSTREAM_NETWORK  := ai-sandbox-upstream
UPSTREAM_BRIDGE   := virbr51
UPSTREAM_CIDR     := 192.168.151.0/24
UPSTREAM_GATEWAY  := 192.168.151.1

# --- Gateway interface ------------------------------------------------------
# Everything that crosses the boundary between the lab and the gateway
# (lab-gateway.mk; concepts/Gateway Separated from the Host Bootstrap). The
# gateway also reads SANDBOX_BRIDGE (its firewall) and the upstream network
# (its MCP route) above; everything else about it lives in its own lane.
#
# Envoy's listeners on the sandbox bridge's host address: the CONNECT tunnel
# and the TLS gateway. The guests' proxy settings point here.
GATEWAY_IP   := 192.168.150.1
PROXY_PORT   := 8080
GATEWAY_PORT := 443
# PEM certificates every sandbox guest must trust (the ca_trust role): the
# gateway CA that signs Envoy's TLS-gateway certificate. Written by the
# gateway_pki role; gitignored (**/.pki/).
CA_TRUST_DIR ?= $(PROJECT_ROOT)/.pki/gateway-ca
# Optional: the CA chain of a TLS-inspecting proxy (Zscaler, ...) between this
# host and the internet, as *.pem / *.crt. Empty or missing means there is no
# such proxy. When it holds a chain, Envoy verifies public upstreams with it
# too, and every lab VM trusts it (ca_trust); see the wiki runbook Run the Lab
# Behind a TLS-Inspecting Proxy. Gitignored (**/.pki/).
TLS_INSPECTION_DIR ?= $(PROJECT_ROOT)/.pki/tls-inspection
# Operator credentials, mode 0600, written by the gateway playbook: the Vault
# and Consul operator tokens scripts/gateway/*.sh read, and the agent-cert
# helper.
OPERATOR_DIR ?= $(HOME)/.config/ai-sandbox
# The dedicated sandbox ssh-agent (sandbox_ssh_agent role): it holds only the
# Vault-signed egress certificate, and only the dev session (lab_ssh) forwards
# it.
SANDBOX_AGENT_SOCK := /run/user/$(shell id -u)/ai-sandbox/ssh-agent.sock

# --- SSH (created by the lab_ssh role) ---------------------------------------
# Keys:    ~/.ssh/key.d/local.<lab>@{admin,dev}
# Configs: ~/.ssh/config.d/local.<lab>@{admin,dev} -> Host local.<lab>.<role>[.<vm>]
SSH_KEY_DIR    := $(HOME)/.ssh/key.d
SSH_CONFIG_DIR := $(HOME)/.ssh/config.d
SSH_ID         := local.$(LAB_NAME)

# --- Python / Ansible virtual environment -----------------------------------
# requirements.txt's ansible-core pin names the venv; terraform/ansible.tf
# derives the same path from the same file.
PYTHON_VERSION       := 3.13
ANSIBLE_CORE_VERSION := $(shell sed -n 's/^ansible-core==\([0-9.]*\).*/\1/p' $(PROJECT_ROOT)/requirements.txt)
VENV                 := $(PROJECT_ROOT)/.ansible-core-$(ANSIBLE_CORE_VERSION)
COLLECTIONS_DIR      := $(PROJECT_ROOT)/.collections
UV                   := $(TOOLS_BIN)/uv
UV_VERSION           := 0.13.5
# uv and the locks name this platform.
PYTHON_PLATFORM      := x86_64-unknown-linux-gnu

# --- Privileged Ansible (the become vault) -----------------------------------
# Host plays connect locally with this inventory (kept apart from the guest
# inventory, whose group_vars/all would otherwise apply to localhost). The
# sudo password is an ansible-vault-encrypted host var; the vault key is a
# random file. Both are gitignored and created by: make -f lab-bootstrap.mk become-vault
HOST_INVENTORY := $(LAB_DIR)/ansible/inventory-host
BECOME_VAULT   := $(HOST_INVENTORY)/host_vars/localhost/become.vault.yml
VAULT_KEY      := $(PROJECT_ROOT)/.ansible_vault_key
# The gateway's real credentials (GitHub PATs, the Anthropic API key): their
# names in vars.yml (committed), their values ansible-vault encrypted in
# vault.yml (gitignored), set with: make -f lab-gateway.mk secrets
CREDENTIALS_VARS  := $(HOST_INVENTORY)/host_vars/localhost/vars.yml
CREDENTIALS_VAULT := $(HOST_INVENTORY)/host_vars/localhost/vault.yml

# Every Ansible run in this lab. Recursive (=): the vault key may be created
# after this file is read (the become-vault target).
ANSIBLE_ENV = ANSIBLE_CONFIG="$(LAB_DIR)/ansible/ansible.cfg" \
	$(if $(wildcard $(VAULT_KEY)),ANSIBLE_VAULT_PASSWORD_FILE="$(VAULT_KEY)")

# --- Verification (the three -verify.mk suites) -----------------------------
# A venv of its own, so the test tools never touch the Ansible one.
PYTEST_VENV := $(PROJECT_ROOT)/.pytest
PYTEST_LOCK := $(PROJECT_ROOT)/requirements-pytest.lock
TESTS_DIR   := $(LAB_DIR)/tests

# What the tests read their expectations and paths from. Every value comes
# from this file, so a test never restates a path or a pin.
PYTEST_ENV := LAB_NAME="$(LAB_NAME)" LAB_DIR="$(LAB_DIR)" PROJECT_ROOT="$(PROJECT_ROOT)" \
	TOOLS_BIN="$(TOOLS_BIN)" IMAGES_DIR="$(IMAGES_DIR)" POOLS_DIR="$(POOLS_DIR)" CA_TRUST_DIR="$(CA_TRUST_DIR)" \
	VENV="$(VENV)" PYTHON_VERSION="$(PYTHON_VERSION)" COLLECTIONS_DIR="$(COLLECTIONS_DIR)" \
	UV="$(UV)" UV_VERSION="$(UV_VERSION)" PYTHON_PLATFORM="$(PYTHON_PLATFORM)" \
	TERRAFORM="$(TERRAFORM)" TF_DIR="$(TF_DIR)" VM_SCRIPTS="$(VM_SCRIPTS)" LIBVIRT_URI="$(LIBVIRT_URI)" \
	SSH_KEY_DIR="$(SSH_KEY_DIR)" SSH_CONFIG_DIR="$(SSH_CONFIG_DIR)" SSH_ID="$(SSH_ID)" \
	SANDBOX_VM="$(SANDBOX_VM)" SANDBOX_AGENT_SOCK="$(SANDBOX_AGENT_SOCK)" \
	SANDBOX_NETWORK="$(SANDBOX_NETWORK)" SANDBOX_BRIDGE="$(SANDBOX_BRIDGE)" SANDBOX_CIDR="$(SANDBOX_CIDR)" \
	GATEWAY_IP="$(GATEWAY_IP)" PROXY_PORT="$(PROXY_PORT)" GATEWAY_PORT="$(GATEWAY_PORT)" \
	UPSTREAM_NETWORK="$(UPSTREAM_NETWORK)" UPSTREAM_BRIDGE="$(UPSTREAM_BRIDGE)" UPSTREAM_CIDR="$(UPSTREAM_CIDR)" \
	OPERATOR_DIR="$(OPERATOR_DIR)" HOST_INVENTORY="$(HOST_INVENTORY)" BECOME_VAULT="$(BECOME_VAULT)" \
	TLS_INSPECTION_DIR="$(TLS_INSPECTION_DIR)" VAULT_KEY="$(VAULT_KEY)" \
	CREDENTIALS_VARS="$(CREDENTIALS_VARS)" CREDENTIALS_VAULT="$(CREDENTIALS_VAULT)"

# --- Terraform variables ----------------------------------------------------
# Make and Terraform share one definition of the storage paths, networks and
# keys (lab-provision.mk runs Terraform; lab-provision-verify.mk plans for drift).
export TF_VAR_images_dir         := $(IMAGES_DIR)
export TF_VAR_pool_dir           := $(LAB_POOL)
export TF_VAR_libvirt_uri        := $(LIBVIRT_URI)
export TF_VAR_admin_ssh_key_path := $(SSH_KEY_DIR)/$(SSH_ID)@admin.pub
export TF_VAR_dev_ssh_key_path   := $(SSH_KEY_DIR)/$(SSH_ID)@dev.pub
export TF_VAR_ca_trust_dir       := $(CA_TRUST_DIR)
export TF_VAR_tls_inspection_dir := $(TLS_INSPECTION_DIR)
export TF_VAR_networks           := {"sandbox":{"name":"$(SANDBOX_NETWORK)","bridge":"$(SANDBOX_BRIDGE)","cidr":"$(SANDBOX_CIDR)","mode":"isolated"},"upstream":{"name":"$(UPSTREAM_NETWORK)","bridge":"$(UPSTREAM_BRIDGE)","cidr":"$(UPSTREAM_CIDR)","mode":"nat"}}

# --- Ansible extra vars -----------------------------------------------------
# Every playbook (host and guest, and the guest runs Terraform starts) gets the
# same lab values from here as one JSON extra-vars document.
LAB_VARS := {"lab_name":"$(LAB_NAME)","project_root":"$(PROJECT_ROOT)","tools_bin":"$(TOOLS_BIN)",\
"images_dir":"$(IMAGES_DIR)","pools_dir":"$(POOLS_DIR)","libvirt_uri":"$(LIBVIRT_URI)",\
"sandbox_vm":"$(SANDBOX_VM)","sandbox_agent_sock":"$(SANDBOX_AGENT_SOCK)",\
"sandbox_bridge":"$(SANDBOX_BRIDGE)","sandbox_cidr":"$(SANDBOX_CIDR)","gateway_ip":"$(GATEWAY_IP)",\
"proxy_port":$(PROXY_PORT),"gateway_port":$(GATEWAY_PORT),\
"upstream_bridge":"$(UPSTREAM_BRIDGE)","upstream_cidr":"$(UPSTREAM_CIDR)","upstream_gateway":"$(UPSTREAM_GATEWAY)",\
"ca_trust_dir":"$(CA_TRUST_DIR)","tls_inspection_dir":"$(TLS_INSPECTION_DIR)","operator_dir":"$(OPERATOR_DIR)"}
export TF_VAR_lab_vars := $(LAB_VARS)
