# ==========================================
# lab-gateway-verify.mk -- verify the gateway after lab-gateway.mk
#
#   make -f lab-gateway-verify.mk           # = all: run tests/gateway
#   make -f lab-gateway-verify.mk PYTEST_ARGS="-k allowlist"
#
# The order of operations is:
#   make -f lab-bootstrap.mk all  ->  make -f lab-bootstrap-verify.mk
#   make -f lab-gateway.mk        ->  make -f lab-gateway-verify.mk
#   make -f lab-provision.mk apply  ->  make -f lab-provision-verify.mk
#
# The tests are read-only and need no sudo: they check root-owned state
# through what the operator can see (unit state, file modes, listeners, and
# the loopback Vault, Consul and Envoy admin APIs with the operator tokens).
# They read every expected value from its source (lab-config.mk, the gateway
# playbook's pin block, vars/gateway.yml, egress-baseline.yml), and a failed
# test names the make target that fixes it.
#
# pytest runs in the .pytest/ venv that lab-bootstrap-verify.mk builds.
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# Extra pytest arguments, e.g. PYTEST_ARGS="-k vault -x".
PYTEST_ARGS ?=

.DEFAULT_GOAL := all
.PHONY: help all host-guard venv

## Display this help message
help:
	@echo "Usage: make -f lab-gateway-verify.mk [target] [PYTEST_ARGS=...]"
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

## Verify the gateway (the default): sync .pytest/, then run tests/gateway
all: host-guard venv
	@$(PYTEST_ENV) "$(PYTEST_VENV)/bin/pytest" -c "$(TESTS_DIR)/pytest.ini" "$(TESTS_DIR)/gateway" $(PYTEST_ARGS)

host-guard:
	@if [ "$$(uname -sm)" != "Linux x86_64" ]; then \
		echo "Error: this lab needs a Linux x86_64 host (uname: $$(uname -sm))"; exit 1; \
	fi

# One test venv, built in one place.
venv:
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-bootstrap-verify.mk" venv
