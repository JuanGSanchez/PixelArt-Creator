"""Guards for the two changes that keep canvas interaction inside the frame budget.

Timings are machine-dependent, so nothing here measures time. Each test pins a
deterministic, observable fact that the speed-up rests on, and every test has a
control that proves the check can fail.

1. **The canvas viewport is opaque and tells the truth about it.** The viewport
   carries ``Qt.WA_OpaquePaintEvent``, which makes Qt skip repainting the
   widgets beneath it on every canvas repaint (under the pixel chrome those are
   large tiled frames). The attribute is only legitimate while the scene really
   paints every pixel it is asked to, including the area outside the document,
   so the tests check both halves:

   * the attribute is set, for every style and mode, and survives a viewport
     replacement;
   * rendering the viewport (and, separately, calling the scene's background
     painter with a rect that reaches far outside the document) into an image
     pre-filled with a sentinel colour leaves **zero** sentinel pixels. The
     leftover count is printed. The control is a scene whose background paint
     does nothing: it must leave sentinel pixels, so the counter is known to see
     garbage.
   * an ancestor-repaint counter: a canvas-only update must deliver no ``Paint``
     event to any ancestor of the viewport; with the attribute cleared (the
     control) it must deliver some. The viewport itself must receive a ``Paint``
     in both runs, so a zero cannot mean "nothing was painted at all".

2. **Frame art is stretched only where stretching paints the same picture.** A
   ``border-image`` whose middle cells are identical is written ``stretch
   stretch`` on the large surfaces (the canvas frame, the tab page area, and the
   dock body from art scale 2 up) and ``repeat repeat`` everywhere else. The
   tests pin the exact mode of every rule of the generated stylesheet for every
   style and mode at scales 1, 2 and 3, the uniformity decision itself (against
   an independent oracle, the real templates and hand-made counter-examples) and
   the rule that a textured template (a pattern tile) never stretches.

Everything runs on the offscreen platform at device-pixel ratio 1.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data import style_catalog
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.theme_art import RoleGrid, Slices, Template
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.theme import (
    THEME_LIGHT,
    apply_theme,
    available_styles,
    available_themes,
    build_qss,
    canvas_roles,
    canvas_surface_roles,
    role_map,
)
from pixelart_creator.ui.theme_art_files import ArtSet, art_set

# --------------------------------------------------------------------------- #
# Matrix and shared helpers                                                    #
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
STYLES = tuple(available_styles())
SCALES = (1, 2, 3)

#: Magenta: an opaque colour no role of any shipped style uses (asserted below).
SENTINEL_RGB = (255, 0, 255)
_SENTINEL_PACKED = (
    0xFF000000 | (SENTINEL_RGB[0] << 16) | (SENTINEL_RGB[1] << 8) | SENTINEL_RGB[2]
)

_PALETTE = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]
_VIEW_SIZE = (480, 360)


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture inside this module.

    This module parametrises over the whole style x mode matrix itself; the
    shared fixture would run every test twice with the canonical style.
    """
    apply_theme(qapp, THEME_LIGHT)
    return THEME_LIGHT


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest, qapp) -> Combo:
    """Apply one style x mode combination to the application and return it."""
    chosen: Combo = request.param
    apply_theme(qapp, chosen.mode, chosen.style)
    return chosen


class NoBackgroundScene(CanvasScene):
    """Control scene: it skips the background fill (the defect, planted)."""

    def drawBackground(  # type: ignore[override]  # noqa: N802
        self, painter: QPainter, rect: QRectF
    ) -> None:
        """Paint no background at all, so whatever was underneath stays visible.

        The document here is empty (fully transparent) and nothing else paints
        a colour, so an untouched image is the expected result of the defect.
        """


def _scene(combo: Combo, *, size: int = 64, scene_cls=CanvasScene) -> CanvasScene:
    """Return a scene of ``size`` x ``size`` px with the combination's roles."""
    scene = scene_cls(Document(size, size, palette=Palette(_PALETTE)))
    scene.set_background_roles(*canvas_roles(combo.mode, combo.style))
    scene.set_surface_roles(*canvas_surface_roles(combo.mode, combo.style))
    return scene


def _view(qtbot, combo: Combo, *, size: int = 64, scene_cls=CanvasScene) -> Canvas_View:
    """Return a shown, pumped canvas view over a fresh scene of ``size`` px."""
    view = Canvas_View(_scene(combo, size=size, scene_cls=scene_cls), QUndoStack())
    qtbot.addWidget(view)
    view.resize(*_VIEW_SIZE)
    view.show()
    _pump()
    return view


def _pump(times: int = 3) -> None:
    for _ in range(times):
        QApplication.processEvents()


def _count_sentinel(image: QImage) -> int:
    """Return how many pixels of ``image`` still hold the sentinel colour."""
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    raw = np.frombuffer(argb.constBits(), dtype=np.uint8, count=argb.sizeInBytes())
    rows = raw.reshape(argb.height(), argb.bytesPerLine())
    pixels = np.ascontiguousarray(rows[:, : argb.width() * 4]).view("=u4")
    return int(np.count_nonzero(pixels == _SENTINEL_PACKED))


def _sentinel_image(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(_SENTINEL_PACKED)
    assert _count_sentinel(image) == width * height  # the counter sees all of it
    return image


def _render_viewport(view: Canvas_View) -> QImage:
    """Render the viewport into an image that starts out all sentinel.

    Only the widget's own paint path writes to the image: the window-background
    flag is left off so nothing but the viewport's painting can cover it.
    """
    viewport = view.viewport()
    image = _sentinel_image(viewport.width(), viewport.height())
    viewport.render(image, renderFlags=QWidget.RenderFlag.DrawChildren)
    return image


def _set_state(view: Canvas_View, state: str) -> None:
    """Put the view in one of the named states the sentinel render covers."""
    scene = view.scene()
    assert isinstance(scene, CanvasScene)
    if state == "default":
        pass
    elif state == "zoom-16":
        view.set_zoom(16.0)
    elif state == "zoom-floor":
        view.set_zoom(1.0)
    elif state == "scrolled-to-corner":
        view.set_zoom(8.0)
        view.horizontalScrollBar().setValue(view.horizontalScrollBar().minimum())
        view.verticalScrollBar().setValue(view.verticalScrollBar().minimum())
    elif state == "tiled-preview":
        scene.set_tiled_preview(True)
    elif state == "grid-zoom-16":
        scene.set_grid_enabled(True)
        view.set_zoom(16.0)
    else:  # pragma: no cover - a typo in this module
        raise AssertionError(f"unknown state {state!r}")
    _pump()


#: Name -> document edge in px. The floor-zoom state uses a small document so most
#: of the viewport lies outside it.
STATES: Dict[str, int] = {
    "default": 64,
    "zoom-16": 64,
    "zoom-floor": 16,
    "scrolled-to-corner": 64,
    "tiled-preview": 64,
    "grid-zoom-16": 64,
}


# --------------------------------------------------------------------------- #
# 1. The sentinel is a colour the canvas can never legitimately paint          #
# --------------------------------------------------------------------------- #


def test_sentinel_colour_is_not_used_by_any_role(combo: Combo):
    """The sentinel cannot be mistaken for a painted colour in any combination."""
    sentinel_hex = "#%02x%02x%02x" % SENTINEL_RGB
    roles = {k: v.lower() for k, v in role_map(combo.mode, combo.style).items()}
    clashes = [k for k, v in roles.items() if v == sentinel_hex]
    assert clashes == [], f"roles equal to the sentinel {sentinel_hex}: {clashes}"
    assert _SENTINEL_PACKED == 0xFFFF00FF


# --------------------------------------------------------------------------- #
# 2. The viewport is opaque                                                    #
# --------------------------------------------------------------------------- #


def test_canvas_viewport_declares_it_paints_every_pixel(qtbot, combo: Combo):
    """The viewport has ``WA_OpaquePaintEvent`` set, in every style and mode."""
    view = _view(qtbot, combo)
    assert view.viewport().testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)


def test_canvas_viewport_stays_opaque_when_the_viewport_is_replaced(
    qtbot, combo: Combo
):
    """A replacement viewport is marked opaque too, not only the first one."""
    view = _view(qtbot, combo)
    old = view.viewport()
    replacement = QWidget()
    replacement.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    view.setViewport(replacement)
    assert view.viewport() is replacement
    assert view.viewport() is not old
    assert replacement.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)


def test_control_a_plain_graphics_view_viewport_is_not_opaque(qtbot):
    """Control: a stock ``QGraphicsView`` viewport is not opaque by itself.

    So a green "attribute is set" result above comes from the canvas view's
    own code and not from a Qt default.
    """
    from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

    plain = QGraphicsView(QGraphicsScene())
    qtbot.addWidget(plain)
    assert not plain.viewport().testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)


# --------------------------------------------------------------------------- #
# 3. ... and the claim is true: nothing is left unpainted                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("state", list(STATES))
def test_canvas_viewport_render_leaves_no_unpainted_pixel(
    qtbot, combo: Combo, state: str
):
    """Every pixel of the viewport is painted, in every view state.

    The viewport is rendered into an image pre-filled with the sentinel colour,
    then the leftover sentinel pixels are counted (and printed): 0 is required.
    """
    view = _view(qtbot, combo, size=STATES[state])
    assert view.viewport().testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    _set_state(view, state)
    image = _render_viewport(view)
    left = _count_sentinel(image)
    total = image.width() * image.height()
    print(f"[{combo.label()} / {state}] sentinel pixels left: {left} of {total}")
    assert total > 0
    assert left == 0


@pytest.mark.parametrize("state", list(STATES))
def test_control_viewport_render_with_no_background_paint_leaves_pixels(
    qtbot, combo: Combo, state: str
):
    """Control: a scene that skips its background paint leaves sentinel pixels.

    The viewport keeps its opaque attribute here, exactly as shipped, so the
    only thing missing is the scene's own fill. The counter must see it.
    """
    view = _view(qtbot, combo, size=STATES[state], scene_cls=NoBackgroundScene)
    assert view.viewport().testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    _set_state(view, state)
    left = _count_sentinel(_render_viewport(view))
    print(f"[{combo.label()} / {state}] CONTROL sentinel pixels left: {left}")
    assert left > 0


def _paint_background(scene: CanvasScene, rect: QRectF, margin: int) -> QImage:
    """Call the scene's background painter for ``rect`` onto a sentinel image.

    ``rect`` is in scene coordinates; ``margin`` shifts the origin so a rect that
    starts at negative scene coordinates lands inside the image.
    """
    image = _sentinel_image(int(rect.width()), int(rect.height()))
    painter = QPainter(image)
    try:
        painter.translate(margin, margin)
        scene.drawBackground(painter, rect)
    finally:
        painter.end()
    return image


def test_scene_background_covers_a_rect_reaching_outside_the_document(combo: Combo):
    """The scene fills a rect that is 40 px larger than the document on every side."""
    scene = _scene(combo, size=64)
    margin = 40
    rect = QRectF(-margin, -margin, 64 + 2 * margin, 64 + 2 * margin)
    left = _count_sentinel(_paint_background(scene, rect, margin))
    print(f"[{combo.label()}] scene background, sentinel pixels left: {left}")
    assert left == 0


def test_scene_background_outside_the_document_is_the_workspace_colour(
    combo: Combo,
):
    """Away from the document the exposed rect is exactly the workspace colour."""
    scene = _scene(combo, size=64)
    workspace, _border = canvas_surface_roles(combo.mode, combo.style)
    rect = QRectF(200, 200, 40, 40)  # entirely outside a 64 px document
    image = _paint_background(scene, rect, -200)
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    raw = np.frombuffer(argb.constBits(), dtype=np.uint8, count=argb.sizeInBytes())
    rows = raw.reshape(argb.height(), argb.bytesPerLine())
    pixels = np.ascontiguousarray(rows[:, : argb.width() * 4]).view("=u4")
    assert workspace.alpha() == 255, "the workspace role must be opaque"
    assert set(np.unique(pixels).tolist()) == {workspace.rgba()}


def test_control_scene_without_background_paint_leaves_sentinel(combo: Combo):
    """Control: the same direct call on a scene with no background paint."""
    scene = _scene(combo, size=64, scene_cls=NoBackgroundScene)
    margin = 40
    rect = QRectF(-margin, -margin, 64 + 2 * margin, 64 + 2 * margin)
    left = _count_sentinel(_paint_background(scene, rect, margin))
    print(f"[{combo.label()}] CONTROL scene background, sentinel left: {left}")
    assert left == rect.width() * rect.height()


# --------------------------------------------------------------------------- #
# 4. A canvas-only update reaches no ancestor                                  #
# --------------------------------------------------------------------------- #


class _PaintCounter(QObject):
    """Application-wide filter counting ``Paint`` events per receiver."""

    def __init__(self) -> None:
        super().__init__()
        self.counts: Dict[QObject, int] = {}

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Paint:
            self.counts[watched] = self.counts.get(watched, 0) + 1
        return False


class _Hosted(NamedTuple):
    view: Canvas_View
    ancestors: List[QWidget]
    window: QTabWidget


def _host_in_tab_page(qtbot, combo: Combo) -> _Hosted:
    """Return a canvas view inside a tab page, as in the product's layout."""
    tabs = QTabWidget()
    qtbot.addWidget(tabs)
    page = QWidget()
    layout = QVBoxLayout(page)
    view = Canvas_View(_scene(combo), QUndoStack())
    layout.addWidget(view)
    layout.addWidget(QLabel("below the canvas"))
    tabs.addTab(page, "canvas")
    tabs.resize(560, 480)
    tabs.show()
    _pump(5)
    ancestors: List[QWidget] = []
    parent = view.viewport().parentWidget()
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parentWidget()
    return _Hosted(view, ancestors, tabs)


def _canvas_only_update(hosted: _Hosted) -> Tuple[int, int]:
    """Update only the viewport; return (ancestor paints, viewport paints)."""
    counter = _PaintCounter()
    app = QApplication.instance()
    assert app is not None
    app.installEventFilter(counter)
    try:
        _pump()  # drain anything queued by showing the window
        counter.counts.clear()
        hosted.view.viewport().update()
        _pump()
    finally:
        app.removeEventFilter(counter)
    viewport = hosted.view.viewport()
    ancestors = sum(counter.counts.get(w, 0) for w in hosted.ancestors)
    return ancestors, counter.counts.get(viewport, 0)


def test_canvas_only_update_paints_no_ancestor(qtbot, combo: Combo):
    """With the viewport opaque, a canvas-only update paints none of its ancestors."""
    hosted = _host_in_tab_page(qtbot, combo)
    assert hosted.view.viewport().testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    assert len(hosted.ancestors) >= 3  # view, page, stack, tab widget
    ancestors, viewport = _canvas_only_update(hosted)
    print(
        f"[{combo.label()}] ancestor paints: {ancestors}, viewport paints: {viewport}"
    )
    assert viewport >= 1, "the update never reached the viewport: a 0 would be vacuous"
    assert ancestors == 0


def test_control_canvas_only_update_paints_ancestors_without_the_attribute(
    qtbot, combo: Combo
):
    """Control: with the attribute cleared the same update paints the ancestors."""
    hosted = _host_in_tab_page(qtbot, combo)
    hosted.view.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    ancestors, viewport = _canvas_only_update(hosted)
    print(
        f"[{combo.label()}] CONTROL ancestor paints: {ancestors}, "
        f"viewport paints: {viewport}"
    )
    assert viewport >= 1
    assert ancestors > 0


# --------------------------------------------------------------------------- #
# 5. Which rules stretch                                                       #
# --------------------------------------------------------------------------- #

_RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
_BORDER_IMAGE = re.compile(
    r'border-image:\s*url\("(?P<url>[^"]+)"\)\s+'
    r"(?P<top>\d+)\s+(?P<right>\d+)\s+(?P<bottom>\d+)\s+(?P<left>\d+)\s+"
    r"(?P<horizontal>\w+)\s+(?P<vertical>\w+)\s*;"
)


class FramedRule(NamedTuple):
    """One stylesheet rule that declares a ``border-image``."""

    position: int
    selector: str
    template: str
    horizontal: str
    vertical: str


def framed_rules(qss: str) -> List[FramedRule]:
    """Return every rule of ``qss`` that declares a ``border-image``, in order."""
    found: List[FramedRule] = []
    for index, rule in enumerate(_RULE.finditer(qss)):
        match = _BORDER_IMAGE.search(rule.group("body"))
        if match is None:
            continue
        selector = " ".join(rule.group("selector").split())
        found.append(
            FramedRule(
                index,
                selector,
                Path(match.group("url")).stem,
                match.group("horizontal"),
                match.group("vertical"),
            )
        )
    return found


#: selector -> the scales at which the rule is written ``stretch stretch``.
#: Every other framed rule of the sheet is ``repeat repeat`` at every scale.
EXPECTED_STRETCH: Dict[str, Tuple[int, ...]] = {
    "QTabWidget::pane": (1, 2, 3),
    "QGraphicsView": (1, 2, 3),
    "QFrame#DockBody": (2, 3),
}
_TEXT_FIELDS_SELECTOR = "QLineEdit, QTextEdit, QPlainTextEdit, QGraphicsView"
_TEMPLATE_OF = {
    "QTabWidget::pane": "panel",
    "QGraphicsView": "field",
    "QFrame#DockBody": "dock_body",
}


@pytest.mark.parametrize("scale", SCALES)
def test_stylesheet_stretches_exactly_the_expected_rules(combo: Combo, scale: int):
    """The set of ``stretch stretch`` rules is exactly the expected one, per scale."""
    rules = framed_rules(build_qss(combo.mode, combo.style, scale=scale))
    assert len(rules) >= 20, f"only {len(rules)} framed rules parsed"
    stretched = {r.selector for r in rules if r.horizontal == "stretch"}
    expected = {s for s, scales in EXPECTED_STRETCH.items() if scale in scales}
    print(
        f"[{combo.label()} S={scale}] {len(rules)} framed rules, "
        f"stretched: {sorted(stretched)}"
    )
    assert stretched == expected
    for rule in rules:
        assert rule.horizontal == rule.vertical, f"mixed modes in {rule}"
        assert rule.horizontal in {"stretch", "repeat"}, rule


@pytest.mark.parametrize("scale", SCALES)
@pytest.mark.parametrize("selector", sorted(EXPECTED_STRETCH))
def test_each_large_surface_rule_has_its_exact_mode(
    combo: Combo, scale: int, selector: str
):
    """Each of the three large-surface rules: its template and its exact mode."""
    rules = [
        r
        for r in framed_rules(build_qss(combo.mode, combo.style, scale=scale))
        if r.selector == selector
    ]
    assert len(rules) == 1, f"{selector!r} appears {len(rules)} times"
    rule = rules[0]
    assert rule.template == _TEMPLATE_OF[selector]
    want = "stretch" if scale in EXPECTED_STRETCH[selector] else "repeat"
    assert (rule.horizontal, rule.vertical) == (want, want)


def test_dock_body_keeps_repeat_at_scale_one_and_stretches_from_two(combo: Combo):
    """The dock body is tiled at art scale 1 and stretched at scales 2 and 3."""
    modes = {}
    for scale in SCALES:
        rules = framed_rules(build_qss(combo.mode, combo.style, scale=scale))
        (rule,) = [r for r in rules if r.selector == "QFrame#DockBody"]
        modes[scale] = rule.horizontal
    print(f"[{combo.label()}] dock body mode by scale: {modes}")
    assert modes == {1: "repeat", 2: "stretch", 3: "stretch"}


@pytest.mark.parametrize("scale", SCALES)
def test_small_widgets_keep_repeat_even_when_their_template_is_uniform(
    combo: Combo, scale: int
):
    """Text fields, item views, buttons, tabs, menus, scroll parts: all ``repeat``."""
    art = art_set(combo.style, combo.mode, scale)
    rules = framed_rules(build_qss(combo.mode, combo.style, scale=scale))
    small = [r for r in rules if r.selector not in EXPECTED_STRETCH]
    assert len(small) >= 17
    uniform_but_tiled = [
        r for r in small if art.is_uniform(r.template.removesuffix("_t"))
    ]
    assert uniform_but_tiled, "no uniform template is used by a small widget"
    assert {r.horizontal for r in small} == {"repeat"}
    assert {r.vertical for r in small} == {"repeat"}


@pytest.mark.parametrize("scale", SCALES)
def test_canvas_frame_rule_follows_the_shared_text_field_rule(combo: Combo, scale: int):
    """The stretched canvas-frame rule comes after the shared field rule.

    Both have the same specificity, so the later one wins; if the order flipped,
    the canvas frame would silently go back to ``repeat``.
    """
    rules = framed_rules(build_qss(combo.mode, combo.style, scale=scale))
    (shared,) = [r for r in rules if r.selector == _TEXT_FIELDS_SELECTOR]
    (canvas,) = [r for r in rules if r.selector == "QGraphicsView"]
    assert shared.horizontal == "repeat"
    assert canvas.horizontal == "stretch"
    assert canvas.position > shared.position


@pytest.mark.parametrize("scale", SCALES)
def test_no_stylesheet_rule_frames_the_pattern_or_an_ornament(combo: Combo, scale: int):
    """Pattern areas and ornaments are painted, not framed: no rule names them."""
    templates = {
        r.template
        for r in framed_rules(build_qss(combo.mode, combo.style, scale=scale))
    }
    assert templates, "no framed rule parsed"
    assert not {"pattern", "ornament"} & templates


# --------------------------------------------------------------------------- #
# 6. The uniformity decision                                                   #
# --------------------------------------------------------------------------- #

#: Templates that must be uniform / textured in every shipped style (fixed pins).
MUST_BE_UNIFORM = ("panel", "field", "dock_body", "dialog", "button_normal", "menu")
MUST_NOT_BE_UNIFORM = (
    "ornament",
    "check_on",
    "check_off",
    "glyph_close",
    "glyph_float",
    "arrow_up",
    "arrow_down",
    "slider_handle",
)


def oracle_is_uniform(template: Template) -> bool:
    """Independent re-statement of "tiling the middle is a no-op" (numpy based)."""
    grid = np.array([list(row) for row in template.grid.rows])
    s = template.slices
    height, width = grid.shape
    if width - s.left - s.right < 1 or height - s.top - s.bottom < 1:
        return False
    middle = grid[s.top : height - s.bottom, s.left : width - s.right]
    if len(np.unique(middle)) != 1:
        return False
    # Edge strips: constant along their own axis, ignoring the corners.
    top = grid[: s.top, s.left : width - s.right]
    bottom = grid[height - s.bottom :, s.left : width - s.right]
    left = grid[s.top : height - s.bottom, : s.left]
    right = grid[s.top : height - s.bottom, width - s.right :]
    for strip in (top, bottom):
        if strip.size and any(len(np.unique(row)) != 1 for row in strip):
            return False
    for strip in (left, right):
        if strip.size and any(len(np.unique(col)) != 1 for col in strip.T):
            return False
    return True


@pytest.mark.parametrize("style", STYLES)
def test_is_uniform_agrees_with_an_independent_oracle_on_every_template(style: str):
    """``is_uniform`` matches the oracle on all templates of the style."""
    art = art_set(style, THEME_LIGHT, 1)
    templates = style_catalog.template_set(style).templates
    assert len(templates) >= 20
    disagreements = {
        name: (art.is_uniform(name), oracle_is_uniform(t))
        for name, t in templates.items()
        if art.is_uniform(name) != oracle_is_uniform(t)
    }
    uniform = sorted(n for n in templates if art.is_uniform(n))
    print(f"[{style}] {len(uniform)} of {len(templates)} templates are uniform")
    assert disagreements == {}


@pytest.mark.parametrize("style", STYLES)
def test_framed_templates_are_uniform_and_glyphs_are_not(style: str):
    """Fixed pins: the frames used on big surfaces are uniform, glyphs are not."""
    art = art_set(style, THEME_LIGHT, 1)
    assert [n for n in MUST_BE_UNIFORM if not art.is_uniform(n)] == []
    assert [n for n in MUST_NOT_BE_UNIFORM if art.is_uniform(n)] == []


@pytest.mark.parametrize("style", STYLES)
def test_transposed_uniform_template_stays_uniform(style: str):
    """The axis-swapped variants (horizontal scroll parts) are decided too."""
    art = art_set(style, THEME_LIGHT, 1)
    assert art.is_uniform("scroll_track")
    assert art.is_uniform("scroll_track", transpose=True)
    assert _mode_of(art.border_image("scroll_track", transpose=True, large=True)) == (
        "stretch",
        "stretch",
    )


def _mode_of(declaration: str) -> Tuple[str, str]:
    match = _BORDER_IMAGE.search(declaration)
    assert match is not None, declaration
    return match.group("horizontal"), match.group("vertical")


@pytest.mark.parametrize("style", STYLES)
def test_border_image_stretches_iff_large_and_uniform(style: str):
    """For every template: ``stretch`` exactly when ``large`` and uniform."""
    art = art_set(style, THEME_LIGHT, 2)
    names = sorted(style_catalog.template_set(style).templates)
    outcomes: Dict[Tuple[bool, bool], int] = {}
    for name in names:
        uniform = art.is_uniform(name)
        small = _mode_of(art.border_image(name))
        large = _mode_of(art.border_image(name, large=True))
        assert small == ("repeat", "repeat"), f"{name}: small widget must tile"
        want = ("stretch", "stretch") if uniform else ("repeat", "repeat")
        assert large == want, f"{name}: uniform={uniform} but large gave {large}"
        outcomes[(uniform, large[0] == "stretch")] = (
            outcomes.get((uniform, large[0] == "stretch"), 0) + 1
        )
    print(f"[{style}] (uniform, stretched) -> templates: {outcomes}")
    assert (True, True) in outcomes and (False, False) in outcomes


@pytest.mark.parametrize("style", STYLES)
def test_border_image_slices_and_widths_do_not_depend_on_the_mode(style: str):
    """Stretching changes the mode words only, never the slices or the widths."""
    art = art_set(style, THEME_LIGHT, 3)
    for name in ("panel", "field", "dock_body"):
        small = art.border_image(name)
        large = art.border_image(name, large=True)
        assert small.replace("repeat repeat", "stretch stretch") == large


# -- hand-made counter-examples (a synthetic art set, written under tmp_path) -- #

_LEGEND = (("A", "accent"), ("B", "border"), ("C", "surface"), ("_", None))
_ONE = Slices(left=1, top=1, right=1, bottom=1)


def _template(rows: Tuple[str, ...], slices: Slices = _ONE) -> Template:
    return Template(
        name="probe", grid=RoleGrid(rows=rows, legend=_LEGEND), slices=slices
    )


COUNTER_EXAMPLES: Dict[str, Tuple[Template, bool]] = {
    "plain frame": (
        _template(("BBBBB", "BAAAB", "BAAAB", "BAAAB", "BBBBB")),
        True,
    ),
    "frame with a hollow (transparent) centre": (
        _template(("BBBBB", "B___B", "B___B", "B___B", "BBBBB")),
        True,
    ),
    "textured centre": (
        _template(("BBBBB", "BABAB", "BBABB", "BABAB", "BBBBB")),
        False,
    ),
    "two-role centre": (
        _template(("BBBBB", "BAACB", "BAACB", "BAACB", "BBBBB")),
        False,
    ),
    "top edge varies along the axis": (
        _template(("BABAB", "BAAAB", "BAAAB", "BAAAB", "BBBBB")),
        False,
    ),
    "left edge varies along the axis": (
        _template(("BBBBB", "BAAAB", "AAAAB", "BAAAB", "BBBBB")),
        False,
    ),
    "no middle on either axis": (_template(("BB", "BB")), False),
    "no middle on one axis": (
        _template(("BBBBB", "BBBBB")),  # wide enough to stretch, but no rows left
        False,
    ),
    "a tile with no slices (a pattern tile)": (
        _template(("ABAB", "BABA", "ABAB", "BABA"), Slices(0, 0, 0, 0)),
        False,
    ),
}


@pytest.fixture
def probe_art(tmp_path: Path) -> Iterator[ArtSet]:
    """An art set bound to a scratch folder; templates are swapped per test."""
    yield ArtSet(tmp_path, STYLES[0], THEME_LIGHT, 2)


@pytest.mark.parametrize("case", sorted(COUNTER_EXAMPLES))
def test_uniformity_of_hand_made_templates(probe_art: ArtSet, case: str):
    """Textured or irregular templates are never uniform; plain frames are."""
    template, expected = COUNTER_EXAMPLES[case]
    probe_art._templates = {"probe": template}  # type: ignore[assignment]
    assert oracle_is_uniform(template) is expected, "the oracle disagrees with the case"
    assert probe_art.is_uniform("probe") is expected
    mode = _mode_of(probe_art.border_image("probe", large=True))
    assert mode == (("stretch",) * 2 if expected else ("repeat",) * 2)
    assert _mode_of(probe_art.border_image("probe")) == ("repeat", "repeat")


@pytest.mark.parametrize("style", STYLES)
def test_the_pattern_tile_is_textured_and_never_stretches(style: str, tmp_path: Path):
    """The shipped pattern tile is not uniform, so even ``large`` keeps ``repeat``."""
    pattern = style_catalog.template_set(style).pattern
    art = ArtSet(tmp_path, style, THEME_LIGHT, 1)
    art._templates = {"pattern": pattern}  # type: ignore[assignment]
    assert len({ch for row in pattern.grid.rows for ch in row}) > 1
    assert art.is_uniform("pattern") is False
    assert _mode_of(art.border_image("pattern", large=True)) == ("repeat", "repeat")


def test_scales_below_one_and_non_integers_are_refused(tmp_path: Path):
    """Control for the scale argument the rules above are parametrised over."""
    from pixelart_creator.logic.theme_art import ThemeArtError

    for bad in (0, -1, 1.5, True):
        with pytest.raises(ThemeArtError):
            ArtSet(tmp_path, STYLES[0], THEME_LIGHT, bad)  # type: ignore[arg-type]


def test_the_matrix_is_not_empty():
    """The parametrisation above covers at least one style and both modes."""
    print(f"matrix: {len(COMBOS)} combinations = {_COMBO_IDS}")
    assert len(STYLES) >= 1
    assert len(available_themes()) == 2
    assert len(COMBOS) == len(STYLES) * len(available_themes())
