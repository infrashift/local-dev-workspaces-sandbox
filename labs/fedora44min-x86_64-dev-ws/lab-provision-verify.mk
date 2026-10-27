# ==========================================
# lab-provision-verify.mk -- verify the lab VMs after lab-provision.mk
#
#   make -f lab-provision-verify.mk                      # = all: tests/guest/baseline
#   make -f lab-provision-verify.mk STACK=python-stack   # ... plus tests/guest/python-stack
#   make -f lab-provision-verify.mk STACK=sandbox        # ... plus the gateway end to end
#   make -f lab-provision-verify.mk PYTEST_ARGS="-k ca_trust"
#
# baseline checks what `make -f lab-provision.mk apply` builds: the VMs are
# running and match Terraform (no drift), cloud-init finished, the admin and
# dev users, the egress configuration, the gateway CA trust and the
# dev_packages. STACK=<name> adds the tests for a stack applied with
# `make -f lab-provision.mk play PLAYBOOK=<name>`; STACK=sandbox proves the
# zero-trust gateway end to end after the python-stack (isolation, no secrets
# in the guest, the scenarios with the three GitHub MCP servers, anti-replay).
# The baseline also checks the optional TLS-inspection chain on every lab VM.
#
# The tests reach each VM through the ssh configs the lab_ssh role wrote
# (~/.ssh/config.d/local.<lab>@{admin,dev}). They run in the .pytest/ venv
# that lab-bootstrap-verify.mk builds. All are read-only.
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# A stack whose tests run after the baseline's: a directory in tests/guest/.
STACK ?=
# Extra pytest arguments, e.g. PYTEST_ARGS="-k users -x".
PYTEST_ARGS ?=

GUEST_TESTS = $(TESTS_DIR)/guest/baseline $(if $(STACK),$(TESTS_DIR)/guest/$(STACK))

.DEFAULT_GOAL := all
.PHONY: help all inventory-guard stack-guard

## Display this help message
help:
	@echo "Usage: make -f lab-provision-verify.mk [target] [STACK=<name>] [PYTEST_ARGS=...]"
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

## Verify the lab VMs (the default): tests/guest/baseline, plus tests/guest/$(STACK)
all: inventory-guard stack-guard
	@$(MAKE) --no-print-directory -f "$(LAB_DIR)/lab-bootstrap-verify.mk" venv
	@$(PYTEST_ENV) "$(PYTEST_VENV)/bin/pytest" -c "$(TESTS_DIR)/pytest.ini" $(GUEST_TESTS) $(PYTEST_ARGS)

inventory-guard:
	@test -f "$(TF_DIR)/output-data/terraform-hosts.yml" || { echo "No VM inventory yet: run make -f lab-provision.mk apply"; exit 1; }

stack-guard:
	@if [ -n "$(STACK)" ] && [ ! -d "$(TESTS_DIR)/guest/$(STACK)" ]; then \
		echo "No tests for STACK=$(STACK). Stacks with tests:"; \
		ls "$(TESTS_DIR)/guest" | grep -v -e '^baseline$$' -e '\.py$$' -e '^__' | sed 's/^/  /'; exit 1; \
	fi
