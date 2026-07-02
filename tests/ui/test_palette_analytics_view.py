"""Palette-analytics view acceptance tests (REQ-P3-UI-011).

One test per acceptance criterion for :class:`Palette_Analytics_View`:

* SC-U011-1 the view lists per-colour usage counts (from logic).
* SC-U011-2 the view is sortable and read-only.
* SC-U011-3 the view is tr()-wrapped, keyboard-reachable, legible in both themes.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_analytics import document_usage_counts
from pixelart_creator.ui.palette_analytics_view import Palette_Analytics_View

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


@pytest.fixture
def view(qtbot):
    """A view bound to a small painted RGBA document ``(view, document)``."""
    document = Document(8, 8, palette=Palette(STARTER))
    buffer = document.frames[0].layers[0].buffer
    for x in range(4):
        buffer.set_pixel(x, 0, (230, 30, 30, 255))
    for x in range(2):
        buffer.set_pixel(x, 1, (255, 255, 255, 255))
    widget = Palette_Analytics_View()
    qtbot.addWidget(widget)
    widget.set_document_provider(lambda: document)
    widget.refresh()
    return widget, document


# -- SC-U011-1 (lists per-colour usage counts from logic) ----------------------


def test_sc_u011_1_lists_usage_counts_from_logic(view):
    """SC-U011-1: the table row count matches the logic usage-count result."""
    widget, document = view
    expected = document_usage_counts(document)
    assert widget._table.rowCount() == len(expected)
    # Total of the count column equals the document pixel count (8*8).
    total = sum(
        int(widget._table.item(r, 1).data(Qt.ItemDataRole.DisplayRole))
        for r in range(widget._table.rowCount())
    )
    assert total == document.width * document.height


# -- SC-U011-2 (sortable, read-only) -------------------------------------------


def test_sc_u011_2_view_is_sortable_and_read_only(view):
    """SC-U011-2: sorting is enabled and no cell is editable."""
    widget, _document = view
    assert widget._table.isSortingEnabled()
    assert widget._table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


# -- SC-U011-3 (tr()-wrapped, keyboard-reachable, both themes) -----------------


def test_sc_u011_3_labelled_and_keyboard_reachable(view):
    """SC-U011-3: labels are set and the table takes keyboard focus."""
    widget, _document = view
    assert widget.accessibleName() != ""
    assert widget._table.accessibleName() != ""
    assert widget._refresh_button.text() != ""
    assert widget._table.focusPolicy() != Qt.FocusPolicy.NoFocus
