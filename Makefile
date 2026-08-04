# Semiconductor Manufacturing SPC Monitoring Platform — task runner.
#
# Every target here is a thin call into scripts/ci/gate.sh, which holds the one
# definition of each gate. CI calls the same script with the same gate names,
# so `make check` and a CI run cannot disagree about what was checked.

GATE := scripts/ci/gate.sh
GATES := $(shell $(GATE) --list)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo "Semiconductor SPC platform — available targets"
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Gate order used by 'make check': $(GATES)"

# --- Environment -----------------------------------------------------------

.PHONY: install
install: ## Create the environment from the committed lockfile
	uv sync --frozen --all-groups

.PHONY: lock
lock: ## Re-resolve dependencies and update uv.lock
	uv lock

.PHONY: hooks
hooks: ## Install the pre-commit hooks into .git/hooks
	uv run --frozen pre-commit install --install-hooks

# --- The gate set ----------------------------------------------------------

.PHONY: check
check: ## Run every gate, in CI order, stopping at the first failure
	@for gate in $(GATES); do $(GATE) $$gate || exit 1; done
	@echo
	@echo "All gates passed: $(GATES)"

.PHONY: format
format: ## G1 — Ruff format check
	@$(GATE) format

.PHONY: lint
lint: ## G1 — Ruff lint
	@$(GATE) lint

.PHONY: typecheck
typecheck: ## G2 — mypy --strict
	@$(GATE) typecheck

.PHONY: architecture
architecture: ## G3 — import-linter contracts
	@$(GATE) architecture

.PHONY: docs
docs: ## Internal documentation links and anchors
	@$(GATE) docs

.PHONY: unit
unit: ## G4 — unit tier
	@$(GATE) unit

.PHONY: statistical
statistical: ## G5 — statistical validation tier
	@$(GATE) statistical

.PHONY: contract
contract: ## G6 — contract tier
	@$(GATE) contract

.PHONY: integration
integration: ## G7 — integration tier
	@$(GATE) integration

.PHONY: e2e
e2e: ## G8 — end-to-end tier
	@$(GATE) e2e

.PHONY: performance
performance: ## G9 — performance budgets
	@$(GATE) performance

.PHONY: security
security: ## G10 — bandit, pip-audit, gitleaks
	@$(GATE) security

.PHONY: coverage
coverage: ## G11 — coverage non-regression in domain/ and analytics/
	@$(GATE) coverage

# --- Convenience -----------------------------------------------------------

.PHONY: fix
fix: ## Apply the formatting and lint fixes Ruff can make safely
	uv run --frozen ruff format .
	uv run --frozen ruff check --fix .

.PHONY: test
test: ## The pre-commit test subset: unit and statistical tiers
	@$(GATE) unit
	@$(GATE) statistical

.PHONY: clean
clean: ## Remove caches and coverage artefacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.json
	rm -f .coverage .coverage.*
	find src tests scripts -name '__pycache__' -type d -prune -exec rm -rf {} +
