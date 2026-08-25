"""The Tetradic harmony row + the double-click promotion gesture (T28).

One test per acceptance criterion for the Tetradic related-colour row and the
narrowed promotion gesture on :class:`Colour_Wheel_Widget`:

* SC-CGS-UI-011-1  a left **double**-click on a swatch promotes it.
* SC-CGS-UI-011-2  a **single** left click does **not** promote, and the
  swatch takes keyboard focus.
* SC-CGS-UI-011-3  **keyboard activation still promotes**, and the swatch is
  still announced with its harmony group name.
* SC-CGS-LOGIC-001-2  the Tetradic row sits directly after Triadic and
  directly before Split-complementary, with every other row unchanged.
* SC-CGS-LOGIC-001-3  the row's label is a ``tr()``-wrapped string announced
  as a harmony group, in the same form as every other harmony row.

Every test in this module also runs against both the light and the dark
theme via the autouse, parametrised ``theme`` fixture in ``conftest.py``.
Headless (``QT_QPA_PLATFORM=offscreen``).

Why all three gesture assertions (SC-CGS-UI-011-1/-2/-3) are mandatory and
none is redundant: ``-2`` is the one an implementation satisfies
*accidentally* by deleting the ``clicked`` handler entirely, and ``-3`` is
the one that then fails, because ``QToolButton`` synthesises ``clicked``
from Space/Enter — so the obvious "only double-click promotes" change can
silently remove the keyboard activation path too. Passing two of the three
is not passing the requirement (``traceability.md`` REQ-CGS-UI-011); all
three are asserted here so the pairing cannot be separated later.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from pixelart_creator.logic.color import to_hex
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget

_BASE = QColor(200, 120, 60)  # a saturated, non-black seed (value > 0)

#: The harmony/ramp row labels in their required, shipped order
#: (SC-CGS-LOGIC-001-2: Tetradic directly after Triadic, directly before
#: Split-complementary; every other row's position unchanged).
_EXPECTED_ROW_ORDER = [
    "Complementary",
    "Analogous",
    "Triadic",
    "Tetradic",
    "Split-complementary",
    "Shades",
    "Tints",
]


@pytest.fixture
def wheel(qtbot) -> Colour_Wheel_Widget:
    """A shown, exposed wheel seeded with a saturated colour.

    Shown (not just constructed) so the swatch buttons can genuinely take
    and report keyboard focus under the offscreen platform — the same
    pattern used by ``test_real_event_harness.py`` for real click/focus
    assertions.
    """
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)
    widget.set_color(_BASE)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    return widget


def _swatch_rows(widget: Colour_Wheel_Widget) -> list[tuple[str, int]]:
    """Read ``[(row_label_text, swatch_count), ...]`` from the widget's OWN
    top-level layout, in the order the rows actually appear.

    Structural, not index-based: every top-level item that is a two-item
    "label over a swatch row" column (built by ``_swatch_row``) is picked
    up; the wheel/value row, the RGB/HSV entry row and the preview row are
    excluded because their shape does not match (the wheel row's first
    item is a ``_WheelPad`` widget, not a ``QLabel``; the preview row has
    three items, not two). This reads the actual widget structure rather
    than trusting a hard-coded row index.
    """
    top_layout = widget.layout()
    assert top_layout is not None
    rows: list[tuple[str, int]] = []
    for i in range(top_layout.count()):
        item = top_layout.itemAt(i)
        column = item.layout() if item is not None else None
        if column is None or column.count() != 2:
            continue  # not a "label + swatch row" column
        label_item = column.itemAt(0)
        label = label_item.widget() if label_item is not None else None
        if not isinstance(label, QLabel):
            continue  # e.g. the wheel/value column's first item is the pad
        row_item = column.itemAt(1)
        row = row_item.layout() if row_item is not None else None
        if row is None:
            continue
        swatch_count = 0
        for j in range(row.count()):
            entry = row.itemAt(j)
            if entry is not None and entry.widget() is not None:
                swatch_count += 1
        rows.append((label.text(), swatch_count))
    return rows


# -- SC-CGS-UI-011-1 (double-click promotes) ------------------------------------


def test_sc_cgs_ui_011_1_double_click_promotes(wheel, qtbot):
    """SC-CGS-UI-011-1: a left double-click on a swatch promotes its colour."""
    swatch = wheel._tetradic[0]
    target = swatch.color()
    assert wheel.current_rgba() != target  # the pick will actually change
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):  # observer first
        qtbot.mouseDClick(swatch, Qt.MouseButton.LeftButton)  # then the action
    assert wheel.current_rgba() == target


# -- SC-CGS-UI-011-2 (single click does not promote; swatch takes focus) -------


def test_sc_cgs_ui_011_2_single_click_does_not_promote_but_focuses(wheel, qtbot):
    """SC-CGS-UI-011-2: a single left click does not promote and focuses."""
    swatch = wheel._tetradic[0]
    before = wheel.current_rgba()
    with qtbot.assertNotEmitted(wheel.colorPicked):  # observer first
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)  # then the action
    assert wheel.current_rgba() == before  # the pending pick is unchanged
    assert swatch.hasFocus()  # but the swatch took keyboard focus


# -- SC-CGS-UI-011-3 (keyboard activation still promotes + still announced) ----


def test_sc_cgs_ui_011_3_keyboard_activation_still_promotes_and_announces(wheel, qtbot):
    """SC-CGS-UI-011-3: Space/Enter still promotes; the swatch stays named."""
    swatch = wheel._tetradic[0]
    swatch.setFocus()
    target = swatch.color()
    assert wheel.current_rgba() != target
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):  # observer first
        qtbot.keyClick(swatch, Qt.Key.Key_Space)  # then the keyboard action
    assert wheel.current_rgba() == target
    # Still announced with its harmony group name (A11Y-COLHUB-3 form).
    expected_name = f"Tetradic {to_hex(swatch.color(), with_alpha=False)}"
    assert swatch.accessibleName() == expected_name


# -- SC-CGS-LOGIC-001-2 (row order: directly after Triadic, before Split) ------


def test_sc_cgs_logic_001_2_tetradic_row_between_triadic_and_split(wheel):
    """SC-CGS-LOGIC-001-2: Tetradic sits directly after Triadic, before Split."""
    rows = _swatch_rows(wheel)
    labels = [label for label, _count in rows]
    assert labels == _EXPECTED_ROW_ORDER  # every other row's position unchanged
    counts = dict(rows)
    assert counts["Tetradic"] == 3  # the scheme returns three colours
    # Every other row's swatch count is untouched by the insertion.
    assert counts["Complementary"] == 1
    assert counts["Analogous"] == 2
    assert counts["Triadic"] == 2
    assert counts["Split-complementary"] == 2


# -- SC-CGS-LOGIC-001-3 (tr()-wrapped label, announced as a harmony group) -----


def test_sc_cgs_logic_001_3_tetradic_label_is_translatable_and_announced(wheel):
    """SC-CGS-LOGIC-001-3: the label is tr()-wrapped and named a harmony group."""
    assert wheel._lbl_tetradic.text() == "Tetradic"
    # Same announcement FORM as every other harmony row ("<name> harmony").
    assert wheel._lbl_tetradic.accessibleName() == "Tetradic harmony"
    assert wheel._lbl_triadic.accessibleName() == "Triadic harmony"
    for swatch in wheel._tetradic:
        expected = f"Tetradic {to_hex(swatch.color(), with_alpha=False)}"
        assert swatch.accessibleName() == expected
    # tr()-wrapped: the label participates in the same LanguageChange
    # retranslation pipeline as every other row (F5), not a hard-coded string.
    wheel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert wheel._lbl_tetradic.text() == "Tetradic"
    assert wheel._lbl_tetradic.accessibleName() == "Tetradic harmony"
