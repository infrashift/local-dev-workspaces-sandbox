# ==========================================
# lab-bootstrap-verify.mk -- verify the host after lab-bootstrap.mk
#
#   make -f lab-bootstrap-verify.mk           # = all: build .pytest/, run tests/host
#   make -f lab-bootstrap-verify.mk PYTEST_ARGS="-k ssh"
#
# The order of operations is:
#   make -f lab-bootstrap.mk all  ->  make -f lab-bootstrap-verify.mk
#   make -f lab-gateway.mk        ->  make -f lab-gateway-verify.mk
#   make -f lab-provision.mk apply  ->  make -f lab-provision-verify.mk
# The gateway has a suite of its own (lab-gateway-verify.mk, tests/gateway).
#
# The tests are read-only and need no sudo. They read every expected value
# from its source (lab-config.mk, the host playbook's pin block,
# requirements.lock, requirements.yml, terraform.tfvars), so they never
# restate a pin. A failed test names the make target that fixes it.
#
# pytest runs in its own venv, .pytest/ at the project root, built by uv from
# the hashed requirements-pytest.lock (lab-gateway-verify.mk and
# lab-provision-verify.mk use it too).
# ==========================================
include $(dir $(lastword $(MAKEFILE_LIST)))lab-config.mk

# Extra pytest arguments, e.g. PYTEST_ARGS="-k ssh -x".
PYTEST_ARGS ?=

.DEFAULT_GOAL := all
.PHONY: help all host-guard uv-guard venv lock

## Display this help message
help:
	@echo "Usage: make -f lab-bootstrap-verify.mk [target] [PYTEST_ARGS=...]"
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

## Verify the host (the default): build .pytest/, then run tests/host
all: host-guard venv
	@$(PYTEST_ENV) "$(PYTEST_VENV)/bin/pytest" -c "$(TESTS_DIR)/pytest.ini" "$(TESTS_DIR)/host" $(PYTEST_ARGS)

host-guard:
	@if [ "$$(uname -sm)" != "Linux x86_64" ]; then \
		echo "Error: this lab needs a Linux x86_64 host (uname: $$(uname -sm))"; exit 1; \
	fi

uv-guard:
	@test -x "$(UV)" || { echo "uv missing at $(UV): run make -f lab-bootstrap.mk all"; exit 1; }

## Create/sync the .pytest venv from the hashed requirements-pytest.lock
venv: uv-guard
	@$(UV) python install $(PYTHON_VERSION)
	@if [ ! -x "$(PYTEST_VENV)/bin/python" ]; then \
		echo ">>> Creating $(PYTEST_VENV) (Python $(PYTHON_VERSION))..."; \
		$(UV) venv "$(PYTEST_VENV)" --python $(PYTHON_VERSION); \
	fi
	@$(UV) pip sync --quiet --require-hashes --python "$(PYTEST_VENV)/bin/python" "$(PYTEST_LOCK)"

## Re-pin requirements-pytest.lock (with hashes) after editing requirements-pytest.txt
lock: uv-guard
	@cd "$(PROJECT_ROOT)" && $(UV) pip compile --generate-hashes \
		--python-version $(PYTHON_VERSION) --python-platform $(PYTHON_PLATFORM) \
		--custom-compile-command "make -f labs/$(LAB_NAME)/lab-bootstrap-verify.mk lock" \
		requirements-pytest.txt -o requirements-pytest.lock
	@echo ">>> requirements-pytest.lock updated; run 'make -f lab-bootstrap-verify.mk venv' and commit both files."
