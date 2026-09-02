"""Acceptance tests for ``Cursor_Feedback_Overlay``.

Covers the WIDGET half of ``REQ-IS-UI-024``, ``-025``, ``-026`` -- the part
built here and reachable without ``ui/main_window.py`` (a sibling task, same wave,
not a dependency of this task): geometry (edge/padding from the named
constants, never re-typed numbers), the restart-on-change contract, cursor
tracking while visible, and the never-takes-input/never-takes-focus
guarantee -- plus the import allow-list AST gate that stands in for the
``ui -> ui`` edge ``check_layering`` structurally cannot see (plan.md §3.3).

**Not exercised here (recorded, not silently skipped):** ``SC-U026-1``
(suppressed during a stroke) and ``SC-U026-2`` (a suppressed square is not
queued) are the SHELL's decision -- ``ui/main_window.py``'s
``_set_active_color`` / ``_on_tool_action`` -- and that sibling task is not a
dependency of this one (same wave, W6). ``SC-U026-3`` (never in an export /
saved project / rendered frame) is likewise a shell + export-path property.
This widget is, BY CONSTRUCTION, a ``viewport()`` child rather than a
``QGraphicsItem`` (module docstring, plan.md §3.3 RULING) -- which is exactly
what makes ``SC-U026-3`` a structural fact once that sibling task parents it correctly --
but that parenting and the stroke-suppression decision are that sibling task's to test.
Recorded as **could not verify here -- depends on that sibling task, not yet built**;
counted as NOT covered by this module (never presumed passing).

Both themes run automatically via the suite's autouse ``theme`` fixture;
none of these assertions depend on theme (the overlay draws the colour/icon
it is TOLD to draw, never a theme role), so no test here parametrises on it
explicitly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from pixelart_creator.logic.constants import (
    FEEDBACK_DURATION_MS,
    FEEDBACK_FADE_TAIL_RATIO,
    FEEDBACK_SQUARE_PAD_RATIO,
    FEEDBACK_SQUARE_PX,
)
from pixelart_creator.ui.cursor_feedback_overlay import Cursor_Feedback_Overlay

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)

NO_MOD = Qt.KeyboardModifier.NoModifier
NO_BTN = Qt.MouseButton.NoButton

_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "pixelart_creator"
    / "ui"
    / "cursor_feedback_overlay.py"
)


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


class _ClickRecordingWidget(QWidget):
    """A plain viewport stand-in that records whether a press reached it."""

    def __init__(self) -> None:
        super().__init__()
        self.press_count = 0

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override name)
        self.press_count += 1
        super().mousePressEvent(event)


def _overlay(qtbot, viewport: QWidget | None = None):
    """Build a real viewport + a real ``Cursor_Feedback_Overlay`` over it."""
    if viewport is None:
        viewport = QWidget()
    qtbot.addWidget(viewport)
    viewport.resize(400, 300)
    viewport.show()
    overlay = Cursor_Feedback_Overlay(viewport)
    qtbot.addWidget(overlay)
    return overlay, viewport


def _move_cursor(viewport: QWidget, x: int, y: int) -> None:
    """Deliver a real ``QMouseEvent.MouseMove`` at ``(x, y)`` through the
    installed event filter -- the exact production feed
    (``viewport.installEventFilter(self)``), not a direct method call."""
    app = QApplication.instance()
    assert app is not None
    pt = QPointF(x, y)
    event = QMouseEvent(QEvent.Type.MouseMove, pt, pt, NO_BTN, NO_BTN, NO_MOD)
    app.sendEvent(viewport, event)


def _solid_icon(rgba: tuple[int, int, int, int]) -> QIcon:
    """A ``FEEDBACK_SQUARE_PX``-sized solid-fill icon, distinguishable by
    sampling its rendered centre pixel (verified 1:1, no scaling artefact,
    against this exact edge length)."""
    pixmap = QPixmap(FEEDBACK_SQUARE_PX, FEEDBACK_SQUARE_PX)
    pixmap.fill(QColor(*rgba))
    return QIcon(pixmap)


def _centre_colour(overlay: Cursor_Feedback_Overlay) -> QColor:
    """Force a real paintEvent and sample the drawn centre pixel -- the
    OBSERVABLE proxy for both fill colour and opacity (alpha), never the
    private ``_color``/``_opacity`` attributes."""
    centre = FEEDBACK_SQUARE_PX // 2
    return overlay.grab().toImage().pixelColor(centre, centre)


# --------------------------------------------------------------------------- #
# REQ-IS-UI-024 / SC-U024-1, SC-U024-2 -- geometry, left of the cursor        #
# --------------------------------------------------------------------------- #


def test_sc_u024_1_and_2_colour_square_left_of_cursor_with_named_padding(qtbot):
    """SC-U024-1: right edge left of the cursor. SC-U024-2: edge/pad from the
    named constants, never re-typed numbers."""
    overlay, viewport = _overlay(qtbot)
    cursor_x, cursor_y = 200, 150
    _move_cursor(viewport, cursor_x, cursor_y)
    overlay.show_colour(RED)

    assert overlay.width() == FEEDBACK_SQUARE_PX
    assert overlay.height() == FEEDBACK_SQUARE_PX

    pad = FEEDBACK_SQUARE_PX * FEEDBACK_SQUARE_PAD_RATIO
    expected_x = round(cursor_x - pad - FEEDBACK_SQUARE_PX)
    expected_y = round(cursor_y - FEEDBACK_SQUARE_PX / 2)
    assert (overlay.x(), overlay.y()) == (expected_x, expected_y)
    # SC-U024-1's own wording: the right edge is to the left of the cursor.
    assert overlay.x() + overlay.width() < cursor_x


def test_sc_u024_1_colour_square_is_actually_filled_with_the_new_colour(qtbot):
    """The square drawn is genuinely filled with the colour just set (not a
    stale/default fill) -- sampled from the real paintEvent output."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 120, 90)
    overlay.show_colour(RED)
    colour = _centre_colour(overlay)
    assert (colour.red(), colour.green(), colour.blue()) == RED[:3]


# --------------------------------------------------------------------------- #
# REQ-IS-UI-025 / SC-U025-1, SC-U025-2 -- geometry, on top of the cursor      #
# --------------------------------------------------------------------------- #


def test_sc_u025_1_icon_square_centred_on_cursor(qtbot):
    """SC-U025-1: the tool square is centred ON the cursor -- the opposite
    side rule from the colour square, same constants."""
    overlay, viewport = _overlay(qtbot)
    cursor_x, cursor_y = 200, 150
    _move_cursor(viewport, cursor_x, cursor_y)
    overlay.show_icon(_solid_icon(RED))

    assert overlay.width() == FEEDBACK_SQUARE_PX
    assert overlay.height() == FEEDBACK_SQUARE_PX
    edge = FEEDBACK_SQUARE_PX
    expected_x = round(cursor_x - edge / 2)
    expected_y = round(cursor_y - edge / 2)
    assert (overlay.x(), overlay.y()) == (expected_x, expected_y)


def test_sc_u025_2_icon_square_shares_geometry_and_duration_with_colour_square(
    qtbot,
):
    """SC-U025-2: same 24px DPI-scaled edge, same 10% padding constant, same
    1000ms duration -- both squares are driven by ONE set of constants."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 50, 50)
    overlay.show_colour(RED)
    colour_edge = (overlay.width(), overlay.height())
    colour_duration = overlay.animation.duration()

    _move_cursor(viewport, 50, 50)
    overlay.show_icon(_solid_icon(GREEN))
    icon_edge = (overlay.width(), overlay.height())
    icon_duration = overlay.animation.duration()

    assert colour_edge == icon_edge == (FEEDBACK_SQUARE_PX, FEEDBACK_SQUARE_PX)
    assert colour_duration == icon_duration == FEEDBACK_DURATION_MS


def test_sc_u025_1_icon_square_shows_the_icon_given(qtbot):
    """The square drawn on a tool change is genuinely the icon passed in."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 80, 80)
    overlay.show_icon(_solid_icon(GREEN))
    colour = _centre_colour(overlay)
    assert (colour.red(), colour.green(), colour.blue()) == GREEN[:3]


# --------------------------------------------------------------------------- #
# SC-U024-4 -- vanishes after the named 1000ms duration                      #
# --------------------------------------------------------------------------- #


def test_sc_u024_4_square_vanishes_after_the_named_duration(qtbot):
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 60, 60)
    overlay.show_colour(RED)
    assert overlay.isVisible() is True

    overlay.animation.setCurrentTime(FEEDBACK_DURATION_MS)
    assert overlay.isVisible() is False


def test_opacity_is_held_then_falls_over_the_named_fade_tail_only(qtbot):
    """Opacity (sampled via the real painted alpha channel, never the private
    attribute) is held at full through the leading
    ``1 - FEEDBACK_FADE_TAIL_RATIO`` span, then genuinely falls only across
    the final ``FEEDBACK_FADE_TAIL_RATIO`` fraction of the duration -- driven
    deterministically via ``QVariantAnimation.setCurrentTime``, no sleep."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 60, 60)
    overlay.show_colour(RED)

    fade_start_ms = FEEDBACK_DURATION_MS * (1.0 - FEEDBACK_FADE_TAIL_RATIO)

    overlay.animation.setCurrentTime(int(fade_start_ms))
    held = _centre_colour(overlay)
    assert held.alpha() == 255, "opacity fell before the fade-tail fraction began"

    mid_fade_ms = fade_start_ms + (FEEDBACK_DURATION_MS - fade_start_ms) / 2
    overlay.animation.setCurrentTime(int(mid_fade_ms))
    mid = _centre_colour(overlay)
    assert 0 < mid.alpha() < 255, "opacity did not fall partway through the fade tail"

    overlay.animation.setCurrentTime(FEEDBACK_DURATION_MS)
    assert overlay.isVisible() is False


# --------------------------------------------------------------------------- #
# SC-U024-3 -- DPI scaling (source-level mechanism guard)                    #
# --------------------------------------------------------------------------- #


def test_sc_u024_3_no_manual_devicepixelratio_multiply_source_guard():
    """SC-U024-3: the square's device size scales via Qt's own backing-store
    DPR handling, never a hand-applied multiply (module docstring: 'No
    devicePixelRatio() factor is applied by hand'). A genuine DPR=2 screen
    cannot be forced under the offscreen QPA platform used by this suite
    (empirically confirmed: ``QTest.mouseClick``-style direct delivery and a
    plain offscreen QScreen both report DPR=1 regardless of env overrides
    applied after QApplication construction) -- this project's own
    established pattern for the identical constraint is
    ``test_portability_ui.py::test_sc_p13_ui_002_1_no_manual_dpr_multiply_in_dpi_code_path``,
    a source-level guard. This test follows that precedent rather than
    asserting a device measurement this environment cannot produce."""
    source = _MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "devicePixelRatio() *",
        "* devicePixelRatio",
        "devicePixelRatioF() *",
        "* devicePixelRatioF()",
    )
    violations = [pattern for pattern in forbidden if pattern in source]
    assert (
        not violations
    ), f"cursor_feedback_overlay.py contains a manual DPR multiply: {violations}"
    # The logical size is set exactly once, from the named constant.
    assert "setFixedSize(FEEDBACK_SQUARE_PX, FEEDBACK_SQUARE_PX)" in source


# --------------------------------------------------------------------------- #
# SC-U024-5 / SC-U025-3 -- restart, never queue                              #
# --------------------------------------------------------------------------- #


def test_sc_u024_5_second_colour_change_restarts_the_animation(qtbot):
    """SC-U024-5: advance 600ms into the animation, then change colour again
    -- exactly one square is visible, filled with the NEW colour, and its
    remaining time is the full duration again (restart, never a queue)."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 150, 150)
    overlay.show_colour(RED)
    overlay.animation.setCurrentTime(600)
    assert overlay.animation.currentTime() == 600

    overlay.show_colour(GREEN)

    assert (
        overlay.animation.currentTime() == 0
    ), "second change did not restart the animation from the beginning"
    assert overlay.isVisible() is True
    colour = _centre_colour(overlay)
    assert (colour.red(), colour.green(), colour.blue()) == GREEN[:3], (
        "square still shows the OLD colour after the second change -- looks "
        "queued behind the first rather than restarted"
    )
    assert colour.alpha() == 255, "opacity was not reset to full on restart"


def test_sc_u025_3_second_tool_change_restarts_the_animation(qtbot):
    """SC-U025-3: same restart contract, for the tool/icon square."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 150, 150)
    overlay.show_icon(_solid_icon(RED))
    overlay.animation.setCurrentTime(600)
    assert overlay.animation.currentTime() == 600

    overlay.show_icon(_solid_icon(GREEN))

    assert (
        overlay.animation.currentTime() == 0
    ), "second tool change did not restart the animation from the beginning"
    assert overlay.isVisible() is True
    colour = _centre_colour(overlay)
    assert (colour.red(), colour.green(), colour.blue()) == GREEN[:3], (
        "square still shows the OLD glyph after the second change -- looks "
        "queued behind the first rather than restarted"
    )
    assert colour.alpha() == 255, "opacity was not reset to full on restart"


# --------------------------------------------------------------------------- #
# SC-U024-6 -- follows the cursor while visible                              #
# --------------------------------------------------------------------------- #


def test_sc_u024_6_square_follows_cursor_while_visible(qtbot):
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 80, 80)
    overlay.show_colour(RED)
    pos_before = (overlay.x(), overlay.y())

    _move_cursor(viewport, 260, 190)
    pos_after = (overlay.x(), overlay.y())

    assert pos_after != pos_before
    pad = FEEDBACK_SQUARE_PX * FEEDBACK_SQUARE_PAD_RATIO
    expected_x = round(260 - pad - FEEDBACK_SQUARE_PX)
    expected_y = round(190 - FEEDBACK_SQUARE_PX / 2)
    assert pos_after == (expected_x, expected_y), "offset from the cursor did not hold"


def test_sc_u024_6_icon_square_also_follows_the_cursor_centred(qtbot):
    """Same 'follows while visible' contract for the icon square, on the
    centred side rather than the left-of side."""
    overlay, viewport = _overlay(qtbot)
    _move_cursor(viewport, 80, 80)
    overlay.show_icon(_solid_icon(RED))

    _move_cursor(viewport, 260, 190)
    edge = FEEDBACK_SQUARE_PX
    expected_x = round(260 - edge / 2)
    expected_y = round(190 - edge / 2)
    assert (overlay.x(), overlay.y()) == (expected_x, expected_y)


def test_square_does_not_reposition_on_cursor_move_while_hidden(qtbot):
    """The 'while visible' qualifier of SC-U024-6: a cursor move before any
    ``show_colour``/``show_icon`` call must not move a not-yet-shown
    overlay."""
    overlay, viewport = _overlay(qtbot)
    initial_pos = (overlay.x(), overlay.y())
    _move_cursor(viewport, 300, 300)
    assert overlay.isVisible() is False
    assert (overlay.x(), overlay.y()) == initial_pos


# --------------------------------------------------------------------------- #
# SC-U024-7 -- no input, no focus                                            #
# --------------------------------------------------------------------------- #


def test_req_is_ui_024_and_025_never_takes_focus(qtbot):
    overlay, viewport = _overlay(qtbot)
    assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus

    _move_cursor(viewport, 90, 90)
    overlay.show_colour(RED)
    overlay.setFocus()  # attempt to force focus onto it
    assert overlay.hasFocus() is False, "the square took keyboard focus"


def test_sc_u024_7_transparent_for_mouse_events_attribute_is_set(qtbot):
    """The real Qt attribute Qt's own window system uses to decide whether a
    click at the overlay's screen position is delivered to it or passed
    through to whatever is underneath."""
    overlay, _viewport = _overlay(qtbot)
    assert (
        overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True
    )


def test_sc_u024_7_installed_event_filter_never_consumes_input(qtbot):
    """SC-U024-7, mechanism-level: the overlay's ``eventFilter`` (installed on
    the viewport to track the cursor, module docstring) returns ``False``
    unconditionally, so Qt keeps delivering every event to the viewport's
    own handler -- a click that reaches the viewport is a click that was
    never intercepted by the overlay's presence.

    A full native hit-test simulation of 'a click over the overlay's screen
    rect lands on the widget underneath it' could not be produced under the
    offscreen QPA platform used by this suite: ``QTest.mouseClick(widget,
    ...)`` sends the event straight to the given ``widget`` and bypasses
    Qt's own child-widget hit-testing entirely -- verified by probe, the
    measured press-count was identical whether ``WA_TransparentForMouseEvents``
    was set or not, so that harness cannot distinguish the two cases. This
    test instead drives the two real, production mechanisms the module's own
    docstring names for this contract: the attribute (previous test) and the
    filter's unconditional ``False`` return, exercised via a real
    ``QApplication.sendEvent`` delivery through the actually-installed
    filter chain (not a bare method call)."""
    viewport = _ClickRecordingWidget()
    qtbot.addWidget(viewport)
    viewport.resize(300, 200)
    viewport.show()
    overlay = Cursor_Feedback_Overlay(viewport)
    qtbot.addWidget(overlay)
    _move_cursor(viewport, 50, 50)
    overlay.show_colour(RED)

    app = QApplication.instance()
    assert app is not None
    pt = QPointF(50, 50)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pt,
        pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        NO_MOD,
    )
    app.sendEvent(viewport, press)
    assert (
        viewport.press_count == 1
    ), "the click never reached the viewport through the overlay's filter chain"

    # The filter's own contract holds for a non-MouseMove event too (not
    # just the MouseMove path it repositions on).
    consumed = overlay.eventFilter(viewport, press)
    assert consumed is False


# --------------------------------------------------------------------------- #
# This module's own gate: the import allow-list AST gate                     #
#                                                                              #
# check_layering cannot see a ui -> ui edge (plan.md §3.3), so this is the    #
# ONLY gate standing between the overlay and a domain back door. It states    #
# its own denominator (how many import statements it examined) so a parse    #
# that silently finds zero imports reads as a FAILURE, never a pass --       #
# this project has five recorded cases of exactly that failure mode.         #
# --------------------------------------------------------------------------- #

_ALLOWED_EXACT = {"pixelart_creator.logic.constants"}


def _scan_imports(source: str, filename: str = "<module>"):
    """Return ``(import_statements, violations)`` for ``source``.

    ``import_statements`` is a list of ``(kind, target, lineno)``; a target
    is allowed iff its root package is ``PySide6`` or it is EXACTLY
    ``pixelart_creator.logic.constants`` (plan.md §3.3, the overlay's own
    docstring "Import allow-list" section).
    """
    tree = ast.parse(source, filename=filename)
    import_statements: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_statements.append(("import", alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            import_statements.append(("from", node.module or "", node.lineno))

    violations = [
        f"line {lineno}: {kind} {target!r}"
        for kind, target, lineno in import_statements
        if not (target.split(".")[0] == "PySide6" or target in _ALLOWED_EXACT)
    ]
    return import_statements, violations


def test_t19_import_allow_list_gate_examines_the_real_module():
    """AST-parse ``ui/cursor_feedback_overlay.py``; every
    ``Import``/``ImportFrom`` target must be ``PySide6.*`` or exactly
    ``pixelart_creator.logic.constants``. Fails loudly, naming the exact
    line and target added, if the set is ever a superset of the allow-list.
    """
    source = _MODULE_PATH.read_text(encoding="utf-8")
    import_statements, violations = _scan_imports(source, filename=str(_MODULE_PATH))

    # A zero-import result means the scan parsed the wrong file (or an empty
    # one) -- the module's own docstring proves imports exist -- and MUST be
    # read as a gate failure, never a silent pass.
    assert import_statements, (
        f"import allow-list gate examined ZERO import statements in "
        f"{_MODULE_PATH} -- this means the file was parsed wrong/empty, not "
        f"that the module genuinely has no imports; treat as a gate failure."
    )

    assert not violations, (
        "cursor_feedback_overlay.py imports outside the allow-list "
        "{PySide6.*, pixelart_creator.logic.constants}: "
        + "; ".join(violations)
        + f" (examined {len(import_statements)} import statement(s) total)"
    )


def test_t19_import_allow_list_gate_detects_a_planted_violation():
    """Self-check that the gate is not a vacuous always-pass: the SAME scan
    function, run over a deliberately poisoned source string (never the real
    product file, never written to disk), must reject an out-of-allow-list
    import and name exactly which one. Guards against the five-times-recorded
    failure class in this project: an import/gate script that finds nothing
    because it parsed the wrong thing, and says nothing about it either."""
    poisoned_source = (
        "from PySide6.QtWidgets import QWidget\n"
        "from pixelart_creator.logic.document import Document\n"  # planted
    )
    import_statements, violations = _scan_imports(poisoned_source)
    assert len(import_statements) == 2
    assert violations == [
        "line 2: from 'pixelart_creator.logic.document'"
    ], f"planted violation was not detected: {violations!r}"
