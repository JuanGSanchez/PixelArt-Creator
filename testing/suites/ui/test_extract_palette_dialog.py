"""Auto-extract-from-image dialog acceptance tests (REQ-P3-UI-010).

One test per acceptance criterion for :class:`Extract_Palette_Dialog`:

* SC-U010-1 extracting from an image yields a ≤N palette.
* SC-U010-2 the N control defaults to ``PALETTE_EXTRACT_DEFAULT_N`` and bounds
  the result.
* SC-U010-3 the median-cut / k-means choice is offered; controls are tr()-wrapped
  and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

from pixelart_creator.logic.constants import PALETTE_EXTRACT_DEFAULT_N
from pixelart_creator.ui.extract_palette_dialog import (
    METHOD_KMEANS,
    METHOD_MEDIAN_CUT,
    Extract_Palette_Dialog,
    image_to_buffer,
)


def _rainbow_image(size: int = 16) -> QImage:
    """An image with many distinct colours (one per pixel column * row)."""
    image = QImage(size, size, QImage.Format.Format_RGBA8888)
    for y in range(size):
        for x in range(size):
            image.setPixelColor(
                x, y, QColor((x * 13) % 256, (y * 17) % 256, (x * y) % 256)
            )
    return image


@pytest.fixture
def dialog(qtbot) -> Extract_Palette_Dialog:
    dlg = Extract_Palette_Dialog()
    qtbot.addWidget(dlg)
    return dlg


# -- SC-U010-1 (extraction yields a ≤N palette) --------------------------------


def test_sc_u010_1_extraction_yields_at_most_n(dialog):
    """SC-U010-1: extracting from a many-colour image returns ≤N colours."""
    dialog._source = image_to_buffer(_rainbow_image())
    dialog._n_spin.setValue(8)
    dialog._on_accept()
    palette = dialog.result_palette()
    assert palette is not None
    assert len(palette) <= 8


# -- SC-U010-2 (N defaults to the constant and bounds the result) --------------


def test_sc_u010_2_n_defaults_to_constant(dialog):
    """SC-U010-2: the N spin defaults to PALETTE_EXTRACT_DEFAULT_N."""
    assert dialog.target_count() == PALETTE_EXTRACT_DEFAULT_N


def test_sc_u010_2_result_bounded_by_n_for_kmeans(dialog):
    """SC-U010-2: k-means also respects the ≤N bound."""
    dialog._source = image_to_buffer(_rainbow_image())
    dialog._method_combo.setCurrentIndex(1)  # k-means
    dialog._n_spin.setValue(5)
    dialog._on_accept()
    palette = dialog.result_palette()
    assert palette is not None
    assert len(palette) <= 5


# -- SC-U010-3 (method choice offered; tr()-wrapped + keyboard-reachable) ------


def test_sc_u010_3_offers_both_methods_labelled_and_focusable(dialog):
    """SC-U010-3: both extraction methods are offered with labels + focusable."""
    tokens = {
        dialog._method_combo.itemData(i) for i in range(dialog._method_combo.count())
    }
    assert tokens == {METHOD_MEDIAN_CUT, METHOD_KMEANS}
    for i in range(dialog._method_combo.count()):
        assert dialog._method_combo.itemText(i) != ""
    assert dialog.windowTitle() != ""
    assert dialog._n_spin.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert dialog._method_combo.focusPolicy() != Qt.FocusPolicy.NoFocus


# -- guard / edge-path coverage (defensive branches) ---------------------------


def test_choose_image_null_warns_and_leaves_ok_disabled(dialog, monkeypatch):
    """Choosing an unreadable image warns and keeps OK disabled (no source)."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        "pixelart_creator.ui.extract_palette_dialog.QFileDialog.getOpenFileName",
        lambda *a, **k: ("/no/such/image.png", ""),
    )
    warned: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )
    dialog._on_choose_image()
    assert warned
    assert not dialog._ok_button.isEnabled()


def test_choose_image_cancelled_is_no_op(dialog, monkeypatch):
    """Cancelling the image chooser (empty path) does nothing."""
    monkeypatch.setattr(
        "pixelart_creator.ui.extract_palette_dialog.QFileDialog.getOpenFileName",
        lambda *a, **k: ("", ""),
    )
    dialog._on_choose_image()
    assert dialog.result_palette() is None


def test_accept_without_source_is_no_op(dialog):
    """Accepting with no chosen image yields no palette (guard branch)."""
    dialog._on_accept()
    assert dialog.result_palette() is None
