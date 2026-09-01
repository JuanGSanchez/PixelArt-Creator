# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure autosave-policy decision function — zero Qt (S11).

Phase-10 Slice A (ADR-0026 §4; spec REQ-P10-LOGIC-002). "Should we autosave now?"
is a **pure, deterministic** function of its inputs — the document-dirty flag, an
elapsed-tick marker, and the last-autosave marker — compared against
:data:`~pixelart_creator.logic.constants.AUTOSAVE_INTERVAL_MS`. Elapsed time is an
**input**, never read from a wall clock inside the function, so the policy is
unit-testable without Qt, a real clock, randomness, or locale.

The caller (``ui/`` autosave timer, off the interactive loop — REQ-P10-LOGIC-004)
supplies a monotonic tick reading (e.g. from ``time.monotonic_ns()`` converted to
ms, or a Qt elapsed timer) as ``elapsed_ticks`` and the tick at which the last
autosave completed as ``last_autosave_marker``. This module does the decision, not a
widget or timer callback.
"""

from __future__ import annotations

from typing import Any

from pixelart_creator.logic.constants import AUTOSAVE_INTERVAL_MS

__all__ = [
    "AutosaveError",
    "should_autosave",
]


class AutosaveError(ValueError):
    """Raised when autosave-policy inputs are malformed or non-monotonic."""


def _require_nonneg_int(value: Any, name: str) -> None:
    """Raise :class:`AutosaveError` unless ``value`` is a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AutosaveError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise AutosaveError(f"{name} must be >= 0, got {value}")


def should_autosave(
    dirty: bool,
    elapsed_ticks: int,
    last_autosave_marker: int,
    interval_ms: int = AUTOSAVE_INTERVAL_MS,
) -> bool:
    """Decide whether an autosave is due — pure and deterministic.

    Returns ``True`` iff the document is dirty **and** at least ``interval_ms``
    ticks have elapsed since the last autosave (``elapsed_ticks -
    last_autosave_marker >= interval_ms``). A clean document never autosaves.

    Args:
        dirty: Whether the working document has unsaved changes.
        elapsed_ticks: Current monotonic tick reading, ms (an input, not a clock
            read here).
        last_autosave_marker: The tick reading at which the last autosave
            completed, ms.
        interval_ms: Minimum ms between autosaves; defaults to
            :data:`AUTOSAVE_INTERVAL_MS`.

    Raises:
        AutosaveError: If ``dirty`` is not a bool; if ``elapsed_ticks`` or
            ``last_autosave_marker`` is not a non-negative int; if ``interval_ms``
            is not a positive int; or if ``elapsed_ticks < last_autosave_marker``
            (a non-monotonic tick contract violation).
    """
    if not isinstance(dirty, bool):
        raise AutosaveError(f"dirty must be a bool, got {dirty!r}")
    _require_nonneg_int(elapsed_ticks, "elapsed_ticks")
    _require_nonneg_int(last_autosave_marker, "last_autosave_marker")
    if isinstance(interval_ms, bool) or not isinstance(interval_ms, int):
        raise AutosaveError(f"interval_ms must be an int, got {interval_ms!r}")
    if interval_ms <= 0:
        raise AutosaveError(f"interval_ms must be > 0, got {interval_ms}")
    if elapsed_ticks < last_autosave_marker:
        raise AutosaveError(
            f"elapsed_ticks ({elapsed_ticks}) must be >= last_autosave_marker "
            f"({last_autosave_marker})"
        )
    if not dirty:
        return False
    return (elapsed_ticks - last_autosave_marker) >= interval_ms
