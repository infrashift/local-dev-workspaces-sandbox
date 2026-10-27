# ==========================================
# lab-provision.mk -- day-to-day workflows for fedora44min-x86_64-dev-ws,
# once lab-bootstrap.mk has prepared the host and lab-gateway.mk the gateway
# (and lab-bootstrap-verify.mk and lab-gateway-verify.mk pass).
#
#   make -f lab-provision.mk apply             # create/update VMs + run site.yml
#   make -f lab-provision.mk status            # every VM: state, IP
#   make -f lab-provision.mk stop|start [VM=fedora-dev-1]
#   make -f lab-provision.mk ssh [ROLE=dev|admin] [VM=...]
#   make -f lab-provision.mk play PLAYBOOK=python-stack   # a stack on top of vm-baseline
#
# After apply (or play): make -f lab-provision-verify.mk [STACK=python-stack|sandbox]
# runs the read-only guest tests.
#
# start/stop/status drive the libvirt domains with virsh, not Terraform, so
# they also bring VMs back after the host reboots.
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

TF := "$(TERRAFORM)" -chdir=$(TF_DIR)

# The TF_VAR_* exports are in lab-config.mk, shared with lab-provision-verify.mk.
VIRSH := virsh -c $(LIBVIRT_URI)

# VM=<name> targets one VM; default is every VM terraform.tfvars declares.
VM ?=
LAB_VMS := $(shell sed -n 's/^[[:space:]]*"\([a-z0-9-]*\)"[[:space:]]*=[[:space:]]*{.*/\1/p' $(TFVARS))
VMS = $(if $(VM),$(VM),$(LAB_VMS))
FIRST_VM = $(if $(VM),$(VM),$(SANDBOX_VM))

# ssh as the dev (default) or admin guest user, through the lab's generated
# ssh config (works whether or not ~/.ssh/config includes config.d/*).
ROLE ?= dev

# play: a playbook in ansible/playbooks/, named without .yml.
PLAYBOOK ?=
PLAYBOOK_FILE = $(LAB_DIR)/ansible/playbooks/$(PLAYBOOK).yml
GUEST_PLAYBOOK = $(ANSIBLE_ENV) "$(SCRIPTS)/ansible-confirm.sh" "$(VENV)/bin/ansible-playbook" \
	--inventory "$(LAB_DIR)/ansible/inventory" \
	--inventory "$(TF_DIR)/output-data/terraform-hosts.yml" \
	--extra-vars '$(LAB_VARS)'

.PHONY: help preflight ca-trust-check init plan apply destroy output status start stop restart ip ssh console ansible play fmt validate test lint clean

## Display this help message
help:
	@echo "Usage: make -f lab-provision.mk [target] [VM=<name>]"
	@echo ""
	@echo "Targets:"
	@awk '/^[a-zA-Z_0-9-]+:/ { \
		helpMessage = match(lastLine, /^## (.*)/); \
		if (helpMessage) { \
			helpCommand = substr($$1, 0, index($$1, ":")-1); \
			helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
			printf "  %-20s %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)

# Refuse to provision on a host lab-bootstrap.mk has not prepared, without the
# gateway lab-gateway.mk installs, when terraform.tfvars names a base image
# that is not in IMAGES_DIR, or when the gateway CA the sandbox guests trust is
# missing.
preflight: ca-trust-check
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-bootstrap.mk" check >/dev/null \
		|| { echo "Host not ready -- see: make -f lab-bootstrap.mk check"; exit 1; }
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" check >/dev/null \
		|| { echo "Gateway not ready -- see: make -f lab-gateway.mk check"; exit 1; }
	@for img in $$(sed -n 's/^[[:space:]]*base_image[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$(TFVARS)" | sort -u); do \
		test -f "$(IMAGES_DIR)/$$img" || { echo "Base image $(IMAGES_DIR)/$$img missing (terraform.tfvars vs lab-bootstrap)"; exit 1; }; \
	done

# Every sandbox guest trusts the gateway CA in CA_TRUST_DIR (ca_trust role);
# without it the guest cannot reach github.com or api.anthropic.com through
# the TLS gateway.
ca-trust-check:
	@ls "$(CA_TRUST_DIR)"/*.pem "$(CA_TRUST_DIR)"/*.crt 2>/dev/null | grep -q . || { \
		echo "No gateway CA in $(CA_TRUST_DIR): run make -f lab-gateway.mk gateway TAGS=pki"; exit 1; }

# ------------------------------------------------------------------------------
# Terraform lifecycle
# ------------------------------------------------------------------------------

## terraform init
init:
	@$(TF) init -input=false

## terraform plan
plan: init
	@$(TF) plan

## Create/update the VMs, wait for SSH, then run the Ansible playbook
apply: preflight init
	@$(TF) apply

## Stop and delete the VMs (base images in IMAGES_DIR are kept)
destroy: init
	@$(TF) destroy

## Show Terraform outputs (VM IPs, libvirt domains)
output:
	@$(TF) output

# ------------------------------------------------------------------------------
# Runtime (works without Terraform: drives the libvirt domains)
# ------------------------------------------------------------------------------

## Show each VM's state and IP
status:
	@printf '%-24s %-14s %s\n' VM STATE IP
	@for vm in $(VMS); do \
		state=$$($(VIRSH) domstate "$$vm" 2>/dev/null || echo "not created"); \
		ip=-; [ "$$state" = running ] && ip=$$("$(VM_SCRIPTS)/vm-ip.sh" "$$vm" "$(LIBVIRT_URI)" 2>/dev/null || echo -); \
		printf '%-24s %-14s %s\n' "$$vm" "$$state" "$$ip"; \
	done

## Start stopped VMs (e.g. after a reboot) and wait for their DHCP lease
start: preflight
	@for vm in $(VMS); do \
		[ "$$($(VIRSH) domstate "$$vm")" = running ] || $(VIRSH) start "$$vm" >/dev/null || exit 1; \
		for i in $$(seq 60); do "$(VM_SCRIPTS)/vm-ip.sh" "$$vm" "$(LIBVIRT_URI)" 2>/dev/null && break; sleep 5; done; \
	done

## Gracefully stop VMs (ACPI shutdown, waits up to 60s each)
stop:
	@for vm in $(VMS); do \
		[ "$$($(VIRSH) domstate "$$vm" 2>/dev/null)" = running ] || continue; \
		$(VIRSH) shutdown "$$vm" >/dev/null; \
		for i in $$(seq 60); do [ "$$($(VIRSH) domstate "$$vm")" = running ] || break; sleep 1; done; \
		[ "$$($(VIRSH) domstate "$$vm")" = running ] && { echo "$$vm ignored ACPI; destroying"; $(VIRSH) destroy "$$vm" >/dev/null; }; \
	done; true

## Stop then start VMs
restart: stop start

## Print a VM's IP address
ip:
	@"$(VM_SCRIPTS)/vm-ip.sh" "$(FIRST_VM)" "$(LIBVIRT_URI)"

## SSH into a VM as ROLE=dev (default) or ROLE=admin
ssh:
	@exec ssh -F "$(SSH_CONFIG_DIR)/$(SSH_ID)@$(ROLE)" "$(SSH_ID).$(ROLE)$(if $(VM),.$(VM))"

## Attach to a VM's serial console (Ctrl-] to leave)
console:
	@exec $(VIRSH) console "$(FIRST_VM)"

## Re-run site.yml (vm-baseline + upstream): dry run first, applies only if you type "yes"
ansible:
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-provision.mk" play PLAYBOOK=site

## Run PLAYBOOK=<name> from ansible/playbooks/ (e.g. python-stack): dry run, then "yes"
play: ca-trust-check
	@test -n "$(PLAYBOOK)" || { echo "Usage: make -f lab-provision.mk play PLAYBOOK=<name>"; \
		ls "$(LAB_DIR)/ansible/playbooks/" | sed -n 's/\.yml$$//p' | sed 's/^/  /'; exit 1; }
	@test -f "$(PLAYBOOK_FILE)" || { echo "No playbook $(PLAYBOOK_FILE)"; exit 1; }
	@test -f "$(TF_DIR)/output-data/terraform-hosts.yml" || { echo "No VM inventory yet: run make -f lab-provision.mk apply"; exit 1; }
	@$(GUEST_PLAYBOOK) "$(PLAYBOOK_FILE)"

# ------------------------------------------------------------------------------
# Quality
# ------------------------------------------------------------------------------

## Format Terraform (lab + shared modules)
fmt:
	@"$(TERRAFORM)" fmt -recursive "$(TF_DIR)" "$(PROJECT_ROOT)/terraform"

## terraform fmt -check + validate
validate: init
	@"$(TERRAFORM)" fmt -check -recursive "$(TF_DIR)" "$(PROJECT_ROOT)/terraform"
	@$(TF) validate

## Terraform unit tests (plan-only; start no VMs)
test: init
	@$(TF) test

## Lint shell scripts, YAML, playbooks, the role contract, the UAT specs and Python
lint:
	@shellcheck "$(SCRIPTS)"/*.sh "$(SCRIPTS)"/gateway/*.sh "$(VM_SCRIPTS)"/*.sh
	@"$(VENV)/bin/yamllint" -s "$(LAB_DIR)/ansible" "$(PROJECT_ROOT)/ansible"
	@"$(SCRIPTS)/check-role-contract.sh"
	@"$(VENV)/bin/python" "$(SCRIPTS)/check-uat-specs.py" "$(LAB_DIR)"
	@cd "$(LAB_DIR)/ansible" && $(ANSIBLE_ENV) PATH="$(VENV)/bin:$$PATH" "$(VENV)/bin/ansible-lint" playbooks/ \
		"$(PROJECT_ROOT)/ansible/roles/host" "$(PROJECT_ROOT)/ansible/roles/gateway" "$(PROJECT_ROOT)/ansible/roles/guest"
	@"$(TOOLS_BIN)/ruff" check "$(PROJECT_ROOT)"

## Remove local Terraform working files (not state, not VMs)
clean:
	@rm -rf "$(TF_DIR)/.terraform" "$(TF_DIR)/output-data"
