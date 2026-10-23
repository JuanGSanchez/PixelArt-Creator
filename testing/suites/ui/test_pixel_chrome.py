"""Dock frames and corner ornaments at the Main_Window's own dock sites.

Covers **SC-VI-UI-007-1 / -2** (title plate, body frame, floating keeps the OS chrome) and
**SC-VI-UI-010-1 / -2 / -3** (ornaments sit on their corners and stay, nothing lies under
one, gold in Light and red in Dark) -- for every one of the six style x mode combinations.
``test_theme.py`` proves the frame MECHANISM on a plain ``QMainWindow``; its header leaves
"wiring at the Main_Window's own dock sites" to this module.

How an ornament is judged. The ornament is a nearest-neighbour sprite drawn inside the
dock body's frame rings at each bottom corner. Its position is NOT read back from the
product (``Ornament_Widget.geometry()`` would only test the product against itself): the
dock is rendered, the sprite (the style's ``ornament`` template, coloured from the
combination's role map, mirrored for the right and bottom corners) is **located by pixels**,
and the found position must equal the one the DATA gives -- the ``dock_body`` template's
ring widths. A locator that finds nothing is a failure, never a pass.

How "nothing lies under an ornament" is judged. The ornament's own opaque cells (not its
10 x 10 box -- its transparent cells hide nothing) are intersected with the rectangle of
every visible control of the dock (buttons, labels, fields, sliders, item views, tab bars,
graphics views, scroll bars). The denominators -- docks, controls, ornaments -- are printed
and must not be zero. A control rectangle is a deliberate SUPERSET of its text bounding box,
so a text box can never overlap an ornament without its control doing so.

Controls (a check that cannot fail proves nothing):

* the corner locator finds nothing on a framed dock that has no ornaments;
* the clear-zone check flags a control planted in a dock corner and passes the same dock
  once its content is inset past the ornament;
* the "stays on its corner" check flags an ornament the application filter no longer places
  after a resize;
* the wiring check flags a dock whose creation site forgot ``install_dock_frame``.

Scope notes, stated and not hidden:

* **Dialogs.** ``install_ornaments(..., dialog=True)`` is exercised on a plain ``QDialog``
  (the mechanism). No product dialog carries ornaments in the current scope, so the dialog half
  of SC-VI-UI-010-1/-2 for product dialogs is "could not verify -- not wired yet" and is
  left to the dialog slice's tests, not presumed.
* **Floating.** The offscreen platform draws no native window frame, so "shows the operating
  system's chrome" is not visible in pixels; ``test_theme.py`` states the same limit. What is
  asserted is what the product controls (no frameless flag, no Qt-drawn plate, plate returns).
* Everything runs on the offscreen platform at device-pixel ratio 1.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, NamedTuple, Optional, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFrame,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.ui import pixel_chrome
from pixelart_creator.ui.appearance_settings import (
    default_appearance,
    save_appearance,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.pixel_chrome import (
    DIALOG_CORNERS,
    DOCK_BODY_OBJECT_NAME,
    DOCK_CORNERS,
    Ornament_Widget,
    dock_content,
    install_dock_frame,
    install_ornaments,
)
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    available_styles,
    role_map,
)
from testing.suites.ui.conftest import assert_settings_isolated
from testing.suites.ui.test_main_window_appearance import _hue_family
from testing.suites.ui.test_theme import (
    _COMBO_IDS,
    COMBOS,
    Combo,
    QFontMetricsFor,
    _array,
    _plate_height,
    _rgb,
    _settle,
    _template,
    _unfocus,
    colour_mask_array,
    frame_share,
    locate,
    sprite,
    sprite_over,
)

# --------------------------------------------------------------------------- #
# Fixtures and helpers                                                         #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(request: pytest.FixtureRequest, qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture (this module is six-way).

    A test that asks for ``combo`` has its combination applied by that fixture
    before the body runs, so the canonical one is applied only for the others.
    """
    if "combo" not in request.fixturenames:
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


def _open_window(
    qtbot, combo: Combo, size: Tuple[int, int] = (1400, 900)
) -> Main_Window:
    """Build a ``Main_Window`` that RESTORES ``combo``, show it and lay out its docks."""
    save_appearance(replace(default_appearance(), style=combo.style, mode=combo.mode))
    window = Main_Window()
    qtbot.addWidget(window)
    assert (window.current_style(), window.current_mode()) == (combo.style, combo.mode)
    window.resize(*size)
    window.show()
    qtbot.waitExposed(window)
    window.apply_first_launch_layout()
    _settle()
    return window


def _shown_docks(window: QMainWindow) -> Tuple[List[QDockWidget], int]:
    """Raise every dock in turn; return the ones that then show something, and the total."""
    docks = window.findChildren(QDockWidget)
    shown: List[QDockWidget] = []
    for dock in docks:
        if dock.isFloating() or not dock.isVisible():
            continue
        dock.raise_()
        _settle()
        if not dock.visibleRegion().isEmpty():
            shown.append(dock)
    return shown, len(docks)


def _ornament_pattern(combo: Combo, corner: str) -> np.ndarray:
    """The ornament sprite coloured for ``combo``, mirrored for ``corner`` (RGBA)."""
    pattern = sprite(combo, "ornament")
    if corner in (pixel_chrome.CORNER_TOP_RIGHT, pixel_chrome.CORNER_BOTTOM_RIGHT):
        pattern = pattern[:, ::-1]
    if corner in (pixel_chrome.CORNER_BOTTOM_LEFT, pixel_chrome.CORNER_BOTTOM_RIGHT):
        pattern = pattern[::-1, :]
    return np.ascontiguousarray(pattern)


def _expected_origin(
    combo: Combo, corner: str, width: int, height: int, frame: str
) -> Tuple[int, int]:
    """Where the DATA puts the ornament: inside the ``frame`` template's rings."""
    slices = _template(combo, frame).slices
    pattern = _ornament_pattern(combo, corner)
    ph, pw = pattern.shape[:2]
    left = corner in (pixel_chrome.CORNER_TOP_LEFT, pixel_chrome.CORNER_BOTTOM_LEFT)
    top = corner in (pixel_chrome.CORNER_TOP_LEFT, pixel_chrome.CORNER_TOP_RIGHT)
    x = slices.left if left else width - slices.right - pw
    y = slices.top if top else height - slices.bottom - ph
    return x, y


def _find_corner(
    image: np.ndarray, combo: Combo, corner: str, frame: str
) -> Tuple[Optional[Tuple[int, int]], Tuple[int, int]]:
    """Locate the sprite of ``corner`` in ``image``; return ``(found_at, expected_at)``.

    ``found_at`` is the match nearest the expected origin, or ``None`` if the sprite is
    nowhere in the image.
    """
    height, width = image.shape[:2]
    expected = _expected_origin(combo, corner, width, height, frame)
    hits = locate(image, _ornament_pattern(combo, corner))
    if not hits:
        return None, expected
    nearest = min(hits, key=lambda p: abs(p[0] - expected[0]) + abs(p[1] - expected[1]))
    return nearest, expected


def _corner_findings(
    image: np.ndarray, combo: Combo, corners: Tuple[str, ...], frame: str
) -> List[str]:
    """One finding per corner whose sprite is missing or is not at its expected origin."""
    findings: List[str] = []
    for corner in corners:
        found, expected = _find_corner(image, combo, corner, frame)
        if found is None:
            findings.append(f"{corner}: sprite not drawn anywhere")
        elif found != expected:
            findings.append(f"{corner}: drawn at {found}, expected {expected}")
    return findings


_CONTROL_TYPES = (
    QAbstractButton,
    QLabel,
    QLineEdit,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QAbstractItemView,
    QTabBar,
    QGraphicsView,
    QTextEdit,
    QPlainTextEdit,
)


class ClearZone(NamedTuple):
    """What one dock's clear-zone measurement found."""

    ornaments: int
    controls: int
    offenders: List[str]


def _ink_mask(
    image_shape: Tuple[int, int],
    combo: Combo,
    corners: Tuple[str, ...],
    frame: str,
    image: np.ndarray,
) -> Tuple[np.ndarray, int]:
    """The boolean mask of every opaque ornament cell of the located sprites."""
    mask = np.zeros(image_shape, dtype=bool)
    located = 0
    for corner in corners:
        found, _expected = _find_corner(image, combo, corner, frame)
        if found is None:
            continue
        located += 1
        pattern = _ornament_pattern(combo, corner)
        ph, pw = pattern.shape[:2]
        x, y = found
        mask[y : y + ph, x : x + pw] |= pattern[..., 3] == 255
    return mask, located


def _examined_rect(control: QWidget) -> QRect:
    """The rectangle (in the control's coordinates) that must stay clear of an ornament.

    A control's own rectangle -- except a text label, whose widget can be taller or wider
    than its text: for it the TEXT bounding box is examined (the spec says "no text").
    """
    if isinstance(control, QLabel) and control.text() and control.pixmap().isNull():
        flags = int(control.alignment())
        if control.wordWrap():
            flags |= int(Qt.TextFlag.TextWordWrap)
        box = control.fontMetrics().boundingRect(
            control.contentsRect(), flags, control.text()
        )
        return box.intersected(control.rect())
    return QRect(QPoint(0, 0), control.size())


def clear_zone(dock: QDockWidget, combo: Combo) -> ClearZone:
    """Measure which controls of ``dock`` lie under an opaque ornament cell.

    The ornaments are located by pixels in the rendered dock, then each visible control's
    rectangle (in dock coordinates) is intersected with the ornaments' opaque cells.
    """
    image = _array(dock)
    height, width = image.shape[:2]
    mask, located = _ink_mask((height, width), combo, DOCK_CORNERS, "dock_body", image)
    offenders: List[str] = []
    controls = 0
    for control in dock.findChildren(QWidget):
        if not isinstance(control, _CONTROL_TYPES) or isinstance(
            control, Ornament_Widget
        ):
            continue
        if not control.isVisibleTo(dock) or control.width() < 1 or control.height() < 1:
            continue
        controls += 1
        origin = control.mapTo(dock, QPoint(0, 0))
        rect = _examined_rect(control).translated(origin)
        rect = rect.intersected(QRect(0, 0, width, height))
        if rect.isEmpty():
            continue
        covered = int(
            mask[rect.top() : rect.bottom() + 1, rect.left() : rect.right() + 1].sum()
        )
        if covered:
            offenders.append(
                f"{dock.windowTitle()!r}: {type(control).__name__} "
                f"{control.objectName()!r} {rect.getRect()} lies under {covered} ornament cell(s)"
            )
    return ClearZone(located, controls, offenders)


def _wiring_findings(window: QMainWindow) -> Tuple[int, List[str]]:
    """Return ``(docks examined, findings)`` for the frame and ornament wiring."""
    findings: List[str] = []
    docks = window.findChildren(QDockWidget)
    for dock in docks:
        body = dock.widget()
        name = dock.windowTitle() or dock.objectName()
        if body is None or body.objectName() != DOCK_BODY_OBJECT_NAME:
            findings.append(f"{name!r}: not framed (widget() is {type(body).__name__})")
            continue
        content = dock_content(dock)
        if content is None or content is body:
            findings.append(f"{name!r}: the DockBody holds no panel")
        corners = sorted(
            o.corner()
            for o in dock.findChildren(
                Ornament_Widget, options=Qt.FindChildOption.FindDirectChildrenOnly
            )
        )
        if corners != sorted(DOCK_CORNERS):
            findings.append(
                f"{name!r}: ornaments at {corners}, not {sorted(DOCK_CORNERS)}"
            )
    return len(docks), findings


# --------------------------------------------------------------------------- #
# Wiring: every creation site frames and ornaments its dock                    #
# --------------------------------------------------------------------------- #


def test_every_dock_of_the_main_window_is_framed_and_carries_two_bottom_ornaments(
    qtbot, combo
):
    """REQ-VI-UI-007 / -010 wiring: each dock is a ``DockBody`` with two bottom ornaments.

    The census covers EVERY ``QDockWidget`` of a shown window (the workflow docks included),
    so a creation site that forgot ``install_dock_frame`` / ``install_ornaments`` is named.
    """
    window = _open_window(qtbot, combo)
    examined, findings = _wiring_findings(window)
    print(f"{combo.label()}: {examined} docks examined, {len(findings)} finding(s)")
    assert examined >= 30, f"only {examined} docks found -- the census saw too little"
    assert not findings, findings
    for name in ("_palette_dock", "_symmetry_dock", "_layer_dock", "_timeline_dock"):
        assert dock_content(getattr(window, name)) is not None


def test_the_wiring_check_names_a_dock_whose_creation_site_forgot_the_frame(
    qtbot, combo
):
    """Control: a dock added with ``setWidget`` alone is reported by name (never silent)."""
    window = _open_window(qtbot, combo)
    forgetful = QDockWidget("Forgetful", window)
    forgetful.setWidget(QLabel("no frame"))
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, forgetful)
    plain = QDockWidget("Frame only", window)
    plain.setWidget(QLabel("frame, no ornaments"))
    install_dock_frame(plain)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, plain)
    _examined, findings = _wiring_findings(window)
    assert any("'Forgetful'" in f and "not framed" in f for f in findings), findings
    assert any(
        "'Frame only'" in f and "ornaments at []" in f for f in findings
    ), findings


# --------------------------------------------------------------------------- #
# SC-VI-UI-007-1 / -2                                                          #
# --------------------------------------------------------------------------- #


def _assert_plate_and_frame(dock: QDockWidget, combo: Combo) -> None:
    """The plate holds the whole title; the body is framed (found by pixels)."""
    _unfocus(dock)
    image = _array(dock)
    plate_h = _plate_height(image, combo, dock)
    s = _template(combo, "dock_title").slices
    interior = (s.left, s.top, image.shape[1] - s.right, plate_h - s.bottom)
    glyphs = locate(
        image[:plate_h], sprite_over(combo, "glyph_close", "title_fill")
    ) + locate(image[:plate_h], sprite_over(combo, "glyph_float", "title_fill"))
    assert (
        len(glyphs) == 2
    ), f"{dock.windowTitle()!r}: {len(glyphs)} title glyph(s), not 2"
    left_of_buttons = min(x for x, _ in glyphs)
    ink = colour_mask_array(image[:plate_h], _rgb(combo, "title_text"))
    region = np.zeros_like(ink)
    region[interior[1] : interior[3], interior[0] : left_of_buttons] = True
    inside = ink & region
    assert inside.sum() > 0, f"{dock.windowTitle()!r}: no title ink inside the plate"
    ys, xs = np.nonzero(inside)
    advance = QFontMetricsFor(dock).horizontalAdvance(dock.windowTitle())
    available = left_of_buttons - interior[0]
    assert advance <= available, (
        f"{dock.windowTitle()!r}: the title ({advance} px) does not fit the plate "
        f"({available} px)"
    )
    assert xs.min() >= interior[0] and xs.max() < left_of_buttons
    assert ys.min() >= interior[1] and ys.max() < interior[3]
    share, examined = frame_share(dock.widget(), combo, "dock_body")
    assert (
        examined > 0 and share == 1.0
    ), f"{dock.windowTitle()!r}: the body frame agrees with dock_body on {share:.4f}"


@pytest.mark.parametrize(
    "dock_name", ["_palette_dock", "_layer_dock", "_timeline_dock"]
)
def test_sc_vi_ui_007_1_docked_docks_show_a_title_plate_and_a_body_frame(
    qtbot, combo, dock_name
):
    """SC-VI-UI-007-1: the Palette, Layers and Timeline docks, docked, in all six combinations.

    Each shows a title plate containing its whole title and a frame around its body, both
    compared with the style's templates cell by cell. (``_plate_height`` confirms the plate
    from the template's own pixels; the helpers are ``test_theme.py``'s.)
    """
    window = _open_window(qtbot, combo)
    dock = getattr(window, dock_name)
    dock.raise_()
    _settle()
    assert dock.isVisible() and not dock.isFloating()
    assert not dock.visibleRegion().isEmpty(), f"{dock_name} is hidden behind a tab"
    _assert_plate_and_frame(dock, combo)


def test_sc_vi_ui_007_2_a_floating_dock_keeps_native_chrome_and_the_plate_returns(
    qtbot, combo
):
    """SC-VI-UI-007-2 (partial, the HEADLESS limit stated in the module note).

    Floating the Layers dock: not frameless, not translucent, no Qt-drawn plate (a band of
    the style's title-fill colour is gone), no reserved title area; docking it again
    brings the plate, the frame AND both ornaments back, found by pixels.
    """
    window = _open_window(qtbot, combo)
    dock = window._layer_dock
    _unfocus(window)
    docked = _array(dock)
    plate_h = _plate_height(docked, combo, dock)
    fill = _rgb(combo, "title_fill")
    docked_fill = int(colour_mask_array(docked[:plate_h], fill).sum())
    assert docked_fill > 0, "the docked plate shows no title fill to compare with"

    dock.setFloating(True)
    _settle()
    assert dock.isFloating()
    assert not dock.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert not dock.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dock.widget().geometry().top() == 0, "a floating dock reserves a title area"
    floating = _array(dock)
    floating_fill = int(colour_mask_array(floating[:plate_h], fill).sum())
    print(
        f"{combo.label()}: title-fill px docked {docked_fill}, floating {floating_fill}"
    )
    assert (
        floating_fill < 0.2 * docked_fill
    ), "a Qt-drawn title plate shows when floating"

    dock.setFloating(False)
    _settle()
    assert not dock.isFloating()
    again = _array(dock)
    assert _plate_height(again, combo, dock) > 0, "the title plate did not return"
    share, examined = frame_share(dock.widget(), combo, "dock_body")
    assert examined > 0 and share == 1.0
    assert _corner_findings(again, combo, DOCK_CORNERS, "dock_body") == []


# --------------------------------------------------------------------------- #
# SC-VI-UI-010-1: ornaments sit on their corners and stay there                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "dock_name", ["_palette_dock", "_layer_dock", "_timeline_dock"]
)
def test_sc_vi_ui_010_1_docked_ornaments_sit_on_their_corners_and_stay_there(
    qtbot, combo, dock_name
):
    """SC-VI-UI-010-1 (docks): a sprite at each bottom corner, before and after each change.

    The changes are a window resize (smaller, then larger than the start) and an
    undock-then-redock; after each one both sprites are located again and must sit at the
    origin the ``dock_body`` rings give.
    """
    window = _open_window(qtbot, combo)
    dock = getattr(window, dock_name)

    def check(stage: str) -> None:
        dock.raise_()
        _settle()
        assert dock.isVisible() and not dock.isFloating(), stage
        assert not dock.visibleRegion().isEmpty(), f"{stage}: hidden behind a tab"
        findings = _corner_findings(_array(dock), combo, DOCK_CORNERS, "dock_body")
        print(
            f"{combo.label()} {dock_name} {stage}: {dock.width()}x{dock.height()} -> {findings or 'ok'}"
        )
        assert not findings, f"{stage}: {findings}"

    check("as opened")
    window.resize(1100, 760)
    _settle()
    check("window resized smaller")
    window.resize(1500, 950)
    _settle()
    check("window resized larger")
    dock.setFloating(True)
    _settle()
    dock.setFloating(False)
    _settle()
    check("undocked and redocked")


def test_sc_vi_ui_010_1_the_corner_locator_finds_nothing_without_ornaments(
    qtbot, combo
):
    """Control: a framed dock with no ornaments yields a finding for each bottom corner."""
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    dock = QDockWidget("Bare", window)
    dock.setWidget(QLabel("content"))
    install_dock_frame(dock)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    window.resize(520, 320)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    _settle()
    findings = _corner_findings(_array(dock), combo, DOCK_CORNERS, "dock_body")
    assert len(findings) == 2 and all(
        "not drawn anywhere" in f for f in findings
    ), findings
    install_ornaments(dock, DOCK_CORNERS)
    _settle()
    assert _corner_findings(_array(dock), combo, DOCK_CORNERS, "dock_body") == []


def test_sc_vi_ui_010_1_a_stale_ornament_is_reported_after_a_resize(qtbot, combo):
    """Control: when the filter no longer places an ornament, a resize leaves it behind.

    The planted state clears the dock's ornament-host property (what the application filter
    keys on); after the resize the corner check must name the stale corners, which proves the
    "still on its corner after each change" assertion is able to fail.
    """
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    dock = QDockWidget("Planted", window)
    dock.setWidget(QLabel("content"))
    install_dock_frame(dock)
    install_ornaments(dock, DOCK_CORNERS)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    window.resize(520, 320)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    _settle()
    assert _corner_findings(_array(dock), combo, DOCK_CORNERS, "dock_body") == []
    dock.setProperty(pixel_chrome._ORNAMENT_HOST_PROPERTY, False)
    window.resize(720, 460)
    _settle()
    findings = _corner_findings(_array(dock), combo, DOCK_CORNERS, "dock_body")
    print(f"{combo.label()}: planted stale ornaments -> {findings}")
    assert findings, "a stale ornament was not reported"


def test_sc_vi_ui_010_1_a_dialog_carries_an_ornament_on_each_of_its_four_corners(
    qtbot, combo
):
    """SC-VI-UI-010-1 (dialog MECHANISM; no product dialog is wired yet).

    A plain ``QDialog`` given ``install_ornaments(..., DIALOG_CORNERS, dialog=True)``
    shows a sprite at each of its four corners inside the ``dialog`` frame's rings, at the
    size it opens at and after it is resized. Product dialogs: could not verify -- not
    wired in this slice.
    """
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.addWidget(QLabel("A dialog"))
    install_ornaments(dialog, DIALOG_CORNERS, dialog=True)
    dialog.resize(320, 200)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    _settle()
    _unfocus(dialog)
    assert _corner_findings(_array(dialog), combo, DIALOG_CORNERS, "dialog") == []
    dialog.resize(460, 300)
    _settle()
    findings = _corner_findings(_array(dialog), combo, DIALOG_CORNERS, "dialog")
    print(f"{combo.label()}: dialog after resize -> {findings or 'ok'}")
    assert not findings


# --------------------------------------------------------------------------- #
# SC-VI-UI-010-2: no text or control lies under an ornament                    #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_010_2_no_control_lies_under_an_ornament_of_a_docked_dock(
    qtbot, combo
):
    """SC-VI-UI-010-2: every docked dock of the window, in each combination.

    Every dock is raised in turn; its two ornaments are located by pixels and each visible
    control's rectangle is intersected with their opaque cells. The denominators are
    printed. Product dialogs: could not verify -- they carry no ornament yet (see the
    module note).
    """
    window = _open_window(qtbot, combo)
    shown, total = _shown_docks(window)
    results = [(dock, clear_zone(dock, combo)) for dock in shown]
    ornaments = sum(r.ornaments for _d, r in results)
    controls = sum(r.controls for _d, r in results)
    offenders = [line for _d, r in results for line in r.offenders]
    print(
        f"{combo.label()}: {len(shown)} of {total} docks shown and examined, "
        f"{ornaments} ornaments located, {controls} controls examined, "
        f"{len(offenders)} control(s) under an ornament"
    )
    for line in offenders:
        print("   ", line)
    assert len(shown) >= 20, f"only {len(shown)} docks were examined"
    assert ornaments == 2 * len(
        shown
    ), f"{ornaments} ornaments located on {len(shown)} docks (expected two each)"
    assert controls > 0
    assert (
        not offenders
    ), f"{len(offenders)} control(s) lie under an ornament: " + "; ".join(offenders[:6])


def _planted_dock(qtbot, margin: int) -> Tuple[QMainWindow, QDockWidget]:
    """A framed, ornamented dock whose only content is a list view (it fills the dock) inset by ``margin``.

    The window is returned too: it owns the dock and must outlive the measurement.
    """
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    dock = QDockWidget("Planted", window)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.addWidget(QListWidget())
    dock.setWidget(panel)
    install_dock_frame(dock)
    install_ornaments(dock, DOCK_CORNERS)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    window.resize(420, 300)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    _settle()
    return window, dock


def test_sc_vi_ui_010_2_the_clear_zone_check_flags_a_planted_control_and_passes_a_clear_one(
    qtbot, combo
):
    """Control: a control in the corner is reported; the same dock inset past it is not."""
    crowded_window, crowded_dock = _planted_dock(qtbot, 0)
    crowded = clear_zone(crowded_dock, combo)
    print(f"{combo.label()}: planted corner control -> {crowded.offenders}")
    assert crowded.ornaments == 2 and crowded.controls >= 1
    assert crowded.offenders, "a control planted under the ornaments was not reported"
    clear_window, clear_dock = _planted_dock(qtbot, 14)
    clear = clear_zone(clear_dock, combo)
    assert clear.ornaments == 2 and clear.controls >= 1
    assert clear.offenders == [], clear.offenders


# --------------------------------------------------------------------------- #
# SC-VI-UI-010-3: gold in Light, red in Dark                                   #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_010_3_ornaments_are_gold_in_light_and_red_in_dark(qtbot, combo):
    """SC-VI-UI-010-3: the RENDERED ornament fill, on a real dock, is the role colour.

    The ornament's fill cell (``O`` in the template) is read from the rendered Layers dock
    at the located sprite's position: it must equal the ``ornament`` role of the combination
    (and the ``ornament_outline`` cell the outline role), and that colour is gold in Light
    and red in Dark by hue. The other mode's fill colour must not be what is drawn.
    """
    window = _open_window(qtbot, combo)
    dock = window._layer_dock
    dock.raise_()
    _settle()
    image = _array(dock)
    expected_hue = "gold" if combo.mode == THEME_LIGHT else "red"
    roles = role_map(combo.mode, combo.style)
    other_mode = "dark" if combo.mode == THEME_LIGHT else "light"
    foreign = role_map(other_mode, combo.style)["ornament"]
    template = _template(combo, "ornament")
    for corner in DOCK_CORNERS:
        found, expected = _find_corner(image, combo, corner, "dock_body")
        assert found == expected, f"{corner}: {found} != {expected}"
        pattern_rows = list(template.grid.rows)
        if corner in (
            pixel_chrome.CORNER_BOTTOM_LEFT,
            pixel_chrome.CORNER_BOTTOM_RIGHT,
        ):
            pattern_rows = pattern_rows[::-1]
        if corner in (pixel_chrome.CORNER_TOP_RIGHT, pixel_chrome.CORNER_BOTTOM_RIGHT):
            pattern_rows = [row[::-1] for row in pattern_rows]
        fills = [
            (x, y)
            for y, row in enumerate(pattern_rows)
            for x, ch in enumerate(row)
            if ch == "O"
        ]
        assert fills, "the ornament template has no fill cell"
        drawn = {
            tuple(int(v) for v in image[found[1] + y, found[0] + x, :3])
            for x, y in fills
        }
        want = _rgb(combo, "ornament")
        print(
            f"{combo.label()} {corner}: {len(fills)} fill cells drawn as {sorted(drawn)}, "
            f"role {roles['ornament']} ({_hue_family(roles['ornament'])})"
        )
        assert drawn == {
            want
        }, f"the drawn fill {drawn} is not the ornament role {want}"
    assert _hue_family(roles["ornament"]) == expected_hue
    assert _hue_family(foreign) != expected_hue, "the other mode is the same hue family"


# --------------------------------------------------------------------------- #
# Follow-up: the reserved ornament band                                         #
#                                                                              #
# ``reserve_ornament_band(dock)`` reserves the ornament sprite's height of the  #
# ACTIVE style as the bottom content margin of the dock's ``DockBody`` layout,  #
# and ``set_active_theme`` re-applies it on a style switch. The sprite is 10    #
# cells high in Washi & Kintsugi, 11 in Edo Night and 9 in Arcade Kikko, so a   #
# band that is not re-applied after a switch is wrong in every other style.     #
#                                                                              #
# The expected height is read from the style DATA (the ``ornament`` template's   #
# grid), never from the product's own margin. Every dock of the window is        #
# examined (shown or hidden: a hidden dock is shown later); the denominators are #
# printed and must not be zero.                                                  #
# --------------------------------------------------------------------------- #


def _ornament_height(style: str) -> int:
    """The height, in cells, of ``style``'s ornament sprite (the band the DATA asks for)."""
    return _template(Combo(style, THEME_LIGHT), "ornament").grid.height


def _body_margins(dock: QDockWidget) -> Optional[Tuple[int, int, int, int]]:
    """``(left, top, right, bottom)`` content margins of the dock's body layout, or ``None``."""
    body = dock.widget()
    if not isinstance(body, QFrame) or body.objectName() != DOCK_BODY_OBJECT_NAME:
        return None
    layout = body.layout()
    if layout is None:
        return None
    m = layout.contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


def _band_findings(window: QMainWindow, style: str) -> Tuple[int, List[str]]:
    """Return ``(docks examined, findings)`` for the band of every dock against ``style``."""
    want = (0, 0, 0, _ornament_height(style))
    findings: List[str] = []
    docks = window.findChildren(QDockWidget)
    for dock in docks:
        got = _body_margins(dock)
        if got != want:
            findings.append(
                f"{dock.windowTitle() or dock.objectName()!r}: margins {got}, expected {want}"
            )
    return len(docks), findings


def test_the_ornament_heights_differ_by_style_so_a_stale_band_is_detectable():
    """Precondition of the follow-up tests: the three styles ask for three different bands."""
    heights = {s: _ornament_height(s) for s in available_styles()}
    print(f"ornament sprite heights by style: {heights}")
    assert len(heights) == 3
    assert len(set(heights.values())) == len(heights), heights
    assert all(h > 0 for h in heights.values())


def test_reserve_ornament_band_sets_the_bottom_margin_to_the_sprite_height_on_every_dock(
    qtbot, combo
):
    """Every dock of the window restoring ``combo`` carries a band of its style's height."""
    window = _open_window(qtbot, combo)
    examined, findings = _band_findings(window, combo.style)
    print(
        f"{combo.label()}: {examined} docks examined, band {_ornament_height(combo.style)} px, "
        f"{len(findings)} wrong"
    )
    for line in findings:
        print("   ", line)
    assert examined >= 20, f"only {examined} docks were examined"
    assert not findings, "; ".join(findings[:6])


def test_reserving_the_band_keeps_a_crowded_dock_clear_of_its_ornaments(qtbot, combo):
    """A crowded dock fails the clear zone; the same dock after ``reserve_ornament_band`` passes.

    ``_planted_dock(qtbot, 0)`` is the dock whose list view fills it corner to corner (the
    control of SC-VI-UI-010-2). Without the band it has offenders; with it, none.
    """
    _window, dock = _planted_dock(qtbot, 0)
    before = clear_zone(dock, combo)
    assert (
        before.ornaments == 2 and before.offenders
    ), "the crowded dock was not crowded"
    assert _body_margins(dock) == (0, 0, 0, 0)

    pixel_chrome.reserve_ornament_band(dock)
    _settle()

    assert _body_margins(dock) == (0, 0, 0, _ornament_height(combo.style))
    after = clear_zone(dock, combo)
    print(
        f"{combo.label()}: crowded dock {len(before.offenders)} offender(s) -> "
        f"{len(after.offenders)} after the band"
    )
    assert after.ornaments == 2 and after.controls >= 1
    assert after.offenders == [], after.offenders


def test_reserve_ornament_band_is_idempotent_and_ignores_an_unframed_dock(qtbot, combo):
    """Twice gives the same band; a dock without the ``DockBody`` frame is left alone."""
    window, dock = _planted_dock(qtbot, 0)
    pixel_chrome.reserve_ornament_band(dock)
    once = _body_margins(dock)
    pixel_chrome.reserve_ornament_band(dock)
    assert _body_margins(dock) == once == (0, 0, 0, _ornament_height(combo.style))

    bare = QDockWidget("Bare", window)
    content = QWidget()
    QVBoxLayout(content).setContentsMargins(3, 4, 5, 6)
    bare.setWidget(content)
    pixel_chrome.reserve_ornament_band(bare)
    assert bare.widget() is content
    layout = content.layout()
    assert layout is not None
    m = layout.contentsMargins()
    assert (m.left(), m.top(), m.right(), m.bottom()) == (3, 4, 5, 6)


@pytest.mark.parametrize("start", COMBOS, ids=_COMBO_IDS)
def test_the_band_and_the_clear_zone_follow_a_runtime_switch(qtbot, start):
    """After a live style switch the band is the new style's, and the clear zone still holds.

    The window restores ``start``; the style is switched to the next one (the sprite
    height changes: 10 -> 11 -> 9 -> 10). Every dock's band must then equal the NEW
    style's height, and the SC-VI-UI-010-2 clear-zone measurement of every shown dock
    must still find two located ornaments per dock and no control under one. The mode is
    then flipped: the band (the same style) must not move. The clear zone is measured
    after the style switch only, because the sprite size is what the switch changes
    (it costs about five seconds a measurement).
    """
    apply_theme(QApplication.instance(), start.mode, start.style)
    window = _open_window(qtbot, start)
    styles = list(available_styles())
    nxt = styles[(styles.index(start.style) + 1) % len(styles)]
    flipped = THEME_DARK if start.mode == THEME_LIGHT else THEME_LIGHT
    old_h, new_h = _ornament_height(start.style), _ornament_height(nxt)
    assert old_h != new_h

    target = Combo(nxt, start.mode)
    window._switch_appearance(target.style, target.mode)
    _settle()
    examined, findings = _band_findings(window, target.style)
    shown, total = _shown_docks(window)
    results = [(dock, clear_zone(dock, target)) for dock in shown]
    ornaments = sum(r.ornaments for _d, r in results)
    controls = sum(r.controls for _d, r in results)
    offenders = [line for _d, r in results for line in r.offenders]
    print(
        f"{start.label()} -> {target.label()}: band {old_h} -> {new_h} px on {examined} "
        f"docks ({len(findings)} wrong); {len(shown)} of {total} docks examined, "
        f"{ornaments} ornaments located, {controls} controls, "
        f"{len(offenders)} under an ornament"
    )
    assert examined >= 20, f"only {examined} docks were examined"
    assert not findings, "after the style switch: " + "; ".join(findings[:6])
    assert len(shown) >= 20, f"only {len(shown)} docks were examined"
    assert ornaments == 2 * len(
        shown
    ), f"{ornaments} ornaments located on {len(shown)} docks (expected two each)"
    assert controls > 0
    assert not offenders, "after the style switch: " + "; ".join(offenders[:6])

    window._switch_appearance(nxt, flipped)
    _settle()
    examined, findings = _band_findings(window, nxt)
    print(f"{target.label()} -> {nxt}-{flipped}: band {new_h} px on {examined} docks")
    assert examined >= 20, f"only {examined} docks were examined"
    assert not findings, "after the mode switch: " + "; ".join(findings[:6])
