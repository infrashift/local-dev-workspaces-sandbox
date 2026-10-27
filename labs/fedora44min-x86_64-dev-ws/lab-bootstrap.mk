# ==========================================
# lab-bootstrap.mk -- one-time host setup for fedora44min-x86_64-dev-ws
#
#   make -f lab-bootstrap.mk become-vault  # once: encrypt your sudo password for Ansible
#   make -f lab-bootstrap.mk all           # uv -> venv -> collections -> host
#   make -f lab-bootstrap.mk check         # read-only: is the host ready?
#
# Make only builds what Ansible needs to run (uv, the hashed venv, pinned
# collections). Everything else is one playbook, bootstrap-host.yml: apt
# packages (KVM, libvirt, OVMF), VM storage, SSH keys and configs, ruff,
# Terraform and the Fedora image.
#
# Ansible always runs as a dry run (--check --diff) first and applies only
# after you type "yes" (ANSIBLE_CONFIRM=yes answers for you, after showing the
# dry run). Privileged tasks take the sudo password from the become vault.
#
# Every download is verified: uv by its release SHA-256 here; Python
# packages by the hashes in requirements.lock; ruff by its release SHA-256;
# Terraform and the Fedora image by GPG, against pinned key fingerprints,
# inside the playbook.
#
# The order of operations:
#   make -f lab-bootstrap.mk all  ->  make -f lab-bootstrap-verify.mk
#   make -f lab-gateway.mk        ->  make -f lab-gateway-verify.mk
#   make -f lab-provision.mk apply  ->  make -f lab-provision-verify.mk
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# Optional: limit the playbook to some roles, e.g. TAGS=ssh,image:
#   packages storage ssh ruff terraform image
TAGS ?=

# Recursive (=), so a target-specific TAGS (the terraform target) applies.
HOST_PLAY = $(VENV)/bin/ansible-playbook -i "$(HOST_INVENTORY)" -e '$(LAB_VARS)' $(if $(TAGS),--tags $(TAGS))
PLAYBOOK  = $(HOST_PLAY) "$(LAB_DIR)/ansible/playbooks/bootstrap-host.yml"

.PHONY: help all host-guard uv venv collections lock become-vault become-guard host terraform check

## Display this help message
help:
	@echo "Usage: make -f lab-bootstrap.mk [target] [TAGS=role,...]"
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

## Everything, in order: uv, venv, collections, then the host playbook
all: uv venv collections host

host-guard:
	@if [ "$$(uname -sm)" != "Linux x86_64" ]; then \
		echo "Error: this lab needs a Linux x86_64 host (uname: $$(uname -sm))"; exit 1; \
	fi

## Install the pinned uv into the project's .tools/bin (SHA-256 verified)
uv: host-guard
	@if "$(UV)" --version 2>/dev/null | grep -q " $(UV_VERSION)"; then \
		echo ">>> uv $(UV_VERSION) already installed. Skipping."; \
	else \
		"$(SCRIPTS)/install-release-binary.sh" \
			"https://github.com/astral-sh/uv/releases/download/$(UV_VERSION)/uv-$(PYTHON_PLATFORM).tar.gz" \
			"$(TOOLS_BIN)" uv uvx; \
	fi

## Create/sync the .ansible-core-<version> venv from the hashed requirements.lock
venv: uv
	@$(UV) python install $(PYTHON_VERSION)
	@if [ ! -x "$(VENV)/bin/python" ]; then \
		echo ">>> Creating $(VENV) (Python $(PYTHON_VERSION))..."; \
		$(UV) venv "$(VENV)" --python $(PYTHON_VERSION); \
	fi
	@echo ">>> Syncing $(VENV) with requirements.lock (hashes required)..."
	@$(UV) pip sync --require-hashes --python "$(VENV)/bin/python" "$(PROJECT_ROOT)/requirements.lock"
	@"$(VENV)/bin/ansible" --version | head -1

## Install the pinned Ansible collections (requirements.yml) into .collections/
collections: venv
	@"$(VENV)/bin/ansible-galaxy" collection install -r "$(PROJECT_ROOT)/requirements.yml" -p "$(COLLECTIONS_DIR)"

## Re-pin requirements.lock (with hashes) after editing requirements.txt
lock:
	@cd "$(PROJECT_ROOT)" && $(UV) pip compile --generate-hashes \
		--python-version $(PYTHON_VERSION) --python-platform $(PYTHON_PLATFORM) \
		--custom-compile-command "make -f labs/$(LAB_NAME)/lab-bootstrap.mk lock" \
		requirements.txt -o requirements.lock
	@echo ">>> requirements.lock updated; run 'make -f lab-bootstrap.mk venv' and commit both files."

## Once: store your sudo password ansible-vault-encrypted (both files gitignored)
become-vault: venv
	@umask 077; if [ ! -s "$(VAULT_KEY)" ]; then \
		openssl rand -base64 48 >"$(VAULT_KEY)" && echo ">>> Created the vault key $(VAULT_KEY) (0600)"; fi
	@mkdir -p "$(dir $(BECOME_VAULT))"
	@read -rsp "sudo password for $$USER: " pw; echo; \
	if ! printf '%s\n' "$$pw" | sudo -S -k -p '' true 2>/dev/null; then echo "That is not your sudo password."; exit 1; fi; \
	umask 077; { echo '---'; echo '# ansible-vault encrypted; created by: make -f lab-bootstrap.mk become-vault'; \
		printf '%s' "$$pw" | "$(VENV)/bin/ansible-vault" encrypt_string --vault-password-file "$(VAULT_KEY)" \
			--stdin-name ansible_become_password 2>/dev/null; } >"$(BECOME_VAULT).tmp" \
	&& mv "$(BECOME_VAULT).tmp" "$(BECOME_VAULT)" && echo ">>> Wrote $(BECOME_VAULT) (0600)"

become-guard:
	@test -s "$(VAULT_KEY)" -a -s "$(BECOME_VAULT)" || { echo "No become vault yet: run make -f lab-bootstrap.mk become-vault"; exit 1; }

## Dry-run the host playbook, then apply it if you type "yes"
host: host-guard become-guard
	@test -x "$(VENV)/bin/ansible-playbook" || { echo "Run: make -f lab-bootstrap.mk venv collections"; exit 1; }
	@$(ANSIBLE_ENV) "$(SCRIPTS)/ansible-confirm.sh" $(PLAYBOOK)

## Install the pinned Terraform (the host playbook's terraform tag: GPG + SHA-256 verified)
terraform: TAGS = terraform
terraform: host

## Read-only readiness report (the dry run must find nothing to change)
check: host-guard become-guard
	@"$(UV)" --version 2>/dev/null | grep -q " $(UV_VERSION)" || { echo "uv $(UV_VERSION) missing: run make -f lab-bootstrap.mk all"; exit 1; }
	@test -x "$(VENV)/bin/ansible-playbook" || { echo "venv $(VENV) missing: run make -f lab-bootstrap.mk all"; exit 1; }
	@test -d "$(COLLECTIONS_DIR)/ansible_collections/community" || { echo "collections missing: run make -f lab-bootstrap.mk all"; exit 1; }
	@$(ANSIBLE_ENV) CHECK_ONLY=1 "$(SCRIPTS)/ansible-confirm.sh" $(PLAYBOOK) \
		|| { echo "Host is not ready: run make -f lab-bootstrap.mk host"; exit 1; }
	@echo "Host is ready."
