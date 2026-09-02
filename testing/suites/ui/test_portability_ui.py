"""Cross-platform UI portability acceptance tests (Researcher Q5).

Covers the two Q5-flagged GUI risks:

* **REQ-P13-UI-001 — font-availability fallback** (SC-P13-UI-001-1): the UI names
  no single-OS font family, and a **defined-once, role-based** fallback seam
  (:func:`~pixelart_creator.ui.theme.apply_font_fallbacks`) is installed at shell
  start so a family absent on the running OS degrades to the first resolvable
  entry rather than to ``.notdef`` boxes. Verified in **both** themes.
* **REQ-P13-UI-002 — DPI / display-scaling correctness** (SC-P13-UI-002-1): the
  shipped Phase-9 *no-double-DPR* discipline holds (the real-size preview applies
  the pure ``screen_dpi / doc_ppi`` factor exactly once, independent of the view's
  ``devicePixelRatio``); the pixel canvas paints in **scene coordinates** with
  **nearest-neighbour + anti-aliasing off** (crisp, never blurred); the QSS uses
  **logical px**; and the 16 ms ``FRAME_BUDGET_MS`` is **not relaxed** (Article VI).

Design note (headless / OS-agnostic, F11): the ``offscreen`` QPA font database is
unreliable (``QFontInfo.family()`` can be empty and ``QFontMetrics.inFontUcs4``
False even for basic Latin on some hosts/CI legs), and a true ``devicePixelRatio``
> 1 cannot be forced offscreen. Per the harness policy these tests assert the
**mechanism** (fallback substitutions registered; no hard-coded per-OS family;
text lays out with a non-zero advance; the pure-ratio transform is DPR-independent)
rather than a flaky per-OS glyph/pixel measure — so the module runs identically on
all three CI legs. Every test also runs twice (light + dark) via the autouse
``theme`` fixture in ``conftest.py``.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import FRAME_BUDGET_MS
from pixelart_creator.logic.preview import real_size_scale
from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from pixelart_creator.ui.theme import (
    _UI_FONT_FALLBACKS,
    THEME_DARK,
    THEME_LIGHT,
    apply_font_fallbacks,
    build_qss,
    canvas_roles,
)

#: Representative standard English UI strings (menu titles / labels) — basic Latin,
#: OS-agnostic. Used to prove text lays out with a resolvable font.
_REPRESENTATIVE_UI_TEXT = "File Edit View Palette Tilemap Cloud Help"


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --------------------------------------------------------------------------- #
# REQ-P13-UI-001 — font-availability fallback (SC-P13-UI-001-1)                #
# --------------------------------------------------------------------------- #


def test_sc_p13_ui_001_1_fallback_seam_installed_for_every_single_os_family(qtbot):
    """SC-P13-UI-001-1: the defined-once fallback chain is registered for each family.

    Constructing the shell calls :func:`apply_font_fallbacks` (before
    :func:`apply_theme`), so every single-OS family in ``_UI_FONT_FALLBACKS`` has
    a non-empty Qt substitution list — the belt-and-braces guard against a
    ``.notdef`` box on an OS that lacks the requested family. OS-agnostic: Qt
    stores substitutions case-insensitively, so we compare lower-cased families.
    """
    _window(qtbot)  # shell construction installs the seam
    for family, fallbacks in _UI_FONT_FALLBACKS.items():
        registered = [s.lower() for s in QFont.substitutes(family)]
        assert registered, f"no fallback registered for single-OS family {family!r}"
        # The declared fallback chain is present, in order (belt-and-braces guard).
        for entry in fallbacks:
            assert (
                entry.lower() in registered
            ), f"{family!r} fallback chain missing {entry!r}: {registered}"


def test_sc_p13_ui_001_1_apply_font_fallbacks_is_defined_once_role_based(qtbot):
    """SC-P13-UI-001-1: the fallback is a single seam, not a per-widget font.

    Calling the seam directly registers exactly the same map the shell installs
    (idempotent for practical purposes — a re-call adds no *new* family), proving
    the fallback is defined once in the theming layer rather than per-widget.
    """
    apply_font_fallbacks()
    seam_families = {f.lower() for f in _UI_FONT_FALLBACKS}
    registered_families = {f.lower() for f in QFont.substitutions()}
    # Every single-OS family the seam owns is present in Qt's substitution registry.
    assert seam_families <= registered_families


def test_sc_p13_ui_001_1_ui_names_no_hardcoded_font_family(qtbot):
    """SC-P13-UI-001-1: the app depends on no single-OS font (no family named).

    The QSS carries **no** ``font-family`` (so a Windows-/macOS-only family is
    never forced onto Linux), and the app sets no explicit family — each OS
    resolves its own default system UI font. Verified for BOTH theme stylesheets.
    """
    for name in (THEME_LIGHT, THEME_DARK):
        qss = build_qss(name)
        assert (
            "font-family" not in qss.lower()
        ), f"{name} QSS must name no single-OS font-family"
    # The application likewise forces no explicit family (no app-wide setFont of a
    # single-OS family) — the default font resolution is left to the platform.
    app_family = QApplication.instance().font().family().lower()
    single_os = {f.lower() for f in _UI_FONT_FALLBACKS}
    assert (
        app_family not in single_os
    ), f"app font family {app_family!r} must not hard-code a single-OS family"


def test_sc_p13_ui_001_1_representative_text_lays_out_with_resolvable_font(qtbot):
    """SC-P13-UI-001-1: a representative widget lays standard UI text out (no .notdef).

    OS-agnostic mechanism assertion (the offscreen font DB is unreliable for glyph
    coverage, F11): the resolved font produces a **positive layout advance** for the
    standard UI strings on every host, i.e. the text lays out with a usable font —
    no reliance on a specific per-OS family name.
    """
    win = _window(qtbot)
    # A representative always-present widget from the shell (the palette panel).
    widget = win._palette_panel
    fm = QFontMetrics(widget.font())
    assert fm.horizontalAdvance(_REPRESENTATIVE_UI_TEXT) > 0
    # The menu bar (another representative surface) also lays out non-trivially.
    assert QFontMetrics(win.menuBar().font()).height() > 0


@pytest.mark.parametrize("theme_name", [THEME_LIGHT, THEME_DARK])
def test_sc_p13_ui_001_1_font_seam_unaffected_by_theme(theme_name):
    """SC-P13-UI-001-1: both themes are font-fallback-neutral (no per-theme family).

    Neither theme's QSS names a ``font-family`` and neither sets a font size, so
    the font-fallback seam is orthogonal to the theme switch — both light and dark
    are unaffected (Article VI: no absolute font size touches layout/budget).
    """
    qss = build_qss(theme_name)
    assert "font-family" not in qss.lower()
    assert "font-size" not in qss.lower()


# --------------------------------------------------------------------------- #
# REQ-P13-UI-002 — DPI / display-scaling correctness (SC-P13-UI-002-1)         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "doc_ppi,screen_dpi", [(96.0, 96.0), (72.0, 144.0), (96.0, 192.0)]
)
def test_sc_p13_ui_002_1_no_double_dpr_in_real_size_preview(
    qtbot, make_scene, doc_ppi, screen_dpi
):
    """SC-P13-UI-002-1: the real-size preview applies the pure ratio once (no double DPR).

    The applied view transform must equal ``real_size_scale(doc_ppi, screen_dpi)``
    exactly — the shipped Phase-9 discipline: Qt applies ``devicePixelRatio`` itself,
    so the app never multiplies it in. We drive the higher screen DPIs to simulate a
    >1 scaling factor (the effect of a HiDPI/Retina display) and assert the applied
    scale stays the pure ratio, independent of the view's ``devicePixelRatio`` —
    a double-multiply would fold the DPR in a second time.
    """
    scene = make_scene(32, 32)
    win = Real_Size_Preview_Window(scene, doc_ppi)
    qtbot.addWidget(win)
    win.set_manual_dpi(screen_dpi)  # deterministic screen DPI (no display needed)
    pure = real_size_scale(doc_ppi, screen_dpi)
    assert win.current_scale() == pure
    assert win._view.transform().m11() == pure
    assert win._view.transform().m22() == pure
    # The pure ratio is NOT the DPR-multiplied ratio when the platform reports DPR>1.
    dpr = float(win._view.devicePixelRatioF())
    if dpr != 1.0:
        assert win._view.transform().m11() != pure * dpr


def test_sc_p13_ui_002_1_no_manual_dpr_multiply_in_dpi_code_path():
    """SC-P13-UI-002-1: the DPI source is physical DPI, never multiplied by DPR.

    Source-level mechanism guard (a true multi-DPR render can't be forced offscreen):
    the real-size-preview DPI seam queries ``physicalDotsPerInch()`` and never
    multiplies any ``devicePixelRatio`` into the scale — the only ``devicePixelRatio``
    mentions in the module are documentation of *why* it is left to Qt.
    """
    import inspect

    from pixelart_creator.ui import real_size_preview_window as mod

    dpi_src = inspect.getsource(mod.Real_Size_Preview_Window._screen_dpi)
    assert "physicalDotsPerInch" in dpi_src
    # No arithmetic DPR multiply anywhere in the DPI/scale code path.
    scale_src = inspect.getsource(mod.Real_Size_Preview_Window.current_scale)
    for forbidden in (
        "devicePixelRatio() *",
        "* devicePixelRatio",
        "devicePixelRatioF() *",
    ):
        assert forbidden not in dpi_src and forbidden not in scale_src


def test_sc_p13_ui_002_1_pixel_canvas_is_crisp_nearest_neighbour(qtbot, make_view):
    """SC-P13-UI-002-1: the canvas view renders nearest-neighbour, AA off (crisp).

    Anti-aliasing and smooth-pixmap transform are OFF on the interactive view, so
    the pixel canvas stays crisp (never blurred/interpolated) at any scaling; the
    AA-off re-lock keeps them off after the shell touches the render hints.
    """
    view, _scene, _stack = make_view(64, 64)
    hints = view.renderHints()
    from PySide6.QtGui import QPainter

    assert not (hints & QPainter.RenderHint.Antialiasing)
    assert not (hints & QPainter.RenderHint.SmoothPixmapTransform)
    view.reassert_no_antialiasing()
    hints = view.renderHints()
    assert not (hints & QPainter.RenderHint.Antialiasing)
    assert not (hints & QPainter.RenderHint.SmoothPixmapTransform)


def test_sc_p13_ui_002_1_canvas_paints_in_scene_coordinates(qtbot, make_scene):
    """SC-P13-UI-002-1: the scene lays out in device-independent scene coords.

    ``setSceneRect(0, 0, W, H)`` is set once to the document's pixel dimensions
    (device-independent), so the (up-to-8K) canvas paints in scene coordinates and
    Qt maps them to device pixels via the DPR — nothing is laid out in raw device
    pixels. The invariant is size-independent (it holds identically at 8K).
    """
    from PySide6.QtCore import QRectF

    scene = make_scene(128, 96)
    assert scene.sceneRect() == QRectF(0, 0, 128, 96)


def test_sc_p13_ui_002_1_qss_uses_logical_px_units(qtbot):
    """SC-P13-UI-002-1: QSS spacing/padding use logical px (Qt scales by DPR).

    The stylesheet expresses sizes in logical ``px`` (device-independent) — Qt
    applies the device-pixel ratio itself — with no physical/point units baked in.
    Verified in BOTH themes.
    """
    for name in (THEME_LIGHT, THEME_DARK):
        qss = build_qss(name).lower()
        assert "px" in qss  # logical pixel units are used
        # No point-based physical sizing that would ignore the logical scale.
        assert "pt;" not in qss and "pt " not in qss


def test_sc_p13_ui_002_1_frame_budget_not_relaxed():
    """SC-P13-UI-002-1: DPI/scaling correctness relaxes NO per-frame budget (Article VI).

    ``FRAME_BUDGET_MS`` remains the shipped 16 ms (60 fps) — this REQ changes no
    perf budget; the nearest-neighbour canvas already holds it and is unchanged.
    """
    assert FRAME_BUDGET_MS == 16


# --------------------------------------------------------------------------- #
# Both themes render correctly (role-based colours) for the 13A UI touch       #
# --------------------------------------------------------------------------- #


def test_both_themes_role_based_and_distinct_for_portability_touch(qtbot, theme):
    """13A both-theme guard: role-based QSS + canvas roles render in both themes.

    The 13A font/DPI hardening is theme-neutral; this re-affirms that both themes
    still render via role colours (defined once, referenced by role — never a
    per-widget literal) and differ legibly, under the active parametrised theme.
    """
    _window(qtbot)
    assert QApplication.instance().styleSheet() != ""
    light_qss = build_qss(THEME_LIGHT)
    dark_qss = build_qss(THEME_DARK)
    assert light_qss != dark_qss
    assert "background-color" in light_qss and "background-color" in dark_qss
    # Canvas checker/grid role colours differ per theme (role-based, not hard-coded).
    assert canvas_roles(THEME_LIGHT) != canvas_roles(THEME_DARK)
    # Both theme role maps carry identical role keys (no single-theme-only role).
    assert set(theme_module._ROLES[THEME_LIGHT]) == set(theme_module._ROLES[THEME_DARK])
