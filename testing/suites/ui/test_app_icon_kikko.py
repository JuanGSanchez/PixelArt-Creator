"""The Kikko Badge wherever the app shows its icon (T053; SC-VI-UI-018-1, REQ-VI-UI-018).

``test_app_icon.py`` owns the loader's contract (eight discrete sizes, degrade-and-log on a
missing or undecodable asset); it is unchanged and must still pass. This module owns the
IDENTITY of what is shown: the window icon, the About dialog's icon and the user guide's
logo must be PIXEL-EQUAL to members of the family the deriver derives from the five
hand-drawn Kikko Badge masters.

"Derived members" are computed here, fresh, by the deriver's own functions
(``scripts/derive_app_icons.py``: ``load_masters`` + ``render_all``) from the committed
masters, NOT read back from the committed ``app-icon-*.png`` files. A committed member that
had drifted from its masters would therefore be caught here as well as by the deriver's
``--check``; and the committed bytes cannot vouch for themselves.

Comparison is by decoded pixels (RGBA, with the RGB of fully transparent pixels ignored),
never by encoded bytes: re-encoded PNG bytes depend on the platform's zlib/libpng.

Controls (a comparison that cannot fail proves nothing):

* the previous brand's ``logo-source-64.png`` (still in the folder, a different image) must
  MISMATCH the Kikko member of the same size -- the comparator tells the two logos apart;
* a planted state redirects the loader to a scratch directory whose ``app-icon-*.png`` files
  are the previous brand's: every shown icon must then fail the comparison;
* an About dialog whose icon is not a family member size (a scaled pixmap) is reported.

Both modes: the suite's two-way ``theme`` fixture applies Light and Dark to the application
for every test here (the icon carries no theme axis; the About dialog is built for the
mode under test). Scratch files live under ``tmp_path``; no committed asset is touched.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon, QImage, QTextDocument

import pixelart_creator.ui.app_icon as app_icon_module
import scripts.derive_app_icons as derive_app_icons
from pixelart_creator.ui.app import create_app
from pixelart_creator.ui.app_icon import (
    RUNTIME_ICON_SIZES_PX,
    guide_logo_image,
)
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui.focus_helpers import image_array

_REPO_ROOT = Path(__file__).resolve().parents[3]
_APP_DIR = _REPO_ROOT / "pixelart_creator" / "icons" / "app"
_OLD_BRAND = _APP_DIR / "logo-source-64.png"

_GUIDE_LOGO_RESOURCE = "pac-logo.png"
_GUIDE_TOPIC = "app-basics"
_GUIDE_LOGO_MEMBER = "app-icon-128.png"


@pytest.fixture(autouse=True)
def _reset_icon_caches():
    """Clear the loader's process-global caches before AND after every test.

    ``app_icon()`` / ``guide_logo_image()`` are ``lru_cache``d; this module redirects the
    loader's resolution root in its planted-state control, and a cached result must never
    leak into a sibling test sharing the xdist worker (same reason as ``test_app_icon.py``).
    """
    app_icon_module.app_icon.cache_clear()
    app_icon_module.guide_logo_image.cache_clear()
    yield
    app_icon_module.app_icon.cache_clear()
    app_icon_module.guide_logo_image.cache_clear()


# --------------------------------------------------------------------------- #
# The derived family, and the pixel comparison                                 #
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _derived() -> Dict[str, np.ndarray]:
    """Every family member, derived from the committed masters, as RGBA arrays."""
    members = derive_app_icons.render_all(derive_app_icons.load_masters(_APP_DIR))
    return {name: np.array(image.convert("RGBA")) for name, image in members.items()}


def _member(size: int) -> np.ndarray:
    name = f"app-icon-{size}.png"
    members = _derived()
    assert name in members, f"{name} is not a member of the deriver's family"
    return members[name]


def _pixels(image: QImage) -> np.ndarray:
    return image_array(image)


def _differences(shown: np.ndarray, expected: np.ndarray) -> str:
    """Return ``""`` when ``shown`` equals ``expected`` pixel for pixel, else why not."""
    if shown.shape != expected.shape:
        return f"size {shown.shape[1]}x{shown.shape[0]} != {expected.shape[1]}x{expected.shape[0]}"
    if not np.array_equal(shown[..., 3], expected[..., 3]):
        return f"alpha differs on {int((shown[..., 3] != expected[..., 3]).sum())} pixel(s)"
    visible = expected[..., 3] > 0
    wrong = (shown[..., :3] != expected[..., :3]).any(axis=-1) & visible
    if wrong.any():
        return f"colour differs on {int(wrong.sum())} of {int(visible.sum())} visible pixel(s)"
    return ""


def _icon_problems(icon: QIcon, label: str) -> List[str]:
    """One finding per runtime size of ``icon`` that is not pixel-equal to its member."""
    problems: List[str] = []
    if icon.isNull():
        return [f"{label}: the icon is null"]
    for size in RUNTIME_ICON_SIZES_PX:
        why = _differences(_pixels(icon.pixmap(size, size).toImage()), _member(size))
        if why:
            problems.append(f"{label} {size}px: {why}")
    return problems


# --------------------------------------------------------------------------- #
# The family itself                                                            #
# --------------------------------------------------------------------------- #


def test_the_runtime_sizes_are_unchanged_and_each_is_a_family_member():
    """``test_app_icon.py``'s eight sizes still stand, and each names a derived member."""
    assert RUNTIME_ICON_SIZES_PX == (512, 256, 128, 64, 48, 32, 24, 16)
    for size in RUNTIME_ICON_SIZES_PX:
        assert _member(size).shape[:2] == (size, size)
    print(
        f"{len(_derived())} derived family members; runtime sizes {RUNTIME_ICON_SIZES_PX}"
    )


def test_the_comparator_tells_the_kikko_badge_from_the_previous_brand():
    """Control: the previous brand's 64 px logo is NOT pixel-equal to the Kikko member."""
    with Image.open(_OLD_BRAND) as old:
        previous = np.array(old.convert("RGBA"))
    kikko = _member(64)
    assert previous.shape == kikko.shape
    why = _differences(previous, kikko)
    print(f"previous brand vs Kikko Badge 64 px: {why}")
    assert why, "the comparator cannot tell the two logos apart"
    assert _differences(kikko, kikko.copy()) == ""


# --------------------------------------------------------------------------- #
# SC-VI-UI-018-1                                                               #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_018_1_the_window_icon_is_a_kikko_badge_member(qtbot):
    """SC-VI-UI-018-1: ``Main_Window.windowIcon()`` is pixel-equal to the derived members."""
    window = Main_Window()
    qtbot.addWidget(window)
    problems = _icon_problems(window.windowIcon(), "window icon")
    print(
        f"window icon: {len(RUNTIME_ICON_SIZES_PX)} sizes compared, {len(problems)} problem(s)"
    )
    assert not problems, problems


def test_sc_vi_ui_018_1_the_application_icon_is_a_kikko_badge_member(qtbot):
    """SC-VI-UI-018-1: the icon ``create_app`` gives the application (taskbar) matches too."""
    app, window = create_app([])
    qtbot.addWidget(window)
    problems = _icon_problems(app.windowIcon(), "application icon")
    assert not problems, problems


def test_sc_vi_ui_018_1_the_about_dialog_shows_a_kikko_badge_member(qtbot, theme):
    """SC-VI-UI-018-1: the About dialog, opened from the Help menu, shows a family member.

    The icon label's pixmap is the one the user sees. Its size must be one of the family's
    own sizes (a scaled pixmap would not be a member) and its pixels must equal that member.
    """
    window = Main_Window()
    qtbot.addWidget(window)
    window._about_action.trigger()
    dialog = window._about_dialog
    assert dialog is not None, "the About action opened no dialog"
    qtbot.addWidget(dialog)
    pixmap = dialog._icon_label.pixmap()
    assert pixmap is not None and not pixmap.isNull(), "the About dialog shows no icon"
    side = pixmap.width()
    print(
        f"{theme}: About icon {pixmap.width()}x{pixmap.height()} at ratio {pixmap.devicePixelRatio()}"
    )
    assert pixmap.width() == pixmap.height()
    assert (
        side in RUNTIME_ICON_SIZES_PX
    ), f"{side} px is not a family size (a scaled pixmap)"
    assert _differences(_pixels(pixmap.toImage()), _member(side)) == ""


def test_sc_vi_ui_018_1_the_guide_logo_is_the_128_px_kikko_badge_member(qtbot):
    """SC-VI-UI-018-1: the user guide's App basics page shows the 128 px family member.

    Two witnesses: the loader's image, and the image the opened guide document actually
    resolves for its ``pac-logo.png`` reference after the real topic is rendered.
    """
    expected = _derived()[_GUIDE_LOGO_MEMBER]
    loaded = guide_logo_image()
    assert loaded is not None, "the guide logo did not load"
    assert _differences(_pixels(loaded), expected) == ""

    window = Main_Window()
    qtbot.addWidget(window)
    window._user_guide_action.trigger()
    dialog = window._user_guide_dialog
    assert dialog is not None, "the User Guide action opened no dialog"
    qtbot.addWidget(dialog)
    dialog.show_topic(_GUIDE_TOPIC)
    resolved = dialog._content_view.document().resource(
        QTextDocument.ResourceType.ImageResource, QUrl(_GUIDE_LOGO_RESOURCE)
    )
    assert resolved is not None and not resolved.isNull(), "the guide shows no logo"
    print(
        f"guide logo {resolved.width()}x{resolved.height()} on the {_GUIDE_TOPIC!r} topic"
    )
    assert _differences(_pixels(resolved), expected) == ""


# --------------------------------------------------------------------------- #
# Controls: the planted previous brand                                         #
# --------------------------------------------------------------------------- #


def _scratch_with_previous_brand(tmp_path: Path) -> Path:
    """A scratch icon folder whose every runtime member is the previous brand's logo."""
    scratch = tmp_path / "previous-brand-icons"
    scratch.mkdir()
    with Image.open(_OLD_BRAND) as old:
        base = old.convert("RGBA")
        for size in RUNTIME_ICON_SIZES_PX:
            base.resize((size, size), Image.Resampling.NEAREST).save(
                scratch / f"app-icon-{size}.png"
            )
    return scratch


def test_a_planted_previous_brand_fails_every_icon_comparison(
    qtbot, tmp_path, monkeypatch
):
    """Control: with the loader pointed at the previous brand, all three surfaces fail.

    The planted folder lives under ``tmp_path``; the committed icons are untouched. Each of
    the window icon, the guide logo and the About icon must now be reported as not the Kikko
    Badge, which shows the comparisons above are able to fail.
    """
    scratch = _scratch_with_previous_brand(tmp_path)
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: scratch)
    app_icon_module.app_icon.cache_clear()
    app_icon_module.guide_logo_image.cache_clear()

    window = Main_Window()
    qtbot.addWidget(window)
    problems = _icon_problems(window.windowIcon(), "window icon")
    print(
        f"planted previous brand: window icon problems {len(problems)} of {len(RUNTIME_ICON_SIZES_PX)}"
    )
    assert len(problems) == len(RUNTIME_ICON_SIZES_PX), problems

    loaded = guide_logo_image()
    assert loaded is not None
    assert _differences(_pixels(loaded), _derived()[_GUIDE_LOGO_MEMBER])

    window._about_action.trigger()
    dialog = window._about_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    pixmap = dialog._icon_label.pixmap()
    shown = _pixels(pixmap.toImage())
    side = pixmap.width()
    assert side not in RUNTIME_ICON_SIZES_PX or _differences(
        shown, _member(side)
    ), "the About icon still equals the Kikko Badge after the previous brand was planted"
