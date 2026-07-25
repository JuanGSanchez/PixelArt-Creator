"""Shared pytest/Hypothesis configuration for the logic test suite (no Qt).

Registers a deterministic Hypothesis profile so property-based tests are
reproducible and portable in CI (NFR-2, plan §7): a fixed random seed and
``derandomize=True`` remove run-to-run flakiness while keeping the shrinking
behaviour. Loaded for every ``tests/logic`` module.
"""

from __future__ import annotations

import pytest
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


@pytest.fixture
def registry_guard():
    """Isolate the module-global DSL op registry (``logic.scripting``).

    Phase-8's op registry is a module-global (AGT-03 report §8): a test that
    registers/unregisters ops must not leak into its neighbours. This snapshots
    the registered op-names on entry and unregisters any op added during the test
    on exit, so built-ins survive and per-test ops are cleaned up.
    """
    from pixelart_creator.logic import scripting

    before = set(scripting.registered_ops())
    yield scripting
    for name in scripting.registered_ops():
        if name not in before:
            scripting.unregister_command(name)


@pytest.fixture
def plugins_guard():
    """Isolate the module-global enabled-plugin table (``logic.plugins``).

    Yields the ``plugins`` module and, on exit, disables every plugin still
    enabled so ``loaded_count()`` returns to its pre-test value and any ops the
    plugin registered are unregistered (``PluginHandle.disable``).
    """
    from pixelart_creator.logic import plugins

    yield plugins
    for handle in list(plugins._LOADED.values()):
        handle.disable()
