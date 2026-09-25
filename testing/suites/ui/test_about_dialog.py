"""UI tests for the About dialog — REQ-AV-UI-002..012.

One test per acceptance criterion (Gherkin scenarios in
the feature's spec §6), driving the PySide6 dialog
headlessly (``QT_QPA_PLATFORM=offscreen``) via the ``qtbot`` fixture. Every
test runs twice, once per theme, via the suite's autouse ``theme`` fixture
(``testing/suites/ui/conftest.py``); tests that make an explicit
theme-contrast assertion take the ``theme`` parameter directly, matching the
project's existing convention (``test_a11y_theme.py``).

Binds ONLY to plan §3.2's fixed contract: ``Main_Window._about_action``
(objectName ``aboutAction``, ``AboutRole``), ``Main_Window._on_about()``,
``Main_Window._about_dialog``, and ``About_Dialog``'s ten objectNames
(``aboutIconLabel``, ``aboutNameLabel``, ``aboutVersionValue``,
``aboutLicenceValue``, ``aboutRepositoryLink``, ``aboutDocumentationLink``,
``aboutReleasesLink``, ``aboutEnvironmentValue``, ``aboutCopyButton``,
``aboutCloseButton``) and its three monkeypatchable seams
(``_qt_version``, ``_pyside_version``, the single ``_open_url`` seam).

Red-first (NFR-5): at `a77b5c0` neither ``pixelart_creator.ui.about_dialog``
nor ``Main_Window._about_action``/``_on_about`` exist at all. Every test
below therefore fails now for the right reason -- the feature's absence
(``ModuleNotFoundError`` at collection, or ``AttributeError`` on
``_about_action``/``_on_about``/``_about_dialog``) -- not a harness or typo
error. This mirrors the project's own precedent for a whole-module absence
(``test_i18n.py``'s docstring: "this whole scenario is a DEFECT by
non-existence, not merely a failing assertion").

MC-3 (manual-check grounding, recorded here and in the report): before
writing the structural keyboard test below, the literal Alt+H -> arrow keys
-> Enter path was attempted against a KNOWN-TRUE control -- the PRE-EXISTING,
already-shipped Help menu / User Guide action, which needs no unimplemented
code at all. ``QTest.keyClick(win, Qt.Key.Key_H, Qt.KeyboardModifier.AltModifier)``
never opened the menu (``_help_menu.isVisible()`` stayed ``False``, no active
popup, the connected slot never fired) -- the offscreen platform cannot
engage Qt's native menu-popup grab, matching the documented PySide6/Qt
limitation. MC-3's keystroke path therefore stays MANUAL; only its
STRUCTURAL half (mnemonic, action presence/enabled state, the dialog's own
Tab chain and its focus indicator) is covered by an automated test here.
"""

from __future__ import annotations

import platform
import socket

import pytest
from PySide6.QtCore import QLocale, Qt, qVersion
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

import pixelart_creator
from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.app_icon import app_icon
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import THEME_DARK
from testing.suites.ui.test_a11y_theme import _WCAG_AA_NORMAL, _contrast_ratio

#: The three fixed links (REQ-AV-UI-005) and their exact target addresses.
_LINKS = [
    ("aboutRepositoryLink", "https://github.com/JuanGSanchez/PixelArt-Creator"),
    ("aboutDocumentationLink", "https://juangsanchez.github.io/PixelArt-Creator/"),
    ("aboutReleasesLink", "https://github.com/JuanGSanchez/PixelArt-Creator/releases"),
]

#: The dialog's Tab chain in order (CL-AV-14: the version value is excluded).
_TAB_CHAIN = [
    "aboutRepositoryLink",
    "aboutDocumentationLink",
    "aboutReleasesLink",
    "aboutCopyButton",
    "aboutCloseButton",
]

_ALL_OBJECT_NAMES = [
    "aboutIconLabel",
    "aboutNameLabel",
    "aboutVersionValue",
    "aboutLicenceValue",
    "aboutRepositoryLink",
    "aboutDocumentationLink",
    "aboutReleasesLink",
    "aboutEnvironmentValue",
    "aboutCopyButton",
    "aboutCloseButton",
]


@pytest.fixture(autouse=True)
def _english_start_language():
    """Force ``QLocale.system()`` to resolve to English before every test.

    ``testing/suites/ui/conftest.py`` already patches ``QLocale.system`` the
    same way, once, at collection time, for the whole UI suite -- so every
    ``Main_Window()`` built anywhere under this directory already starts in
    English regardless of the host OS locale. This machine's own Windows
    locale is ``es_ES``: verified directly this session (throwaway
    diagnostic script, discarded) that WITHOUT the conftest patch a freshly
    constructed ``Main_Window`` starts with ``_about_action.text() ==
    "&Acerca de PixelArt Creator"`` (Spanish), because
    ``LanguageManager.install_from_locale()`` reads ``QLocale.system()`` at
    construction. This fixture repeats that same patch LOCALLY and
    EXPLICITLY in this file (autouse, so it needs no per-test opt-in), so
    every test here is provably independent of the conftest patch's
    continued presence too, and its outcome matches CI's neutral/English
    runner regardless of which machine runs it (F11 / portability).
    """
    QLocale.system = staticmethod(  # type: ignore[method-assign]
        lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    )
    yield


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _open_about(qtbot, win: Main_Window | None = None):
    """Trigger Help > About on ``win`` (or a fresh window) and return both."""
    win = win or _window(qtbot)
    win._about_action.trigger()
    dialog = win._about_dialog
    qtbot.addWidget(dialog)
    return win, dialog


def _child(dialog, name: str) -> QWidget:
    widget = dialog.findChild(QWidget, name)
    assert widget is not None, f"About_Dialog is missing the {name!r} widget"
    return widget


def _tab_focusable(widget: QWidget) -> bool:
    """Return whether ``widget`` reports the ``Qt.FocusPolicy.TabFocus`` bit
    RIGHT NOW, on the RUNNING platform.

    A platform's native style can make a widget class not keyboard-Tab-
    reachable by default (measured, PR #73 CI: macOS/``QMacStyle`` leaves an
    ordinary, non-default ``QPushButton`` -- ``aboutCopyButton`` -- without
    the ``TabFocus`` bit, while the dialog's own default button --
    ``aboutCloseButton`` -- keeps it). Forcing
    ``QStyleHints.setTabFocusBehavior(TabFocusAllControls)`` was tried and
    measured to have NO effect on that platform (same CI run), so the
    per-widget ``focusPolicy()`` bit -- read fresh, never assumed -- is the
    correct, platform-derived signal for "does a real Tab keypress reach
    this widget right now", and every Tab-chain test below is built from it
    rather than from a fixed platform assumption.
    """
    return bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)


def _max_glyph_contrast(widget: QWidget) -> float:
    """Return the highest WCAG contrast ratio between any rendered pixel of
    ``widget`` and its own background, sampled at an unpainted corner pixel
    of the SAME grab.

    Reuses ``_contrast_ratio`` (and, transitively, its luminance helper) from
    ``test_a11y_theme`` -- the exact instrument the theme role-pair tests
    already use -- so the 4.5:1 floor and the luminance formula are imported,
    never restated (plan §6, OB-8). This is the RENDERED measurement plan §6
    calls for (as opposed to the role-pair-only check in
    ``test_a11y_theme.py``): it grabs the widget as Qt actually painted it,
    with the app-wide QSS background already composited in (verified this
    session: a standalone, app-styled ``QLabel``'s own ``grab()`` already
    shows the theme's background colour at its corner, with no parent frame
    needed).
    """
    image = widget.grab().toImage()
    if image.width() == 0 or image.height() == 0:
        return 1.0
    bg_hex = image.pixelColor(0, 0).name()
    best = 1.0
    for y in range(image.height()):
        for x in range(image.width()):
            ratio = _contrast_ratio(image.pixelColor(x, y).name(), bg_hex)
            if ratio > best:
                best = ratio
    return best


# =========================================================================== #
# REQ-AV-UI-002 -- Help > About PixelArt Creator, AboutRole                    #
# =========================================================================== #


def test_sc_av_ui_002_1_about_action_carries_about_role(qtbot):
    """@C-6 / SC-AV-UI-002-1: the entry's objectName is ``aboutAction`` and its
    menu role reads ``AboutRole``."""
    win = _window(qtbot)
    assert win._about_action.objectName() == "aboutAction"
    assert win._about_action.menuRole() == win._about_action.MenuRole.AboutRole


def test_sc_av_ui_002_2_help_menu_order_and_f1_unchanged(qtbot):
    """@derived / SC-AV-UI-002-2: on a platform that keeps About under Help,
    the menu reads User Guide, separator, AI Assistant, separator, About
    PixelArt Creator -- and F1 still opens the User Guide.

    Headless tests do not relocate menus (plan §6/C-6 rationale), so this
    asserts the ORDER as ``QMenu.actions()`` reports it on every OS under
    ``QT_QPA_PLATFORM=offscreen``, which is where Windows/Linux keep it.
    """
    from PySide6.QtGui import QKeySequence

    win = _window(qtbot)
    actions = win._help_menu.actions()
    assert win._user_guide_action in actions
    assert win._about_action in actions
    assert actions.index(win._about_action) == len(actions) - 1
    assert actions[actions.index(win._about_action) - 1].isSeparator()
    # F1 is unchanged.
    assert win._user_guide_action.shortcut() == QKeySequence(Qt.Key.Key_F1)


# =========================================================================== #
# REQ-AV-UI-003 -- the dialog opens, modal, with its fixed content             #
# =========================================================================== #


def test_sc_av_ui_003_1_dialog_opens_modal_with_content(qtbot):
    """@C-5 / SC-AV-UI-003-1: a modal dialog opens with every listed element."""
    _win, dialog = _open_about(qtbot)
    assert dialog.isModal()
    assert dialog.windowTitle() == "About PixelArt Creator"
    for name in _ALL_OBJECT_NAMES:
        _child(dialog, name)
    assert _child(dialog, "aboutNameLabel").text() == "PixelArt Creator"
    assert _child(dialog, "aboutLicenceValue").text() == "Apache License 2.0"


def test_sc_av_ui_003_2_dialog_icon_matches_main_window_icon(qtbot):
    """@derived / SC-AV-UI-003-2: the dialog's icon is the one ``app_icon()``
    supplies to the main window."""
    _win, dialog = _open_about(qtbot)
    icon_label = _child(dialog, "aboutIconLabel")
    shown = icon_label.pixmap()
    assert shown is not None and not shown.isNull()
    expected = app_icon().pixmap(shown.size())
    assert shown.toImage() == expected.toImage()


# =========================================================================== #
# REQ-AV-UI-004 -- the version shown is the running version, selectable       #
# =========================================================================== #


def test_sc_av_ui_004_1_version_value_equals_app_version(qtbot):
    """@C-5 / SC-AV-UI-004-1: the version value equals
    ``pixelart_creator.__version__``."""
    _win, dialog = _open_about(qtbot)
    assert _child(dialog, "aboutVersionValue").text() == pixelart_creator.__version__


def test_sc_av_ui_004_2_new_release_shows_its_new_number(qtbot, monkeypatch):
    """SC-AV-UI-004-2: a new release shows its new number with no dialog
    change (the value the test installs, NFR-2)."""
    monkeypatch.setattr(pixelart_creator, "__version__", "0.3.2", raising=False)
    _win, dialog = _open_about(qtbot)
    assert _child(dialog, "aboutVersionValue").text() == "0.3.2"


def test_sc_av_ui_004_3_version_value_selectable_and_out_of_tab_chain(qtbot):
    """@C-8 (selectable half) / SC-AV-UI-004-3: the version value carries
    ``TextSelectableByMouse``; CL-AV-14 keeps keyboard focus off it."""
    _win, dialog = _open_about(qtbot)
    version_value = _child(dialog, "aboutVersionValue")
    flags = version_value.textInteractionFlags()
    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
    assert version_value.focusPolicy() in (
        Qt.FocusPolicy.NoFocus,
        Qt.FocusPolicy.ClickFocus,
    )


# =========================================================================== #
# REQ-AV-UI-005 -- three links, opened in the default browser only on click   #
# =========================================================================== #


@pytest.mark.parametrize("object_name,url", _LINKS)
def test_sc_av_ui_005_1_each_link_target(qtbot, object_name, url):
    """SC-AV-UI-005-1: each link's target is its exact address.

    Plan §3.2: "Each link label carries a dynamic property `url` equal to
    its target. The href in its rich text is the same value." -- so the
    address is checked both as the dynamic property AND as the embedded
    ``href`` in the rendered rich text (never the translated caption, which
    is a separate, translated element per CL-AV-5).
    """
    _win, dialog = _open_about(qtbot)
    link = _child(dialog, object_name)
    assert link.property("url") == url
    assert url in link.text()


def test_sc_av_ui_005_2_clicking_link_hands_off_to_open_url(qtbot, monkeypatch):
    """SC-AV-UI-005-2: activating a link hands its target to ``_open_url``
    exactly once (the ONE URL seam, plan §3.2/task instructions)."""
    import pixelart_creator.ui.about_dialog as about_dialog_module

    calls: list[str] = []
    monkeypatch.setattr(about_dialog_module, "_open_url", lambda url: calls.append(url))
    _win, dialog = _open_about(qtbot)
    link = _child(dialog, "aboutDocumentationLink")
    link.linkActivated.emit("https://juangsanchez.github.io/PixelArt-Creator/")
    assert calls == ["https://juangsanchez.github.io/PixelArt-Creator/"]


def test_sc_av_ui_005_3_nothing_opened_unless_a_link_is_clicked(qtbot, monkeypatch):
    """SC-AV-UI-005-3: opening, leaving open, and closing the dialog without
    clicking a link hands nothing to ``_open_url``."""
    import pixelart_creator.ui.about_dialog as about_dialog_module

    calls: list[str] = []
    monkeypatch.setattr(about_dialog_module, "_open_url", lambda url: calls.append(url))
    _win, dialog = _open_about(qtbot)
    dialog.close()
    assert calls == []


@pytest.mark.parametrize("object_name,url", _LINKS)
@pytest.mark.parametrize(
    "key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]
)
def test_sc_av_ui_005_4_keyboard_activates_a_focused_link(
    qtbot, monkeypatch, object_name, url, key
):
    """REQ-AV-UI-005 (``LinksAccessibleByKeyboard``): keyboard activation of a
    focused link must open it and keep the dialog open. With a link reached
    by REAL Tab navigation and focused, a real keyboard Return/Enter/Space
    must activate it -- hand its URL to ``_open_url`` exactly once -- and
    must NOT close the dialog.

    Without a keyboard-activation handler, Return/Enter/Space on a focused
    link instead falls through to ``QDialog``'s own default-button handling
    (``_close_button.setDefault(True)`` + ``setAutoDefault(True)``) and
    closes the dialog, leaving ``_open_url`` uncalled -- reproducible for all
    three keys. A direct ``linkActivated.emit(url)`` call still reaches
    ``_open_url`` on its own, so the signal wiring is not what this test
    guards: it guards the real keyboard path reaching that same signal.

    Uses ``_tab_focusable`` (see its docstring): the Tab-press count below is
    derived from which links the RUNNING platform actually makes
    Tab-reachable right now, never a fixed step count -- a link this
    platform does not make Tab-reachable is reported "could not verify"
    (skipped with a reason), never silently passed.
    """
    import pixelart_creator.ui.about_dialog as about_dialog_module

    calls: list[str] = []
    monkeypatch.setattr(about_dialog_module, "_open_url", lambda u: calls.append(u))

    win, dialog = _open_about(qtbot)
    win.show()
    dialog.show()
    qtbot.waitExposed(dialog)

    # Reach the target link by REAL Tab navigation (never a direct
    # setFocus() jump onto the link itself), counted only across the links
    # this platform reports as Tab-focusable right now.
    tab_focusable_links = [
        _child(dialog, name)
        for name, _url in _LINKS
        if _tab_focusable(_child(dialog, name))
    ]
    link = _child(dialog, object_name)
    if link not in tab_focusable_links:
        pytest.skip(
            f"{object_name} does not report Qt.FocusPolicy.TabFocus on this "
            "platform -- could not verify real keyboard reach here"
        )

    first = tab_focusable_links[0]
    first.setFocus(Qt.FocusReason.TabFocusReason)
    assert dialog.focusWidget() is first, (
        f"{first.objectName()!r} (the first Tab-focusable link on this "
        "platform) did not accept focus"
    )
    for _ in range(tab_focusable_links.index(link)):
        qtbot.keyClick(dialog, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is link, (
        f"Tab navigation did not reach {object_name!r}; focus is on "
        f"{dialog.focusWidget().objectName() if dialog.focusWidget() else None!r}"
    )

    QTest.keyClick(link, key)
    qtbot.wait(10)

    assert calls == [url], (
        f"{object_name}/{key!r}: expected _open_url called once with "
        f"{url!r}, got {calls!r}"
    )
    assert dialog.isVisible(), (
        f"{object_name}/{key!r}: the dialog closed instead of activating the link"
    )


# =========================================================================== #
# REQ-AV-UI-006 -- environment facts + Copy                                   #
# =========================================================================== #


def test_sc_av_ui_006_1_copy_puts_environment_facts_on_clipboard(qtbot):
    """@C-7 / SC-AV-UI-006-1: Copy places app version, OS, Python and Qt
    versions on the clipboard."""
    _win, dialog = _open_about(qtbot)
    copy_button = _child(dialog, "aboutCopyButton")
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    clip_text = QGuiApplication.clipboard().text()
    assert pixelart_creator.__version__ in clip_text
    assert platform.system() in clip_text
    assert platform.python_version() in clip_text
    assert qVersion() in clip_text


def test_sc_av_ui_006_2_copied_text_is_one_line_and_matches_shown(qtbot):
    """@derived / SC-AV-UI-006-2: the copied text has no line break and
    equals exactly the environment line the dialog shows."""
    _win, dialog = _open_about(qtbot)
    shown = _child(dialog, "aboutEnvironmentValue").text()
    copy_button = _child(dialog, "aboutCopyButton")
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    clip_text = QGuiApplication.clipboard().text()
    assert "\n" not in clip_text and "\r" not in clip_text
    assert clip_text == shown


# =========================================================================== #
# REQ-AV-UI-007 -- "unknown" instead of failure; opening never raises         #
# =========================================================================== #


def test_sc_av_ui_007_1_os_version_raising_shows_unknown(qtbot, monkeypatch):
    """@C-15 / SC-AV-UI-007-1: ``platform.version()`` raising -> the dialog
    still opens, and the copied line carries "unknown" for the OS version."""

    def _raise():
        raise OSError("simulated platform.version() failure")

    monkeypatch.setattr(platform, "version", _raise)
    _win, dialog = _open_about(qtbot)  # must not raise
    copy_button = _child(dialog, "aboutCopyButton")
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    assert "unknown" in QGuiApplication.clipboard().text()


@pytest.mark.parametrize(
    "patch_target",
    [
        "platform.version",
        "platform.python_version",
        "pixelart_creator.ui.about_dialog._qt_version",
        "pixelart_creator.ui.about_dialog._pyside_version",
    ],
)
def test_sc_av_ui_007_2_each_fact_degrades_on_its_own(qtbot, monkeypatch, patch_target):
    """@derived / SC-AV-UI-007-2: each undeterminable fact shows "unknown" on
    its own; the dialog opens without raising and the other facts stay known."""

    def _raise(*_a, **_k):
        raise RuntimeError(f"simulated failure of {patch_target}")

    monkeypatch.setattr(patch_target, _raise)
    _win, dialog = _open_about(qtbot)  # must not raise
    env_text = _child(dialog, "aboutEnvironmentValue").text()
    assert "unknown" in env_text
    # The app name/version part is never the failing fact here, so it must
    # still be present and known.
    assert pixelart_creator.__version__ in env_text


def test_sc_av_ui_007_3_missing_icon_does_not_stop_the_dialog(qtbot, monkeypatch):
    """@derived / SC-AV-UI-007-3: a null ``app_icon()`` does not stop the
    dialog opening with its other content."""
    import pixelart_creator.ui.about_dialog as about_dialog_module

    monkeypatch.setattr(about_dialog_module, "app_icon", lambda: QIcon())
    _win, dialog = _open_about(qtbot)  # must not raise
    assert _child(dialog, "aboutNameLabel").text() == "PixelArt Creator"
    assert _child(dialog, "aboutLicenceValue").text() == "Apache License 2.0"


# =========================================================================== #
# REQ-AV-UI-008 -- keyboard operation                                        #
# =========================================================================== #


def test_sc_av_ui_008_2_esc_closes_dialog_and_focus_returns(qtbot):
    """@C-8 (first half) / SC-AV-UI-008-2: Esc closes the dialog (QDialog
    reject) and the main window regains it as the active top-level widget."""
    win, dialog = _open_about(qtbot)
    win.show()
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.isVisible()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    assert dialog.result() == dialog.DialogCode.Rejected


def test_tab_chain_reaches_every_platform_tab_focusable_control_and_wraps(
    qtbot,
):
    """REQ-AV-UI-008 (Tab reach clause; CL-AV-14), platform-reachability half:
    Tab visits, in order, every Tab-chain control the RUNNING platform
    reports as ``Qt.FocusPolicy.TabFocus``-able right now, and wraps back to
    the first one.

    A platform's native style can make an ordinary (non-default) push button
    not keyboard-Tab-reachable by default -- measured, PR #73 CI:
    macOS/``QMacStyle`` leaves ``aboutCopyButton`` without the ``TabFocus``
    bit while ``aboutCloseButton`` (the dialog's own default button) keeps
    it. Forcing ``QStyleHints.setTabFocusBehavior(TabFocusAllControls)`` was
    tried first and measured to have NO effect there (same CI run) -- so the
    expected sequence here is DERIVED from each control's own
    ``focusPolicy()`` on whatever platform runs the test (``_tab_focusable``),
    never pinned to one platform's list. The DECLARED order (every one of
    the five controls, regardless of platform) is checked separately and
    platform-independently by
    ``test_declared_tab_order_lists_links_copy_close_in_order`` below, so an
    actual ordering regression is still caught on every platform even where
    this test's expected sequence is a strict subset.
    """
    win, dialog = _open_about(qtbot)
    win.show()
    dialog.show()
    qtbot.waitExposed(dialog)

    ordered_widgets = [_child(dialog, name) for name in _TAB_CHAIN]
    expected = [w for w in ordered_widgets if _tab_focusable(w)]
    assert expected, (
        "no Tab-chain control reports Qt.FocusPolicy.TabFocus on this "
        "platform -- nothing to verify"
    )

    first = expected[0]
    first.setFocus(Qt.FocusReason.TabFocusReason)
    assert dialog.focusWidget() is first, (
        f"{first.objectName()!r} (the first Tab-focusable control on this "
        "platform) did not accept focus"
    )
    for widget in expected[1:]:
        qtbot.keyClick(dialog, Qt.Key.Key_Tab)
        current = dialog.focusWidget()
        assert current is widget, (
            f"Tab did not reach {widget.objectName()!r}; focus is on "
            f"{current.objectName() if current else None!r}"
        )

    # Wraps back to the first Tab-focusable control.
    qtbot.keyClick(dialog, Qt.Key.Key_Tab)
    current = dialog.focusWidget()
    assert current is first, (
        "Tab from the last Tab-focusable control did not wrap back to "
        f"{first.objectName()!r}; focus is on "
        f"{current.objectName() if current else None!r}"
    )


def test_declared_tab_order_lists_links_copy_close_in_order(qtbot):
    """REQ-AV-UI-008 (Tab reach clause; CL-AV-14), platform-independent half:
    ``About_Dialog``'s own DECLARED tab order -- its explicit
    ``QWidget.setTabOrder`` chain -- lists the three links, then Copy, then
    Close, in exactly that order, on every platform.

    Checked via ``nextInFocusChain()`` walked from the first link: this
    reflects the explicit chain wiring itself, never filtered by any
    platform's runtime Tab-key reachability (``focusPolicy()`` /
    ``QStyleHints``), so a genuine ordering regression (e.g. two
    ``setTabOrder`` calls swapped) is still caught everywhere, independent of
    ``test_tab_chain_reaches_every_platform_tab_focusable_control_and_wraps``
    above.
    """
    _win, dialog = _open_about(qtbot)
    ordered_widgets = [_child(dialog, name) for name in _TAB_CHAIN]

    current = ordered_widgets[0]
    for expected in ordered_widgets[1:]:
        following = current.nextInFocusChain()
        assert following is expected, (
            "declared tab order broken: expected "
            f"{expected.objectName()!r} to directly follow "
            f"{current.objectName()!r} in About_Dialog's own setTabOrder "
            f"chain, got {following.objectName() if following else None!r}"
        )
        current = following


def test_mc3_structural_mnemonic_action_presence_and_focus_indicator(qtbot):
    """MC-3 (structural half only -- see module docstring for the known-true
    control that showed the literal keystroke path is untestable headless).

    Covers: the mnemonic lives in ``&Help``, the About action is present,
    enabled and reachable in the menu, and every Tab-chain control shows a
    visible focus indicator (the app-wide themed ``:focus`` rule).
    """
    win, dialog = _open_about(qtbot)
    assert win._help_menu.title() == win.tr("&Help")
    assert win._about_action in win._help_menu.actions()
    assert win._about_action.isEnabled()

    for name in _TAB_CHAIN:
        widget = _child(dialog, name)
        assert (
            widget.focusPolicy() != Qt.FocusPolicy.NoFocus
        ), f"{name} is not keyboard-focusable"
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


# =========================================================================== #
# REQ-AV-UI-009 -- accessible names                                          #
# =========================================================================== #


def test_sc_av_ui_009_1_interactive_controls_have_accessible_names(qtbot):
    """@derived / SC-AV-UI-009-1: each of the three links, Copy and Close has
    a non-empty accessible name. [also: a11y-audit]"""
    _win, dialog = _open_about(qtbot)
    for name in _TAB_CHAIN:
        widget = _child(dialog, name)
        assert widget.accessibleName() != "", f"{name} has no accessible name"


# =========================================================================== #
# REQ-AV-UI-010 -- readable in both themes (RENDERED measurement)             #
# =========================================================================== #


def test_sc_av_ui_010_1_version_text_contrast(qtbot, theme):
    """@C-9 / SC-AV-UI-010-1: the version text meets 4.5:1 against the
    dialog's rendered background, in both light and dark."""
    _win, dialog = _open_about(qtbot)
    dialog.show()
    qtbot.waitExposed(dialog)
    ratio = _max_glyph_contrast(_child(dialog, "aboutVersionValue"))
    assert ratio >= _WCAG_AA_NORMAL, f"{theme}: version text contrast {ratio:.2f}:1"


def test_sc_av_ui_010_2_all_text_and_links_meet_contrast(qtbot, theme):
    """SC-AV-UI-010-2: every text and link in the dialog meets 4.5:1 against
    the dialog's rendered background, in both themes."""
    _win, dialog = _open_about(qtbot)
    dialog.show()
    qtbot.waitExposed(dialog)
    for name in _ALL_OBJECT_NAMES:
        if name == "aboutIconLabel":
            continue  # not text; no contrast claim applies
        ratio = _max_glyph_contrast(_child(dialog, name))
        assert ratio >= _WCAG_AA_NORMAL, f"{theme}: {name} contrast {ratio:.2f}:1"


def test_rendered_contrast_measurement_catches_a_real_failure(qtbot, theme):
    """Methodology control (plan §6): the SAME rendered measurement MUST FAIL
    when a link anchor is forced to the Qt palette-default blue (``#0000ff``)
    in the dark theme -- proving the instrument can catch a real failure, not
    merely confirm a pass. Grounds the plan's own probe (1.65:1 in dark).

    This control does NOT touch ``About_Dialog`` (so it is independent of
    the dialog's implementation and legitimately PASSES already, today, against
    `a77b5c0` -- it validates the TEST'S OWN measurement method, not a
    product acceptance criterion, so it is not part of the red-first count).
    It builds its own themed ``QWidget``/``QLabel`` over the SAME role
    background ``apply_theme`` would give the real dialog.
    """
    bg = theme_module._ROLES[theme]["background"]
    widget = QWidget()
    widget.setStyleSheet(f"background-color: {bg};")
    layout = QVBoxLayout(widget)
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(
        '<a href="x" style="color:#0000ff; text-decoration: underline;">Link</a>'
    )
    layout.addWidget(label)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    ratio = _max_glyph_contrast(label)
    if theme == THEME_DARK:
        assert ratio < _WCAG_AA_NORMAL, (
            f"control did not fail as expected: palette-default link measured "
            f"{ratio:.2f}:1 in dark (plan probe: 1.65:1)"
        )


# =========================================================================== #
# REQ-AV-UI-011 -- no network access                                         #
# =========================================================================== #


def test_sc_av_ui_011_1_no_network_call_on_open_copy_close(qtbot, monkeypatch):
    """@C-10 / SC-AV-UI-011-1: opening, Copy, and closing make no network
    call; ``_open_url`` is never called either (nothing is clicked)."""
    import pixelart_creator.ui.about_dialog as about_dialog_module

    def _raise(*_a, **_k):
        raise AssertionError("a network call was attempted")

    monkeypatch.setattr(socket.socket, "connect", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)
    calls: list[str] = []
    monkeypatch.setattr(about_dialog_module, "_open_url", lambda url: calls.append(url))

    _win, dialog = _open_about(qtbot)
    copy_button = _child(dialog, "aboutCopyButton")
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    dialog.close()
    assert calls == []


def test_sc_av_ui_011_2_works_with_no_network_connection(
    qtbot, monkeypatch, mute_message_boxes
):
    """SC-AV-UI-011-2: with no network connection the dialog opens showing
    the name, version, licence and links, and no error/warning is shown."""

    def _raise(*_a, **_k):
        raise OSError("network unreachable (simulated)")

    monkeypatch.setattr(socket.socket, "connect", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)

    _win, dialog = _open_about(qtbot)  # must not raise
    assert _child(dialog, "aboutNameLabel").text() == "PixelArt Creator"
    assert _child(dialog, "aboutVersionValue").text() != ""
    assert _child(dialog, "aboutLicenceValue").text() == "Apache License 2.0"
    for name, _url in _LINKS:
        _child(dialog, name)
    assert mute_message_boxes == []


# =========================================================================== #
# REQ-AV-UI-012 -- translated, and re-translated live                        #
# =========================================================================== #


def test_sc_av_ui_012_1_dialog_is_in_spanish(qtbot):
    """@C-11 / SC-AV-UI-012-1: every translated element differs from its
    English source; the product name, version, licence and environment
    values (identity/value elements, CL-AV-5) are unchanged."""
    win = _window(qtbot)
    _w, en_dialog = _open_about(qtbot, win)
    en_title = en_dialog.windowTitle()
    en_copy = _child(en_dialog, "aboutCopyButton").text()
    en_close = _child(en_dialog, "aboutCloseButton").text()
    en_accessible = {
        name: _child(en_dialog, name).accessibleName() for name in _TAB_CHAIN
    }
    en_dialog.close()

    try:
        assert win._language_manager.set_language("es") is True
        _w, es_dialog = _open_about(qtbot, win)

        assert es_dialog.windowTitle() != en_title
        assert _child(es_dialog, "aboutCopyButton").text() != en_copy
        assert _child(es_dialog, "aboutCloseButton").text() != en_close
        for name, en_name in en_accessible.items():
            es_name = _child(es_dialog, name).accessibleName()
            assert (
                es_name != "" and es_name != en_name
            ), f"{name} accessible name did not change: {es_name!r}"

        assert _child(es_dialog, "aboutNameLabel").text() == "PixelArt Creator"
        assert (
            _child(es_dialog, "aboutVersionValue").text()
            == pixelart_creator.__version__
        )
        assert _child(es_dialog, "aboutLicenceValue").text() == "Apache License 2.0"
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)


def test_sc_av_ui_012_2_open_dialog_retranslates_live(qtbot):
    """@C-12 / SC-AV-UI-012-2: the OPEN dialog's texts change to Spanish
    without closing and reopening it (CL-AV-7: driven through
    ``LanguageManager.set_language``, the neutral form C-12 asks for).

    ``QCoreApplication.installTranslator``/``removeTranslator`` deliver
    ``QEvent.LanguageChange`` as a POSTED event (first to the
    ``QApplication`` instance, which in turn posts it on to every top-level
    widget) -- never sent synchronously -- so an already-open dialog only
    picks up the new catalogue once the event loop actually processes that
    posted event. Verified directly this session (throwaway diagnostic,
    discarded): with no ``processEvents()`` the text is unchanged even after
    ``set_language`` returns; one ``QApplication.processEvents()`` call is
    enough to flush both posts and reach ``changeEvent``. The explicit call
    below drives that REAL propagation path -- the same one the shipped
    product relies on -- rather than a synthetic ``QApplication.sendEvent``,
    and matches this suite's own established convention for the identical
    ``LanguageManager.set_language`` + retranslation-assertion shape
    (``test_i18n_input_scheme.py``, e.g. its
    ``test_sc_b002_1_frame_panel_menu_labels_resolve_under_es``).
    """
    win, dialog = _open_about(qtbot)
    original_copy = _child(dialog, "aboutCopyButton").text()
    try:
        assert win._language_manager.set_language("es") is True
        QApplication.processEvents()
        assert _child(dialog, "aboutCopyButton").text() != original_copy
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)
        QApplication.processEvents()


def test_sc_av_ui_012_3_menu_entry_in_spanish(qtbot):
    """SC-AV-UI-012-3: the Ayuda menu's About entry reads in Spanish, as the
    Spanish catalogue renders it.

    See ``test_sc_av_ui_012_2_open_dialog_retranslates_live`` above for why
    ``QApplication.processEvents()`` is required here: the posted
    ``LanguageChange`` event that drives ``Main_Window.changeEvent`` /
    ``_retranslate`` needs the event loop to run once after
    ``set_language`` before the already-built ``_about_action`` re-sets its
    text.
    """
    win = _window(qtbot)
    english_text = win._about_action.text()
    try:
        assert win._language_manager.set_language("es") is True
        QApplication.processEvents()
        assert win._about_action.text() != english_text
        assert win._about_action.text() != ""
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)
        QApplication.processEvents()
