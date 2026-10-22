"""Theme, focus and pixel-chrome acceptance tests (REQ-VI-UI-003 .. -009; ADR-0069/0070).

This module verifies the **rendered** result of the pixel-art visual identity at
the UI level, over every shipped combination of a *style* and a *mode* (the
catalogue's styles x modes -- ``COMBOS`` below prints its own size). The suite's
autouse ``theme`` fixture covers the two modes of the canonical style only
(plan 5.2, A-6: "six-way on every UI test would triple the suite"); the
theme-sensitive gates listed in ADR-0070 decision 9 are therefore parametrised
here, explicitly, over all combinations:

* role-key parity, focus distinct from accent, no widget colour literal;
* the stylesheet contract (``app.styleSheet() == build_qss(mode, style, scale=
  art_scale())``, no ``font-family`` / ``font-size`` / ``:focus``, ``px`` only,
  quoted forward-slash ``url("...")``, ``border-width`` = slice count and
  ``border-image`` slices = slice x scale);
* the focus overlay (rendered focus-role pixels present only on the focused
  control, the state beneath it still visible, the ring's contrast against
  every colour it touches, the tab-bar refit);
* the selected-state cue ring (a non-colour cue where the fill contrast is
  below 3:1);
* frames of the full control set, located **by pixels** (never by
  ``QStyle.subControlRect``, which T040 measured wrong for spin and combo
  buttons, QSS sliders and horizontal scroll bars), popups, dialogs, headings,
  docked docks, the flat canvas workspace.

How a frame is judged. The art is nearest-neighbour with no antialiasing, so a
frame pixel is the role colour of the template cell or it is not. A frame test
composes the template at the widget's own size (``logic.theme_art``), colours
it from the combination's role map and compares the widget's grab with it
cell by cell; ``frame_share`` is the share of examined cells that agree. Every
such check has a control: the same comparison against a native (unstyled)
widget must score far lower (``test_frame_comparator_rejects_the_native_look``),
and the focus counter must report nothing on a control that has no overlay
(``test_focus_helper_fails_on_a_control_without_a_ring``).

Scope notes (stated, not hidden):

* Only the two styles the catalogue ships today are in the matrix; Arcade Kikko
  joins automatically when its data lands (T024). The matrix is four
  combinations until then, not six.
* The dock tests exercise the **mechanism** (``install_dock_frame`` on a dock of
  a plain ``QMainWindow``). Wiring the frame at the Main_Window's own dock sites
  is T052/T053 and is tested there.
* Everything runs on the offscreen platform at device-pixel ratio 1.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollBar,
    QSlider,
    QSpinBox,
    QTabBar,
    QTableWidget,
    QToolButton,
    QToolTip,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data import style_catalog
from pixelart_creator.logic import theme_art
from pixelart_creator.logic.contrast import (
    COMPONENT_MIN_RATIO,
    FOCUS_MIN_RATIO,
    contrast_ratio,
)
from pixelart_creator.logic.theme_art import Template
from pixelart_creator.ui import pixel_chrome
from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.theme import (
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    art_scale,
    available_styles,
    available_themes,
    build_qss,
    canvas_surface_roles,
    role_map,
)
from pixelart_creator.ui.theme_art_files import (
    art_root,
    art_set,
    reset_art,
    transposed,
)
from testing.suites.ui.focus_helpers import (
    assert_focus_rendered,
    count_colour_pixels,
    distinct_neighbours,
    focus_pixel_rgb,
    grab_image,
    image_array,
    measure_focus,
    reveal,
)

# --------------------------------------------------------------------------- #
# The matrix                                                                  #
# --------------------------------------------------------------------------- #


class Combo(NamedTuple):
    """One style x mode combination of the catalogue."""

    style: str
    mode: str

    def label(self) -> str:
        """Return the pytest id of the combination."""
        return f"{self.style}-{self.mode}"


COMBOS: Tuple[Combo, ...] = tuple(
    Combo(style, mode) for style in available_styles() for mode in available_themes()
)
_COMBO_IDS = [c.label() for c in COMBOS]


@pytest.fixture(autouse=True)
def theme(request: pytest.FixtureRequest, qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture inside this module.

    The conftest fixture would run every test here twice with the canonical
    style, duplicating the combination matrix this module parametrises itself.
    This one applies the canonical combination once, so a test that does not
    ask for ``combo`` still runs against a known stylesheet. A test that asks for
    ``combo`` has its combination applied by that fixture before the body runs, so
    the canonical one is not applied first: it would be a second restyle of every
    widget still alive, discarded at once.
    """
    if "combo" not in request.fixturenames:
        apply_theme(qapp, THEME_LIGHT)
    return THEME_LIGHT


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest, qapp) -> Combo:
    """Apply one style x mode combination to the application and return it."""
    chosen: Combo = request.param
    apply_theme(qapp, chosen.mode, chosen.style)
    return chosen


def _roles(c: Combo) -> Dict[str, str]:
    return dict(role_map(c.mode, c.style))


def _rgb(c: Combo, role: str) -> Tuple[int, int, int]:
    value = _roles(c)[role]
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _hex(rgb: Sequence[int]) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


def _packed(rgb: Tuple[int, int, int]) -> int:
    return 0xFF000000 | (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]


def _array(widget: QWidget) -> np.ndarray:
    return image_array(grab_image(widget))


def _unfocus(widget: QWidget) -> None:
    """Take keyboard focus off everything in ``widget``'s window (no ring)."""
    focused = QApplication.focusWidget()
    if focused is not None:
        focused.clearFocus()
    QApplication.processEvents()
    QApplication.processEvents()


def _settle() -> None:
    QApplication.processEvents()
    QApplication.processEvents()


def _show(qtbot, widget: QWidget) -> QWidget:
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    _settle()
    return widget


# --- composing the expected picture -------------------------------------------


def _template(c: Combo, name: str, *, transpose: bool = False) -> Template:
    template = style_catalog.template_set(c.style).get(name)
    return transposed(template) if transpose else template


def _composed(
    c: Combo, name: str, w: int, h: int, *, transpose: bool = False
) -> np.ndarray:
    """Return template ``name`` composed to ``w`` x ``h`` and coloured, RGBA."""
    template = _template(c, name, transpose=transpose)
    grid = (
        template.grid if template.slices.is_zero else theme_art.compose(template, w, h)
    )
    return np.array(theme_art.render(grid, _roles(c), 1).data, copy=True)


def _band(template: Template, w: int, h: int) -> np.ndarray:
    """Return the boolean mask of the frame ring (the slices) of a ``w`` x ``h`` box."""
    s = template.slices
    mask = np.zeros((h, w), dtype=bool)
    mask[: s.top, :] = True
    mask[h - s.bottom :, :] = True
    mask[:, : s.left] = True
    mask[:, w - s.right :] = True
    return mask


def _agree(
    image: np.ndarray, expected: np.ndarray, mask: np.ndarray
) -> Tuple[float, int]:
    """Return ``(share, examined)`` of opaque masked cells whose RGB equal."""
    examined_mask = mask & (expected[..., 3] == 255)
    examined = int(examined_mask.sum())
    if examined == 0:
        return 0.0, 0
    same = (image[..., :3] == expected[..., :3]).all(axis=-1) & examined_mask
    return float(same.sum()) / examined, examined


def frame_share(
    widget: QWidget,
    c: Combo,
    name: str,
    *,
    transpose: bool = False,
    whole: bool = False,
    skip_outer: int = 0,
) -> Tuple[float, int]:
    """Return how much of ``widget``'s grab agrees with template ``name``.

    Args:
        widget: The (unfocused, shown) widget whose own rectangle is the frame.
        c: The combination whose role colours colour the template.
        name: The template name.
        transpose: Compare against the transposed template (horizontal bars).
        whole: Compare every opaque cell (a text-free control), not only the
            frame ring.
        skip_outer: Ignore this many outermost cells on every side (a focused
            control wears its ring over them).

    Returns:
        ``(share, examined cells)``.
    """
    image = _array(widget)
    h, w = image.shape[:2]
    expected = _composed(c, name, w, h, transpose=transpose)
    template = _template(c, name, transpose=transpose)
    mask = np.ones((h, w), dtype=bool) if whole else _band(template, w, h)
    if skip_outer:
        mask[:skip_outer, :] = False
        mask[h - skip_outer :, :] = False
        mask[:, :skip_outer] = False
        mask[:, w - skip_outer :] = False
    return _agree(image, expected, mask)


def locate(
    image: np.ndarray, pattern: np.ndarray, mask: Optional[np.ndarray] = None
) -> List[Tuple[int, int]]:
    """Return the ``(x, y)`` of every place ``pattern`` appears in ``image``.

    Only the opaque cells of ``pattern`` that are also set in ``mask`` are
    compared (a sub-control sprite is drawn over its frame's interior, so the
    interior of a button frame is masked out and the ring alone is located).
    """
    ph, pw = pattern.shape[:2]
    ih, iw = image.shape[:2]
    if ph > ih or pw > iw:
        return []
    use = pattern[..., 3] == 255
    if mask is not None:
        use = use & mask
    ok = np.ones((ih - ph + 1, iw - pw + 1), dtype=bool)
    for y, x in zip(*np.nonzero(use)):
        for channel in range(3):
            ok &= (
                image[y : y + ih - ph + 1, x : x + iw - pw + 1, channel]
                == pattern[y, x, channel]
            )
    return [(int(x), int(y)) for y, x in zip(*np.nonzero(ok))]


def sprite(c: Combo, name: str) -> np.ndarray:
    """Return the sprite template ``name`` coloured, at its native size."""
    template = _template(c, name)
    return np.array(theme_art.render(template.grid, _roles(c), 1).data, copy=True)


def sprite_over(c: Combo, name: str, ground_role: str) -> np.ndarray:
    """Return sprite ``name`` with its transparent cells filled in the ``ground_role`` colour.

    A sprite made of text-coloured cells can also be found inside glyph ink; with its
    own ground required as well, only the sprite matches.
    """
    out = sprite(c, name)
    ground = _rgb(c, ground_role)
    clear = out[..., 3] != 255
    out[clear, :3] = ground
    out[..., 3] = 255
    return out


# --------------------------------------------------------------------------- #
# The matrix itself, and SC-VI-UI-003-1..3                                    #
# --------------------------------------------------------------------------- #


def test_matrix_covers_every_shipped_style_and_mode_and_is_not_empty():
    """The parametrisation is the catalogue's own styles x modes, and not zero.

    Printed on purpose: a matrix that silently shrank to nothing would turn every
    six-way test below into a vacuous pass (the denominator rule).
    """
    index = style_catalog.style_ids(), style_catalog.mode_ids()
    assert len(COMBOS) == len(index[0]) * len(index[1])
    assert len(COMBOS) >= 1
    assert set(COMBOS) == {Combo(s, m) for s in index[0] for m in index[1]}
    print(f"combinations in the matrix: {len(COMBOS)} = {_COMBO_IDS}")


def test_sc_vi_ui_003_1_all_role_maps_carry_identical_keys():
    """SC-VI-UI-003-1: the role-key sets of every combination are identical."""
    keysets = {c: frozenset(role_map(c.mode, c.style)) for c in COMBOS}
    reference = next(iter(keysets.values()))
    assert reference, "a role map with no keys examined nothing"
    for c, keys in keysets.items():
        assert keys == reference, f"{c.label()}: differs by {sorted(keys ^ reference)}"
    assert set(style_catalog.role_keys()) == set(reference)
    print(f"role maps examined: {len(keysets)}, keys each: {len(reference)}")


def test_sc_vi_ui_003_1_legacy_roles_alias_serves_the_default_style():
    """Older callers read ``theme._ROLES[mode]``: it is the default style's maps."""
    legacy = theme_module._ROLES
    assert set(legacy) == set(available_themes())
    for mode in available_themes():
        assert legacy[mode] == dict(role_map(mode, DEFAULT_STYLE))
    with pytest.raises(AttributeError):
        theme_module.__getattr__("no_such_name")


def test_sc_vi_ui_003_2_focus_is_its_own_colour(combo):
    """SC-VI-UI-003-2: the focus role and the accent role are different colours."""
    roles = _roles(combo)
    assert roles["focus"].lower() != roles["accent"].lower()


def test_unknown_mode_and_style_are_refused_by_name():
    """A mode or style the catalogue does not ship raises ValueError, naming it."""
    with pytest.raises(ValueError, match="no-such-mode"):
        role_map("no-such-mode")
    with pytest.raises(ValueError, match="no-such-style"):
        role_map(THEME_LIGHT, "no-such-style")
    with pytest.raises(ValueError):
        build_qss("no-such-mode")


_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_FUNCTIONAL_COLOUR = re.compile(r"\b(?:rgba?|hsla?|hsva?|qlineargradient|palette)\s*\(")


def _blocks(qss: str) -> List[Tuple[str, Dict[str, str]]]:
    """Parse a stylesheet into ``(selector, {property: value})`` blocks."""
    out: List[Tuple[str, Dict[str, str]]] = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", qss):
        props: Dict[str, str] = {}
        for declaration in body.split(";"):
            if ":" in declaration:
                name, value = declaration.split(":", 1)
                props[name.strip()] = value.strip()
        out.append((" ".join(selector.split()), props))
    return out


def test_sc_vi_ui_003_3_every_colour_in_the_app_stylesheet_is_a_role(combo):
    """SC-VI-UI-003-3 (second half): every colour in the one stylesheet is a role."""
    qss = build_qss(combo.mode, combo.style, scale=1)
    allowed = {value.lower() for value in _roles(combo).values()}
    found = _HEX.findall(qss)
    assert found, "the stylesheet carries no colour at all -- nothing was examined"
    stray = sorted({h for h in found if h.lower() not in allowed})
    assert not stray, f"colours that are no role of {combo.label()}: {stray}"
    assert not _FUNCTIONAL_COLOUR.search(
        qss
    ), "a functional colour (rgb(), palette() ...)"
    for _selector, props in _blocks(qss):
        for name, value in props.items():
            if "color" in name or name == "background":
                words = [w for w in re.split(r"[\s,]+", value) if w]
                for word in words:
                    assert (
                        word.startswith("#")
                        or word.startswith("url(")
                        or word in {"transparent", "none"}
                    ), f"{name}: {value!r} names a colour that is no role"


def test_sc_vi_ui_003_3_generated_art_uses_only_role_colours(combo):
    """SC-VI-UI-003-3: the art files the stylesheet loads contain role colours only."""
    allowed = {_rgb(combo, role) for role in _roles(combo)}
    templates = style_catalog.template_set(combo.style).templates
    assert templates, "no templates examined"
    art = art_set(combo.style, combo.mode, 2)
    examined = 0
    for name in sorted(templates):
        image = QImage(str(art.path(name)))
        assert not image.isNull(), name
        data = image_array(image)
        opaque = data[data[..., 3] == 255][:, :3]
        assert (data[..., 3][data[..., 3] != 255] == 0).all(), f"{name}: partial alpha"
        colours = {tuple(int(v) for v in px) for px in np.unique(opaque, axis=0)}
        assert (
            colours <= allowed
        ), f"{name}: off-role colours {sorted(colours - allowed)}"
        examined += 1
    print(f"{combo.label()}: {examined} art files examined at scale 2")


def _widgets_with_stylesheet(root: QWidget) -> List[str]:
    found = [
        f"{type(w).__name__}:{w.objectName() or w.accessibleName()}"
        for w in root.findChildren(QWidget)
        if w.styleSheet()
    ]
    if root.styleSheet():
        found.append(type(root).__name__)
    return found


# --------------------------------------------------------------------------- #
# The stylesheet contract (ADR-0069 decision 2, plan 3.5, test-contract list) #
# --------------------------------------------------------------------------- #


def test_stylesheet_equals_build_qss_at_the_art_scale(combo, qapp):
    """The one app stylesheet IS ``build_qss(mode, style, scale=art_scale())``.

    Exact equality, no concatenated sheet, no per-window sheet (K-7, NFR-5): the
    contract that replaced ``app.styleSheet() == build_qss(mode)``.
    """
    apply_theme(qapp, combo.mode, combo.style)
    scale = art_scale()
    assert scale >= 1
    assert qapp.styleSheet() == build_qss(combo.mode, combo.style, scale=scale)
    assert qapp.styleSheet().count("QMainWindow, QWidget {") == 1, "not ONE sheet"


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_a_pinned_scale_is_what_the_application_shows(combo, qapp, scale):
    """``apply_theme(..., scale=S)`` applies exactly ``build_qss(..., scale=S)``."""
    apply_theme(qapp, combo.mode, combo.style, scale=scale)
    assert qapp.styleSheet() == build_qss(combo.mode, combo.style, scale=scale)
    apply_theme(qapp, combo.mode, combo.style)
    assert qapp.styleSheet() == build_qss(combo.mode, combo.style, scale=art_scale())


def test_build_qss_is_deterministic_and_each_combination_differs(qapp):
    """Same arguments, same sheet; different combinations, different sheets."""
    sheets = {c: build_qss(c.mode, c.style, scale=1) for c in COMBOS}
    for c in COMBOS:
        assert build_qss(c.mode, c.style, scale=1) == sheets[c]
    assert len(set(sheets.values())) == len(sheets), "two combinations share a sheet"
    for style in available_styles():
        assert sheets[Combo(style, THEME_LIGHT)] != sheets[Combo(style, THEME_DARK)]


class _FakeScreen:
    def __init__(self, ratio: float) -> None:
        self._ratio = ratio

    def devicePixelRatio(self) -> float:
        return self._ratio


@pytest.mark.parametrize(
    "ratios, expected",
    [
        ([], 1),
        ([1.0], 1),
        ([1.0, 1.0], 1),
        ([1.0, 2.0], 2),
        ([2.0, 1.0], 2),
        ([1.5], 2),
        ([2.0000000001], 2),
        ([1.0, 2.5, 2.0], 3),
        ([3.0], 3),
        ([0.75], 1),
    ],
)
def test_art_scale_is_the_highest_whole_number_ratio_among_screens(
    monkeypatch, ratios, expected
):
    """``art_scale()`` = max over screens of ceil(DPR), >= 1, 1 with no screen."""
    screens = [_FakeScreen(r) for r in ratios]
    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: screens))
    assert art_scale() == expected


@pytest.mark.parametrize("scale", [1, 2])
def test_stylesheet_names_no_font_family_or_size_and_one_font_weight(combo, scale):
    """No ``font-family``, no ``font-size``; the ONLY font declaration is a weight.

    ``QDockWidget { font-weight: bold; }`` (T040 item 3, spec A-1): a weight is
    not a family or a size, so the retained portability assertions stand.
    """
    qss = build_qss(combo.mode, combo.style, scale=scale)
    lowered = qss.lower()
    assert "font-family" not in lowered
    assert "font-size" not in lowered
    assert re.search(r"(?<![\w-])font\s*:", lowered) is None, "the font shorthand"
    declared = [
        (selector, name, value)
        for selector, props in _blocks(qss)
        for name, value in props.items()
        if name.startswith("font")
    ]
    assert declared == [("QDockWidget", "font-weight", "bold")], declared


def test_stylesheet_has_no_focus_rule_and_uses_logical_pixels_only(combo):
    """No ``:focus`` rule (the ring is an overlay), ``px`` units, no ``pt``."""
    qss = build_qss(combo.mode, combo.style, scale=2)
    assert ":focus" not in qss
    assert "px" in qss
    assert re.search(r"\d\s*pt\b", qss) is None
    assert (
        "@2x" not in qss and "@3x" not in qss
    ), "per-device art variants are withdrawn"


_URL = re.compile(r"url\((.*?)\)")


def test_art_urls_are_quoted_forward_slash_paths_to_existing_png_files(combo):
    """``url("...")``: quoted, forward slashes, an existing PNG under the art root."""
    qss = build_qss(combo.mode, combo.style, scale=2)
    arguments = _URL.findall(qss)
    assert arguments, "the stylesheet references no art -- nothing examined"
    root = art_root().resolve()
    for argument in arguments:
        assert argument.startswith('"') and argument.endswith('"'), argument
        path = argument[1:-1]
        assert "\\" not in path and not path.startswith("file:"), path
        assert "%" not in Path(path).name
        resolved = Path(path)
        assert resolved.is_file(), path
        assert resolved.suffix == ".png"
        assert root in resolved.resolve().parents, f"{path} is outside {root}"
    print(f"{combo.label()}: {len(arguments)} url() references examined")


_BORDER_IMAGE = re.compile(
    r'border-image:\s*url\("([^"]+)"\)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+repeat\s+repeat;'
    r"\s*border-width:\s*(\d+)px\s+(\d+)px\s+(\d+)px\s+(\d+)px;"
)


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_border_width_is_the_slice_count_and_image_slices_are_slice_times_scale(
    combo, scale
):
    """ADR-0069 decision 1: ``border-width`` = slices; ``border-image`` slices = x S.

    Read back from the generated stylesheet and compared with the template data
    and with the PNG's own size: one art pixel is one logical pixel, the image
    carries S device pixels per art pixel.
    """
    qss = build_qss(combo.mode, combo.style, scale=scale)
    rules = _BORDER_IMAGE.findall(qss)
    assert rules, "no border-image rule was examined"
    for path, *numbers in rules:
        slices_image = tuple(int(n) for n in numbers[:4])
        border_width = tuple(int(n) for n in numbers[4:])
        stem = Path(path).stem
        transpose = stem.endswith("_t")
        name = stem[:-2] if transpose else stem
        template = _template(combo, name, transpose=transpose)
        s = template.slices
        expected = (s.top, s.right, s.bottom, s.left)
        assert (
            border_width == expected
        ), f"{stem}: border-width {border_width} != {expected}"
        assert slices_image == tuple(v * scale for v in expected), stem
        image = QImage(path)
        assert (image.width(), image.height()) == (
            template.grid.width * scale,
            template.grid.height * scale,
        ), f"{stem}: file is not the template at scale {scale}"
    print(f"{combo.label()} S={scale}: {len(rules)} border-image rules examined")


def test_stylesheet_carries_the_measured_t040_arrangements(combo):
    """The T040 rules (plan 5.1a items 1, 4, 5, 11) are in the one stylesheet."""
    qss = build_qss(combo.mode, combo.style, scale=1)
    by_selector = {selector: props for selector, props in _blocks(qss)}
    # item 1: no background on the dock title; transparent on the framed selectors
    assert "background" not in by_selector["QDockWidget::title"]
    assert "background-color" not in by_selector["QDockWidget::title"]
    for selector in ("QPushButton, QToolButton", "QToolBar", "QFrame#DockBody"):
        assert by_selector[selector]["background"] == "transparent", selector
    # item 5: item views carry `outline: 0`
    assert by_selector["QListView, QTreeView, QTableView"]["outline"] == "0"
    # item 4: scroll bar V2 only -- the track on ::add-page / ::sub-page, none on the bar
    assert "border-image" not in by_selector["QScrollBar:vertical"]
    assert "border-image" not in by_selector["QScrollBar:horizontal"]
    assert (
        "border-image"
        in by_selector["QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical"]
    )
    handle = by_selector["QSlider::handle:horizontal"]
    assert "height" not in handle, "a declared handle height makes Qt scale (blur) it"
    assert handle["width"].endswith("px") and handle["margin"].startswith("-")
    embedded = by_selector[
        "QSpinBox QLineEdit, QDoubleSpinBox QLineEdit, QComboBox QLineEdit"
    ]
    assert embedded["border"] == "none"
    # the tooltip background is a role, never Qt's own
    assert (
        by_selector["QToolTip"]["background-color"].lower()
        == _roles(combo)["hover"].lower()
    )


# --------------------------------------------------------------------------- #
# Keyboard focus: a rendered overlay, not a stylesheet rule                   #
# (REQ-VI-UI-005, SC-VI-UI-005-1..4, spec A-4, ADR-0069 decision 5)           #
# --------------------------------------------------------------------------- #


def _tab_bar() -> QTabBar:
    bar = QTabBar()
    for title in ("One", "Two", "Three"):
        bar.addTab(title)
    return bar


def _list_widget() -> QListWidget:
    widget = QListWidget()
    widget.addItems(["alpha", "beta", "gamma"])
    widget.setMinimumSize(140, 90)
    return widget


def _tree_widget() -> QTreeWidget:
    widget = QTreeWidget()
    widget.setHeaderLabels(["Name", "Kind"])
    widget.setMinimumSize(160, 100)
    return widget


def _table_widget() -> QTableWidget:
    widget = QTableWidget(3, 2)
    widget.setMinimumSize(160, 100)
    return widget


def _combo() -> QComboBox:
    widget = QComboBox()
    widget.addItems(["one", "two"])
    return widget


def _tool_button() -> QToolButton:
    widget = QToolButton()
    widget.setText("Tool")
    return widget


def _slider() -> QSlider:
    widget = QSlider(Qt.Orientation.Horizontal)
    widget.setMinimumWidth(120)
    widget.setValue(50)
    return widget


#: Every framed, keyboard-focusable control class of REQ-VI-UI-009 (the ring is
#: drawn for these); a name -> factory table so each class is its own test.
FOCUS_KINDS = {
    "push_button": lambda: QPushButton("Button"),
    "tool_button": _tool_button,
    "line_edit": lambda: QLineEdit("text"),
    "spin_box": QSpinBox,
    "double_spin_box": QDoubleSpinBox,
    "combo_box": _combo,
    "check_box": lambda: QCheckBox("check"),
    "slider": _slider,
    "tab_bar": _tab_bar,
    "list_widget": _list_widget,
    "tree_widget": _tree_widget,
    "table_widget": _table_widget,
}


def _host(qtbot, *controls: QWidget) -> QWidget:
    """Show ``controls`` stacked in a plain top-level window and return it."""
    window = QWidget()
    layout = QVBoxLayout(window)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(10)
    for control in controls:
        layout.addWidget(control)
        # qtbot keeps only a weak reference to the window: tie its life to the
        # controls the test holds, or the window is collected under them.
        control._host_window = window  # type: ignore[attr-defined]
    window.setFixedWidth(260)
    return _show(qtbot, window)


@pytest.mark.parametrize("kind", sorted(FOCUS_KINDS))
def test_sc_vi_ui_005_1_focus_ring_is_rendered_on_every_framed_control(
    qtbot, combo, kind
):
    """SC-VI-UI-005-1 / spec A-4: focus-role pixels appear on focus, only then.

    The rendered replacement of the stylesheet-substring proxy, run for each
    framed control class in every combination: 0 focus-colour pixels unfocused,
    more than 0 focused, 0 again after focus-out, examined pixels non-zero.
    """
    control = FOCUS_KINDS[kind]()
    _host(qtbot, control)
    evidence = assert_focus_rendered(qtbot, control, combo.mode, combo.style)
    print(evidence.describe())


def test_focus_helper_fails_on_a_control_without_a_ring(qtbot, combo):
    """Control for the shared helper: a control that gets no overlay FAILS it.

    A plain focusable label is not one of the framed classes, so the filter adds
    no ring. The helper must report that, not pass it -- the case the withdrawn
    ``":focus" in styleSheet()`` proxy could not see.
    """
    label = QLabel("not a framed control")
    label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    _host(qtbot, label)
    evidence = measure_focus(qtbot, label, combo.mode, combo.style)
    assert evidence.examined > 0 and evidence.focused_px == 0, evidence.describe()
    with pytest.raises(AssertionError, match="no focus ring is drawn on focus"):
        assert_focus_rendered(qtbot, label, combo.mode, combo.style)


def test_a_window_of_controls_shows_no_focus_colour_until_one_is_focused(qtbot, combo):
    """No control carries the focus colour of its own: only the ring does."""
    controls = [FOCUS_KINDS[k]() for k in ("push_button", "line_edit", "check_box")]
    window = _host(qtbot, *controls)
    reveal(qtbot, window)
    _unfocus(window)
    rgb = focus_pixel_rgb(combo.mode, combo.style)
    image = grab_image(window)
    assert image.width() * image.height() > 0
    assert count_colour_pixels(image, rgb) == 0
    controls[1].setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    assert count_colour_pixels(grab_image(window), rgb) > 0


def test_sc_vi_ui_005_1_focus_contrast_against_every_touched_role(combo):
    """SC-VI-UI-005-1 / REQ-VI-UI-004: the ring is >= 3:1 against each role it touches.

    The touched roles are DERIVED from the templates (the ring composed over every
    framed control in every state on each ground), never declared by hand; the
    pair list is printed and must not be empty.
    """
    touched = theme_art.focus_touch_roles(style_catalog.template_set(combo.style))
    assert touched, "the ring touches nothing -- an empty derivation must not pass"
    roles = _roles(combo)
    worst = None
    for role in touched:
        ratio = contrast_ratio(roles["focus"], roles[role])
        assert ratio >= FOCUS_MIN_RATIO, (
            f"{combo.label()}: focus {roles['focus']} on {role} {roles[role]} "
            f"= {ratio:.2f}:1 (< {FOCUS_MIN_RATIO}:1)"
        )
        worst = ratio if worst is None else min(worst, ratio)
    print(f"{combo.label()}: {len(touched)} derived focus pairs, worst {worst:.2f}:1")


def test_sc_vi_ui_005_1_the_dark_ring_no_longer_fails_background_or_panel(combo):
    """SC-VI-UI-005-1: not the old 2.88:1 against the background or 2.16:1 on a panel."""
    roles = _roles(combo)
    for ground in ("background", "surface"):
        ratio = contrast_ratio(roles["focus"], roles[ground])
        assert (
            ratio >= FOCUS_MIN_RATIO
        ), f"{combo.label()}: focus on {ground} {ratio:.2f}:1"
        assert round(ratio, 2) not in (2.88, 2.16)


def _neighbour_colours(widget: QWidget, c: Combo) -> Tuple[int, set]:
    """Return ``(focus px, {RGB colours 4-adjacent to the ring})`` of ``widget`` focused."""
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    image = grab_image(widget)
    rgb = focus_pixel_rgb(c.mode, c.style)
    return count_colour_pixels(image, rgb), distinct_neighbours(image, rgb)


@pytest.mark.parametrize(
    "kind", ["push_button", "tool_button", "line_edit", "spin_box"]
)
def test_sc_vi_ui_004_the_rendered_ring_only_touches_gated_colours(qtbot, combo, kind):
    """REQ-VI-UI-004 (third bullet), RENDERED: each colour the ring touches is gated.

    Every colour found 4-adjacent to a ring pixel in the real grab must be one the
    derived pair list covers (the touched roles plus the two grounds), and each of
    them must be >= 3:1 against the ring. A colour outside that set would be an
    ungated pair on screen.
    """
    control = FOCUS_KINDS[kind]()
    _host(qtbot, control)
    reveal(qtbot, control)
    _unfocus(control)
    focus_px, neighbours = _neighbour_colours(control, combo)
    assert focus_px > 0 and neighbours, "nothing was examined"
    touched = set(theme_art.focus_touch_roles(style_catalog.template_set(combo.style)))
    gated = {_rgb(combo, r) for r in touched | set(theme_art.DEFAULT_FOCUS_GROUNDS)}
    ring = _hex(_rgb(combo, "focus"))
    for colour in neighbours:
        assert colour in gated, f"{_hex(colour)} touches the ring but is no gated role"
        ratio = contrast_ratio(ring, _hex(colour))
        assert ratio >= FOCUS_MIN_RATIO, f"{ring} on {_hex(colour)} = {ratio:.2f}:1"
    print(f"{combo.label()} {kind}: {len(neighbours)} touched colours, all gated")


def _fill_count(widget: QWidget, c: Combo, role: str) -> int:
    return count_colour_pixels(grab_image(widget), _packed(_rgb(c, role)))


def _hover(widget: QWidget) -> None:
    """Put the pointer over ``widget``, entering from outside so Qt sees an enter.

    A move to a point the platform already considers current delivers no enter
    event (the offscreen cursor outlives the previous test's window), so the
    pointer is first moved off the widget.
    """
    QTest.mouseMove(widget, QPoint(-6, -6))
    _settle()
    QTest.mouseMove(widget, QPoint(widget.width() // 2, widget.height() // 2))
    _settle()
    assert widget.underMouse(), "the pointer is not over the widget"


def test_sc_vi_ui_005_2_focus_stays_while_hovered_and_pressed_and_the_state_shows(
    qtbot, combo
):
    """SC-VI-UI-005-2: focus-role pixels persist, and the hover then pressed fill shows.

    A focused push button is hovered, then pressed: the ring is there throughout,
    and the count of ``hover`` (then ``pressed``) fill pixels equals the unfocused
    count of the same state -- the ring hides nothing of the state beneath it.
    (Focus is gained AFTER the state is set: a button's focus-out ends a press.)
    """
    button = QPushButton("")
    button.setFixedHeight(28)
    _host(qtbot, button)
    reveal(qtbot, button)
    rgb = focus_pixel_rgb(combo.mode, combo.style)

    def measure(role: str) -> Tuple[int, int, int]:
        assert not button.hasFocus()
        unfocused_fill = _fill_count(button, combo, role)
        button.setFocus(Qt.FocusReason.TabFocusReason)
        _settle()
        image = grab_image(button)
        return (
            unfocused_fill,
            count_colour_pixels(image, rgb),
            count_colour_pixels(image, _packed(_rgb(combo, role))),
        )

    _unfocus(button)
    _hover(button)
    fill, ring_px, fill_focused = measure("hover")
    assert fill > 0, "the hover fill is not drawn at all"
    assert ring_px > 0, "no ring on the hovered, focused button"
    assert fill_focused == fill, "the ring hid part of the hover fill"

    _unfocus(button)
    button.setDown(True)
    _settle()
    assert button.isDown()
    fill, ring_px, fill_focused = measure("pressed")
    assert fill > 0, "the pressed fill is not drawn at all"
    assert ring_px > 0, "no ring on the pressed, focused button"
    assert fill_focused == fill, "the ring hid part of the pressed fill"
    button.setDown(False)


def test_sc_vi_ui_005_3_a_focused_checked_button_keeps_focus_and_the_checked_cue(
    qtbot, combo
):
    """SC-VI-UI-005-3: focus-role pixels and the checked fill + cue are both present."""
    button = QPushButton("")
    button.setCheckable(True)
    button.setChecked(True)
    button.setFixedHeight(28)
    _host(qtbot, button)
    reveal(qtbot, button)
    _unfocus(button)
    before = grab_image(button)
    fill = _packed(_rgb(combo, "accent"))
    cue = _packed(_rgb(combo, "accent_text"))
    # The cue ring is inside the focus ring (depth 3, the ring is 2 px). A role
    # colour can also be a frame colour (Washi Dark: accent_text == frame_hi), so
    # the cue is counted only INSIDE the ring's own depth, where nothing else is.
    depth = style_catalog.template_set(combo.style).get("focus_ring").slices.left
    inner = QRect(depth, depth, button.width() - 2 * depth, button.height() - 2 * depth)
    cue_before = count_colour_pixels(before.copy(inner), cue)
    assert count_colour_pixels(before, fill) > 0
    assert cue_before > 0, "no cue is drawn on the checked button"
    button.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    after = grab_image(button)
    assert count_colour_pixels(after, focus_pixel_rgb(combo.mode, combo.style)) > 0
    assert count_colour_pixels(after, fill) == count_colour_pixels(before, fill)
    assert (
        count_colour_pixels(after.copy(inner), cue) == cue_before
    ), "the ring hid the cue"


def test_sc_vi_ui_005_4_focus_moves_by_tab_and_moves_nothing(qtbot, combo):
    """SC-VI-UI-005-4: after Tab the first shows no ring, the second does; no geometry change."""
    first, second = QPushButton("First"), QPushButton("Second")
    window = _host(qtbot, first, second)
    reveal(qtbot, window)
    rgb = focus_pixel_rgb(combo.mode, combo.style)
    _unfocus(window)
    first.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    geometry = (first.geometry(), second.geometry())
    assert count_colour_pixels(grab_image(first), rgb) > 0
    assert count_colour_pixels(grab_image(second), rgb) == 0
    QTest.keyClick(window, Qt.Key.Key_Tab)
    _settle()
    assert second.hasFocus()
    assert (
        count_colour_pixels(grab_image(first), rgb) == 0
    ), "the first still shows a ring"
    assert count_colour_pixels(grab_image(second), rgb) > 0, "the second shows no ring"
    assert (
        first.geometry(),
        second.geometry(),
    ) == geometry, "focus moved or resized a control"


def _tab_rects(bar: QTabBar) -> List[Tuple[int, int, int, int]]:
    return [
        (
            bar.tabRect(i).x(),
            bar.tabRect(i).y(),
            bar.tabRect(i).width(),
            bar.tabRect(i).height(),
        )
        for i in range(bar.count())
    ]


def _ring_px_in(bar: QTabBar, index: int, rgb: int) -> int:
    rect = bar.tabRect(index)
    image = grab_image(bar).copy(rect)
    return count_colour_pixels(image, rgb)


def test_tab_bar_ring_follows_the_current_tab_after_arrow_keys(qtbot, combo):
    """T040 item 5: the ring is refitted to the current tab on ``currentChanged``.

    A tab bar gets one FocusIn per focus gain and none when the arrow keys move
    the current tab, so the refit is what keeps the ring on the current tab.
    """
    bar = _tab_bar()
    _host(qtbot, bar)
    reveal(qtbot, bar)
    rgb = focus_pixel_rgb(combo.mode, combo.style)
    _unfocus(bar)
    bar.setCurrentIndex(0)
    bar.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    assert _ring_px_in(bar, 0, rgb) > 0
    QTest.keyClick(bar, Qt.Key.Key_Right)
    _settle()
    assert bar.currentIndex() == 1
    assert _ring_px_in(bar, 1, rgb) > 0, "the ring did not follow to the current tab"
    assert _ring_px_in(bar, 0, rgb) == 0, "the ring stayed on the previous tab"
    QTest.keyClick(bar, Qt.Key.Key_Right)
    _settle()
    assert bar.currentIndex() == 2 and _ring_px_in(bar, 2, rgb) > 0
    assert _ring_px_in(bar, 1, rgb) == 0


def test_tab_bar_control_without_the_refit_shows_no_ring_on_the_current_tab(
    qtbot, combo
):
    """Control for the refit test: with ``currentChanged`` disconnected it FAILS the check.

    T040 measured 0 ring pixels on the current tab with the refit disconnected;
    this reproduces it, so the test above is known to be able to see the defect.
    """
    bar = _tab_bar()
    _host(qtbot, bar)
    reveal(qtbot, bar)
    rgb = focus_pixel_rgb(combo.mode, combo.style)
    _unfocus(bar)
    bar.setCurrentIndex(0)
    bar.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    chrome = pixel_chrome.chrome_filter(QApplication.instance())
    bar.currentChanged.disconnect(chrome._on_tab_changed)
    QTest.keyClick(bar, Qt.Key.Key_Right)
    _settle()
    assert bar.currentIndex() == 1
    assert _ring_px_in(bar, 1, rgb) == 0, "the control did not reproduce the defect"
    assert _ring_px_in(bar, 0, rgb) > 0


def _off_palette_pixels(widget: QWidget, c: Combo) -> int:
    allowed = np.array(sorted({_rgb(c, role) for role in _roles(c)}), dtype=np.uint8)
    data = image_array(grab_image(widget))
    rgb = data[..., :3].reshape(-1, 3)
    known = np.zeros(len(rgb), dtype=bool)
    for colour in allowed:
        known |= (rgb == colour).all(axis=1)
    return int((~known).sum())


def _blank_list() -> QListWidget:
    widget = QListWidget()
    for _ in range(3):
        widget.addItem("")
    widget.setMinimumSize(140, 90)
    return widget


def test_item_view_focus_adds_no_off_palette_pixels_with_outline_zero(qtbot, combo):
    """T040 item 5: item views carry ``outline: 0`` so Qt's own focus rect adds nothing.

    A focused list (a current row, blank items so no glyph is drawn) holds
    0 pixels outside the role palette.
    """
    widget = _blank_list()
    _host(qtbot, widget)
    reveal(qtbot, widget)
    widget.setCurrentRow(1)
    _unfocus(widget)
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    assert (
        count_colour_pixels(
            grab_image(widget), focus_pixel_rgb(combo.mode, combo.style)
        )
        > 0
    )
    assert _off_palette_pixels(widget, combo) == 0


def test_item_view_control_without_outline_zero_adds_off_palette_pixels(
    qtbot, combo, qapp
):
    """Control for the test above: strip ``outline: 0`` and Qt's focus rect appears.

    The same list under the same sheet minus that one declaration shows
    off-palette pixels -- the measurement can see the defect it guards.
    """
    widget = _blank_list()
    _host(qtbot, widget)
    qapp.setStyleSheet(
        build_qss(combo.mode, combo.style, scale=art_scale()).replace("outline: 0;", "")
    )
    try:
        reveal(qtbot, widget)
        widget.setCurrentRow(1)
        _unfocus(widget)
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        _settle()
        assert (
            _off_palette_pixels(widget, combo) > 0
        ), "no off-palette pixel without outline: 0"
    finally:
        apply_theme(qapp, combo.mode, combo.style)


# --------------------------------------------------------------------------- #
# Selected and checked states are not told apart by colour alone              #
# (REQ-VI-UI-006, SC-VI-UI-006-1/-2)                                          #
# --------------------------------------------------------------------------- #

#: accent / surface fill contrast the spec quotes for the combinations whose
#: selected fill alone fails the 3:1 component floor (spec REQ-VI-UI-006).
_QUOTED_FILL_CONTRAST = {
    ("washi-kintsugi", THEME_LIGHT): 1.90,
    ("washi-kintsugi", THEME_DARK): 2.79,
    ("edo-night", THEME_LIGHT): 1.57,
    ("arcade-kikko", THEME_LIGHT): 1.62,
    ("arcade-kikko", THEME_DARK): 2.52,
}


def _pixel_hex(image: np.ndarray, x: int, y: int) -> str:
    return _hex(tuple(int(v) for v in image[y, x, :3]))


def _distinct_from_fill(
    image: np.ndarray, rect: Tuple[int, int, int, int], fill: str
) -> List[str]:
    """Return the colours inside ``rect`` (x, y, w, h) other than ``fill`` itself."""
    x, y, w, h = rect
    region = image[y : y + h, x : x + w]
    opaque = region[region[..., 3] == 255][:, :3]
    found = {tuple(int(v) for v in px) for px in np.unique(opaque, axis=0)}
    return sorted(_hex(c) for c in found if _hex(c) != fill.lower())


def _assert_told_apart(
    c: Combo,
    what: str,
    unselected_fill: str,
    selected_fill: str,
    cue_colours: List[str],
) -> None:
    """SC-VI-UI-006-1: the fills differ by >= 3:1, or a cue >= 3:1 against the fill is drawn."""
    ratio = contrast_ratio(selected_fill, unselected_fill)
    if ratio >= COMPONENT_MIN_RATIO:
        return
    assert cue_colours, (
        f"{c.label()} {what}: selected fill {selected_fill} vs unselected "
        f"{unselected_fill} = {ratio:.2f}:1 (< {COMPONENT_MIN_RATIO}:1) and NO "
        "non-colour cue is drawn inside the selected fill"
    )
    best = max(contrast_ratio(cue, selected_fill) for cue in cue_colours)
    assert (
        best >= COMPONENT_MIN_RATIO
    ), f"{c.label()} {what}: the cue is only {best:.2f}:1 against the selected fill"


def _checked_button_pair(qtbot) -> Tuple[QPushButton, QPushButton]:
    unchecked, checked = QPushButton(""), QPushButton("")
    for button in (unchecked, checked):
        button.setCheckable(True)
        button.setFixedHeight(28)
    checked.setChecked(True)
    _host(qtbot, unchecked, checked)
    return unchecked, checked


def test_sc_vi_ui_006_1_a_checked_button_is_told_apart_without_colour_alone(
    qtbot, combo
):
    """SC-VI-UI-006-1: checked vs unchecked fill >= 3:1, or a >= 3:1 cue ring is drawn.

    Measured on the rendered buttons (their centre pixels are the two fills; every
    other opaque colour inside the checked frame ring is a cue candidate).
    """
    unchecked, checked = _checked_button_pair(qtbot)
    reveal(qtbot, checked)
    _unfocus(checked)
    plain, picked = _array(unchecked), _array(checked)
    h, w = picked.shape[:2]
    unselected_fill = _pixel_hex(plain, w // 2, h // 2)
    selected_fill = _pixel_hex(picked, w // 2, h // 2)
    assert (
        unselected_fill != selected_fill
    ), "a checked button looks like an unchecked one"
    depth = _template(combo, "button_checked").slices.left
    inner = (depth - 1, depth - 1, w - 2 * (depth - 1), h - 2 * (depth - 1))
    cues = _distinct_from_fill(picked, inner, selected_fill)
    _assert_told_apart(combo, "checked button", unselected_fill, selected_fill, cues)


def test_sc_vi_ui_006_2_the_cue_ring_matches_the_template_cell_for_cell(qtbot, combo):
    """SC-VI-UI-006-2: the checked frame IS the template, cue ring included.

    The whole text-free checked button equals ``button_checked`` composed at its
    own size and coloured from the role map (every opaque cell), and the cue ring
    -- the template's ``accent_text`` cells inside the fill -- is non-empty.
    """
    _unchecked, checked = _checked_button_pair(qtbot)
    reveal(qtbot, checked)
    _unfocus(checked)
    share, examined = frame_share(checked, combo, "button_checked", whole=True)
    assert examined > 0
    assert (
        share == 1.0
    ), f"{combo.label()}: checked button agrees with its template {share:.4f}"
    template = _template(combo, "button_checked")
    cue_cells = sum(
        1
        for row in template.grid.rows
        for symbol in row
        if template.grid.role_of(symbol) == "accent_text"
    )
    assert cue_cells > 0, "the checked template has no cue cells"


@pytest.mark.parametrize("style, mode", sorted(_QUOTED_FILL_CONTRAST))
def test_sc_vi_ui_006_2_where_the_fill_contrast_is_below_3_the_cue_is_present(
    qtbot, style, mode
):
    """SC-VI-UI-006-2: the five quoted combinations carry the non-colour cue.

    The accent/surface fill contrast is first checked against the figure the spec
    quotes (so the premise is measured, not assumed); then the selected tab and a
    checked button each show a cue. A combination the catalogue does not ship yet
    (Arcade Kikko, T024) is not in this list's run: it is reported in the module
    docstring, not skipped silently here.
    """
    c = Combo(style, mode)
    if c not in COMBOS:
        pytest.skip(f"{style} is not in the catalogue yet (T024); not examined")
    apply_theme(QApplication.instance(), mode, style)
    ratio = contrast_ratio(_roles(c)["accent"], _roles(c)["surface"])
    assert round(ratio, 2) == _QUOTED_FILL_CONTRAST[(style, mode)]
    assert ratio < COMPONENT_MIN_RATIO
    _unchecked, checked = _checked_button_pair(qtbot)
    reveal(qtbot, checked)
    _unfocus(checked)
    picked = _array(checked)
    h, w = picked.shape[:2]
    fill = _pixel_hex(picked, w // 2, h // 2)
    depth = _template(c, "button_checked").slices.left
    cues = _distinct_from_fill(
        picked, (depth - 1, depth - 1, w - 2 * (depth - 1), h - 2 * (depth - 1)), fill
    )
    assert cues, "the checked button carries no cue"


def _tab_frame_rect(
    bar: QTabBar, c: Combo, index: int, name: str
) -> Tuple[int, int, int, int]:
    """Locate tab ``index``'s frame box BY PIXELS: the rect whose band equals ``name``.

    ``tabRect`` is a layout rect (it includes the tab margin), so the frame box is
    found as the candidate of the rect trimmed on the right by 0..4 px whose ring
    agrees with the template; the search is part of the measurement.
    """
    image = _array(bar)
    rect = bar.tabRect(index)
    for trim in range(0, 5):
        w, h = rect.width() - trim, rect.height()
        crop = image[rect.y() : rect.y() + h, rect.x() : rect.x() + w]
        expected = _composed(c, name, w, h)
        share, examined = _agree(crop, expected, _band(_template(c, name), w, h))
        if examined and share == 1.0:
            return rect.x(), rect.y(), w, h
    raise AssertionError(f"tab {index}: no frame box agrees with template {name!r}")


def _blank_tab_bar() -> QTabBar:
    bar = QTabBar()
    for _ in range(3):
        bar.addTab("")
    return bar


def test_sc_vi_ui_006_the_selected_tab_is_told_apart_without_colour_alone(qtbot, combo):
    """SC-VI-UI-006-1/-2: the selected tab shows the cue where its fill alone is < 3:1."""
    bar = _blank_tab_bar()
    _host(qtbot, bar)
    reveal(qtbot, bar)
    bar.setCurrentIndex(1)
    _unfocus(bar)
    image = _array(bar)
    selected = _tab_frame_rect(bar, combo, 1, "button_checked")
    plain = _tab_frame_rect(bar, combo, 0, "button_normal")
    sx, sy, sw, sh = selected
    px, py, pw, ph = plain
    selected_fill = _pixel_hex(image, sx + sw // 2, sy + sh // 2)
    unselected_fill = _pixel_hex(image, px + pw // 2, py + ph // 2)
    assert selected_fill != unselected_fill
    cues = _distinct_from_fill(image, (sx + 1, sy + 1, sw - 2, sh - 2), selected_fill)
    _assert_told_apart(combo, "selected tab", unselected_fill, selected_fill, cues)


def test_sc_vi_ui_006_the_checked_check_box_carries_its_mark(qtbot, combo):
    """REQ-VI-UI-006: a checked check box differs from an unchecked one by a drawn mark.

    The indicator is located by pixels (the ``check_on`` / ``check_off`` sprites
    must each appear exactly once); the mark is the sprite's ``accent_text`` cells
    and is >= 3:1 against the checked fill.
    """
    off, on = QCheckBox(""), QCheckBox("")
    on.setChecked(True)
    _host(qtbot, off, on)
    reveal(qtbot, on)
    _unfocus(on)
    on_image, off_image = _array(on), _array(off)
    assert len(locate(on_image, sprite(combo, "check_on"))) == 1
    assert len(locate(off_image, sprite(combo, "check_off"))) == 1
    assert locate(on_image, sprite(combo, "check_off")) == []
    roles = _roles(combo)
    assert contrast_ratio(roles["accent_text"], roles["accent"]) >= COMPONENT_MIN_RATIO


def test_sc_vi_ui_006_2_the_selected_list_row_carries_the_cue(qtbot, combo):
    """SC-VI-UI-006-2: the selected list row carries the non-colour cue.

    The rows hold blank text, so any pixel inside the selected row that is not its
    fill is a cue; the unselected row's fill is the other operand of the 3:1 test.
    """
    widget = _blank_list()
    _host(qtbot, widget)
    reveal(qtbot, widget)
    widget.setCurrentRow(1)
    widget.clearSelection()
    widget.item(1).setSelected(True)
    _unfocus(widget)
    image = image_array(grab_image(widget.viewport()))
    selected_rect = widget.visualItemRect(widget.item(1))
    plain_rect = widget.visualItemRect(widget.item(2))
    selected_fill = _pixel_hex(
        image, selected_rect.center().x(), selected_rect.center().y()
    )
    unselected_fill = _pixel_hex(
        image, plain_rect.center().x(), plain_rect.center().y()
    )
    assert selected_fill != unselected_fill, "the selected row looks unselected"
    cues = _distinct_from_fill(
        image,
        (
            selected_rect.x(),
            selected_rect.y(),
            selected_rect.width(),
            selected_rect.height(),
        ),
        selected_fill,
    )
    _assert_told_apart(combo, "selected list row", unselected_fill, selected_fill, cues)


def test_sc_vi_ui_006_the_selected_menu_item_carries_the_cue(qtbot, combo):
    """REQ-VI-UI-006: the selected (active) menu item carries the non-colour cue."""
    menu = QMenu()
    actions = [menu.addAction("") for _ in range(3)]
    qtbot.addWidget(menu)
    menu.popup(QPoint(40, 40))
    qtbot.waitExposed(menu)
    menu.setActiveAction(actions[1])
    _settle()
    image = _array(menu)
    selected_rect = menu.actionGeometry(actions[1])
    plain_rect = menu.actionGeometry(actions[2])
    selected_fill = _pixel_hex(
        image, selected_rect.center().x(), selected_rect.center().y()
    )
    unselected_fill = _pixel_hex(
        image, plain_rect.center().x(), plain_rect.center().y()
    )
    assert selected_fill != unselected_fill, "the active menu item looks inactive"
    cues = _distinct_from_fill(
        image,
        (
            selected_rect.x(),
            selected_rect.y(),
            selected_rect.width(),
            selected_rect.height(),
        ),
        selected_fill,
    )
    _assert_told_apart(
        combo, "selected menu item", unselected_fill, selected_fill, cues
    )
    menu.close()


# --------------------------------------------------------------------------- #
# The full control set carries pixel frames (REQ-VI-UI-009, SC-VI-UI-009-1/-2)#
# --------------------------------------------------------------------------- #

_FRAME_FLOOR = 0.99


def _line_edit() -> QLineEdit:
    return QLineEdit("text")


def _text_edit():
    from PySide6.QtWidgets import QTextEdit

    widget = QTextEdit()
    widget.setMinimumSize(140, 70)
    return widget


#: Control class -> (factory, the template its own rectangle is framed with).
FRAMED_CONTROLS = {
    "push_button": (lambda: QPushButton("Button"), "button_normal"),
    "tool_button": (_tool_button, "button_normal"),
    "line_edit": (_line_edit, "field"),
    "text_edit": (_text_edit, "field"),
    "combo_box": (_combo, "field"),
    "spin_box": (QSpinBox, "field"),
    "double_spin_box": (QDoubleSpinBox, "field"),
    "list_widget": (_list_widget, "field"),
    "tree_widget": (_tree_widget, "field"),
    "table_widget": (_table_widget, "field"),
}


@pytest.mark.parametrize("kind", sorted(FRAMED_CONTROLS))
def test_sc_vi_ui_009_1_every_control_class_shows_its_pixel_frame(qtbot, combo, kind):
    """SC-VI-UI-009-1: each control's own rectangle carries its template's frame.

    The control's frame ring in the real grab is compared cell by cell with the
    template composed at the control's size and coloured from the role map; it
    must agree, and the number of cells examined is printed and non-zero.
    """
    factory, name = FRAMED_CONTROLS[kind]
    control = factory()
    _host(qtbot, control)
    reveal(qtbot, control)
    _unfocus(control)
    share, examined = frame_share(control, combo, name)
    print(f"{combo.label()} {kind}: {examined} frame cells examined, share {share:.4f}")
    assert examined > 0
    assert (
        share >= _FRAME_FLOOR
    ), f"{kind} agrees with {name!r} on {share:.4f} of its frame"


def test_frame_comparator_rejects_the_native_look(qtbot, combo, qapp):
    """Control for every frame test: the unstyled native widget scores far lower.

    With the application stylesheet removed a push button and a line edit show Qt's
    own look; the SAME comparison that passes the themed widgets must fail them.
    """
    themed = QPushButton("Button")
    plain = QLineEdit("text")
    _host(qtbot, themed, plain)
    reveal(qtbot, themed)
    _unfocus(themed)
    themed_share, themed_n = frame_share(themed, combo, "button_normal")
    assert themed_n > 0 and themed_share >= _FRAME_FLOOR
    qapp.setStyleSheet("")
    try:
        _settle()
        for widget, name in ((themed, "button_normal"), (plain, "field")):
            share, examined = frame_share(widget, combo, name)
            assert examined > 0
            assert share < 0.5, f"the native {type(widget).__name__} scored {share:.3f}"
    finally:
        apply_theme(qapp, combo.mode, combo.style)


def test_sc_vi_ui_009_2_button_states_each_render_their_own_frame(qtbot, combo):
    """SC-VI-UI-009-2: normal, hover, pressed and checked each match their own template.

    A text-free button, whole picture (frame and fill) compared with
    ``button_normal`` / ``button_hover`` / ``button_pressed`` / ``button_checked``
    composed at its size -- and the four renders are pairwise different.
    """
    button = QPushButton("")
    button.setCheckable(True)
    button.setFixedHeight(28)
    _host(qtbot, button)
    reveal(qtbot, button)
    renders: Dict[str, bytes] = {}

    def check(state: str, name: str) -> None:
        share, examined = frame_share(button, combo, name, whole=True)
        assert examined > 0
        assert (
            share == 1.0
        ), f"{combo.label()} {state}: agrees with {name!r} on {share:.4f}"
        renders[state] = _array(button).tobytes()

    _unfocus(button)
    _hover_away(button)
    check("normal", "button_normal")
    _hover(button)
    check("hover", "button_hover")
    _hover_away(button)
    button.setChecked(True)
    _settle()
    check("checked", "button_checked")
    button.setDown(True)
    _settle()
    check("pressed", "button_pressed")
    button.setDown(False)
    assert len(set(renders.values())) == len(renders), "two states look identical"


def _hover_away(widget: QWidget) -> None:
    QTest.mouseMove(widget, QPoint(-6, -6))
    _settle()


def test_sc_vi_ui_009_2_disabled_button_label_uses_the_disabled_text_role(qtbot, combo):
    """SC-VI-UI-009-2: the disabled label is drawn in ``disabled_text``, not ``text``.

    Compared with the same button enabled: the enabled label's ink is ``text``; the
    disabled label's ink is ``disabled_text`` and ``text`` is absent from it.
    """
    enabled, disabled = QPushButton("MMMM"), QPushButton("MMMM")
    disabled.setEnabled(False)
    _host(qtbot, enabled, disabled)
    reveal(qtbot, enabled)
    _unfocus(enabled)
    text, dim = _packed(_rgb(combo, "text")), _packed(_rgb(combo, "disabled_text"))
    inner = QRect(5, 5, enabled.width() - 10, enabled.height() - 10)
    enabled_inner = grab_image(enabled).copy(inner)
    disabled_inner = grab_image(disabled).copy(inner)
    assert count_colour_pixels(enabled_inner, text) > 0, "no enabled label ink examined"
    assert (
        count_colour_pixels(disabled_inner, dim) > 0
    ), "the disabled label is not drawn"
    assert count_colour_pixels(disabled_inner, text) == 0
    assert share_frame(disabled, combo) >= _FRAME_FLOOR


def share_frame(widget: QWidget, c: Combo, name: str = "button_normal") -> float:
    share, examined = frame_share(widget, c, name)
    assert examined > 0
    return share


# --------------------------------------------------------------------------- #
# Sub-controls, located BY PIXELS (T040 obligation): never QStyle.subControlRect
# --------------------------------------------------------------------------- #


def _ring_of(c: Combo, name: str, w: int, h: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(coloured template at w x h, ring mask)`` -- the interior may hold a sprite."""
    return _composed(c, name, w, h), _band(_template(c, name), w, h)


def _find_ring(
    image: np.ndarray,
    c: Combo,
    name: str,
    sizes: Sequence[Tuple[int, int]],
    *,
    transpose: bool = False,
) -> Tuple[Tuple[int, int], List[Tuple[int, int]]]:
    """Return the first ``(w, h)`` of ``sizes`` whose ring appears, and where."""
    for w, h in sizes:
        pattern = _composed(c, name, w, h, transpose=transpose)
        mask = _band(_template(c, name, transpose=transpose), w, h)
        found = locate(image, pattern, mask)
        if found:
            return (w, h), found
    return (0, 0), []


def _inside(
    point: Tuple[int, int],
    size: Tuple[int, int],
    frame: Tuple[int, int],
    fsize: Tuple[int, int],
) -> bool:
    x, y = point
    fx, fy = frame
    return (
        fx <= x
        and fy <= y
        and x + size[0] <= fx + fsize[0]
        and y + size[1] <= fy + fsize[1]
    )


def _spin_frames(
    spin: QWidget, c: Combo
) -> Tuple[np.ndarray, Tuple[int, int], List[Tuple[int, int]]]:
    image = _array(spin)
    sizes = [(w, h) for h in range(6, 13) for w in range(8, 15)]
    size, found = _find_ring(image, c, "subbutton", sizes)
    return image, size, sorted(found, key=lambda p: p[1])


def _ring_depth(c: Combo) -> int:
    """Return the focus ring's thickness in art pixels (the cells it covers)."""
    return style_catalog.template_set(c.style).get("focus_ring").slices.left


def _check_spin(spin: QWidget, c: Combo, *, focused: bool = False) -> None:
    """Assert the spin box shows its framed field, two step buttons and both arrows.

    ``focused``: the control wears its focus ring over the outermost cells of the
    field frame (a mouse press focuses it), so those cells are not compared.
    """
    share, examined = frame_share(
        spin, c, "field", skip_outer=_ring_depth(c) if focused else 0
    )
    assert examined > 0 and share >= _FRAME_FLOOR, f"field frame agrees on {share:.4f}"
    image, size, frames = _spin_frames(spin, c)
    assert size != (0, 0) and len(frames) == 2, f"step-button frames found: {frames}"
    up_xy, down_xy = frames
    up = locate(image, sprite(c, "arrow_up"))
    down = locate(image, sprite(c, "arrow_down"))
    arrow_size = sprite(c, "arrow_up").shape[1::-1]
    assert len(up) == 1 and len(down) == 1, (up, down)
    assert _inside(
        up[0], arrow_size, up_xy, size
    ), "the up arrow is not in the upper button"
    assert _inside(
        down[0], arrow_size, down_xy, size
    ), "the down arrow is not in the lower one"
    assert up_xy[1] < down_xy[1] and up_xy[0] == down_xy[0]


@pytest.mark.parametrize("spin_class", [QSpinBox, QDoubleSpinBox])
def test_sc_vi_ui_009_1_spin_box_step_buttons_are_framed_and_carry_their_arrows(
    qtbot, combo, spin_class
):
    """SC-VI-UI-009-1: a spin box shows two framed step buttons with up and down arrows.

    Located by pixels: the ``subbutton`` ring must appear exactly twice (up above
    down) at the stylesheet's size, the ``arrow_up`` sprite exactly once inside the
    upper frame and ``arrow_down`` exactly once inside the lower one.
    """
    spin = spin_class()
    _host(qtbot, spin)
    reveal(qtbot, spin)
    _unfocus(spin)
    _check_spin(spin, combo)


def _check_combo(box: QComboBox, c: Combo) -> None:
    """Assert the combo box shows its framed field and a framed drop-down with its arrow."""
    share, examined = frame_share(box, c, "field")
    assert examined > 0 and share >= _FRAME_FLOOR, f"field frame agrees on {share:.4f}"
    image = _array(box)
    sizes = [(w, h) for h in range(8, 22) for w in range(8, 15)]
    size, found = _find_ring(image, c, "subbutton", sizes)
    assert size != (0, 0) and len(found) == 1, f"drop-down frames found: {found}"
    arrows = locate(image, sprite(c, "arrow_down"))
    assert len(arrows) == 1
    assert _inside(arrows[0], sprite(c, "arrow_down").shape[1::-1], found[0], size)


def test_sc_vi_ui_009_1_combo_drop_down_is_framed_and_carries_its_arrow(qtbot, combo):
    """SC-VI-UI-009-1: a combo box shows one framed drop-down button with the down arrow."""
    box = _combo()
    _host(qtbot, box)
    reveal(qtbot, box)
    _unfocus(box)
    _check_combo(box, combo)


def _scroll_bar(orientation: Qt.Orientation) -> QScrollBar:
    bar = QScrollBar(orientation)
    bar.setRange(0, 100)
    bar.setPageStep(20)
    bar.setValue(50)
    if orientation == Qt.Orientation.Vertical:
        bar.setFixedHeight(120)
    else:
        bar.setFixedWidth(160)
    return bar


def _scroll_geometry(
    bar: QScrollBar, c: Combo
) -> Tuple[np.ndarray, bool, int, int, Tuple[int, int], Tuple[int, int]]:
    """Locate the handle by pixels: ``(image, vertical, thick, span, (hx, hy), (hw, hh))``."""
    image = _array(bar)
    vertical = bar.orientation() == Qt.Orientation.Vertical
    template = _template(c, "scroll_handle", transpose=not vertical)
    thick = image.shape[1] if vertical else image.shape[0]
    span = image.shape[0] if vertical else image.shape[1]
    s = template.slices
    start = s.top + s.bottom if vertical else s.left + s.right
    for length in range(start, span):
        w, h = (thick, length) if vertical else (length, thick)
        found = locate(
            image, _composed(c, "scroll_handle", w, h, transpose=not vertical)
        )
        if found:
            assert len(found) == 1, f"{len(found)} handle frames found"
            return image, vertical, thick, span, found[0], (w, h)
    raise AssertionError("no scroll-bar handle frame is found by pixels")


def _check_scroll(bar: QScrollBar, c: Combo) -> None:
    """Assert the handle frame and both track pages match their templates."""
    image, vertical, thick, span, (hx, hy), (hw, hh) = _scroll_geometry(bar, c)
    # The pages either side of the handle. Qt lets a page run on UNDER the handle,
    # so the page's far edge (the slice nearest the handle) is hidden: compare the
    # visible part with the page composed that much longer and cropped.
    transpose = not vertical
    s = _template(c, "scroll_track", transpose=transpose).slices
    hidden_after = s.bottom if vertical else s.right  # before-page: its trailing edge
    hidden_before = s.top if vertical else s.left  # after-page: its leading edge
    before_len = hy if vertical else hx
    after_len = span - (hy + hh if vertical else hx + hw)
    examined = 0
    for length, hidden, first in (
        (before_len, hidden_after, True),
        (after_len, hidden_before, False),
    ):
        if length <= 0:
            continue
        full = length + hidden
        w, h = (thick, full) if vertical else (full, thick)
        expected = _composed(c, "scroll_track", w, h, transpose=transpose)
        if first:
            expected = expected[:length] if vertical else expected[:, :length]
            region = image[:length] if vertical else image[:, :length]
        else:
            expected = expected[-length:] if vertical else expected[:, -length:]
            start = hy + hh if vertical else hx + hw
            region = image[start:] if vertical else image[:, start:]
        share, cells = _agree(region, expected, np.ones(region.shape[:2], dtype=bool))
        assert cells > 0 and share == 1.0, f"track page agrees on {share:.4f}"
        examined += cells
    assert examined > 0


@pytest.mark.parametrize(
    "orientation", [Qt.Orientation.Vertical, Qt.Orientation.Horizontal]
)
def test_sc_vi_ui_009_1_scroll_bar_track_and_handle_are_framed(
    qtbot, combo, orientation
):
    """SC-VI-UI-009-1: the scroll bar's handle and both track pages match their templates.

    Located by pixels: the ``scroll_handle`` frame (horizontal = transposed) is
    found exactly once at a length >= its slices; the two track pages either side of
    it equal ``scroll_track`` composed to their own rectangles, cell for cell.
    """
    bar = _scroll_bar(orientation)
    window = _host(qtbot, bar)
    window.setFixedWidth(max(window.width(), 200))
    reveal(qtbot, bar)
    _unfocus(bar)
    _check_scroll(bar, combo)


def _check_slider(slider: QSlider, c: Combo, *, focused: bool = False) -> None:
    """Assert the slider shows its handle sprite once, centred on its framed groove.

    ``focused``: the ring covers the groove's end caps, which are then not compared.
    """
    image = _array(slider)
    handles = locate(image, sprite(c, "slider_handle"))
    assert len(handles) == 1, f"handle sprite found at {handles}"
    hx, hy = handles[0]
    handle_h, handle_w = sprite(c, "slider_handle").shape[:2]
    groove_template = _template(c, "slider_groove")
    width = image.shape[1]
    found: List[Tuple[int, int]] = []
    for gh in range(groove_template.slices.top + groove_template.slices.bottom, 12):
        pattern = _composed(c, "slider_groove", width, gh)
        mask = _band(groove_template, width, gh)
        mask[:, hx : hx + handle_w] = False  # the handle is drawn over the groove
        if focused:
            depth = _ring_depth(c)
            mask[:, :depth] = False
            mask[:, width - depth :] = False
        found = [(gh, y) for (x, y) in locate(image, pattern, mask) if x == 0]
        if found:
            break
    assert found, "no groove frame is found by pixels"
    gh, gy = found[0]
    assert (
        abs((hy + handle_h / 2) - (gy + gh / 2)) <= 1
    ), "the handle is not centred on the groove"


def test_sc_vi_ui_009_1_slider_groove_and_handle_are_framed(qtbot, combo):
    """SC-VI-UI-009-1: a slider shows its groove frame and its handle sprite.

    Located by pixels: the handle sprite appears exactly once; the groove is the
    ``slider_groove`` template composed across the whole control, matched on its
    ring everywhere the handle does not cover it, at a height found by search.
    """
    slider = _slider()
    _host(qtbot, slider)
    reveal(qtbot, slider)
    _unfocus(slider)
    _check_slider(slider, combo)


def test_sc_vi_ui_009_1_check_box_indicator_sprites_follow_the_state(qtbot, combo):
    """SC-VI-UI-009-1: a check box shows ``check_off`` unchecked and ``check_on`` checked."""
    off, on = QCheckBox("x"), QCheckBox("x")
    on.setChecked(True)
    _host(qtbot, off, on)
    reveal(qtbot, on)
    _unfocus(on)
    assert len(locate(_array(off), sprite(combo, "check_off"))) == 1
    assert len(locate(_array(on), sprite(combo, "check_on"))) == 1
    assert locate(_array(off), sprite(combo, "check_on")) == []


# --- the still-unexamined surfaces (plan R-5, T040 obligation) -----------------


@pytest.mark.parametrize(
    "kind",
    ["spin_box", "double_spin_box", "combo_box", "check_box", "slider", "scroll_bar"],
)
def test_disabled_controls_keep_their_frames_and_sprites(qtbot, combo, kind):
    """R-5 (disabled sub-control states): a disabled control is still framed, not native.

    The disabled variants have no art of their own, so the enabled assertions hold
    unchanged for each of them: frame ring, step buttons and arrows, drop-down,
    indicator sprite, handle and groove, track pages.
    """
    if kind in ("spin_box", "double_spin_box"):
        control: QWidget = QSpinBox() if kind == "spin_box" else QDoubleSpinBox()
    elif kind == "combo_box":
        control = _combo()
    elif kind == "check_box":
        control = QCheckBox("x")
    elif kind == "slider":
        control = _slider()
    else:
        control = _scroll_bar(Qt.Orientation.Vertical)
    window = _host(qtbot, control)
    reveal(qtbot, window)
    control.setEnabled(False)
    _settle()
    assert not control.isEnabled()
    if kind in ("spin_box", "double_spin_box"):
        _check_spin(control, combo)
    elif kind == "combo_box":
        _check_combo(control, combo)
    elif kind == "check_box":
        assert len(locate(_array(control), sprite(combo, "check_off"))) == 1
    elif kind == "slider":
        _check_slider(control, combo)
    else:
        _check_scroll(control, combo)


def test_pressed_spin_button_stays_framed_with_its_arrow(qtbot, combo):
    """R-5 (pressed sub-control state): a pressed step button is still framed, arrow drawn.

    The up button is located BY PIXELS, pressed with a real mouse press at its
    centre, and the checks run again with the button held down.
    """
    spin = QSpinBox()
    spin.setRange(0, 1000)
    _host(qtbot, spin)
    reveal(qtbot, spin)
    _unfocus(spin)
    _image, size, frames = _spin_frames(spin, combo)
    assert len(frames) == 2
    ux, uy = frames[0]
    centre = QPoint(ux + size[0] // 2, uy + size[1] // 2)
    before = spin.value()
    QTest.mousePress(
        spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre
    )
    _settle()
    try:
        assert spin.value() == before + 1, "the press did not land on the up button"
        _check_spin(spin, combo, focused=spin.hasFocus() or spin.lineEdit().hasFocus())
    finally:
        QTest.mouseRelease(
            spin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre
        )


def test_pressed_scroll_handle_and_slider_handle_stay_framed(qtbot, combo):
    """R-5 (pressed state): a held scroll-bar handle and slider handle keep their art."""
    bar = _scroll_bar(Qt.Orientation.Vertical)
    slider = _slider()
    window = _host(qtbot, bar, slider)
    reveal(qtbot, window)
    _unfocus(window)
    _image, _v, _t, _s, (hx, hy), (hw, hh) = _scroll_geometry(bar, combo)
    centre = QPoint(hx + hw // 2, hy + hh // 2)
    QTest.mousePress(
        bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre
    )
    _settle()
    try:
        assert bar.isSliderDown(), "the press did not land on the handle"
        _check_scroll(bar, combo)
    finally:
        QTest.mouseRelease(
            bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre
        )
    handles = locate(_array(slider), sprite(combo, "slider_handle"))
    assert len(handles) == 1
    hsprite = sprite(combo, "slider_handle").shape
    point = QPoint(handles[0][0] + hsprite[1] // 2, handles[0][1] + hsprite[0] // 2)
    QTest.mousePress(
        slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    _settle()
    try:
        assert slider.isSliderDown(), "the press did not land on the slider handle"
        _check_slider(slider, combo, focused=slider.hasFocus())
    finally:
        QTest.mouseRelease(
            slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
        )


# --------------------------------------------------------------------------- #
# Popups, dialogs, headings (REQ-VI-UI-008, SC-VI-UI-008-1/-2)                #
# --------------------------------------------------------------------------- #


def _corners_opaque(image: np.ndarray) -> Tuple[int, int, int, int]:
    return (
        int(image[0, 0, 3]),
        int(image[0, -1, 3]),
        int(image[-1, 0, 3]),
        int(image[-1, -1, 3]),
    )


def test_sc_vi_ui_008_2_a_menu_is_framed_and_has_square_outer_corners(qtbot, combo):
    """SC-VI-UI-008-2: a menu carries the ``menu`` frame and its four corners are opaque.

    Square corners are measured, not assumed: every corner pixel of the popup is
    opaque (no notch showing a translucent or native backing), no translucent
    attribute is set, and the frame ring agrees with the template.
    """
    menu = QMenu()
    for text in ("One", "Two", "Three"):
        menu.addAction(text)
    qtbot.addWidget(menu)
    menu.popup(QPoint(40, 40))
    qtbot.waitExposed(menu)
    _settle()
    try:
        assert not menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        image = _array(menu)
        assert _corners_opaque(image) == (255, 255, 255, 255)
        share, examined = frame_share(menu, combo, "menu")
        assert (
            examined > 0 and share >= _FRAME_FLOOR
        ), f"menu frame agrees on {share:.4f}"
    finally:
        menu.close()


def _tooltip_window() -> Optional[QWidget]:
    for widget in QApplication.topLevelWidgets():
        if widget.metaObject().className() == "QTipLabel" and widget.isVisible():
            return widget
    return None


def test_sc_vi_ui_008_2_the_tooltip_is_square_framed_and_a_role_colour(qtbot, combo):
    """SC-VI-UI-008-2: the tooltip background is a role colour (not ``#EFEFEF``), square, framed.

    The tooltip's fill is the ``hover`` role; Qt's own unthemed ``#EFEFEF`` appears
    nowhere in it; the four corners are opaque and the ``tooltip`` frame agrees.
    """
    host = QPushButton("host")
    _host(qtbot, host)
    reveal(qtbot, host)
    QToolTip.showText(host.mapToGlobal(QPoint(10, 10)), "Tooltip text", host)
    qtbot.waitUntil(lambda: _tooltip_window() is not None, timeout=2000)
    tip = _tooltip_window()
    assert tip is not None
    try:
        _settle()
        image = _array(tip)
        assert _corners_opaque(image) == (255, 255, 255, 255)
        depth = _template(combo, "tooltip").slices.left
        fill = tuple(int(v) for v in image[depth, depth, :3])
        assert fill == _rgb(
            combo, "hover"
        ), f"tooltip fill {_hex(fill)} is not the hover role"
        assert (
            not (image[..., :3] == np.array([239, 239, 239], dtype=np.uint8))
            .all(axis=-1)
            .any()
        )
        share, examined = frame_share(tip, combo, "tooltip")
        assert (
            examined > 0 and share >= _FRAME_FLOOR
        ), f"tooltip frame agrees on {share:.4f}"
    finally:
        QToolTip.hideText()


def test_sc_vi_ui_008_2_the_combo_popup_list_carries_the_menu_frame_and_square_corners(
    qtbot, combo
):
    """SC-VI-UI-008-2 / R-5: the combo box's list shows the ``menu`` frame, square corners.

    One of the surfaces plan R-5 left unexamined: the popup list of a combo box.
    """
    box = _combo()
    _host(qtbot, box)
    reveal(qtbot, box)
    box.showPopup()
    view = box.view()
    qtbot.waitUntil(view.isVisible, timeout=2000)
    _settle()
    try:
        share, examined = frame_share(view, combo, "menu")
        assert (
            examined > 0 and share >= _FRAME_FLOOR
        ), f"popup list frame agrees on {share:.4f}"
        container = view.window()
        assert not container.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert _corners_opaque(_array(container)) == (255, 255, 255, 255)
    finally:
        box.hidePopup()


def _blank_dialog(qtbot, *, heading: Optional[str] = None) -> QDialog:
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    if heading is not None:
        label = QLabel(heading)
        label.setObjectName("dialogHeading")
        layout.addWidget(label)
    blank = QWidget()
    blank.setFixedSize(180, 80)
    layout.addWidget(blank)
    dialog._blank = blank  # type: ignore[attr-defined]
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    _settle()
    return dialog


def test_sc_vi_ui_008_1_a_dialog_keeps_its_native_bar_shows_its_frame_and_has_no_band(
    qtbot, combo
):
    """SC-VI-UI-008-1: framed inside the window, native title bar kept, no empty band.

    * the pixel frame is inside the dialog window: its ring equals ``dialog``;
    * the title bar stays the operating system's: the dialog is not frameless, not
      translucent (offscreen draws no native bar, so the contract tested is that
      nothing in the product replaces it);
    * no empty title band: everything inside the frame ring of a dialog with no
      heading is the one ``background`` colour, from the top ring down to the
      first control.
    """
    dialog = _blank_dialog(qtbot)
    _unfocus(dialog)
    flags = dialog.windowFlags()
    assert not flags & Qt.WindowType.FramelessWindowHint
    assert not dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    share, examined = frame_share(dialog, combo, "dialog")
    assert examined > 0 and share == 1.0, f"dialog frame agrees on {share:.4f}"
    image = _array(dialog)
    s = _template(combo, "dialog").slices
    h, w = image.shape[:2]
    top_zone = image[s.top : s.top + 8, s.left : w - s.right, :3]
    ground = np.array(_rgb(combo, "background"), dtype=np.uint8)
    assert (
        top_zone == ground
    ).all(), "something other than the ground lies under the top ring"
    interior = image[s.top : h - s.bottom, s.left : w - s.right, :3]
    colours = {
        tuple(int(v) for v in px) for px in np.unique(interior.reshape(-1, 3), axis=0)
    }
    assert colours == {
        _rgb(combo, "background")
    }, "the dialog interior is not one ground"


def test_sc_vi_ui_008_1_a_real_dialog_is_framed_without_an_empty_band(qtbot, combo):
    """SC-VI-UI-008-1: the app's own New Document dialog carries the frame and no band."""
    from pixelart_creator.ui.new_document_dialog import New_Document_Dialog

    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    _unfocus(dialog)
    share, examined = frame_share(dialog, combo, "dialog")
    assert examined > 0 and share == 1.0, f"dialog frame agrees on {share:.4f}"
    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    image = _array(dialog)
    s = _template(combo, "dialog").slices
    h, w = image.shape[:2]
    ground = np.array(_rgb(combo, "background"), dtype=np.uint8)
    # the first rows under the top ring, across the whole inner width, are ground
    zone = image[s.top : s.top + 3, s.left : w - s.right, :3]
    assert (
        zone == ground
    ).all(), "an empty band (not the ground) sits under the top ring"


def test_dialog_heading_row_takes_the_heading_frame(qtbot, combo):
    """A label named ``dialogHeading`` (the name plan 5.1 defines) carries the ``heading`` frame.

    The heading frame (ring 1/1/2/1) is drawn only on that object name; the object
    name is the one plan 5.1 and ``ui/theme.py`` use. (The shipped template data
    names it differently: see ``test_template_hints_name_selectors_the_stylesheet_has``.)
    """
    dialog = _blank_dialog(qtbot, heading="Heading")
    heading = dialog.findChild(QLabel, "dialogHeading")
    assert heading is not None
    share, examined = frame_share(heading, combo, "heading")
    assert examined > 0 and share == 1.0, f"heading frame agrees on {share:.4f}"


_HINT_SELECTOR = re.compile(r"\b(Q[A-Za-z]+)#([A-Za-z0-9_]+)")


def test_template_hints_name_selectors_the_stylesheet_has(combo):
    """Every ``Class#ObjectName`` a template's ``qss_hint`` names is a selector in the stylesheet.

    Reconciles the dialog heading's object name across its three sources. The
    plan and ``ui/theme.py`` say ``QLabel#dialogHeading``; the committed
    ``templates.json`` hint says ``QLabel#DialogHeading``. A hint that names a
    selector no stylesheet rule carries misleads whoever wires the next dialog.
    """
    qss = build_qss(combo.mode, combo.style, scale=1)
    selectors = {sel for sel, _ in _blocks(qss)}
    flat = " ".join(selectors).replace(",", " ")
    examined = 0
    missing: List[str] = []
    for name, template in style_catalog.template_set(combo.style).templates.items():
        hint = getattr(template, "qss_hint", "") or ""
        for cls, obj in _HINT_SELECTOR.findall(hint):
            examined += 1
            if f"{cls}#{obj}" not in flat:
                missing.append(f"{name}: {cls}#{obj}")
    assert examined > 0, "no hint named an object-name selector -- nothing was examined"
    assert not missing, f"qss_hint selectors absent from the stylesheet: {missing}"


# --------------------------------------------------------------------------- #
# Tree and table headers (plan R-5: header sections)                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("kind", ["tree_widget", "table_widget"])
def test_header_sections_carry_the_border_role_not_the_native_look(qtbot, combo, kind):
    """R-5: tree/table header sections are drawn from roles (1 px ``border``, ``surface`` fill).

    The header is not part of the REQ-VI-UI-009 frame set (it takes role colours,
    spec section 11.3); what is tested is that it does not fall back to the native
    look: the header's pixels are all from the role palette, the ``border`` role is
    present as the section outline, and the ``surface`` fill is present.
    """
    widget = FOCUS_KINDS[kind]()
    _host(qtbot, widget)
    reveal(qtbot, widget)
    if isinstance(widget, QTableWidget):
        header = widget.horizontalHeader()
    else:
        header = widget.header()
    _unfocus(widget)
    image = image_array(grab_image(header))
    assert image.shape[0] > 0 and image.shape[1] > 0
    palette = {_rgb(combo, role) for role in _roles(combo)}
    rgb = image[..., :3].reshape(-1, 3)
    colours = {tuple(int(v) for v in px) for px in np.unique(rgb, axis=0)}
    # text is antialiased by the platform font: tolerate glyph pixels, require the structure
    assert (
        _rgb(combo, "border") in colours
    ), "no header section outline in the border role"
    assert (
        _rgb(combo, "surface") in colours
    ), "no header section fill in the surface role"
    off = [c for c in colours if c not in palette]
    glyph_pixels = sum(
        int(((rgb == np.array(c, dtype=np.uint8)).all(axis=1)).sum()) for c in off
    )
    assert glyph_pixels < 0.15 * len(
        rgb
    ), f"{glyph_pixels} of {len(rgb)} header pixels are off-palette"


# --------------------------------------------------------------------------- #
# Docked docks: a title plate and a body frame (REQ-VI-UI-007, mechanism)      #
# --------------------------------------------------------------------------- #


def _docked(qtbot, title: str = "Palette") -> Tuple[QMainWindow, QDockWidget, QWidget]:
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    dock = QDockWidget(title, window)
    panel = _list_widget()
    dock.setWidget(panel)
    pixel_chrome.install_dock_frame(dock)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    window.resize(520, 320)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window._keep = (dock, panel)  # type: ignore[attr-defined]
    _settle()
    return window, dock, panel


def test_install_dock_frame_wraps_once_and_keeps_the_panel_reachable(qtbot, combo):
    """``install_dock_frame`` is idempotent; ``dock_content`` returns the very panel."""
    window, dock, panel = _docked(qtbot)
    body = dock.widget()
    assert body.objectName() == pixel_chrome.DOCK_BODY_OBJECT_NAME
    assert pixel_chrome.dock_content(dock) is panel
    assert pixel_chrome.install_dock_frame(dock) is body, "a second wrap added a frame"
    assert dock.widget() is body and pixel_chrome.dock_content(dock) is panel
    bare = QDockWidget("Bare", window)
    other = QLabel("x")
    bare.setWidget(other)
    assert (
        pixel_chrome.dock_content(bare) is other
    ), "an unwrapped dock must still resolve"


def _plate_height(image: np.ndarray, c: Combo, dock: QDockWidget) -> int:
    """Return the title plate's height: the body's top edge, CONFIRMED by pixels.

    The plate ends where the ``DockBody`` frame begins (its geometry gives the row);
    the rows above it must then equal the ``dock_title`` template composed to that
    size, every cell, with the title and glyph ink (``title_text`` pixels) excluded.
    A search for "any height whose ring matches" is ambiguous when a style's frame
    edge colour equals its title fill (Edo Night Light), so the layout row is taken
    and the pixels are the check.
    """
    template = _template(c, "dock_title")
    height = dock.widget().geometry().top()
    width = image.shape[1]
    assert (
        template.slices.top + template.slices.bottom < height < 80
    ), f"plate height {height}"
    expected = _composed(c, "dock_title", width, height)
    ink = colour_mask_array(image[:height], _rgb(c, "title_text"))
    mask = ~ink
    share, examined = _agree(image[:height], expected, mask)
    assert (
        examined > 0 and share == 1.0
    ), f"the title plate agrees with its template on {share:.4f}"
    return height


def test_sc_vi_ui_007_1_a_docked_dock_shows_its_title_plate_and_body_frame(
    qtbot, combo
):
    """SC-VI-UI-007-1 (mechanism): the plate holds the whole title; the body is framed.

    * the ``dock_title`` plate is found by pixels at the top of the dock;
    * the title's ink (``title_text`` pixels) lies wholly inside the plate band, to
      the left of the float and close glyphs, which are located by their sprites;
    * the ``DockBody`` frame around the content equals ``dock_body`` (the ring it
      has: no top ring, the plate carries it).
    Wiring at the Main_Window's own dock sites is T052; tested at T053.
    """
    window, dock, panel = _docked(qtbot, "Palette")
    _unfocus(window)
    image = _array(dock)
    plate_h = _plate_height(image, combo, dock)
    s = _template(combo, "dock_title").slices
    interior = (s.left, s.top, image.shape[1] - s.right, plate_h - s.bottom)
    # the buttons' glyphs, located by pixels
    glyphs = locate(
        image[:plate_h], sprite_over(combo, "glyph_close", "title_fill")
    ) + locate(image[:plate_h], sprite_over(combo, "glyph_float", "title_fill"))
    assert (
        len(glyphs) == 2
    ), f"the close and float glyphs were found {len(glyphs)} time(s), not 2"
    left_of_buttons = min([x for x, _ in glyphs], default=interior[2])
    ink = colour_mask_array(image[:plate_h], _rgb(combo, "title_text"))
    region = np.zeros_like(ink)
    region[interior[1] : interior[3], interior[0] : left_of_buttons] = True
    inside = ink & region
    assert inside.sum() > 0, "no title ink is drawn inside the plate"
    ys, xs = np.nonzero(inside)
    font = QFontMetricsFor(dock)
    advance = font.horizontalAdvance("Palette")
    available = left_of_buttons - interior[0]
    assert (
        advance <= available
    ), f"the title ({advance} px) does not fit the plate ({available} px)"
    assert xs.min() >= interior[0] and xs.max() < left_of_buttons
    assert ys.min() >= interior[1] and ys.max() < interior[3]
    # nothing of the title ink is clipped by the plate's own ring on the left/top/bottom
    assert ys.min() > interior[1] - 1 and xs.min() > interior[0] - 1
    # the body frame
    body = dock.widget()
    share, examined = frame_share(body, combo, "dock_body")
    assert examined > 0 and share == 1.0, f"body frame agrees on {share:.4f}"


def colour_mask_array(image: np.ndarray, rgb: Tuple[int, int, int]) -> np.ndarray:
    """Return the boolean mask of opaque pixels of an RGBA array equal to ``rgb``."""
    return (
        (image[..., 0] == rgb[0])
        & (image[..., 1] == rgb[1])
        & (image[..., 2] == rgb[2])
        & (image[..., 3] == 255)
    )


def QFontMetricsFor(widget: QWidget):  # noqa: N802 - reads as the constructor it wraps
    """Return the font metrics of ``widget``'s resolved font (a bold dock title is bold)."""
    from PySide6.QtGui import QFontMetrics

    font = widget.font()
    font.setBold(True)
    return QFontMetrics(font)


def test_sc_vi_ui_007_2_a_floating_dock_keeps_native_chrome_and_the_plate_returns(
    qtbot, combo
):
    """SC-VI-UI-007-2 (partial): floating the dock hands it to the window system; re-docking restores.

    HEADLESS LIMIT, stated: the offscreen platform draws no native window frame, so
    "shows the operating system's chrome" cannot be seen in pixels here -- that half
    is "could not verify" (it needs a native-platform run, not performed). What IS
    asserted is what the product controls: a floating dock is not frameless and not
    translucent (nothing replaces the OS bar), it reserves no title area and shows no
    Qt-drawn title plate (the plate's ring does not appear at its top), and re-docking
    brings the title plate and the body frame back, found by pixels.
    """
    window, dock, panel = _docked(qtbot)
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
    assert (
        dock.widget().geometry().top() == 0
    ), "a floating dock still reserves a title area"
    floating = _array(dock)
    floating_fill = int(colour_mask_array(floating[:plate_h], fill).sum())
    # the plate is a band of title-fill colour: a dock without it shows (almost) none
    assert floating_fill < 0.2 * docked_fill, (
        f"a Qt-drawn title plate shows on the floating dock "
        f"({floating_fill} title-fill px against {docked_fill} when docked)"
    )
    dock.setFloating(False)
    _settle()
    assert not dock.isFloating()
    assert (
        _plate_height(_array(dock), combo, dock) > 0
    ), "the title plate did not return"
    share, examined = frame_share(dock.widget(), combo, "dock_body")
    assert examined > 0 and share == 1.0


# --------------------------------------------------------------------------- #
# The art directory may hold a space and non-ASCII characters (plan R-8)      #
# --------------------------------------------------------------------------- #


def test_art_renders_from_a_directory_with_a_space_and_non_ascii_characters(
    qtbot, combo, qapp, tmp_path
):
    """R-8 (T040 item 11): the quoted forward-slash ``url()`` resolves in a hostile path.

    The art is regenerated under a temp root named with a space, accents and CJK
    characters; a framed button rendered from it still equals its template, so the
    files were found and drawn. The product's own art directory is restored after.
    """
    hostile = tmp_path / "art dir äöü 森"
    original = art_root()
    reset_art(hostile)
    try:
        apply_theme(qapp, combo.mode, combo.style)
        assert str(hostile.resolve()) in str(Path(art_root()).resolve())
        qss = qapp.styleSheet()
        assert (
            "art dir" in qss and "森" in qss
        ), "the stylesheet does not use the hostile root"
        button = QPushButton("Button")
        _host(qtbot, button)
        reveal(qtbot, button)
        _unfocus(button)
        share, examined = frame_share(button, combo, "button_normal")
        assert (
            examined > 0 and share >= _FRAME_FLOOR
        ), f"frame from the hostile root agrees on {share:.4f}"
        files = list(hostile.rglob("*.png"))
        assert files, "no art file was written under the hostile root"
    finally:
        reset_art(original)
        apply_theme(qapp, combo.mode, combo.style)


# --------------------------------------------------------------------------- #
# Colour defined once: no widget carries a stylesheet of its own (SC-003-3)    #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_003_3_no_widget_of_the_main_window_carries_a_stylesheet(qtbot, combo):
    """SC-VI-UI-003-3 (first half): no widget of the main window has a stylesheet of its own.

    Every widget under a freshly built ``Main_Window`` is examined; the denominator
    is printed. Any offender is a colour or rule defined outside the one app
    stylesheet (NFR-5).
    """
    from pixelart_creator.ui.main_window import Main_Window

    window = Main_Window()
    qtbot.addWidget(window)
    widgets = window.findChildren(QWidget)
    assert len(widgets) > 100, "too few widgets examined for a main window"
    offenders = _widgets_with_stylesheet(window)
    print(
        f"{combo.label()}: {len(widgets)} widgets examined, {len(offenders)} with a stylesheet"
    )
    assert not offenders, f"widgets carrying a stylesheet of their own: {offenders}"


# --------------------------------------------------------------------------- #
# The canvas workspace stays flat (REQ-CGS-UI-005; ADR-0069 decision 7)        #
# --------------------------------------------------------------------------- #


def test_canvas_workspace_is_one_flat_role_colour_and_carries_no_pattern(
    make_scene, combo
):
    """The ground behind the document is the single ``canvas_workspace`` role, no pattern.

    Rendered for every combination: each pixel clear of the document and its
    border equals the workspace role exactly; one colour, nothing tiled. A
    ``Pattern_Area_Widget`` is nowhere under a canvas view.
    """
    from PySide6.QtCore import QRectF

    from pixelart_creator.ui.theme import canvas_roles

    scene = make_scene(6, 6)
    scene.set_background_roles(*canvas_roles(combo.mode, combo.style))
    scene.set_surface_roles(*canvas_surface_roles(combo.mode, combo.style))
    scene.set_grid_enabled(False)
    expose = 18
    image = QImage(expose, expose, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter

    painter = QPainter(image)
    scene.drawBackground(painter, QRectF(0, 0, expose, expose))
    painter.end()
    data = image_array(image)
    outside = np.ones((expose, expose), dtype=bool)
    outside[:8, :8] = False  # the document (6 px) and its border margin
    cells = data[outside][:, :3]
    assert len(cells) > 0
    workspace = _rgb(combo, "canvas_workspace")
    assert (
        cells == np.array(workspace, dtype=np.uint8)
    ).all(), "the workspace is not flat"
    assert {tuple(int(v) for v in px) for px in np.unique(cells, axis=0)} == {workspace}


def test_no_pattern_area_lies_on_or_under_the_canvas(qtbot, combo):
    """ADR-0069 decision 7: the pattern is never on the canvas workspace."""
    from pixelart_creator.ui.canvas_view import Canvas_View
    from pixelart_creator.ui.pixel_chrome import Pattern_Area_Widget

    window = QMainWindow()
    window.setCentralWidget(QWidget())
    qtbot.addWidget(window)
    from PySide6.QtGui import QUndoStack

    from pixelart_creator.logic.document import Document
    from pixelart_creator.logic.palette import Palette
    from pixelart_creator.ui.canvas_scene import CanvasScene

    scene = CanvasScene(Document(16, 16, palette=Palette([(0, 0, 0, 255)])))
    view = Canvas_View(scene, QUndoStack())
    window.setCentralWidget(view)
    window.show()
    qtbot.waitExposed(window)
    assert view.findChildren(Pattern_Area_Widget) == []
    assert view.viewport().findChildren(Pattern_Area_Widget) == []
    assert not isinstance(view.parentWidget(), Pattern_Area_Widget)


# --------------------------------------------------------------------------- #
# Colour-swatch buttons must still show their colour under the framed buttons  #
# (a regression check on REQ-VI-UI-009: the frame's fill must not hide data)   #
# --------------------------------------------------------------------------- #


#: A swatch the user can recognise: at least an 8 x 8 block of its colour. The test
#: does not prescribe HOW the colour is shown (a fill, an icon), only that it is.
_MIN_SWATCH_PX = 64


def _swatch_px(button: QWidget, rgb: Tuple[int, int, int]) -> int:
    return count_colour_pixels(grab_image(button), _packed(rgb))


def test_onion_skin_tint_buttons_show_their_swatch_colour(qtbot, combo):
    """The previous/next-frame tint buttons paint the colour they stand for.

    Each is a ``QPushButton`` whose swatch colour is a per-widget ``background-color``;
    the framed push button rule draws the template's opaque fill over it, so the
    colour the user picked is not visible. At least ``_MIN_SWATCH_PX`` pixels of the
    tint must show (before the frame work the whole button was that colour: 1220 px).
    """
    from pixelart_creator.ui.onion_skin_controls import Onion_Skin_Controls

    controls = Onion_Skin_Controls()
    _show(qtbot, controls)
    _unfocus(controls)
    for button, tint in (
        (controls._prev_tint_button, controls._tint_prev),
        (controls._next_tint_button, controls._tint_next),
    ):
        shown = _swatch_px(button, tuple(tint[:3]))
        assert shown >= _MIN_SWATCH_PX, (
            f"{combo.label()}: {shown} px of the tint {_hex(tuple(tint[:3]))} show "
            f"on the button (needs >= {_MIN_SWATCH_PX})"
        )


def test_tag_dialog_colour_button_shows_its_swatch_colour(qtbot, combo):
    """The tag colour button paints the colour of the tag (``#ff0000ff`` by default)."""
    from pixelart_creator.ui.frame_tags_panel import Tag_Dialog

    dialog = Tag_Dialog(frame_count=4)
    _show(qtbot, dialog)
    _unfocus(dialog)
    shown = _swatch_px(dialog._color_button, (255, 0, 0))
    assert shown >= _MIN_SWATCH_PX, (
        f"{combo.label()}: {shown} px of #ff0000 show on the colour button "
        f"(needs >= {_MIN_SWATCH_PX})"
    )


# --------------------------------------------------------------------------- #
# Every keyboard-focusable widget of the main window shows a ring (census)    #
# --------------------------------------------------------------------------- #


def _is_ring_bearer(widget: QWidget) -> bool:
    """Return whether the ring is drawn on ``widget`` itself.

    A scroll area's viewport is focus-proxied to its view (the view wears the ring),
    and a spin or combo box's embedded line edit rings its parent; neither is a
    separate control to examine.
    """
    from PySide6.QtWidgets import QAbstractScrollArea

    parent = widget.parentWidget()
    if isinstance(widget, QLineEdit) and isinstance(
        parent, (QAbstractSpinBox, QComboBox)
    ):
        return False
    if isinstance(parent, QAbstractScrollArea) and parent.viewport() is widget:
        return False
    return True


def test_every_keyboard_focusable_widget_of_the_main_window_shows_a_focus_ring(
    qtbot, combo, qapp
):
    """REQ-VI-UI-005: every focusable, visible, enabled widget wears the ring on focus.

    The census of a shown ``Main_Window`` (every dock raised): each widget whose focus
    policy accepts the keyboard is given focus and must show focus-role pixels. The
    number examined is printed and must be large; a widget with a focus policy but
    no ring (a focusable ``QLabel`` is outside the filter's control classes) is
    listed by name.
    """
    from pixelart_creator.ui.main_window import Main_Window

    window = Main_Window()  # applies Light at construction, whatever combo said
    qtbot.addWidget(window)
    apply_theme(qapp, combo.mode, combo.style)
    window.resize(1400, 900)
    window.show()
    qtbot.waitExposed(window)
    for dock in window.findChildren(QDockWidget):
        dock.show()
    _settle()
    examined = 0
    offenders: List[str] = []
    for widget in window.findChildren(QWidget):
        if (
            widget.focusPolicy() == Qt.FocusPolicy.NoFocus
            or not widget.isVisible()
            or not widget.isEnabled()
            or widget.width() < 4
            or widget.height() < 4
            or not _is_ring_bearer(widget)
        ):
            continue
        examined += 1
        evidence = measure_focus(qtbot, widget, combo.mode, combo.style)
        if evidence.focused_px == 0:
            owner = widget.parentWidget()
            offenders.append(
                f"{type(widget).__name__} {widget.objectName()!r} "
                f"(accessible name {widget.accessibleName()!r}, in {type(owner).__name__})"
            )
    print(
        f"{combo.label()}: {examined} focusable widgets examined, {len(offenders)} without a ring"
    )
    assert (
        examined > 50
    ), f"only {examined} widgets examined -- the census found nothing"
    assert not offenders, f"focusable widgets that show no focus ring: {offenders}"
