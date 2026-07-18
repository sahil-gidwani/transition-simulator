# syntax=docker/dockerfile:1
# Built from the repo root: docker build -f server/Dockerfile .
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS build

# Optional extra root CAs for TLS-inspecting proxies (see docker/certs/README.md).
# The directory ships with only a README; update-ca-certificates ignores non-.crt files.
COPY docker/certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
ENV UV_NATIVE_TLS=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
# Dependency layer: invalidated only when the lockfile changes.
COPY server/pyproject.toml server/uv.lock server/.python-version ./
RUN uv sync --locked --no-default-groups --no-install-project
# Project layer: wheel install (offline; uv_build packages app+pipeline) so
# /api/health reports the real package version.
COPY server/app/ app/
COPY server/pipeline/ pipeline/
RUN uv sync --locked --no-default-groups --no-editable

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=build /app/.venv .venv
COPY server/data/processed/ data/processed/
ENV PATH="/app/.venv/bin:$PATH" \
    PRECEDENT_DATA_DIR=/app/data/processed \
    PYTHONUNBUFFERED=1

RUN useradd --system --create-home --shell /usr/sbin/nologin precedent
USER precedent

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
