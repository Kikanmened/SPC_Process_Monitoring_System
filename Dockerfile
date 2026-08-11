# Multi-stage image — DEPLOYMENT_PLAN.md §4.
# Build: docker build -t spc-platform:local .
# Runtime is non-root, lockfile-frozen, no build toolchain.

FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /usr/local/bin/uv
WORKDIR /build

# Install into /opt/venv (not /build/.venv) so console-script shebangs still
# resolve after the runtime-stage copy. Relocating .venv breaks #! paths and
# yields: exec /opt/venv/bin/uvicorn: no such file or directory.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY dashboard/ dashboard/
COPY configs/ configs/
COPY data/reference/ data/reference/

RUN uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

# WeasyPrint system libraries (Phase 13 deferred PDF runtime).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        libglib2.0-0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin --uid 10001 spc

WORKDIR /app

COPY --from=builder --chown=spc:spc /opt/venv /opt/venv
COPY --chown=spc:spc src/ /app/src/
COPY --chown=spc:spc dashboard/ /app/dashboard/
COPY --chown=spc:spc configs/ /app/configs/
COPY --chown=spc:spc data/reference/ /app/data/reference/
COPY --chown=spc:spc scripts/ops/ /app/scripts/ops/
COPY --chown=spc:spc migrations/ /app/migrations/
COPY --chown=spc:spc alembic.ini /app/alembic.ini
COPY scripts/ops/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src:/app" \
    SPC_PROFILE=local \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Entrypoint starts as root only to chown volume mounts, then setpriv to uid 10001.
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD spc-platform health || exit 1

CMD ["uvicorn", "spc_platform.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
