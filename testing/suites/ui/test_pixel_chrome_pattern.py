"""The faint pattern: where it may appear and where it may not (REQ-VI-UI-011).

Covers **SC-VI-UI-011-1** (no pattern pixel lies under text), **SC-VI-UI-011-2** (the pattern
appears only on the two enumerated areas) and **SC-VI-UI-011-3** (the canvas workspace
stays one flat colour) -- each over all six style x mode combinations.

The two areas are P1, the tool toolbar's empty tail, and P2, the Timeline dock's strip right
of the transport controls (both are placed in ``main_window.py``; P2 is NOT in
``timeline_panel.py``).

How a "pattern pixel" is defined without trusting the product's own idea of one. The window
is rendered twice with the SAME widget tree: once as shipped and once with the pattern tile
replaced by a fully transparent one (the "off" seam; the ground fill is still painted). A
pixel that differs between the two renders is a pattern pixel, wherever it is and whichever
widget painted it. A determinism control renders the shipped state twice and requires the
two to be identical, so a difference can only come from the pattern. Text is judged by the
rectangle of every visible text-bearing control (labels, buttons, fields, combo and spin
boxes, tab bars, item views): a deliberate SUPERSET of the glyph box.

Controls (a check that cannot fail proves nothing):

* the on/off render of a ``Pattern_Area_Widget`` that hosts labels, with the clip DISABLED,
  shows pattern pixels under the labels (bleed); with the shipped clip it shows none, even
  within the clearance the product promises around each child;
* the "only on the two areas" check flags a third ``Pattern_Area_Widget`` planted in a dock;
* the flat-workspace check flags a pattern area planted over the canvas viewport.

The numbers (boxes examined, pattern pixels present, per area) are printed and asserted
non-zero. Limits, stated and not hidden: offscreen platform, device-pixel ratio 1, the window
laid out at 1800 x 900 so the P2 strip has a width (at the default 807 px window the transport
controls fill the dock and P2 is zero wide, by design); dialogs are rendered through the
About dialog only, which holds no pattern area.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QTabBar,
    QWidget,
)

from pixelart_creator.logic.constants import PATTERN_CHILD_CLEARANCE_PX
from pixelart_creator.ui import pixel_chrome
from pixelart_creator.ui.about_dialog import About_Dialog
from pixelart_creator.ui.appearance_settings import (
    default_appearance,
    save_appearance,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.pixel_chrome import Pattern_Area_Widget
from pixelart_creator.ui.theme import (
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
    canvas_surface_roles,
)
from testing.suites.ui.conftest import assert_settings_isolated
from testing.suites.ui.test_theme import (
    _COMBO_IDS,
    COMBOS,
    Combo,
    _array,
    _rgb,
    _settle,
    _unfocus,
)

_TEXT_TYPES = (
    QLabel,
    QAbstractButton,
    QLineEdit,
    QComboBox,
    QAbstractSpinBox,
    QTabBar,
    QAbstractItemView,
)

#: The layout the P2 strip needs to have a width (see the module note).
_WINDOW_SIZE = (1800, 900)


# --------------------------------------------------------------------------- #
# Fixtures and helpers                                                         #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture (this module is six-way)."""
    apply_theme(qapp, THEME_LIGHT)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store) -> None:
    """Fail before any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest, qapp) -> Combo:
    """One of the six style x mode combinations, applied to the application."""
    chosen: Combo = request.param
    apply_theme(qapp, chosen.mode, chosen.style)
    return chosen


def _open_window(qtbot, combo: Combo) -> Main_Window:
    """Build a window that RESTORES ``combo``; show it wide enough for the P2 strip."""
    save_appearance(replace(default_appearance(), style=combo.style, mode=combo.mode))
    window = Main_Window()
    qtbot.addWidget(window)
    assert (window.current_style(), window.current_mode()) == (combo.style, combo.mode)
    window.resize(*_WINDOW_SIZE)
    window.show()
    qtbot.waitExposed(window)
    window.apply_first_launch_layout()
    _settle()
    _unfocus(window)
    return window


def _transparent_tile(scale: int) -> QPixmap:
    tile = QPixmap(1, 1)
    tile.fill(Qt.GlobalColor.transparent)
    tile.setDevicePixelRatio(scale)
    return tile


def _render_pair(monkeypatch, widget: QWidget) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(as shipped, pattern off)`` renders of ``widget`` (same widget tree).

    Also asserts the determinism control: a second render of the shipped state is
    identical to the first, so any difference between the pair is the pattern.
    """
    shipped = _array(widget)
    again = _array(widget)
    assert np.array_equal(shipped, again), "the shipped render is not deterministic"
    with monkeypatch.context() as patch:
        patch.setattr(pixel_chrome, "_pattern_pixmap", _transparent_tile)
        off = _array(widget)
    assert shipped.shape == off.shape
    return shipped, off


def _pattern_mask(shipped: np.ndarray, off: np.ndarray) -> np.ndarray:
    """The boolean mask of pixels that exist only because the pattern is drawn."""
    return (shipped != off).any(axis=-1)


def _box(widget: QWidget, root: QWidget) -> QRect:
    return QRect(widget.mapTo(root, QPoint(0, 0)), widget.size())


def _text_boxes(root: QWidget) -> List[Tuple[str, QRect]]:
    """Rectangles (in ``root`` coordinates) of every visible, rendered text-bearing control."""
    boxes: List[Tuple[str, QRect]] = []
    for widget in root.findChildren(QWidget):
        if not isinstance(widget, _TEXT_TYPES) or isinstance(
            widget, pixel_chrome.Ornament_Widget
        ):
            continue
        if not widget.isVisibleTo(root) or widget.width() < 1 or widget.height() < 1:
            continue
        if isinstance(widget, (QLabel, QAbstractButton)) and not (
            widget.text() if hasattr(widget, "text") else ""
        ):
            continue
        rect = _box(widget, root)
        if not rect.intersects(root.rect()):
            continue  # a dock behind a tab sits off-screen: it is not rendered
        boxes.append((f"{type(widget).__name__} {widget.objectName()!r}", rect))
    return boxes


def _count_in(mask: np.ndarray, rect: QRect) -> int:
    clipped = rect.intersected(QRect(0, 0, mask.shape[1], mask.shape[0]))
    if clipped.isEmpty():
        return 0
    return int(
        mask[
            clipped.top() : clipped.bottom() + 1, clipped.left() : clipped.right() + 1
        ].sum()
    )


def _under_text(mask: np.ndarray, boxes: List[Tuple[str, QRect]]) -> List[str]:
    """One line per text box that holds at least one pattern pixel."""
    lines: List[str] = []
    for name, rect in boxes:
        covered = _count_in(mask, rect)
        if covered:
            lines.append(f"{name} {rect.getRect()} holds {covered} pattern pixel(s)")
    return lines


def _areas(window: Main_Window) -> List[Pattern_Area_Widget]:
    return window.findChildren(Pattern_Area_Widget)


def _outside(mask: np.ndarray, rects: List[QRect]) -> int:
    """Pattern pixels that lie outside every rectangle of ``rects``."""
    keep = np.zeros_like(mask)
    for rect in rects:
        clipped = rect.intersected(QRect(0, 0, mask.shape[1], mask.shape[0]))
        if not clipped.isEmpty():
            keep[
                clipped.top() : clipped.bottom() + 1,
                clipped.left() : clipped.right() + 1,
            ] = True
    return int((mask & ~keep).sum())


# --------------------------------------------------------------------------- #
# SC-VI-UI-011-1: no pattern pixel lies under text                             #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_011_1_no_pattern_pixel_lies_under_text_in_the_window_and_its_docks(
    qtbot, combo, monkeypatch
):
    """SC-VI-UI-011-1 (six-way): every text box of the window, docks included.

    The window is rendered with the pattern on and off (the seam); every visible
    text-bearing control's rectangle is searched for pattern pixels. The boxes examined and
    the pattern pixels present (in total and per area) are printed and must be non-zero --
    a window with no pattern would otherwise pass for "none under text".
    """
    window = _open_window(qtbot, combo)
    areas = _areas(window)
    assert len(areas) == 2, f"expected the two enumerated areas, found {len(areas)}"
    shipped, off = _render_pair(monkeypatch, window)
    mask = _pattern_mask(shipped, off)
    boxes = _text_boxes(window)
    offenders = _under_text(mask, boxes)
    per_area = {id(a): _count_in(mask, _box(a, window)) for a in areas}
    print(
        f"{combo.label()}: {len(boxes)} text boxes examined, {int(mask.sum())} pattern "
        f"pixels present (per area {sorted(per_area.values())}), "
        f"{len(offenders)} box(es) holding pattern pixels"
    )
    for line in offenders:
        print("   ", line)
    assert len(boxes) >= 30, f"only {len(boxes)} text boxes were examined"
    assert int(mask.sum()) > 0, "no pattern pixel is present -- nothing was tested"
    assert all(
        count > 0 for count in per_area.values()
    ), f"an area shows no pattern: {sorted(per_area.values())}"
    assert not offenders, offenders[:6]


def test_sc_vi_ui_011_1_a_dialog_holds_text_and_no_pattern(qtbot, combo, monkeypatch):
    """SC-VI-UI-011-1 (dialog): the About dialog is rendered with the pattern on and off.

    Its text boxes are examined and no pattern pixel is present anywhere in it (it holds no
    pattern area). The count of examined boxes is printed and must be non-zero.
    """
    dialog = About_Dialog(combo.mode)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    _settle()
    _unfocus(dialog)
    shipped, off = _render_pair(monkeypatch, dialog)
    mask = _pattern_mask(shipped, off)
    boxes = _text_boxes(dialog)
    print(
        f"{combo.label()}: About dialog {len(boxes)} text boxes, {int(mask.sum())} pattern pixels"
    )
    assert boxes, "the dialog has no text box to examine"
    assert not _under_text(mask, boxes)
    assert int(mask.sum()) == 0


def _host_with_labels(qtbot) -> Tuple[Pattern_Area_Widget, List[QLabel]]:
    """A pattern area that hosts two labels (transparent: the pattern would show through)."""
    area = Pattern_Area_Widget()
    area.resize(360, 160)
    first = QLabel("Pattern host one", area)
    first.move(30, 30)
    second = QLabel("Second label", area)
    second.move(190, 100)
    for label in (first, second):
        label.adjustSize()
    qtbot.addWidget(area)
    area.show()
    qtbot.waitExposed(area)
    _settle()
    return area, [first, second]


def _grown(widget: QWidget, area: QWidget, by: int) -> QRect:
    return _box(widget, area).adjusted(-by, -by, by, by)


def test_sc_vi_ui_011_1_the_clip_keeps_pattern_out_of_a_hosted_label_and_its_clearance(
    qtbot, combo, monkeypatch
):
    """SC-VI-UI-011-1 (mechanism, with its control): clip on -> none; clip disabled -> bleed.

    A pattern area hosts two labels. With the shipped clip the on/off diff shows NO pattern
    pixel inside either label's rectangle grown by ``PATTERN_CHILD_CLEARANCE_PX``, while the
    rest of the area does show pattern. With ``clip_region`` replaced by the whole rectangle
    (the planted defect) pattern pixels appear under the labels: the check is able to fail.
    """
    area, labels = _host_with_labels(qtbot)
    boxes = [
        (f"label {label.text()!r}", _grown(label, area, PATTERN_CHILD_CLEARANCE_PX))
        for label in labels
    ]
    shipped, off = _render_pair(monkeypatch, area)
    mask = _pattern_mask(shipped, off)
    clipped_under = [_count_in(mask, rect) for _n, rect in boxes]
    total = int(mask.sum())
    print(
        f"{combo.label()}: clip ON  -> {total} pattern px, under the labels "
        f"(+{PATTERN_CHILD_CLEARANCE_PX} px clearance) {clipped_under}"
    )
    assert total > 0 and clipped_under == [0, 0]

    with monkeypatch.context() as patch:
        patch.setattr(
            Pattern_Area_Widget, "clip_region", lambda self: QRegion(self.rect())
        )
        bled_shipped, bled_off = _render_pair(monkeypatch, area)
    bled = _pattern_mask(bled_shipped, bled_off)
    bleed_under = [_count_in(bled, rect) for _n, rect in boxes]
    print(
        f"{combo.label()}: clip OFF -> {int(bled.sum())} pattern px, under the labels {bleed_under}"
    )
    assert all(
        count > 0 for count in bleed_under
    ), f"the planted unclipped pattern did not bleed under the labels: {bleed_under}"
    assert int(bled.sum()) > total


# --------------------------------------------------------------------------- #
# SC-VI-UI-011-2: only on the two enumerated areas                             #
# --------------------------------------------------------------------------- #


def _two_areas(window: Main_Window) -> Tuple[Pattern_Area_Widget, Pattern_Area_Widget]:
    """Return ``(P1, P2)``: the area in the tool toolbar, the one in the Timeline dock."""
    areas = _areas(window)
    p1 = [a for a in areas if window._toolbar.isAncestorOf(a)]
    p2 = [a for a in areas if window._timeline_dock.isAncestorOf(a)]
    assert (
        len(p1) == 1 and len(p2) == 1 and len(areas) == 2
    ), f"found {len(areas)} pattern areas: {len(p1)} in the toolbar, {len(p2)} in the Timeline"
    return p1[0], p2[0]


def test_sc_vi_ui_011_2_the_pattern_appears_only_on_the_two_enumerated_areas(
    qtbot, combo, monkeypatch
):
    """SC-VI-UI-011-2 (six-way): every pattern pixel lies inside P1 or P2; each shows some.

    P1 is the tool toolbar's tail, below its last control; P2 is the Timeline dock's strip,
    to the right of the transport controls and on their row.
    """
    window = _open_window(qtbot, combo)
    p1, p2 = _two_areas(window)
    shipped, off = _render_pair(monkeypatch, window)
    mask = _pattern_mask(shipped, off)
    rects = [_box(p1, window), _box(p2, window)]
    in1, in2 = _count_in(mask, rects[0]), _count_in(mask, rects[1])
    stray = _outside(mask, rects)
    print(
        f"{combo.label()}: pattern pixels {int(mask.sum())}: P1 {in1}, P2 {in2}, "
        f"outside both {stray}"
    )
    assert in1 > 0 and in2 > 0, "an enumerated area shows no pattern"
    assert stray == 0, f"{stray} pattern pixel(s) outside the two enumerated areas"

    # geometry: P1 below the toolbar's last control; P2 right of the transport controls
    toolbar_boxes = [
        _box(w, window)
        for w in window._toolbar.findChildren(QWidget)
        if w.isVisibleTo(window)
        and not p1.isAncestorOf(w)
        and w is not p1
        and w.parentWidget() is window._toolbar
    ]
    assert toolbar_boxes, "the toolbar has no other control to compare P1 with"
    assert rects[0].top() >= max(
        b.bottom() for b in toolbar_boxes
    ), "P1 is not the toolbar's tail"
    controls = _box(window._playback_controls, window)
    assert (
        rects[1].left() >= controls.right()
    ), "P2 is not right of the transport controls"
    assert (
        rects[1].top() < controls.bottom() and rects[1].bottom() > controls.top()
    ), "P2 is not on the transport controls' row"


def test_sc_vi_ui_011_2_a_third_pattern_area_is_reported(qtbot, combo, monkeypatch):
    """Control: a pattern area planted in the Layers dock is a stray the check names."""
    window = _open_window(qtbot, combo)
    p1, p2 = _two_areas(window)
    panel = pixel_chrome.dock_content(window._layer_dock)
    assert panel is not None
    planted = Pattern_Area_Widget(panel)
    planted.setGeometry(4, 4, 80, 40)
    planted.show()
    planted.raise_()
    _settle()
    shipped, off = _render_pair(monkeypatch, window)
    mask = _pattern_mask(shipped, off)
    stray = _outside(mask, [_box(p1, window), _box(p2, window)])
    print(f"{combo.label()}: planted third area -> {stray} stray pattern pixel(s)")
    assert stray > 0, "a pattern area outside the two enumerated ones was not detected"


# --------------------------------------------------------------------------- #
# SC-VI-UI-011-3: the canvas workspace stays one flat colour                   #
# --------------------------------------------------------------------------- #


def _workspace_findings(
    window: Main_Window, combo: Combo
) -> Tuple[int, int, int, List[str]]:
    """Examine the rendered canvas: ``(workspace px, ring px, doc px, findings)``.

    Every viewport pixel outside the document and a 3 px ring around it must equal the
    ``canvas_workspace`` role; the ring may hold the ``canvas_border`` role as well.
    """
    record = window.active_tab()
    view, scene = record.view, record.scene
    view.set_zoom(4.0)
    _settle()
    image = _array(view.viewport())
    height, width = image.shape[:2]
    doc = view.mapFromScene(
        QRectF(0, 0, scene.sceneRect().width(), scene.sceneRect().height())
    ).boundingRect()
    ring = doc.adjusted(-3, -3, 3, 3)
    inside_ring = np.zeros((height, width), dtype=bool)
    clipped = ring.intersected(QRect(0, 0, width, height))
    inside_ring[
        clipped.top() : clipped.bottom() + 1, clipped.left() : clipped.right() + 1
    ] = True
    in_doc = np.zeros((height, width), dtype=bool)
    d = doc.intersected(QRect(0, 0, width, height))
    in_doc[d.top() : d.bottom() + 1, d.left() : d.right() + 1] = True
    workspace = np.array(_rgb(combo, "canvas_workspace"), dtype=np.uint8)
    border = np.array(_rgb(combo, "canvas_border"), dtype=np.uint8)
    outside = ~inside_ring
    findings: List[str] = []
    bad = outside & ~(image[..., :3] == workspace).all(axis=-1)
    if bad.any():
        ys, xs = np.nonzero(bad)
        colours = {
            tuple(int(v) for v in image[y, x, :3]) for y, x in zip(ys[:50], xs[:50])
        }
        findings.append(
            f"{int(bad.sum())} workspace pixel(s) are not the workspace role: {sorted(colours)[:4]}"
        )
    ring_only = inside_ring & ~in_doc
    ring_bad = ring_only & ~(
        (image[..., :3] == workspace).all(axis=-1)
        | (image[..., :3] == border).all(axis=-1)
    )
    if ring_bad.any():
        findings.append(
            f"{int(ring_bad.sum())} pixel(s) in the document's ring are neither workspace nor border"
        )
    return int(outside.sum()), int(ring_only.sum()), int(in_doc.sum()), findings


def test_sc_vi_ui_011_3_the_canvas_workspace_stays_one_flat_colour(qtbot, combo):
    """SC-VI-UI-011-3 (six-way): a document is open; its workspace is one role colour.

    The window opens in the default combination and is SWITCHED to ``combo`` at runtime
    (so the style threaded into the canvas roles is what is measured). Every viewport pixel
    outside the document and its 3 px ring equals ``canvas_workspace``; that colour is
    neither checker colour; and no pattern area lies on or over the canvas.
    """
    window = Main_Window()
    qtbot.addWidget(window)
    window.resize(*_WINDOW_SIZE)
    window.show()
    qtbot.waitExposed(window)
    window.apply_first_launch_layout()
    window.set_style(combo.style)
    window.set_mode(combo.mode)
    _settle()
    assert window.active_tab() is not None, "no document is open"
    workspace_px, ring_px, doc_px, findings = _workspace_findings(window, combo)
    print(
        f"{combo.label()}: {workspace_px} workspace px examined, {ring_px} ring px, "
        f"{doc_px} document px excluded, {len(findings)} finding(s)"
    )
    assert workspace_px > 1000 and doc_px > 0
    assert not findings, findings
    light, dark, _grid = canvas_roles(combo.mode, combo.style)
    workspace, _border = canvas_surface_roles(combo.mode, combo.style)
    assert workspace.name() != light.name() and workspace.name() != dark.name(), (
        f"the workspace colour {workspace.name()} equals a checker colour "
        f"({light.name()}, {dark.name()})"
    )
    canvas = window.active_tab().view
    for area in _areas(window):
        assert not canvas.isAncestorOf(area) and not area.isAncestorOf(canvas)
        assert not _box(area, window).intersects(_box(canvas.viewport(), window))


def test_sc_vi_ui_011_3_a_pattern_planted_over_the_workspace_is_reported(qtbot, combo):
    """Control: a pattern area over the viewport makes the flatness check report a finding."""
    window = Main_Window()
    qtbot.addWidget(window)
    window.resize(*_WINDOW_SIZE)
    window.show()
    qtbot.waitExposed(window)
    window.apply_first_launch_layout()
    window.set_style(combo.style)
    window.set_mode(combo.mode)
    _settle()
    assert (
        _workspace_findings(window, combo)[3] == []
    ), "the control starts from a clean canvas"
    view = window.active_tab().view
    planted = Pattern_Area_Widget(view.viewport())
    planted.setGeometry(0, 0, 150, 120)
    planted.show()
    planted.raise_()
    _settle()
    findings = _workspace_findings(window, combo)[3]
    print(f"{combo.label()}: planted pattern over the workspace -> {findings}")
    assert findings, "a pattern over the canvas workspace was not reported"
