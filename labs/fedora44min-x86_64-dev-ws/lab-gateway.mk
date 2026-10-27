# ==========================================
# lab-gateway.mk -- the zero-trust surrogate-credential gateway on this host,
# for fedora44min-x86_64-dev-ws (concepts/Zero-Trust Surrogate Gateway)
#
#   make -f lab-gateway.mk                 # = gateway: dry run, then apply
#   make -f lab-gateway.mk secrets         # once: encrypt the real GitHub PATs and Anthropic key
#   make -f lab-gateway.mk check           # read-only: is the gateway ready?
#   make -f lab-gateway.mk allowlist|allow|deny   # the egress allow list
#   eval "$(make -s -f lab-gateway.mk cli)"        # vault/consul CLIs, read-only
#   make -f lab-gateway.mk break-glass REASON=...  # 15 minutes with the real credentials
#
# Run it once the host is bootstrapped and verified:
#   make -f lab-bootstrap.mk all  ->  make -f lab-bootstrap-verify.mk
#   make -f lab-gateway.mk        ->  make -f lab-gateway-verify.mk
#   make -f lab-provision.mk apply  ->  make -f lab-provision-verify.mk
# It uses what the bootstrap built (the venv, the collections, the become
# vault) and refuses to start without them.
#
# One playbook, gateway-host.yml: Vault, Vault Proxy, Consul, consul-template,
# Envoy, the gateway PKI, the sandbox firewall and the sandbox ssh-agent.
# Ansible always runs as a dry run (--check --diff) first and applies only
# after you type "yes" (ANSIBLE_CONFIRM=yes answers for you, after showing the
# dry run). Vault, Consul, consul-template and Envoy are verified by GPG,
# against pinned key fingerprints, inside the playbook.
#
# Everything the gateway owns sits in its own lane, so it can move to a
# project of its own (concepts/Gateway Separated from the Host Bootstrap):
# ansible/roles/gateway/, scripts/gateway/, gateway-host.yml,
# vars/{gateway,egress-baseline}.yml, tests/gateway/ and these two makefiles.
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# Optional: limit the playbook to some roles, e.g. TAGS=vault,envoy:
#   binaries pki vault consul envoy firewall ssh_agent
TAGS ?=

GATEWAY = $(VENV)/bin/ansible-playbook -i "$(HOST_INVENTORY)" -e '$(LAB_VARS)' $(if $(TAGS),--tags $(TAGS)) \
	"$(LAB_DIR)/ansible/playbooks/gateway-host.yml"
GATEWAY_SCRIPTS := $(SCRIPTS)/gateway
# break-glass.yml leaves its single-use wrapping token here (tmpfs, 0600).
BREAK_GLASS_WRAP := /run/user/$(shell id -u)/ai-sandbox-break-glass.wrap

.DEFAULT_GOAL := gateway
.PHONY: help guard gateway check secrets agent-cert allowlist allow deny cli break-glass

## Display this help message
help:
	@echo "Usage: make -f lab-gateway.mk [target] [TAGS=role,...]"
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

# What lab-bootstrap.mk must have built first.
guard:
	@if [ "$$(uname -sm)" != "Linux x86_64" ]; then \
		echo "Error: this lab needs a Linux x86_64 host (uname: $$(uname -sm))"; exit 1; \
	fi
	@test -x "$(VENV)/bin/ansible-playbook" || { echo "venv $(VENV) missing: run make -f lab-bootstrap.mk all"; exit 1; }
	@test -d "$(COLLECTIONS_DIR)/ansible_collections/community" || { echo "collections missing: run make -f lab-bootstrap.mk all"; exit 1; }
	@test -s "$(VAULT_KEY)" -a -s "$(BECOME_VAULT)" || { echo "No become vault yet: run make -f lab-bootstrap.mk become-vault"; exit 1; }

## Dry-run the gateway playbook (Vault, Consul, Envoy, firewall), then apply it if you type "yes"
gateway: guard
	@$(ANSIBLE_ENV) "$(SCRIPTS)/ansible-confirm.sh" $(GATEWAY)

## Read-only readiness report (the dry run must find nothing to change)
check: guard
	@$(ANSIBLE_ENV) CHECK_ONLY=1 "$(SCRIPTS)/ansible-confirm.sh" $(GATEWAY) \
		|| { echo "Gateway is not ready: run make -f lab-gateway.mk"; exit 1; }
	@echo "Gateway is ready."

## Once (and to rotate): encrypt the GitHub PATs and the Anthropic key in vault.yml, then load them [NAME=<secret>]
secrets: guard
	@"$(GATEWAY_SCRIPTS)/sandbox-secret.sh" "$(CREDENTIALS_VARS)" "$(CREDENTIALS_VAULT)" "$(VAULT_KEY)" \
		"$(VENV)/bin/ansible-vault" "$(LAB_DIR)/ansible/vars/gateway.yml" "$(VENV)/bin/python" $(or $(NAME),all)
	@echo "Loading them into Vault (vault_gateway):"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" gateway TAGS=vault

## Refresh the sandbox ssh-agent's Vault-signed certificate (scenario 4)
agent-cert:
	@"$(OPERATOR_DIR)/bin/ai-sandbox-agent-cert"

## Print how to load the vault/consul CLI environment (unix sockets, operator tokens; read-only use)
cli:
	@test -r "$(OPERATOR_DIR)/env.sh" || { echo "No $(OPERATOR_DIR)/env.sh: run make -f lab-gateway.mk gateway"; exit 1; }
	@echo ". $(OPERATOR_DIR)/env.sh"

## Break-glass: a 15-minute, audited token that reads the real credentials, in a shell or CMD (REASON="why")
break-glass: guard
	@test -n "$(REASON)" || { echo 'Usage: make -f lab-gateway.mk break-glass REASON="why" [CMD="vault kv get ..."]'; exit 1; }
	@$(ANSIBLE_ENV) BREAK_GLASS_REASON="$(REASON)" BREAK_GLASS_WRAP="$(BREAK_GLASS_WRAP)" \
		$(VENV)/bin/ansible-playbook -i "$(HOST_INVENTORY)" "$(LAB_DIR)/ansible/playbooks/break-glass.yml"
	@"$(GATEWAY_SCRIPTS)/break-glass.sh" "$(OPERATOR_DIR)" "$(BREAK_GLASS_WRAP)" $(CMD)

## List the egress allow list (Consul K/V): baseline and operator entries
allowlist:
	@"$(GATEWAY_SCRIPTS)/egress-allowlist.sh" "$(OPERATOR_DIR)" list

## Allow HOST=<host:port> [REASON="..."] through the CONNECT tunnel
allow:
	@test -n "$(HOST)" || { echo "Usage: make -f lab-gateway.mk allow HOST=example.com:443 REASON=\"why\""; exit 1; }
	@"$(GATEWAY_SCRIPTS)/egress-allowlist.sh" "$(OPERATOR_DIR)" add "$(HOST)" "$(REASON)"

## Remove HOST=<host:port> from the operator allow list
deny:
	@test -n "$(HOST)" || { echo "Usage: make -f lab-gateway.mk deny HOST=example.com:443"; exit 1; }
	@"$(GATEWAY_SCRIPTS)/egress-allowlist.sh" "$(OPERATOR_DIR)" remove "$(HOST)"
