"""The Theme menu, its persistence and the art-scale rebuild (REQ-VI-UI-001, -002, -012).

What is covered, by scenario id (the visual-identity feature's scenarios):

* **SC-VI-UI-001-1** the Theme menu offers three styles and two modes, exactly one of
  each checked -- over all six restored combinations;
* **SC-VI-UI-001-2** a chosen combination applies at once (no restart, no new window),
  seen in the one application stylesheet, the painted-part state and the rendered
  pixels of a framed dock -- over all six targets;
* **SC-VI-UI-001-3** Light carries gold accents and Dark carries red accents (role maps,
  hue-classified, plus the accent actually rendered on the checked tool button);
* **SC-VI-UI-002-1 / -2** the mode and the style are remembered across a restart. The
  in-process "restart" builds a second ``Main_Window`` after resetting the application to
  the unstyled default (so the new window must restore, not inherit); ONE test restarts
  a REAL process, writing in one interpreter and reading in another;
* **SC-VI-UI-002-3** a first launch with no stored setting is Washi & Kintsugi in Light;
* **SC-VI-UI-002-4** an unknown stored style (or mode, or switch) yields the default while
  a valid sibling value is kept;
* the **art-scale rebuild**: invoking the screen-change handler with a STUBBED screen set.

Isolation. Every test here runs under the suite's autouse ``settings_store`` redirect and
asserts it FIRST (``assert_settings_isolated``), so the real store (the registry, a plist,
``~/.config``) is neither read nor written. Planted settings are written with the
four-argument ``QSettings(defaultFormat, UserScope, org, app)`` form the product uses; the
two-argument form is always native format and would bypass the redirect. The
subprocess test also points ``APPDATA``/``HOME``/``XDG_CONFIG_HOME`` at a temporary
directory, so the child cannot reach the favourites file of a real profile either.

Both modes. The suite's two-way ``theme`` fixture is replaced inside this module (as in
``test_theme.py``) by the module's own six-way ``combo`` parametrisation: a ``Main_Window``
restores the stored combination at construction and would ignore the conftest's.

HONEST LIMITS, stated and not hidden:

* the art-scale test stubs ``QGuiApplication.screens``; it is **NOT a real hot-plug**,
  which was never measured and the offscreen platform cannot emulate;
* the in-process restart shares one ``QApplication`` and module state with its first
  window; the real-process test is the one that crosses an interpreter boundary;
* the Theme menu is read through its actions (``QMenu.actions()``); no native popup is
  opened (Qt popups cannot be driven headlessly, see the popup-grab note in the suite).

``test_tool_icons.py::test_sc_u027_5_runtime_theme_switch_retints_mounted_icons`` reads the
documented default (``win._theme == THEME_LIGHT``); the default-launch tests below keep that
reading true and print the combination they observed.
"""

from __future__ import annotations

import colorsys
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QToolButton

from pixelart_creator.data import style_catalog
from pixelart_creator.ui import pixel_chrome
from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
from pixelart_creator.ui.appearance_settings import (
    KEY_MODE,
    KEY_PIXEL_PERFECT,
    KEY_STYLE,
    KEY_USE_SYSTEM_FONT,
    SETTINGS_GROUP,
    default_appearance,
    load_appearance,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    art_scale,
    available_styles,
    available_themes,
    build_qss,
    role_map,
)
from testing.suites.ui.conftest import (
    assert_settings_isolated,
    settings_location_is_under,
)
from testing.suites.ui.focus_helpers import (
    count_colour_pixels,
    grab_image,
    image_array,
)
from testing.suites.ui.test_theme import _COMBO_IDS, COMBOS, Combo, frame_share

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The three style ids and their menu labels (the labels are the spec's wording).
_STYLE_LABELS: Dict[str, str] = {
    "washi-kintsugi": "Washi & Kintsugi",
    "edo-night": "Edo Night",
    "arcade-kikko": "Arcade Kikko",
}
_MODE_LABELS: Dict[str, str] = {THEME_LIGHT: "Light", THEME_DARK: "Dark"}


# --------------------------------------------------------------------------- #
# Fixtures: a six-way combination, the isolation guard, small helpers          #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture with one known starting sheet."""
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store: Path) -> Path:
    """Fail BEFORE any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)
    return settings_store


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest) -> Combo:
    """One style x mode combination (six; the matrix size is printed by test_theme)."""
    chosen: Combo = request.param
    return chosen


def _production_settings() -> QSettings:
    """The four-argument form ``ui/appearance_settings.py`` uses."""
    return QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        ORGANIZATION_NAME,
        APPLICATION_NAME,
    )


def _store(values: Dict[str, object]) -> None:
    """Plant ``values`` in the ``appearance`` group of the isolated store."""
    settings = _production_settings()
    settings.beginGroup(SETTINGS_GROUP)
    for key, value in values.items():
        settings.setValue(key, value)
    settings.endGroup()
    settings.sync()


def _stored(key: str):
    """Read one raw value from the ``appearance`` group (``None`` when absent)."""
    settings = _production_settings()
    settings.beginGroup(SETTINGS_GROUP)
    value = settings.value(key)
    settings.endGroup()
    return value


def _label(text: str) -> str:
    """Return the label a user reads: ``&&`` is a literal ``&``, a lone ``&`` a mnemonic."""
    return re.sub(r"&(.)", r"\1", text)


def _open(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _fresh_process_state(qapp) -> None:
    """Return the application to what a just-started process shows: the default sheet."""
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)


def _other(combo: Combo) -> Combo:
    """Return a combination that differs from ``combo`` in BOTH style and mode."""
    styles = list(available_styles())
    modes = list(available_themes())
    style = styles[(styles.index(combo.style) + 1) % len(styles)]
    mode = modes[(modes.index(combo.mode) + 1) % len(modes)]
    return Combo(style, mode)


def _style_actions(win: Main_Window) -> List[QAction]:
    return list(win._style_menu.actions())


def _mode_actions(win: Main_Window) -> List[QAction]:
    """The Light and Dark entries of the Theme menu, by what the user reads."""
    wanted = set(_MODE_LABELS.values())
    return [a for a in win._theme_menu.actions() if _label(a.text()) in wanted]


def _checked_labels(actions: List[QAction]) -> List[str]:
    return [_label(a.text()) for a in actions if a.isChecked()]


def _assert_shows(win: Main_Window, qapp, combo: Combo) -> None:
    """The window, the one stylesheet and the painted parts all show ``combo``."""
    assert (win.current_style(), win.current_mode()) == (combo.style, combo.mode)
    assert qapp.styleSheet() == build_qss(combo.mode, combo.style, scale=art_scale())
    assert (pixel_chrome.active_style(), pixel_chrome.active_mode()) == (
        combo.style,
        combo.mode,
    )
    assert _checked_labels(_style_actions(win)) == [_STYLE_LABELS[combo.style]]
    assert _checked_labels(_mode_actions(win)) == [_MODE_LABELS[combo.mode]]
    assert win.styleSheet() == "", "a per-window stylesheet was added (NFR-5)"


def _hue_family(hex_colour: str) -> str:
    """Classify a role colour as ``gold`` or ``red`` by hue (else ``other``).

    The bands are this suite's reading of the two words in the spec, stated so they can
    be argued with: gold = hue 30-55 degrees, red = hue within 20 degrees of 0 (340-360
    and 0-20), each with saturation >= 0.5 so a grey cannot pass for either.
    """
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, _value = colorsys.rgb_to_hsv(r, g, b)
    degrees = hue * 360.0
    if saturation < 0.5:
        return "other"
    if 30.0 <= degrees <= 55.0:
        return "gold"
    if degrees >= 340.0 or degrees <= 20.0:
        return "red"
    return "other"


# --------------------------------------------------------------------------- #
# SC-VI-UI-001-1: the Theme menu                                              #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_001_1_theme_menu_offers_three_styles_and_two_modes(
    qtbot, qapp, combo, settings_store
):
    """SC-VI-UI-001-1: three styles, two modes, exactly one of each checked.

    The window is built with ``combo`` stored, so the checked entries are the RESTORED
    ones in every one of the six cases. The Theme menu must be on the menu bar.
    """
    _store({KEY_STYLE: combo.style, KEY_MODE: combo.mode})
    win = _open(qtbot)
    assert win._theme_menu.menuAction() in win.menuBar().actions(), "no Theme menu"
    styles = _style_actions(win)
    modes = _mode_actions(win)
    print(
        f"{combo.label()}: styles {[_label(a.text()) for a in styles]} "
        f"modes {[_label(a.text()) for a in modes]}"
    )
    assert [_label(a.text()) for a in styles] == list(_STYLE_LABELS.values())
    assert sorted(_label(a.text()) for a in modes) == sorted(_MODE_LABELS.values())
    assert all(a.isCheckable() for a in styles + modes)
    assert _checked_labels(styles) == [_STYLE_LABELS[combo.style]]
    assert _checked_labels(modes) == [_MODE_LABELS[combo.mode]]


def test_sc_vi_ui_001_1_the_menu_lists_exactly_the_styles_the_catalogue_ships(
    qtbot,
):
    """The three labels are not a hard-coded list the catalogue could outgrow unseen."""
    win = _open(qtbot)
    assert set(win._style_actions) == set(style_catalog.style_ids())
    assert set(_STYLE_LABELS) == set(style_catalog.style_ids())
    assert len(_style_actions(win)) == len(style_catalog.style_ids()) == 3


# --------------------------------------------------------------------------- #
# SC-VI-UI-001-2: a chosen combination applies at once                         #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_001_2_choosing_edo_night_then_dark_applies_without_a_restart(
    qtbot, qapp
):
    """SC-VI-UI-001-2 as written: W&K Light, choose Edo Night, then Dark."""
    win = _open(qtbot)
    _assert_shows(win, qapp, Combo("washi-kintsugi", THEME_LIGHT))
    win._style_actions["edo-night"].trigger()
    _assert_shows(win, qapp, Combo("edo-night", THEME_LIGHT))
    next(a for a in _mode_actions(win) if _label(a.text()) == "Dark").trigger()
    _assert_shows(win, qapp, Combo("edo-night", THEME_DARK))


def test_sc_vi_ui_001_2_every_combination_applies_at_once_and_is_rendered(
    qtbot, qapp, combo
):
    """SC-VI-UI-001-2 (six-way): trigger the style entry then the mode entry.

    Start from a combination that differs in BOTH axes. The one application stylesheet
    equals ``build_qss(mode, style, scale=art_scale())`` after each step, and the PIXELS
    of a framed dock follow: the dock body frame agrees with the NEW combination's
    ``dock_body`` template and not with the old one (the comparator is controlled by the
    mismatch on the old combination).
    """
    start = _other(combo)
    _store({KEY_STYLE: start.style, KEY_MODE: start.mode})
    win = _open(qtbot)
    win.resize(1100, 800)
    win.show()
    qtbot.waitExposed(win)
    QApplication.processEvents()
    _assert_shows(win, qapp, start)
    before = image_array(grab_image(win))

    win._style_actions[combo.style].trigger()
    next(
        a for a in _mode_actions(win) if _label(a.text()) == _MODE_LABELS[combo.mode]
    ).trigger()
    QApplication.processEvents()
    _assert_shows(win, qapp, combo)

    after = image_array(grab_image(win))
    assert before.shape != after.shape or not np.array_equal(
        before, after
    ), "the window renders identically after the switch"
    dock = win._layer_dock
    assert dock.isVisible() and not dock.isFloating()
    body = dock.widget()
    share_new, examined = frame_share(body, combo, "dock_body")
    share_old, _ = frame_share(body, start, "dock_body")
    print(
        f"{combo.label()} from {start.label()}: dock body frame agrees with the new "
        f"template on {share_new:.4f} of {examined} cells, with the old one on "
        f"{share_old:.4f}"
    )
    assert examined > 0 and share_new == 1.0
    assert share_old < 1.0, "the comparator cannot tell the two combinations apart"


def test_set_style_with_an_unknown_id_raises_and_changes_nothing(qtbot, qapp):
    """An unknown style id is refused BEFORE any state or the store changes."""
    win = _open(qtbot)
    sheet = qapp.styleSheet()
    with pytest.raises(ValueError, match="no-such-style"):
        win.set_style("no-such-style")
    assert (win.current_style(), win.current_mode()) == (DEFAULT_STYLE, THEME_LIGHT)
    assert qapp.styleSheet() == sheet
    assert _stored(KEY_STYLE) is None, "the store was written for a refused style"


# --------------------------------------------------------------------------- #
# SC-VI-UI-001-3: gold accents in Light, red accents in Dark                   #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_001_3_accent_and_ornament_roles_are_gold_in_light_red_in_dark(
    combo,
):
    """SC-VI-UI-001-3 (six-way): the ``accent`` and ``ornament`` roles by hue."""
    roles = role_map(combo.mode, combo.style)
    expected = "gold" if combo.mode == THEME_LIGHT else "red"
    got = {name: _hue_family(roles[name]) for name in ("accent", "ornament")}
    print(
        f"{combo.label()}: accent {roles['accent']} ornament {roles['ornament']} -> {got}"
    )
    assert got == {"accent": expected, "ornament": expected}


def test_sc_vi_ui_001_3_the_hue_classifier_tells_gold_red_and_grey_apart():
    """Control for the classifier: known gold, known red and a grey are told apart."""
    assert _hue_family("#F2B01E") == "gold"
    assert _hue_family("#C8283A") == "red"
    assert _hue_family("#808080") == "other"
    assert _hue_family("#2A3F9F") == "other"
    assert _hue_family("#F2B01E") != _hue_family("#C8283A")


def test_sc_vi_ui_001_3_the_accent_is_rendered_on_the_checked_tool_button(
    qtbot, qapp, combo
):
    """SC-VI-UI-001-3 (rendered): the checked tool shows accent-role pixels.

    The same number of pixels of the OTHER mode's accent colour is the control: it must
    be zero on the checked tool, so the count is a measurement of the applied role.
    """
    _store({KEY_STYLE: combo.style, KEY_MODE: combo.mode})
    win = _open(qtbot)
    win.show()
    qtbot.waitExposed(win)
    QApplication.processEvents()
    checked = [a for a in win._tool_actions.values() if a.isChecked()]
    assert len(checked) == 1, "no single checked tool to look at"
    button = win._toolbar.widgetForAction(checked[0])
    assert isinstance(button, QToolButton)
    roles = role_map(combo.mode, combo.style)
    other = role_map(
        THEME_DARK if combo.mode == THEME_LIGHT else THEME_LIGHT, combo.style
    )
    image = grab_image(button)

    def packed(hex_colour: str) -> int:
        return 0xFF000000 | int(hex_colour[1:], 16)

    own = count_colour_pixels(image, packed(roles["accent"]))
    foreign = count_colour_pixels(image, packed(other["accent"]))
    print(
        f"{combo.label()}: accent px on the checked tool {own}, other-mode accent {foreign}"
    )
    assert own > 0, "the accent role is not drawn on the checked tool button"
    assert foreign == 0


# --------------------------------------------------------------------------- #
# SC-VI-UI-002-3: first launch                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("stale_mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_002_3_a_first_launch_is_washi_kintsugi_in_light(
    qtbot, qapp, stale_mode, settings_store
):
    """SC-VI-UI-002-3 (both modes of the stale state): no stored setting -> W&K Light.

    The application is first left in ``stale_mode`` (what an earlier window or the suite's
    own fixture would leave); a window with nothing stored must still open in Light. This
    is also the reading ``test_tool_icons.py`` relies on (``win._theme == THEME_LIGHT``).
    """
    apply_theme(qapp, stale_mode, "arcade-kikko")
    assert not _production_settings().contains(f"{SETTINGS_GROUP}/{KEY_STYLE}")
    win = _open(qtbot)
    print(f"stale {stale_mode}: opened as {win.current_style()}/{win.current_mode()}")
    assert win.current_style() == "washi-kintsugi" == DEFAULT_STYLE
    assert win.current_mode() == THEME_LIGHT
    assert win._theme == THEME_LIGHT, "the reading test_tool_icons.py depends on"
    _assert_shows(win, qapp, Combo("washi-kintsugi", THEME_LIGHT))
    assert load_appearance() == default_appearance()
    assert not any(
        settings_store.rglob("*.ini")
    ), "a bare first launch wrote the settings file"


# --------------------------------------------------------------------------- #
# SC-VI-UI-002-1 / -2: remembered across a restart                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_002_1_the_mode_is_remembered_across_a_restart(
    qtbot, qapp, mode, settings_store
):
    """SC-VI-UI-002-1 (both modes): select ``mode`` from the other one, restart.

    The first window starts in the OTHER mode (stored), the user selects ``mode`` through
    the menu; the application is reset to the unstyled default; a second window must open
    in ``mode``. The ini file under the isolated root is read as the second witness.
    """
    other = THEME_DARK if mode == THEME_LIGHT else THEME_LIGHT
    _store({KEY_MODE: other})
    first = _open(qtbot)
    assert first.current_mode() == other
    next(
        a for a in _mode_actions(first) if _label(a.text()) == _MODE_LABELS[mode]
    ).trigger()
    assert first.current_mode() == mode
    first.close()

    _fresh_process_state(qapp)
    second = _open(qtbot)
    print(f"selected {mode}, restarted: opened in {second.current_mode()}")
    assert second.current_mode() == mode
    _assert_shows(second, qapp, Combo(DEFAULT_STYLE, mode))
    files = list(settings_store.rglob("*.ini"))
    assert files and settings_location_is_under(str(files[0]), settings_store)
    assert f"mode={mode}" in files[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("style", sorted(_STYLE_LABELS))
def test_sc_vi_ui_002_2_the_style_is_remembered_across_a_restart(
    qtbot, qapp, style, settings_store
):
    """SC-VI-UI-002-2 (all three styles): select ``style`` from another, restart."""
    others = [s for s in _STYLE_LABELS if s != style]
    _store({KEY_STYLE: others[0]})
    first = _open(qtbot)
    assert first.current_style() == others[0]
    first._style_actions[style].trigger()
    assert first.current_style() == style
    first.close()

    _fresh_process_state(qapp)
    second = _open(qtbot)
    print(f"selected {style}, restarted: opened in {second.current_style()}")
    assert second.current_style() == style
    _assert_shows(second, qapp, Combo(style, THEME_LIGHT))
    files = list(settings_store.rglob("*.ini"))
    assert files and f"style={style}" in files[0].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "style, mode", [("arcade-kikko", THEME_DARK), ("edo-night", THEME_DARK)]
)
def test_sc_vi_ui_002_1_and_2_a_real_process_restart_keeps_style_and_mode(
    tmp_path, style, mode
):
    """SC-VI-UI-002-1/-2 across a REAL interpreter boundary.

    Process A builds the window, picks the style and the mode through the menu actions
    and exits; process B (a new interpreter) opens a window and prints what it shows.
    Both children redirect the settings to ``tmp_path`` with the suite's own helper, and
    their profile directories (``APPDATA``, ``HOME``, ``XDG_CONFIG_HOME``) are temporary,
    so neither can read or write a real user's settings or favourites.
    """
    root = tmp_path / "qs-root"
    profile = tmp_path / "profile"
    profile.mkdir()
    prelude = (
        "import sys; from pathlib import Path;"
        "from testing.suites.ui.conftest import redirect_settings_store,"
        " assert_settings_isolated;"
        "root = Path(sys.argv[1]); redirect_settings_store(root);"
        "assert_settings_isolated(root);"
        "from PySide6.QtWidgets import QApplication; app = QApplication([]);"
        "from pixelart_creator.ui.main_window import Main_Window; w = Main_Window();"
    )
    write = (
        prelude + f"w._style_actions[{style!r}].trigger();"
        f"w._theme_dark_action.trigger() if {mode!r} == 'dark' else "
        "w._theme_light_action.trigger();"
        "print('WROTE', w.current_style(), w.current_mode())"
    )
    read = prelude + "print('READ', w.current_style(), w.current_mode())"
    env = dict(os.environ)
    env.update(
        PYTHONPATH=os.pathsep.join(
            [str(_REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        ),
        QT_QPA_PLATFORM="offscreen",
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
    )

    def run(script: str) -> str:
        done = subprocess.run(
            [sys.executable, "-B", "-c", script, str(root)],
            cwd=str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=100,
        )
        assert (
            done.returncode == 0
        ), f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
        return done.stdout.strip().splitlines()[-1]

    assert run(write) == f"WROTE {style} {mode}"
    files = list(root.rglob("*.ini"))
    assert files, "process A wrote no settings file under the redirected root"
    assert run(read) == f"READ {style} {mode}"


# --------------------------------------------------------------------------- #
# SC-VI-UI-002-4: unknown stored values                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_002_4_an_unknown_stored_style_yields_the_default(qtbot, qapp, mode):
    """SC-VI-UI-002-4 (both modes): an unshipped style falls back, a valid mode is kept."""
    _store({KEY_STYLE: "no-such-style", KEY_MODE: mode})
    win = _open(qtbot)
    print(
        f"stored style 'no-such-style' + mode {mode}: opened {win.current_style()}/{win.current_mode()}"
    )
    assert win.current_style() == "washi-kintsugi"
    assert win.current_mode() == mode
    _assert_shows(win, qapp, Combo("washi-kintsugi", mode))


@pytest.mark.parametrize("bad_style", ["", "WASHI-KINTSUGI", "edo night", 3, "../x"])
def test_sc_vi_ui_002_4_every_kind_of_unknown_style_falls_back(qtbot, qapp, bad_style):
    """Empty, wrong-case, spaced, non-text and path-like values are all unknown."""
    _store({KEY_STYLE: bad_style})
    win = _open(qtbot)
    assert win.current_style() == "washi-kintsugi"


def test_sc_vi_ui_002_4_unknown_mode_and_unreadable_switches_fall_back_individually(
    qtbot, qapp
):
    """Each stored value is judged alone: a valid one is kept beside an invalid one."""
    _store(
        {
            KEY_STYLE: "edo-night",
            KEY_MODE: 3,
            KEY_PIXEL_PERFECT: "maybe",
            KEY_USE_SYSTEM_FONT: "true",
        }
    )
    win = _open(qtbot)
    assert win.current_style() == "edo-night"
    assert win.current_mode() == THEME_LIGHT, "an unknown mode must fall back to Light"
    assert (
        win.pixel_perfect_interface() is True
    ), "an unreadable switch keeps its default"
    assert win.use_system_font() is True, "a readable 'true' must be kept"


# --------------------------------------------------------------------------- #
# The other two Theme-menu entries (REQ-VI-UI-012, the menu item and its storage) #
# --------------------------------------------------------------------------- #


def test_the_theme_menu_carries_use_system_font_and_pixel_perfect_with_defaults(
    qtbot,
):
    """ "Use system font" is off, "Pixel-perfect interface" is on, both checkable."""
    win = _open(qtbot)
    labels = {_label(a.text()): a for a in win._theme_menu.actions() if a.isCheckable()}
    assert "Use system font" in labels and "Pixel-perfect interface" in labels
    assert labels["Use system font"].isChecked() is False
    assert labels["Pixel-perfect interface"].isChecked() is True
    assert win.use_system_font() is False and win.pixel_perfect_interface() is True


def test_the_two_switches_store_announce_and_survive_a_restart(
    qtbot, qapp, settings_store
):
    """Toggling stores the value, emits once, and the next window shows it."""
    win = _open(qtbot)
    font_calls: List[bool] = []
    perfect_calls: List[bool] = []
    win.useSystemFontChanged.connect(font_calls.append)
    win.pixelPerfectInterfaceChanged.connect(perfect_calls.append)

    win._use_system_font_action.trigger()
    win._interface_pixel_perfect_action.trigger()
    assert font_calls == [True] and perfect_calls == [False]
    win.set_use_system_font(True)  # unchanged: no second signal
    assert font_calls == [True]
    win.close()

    _fresh_process_state(qapp)
    again = _open(qtbot)
    assert again.use_system_font() is True and again.pixel_perfect_interface() is False
    assert again._use_system_font_action.isChecked() is True
    assert again._interface_pixel_perfect_action.isChecked() is False


def test_the_theme_menu_texts_survive_a_language_change(qtbot):
    """F5: the appearance labels are re-set (not blanked) by a LanguageChange event."""
    win = _open(qtbot)
    before = [a.text() for a in _style_actions(win)]
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert [a.text() for a in _style_actions(win)] == before
    assert all(a.text() for a in win._theme_menu.actions() if not a.isSeparator())


def test_a11y_every_theme_menu_entry_is_labelled_and_its_access_keys_are_unique(qtbot):
    """a11y: each entry reads as text, the new ones carry a status tip, access keys differ.

    Menu entries are announced by their text, so an empty one would be silent; the Style
    submenu's title is one of the Theme menu's entries and takes part in the access-key
    check. Access keys (the letter after a lone ``&``) must be unique within one menu level,
    or Alt+letter would be ambiguous.
    """
    win = _open(qtbot)
    top = [a for a in win._theme_menu.actions() if not a.isSeparator()]
    assert len(top) >= 5, "the Theme menu has fewer entries than the spec lists"
    for action in top + _style_actions(win):
        assert _label(action.text()).strip(), f"an entry has no text: {action.text()!r}"
    for action in (
        win._use_system_font_action,
        win._interface_pixel_perfect_action,
        win._style_menu.menuAction(),
    ):
        assert action.statusTip().strip(), f"{action.text()!r} has no status tip"

    def keys(actions) -> List[str]:
        found: List[str] = []
        for action in actions:
            found += re.findall(r"(?<!&)&([^&])", action.text())
        return [k.lower() for k in found]

    top_keys = keys(top)
    print(f"Theme menu access keys: {top_keys}")
    assert len(top_keys) == len(set(top_keys)), f"duplicate access keys {top_keys}"
    style_keys = keys(_style_actions(win))
    assert len(style_keys) == len(set(style_keys))


# --------------------------------------------------------------------------- #
# The art-scale rebuild (measured verdict: stubbed screens, no real hot-plug)  #
# --------------------------------------------------------------------------- #


class _FakeScreen:
    """A stand-in with the only method ``art_scale`` reads."""

    def __init__(self, ratio: float) -> None:
        self._ratio = ratio

    def devicePixelRatio(self) -> float:
        return self._ratio


def _stub_screens(monkeypatch, ratios: List[float]) -> None:
    fakes = [_FakeScreen(r) for r in ratios]
    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: fakes))


_REBUILD_COMBOS: Tuple[Combo, ...] = (
    Combo("washi-kintsugi", THEME_LIGHT),
    Combo("edo-night", THEME_DARK),
    Combo("arcade-kikko", THEME_DARK),
)


@pytest.mark.parametrize(
    "chosen", _REBUILD_COMBOS, ids=[c.label() for c in _REBUILD_COMBOS]
)
def test_art_scale_rebuild_on_a_stubbed_screen_set(qtbot, qapp, monkeypatch, chosen):
    """The screen-change handler rebuilds the sheet only when the maximum DPR changes.

    NOT A REAL HOT-PLUG. The screen list is stubbed (``QGuiApplication.screens``) and the
    handler is invoked directly, then once more through the real ``screenRemoved`` signal
    it is connected to; the offscreen platform cannot add, remove or rescale a screen and
    no real hot-plug was ever measured.

    Steps, each asserted:

    1. one screen at DPR 1 -> the window's sheet is ``build_qss(.., scale=1)``;
    2. the SAME maximum (two screens, 1.0 and 1.0) -> NO re-apply (``build_qss`` not
       called, the sheet object unchanged);
    3. the maximum becomes 2 -> exactly one re-apply, the sheet equals
       ``build_qss(mode, style, scale=2)``, still ONE sheet, the window carries none;
    4. an unchanged maximum of 2 (a different screen mix) -> NO re-apply;
    5. a screen removed (maximum back to 1) -> one re-apply at scale 1, delivered through
       the ``screenRemoved`` signal;
    6. a pinned scale is never rebuilt, whatever the screens say.
    """
    _store({KEY_STYLE: chosen.style, KEY_MODE: chosen.mode})
    win = _open(qtbot)
    real_build = theme_module.build_qss
    calls: List[int] = []

    def counting(mode: str, style: str = DEFAULT_STYLE, *, scale: int = 1) -> str:
        calls.append(scale)
        return real_build(mode, style, scale=scale)

    monkeypatch.setattr(theme_module, "build_qss", counting)
    handler = theme_module._on_screens_changed

    # 1 -- the starting point is measured, not assumed.
    assert art_scale() == 1, "the offscreen platform did not report DPR 1"
    assert qapp.styleSheet() == real_build(chosen.mode, chosen.style, scale=1)

    # 2 -- the maximum is unchanged.
    sheet = qapp.styleSheet()
    _stub_screens(monkeypatch, [1.0, 1.0])
    assert art_scale() == 1
    handler()
    assert calls == [], f"unchanged maximum rebuilt the sheet: {calls}"
    assert qapp.styleSheet() == sheet

    # 3 -- the maximum changes to 2.
    _stub_screens(monkeypatch, [1.0, 2.0])
    assert art_scale() == 2
    handler()
    assert calls == [2], f"expected one rebuild at scale 2, got {calls}"
    assert qapp.styleSheet() == real_build(chosen.mode, chosen.style, scale=2)
    assert qapp.styleSheet() != sheet, "the rebuilt sheet is the old one"
    assert qapp.styleSheet().count("QMainWindow, QWidget {") == 1
    assert win.styleSheet() == ""
    assert (win.current_style(), win.current_mode()) == (chosen.style, chosen.mode)

    # 4 -- a different mix with the same maximum.
    calls.clear()
    _stub_screens(monkeypatch, [2.0, 1.0, 2.0])
    handler()
    assert calls == [], f"unchanged maximum 2 rebuilt the sheet: {calls}"

    # 5 -- a screen is removed: delivered through the real signal.
    _stub_screens(monkeypatch, [1.0])
    qapp.screenRemoved.emit(qapp.primaryScreen())
    assert calls == [1], f"expected one rebuild at scale 1, got {calls}"
    assert qapp.styleSheet() == real_build(chosen.mode, chosen.style, scale=1)

    # 6 -- a pinned scale is never rebuilt.
    calls.clear()
    apply_theme(qapp, chosen.mode, chosen.style, scale=3)
    pinned_sheet = qapp.styleSheet()
    calls.clear()
    _stub_screens(monkeypatch, [4.0])
    handler()
    assert calls == [] and qapp.styleSheet() == pinned_sheet
    print(
        f"{chosen.label()}: stubbed screen sets only (NOT a real hot-plug); "
        "unchanged -> 0 rebuilds, 1 -> 2 -> 1 -> 1 rebuild each"
    )
    apply_theme(qapp, chosen.mode, chosen.style)


def test_art_scale_rebuild_follows_the_style_and_mode_chosen_at_runtime(
    qtbot, qapp, monkeypatch
):
    """The rebuild uses the combination the user switched to, not the launch one.

    A switch through the menu records the new combination in the theme module; a later
    screen change must rebuild THAT, not the combination the window opened with.
    """
    win = _open(qtbot)
    win._style_actions["arcade-kikko"].trigger()
    win.set_mode(THEME_DARK)
    _stub_screens(monkeypatch, [2.0])
    theme_module._on_screens_changed()
    assert qapp.styleSheet() == build_qss(THEME_DARK, "arcade-kikko", scale=2)
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
