"""Real-size preview scale — pure device-independent math, zero Qt (S11).

The one pure geometry input the real-size preview needs (ADR-0023 §4, research §4):
the device-independent screen-pixels-per-document-pixel factor
``real_size_scale(doc_ppi, screen_dpi) = screen_dpi / doc_ppi``. This lives here,
Qt-free and unit-testable; the Qt DPI *query* (``QScreen.physicalDotsPerInch()``)
and the manual on-screen-ruler calibration live in ``ui/`` (REQ-P9-LOGIC-007).

**DPR caveat (the highest-risk finding, research §4.2):** ``physicalDotsPerInch()``
is *already* device-independent and Qt applies ``devicePixelRatio()`` automatically,
so the UI must **NOT** multiply the scale by DPR — doing so double-scales on HiDPI.
This module therefore does **no** DPR math; it is a single closed-form ratio.

Constants come from :mod:`pixelart_creator.logic.constants` (S12): the document PPI
default is ``DEFAULT_DOCUMENT_PPI``, a first-class :class:`~pixelart_creator.logic.
document.Document` field (ADR-0025 §1).
"""

from __future__ import annotations

import math

__all__ = ["PreviewError", "real_size_scale"]


class PreviewError(ValueError):
    """Raised on an invalid real-size scale input (non-positive PPI/DPI)."""


def real_size_scale(doc_ppi: float, screen_dpi: float) -> float:
    """Return the device-independent screen-px-per-doc-px factor.

    ``screen_dpi / doc_ppi`` — how many device-independent screen pixels one
    document pixel occupies so the artwork appears at true physical size (research
    §4.1). Pure and deterministic; **no** DPR math (Qt applies DPR — ADR-0023 §4)
    (REQ-P9-LOGIC-007/-009; SC-L007-1).

    Args:
        doc_ppi: The document's pixels-per-inch (``Document.ppi``), ``> 0``.
        screen_dpi: The monitor's physical DPI (from ``QScreen`` or manual
            calibration), ``> 0``.

    Raises:
        PreviewError: If either value is not a finite number ``> 0``.
    """
    _require_positive(doc_ppi, "doc_ppi")
    _require_positive(screen_dpi, "screen_dpi")
    return screen_dpi / doc_ppi


def _require_positive(value: object, name: str) -> None:
    """Raise :class:`PreviewError` unless ``value`` is a finite number ``> 0``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreviewError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value) or value <= 0.0:
        raise PreviewError(f"{name} must be finite and > 0, got {value}")
