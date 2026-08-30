"""UI acceptance tests for `REQ-IS-UI-027` -- the eleven tool glyphs and their
loader (T-16).

Covers every scenario `tasks.md` assigns to this task, `SC-U027-1..6`:

- SC-U027-1: every tool action carries a non-null icon that renders to a
  non-empty pixmap.
- SC-U027-2: the eleven glyphs are pairwise distinct at the same render size.
- SC-U027-3: the two boolean toggles (Filled Shapes, Pixel Perfect) stay
  text-only -- no twelfth glyph slipped onto a non-tool action.
- SC-U027-4: icons never displace the accessible name -- each tool action
  keeps a non-empty ``text()``, a non-empty accessible name (the actual
  AT-facing name Qt's accessibility bridge derives for the mounted toolbar
  button, queried live via ``QAccessible`` rather than assumed equal to
  ``text()``), and a tooltip naming the tool and its key.
- SC-U027-5: the tinted pixmap differs between the light and dark themes at
  the same coordinate, proving the tint is live rather than baked, and a
  runtime theme switch re-tints the already-mounted icons (T-36's wiring),
  not just icons resolved fresh.
- SC-U027-6 (spec-only, review -- authorship of the SVGs is a human
  judgement; the one part of it this module CAN assert in code is D-10's
  licence-surface consequence): no `NOTICE` entry was added for the glyphs.

The bijection assertion (`set(TOOL_GLYPH_IDS) == set(win._tool_actions)`) is
the one plan.md section 4.3 names as "the assertion that earns its keep": it
catches a renamed tool, a missing glyph, and a stray twelfth file in a single
line, with a failure message naming which side of the symmetric difference is
wrong.

This module depends on T-36 (the mounting task), not on T-14 alone --
`tasks.md`'s 2026-08-30 dependency correction: T-14 only builds the resolver,
nothing mounted an icon on a `QAction` until T-36, so the bijection and
non-null-icon assertions could not have passed against T-14 alone.

Every test in this module also runs under both the light and the dark QSS
theme via the autouse ``theme`` fixture in ``conftest.py`` (app-level
stylesheet parametrisation). That is independent of the *glyph tint* theme
this module exercises directly through ``Main_Window._theme`` /
``tool_icon(..., theme=...)`` -- the two are different axes, and both are
covered here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pytest
from PySide6.QtGui import QAccessible, QImage

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import THEME_DARK, THEME_LIGHT
from pixelart_creator.ui.tool_icons import TOOL_GLYPH_IDS, tool_icon

#: Render size requested from each `QIcon.pixmap()` call in this module.
#: Deliberately NOT imported from `tool_icons._ICON_RENDER_SIZE_PX` (a
#: private module constant) -- `QIcon.pixmap()` rescales regardless of the
#: resolver's own internal render size, so this test asserts on observable
#: behaviour, not on an implementation detail (pytest-qt-harness).
_RENDER_PX = 32

#: The eleven tool labels `Main_Window._retranslate()` assigns, keyed by
#: `tool_id` -- matches `main_window.py`'s own `labels` dict exactly, so a
#: renamed label fails HERE rather than passing silently on a bare
#: `!= ""` check.
_EXPECTED_LABELS = {
    "pencil": "Pencil",
    "eraser": "Eraser",
    "fill": "Fill",
    "line": "Line",
    "picker": "Colour picker",
    "rectangle": "Rectangle",
    "ellipse": "Ellipse",
    "select_rect": "Rectangle select",
    "select_lasso": "Lasso select",
    "select_wand": "Magic wand",
    "dither": "Dither",
}

#: The eleven home-row shortcut keys `Main_Window._build_actions()` assigns,
#: keyed by `tool_id` -- matches `main_window.py`'s own `tool_shortcuts` dict
#: (and `test_a11y_theme.py`'s `_EXPECTED_TOOL_SHORTCUTS`) exactly, so the
#: tooltip-names-its-key half of SC-U027-4 is checked against the real
#: binding rather than an arbitrary string.
_EXPECTED_TOOL_SHORTCUTS = {
    "pencil": "A",
    "picker": "Shift+A",
    "eraser": "Q",
    "rectangle": "S",
    "line": "W",
    "ellipse": "Shift+W",
    "select_rect": "D",
    "fill": "F",
    "dither": "Shift+F",
    "select_lasso": "E",
    "select_wand": "Shift+E",
}


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _rendered_image(icon, size: int = _RENDER_PX) -> QImage:
    return icon.pixmap(size, size).toImage()


def _first_opaque_pixel(image: QImage) -> Optional[Tuple[int, int]]:
    """Return the coordinate of the first fully-opaque pixel in ``image``.

    Fully opaque (alpha == 255), not merely alpha > 0, so the comparison
    this backs never lands on an antialiased edge pixel where light- and
    dark-theme blending could coincidentally agree.
    """
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() == 255:
                return x, y
    return None


def _accessible_name(widget) -> str:
    """Return the AT-facing accessible name Qt derives for ``widget``.

    Queried live through :class:`QAccessible` rather than
    ``widget.accessibleName()`` -- the latter is empty by construction unless
    explicitly set (measured: a plain ``QToolButton`` mounted from a
    ``QAction`` with ``setText()`` alone reports ``accessibleName() == ""``),
    while Qt's accessibility bridge derives the real AT-facing name from the
    action's text at query time. Asserting on the bridge's own answer is the
    only way to test what a screen reader actually receives, rather than a
    property nobody in this codebase ever sets.
    """
    iface = QAccessible.queryAccessibleInterface(widget)
    assert iface is not None, "no QAccessible interface for the mounted tool button"
    return iface.text(QAccessible.Text.Name)


# ---------------------------------------------------------------------------
# The bijection -- "the assertion that earns its keep" (plan.md Section 4.3)
# ---------------------------------------------------------------------------


def test_sc_u027_bijection_glyph_ids_match_mounted_tool_actions(qtbot):
    """`set(TOOL_GLYPH_IDS) == set(win._tool_actions)`.

    Catches a renamed tool, a missing glyph, AND a stray twelfth file in one
    line -- the failure message names the symmetric difference so a failure
    says which side is wrong, not just that the two sets differ.
    """
    win = _window(qtbot)
    glyph_ids = set(TOOL_GLYPH_IDS)
    mounted_ids = set(win._tool_actions)
    glyphs_without_action = glyph_ids - mounted_ids
    actions_without_glyph = mounted_ids - glyph_ids
    assert glyph_ids == mounted_ids, (
        "TOOL_GLYPH_IDS and win._tool_actions diverge -- "
        f"glyph ids with no mounted action: {sorted(glyphs_without_action) or 'none'}; "
        f"mounted actions with no matching glyph id: {sorted(actions_without_glyph) or 'none'}"
    )


# ---------------------------------------------------------------------------
# SC-U027-1 -- every tool action carries a non-null icon
# ---------------------------------------------------------------------------


def test_sc_u027_1_every_tool_action_has_non_null_icon(qtbot):
    win = _window(qtbot)
    assert set(win._tool_actions) == set(TOOL_GLYPH_IDS)  # precondition, proven above
    for tool_id, action in win._tool_actions.items():
        icon = action.icon()
        assert not icon.isNull(), f"{tool_id}: mounted action.icon() is null"
        pixmap = icon.pixmap(_RENDER_PX, _RENDER_PX)
        assert not pixmap.isNull(), f"{tool_id}: icon renders to a null pixmap"
        assert (
            pixmap.width() > 0 and pixmap.height() > 0
        ), f"{tool_id}: icon renders to an empty ({pixmap.width()}x{pixmap.height()}) pixmap"


# ---------------------------------------------------------------------------
# SC-U027-2 -- the eleven glyphs are pairwise distinct
# ---------------------------------------------------------------------------


def test_sc_u027_2_the_eleven_glyphs_are_pairwise_distinct(qapp):
    rendered = {
        tool_id: _rendered_image(tool_icon(tool_id, theme=THEME_LIGHT))
        for tool_id in TOOL_GLYPH_IDS
    }
    ids = list(rendered)
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1 :]:
            assert (
                rendered[id_a] != rendered[id_b]
            ), f"{id_a} and {id_b} render identical glyphs at {_RENDER_PX}px"


# ---------------------------------------------------------------------------
# SC-U027-3 -- the boolean toggles stay text-only
# ---------------------------------------------------------------------------


def test_sc_u027_3_filled_shapes_and_pixel_perfect_toggles_stay_text_only(qtbot):
    """Filled Shapes and Pixel Perfect are not tools (spec section 5.8) and
    carry no icon -- eleven glyphs, never a twelfth."""
    win = _window(qtbot)
    assert win._filled_action.icon().isNull(), "Filled Shapes toggle gained an icon"
    assert (
        win._pixel_perfect_action.icon().isNull()
    ), "Pixel Perfect toggle gained an icon"
    assert win._filled_action.text() != ""
    assert win._pixel_perfect_action.text() != ""


# ---------------------------------------------------------------------------
# SC-U027-4 -- icons do not displace text, accessible name, or tooltip
# ---------------------------------------------------------------------------


def test_sc_u027_4_every_tool_action_keeps_text_and_accessible_name(qtbot):
    """Article V.1: an icon-only toolbar is unusable with a screen reader.

    Every tool action's ``text()``, live AT-facing accessible name, and
    tooltip (naming the tool and its assigned key) are asserted explicitly,
    per action -- not inferred from the icon's presence.
    """
    win = _window(qtbot)
    assert set(_EXPECTED_LABELS) == set(TOOL_GLYPH_IDS)  # fixture self-check
    assert set(_EXPECTED_TOOL_SHORTCUTS) == set(TOOL_GLYPH_IDS)  # fixture self-check
    for tool_id, action in win._tool_actions.items():
        # text() -- the label itself.
        assert action.text() != "", f"{tool_id}: action.text() is empty"
        assert action.text() == _EXPECTED_LABELS[tool_id], (
            f"{tool_id}: expected label {_EXPECTED_LABELS[tool_id]!r}, "
            f"got {action.text()!r}"
        )
        # accessible name -- the actual AT-facing name Qt's accessibility
        # bridge derives for the mounted toolbar button.
        button = win._toolbar.widgetForAction(action)
        assert button is not None, f"{tool_id}: action is not mounted on the toolbar"
        name = _accessible_name(button)
        assert name != "", f"{tool_id}: accessible name is empty"
        # tooltip -- names the tool and its key.
        tooltip = action.toolTip()
        assert tooltip != "", f"{tool_id}: tooltip is empty"
        key = _EXPECTED_TOOL_SHORTCUTS[tool_id]
        assert (
            key in tooltip
        ), f"{tool_id}: tooltip {tooltip!r} does not name its key {key!r}"


# ---------------------------------------------------------------------------
# SC-U027-5 (part 1) -- the tint is live, not baked: resolver output differs
# between the light and the dark theme at the same coordinate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_id", TOOL_GLYPH_IDS)
def test_sc_u027_5_tinted_pixmap_differs_between_light_and_dark_theme(qapp, tool_id):
    light_image = _rendered_image(tool_icon(tool_id, theme=THEME_LIGHT))
    dark_image = _rendered_image(tool_icon(tool_id, theme=THEME_DARK))
    coordinate = _first_opaque_pixel(light_image)
    assert coordinate is not None, (
        f"{tool_id}: no fully-opaque pixel found in the light-theme render "
        "-- cannot prove the tint is live without one"
    )
    assert coordinate == _first_opaque_pixel(dark_image), (
        f"{tool_id}: light and dark renders have different alpha silhouettes "
        "-- the two themes should differ only in tint colour, not in shape"
    )
    x, y = coordinate
    light_pixel = light_image.pixelColor(x, y)
    dark_pixel = dark_image.pixelColor(x, y)
    assert light_pixel != dark_pixel, (
        f"{tool_id}: pixel at ({x}, {y}) is {light_pixel.name()} in both themes -- "
        "a tinter that returns an identical pixmap for both themes would pass a "
        "non-null-only check but must fail this one"
    )


# ---------------------------------------------------------------------------
# SC-U027-5 (part 2) -- a runtime theme switch re-tints the MOUNTED icons
# ---------------------------------------------------------------------------


def test_sc_u027_5_runtime_theme_switch_retints_mounted_icons(qtbot):
    """T-36 wired `set_theme` to call `_apply_tool_icons` again.

    Without that wiring the toolbar would keep dark glyphs on a light ground
    (or vice versa) after a runtime switch -- a defect invisible to any test
    that builds a window once. This test builds ONE window, captures the
    mounted icon before the switch, calls `win.set_theme(...)`, and asserts
    the SAME action's mounted icon changed in place.
    """
    win = _window(qtbot)
    assert win._theme == THEME_LIGHT  # the documented default

    before_images = {}
    for tool_id, action in win._tool_actions.items():
        image = _rendered_image(action.icon())
        coordinate = _first_opaque_pixel(image)
        assert (
            coordinate is not None
        ), f"{tool_id}: no fully-opaque pixel found before the theme switch"
        before_images[tool_id] = (image, coordinate)

    win.set_theme(THEME_DARK)
    assert win._theme == THEME_DARK

    for tool_id, action in win._tool_actions.items():
        before_image, coordinate = before_images[tool_id]
        after_image = _rendered_image(action.icon())
        x, y = coordinate
        before_pixel = before_image.pixelColor(x, y)
        after_pixel = after_image.pixelColor(x, y)
        assert before_pixel != after_pixel, (
            f"{tool_id}: mounted icon did not change after set_theme({THEME_DARK!r}) -- "
            f"pixel at ({x}, {y}) stayed {before_pixel.name()}"
        )
        # The re-tinted mounted icon must match the resolver's own dark-theme
        # output, not merely "some other colour".
        expected = _rendered_image(tool_icon(tool_id, theme=THEME_DARK))
        assert after_image.pixelColor(x, y) == expected.pixelColor(x, y), (
            f"{tool_id}: re-tinted mounted icon does not match "
            f"tool_icon({tool_id!r}, theme={THEME_DARK!r})'s own output"
        )


# ---------------------------------------------------------------------------
# SC-U027-6 -- no NOTICE entry was added for the glyphs (D-10)
# ---------------------------------------------------------------------------


def test_sc_u027_6_no_notice_entry_added_for_the_glyphs():
    """D-10: the eleven glyphs are original works authored in this repository,
    so no third-party licence obligation enters the repository -- and
    therefore no `NOTICE` entry names them.

    This asserts the absence directly against the real, on-disk `NOTICE`
    file: no case-insensitive mention of "icon"/"glyph"/"svg" appears
    anywhere in it. `NOTICE`'s only entries today are PySide6/Qt, NumPy,
    Pillow and pytest -- none of which is an icon set -- so this is a
    genuine absence check, not a tautology.
    """
    repo_root = Path(__file__).resolve().parents[3]
    notice_path = repo_root / "NOTICE"
    assert notice_path.is_file(), f"NOTICE not found at {notice_path}"
    text = notice_path.read_text(encoding="utf-8").lower()
    for forbidden in ("icon", "glyph", "svg"):
        assert forbidden not in text, (
            f"NOTICE gained a mention of {forbidden!r} -- the glyphs are original "
            "works and must carry no third-party attribution (D-10)"
        )
