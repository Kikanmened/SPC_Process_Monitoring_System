#!/usr/bin/env bash
#
# Every quality gate, defined once.
#
# `make check` runs these in order; the GitHub Actions workflow runs each as
# its own job by name. Neither holds its own copy of a command, so local and
# CI cannot drift — which is the only reason `make check` is worth trusting.
#
# Gate identifiers map to QUALITY_ASSURANCE_PLAN.md §3 (G1–G12) and the stage
# order in TESTING_STRATEGY.md §9: fastest-failing first, so a formatting slip
# never consumes a full test run.
#
# Usage:
#   scripts/ci/gate.sh <gate>
#   scripts/ci/gate.sh --list

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

# Ordered. `make check` depends on this order.
GATES=(
  format
  lint
  typecheck
  architecture
  docs
  unit
  statistical
  contract
  integration
  e2e
  performance
  security
  coverage
)

py() {
  uv run --frozen "$@"
}

# A tier with no tests yet exits 5 from pytest. That is reported as EMPTY
# rather than passed silently: until Phase 9 populates the statistical tier and
# Phase 10 the integration tier, an empty tier is the expected state, and
# hiding it would make the gate decorative. Remove this once every tier is
# populated.
run_tier() {
  local marker="$1"
  shift
  local status=0
  py pytest -m "${marker}" "$@" || status=$?
  if [ "${status}" -eq 5 ]; then
    echo "EMPTY: no test carries the '${marker}' marker yet."
    return 0
  fi
  return "${status}"
}

gate_format() {
  py ruff format --check .
}

gate_lint() {
  py ruff check .
}

gate_typecheck() {
  py mypy
}

gate_architecture() {
  py lint-imports
}

gate_docs() {
  py python scripts/ci/check_docs_links.py
}

gate_unit() {
  run_tier unit
}

# Reported separately everywhere it runs. A failure here means a number the
# platform produces is wrong, and that must be unmistakable rather than buried
# among passing unit tests (QUALITY_ASSURANCE_PLAN.md §3).
gate_statistical() {
  run_tier statistical
}

gate_contract() {
  run_tier contract
}

gate_integration() {
  run_tier integration
}

gate_e2e() {
  run_tier e2e
}

gate_performance() {
  run_tier performance
}

gate_security() {
  py bandit --configfile pyproject.toml --recursive src scripts --quiet
  # Audit the locked dependency set rather than the installed environment: the
  # lockfile is what production installs, and exporting it excludes this
  # project's own editable install, which has no PyPI advisory record. --strict
  # is kept, so a dependency that cannot be audited fails the gate rather than
  # being quietly reported as clean.
  local requirements
  requirements="$(mktemp)"
  uv export --frozen --all-groups --no-emit-project --no-hashes \
    --format requirements-txt --quiet --output-file "${requirements}"
  py pip-audit --strict --no-deps --progress-spinner off --requirement "${requirements}"
  rm -f "${requirements}"
  scripts/ci/gitleaks.sh
}

gate_coverage() {
  rm -f coverage.json .coverage .coverage.*
  run_tier "unit or statistical" --cov=spc_platform --cov-report=term-missing
  py coverage json --quiet -o coverage.json
  py python scripts/ci/check_coverage.py
}

usage() {
  echo "usage: scripts/ci/gate.sh <gate>" >&2
  echo "gates: ${GATES[*]}" >&2
}

main() {
  if [ "$#" -ne 1 ]; then
    usage
    return 2
  fi

  if [ "$1" = "--list" ]; then
    printf '%s\n' "${GATES[@]}"
    return 0
  fi

  local gate="$1"
  local known=0
  for candidate in "${GATES[@]}"; do
    if [ "${candidate}" = "${gate}" ]; then
      known=1
      break
    fi
  done
  if [ "${known}" -eq 0 ]; then
    echo "unknown gate: ${gate}" >&2
    usage
    return 2
  fi

  echo "──▶ ${gate}"
  "gate_${gate}"
}

main "$@"
