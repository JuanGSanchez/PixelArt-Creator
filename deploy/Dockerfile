# Container image for the shipped sync_backend/ asyncio-websockets relay.
# Phase-13 Slice 13C (REQ-P13-BACKEND-001, Researcher Q4). Builds an image that runs
# the EXISTING, UNMODIFIED sync_backend/ on a generic VPS via the deploy/ launcher —
# NO backend source change (artifacts only).
#
# Deliberately Qt-free: the backend import chain (SyncServer -> logic.sync_protocol ->
# logic.cloud_validation -> logic.constants + store) touches only stdlib + `websockets`.
# We therefore copy the source and install ONLY `websockets` — never PySide6/numpy/
# Pillow/pycrdt (the GUI/desktop stack), keeping the image small.

# Base pinned to the project's single parametric source: the repo-root
# `.python-version` file ("3.13.13"), confirmed on Docker Hub 2026-05-20
# (design-docs/research/research-ci-python-3-13-13-pins.md, Q3). Kept in sync
# by scripts/check_python_version.py (exact-patch precision for this site).
FROM python:3.13.13-slim-bookworm

# Fail fast, unbuffered logs (so `docker logs` / journald see the "listening" line).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Only runtime dependency of the backend import chain. Pinned to match pyproject.toml
# ("websockets==16.0") so the container runs the exact wire library CI tests against.
RUN pip install --no-cache-dir "websockets==16.0"

# Copy just the source the relay needs. sync_backend/ stays byte-identical (copied,
# never edited). pixelart_creator/ supplies the pure logic/ framing the backend imports;
# deploy/ supplies the run-forever launcher. PYTHONPATH=/app lets both packages resolve.
COPY pixelart_creator/ /app/pixelart_creator/
COPY sync_backend/ /app/sync_backend/
COPY deploy/ /app/deploy/

ENV PYTHONPATH=/app

# VPS-facing bind + default port (Q4: bind 0.0.0.0, not localhost). The relay serves
# plain WS; TLS is terminated by the Nginx reverse proxy (deploy/nginx-sync.conf).
ENV PIXELART_SYNC_HOST=0.0.0.0 \
    PIXELART_SYNC_PORT=8765

# Dedicated non-root service user (least privilege).
RUN useradd --system --no-create-home --uid 10001 pixelart-sync
USER pixelart-sync

# The relay listens on the configured port (keep in sync with PIXELART_SYNC_PORT).
EXPOSE 8765

# File-descriptor ceiling (Q4 scaling floor): each live WebSocket client holds an fd, so
# the ~10K-connections/process ceiling needs a raised nofile limit. EXPOSE/USER cannot
# set ulimits — the OPERATOR MUST pass it at run time:
#
#   docker build -f deploy/Dockerfile -t pixelart-sync .
#   docker run --rm \
#       --ulimit nofile=65535:65535 \    # Q4 FD floor >= 65535 (~10K conns/process)
#       -p 8765:8765 \
#       pixelart-sync
#
# Python is PID 1 here and handles SIGTERM itself (deploy/run_sync_backend.py registers
# a graceful SIGTERM -> stop() handler), so `docker stop` shuts the relay down cleanly.
CMD ["python", "deploy/run_sync_backend.py"]
