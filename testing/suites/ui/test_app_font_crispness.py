# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Nifen Art is drawn pixel-exact by the running Qt platform (REQ-VI-UI-014).

Acceptance scenario SC-VI-UI-014-1: with smoothing and hinting off, rendering
the bundled Nifen Art fonts at 12 px and 24 px (whole multiples of the 12 px
em) gives **0 non-binary pixels** and **0 mismatches against the source grid**,
and the number of glyphs and pixels examined is printed and is not zero.

What is measured
----------------
Each glyph is rendered alone by Qt from the built TTF, in black on white in an
opaque ``QImage`` at device pixel ratio 1, and compared with the glyph's source
grid (``fonts-src/nifen-art``) scaled by the integer ``size / em``:

* a **non-binary pixel** is any pixel that is not pure black or pure white
  (grey from smoothing, or a coloured fringe from sub-pixel text);
* a **mismatch** is a pixel whose lit/unlit state differs from the grid.

The font is loaded straight from ``pixelart_creator/fonts`` through
``QFontDatabase`` and drawn with ``QFont.NoAntialias`` + ``PreferNoHinting``
while the painter's ``TextAntialiasing`` hint is left ON, which is how a widget
painter reaches the font: the font's own strategy alone must keep the text
crisp.

The instrument carries its own controls (a probe that cannot show a known-true
and a known-false signal proves nothing):

* positive control: the grid painted directly with integer rectangles and
  antialiasing off must give 0 non-binary and 0 mismatches;
* negative control: the same grid painted antialiased at a half-pixel offset
  must be detected in every glyph;
* the catching assertion is itself shown to FIRE on a planted defect: an
  antialiased font render and a fractional font size.

Where it runs
-------------
Every test carries the ``native_font`` marker. It runs on whatever Qt platform
the process has: headless ``offscreen`` in the default suite (where the
native-platform guard below is skipped, with its reason, and counted), and on a
real platform plugin (``windows``, ``cocoa``, ``xcb`` ...) when selected with
``-m native_font`` and ``QT_QPA_PLATFORM`` set to that plugin (the suite's
``conftest.py`` only *defaults* to ``offscreen``). A run that selects
``native_font`` but is on a non-native platform FAILS in
``test_native_platform_was_examined``; a run that examines zero glyphs or zero
pixels fails in :func:`require_examined`. Nothing here makes a claim about a
platform the process was not on: every printed line names the platform.

Run the native leg, for example::

    QT_QPA_PLATFORM=windows python -m pytest -m native_font \
        testing/suites/ui/test_app_font_crispness.py -p no:cacheprovider -rs

The ``theme`` fixture is overridden below: the measurement paints black on
white into an image and never touches a styled widget, so the light/dark
doubling of the suite's autouse fixture would only repeat identical work.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, qVersion
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontInfo,
    QGuiApplication,
    QImage,
    QPainter,
)

pytestmark = pytest.mark.native_font

from testing.suites.ui.test_app_font import (  # noqa: E402,F401  (fixtures used by name)
    _leave_the_font_as_found,
    _store_is_isolated,
    class_font_problems,
    mode,
    nifen_problems,
    open_window,
)

# --------------------------------------------------------------------------- #
# Locations (resolved from this file; nothing is read from the working dir).   #
# --------------------------------------------------------------------------- #

_ROOT = Path(__file__).resolve().parents[3]
_FONT_DIR = _ROOT / "pixelart_creator" / "fonts"
_SRC_DIR = _ROOT / "fonts-src" / "nifen-art"
_SRC_LIB = _ROOT / "scripts" / "font" / "nifen_src.py"

_REGULAR_TTF = _FONT_DIR / "NifenArt-Regular.ttf"
_BOLD_TTF = _FONT_DIR / "NifenArt-Bold.ttf"

#: The family name both bundled faces register under.
FAMILY = "Nifen Art"

#: Platform plugins that are NOT a native display (nothing real is drawn to).
NON_NATIVE_PLATFORMS = frozenset({"offscreen", "minimal", "minimalegl", "vnc", "webgl"})

#: Default-ignorable codepoints: text shaping draws nothing for them, so a
#: glyph-by-glyph comparison cannot apply. Excluded by name, never silently.
IGNORABLE_CPS = frozenset({0x00AD})

WEIGHTS = ("regular", "bold")

#: SC-VI-UI-014-1 sizes: one and two ems (asserted against the declared em below).
_SIZES = (12, 24)

# --------------------------------------------------------------------------- #
# The source grid (a stdlib-only module of the repo, loaded by path).          #
# --------------------------------------------------------------------------- #


def _load_nifen_src():
    """Import ``scripts/font/nifen_src.py`` by path, under a private module name."""
    name = "_crispness_nifen_src"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SRC_LIB)
    assert spec is not None and spec.loader is not None, f"cannot load {_SRC_LIB}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module through here
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class GlyphGrid:
    """One glyph's source grid in one weight."""

    cp: int
    pixels: frozenset
    advance: int


@dataclass(frozen=True)
class Metrics:
    """The figures of the grid contract this module depends on."""

    em_px: int
    ascent_px: int
    descent_px: int

    @property
    def line_px(self) -> int:
        return self.ascent_px + self.descent_px


@dataclass
class Model:
    """The source of truth the renders are compared with."""

    metrics: Metrics
    grids: Dict[str, List[GlyphGrid]]  # weight -> non-empty glyph grids
    empty: Dict[str, int]  # weight -> codepoints with no ink (not renderable)


@pytest.fixture(scope="module")
def model() -> Model:
    """Parse the source grids once: every codepoint, both weights."""
    lib = _load_nifen_src()
    font = lib.Font(lib.parse_sources(str(_SRC_DIR)))
    raw = font.srcs.metrics
    metrics = Metrics(
        em_px=int(raw["em_px"]),
        ascent_px=int(raw["line_ascent_px"]),
        descent_px=int(raw["line_descent_px"]),
    )
    cps = [cp for cp in font.codepoints() if cp not in IGNORABLE_CPS]
    grids: Dict[str, List[GlyphGrid]] = {w: [] for w in WEIGHTS}
    empty: Dict[str, int] = {w: 0 for w in WEIGHTS}
    for weight in WEIGHTS:
        for cp in cps:
            bmp = font.bmp(cp, weight)
            if not bmp.px:
                empty[weight] += 1
                continue
            grids[weight].append(GlyphGrid(cp, frozenset(bmp.px), int(bmp.adv)))
    return Model(metrics, grids, empty)


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture: this measurement is theme-free."""
    return "none"


@pytest.fixture(scope="module")
def loaded_fonts(qapp) -> Iterator[Dict[str, int]]:
    """Register both bundled faces with ``QFontDatabase`` and remove them afterwards."""
    ids: Dict[str, int] = {}
    for weight, path in (("regular", _REGULAR_TTF), ("bold", _BOLD_TTF)):
        assert path.is_file(), f"bundled font missing: {path}"
        ident = QFontDatabase.addApplicationFont(str(path))
        assert ident >= 0, f"Qt could not load {path.name} on {_platform()}"
        families = QFontDatabase.applicationFontFamilies(ident)
        assert (
            FAMILY in families
        ), f"{path.name} registered as {families}, not {FAMILY!r}"
        ids[weight] = ident
    try:
        yield ids
    finally:
        for ident in ids.values():
            QFontDatabase.removeApplicationFont(ident)


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RenderSpec:
    """How the font is asked to be drawn."""

    strategy: QFont.StyleStrategy
    hinting: QFont.HintingPreference
    text_antialiasing_hint: bool = True


#: What the product asks for: no smoothing, no hinting adjustments.
CRISP = RenderSpec(
    QFont.StyleStrategy.NoAntialias, QFont.HintingPreference.PreferNoHinting
)
#: A planted defect: the font asks for smoothing.
SMOOTH = RenderSpec(
    QFont.StyleStrategy.PreferAntialias, QFont.HintingPreference.PreferNoHinting
)

_BLACK = QColor(0, 0, 0)
_WHITE = QColor(255, 255, 255)


def _platform() -> str:
    return QGuiApplication.platformName()


def _geometry(metrics: Metrics, advance: int, k: int) -> Tuple[int, int, int, int]:
    """Return ``(pad, width, height, baseline)`` for one glyph at scale ``k``."""
    pad = 2 * k
    width = advance * k + 2 * pad
    height = metrics.line_px * k + 2 * pad
    baseline = pad + metrics.ascent_px * k
    return pad, width, height, baseline


def _expected_mask(metrics: Metrics, glyph: GlyphGrid, k: int) -> np.ndarray:
    pad, width, height, baseline = _geometry(metrics, glyph.advance, k)
    mask = np.zeros((height, width), dtype=bool)
    for x, y in glyph.pixels:
        mask[
            baseline - (y + 1) * k : baseline - y * k,
            pad + x * k : pad + (x + 1) * k,
        ] = True
    return mask


def _as_rgb(image: QImage) -> np.ndarray:
    width, height = image.width(), image.height()
    raw = np.frombuffer(image.constBits(), dtype=np.uint8)
    return (
        raw.reshape(height, image.bytesPerLine())[:, : width * 4]
        .reshape(height, width, 4)[:, :, :3]
        .copy()
    )


def _make_font(family: str, weight: str, px: int, spec: RenderSpec) -> QFont:
    font = QFont(family)
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.Bold if weight == "bold" else QFont.Weight.Normal)
    font.setStyleStrategy(spec.strategy)
    font.setHintingPreference(spec.hinting)
    return font


def _blank(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.setDevicePixelRatio(1.0)
    image.fill(_WHITE)
    return image


def render_text(
    metrics: Metrics, glyph: GlyphGrid, weight: str, px: int, k: int, spec: RenderSpec
) -> np.ndarray:
    """Draw one glyph with the real font and return its RGB array."""
    pad, width, height, baseline = _geometry(metrics, glyph.advance, k)
    image = _blank(width, height)
    painter = QPainter(image)
    painter.setFont(_make_font(FAMILY, weight, px, spec))
    painter.setRenderHint(
        QPainter.RenderHint.TextAntialiasing, spec.text_antialiasing_hint
    )
    painter.setPen(_BLACK)
    painter.drawText(QPointF(pad, baseline), chr(glyph.cp))
    painter.end()
    return _as_rgb(image)


def render_grid(
    metrics: Metrics, glyph: GlyphGrid, k: int, antialias: bool
) -> np.ndarray:
    """Paint the source grid directly (the controls): no font is involved."""
    pad, width, height, baseline = _geometry(metrics, glyph.advance, k)
    image = _blank(width, height)
    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_BLACK)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, antialias)
    if antialias:
        painter.translate(0.5, 0.5)  # a half-pixel offset: every edge straddles pixels
        for x, y in glyph.pixels:
            painter.drawRect(QRectF(pad + x * k, baseline - (y + 1) * k, k, k))
    else:
        for x, y in glyph.pixels:
            painter.fillRect(QRect(pad + x * k, baseline - (y + 1) * k, k, k), _BLACK)
    painter.end()
    return _as_rgb(image)


# --------------------------------------------------------------------------- #
# Counting                                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class Tally:
    """Counts with their denominators."""

    label: str
    glyphs: int = 0
    pixels: int = 0
    nonbinary: int = 0
    mismatch: int = 0
    glyphs_with_nonbinary: int = 0
    glyphs_with_mismatch: int = 0

    def add(self, rgb: np.ndarray, expected: np.ndarray) -> None:
        black = np.all(rgb == 0, axis=2)
        white = np.all(rgb == 255, axis=2)
        nonbinary = int((~(black | white)).sum())
        mismatch = int(((rgb[:, :, 1] < 128) != expected).sum())
        self.glyphs += 1
        self.pixels += int(rgb.shape[0] * rgb.shape[1])
        self.nonbinary += nonbinary
        self.mismatch += mismatch
        self.glyphs_with_nonbinary += 1 if nonbinary else 0
        self.glyphs_with_mismatch += 1 if mismatch else 0

    def line(self) -> str:
        return (
            f"{self.label}: glyphs examined {self.glyphs}, "
            f"pixels examined {self.pixels}, non-binary pixels {self.nonbinary} "
            f"(in {self.glyphs_with_nonbinary} glyphs), "
            f"mismatched pixels {self.mismatch} (in {self.glyphs_with_mismatch} glyphs)"
        )


#: Running totals, for the closing line. Informational only: under a
#: process-parallel run each worker sees its own share, and no verdict depends
#: on them (every verdict is taken per measurement, in :func:`require_examined`).
_TOTALS = {"measurements": 0, "glyphs": 0, "pixels": 0}


def require_examined(tally: Tally) -> Tally:
    """Fail when a measurement examined nothing: zero is not a pass."""
    assert (
        tally.glyphs > 0
    ), f"{tally.label}: examined 0 glyphs - the measurement saw nothing"
    assert (
        tally.pixels > 0
    ), f"{tally.label}: examined 0 pixels - the measurement saw nothing"
    _TOTALS["measurements"] += 1
    _TOTALS["glyphs"] += tally.glyphs
    _TOTALS["pixels"] += tally.pixels
    return tally


def assert_pixel_exact(tally: Tally) -> None:
    """The catching assertion: examined > 0, 0 non-binary pixels, 0 mismatches."""
    require_examined(tally)
    assert tally.nonbinary == 0, f"{tally.line()} -> non-binary pixels must be 0"
    assert (
        tally.mismatch == 0
    ), f"{tally.line()} -> mismatches against the source grid must be 0"


def _say(capsys: pytest.CaptureFixture, text: str) -> None:
    """Print a line that reaches the terminal even without ``-s``."""
    with capsys.disabled():
        print(f"\n[native_font] {text}", flush=True)


def measure_font(
    model: Model,
    weight: str,
    px: int,
    spec: RenderSpec,
    *,
    label: str,
    k: Optional[int] = None,
) -> Tally:
    """Render every glyph with the real font at ``px``; tally it against scale ``k``."""
    scale = k if k is not None else px // model.metrics.em_px
    tally = Tally(label)
    for glyph in model.grids[weight]:
        rgb = render_text(model.metrics, glyph, weight, px, scale, spec)
        tally.add(rgb, _expected_mask(model.metrics, glyph, scale))
    return tally


def measure_grid(
    model: Model, weight: str, k: int, *, antialias: bool, label: str
) -> Tally:
    """Paint every source grid directly (no font) and tally it the same way."""
    tally = Tally(label)
    for glyph in model.grids[weight]:
        rgb = render_grid(model.metrics, glyph, k, antialias)
        tally.add(rgb, _expected_mask(model.metrics, glyph, k))
    return tally


def _is_native_run_requested(config: pytest.Config) -> bool:
    """True when the ``native_font`` marker was selected with ``-m``."""
    expr = config.getoption("markexpr", default="") or ""
    return "native_font" in expr and "not native_font" not in expr


@pytest.fixture(scope="module")
def font_path_shows_smoothing(model: Model, loaded_fonts) -> bool:
    """Whether this platform's font path shows smoothing when the font asks for it.

    The font-level negative control. A platform that never smooths text, even on
    request (the headless ``offscreen`` plugin on Windows does not), cannot
    demonstrate that the non-binary count would notice smoothing there, so on
    such a platform that count is reported as uninformative instead of being
    passed off as a measurement.
    """
    probe = measure_font(
        model, "regular", 12, SMOOTH, label="font-path smoothing control"
    )
    return require_examined(probe).nonbinary > 0


# --------------------------------------------------------------------------- #
# Environment and platform                                                     #
# --------------------------------------------------------------------------- #


def test_environment_is_recorded(qapp, capsys, model: Model) -> None:
    """Print what this run is measuring on, and refuse an empty source model."""
    import PySide6

    screen = qapp.primaryScreen()
    env = {k: v for k, v in sorted(os.environ.items()) if k.startswith("QT_")}
    _say(
        capsys,
        f"platform={_platform()} Qt={qVersion()} PySide6={PySide6.__version__} "
        f"python={sys.version.split()[0]} screen_dpr={screen.devicePixelRatio():.2f} "
        f"logical_dpi={screen.logicalDotsPerInch():.1f} env={env or '{}'}",
    )
    _say(
        capsys,
        f"source grids: em {model.metrics.em_px} px, "
        f"line box {model.metrics.line_px} px "
        f"(ascent {model.metrics.ascent_px}, descent {model.metrics.descent_px}); "
        f"regular {len(model.grids['regular'])} glyphs with ink "
        f"({model.empty['regular']} without), bold {len(model.grids['bold'])} "
        f"({model.empty['bold']} without); excluded as default-ignorable: "
        f"{', '.join('U+%04X' % c for c in sorted(IGNORABLE_CPS))}",
    )
    assert model.grids["regular"], "no Regular glyph was read from the source grids"
    assert model.grids["bold"], "no Bold glyph was read from the source grids"
    assert model.metrics.em_px == 12 and model.metrics.line_px == 14


def test_native_platform_was_examined(
    qapp, capsys, request: pytest.FixtureRequest
) -> None:
    """A run that selects ``native_font`` must be on a native platform plugin.

    In the default suite (offscreen) there is no native display to examine:
    that is a counted skip with its reason, not a silent pass. A native run
    (``-m native_font``) that ended up on a non-native plugin examined no
    platform at all and fails.
    """
    name = _platform()
    native = name not in NON_NATIVE_PLATFORMS
    _say(capsys, f"platform plugin in use: {name!r} (native display: {native})")
    if _is_native_run_requested(request.config):
        assert native, (
            "native run requested (-m native_font) but the platform plugin is "
            f"{name!r}: "
            "no native platform was examined. Set QT_QPA_PLATFORM to the real plugin "
            "(windows, cocoa, xcb ...) on a machine with a display."
        )
    elif not native:
        pytest.skip(
            f"platform plugin {name!r} is not a native display; the native leg is "
            "selected with -m native_font and QT_QPA_PLATFORM set to a real plugin"
        )


# --------------------------------------------------------------------------- #
# The instrument's controls                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("weight", WEIGHTS)
@pytest.mark.parametrize("k", [1, 2], ids=["12px", "24px"])
def test_positive_control_grid_painted_directly_is_pixel_exact(
    model: Model, capsys, weight: str, k: int
) -> None:
    """SC-VI-UI-014-1 control: a directly painted grid has 0 non-binary, 0 mismatch."""
    tally = measure_grid(
        model, weight, k, antialias=False, label=f"POSITIVE control {weight} grid x{k}"
    )
    _say(capsys, f"{_platform()} {tally.line()}")
    assert_pixel_exact(tally)


@pytest.mark.parametrize("weight", WEIGHTS)
@pytest.mark.parametrize("k", [1, 2], ids=["12px", "24px"])
def test_negative_control_antialiased_grid_is_detected_in_every_glyph(
    model: Model, capsys, weight: str, k: int
) -> None:
    """SC-VI-UI-014-1 control: the same grid painted antialiased is seen as smoothed."""
    tally = require_examined(
        measure_grid(
            model,
            weight,
            k,
            antialias=True,
            label=f"NEGATIVE control {weight} grid x{k}",
        )
    )
    _say(capsys, f"{_platform()} {tally.line()}")
    assert (
        tally.nonbinary > 0
    ), f"{tally.line()} -> the instrument is blind to smoothing"
    assert tally.glyphs_with_nonbinary == tally.glyphs, (
        f"{tally.line()} -> smoothing missed in "
        f"{tally.glyphs - tally.glyphs_with_nonbinary} glyphs"
    )


# --------------------------------------------------------------------------- #
# The catching assertion fires on planted defects                              #
# --------------------------------------------------------------------------- #


def test_catching_assertion_fires_on_a_planted_antialiased_font_render(
    model: Model, loaded_fonts, capsys, request: pytest.FixtureRequest
) -> None:
    """Planted defect 1: the font is drawn with smoothing; the catching assertion fires.

    Where the platform never smooths text even when asked, the control cannot
    fire, and that is stated: a counted skip in the default suite, a failure in
    a native run (a native platform whose font path is blind to smoothing has
    not been shown to be crisp).
    """
    tally = require_examined(
        measure_font(
            model, "regular", 12, SMOOTH, label="PLANTED smoothing, regular 12px"
        )
    )
    _say(capsys, f"{_platform()} {tally.line()}")
    if tally.nonbinary == 0:
        reason = (
            f"platform plugin {_platform()!r} drew {tally.glyphs} glyphs with "
            "smoothing requested and produced 0 non-binary pixels: its font path "
            "never smooths, so "
            "the non-binary count cannot be shown to fire here"
        )
        if _is_native_run_requested(request.config):
            pytest.fail(reason)
        pytest.skip(reason)
    with pytest.raises(AssertionError, match="non-binary pixels must be 0"):
        assert_pixel_exact(tally)


@pytest.mark.parametrize("px", [11, 13])
def test_catching_assertion_fires_on_a_planted_fractional_size(
    model: Model, loaded_fonts, capsys, px: int
) -> None:
    """Planted defect 2: a size that is not a multiple of the em must be caught."""
    em = model.metrics.em_px
    assert (
        px % em != 0
    ), "a fractional-size plant must not be a whole multiple of the em"
    tally = require_examined(
        measure_font(
            model, "regular", px, CRISP, k=1, label=f"PLANTED fractional {px}px regular"
        )
    )
    _say(capsys, f"{_platform()} {tally.line()}")
    assert tally.mismatch > 0, f"{tally.line()} -> a fractional size went undetected"
    with pytest.raises(
        AssertionError, match="mismatches against the source grid must be 0"
    ):
        assert_pixel_exact(tally)


def test_zero_examined_fails() -> None:
    """A measurement that saw nothing is a failure, never a pass."""
    with pytest.raises(AssertionError, match="examined 0 glyphs"):
        require_examined(Tally("EMPTY"))
    with pytest.raises(AssertionError, match="examined 0 pixels"):
        require_examined(Tally("NO PIXELS", glyphs=1))
    with pytest.raises(AssertionError, match="examined 0 glyphs"):
        assert_pixel_exact(Tally("EMPTY"))


# --------------------------------------------------------------------------- #
# Item views: colour fringe and the platform's per-class fonts                  #
# --------------------------------------------------------------------------- #
#
# On native Windows the rows of an item view (``QListWidget``, ``QTreeWidget``,
# ``QTableWidget``) were drawn in the platform font with sub-pixel (ClearType)
# smoothing, which puts blue and yellow fringes around every glyph, while labels
# were clean. The cause: the platform theme gives some widget classes a font of
# their own, and the first style sheet (or any ``setStyle``) writes those back
# over the application font. The tests below measure the fringe itself, with a
# clean-widget control (a ``QLabel`` with the same string) and a known-true signal
# (the platform font in the same views must fringe, or the instrument is blind),
# and check what the platform's per-class fonts do after a style sheet.
#
# The fringe measurement runs in the default headless suite as well (it must find
# 0 there too); the two tests that need the platform to PUT fonts back and to
# fringe are meaningful only on a native plugin: in the default suite they are
# counted skips with their reason, and in a ``-m native_font`` run on a
# non-native platform they FAIL.

_SAMPLE = "Hamburgefonstiv Layers 0123"
_ROWS = 3


def _require_native_or_skip(request: pytest.FixtureRequest, what: str) -> None:
    """Skip (counted, with the reason) off a native platform; FAIL if native was asked for."""
    name = _platform()
    native = name not in NON_NATIVE_PLATFORMS
    if _is_native_run_requested(request.config):
        assert native, (
            f"native run requested (-m native_font) but the platform plugin is {name!r}: "
            f"{what} was not examined on a native platform"
        )
    elif not native:
        pytest.skip(
            f"{what} is meaningful only on a native platform plugin (the platform theme "
            f"gives widget classes their own fonts and smooths text there); the current "
            f"plugin is {name!r}. Run it with -m native_font and QT_QPA_PLATFORM set to a "
            f"real plugin."
        )


@dataclass
class Fringe:
    """What one text rendering put on the screen."""

    kind: str
    text_px: int
    fringe_px: int
    ink: Optional[Tuple[int, ...]]

    def line(self) -> str:
        return (
            f"{self.kind}: text pixels examined {self.text_px}, off-ink/off-ground "
            f"(fringe) pixels {self.fringe_px}, ink {self.ink}"
        )


def _array_of(widget) -> np.ndarray:
    image = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    return (
        np.frombuffer(image.constBits(), dtype=np.uint8)
        .reshape(height, image.bytesPerLine())[:, : width * 4]
        .reshape(height, width, 4)[..., :3]
        .copy()
    )


def measure_fringe(kind: str, widget, fill) -> Fringe:
    """Render ``widget`` with empty text and with the sample; classify the text pixels.

    The pixels that differ between the two renderings are the text. The ink is the
    most common colour among them; the ground is every colour the empty rendering
    shows in the same box. A text pixel that is neither is a fringe pixel (what
    sub-pixel smoothing puts around a glyph).
    """
    from collections import Counter

    from PySide6.QtWidgets import QApplication

    fill(widget, "")
    QApplication.processEvents()
    empty = _array_of(widget)
    fill(widget, _SAMPLE)
    QApplication.processEvents()
    texted = _array_of(widget)
    assert empty.shape == texted.shape
    diff = (texted != empty).any(axis=2)
    text_px = int(diff.sum())
    if text_px == 0:
        return Fringe(kind, 0, 0, None)
    ys, xs = np.nonzero(diff)
    box = (
        slice(int(ys.min()), int(ys.max()) + 1),
        slice(int(xs.min()), int(xs.max()) + 1),
    )
    ground = {tuple(int(c) for c in px) for px in empty[box].reshape(-1, 3)}
    colours = Counter(tuple(int(c) for c in px) for px in texted[diff])
    ink = colours.most_common(1)[0][0]
    fringe = sum(
        n for colour, n in colours.items() if colour != ink and colour not in ground
    )
    return Fringe(kind, text_px, int(fringe), ink)


def _make_views(parent):
    """Return ``(kind, widget, fill)`` for a list, a tree, a table and the QLabel control."""
    from PySide6.QtWidgets import (
        QLabel,
        QListWidget,
        QTableWidget,
        QTableWidgetItem,
        QTreeWidget,
        QTreeWidgetItem,
    )

    def fill_list(view, text):
        view.clear()
        for _ in range(_ROWS):
            view.addItem(text)

    def fill_tree(view, text):
        view.clear()
        for _ in range(_ROWS):
            view.addTopLevelItem(QTreeWidgetItem([text]))

    def fill_table(view, text):
        for row in range(_ROWS):
            view.setItem(row, 0, QTableWidgetItem(text))

    def fill_label(label, text):
        label.setText(text)

    lst = QListWidget(parent)
    tree = QTreeWidget(parent)
    tree.setHeaderHidden(True)
    table = QTableWidget(_ROWS, 1, parent)
    table.horizontalHeader().hide()
    table.verticalHeader().hide()
    label = QLabel(parent)
    views = [
        ("list", lst, fill_list),
        ("tree", tree, fill_tree),
        ("table", table, fill_table),
        ("label (control)", label, fill_label),
    ]
    for _kind, widget, _fill in views:
        widget.setWindowFlag(Qt.WindowType.Window, True)
        widget.resize(192, 82)
        widget.show()
    table.setColumnWidth(0, 180)
    return views


def test_item_view_rows_are_nifen_art_and_show_no_colour_fringe(
    qtbot, capsys, mode, request: pytest.FixtureRequest
) -> None:
    """List, tree and table rows have 0 fringe pixels; the QLabel control has 0 too.

    The window is built through the product's own start-up (font, style sheet,
    font re-applied), then a list, a tree and a table are shown with the same
    string in 192 x 82 boxes. The rows' text is measured and the delegate's
    option font is asserted Nifen Art, so a view whose rows are not in the pixel
    font fails even where it happens not to fringe. The number of text pixels
    examined is printed and must not be zero. A fringed item view FAILS the test;
    nothing is skipped or tolerated.
    """
    from testing.suites.ui.test_app_font import _option_font

    win = open_window(qtbot, mode, settle=False)
    views = _make_views(win)
    results: List[Fringe] = []
    for kind, widget, fill in views:
        qtbot.addWidget(widget)
        result = measure_fringe(kind, widget, fill)
        results.append(result)
        _say(capsys, f"{_platform()} [{mode}] {result.line()}")
    for result in results:
        assert (
            result.text_px > 0
        ), f"{result.kind}: the text drew nothing: {result.line()}"
    wrong = [r.line() for r in results if r.fringe_px > 0]
    assert not wrong, "colour-fringed text in an item view: " + "; ".join(wrong)
    for kind, widget, fill in views[:3]:
        fill(widget, _SAMPLE)
        problems = nifen_problems(f"{kind} row font", _option_font(widget))
        assert not problems, problems


def test_the_fringe_instrument_sees_the_platform_font_fringe_natively(
    qtbot, capsys, mode, request: pytest.FixtureRequest
) -> None:
    """Known-true signal: with "Use system font" the same views DO fringe, natively.

    A measurement that has never been shown to find a fringe proves nothing by
    finding none. On a native platform the platform font's rows are drawn with
    sub-pixel smoothing, so the same list, tree and table with the platform font
    must show fringe pixels; none means the instrument is blind here (or the
    display has smoothing switched off) and the test fails. Off a native platform
    this is a counted skip.
    """
    _require_native_or_skip(request, "the fringe control")
    win = open_window(qtbot, mode, use_system_font=True, settle=False)
    views = _make_views(win)
    seen = 0
    for kind, widget, fill in views[:3]:
        qtbot.addWidget(widget)
        result = measure_fringe(kind, widget, fill)
        _say(capsys, f"{_platform()} [{mode}] PLATFORM FONT {result.line()}")
        assert result.text_px > 0
        seen += result.fringe_px
    assert (
        seen > 0
    ), "the platform font showed no fringe in any item view: the instrument is blind"


def test_item_views_menus_and_dock_titles_stay_nifen_art_after_a_style_sheet_natively(
    qtbot, capsys, mode, request: pytest.FixtureRequest
) -> None:
    """Class-font regression: after a style sheet, item views, menus and dock titles are Nifen Art.

    Native only. The window is built through the product's start-up, so its first
    style sheet is the one that makes the platform write its per-class fonts back;
    item views, menus, the menu bar, tool tips and dock titles are then examined
    (the per-class font table, fresh widgets, the real window's roles). The control
    clears and restores the style sheet, which makes the platform put those fonts
    back: the same examination MUST flag it (otherwise the platform does not do
    what this regression is about and the check proves nothing here, so the test fails), and
    ``ensure_interface_font`` must undo it. Off a native platform: a counted skip,
    or a failure when ``-m native_font`` selected it.
    """
    from PySide6.QtWidgets import QApplication, QDockWidget, QMenu

    from pixelart_creator.ui import app_font

    _require_native_or_skip(request, "the per-class font regression")
    win = open_window(qtbot, mode, settle=False)
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    def real_roles() -> List[str]:
        wrong: List[str] = []
        wrong.extend(nifen_problems("menu bar", win.menuBar().font()))
        for top in win.menuBar().actions():
            menu = top.menu()
            if isinstance(menu, QMenu):
                menu.ensurePolished()
                wrong.extend(nifen_problems(f"menu {top.text()!r}", menu.font()))
        for dock in win.findChildren(QDockWidget):
            wrong.extend(
                nifen_problems(f"dock {dock.windowTitle()!r}", dock.font(), bold=True)
            )
        wrong.extend(nifen_problems("layer tree", win._layer_panel._tree.font()))
        return wrong

    before = class_font_problems(app, win) + real_roles()
    _say(
        capsys,
        f"{_platform()} [{mode}] after the product's own first style sheet: "
        f"{len(before)} problems",
    )
    assert not before, "after the first style sheet:\n  " + "\n  ".join(before[:20])

    sheet = app.styleSheet()
    assert sheet, "the application carries no style sheet"
    app.setStyleSheet("")
    app.setStyleSheet(sheet)
    QApplication.processEvents()
    flagged = class_font_problems(app, win)
    _say(
        capsys,
        f"{_platform()} [{mode}] CONTROL (style sheet cleared and restored): "
        f"{len(flagged)} problems",
    )
    assert flagged, (
        "the platform did not put its per-class fonts back after the style sheet was "
        "cleared and restored: this check cannot see this regression here"
    )
    app_font.ensure_interface_font(app, False)
    QApplication.processEvents()
    after = class_font_problems(app, win)
    assert (
        not after
    ), "ensure_interface_font left per-class fonts behind:\n  " + "\n  ".join(
        after[:20]
    )


# --------------------------------------------------------------------------- #
# The real measurement                                                         #
# --------------------------------------------------------------------------- #


def test_sizes_are_whole_multiples_of_the_em(model: Model) -> None:
    """REQ-VI-UI-014: the sizes under test are 1x and 2x the em of the grid contract."""
    em = model.metrics.em_px
    assert _SIZES == (em, 2 * em)
    assert all(px % em == 0 for px in _SIZES)


@pytest.mark.parametrize("weight", WEIGHTS)
@pytest.mark.parametrize("px", [12, 24], ids=["12px", "24px"])
def test_loaded_face_is_nifen_art_at_the_requested_pixel_size(
    qapp, loaded_fonts, weight: str, px: int
) -> None:
    """The font under test is Nifen Art at exactly ``px``, not a substitute."""
    info = QFontInfo(_make_font(FAMILY, weight, px, CRISP))
    assert (
        info.family() == FAMILY
    ), f"Qt resolved {FAMILY!r} to {info.family()!r} on {_platform()}"
    assert info.pixelSize() == px, f"asked {px} px, Qt resolved {info.pixelSize()} px"
    assert info.bold() == (
        weight == "bold"
    ), f"{weight}: Qt resolved bold={info.bold()}"


@pytest.mark.parametrize("weight", WEIGHTS)
@pytest.mark.parametrize("px", _SIZES, ids=["12px", "24px"])
def test_nifen_art_is_pixel_exact(
    model: Model,
    loaded_fonts,
    font_path_shows_smoothing: bool,
    capsys,
    weight: str,
    px: int,
) -> None:
    """SC-VI-UI-014-1: 0 non-binary pixels and 0 mismatches at 12 px and 24 px.

    ``NoAntialias`` + ``PreferNoHinting``; every glyph of the declared set with
    ink, in this weight. The counts and what they were taken over are printed.
    """
    started = time.perf_counter()
    tally = measure_font(model, weight, px, CRISP, label=f"NIFEN ART {weight} {px}px")
    elapsed = time.perf_counter() - started
    sensitivity = (
        "smoothing control fires on this font path"
        if font_path_shows_smoothing
        else "smoothing control does NOT fire on this font path: the non-binary figure "
        "is not informative here, the mismatch figure still is"
    )
    _say(capsys, f"{_platform()} {tally.line()} [{elapsed:.2f} s] ({sensitivity})")
    assert_pixel_exact(tally)


def test_zz_totals_were_not_zero(capsys) -> None:
    """Closing line: what this process examined in total (informational under -n)."""
    _say(
        capsys,
        f"{_platform()} TOTAL in this process: {_TOTALS['measurements']} measurements, "
        f"{_TOTALS['glyphs']} glyphs, {_TOTALS['pixels']} pixels examined",
    )
    if "PYTEST_XDIST_WORKER" not in os.environ:
        assert _TOTALS["measurements"] > 0, "this module examined nothing"
        assert _TOTALS["glyphs"] > 0 and _TOTALS["pixels"] > 0
