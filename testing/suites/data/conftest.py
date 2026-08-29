"""Shared pytest/Hypothesis configuration for the data test suite (no Qt).

Mirrors ``tests/logic/conftest.py``: registers the deterministic ``ci``
Hypothesis profile so any property-based data test is reproducible and portable
in CI (NFR-2). Loaded for every ``tests/data`` module.
"""

from __future__ import annotations

from hypothesis import HealthCheck, settings

try:  # pragma: no cover - registration guard
    settings.register_profile(
        "ci",
        derandomize=True,
        deadline=None,
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
    )
except Exception:  # pragma: no cover - already registered
    pass

settings.load_profile("ci")
