# =============================================================================
# CI-ONLY container image -- the Linux leg of scripts/run_ci.py's local
# fallback (AGT-09 GitHub/DevOps). NOT the product's own deployment artifact.
#
# LOCATION JUSTIFICATION: this repository already has a `deploy/Dockerfile`,
# which builds the SHIPPED sync_backend/ relay image (referenced by name from
# tests/deploy/test_vps_localhost.py's `_DOCKERFILE` constant) -- a real,
# load-bearing, product deployment artifact. Putting a SECOND, unrelated
# Dockerfile (this one: "run the desktop-app test suite headlessly") under
# that same `deploy/` root would conflate two different concerns under one
# folder name -- "deploy the product to a VPS" vs "run CI checks in a
# container" -- exactly the kind of ambiguity this project's layout
# discipline avoids elsewhere. `.ci/` is therefore a distinct, dedicated root
# for CI-only machinery, parallel in spirit to `.github/` (GitHub-owned CI
# config) but for the container-execution side of the same job.
#
# WHAT THIS IMAGE IS FOR: gives `scripts/run_ci.py --local`'s Linux leg (and
# a developer invoking it directly) a container that can import/run PySide6
# headlessly, so `scripts/run_ci_locally.py --job quality-gate` can execute
# inside it exactly as it does natively on Windows. It reproduces ONLY the
# Ubuntu-runner OS-library layer of `.github/workflows/ci.yml`'s
# `quality-gate` job -- it does not attempt to reproduce GitHub's full hosted
# runner image (see UNVERIFIED note below).
#
# UNVERIFIED, STATED PLAINLY: this file was authored and has NEVER BEEN BUILT
# OR RUN in the session that wrote it -- the host has no Docker, no Podman,
# and no WSL2 (verified this session: all three absent). Every line below is
# derived directly from ci.yml's own committed step (see DRIFT GUARD below),
# not invented, but "derived correctly" is not the same claim as "built and
# ran successfully" -- it has not been exercised. Do not report this image as
# working; report it as unverified until someone with a container runtime
# actually builds and runs it.
#
# DRIFT GUARD: the apt package list immediately below MUST stay identical to
# `.github/workflows/ci.yml`'s "Install Qt runtime OS libraries (Ubuntu)"
# step. `scripts/check_ci_docker_drift.py` parses BOTH files and fails (exit
# 1) the moment they disagree; `scripts/run_ci.py`'s Linux-leg fallback runs
# that guard before every image build, so a stale list blocks the build
# instead of silently shipping. That guard is NOT (yet) wired into
# `.github/workflows/ci.yml` itself -- editing ci.yml is out of scope for the
# task that authored this file; this is a known, reported gap, not an
# oversight (see scripts/check_ci_docker_drift.py's own header and the
# accompanying subagent report).
#
# DOCKER HUB ANONYMOUS PULL LIMIT (why a cold build can start failing with NO
# code change): pulling this base image anonymously (no `docker login`) is
# rate-limited by Docker Hub to 100 pulls / 6h per IPv4 address (vs 200 / 6h
# for an authenticated free account) -- confirmed 2026-08-02,
# https://docs.docker.com/docker-hub/usage/pulls/ (see
# design-docs/research/research-local-ci-github-docker.md §C2). A shared
# office/CI-runner IP can exhaust that budget from unrelated pulls alone; if
# builds start failing with a 429/rate-limit error and nothing in this file
# changed, that is almost certainly why -- `docker login` (free account,
# still no payment method needed) doubles the budget.
#
# BASE IMAGE PINNING: pinned by TAG (python:3.12-slim-bookworm) to match
# ci.yml's `actions/setup-python` pin (python-version: "3.12") and this
# project's own `deploy/Dockerfile` base choice, for consistency across the
# two Dockerfiles in this repo. NOT pinned by digest yet -- a future
# hardening step could add `@sha256:<digest>` for fully reproducible pulls;
# left as a tag pin for now so routine Debian/Python patch updates keep
# flowing without a manual re-pin, matching this project's existing
# deploy/Dockerfile convention. Note this explicitly rather than silently
# picking one: digest-pinning is a real, deferred hardening item.
# =============================================================================
FROM python:3.12-slim-bookworm

# Fail fast, unbuffered logs -- matches deploy/Dockerfile's convention so
# pytest/pip output streams live instead of buffering silently.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Headless Qt (F11) -- the SAME env var ci.yml sets at workflow level, so a
# step run inside this container behaves like the Ubuntu leg, not a step
# that forgot to set it.
ENV QT_QPA_PLATFORM=offscreen \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ----- Qt runtime OS libraries (Ubuntu) -- COPIED VERBATIM from ci.yml's own
# "Install Qt runtime OS libraries (Ubuntu)" step (F11: xkbcommon, EGL/GL,
# dbus, X libs for the offscreen platform plugin). scripts/check_ci_docker_
# drift.py enforces that this list and that step never silently disagree --
# see the DRIFT GUARD note above. Do not edit this list without also
# updating ci.yml (or vice versa); the guard will fail the Linux leg build
# the moment the two diverge, which is the intended behaviour, not a bug to
# work around by editing the guard.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libegl1 libgl1 libxkbcommon0 libdbus-1-3 \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 && \
    rm -rf /var/lib/apt/lists/*

# NO project source is baked into this image. The Linux leg (scripts/run_ci.
# py's run_linux_leg_in_container) bind-mounts the working tree at run time
# (`docker run -v <repo>:/workspace -w /workspace ...`) and installs the
# project's own pinned dependency closure (`pip install -c constraints.txt
# -e ".[dev]"`) against that mount before invoking scripts/run_ci_locally.py
# inside the container -- so the container always tests the REAL, current
# working tree, never a copy frozen at image-build time. This mirrors why
# ci.yml's own "Install project" step runs after `actions/checkout`, not
# before: dependency installation must see the actual source being tested.
WORKDIR /workspace

# No CMD/ENTRYPOINT: scripts/run_ci.py passes the full install-then-test
# command explicitly on every `docker run` invocation (see its own header),
# so there is nothing this image should run unattended.
