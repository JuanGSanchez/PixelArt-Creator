"""Shared pytest/Hypothesis configuration for the logic test suite (no Qt).

Registers a deterministic Hypothesis profile so property-based tests are
reproducible and portable in CI (NFR-2, plan §7): a fixed random seed and
``derandomize=True`` remove run-to-run flakiness while keeping the shrinking
behaviour. Loaded for every ``tests/logic`` module.
"""

from __future__ import annotations

from hypothesis import HealthCheck, settings

# Register once; guard against re-registration if another conftest already did.
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
