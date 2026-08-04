#!/usr/bin/env bash
#
# Secret scanning — gate G10, objective Q7 (QUALITY_ASSURANCE_PLAN.md §1, §3).
#
# gitleaks is a Go binary rather than a Python package, so it is fetched from
# its pinned release and cached in .tools/. The download is checksum-verified
# against the checksums file published with the same release: an unverified
# binary in a security gate is worse than no gate, because it is trusted.
#
# The version is pinned deliberately. A scanner that silently updates changes
# what "clean" means between two runs of the same commit.

set -euo pipefail

GITLEAKS_VERSION="8.30.1"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS_DIR="${REPO_ROOT}/.tools"
BINARY="${TOOLS_DIR}/gitleaks-${GITLEAKS_VERSION}"

detect_asset() {
  local os arch
  case "$(uname -s)" in
    Darwin) os="darwin" ;;
    Linux) os="linux" ;;
    *)
      echo "gitleaks: unsupported operating system $(uname -s)" >&2
      return 1
      ;;
  esac
  case "$(uname -m)" in
    arm64 | aarch64) arch="arm64" ;;
    x86_64 | amd64) arch="x64" ;;
    *)
      echo "gitleaks: unsupported architecture $(uname -m)" >&2
      return 1
      ;;
  esac
  echo "gitleaks_${GITLEAKS_VERSION}_${os}_${arch}.tar.gz"
}

install_gitleaks() {
  local asset base workdir
  asset="$(detect_asset)"
  base="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
  workdir="$(mktemp -d)"
  trap 'rm -rf "${workdir}"' RETURN

  echo "Fetching gitleaks ${GITLEAKS_VERSION} (${asset})"
  curl --fail --silent --show-error --location --output "${workdir}/${asset}" "${base}/${asset}"
  curl --fail --silent --show-error --location \
    --output "${workdir}/checksums.txt" \
    "${base}/gitleaks_${GITLEAKS_VERSION}_checksums.txt"

  (cd "${workdir}" && grep " ${asset}\$" checksums.txt | shasum -a 256 -c -)

  tar -xzf "${workdir}/${asset}" -C "${workdir}" gitleaks
  mkdir -p "${TOOLS_DIR}"
  mv "${workdir}/gitleaks" "${BINARY}"
  chmod +x "${BINARY}"
}

if [ ! -x "${BINARY}" ]; then
  install_gitleaks
fi

cd "${REPO_ROOT}"

# The working tree is scanned unconditionally. History is scanned as well when
# there is history: a secret that was committed and then removed is still
# disclosed, and `gitleaks dir` cannot see it.
"${BINARY}" dir . --no-banner --redact --exit-code 1

if git rev-parse HEAD >/dev/null 2>&1; then
  "${BINARY}" git . --no-banner --redact --exit-code 1
else
  echo "No commits yet; skipping history scan."
fi
