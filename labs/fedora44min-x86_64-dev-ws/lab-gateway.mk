# ==========================================
# lab-gateway.mk -- the zero-trust surrogate-credential gateway on this host,
# for fedora44min-x86_64-dev-ws (concepts/Zero-Trust Surrogate Gateway)
#
#   make -f lab-gateway.mk                 # = gateway: dry run, then apply
#   make -f lab-gateway.mk secret-set      # once: encrypt the real GitHub PATs and Anthropic key
#   make -f lab-gateway.mk check           # read-only: is the gateway ready, the allow list in step?
#   make -f lab-gateway.mk allow-list|allow|deny|allow-plan|allow-sync   # the egress allow list
#   make -f lab-gateway.mk secrets-list|secret-rotate|secret-add|...     # the real credentials
#   eval "$(make -s -f lab-gateway.mk cli)"        # vault/consul CLIs, read-only
#   make -f lab-gateway.mk break-glass REASON=...  # 15 minutes with the real credentials
#
# Day 2, the operator's files (committed; the targets edit them, so commit after a change):
#   ansible/vars/egress-allow.yml     the operator allow list: https, tcp and ssh entries
#   ansible/vars/gateway-secrets.yml  the registry of real credentials (names, never values)
# lab-sandbox-ops.mk gathers these targets with the lab's own (start, ssh, verify).
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
# vars/{gateway,gateway-secrets,egress-baseline,egress-allow}.yml, tests/gateway/
# and these two makefiles.
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# Optional: limit the playbook to some roles, e.g. TAGS=vault,envoy:
#   binaries pki vault consul envoy firewall ssh_agent
TAGS ?=

GATEWAY = $(VENV)/bin/ansible-playbook -i "$(HOST_INVENTORY)" -e '$(LAB_VARS)' $(if $(TAGS),--tags $(TAGS)) \
	"$(LAB_DIR)/ansible/playbooks/gateway-host.yml"
GATEWAY_SCRIPTS := $(SCRIPTS)/gateway
VARS_DIR        := $(LAB_DIR)/ansible/vars
PYTHON          := $(VENV)/bin/python
# The allow file <-> Consul (egress-allowlist.sh, rules in egress_allow.py).
ALLOWLIST = "$(GATEWAY_SCRIPTS)/egress-allowlist.sh" "$(OPERATOR_DIR)" "$(VARS_DIR)" "$(PYTHON)"
# The secrets registry and vault.yml (sandbox-secret.sh, rules in gateway_secrets.py).
SECRET = "$(GATEWAY_SCRIPTS)/sandbox-secret.sh" "$(VARS_DIR)" "$(CREDENTIALS_VAULT)" "$(VAULT_KEY)" \
	"$(VENV)/bin/ansible-vault" "$(PYTHON)" "$(OPERATOR_DIR)"
REPORT = "$(PYTHON)" -I "$(GATEWAY_SCRIPTS)/gateway_report.py"
# The sandbox agent's certificate (sandbox_ssh_agent).
AGENT_CERT := $(HOME)/.ssh/key.d/ai-sandbox.egress-cert.pub
# allow/deny: HOST=<host:port>, or HOST=<host> PORT=<port>.
ENTRY = $(HOST)$(if $(PORT),:$(PORT))
# allow USER=<login> (kind ssh). Only from the command line: the environment's
# USER is the operator's own login, never an ssh target's.
SSH_USER = $(if $(filter command line,$(origin USER)),$(USER))
# denied/audit: how far back to look (<n>m, <n>h, <n>d).
SINCE ?= 24h
# break-glass.yml leaves its single-use wrapping token here (tmpfs, 0600).
BREAK_GLASS_WRAP := /run/user/$(shell id -u)/ai-sandbox-break-glass.wrap

.DEFAULT_GOAL := gateway
.PHONY: help guard gateway check secrets secrets-list secrets-check secret-set secret-rotate secret-add \
	secret-remove agent-cert agent-cert-status allowlist allow-list allow-plan allow-sync allow deny \
	ssh-principals denied audit cli break-glass

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

## Read-only readiness report: the dry run finds nothing to change, the allow list and the secrets agree
check: guard
	@$(ANSIBLE_ENV) CHECK_ONLY=1 "$(SCRIPTS)/ansible-confirm.sh" $(GATEWAY) \
		|| { echo "Gateway is not ready: run make -f lab-gateway.mk"; exit 1; }
	@$(ALLOWLIST) plan || { echo "The allow list is out of step with egress-allow.yml: make -f lab-gateway.mk allow-sync"; exit 1; }
	@$(SECRET) check
	@echo "Gateway is ready."

# --- Credentials: vars/gateway-secrets.yml (names) + vault.yml (values) -----

## List the real credentials: kind, repository, held in vault.yml, loaded into Vault, rotated, expires
secrets-list:
	@$(SECRET) list

## Check that the secrets registry, the surrogates and vault.yml agree, and nothing has expired
secrets-check:
	@$(SECRET) check

## Set secrets at a hidden prompt (NAME=<name>, default: each one vault.yml lacks), then load them into Vault [EXPIRES=]
secret-set: guard
	@$(SECRET) set $(or $(NAME),all) $(EXPIRES)
	@echo "Loading them into Vault (vault_gateway):"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" gateway TAGS=vault

# The name before the registry existed.
secrets: secret-set

## Replace NAME=<name>'s value, record today and its new expiry in the registry, then load it [EXPIRES=YYYY-MM-DD]
secret-rotate: guard
	@test -n "$(NAME)" || { echo "Usage: make -f lab-gateway.mk secret-rotate NAME=<name> [EXPIRES=YYYY-MM-DD]"; exit 1; }
	@$(SECRET) rotate "$(NAME)" $(EXPIRES)
	@echo "Loading it into Vault (vault_gateway):"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" gateway TAGS=vault

## Register a new secret and set it: NAME=<name> KIND=github-pat|anthropic-api-key [REPO=<owner/name>]
secret-add: guard
	@test -n "$(NAME)" -a -n "$(KIND)" || { echo "Usage: make -f lab-gateway.mk secret-add NAME=<name> KIND=github-pat REPO=<owner/name>"; exit 1; }
	@$(SECRET) add "$(NAME)" "$(KIND)" $(REPO)
	@echo "Then: add its surrogates to vars/gateway.yml (above), make -f lab-gateway.mk gateway, and the guest playbook."

## Remove NAME=<name> from the registry and vault.yml (remove its surrogates from vars/gateway.yml first)
secret-remove:
	@test -n "$(NAME)" || { echo "Usage: make -f lab-gateway.mk secret-remove NAME=<name>"; exit 1; }
	@$(SECRET) remove "$(NAME)"

# --- The sandbox ssh-agent ---------------------------------------------------

## Refresh the sandbox ssh-agent's Vault-signed certificate (scenario 4)
agent-cert:
	@"$(OPERATOR_DIR)/bin/ai-sandbox-agent-cert"

## Show the sandbox agent certificate's principals and how long it is still valid
agent-cert-status:
	@test -r "$(AGENT_CERT)" || { echo "No $(AGENT_CERT): make -f lab-gateway.mk agent-cert"; exit 1; }
	@ssh-keygen -L -f "$(AGENT_CERT)" | $(REPORT) agent 3600; rc=$$?; [ $$rc -ne 3 ] || rc=0; \
		[ $$rc -eq 0 ] || echo "Renew it: make -f lab-gateway.mk agent-cert"; exit $$rc

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

# --- Egress: vars/egress-allow.yml -> Consul allow/ -> Envoy -----------------

## List the egress allow list: baseline (catalog) and operator (egress-allow.yml) entries, with any drift
allow-list:
	@$(ALLOWLIST) list

# The name before the allow file existed.
allowlist: allow-list

## Show what allow-sync would change in Consul to match egress-allow.yml (exit 2 when out of step)
allow-plan:
	@$(ALLOWLIST) plan

## Make Consul's allow list match egress-allow.yml (after a typed "yes"), and the agent's ssh principals
allow-sync:
	@$(ALLOWLIST) sync
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" ssh-principals

## Allow HOST=<host:port> REASON="why" [KIND=https|tcp|ssh] [USER=<ssh login>] [EXPIRES=YYYY-MM-DD]
allow:
	@test -n "$(HOST)" -a -n "$(REASON)" || { echo "Usage: make -f lab-gateway.mk allow HOST=example.com:443 REASON=\"why\" [KIND=] [USER=] [EXPIRES=]"; exit 1; }
	@$(ALLOWLIST) add "$(ENTRY)" "$(REASON)" "$(or $(KIND),-)" "$(or $(SSH_USER),-)" "$(or $(EXPIRES),-)"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" ssh-principals

## Remove HOST=<host:port> from the operator allow list (egress-allow.yml and Consul)
deny:
	@test -n "$(HOST)" || { echo "Usage: make -f lab-gateway.mk deny HOST=example.com:443"; exit 1; }
	@$(ALLOWLIST) remove "$(ENTRY)"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" ssh-principals

# When the allow file's ssh users differ from the agent certificate's
# principals, re-run the gateway for Vault's SSH role and the agent.
ssh-principals:
	@$(ALLOWLIST) principals-drift \
		|| $(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk" gateway TAGS=vault,ssh_agent

## The CONNECTs the tunnel refused, by host:port: candidates for the allow list [SINCE=24h]
denied:
	@journalctl -u envoy --since "-$(SINCE)" -o cat --no-pager | $(REPORT) denied "$(VARS_DIR)/gateway.yml"

## Break-glass activity in Vault's audit log: mints (who, why), unwraps, reads [SINCE=7d] (uses sudo)
audit: SINCE = 7d
audit:
	@sudo cat /var/log/vault/audit.log | $(REPORT) audit "$(SINCE)"
