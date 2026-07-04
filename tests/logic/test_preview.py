"""Tests for pixelart_creator.logic.preview — real-size scale.

REQ-P9-LOGIC-007 [GEO]: real_size_scale(doc_ppi, screen_dpi) == screen_dpi/doc_ppi
— a pure, deterministic ratio (no DPR math; DPR is the ui/ concern). Equal DPI/PPI
→ 1.0; the DEFAULT_DOCUMENT_PPI default; non-positive/non-finite inputs raise
PreviewError. Zero Qt. Maps to SC-L007-1.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.preview import PreviewError, real_size_scale


def test_real_size_scale_is_dpi_over_ppi():
    assert real_size_scale(72.0, 144.0) == 2.0
    assert real_size_scale(96.0, 48.0) == 0.5


def test_equal_dpi_ppi_is_unity():
    # SC-L007-1 edge case: matching resolutions render 1:1.
    assert real_size_scale(96.0, 96.0) == 1.0


def test_default_document_ppi_constant():
    assert constants.DEFAULT_DOCUMENT_PPI == 72.0
    # At the default document PPI a 72-DPI screen renders 1:1.
    assert real_size_scale(constants.DEFAULT_DOCUMENT_PPI, 72.0) == 1.0


def test_real_size_scale_deterministic():
    assert real_size_scale(72.0, 110.0) == real_size_scale(72.0, 110.0)


@pytest.mark.parametrize(
    "doc_ppi,screen_dpi",
    [
        (0.0, 96.0),
        (-72.0, 96.0),
        (72.0, 0.0),
        (72.0, -96.0),
        (float("nan"), 96.0),
        (72.0, float("inf")),
        (True, 96.0),
        (72.0, "x"),
    ],
)
def test_real_size_scale_rejects_invalid(doc_ppi, screen_dpi):
    with pytest.raises(PreviewError):
        real_size_scale(doc_ppi, screen_dpi)  # type: ignore[arg-type]


@given(
    doc_ppi=st.floats(
        min_value=1.0, max_value=2000.0, allow_nan=False, allow_infinity=False
    ),
    screen_dpi=st.floats(
        min_value=1.0, max_value=2000.0, allow_nan=False, allow_infinity=False
    ),
)
def test_property_scale_equals_ratio(doc_ppi, screen_dpi):
    assert real_size_scale(doc_ppi, screen_dpi) == pytest.approx(screen_dpi / doc_ppi)
