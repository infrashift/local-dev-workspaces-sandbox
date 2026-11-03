# ==========================================
# lab-sandbox-ops.mk -- the sandbox operator's Day 2 entry point for
# fedora44min-x86_64-dev-ws: one place for the tasks that recur once the lab
# is built (runbooks/Operate the Sandbox (Day 2) in the wiki).
#
#   make -f lab-sandbox-ops.mk                    # = help, by section
#   make -f lab-sandbox-ops.mk up | down | status # after a host reboot; before leaving
#   make -f lab-sandbox-ops.mk ssh                # the dev session (renews the agent certificate first)
#   make -f lab-sandbox-ops.mk allow HOST=example.com:443 REASON="why"
#   make -f lab-sandbox-ops.mk secret-rotate NAME=private-scratch-1
#
# It holds no logic of its own: every target runs one in lab-gateway.mk,
# lab-provision.mk or a -verify.mk suite, which stay the owners (the gateway
# keeps its own lane: concepts/Gateway Separated from the Host Bootstrap).
# Variables given here (HOST=, NAME=, VM=, STACK=, ...) pass through.
#
# The first build, once, in order:
#   make -f lab-bootstrap.mk all   ->  make -f lab-bootstrap-verify.mk
#   make -f lab-gateway.mk         ->  make -f lab-gateway-verify.mk
#   make -f lab-provision.mk apply ->  make -f lab-provision-verify.mk
#
# The operator's files (committed; allow, deny and the secret-* targets edit
# them, so commit after a change):
#   ansible/vars/egress-allow.yml     the operator allow list: https, tcp and ssh entries
#   ansible/vars/gateway-secrets.yml  the registry of real credentials (names, never values)
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

GATEWAY_MK   = $(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway.mk"
PROVISION_MK = $(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-provision.mk"
# The gateway's services: system units, and the operator's sandbox agent.
GATEWAY_UNITS := vault ai-sandbox-vault-unseal vault-proxy consul ai-sandbox-consul-template envoy ai-sandbox-firewall
AGENT_UNIT    := ai-sandbox-ssh-agent.service
ROLE ?= dev

.DEFAULT_GOAL := help
.PHONY: help up down status gateway-status ssh console allow-list allow deny allow-plan allow-sync denied \
	secrets-list secret-set secret-rotate secret-add secret-remove secrets-check break-glass audit \
	agent-cert agent-cert-status gateway apply play verify lint

## Display this help message, by section
help:
	@echo "Usage: make -f lab-sandbox-ops.mk [target] [VAR=value ...]"
	@awk '/^##@ / { printf "\n%s\n", substr($$0, 5); next } \
		/^[a-zA-Z_0-9-]+:/ { \
			if (match(lastLine, /^## (.*)/)) { \
				printf "  %-20s %s\n", substr($$1, 0, index($$1, ":")-1), substr(lastLine, RSTART + 3, RLENGTH); \
			} \
		} \
		{ lastLine = $$0 }' "$(LAB_DIR)/lab-sandbox-ops.mk"

##@ Lifecycle

## After a host reboot: check the gateway's services, start the VMs, renew the agent certificate, show status
up: gateway-status
	@$(PROVISION_MK) start
	@$(GATEWAY_MK) agent-cert-status >/dev/null 2>&1 || $(GATEWAY_MK) agent-cert
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-sandbox-ops.mk" status

## Stop the VMs (ACPI shutdown); the gateway keeps running
down:
	@$(PROVISION_MK) stop

## One screen: VMs, gateway services, agent certificate, allow-list drift, secrets
status:
	@$(PROVISION_MK) status
	@echo
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-sandbox-ops.mk" gateway-status || true
	@printf '%-36s ' "agent certificate"; $(GATEWAY_MK) agent-cert-status 2>&1 | head -1 || true
	@printf '%-36s ' "allow list"; $(GATEWAY_MK) allow-plan >/dev/null 2>&1 \
		&& echo "egress-allow.yml and Consul agree" || echo "OUT OF STEP: make -f lab-sandbox-ops.mk allow-plan"
	@printf '%-36s ' "secrets"; $(GATEWAY_MK) secrets-check 2>&1 | tail -1

# Every gateway service is active (fails, naming them, when one is not).
gateway-status:
	@down=""; for u in $(GATEWAY_UNITS); do \
		state=$$(systemctl is-active "$$u" 2>/dev/null); printf '%-36s %s\n' "$$u" "$$state"; \
		[ "$$state" = active ] || down="$$down $$u"; \
	done; \
	state=$$(systemctl --user is-active $(AGENT_UNIT) 2>/dev/null); printf '%-36s %s\n' "$(AGENT_UNIT) (user)" "$$state"; \
	[ "$$state" = active ] || down="$$down $(AGENT_UNIT)"; \
	[ -z "$$down" ] || { echo "Not active:$$down. journalctl -u <unit>, or make -f lab-gateway.mk"; exit 1; }

## SSH into the sandbox as ROLE=dev (default; renews the agent certificate when under 1h is left) or ROLE=admin
ssh:
	@[ "$(ROLE)" != dev ] || $(GATEWAY_MK) agent-cert-status >/dev/null 2>&1 || $(GATEWAY_MK) agent-cert
	@$(PROVISION_MK) ssh

## Attach to a VM's serial console (Ctrl-] to leave) [VM=]
console:
	@$(PROVISION_MK) console

##@ Egress (ansible/vars/egress-allow.yml)

## The allow list: baseline and operator entries, with any drift between the file and Consul
allow-list:
	@$(GATEWAY_MK) $@

## Allow HOST=<host:port> REASON="why" [KIND=https|tcp|ssh] [USER=<ssh login>] [EXPIRES=YYYY-MM-DD]
allow:
	@$(GATEWAY_MK) $@

## Remove HOST=<host:port> from the operator allow list
deny:
	@$(GATEWAY_MK) $@

## What allow-sync would change in Consul to match the file
allow-plan:
	@$(GATEWAY_MK) $@

## Make Consul match the file, after a typed "yes" (after editing it by hand, or a pull)
allow-sync:
	@$(GATEWAY_MK) $@

## The CONNECTs the tunnel refused, by host:port: candidates for the allow list [SINCE=24h]
denied:
	@$(GATEWAY_MK) $@

##@ Credentials (ansible/vars/gateway-secrets.yml + vault.yml)

## The real credentials: held, loaded into Vault, rotated, expiring
secrets-list:
	@$(GATEWAY_MK) $@

## Set secrets at a hidden prompt [NAME=<name>] [EXPIRES=], then load them into Vault
secret-set:
	@$(GATEWAY_MK) $@

## Replace NAME=<name>'s value and record its dates [EXPIRES=YYYY-MM-DD], then load it
secret-rotate:
	@$(GATEWAY_MK) $@

## Register and set a new secret: NAME=<name> KIND=github-pat|anthropic-api-key [REPO=<owner/name>]
secret-add:
	@$(GATEWAY_MK) $@

## Remove NAME=<name> from the registry and vault.yml (after removing its surrogates)
secret-remove:
	@$(GATEWAY_MK) $@

## The registry, the surrogates and vault.yml agree, and nothing has expired
secrets-check:
	@$(GATEWAY_MK) $@

## Break-glass: a 15-minute, audited token that reads the real credentials (REASON="why" [CMD=])
break-glass:
	@$(GATEWAY_MK) $@

## Break-glass activity in Vault's audit log [SINCE=7d] (uses sudo)
audit:
	@$(GATEWAY_MK) $@

##@ SSH (the sandbox ssh-agent)

## Renew the sandbox agent's Vault-signed certificate
agent-cert:
	@$(GATEWAY_MK) $@

## The agent certificate's principals and how long it is still valid
agent-cert-status:
	@$(GATEWAY_MK) $@

##@ Change and verify

## Apply the gateway playbook: dry run, then "yes" [TAGS=]
gateway:
	@$(GATEWAY_MK) $@

## Create or update the VMs and run site.yml: dry run, then "yes"
apply:
	@$(PROVISION_MK) $@

## Run PLAYBOOK=<name> on the VMs (e.g. python-stack): dry run, then "yes"
play:
	@$(PROVISION_MK) $@

## Verify the gateway, then the VMs [STACK=python-stack|sandbox]
verify:
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-gateway-verify.mk"
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-provision-verify.mk"

## Lint the shell scripts, YAML, playbooks, role contract, UAT specs and Python
lint:
	@$(PROVISION_MK) $@
