#!/bin/sh
# Ensure volume mount points are writable by the non-root service account,
# then drop privileges (DEPLOYMENT_PLAN.md §4 — non-root runtime).
set -eu

DATA_ROOT="${SPC_DATA_ROOT:-/var/spc/data}"
LOG_ROOT="${SPC_LOG_ROOT:-/var/spc/logs}"
BACKUP_ROOT="${SPC_BACKUP_ROOT:-/var/spc/backups}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p \
    "$DATA_ROOT/raw" \
    "$DATA_ROOT/interim" \
    "$DATA_ROOT/processed" \
    "$DATA_ROOT/ops" \
    "$DATA_ROOT/archive/quarantine" \
    "$LOG_ROOT/audit" \
    "$BACKUP_ROOT"
  # Bind mounts (e.g. raw:ro) may refuse chown; ignore those failures.
  chown -R spc:spc "$DATA_ROOT/interim" "$DATA_ROOT/processed" "$DATA_ROOT/ops" \
    "$DATA_ROOT/archive" "$LOG_ROOT" "$BACKUP_ROOT" 2>/dev/null || true
  chown spc:spc "$DATA_ROOT" 2>/dev/null || true
  # Preserve a writable HOME for Streamlit/config under the service account.
  export HOME=/home/spc
  export USER=spc
  exec setpriv --reuid=10001 --regid=10001 --clear-groups -- "$@"
fi

exec "$@"
