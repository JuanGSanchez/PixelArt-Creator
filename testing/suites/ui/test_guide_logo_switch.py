"""The hidden switch over the user guide's logo (REQ-VI-UI-017).

What is covered, by scenario id (the visual-identity feature's scenarios):

* **SC-VI-UI-017-1** activating the switch toggles the guide's page text to Nifen
  Art and back, and no text outside the page changes font (a snapshot of every
  widget font in the main window and the guide, of the application font and of
  the per-class fonts, taken before and after, with a control that the snapshot
  notices a font change);
* **SC-VI-UI-017-2** the switch is reached with Tab, wears the focus ring (counted
  in rendered pixels), exposes an accessible name that says what it does,
  toggles on Enter, on Space and on a click, and shows no label;
* **SC-VI-UI-017-3** the state is remembered: announced through
  ``pixelFontChanged`` (the observer is connected before the action), stored,
  and seen by the next window's guide;
* where the switch sits: it covers the logo as PAINTED (found by matching the
  logo's own pixels in a grab of the page, with a control that the matcher can
  fail), after a scroll, a resize and a change of topic; it is hidden on a page
  with no logo and covers the alternative text when the asset is missing.

Both modes. Every test takes the ``mode`` parameter of ``test_app_font`` (Light
and Dark), plants it in the settings store and reads it back from the window.

First display versus later. The page is laid out before the logo's image is
registered, so on the first display the logo's line is 16 px tall while the image
is painted 128 px tall; the document is laid out again on the first resize. The
tests that ask about something other than that first display (keyboard, focus
ring, snapshot) call :func:`relayout` first, so one cause does not decide all of
them; ``test_the_switch_covers_the_painted_logo_on_first_display`` asks the
first-display question and nothing else.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QFont, QImage
from PySide6.QtWidgets import QApplication, QTextBrowser, QWidget

from pixelart_creator.ui import app_font
from pixelart_creator.ui import user_guide as user_guide_module
from pixelart_creator.ui.app_icon import guide_logo_image
from pixelart_creator.ui.guide_logo_switch import LOGO_SWITCH_OBJECT_NAME
from pixelart_creator.ui.theme import THEME_LIGHT
from testing.suites.ui.focus_helpers import (
    assert_focus_rendered,
    grab_image,
    image_array,
)
from testing.suites.ui.test_app_font import (  # noqa: F401  (fixtures used by name)
    NIFEN,
    _leave_the_font_as_found,
    _store_is_isolated,
    facts_of,
    mode,
    open_guide,
    open_window,
    say,
    theme,
)
from testing.suites.ui.test_user_guide import _make_dialog

_LOGO_URL = "pac-logo.png"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def relayout(dialog) -> None:
    """Make the page lay itself out again (what the first resize does)."""
    size = dialog.size()
    dialog.resize(size.width() + 1, size.height())
    QApplication.processEvents()
    dialog.resize(size)
    QApplication.processEvents()


def _agreement(view: np.ndarray, logo: np.ndarray, x: int, y: int) -> Tuple[float, int]:
    """Return ``(share, opaque pixels compared)`` of ``logo`` placed at ``(x, y)``."""
    y0, y1 = max(0, y), min(view.shape[0], y + logo.shape[0])
    x0, x1 = max(0, x), min(view.shape[1], x + logo.shape[1])
    if y1 <= y0 or x1 <= x0:
        return 0.0, 0
    part = logo[y0 - y : y1 - y, x0 - x : x1 - x]
    mask = part[..., 3] == 255
    count = int(mask.sum())
    if count == 0:
        return 0.0, 0
    same = (view[y0:y1, x0:x1, :3][mask] == part[..., :3][mask]).all(axis=1)
    return float(same.mean()), count


def painted_logo_rect(browser: QTextBrowser, image: Optional[QImage] = None):
    """Return ``(rect, score)``: where the logo's pixels are in the page, or ``None``.

    Found from the logo's own pixels, independent of the layout code the switch
    uses: a few hundred of its opaque pixels vote for every offset they would put
    the logo at, and the best offsets are then compared in full. The rectangle can
    lie partly above the viewport (an inline image sits on its line's baseline).
    """
    logo = image if image is not None else guide_logo_image()
    assert logo is not None
    lg = image_array(logo)
    view = image_array(grab_image(browser.viewport()))
    height, width = view.shape[:2]
    ys, xs = np.nonzero(lg[..., 3] == 255)
    pick = np.linspace(0, ys.size - 1, 160).astype(int)
    pad = max(lg.shape)
    votes = np.zeros((height + 2 * pad, width + 2 * pad), dtype=np.int32)
    for index in pick:
        dy, dx = int(ys[index]), int(xs[index])
        equal = (view[..., :3] == lg[dy, dx, :3]).all(axis=2)
        votes[pad - dy : pad - dy + height, pad - dx : pad - dx + width] += equal
    order = np.argsort(votes, axis=None)[::-1][:12]
    best: Optional[Tuple[float, int, int]] = None
    for flat in order:
        vy, vx = np.unravel_index(flat, votes.shape)
        x, y = int(vx) - pad, int(vy) - pad
        share, count = _agreement(view, lg, x, y)
        if count >= 400 and (best is None or share > best[0]):
            best = (share, x, y)
    if best is None or best[0] < 0.98:
        return None, 0.0 if best is None else best[0]
    return QRect(best[1], best[2], lg.shape[1], lg.shape[0]), best[0]


def font_snapshot(win, dialog) -> Dict[str, str]:
    """Return the font of every widget of the window and the guide, and the app's.

    The page's own document default font is left out: it is the one font the
    switch is allowed to change. Everything else is in: widget fonts (the page
    pane's own included), the application font and every per-class font.
    """
    snapshot: Dict[str, str] = {}
    for owner, root in (("window", win), ("guide", dialog)):
        for index, widget in enumerate([root, *root.findChildren(QWidget)]):
            key = f"{owner}:{index}:{type(widget).__name__}:{widget.objectName()}"
            snapshot[key] = widget.font().toString()
    snapshot["application"] = QApplication.font().toString()
    for name in app_font._PLATFORM_CLASS_FONTS:
        snapshot[f"class:{name}"] = QApplication.font(name).toString()  # type: ignore[call-overload]
    return snapshot


def changed(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
    """Return the keys whose font differs (or that appeared or vanished)."""
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


def page_family(dialog) -> str:
    """Return the family the page's text is given."""
    return dialog._content_view.document().defaultFont().family()


# --------------------------------------------------------------------------- #
# SC-VI-UI-017-1: it toggles the page text and nothing else                     #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_017_1_the_switch_toggles_the_page_text_and_nothing_else(
    qtbot, capsys, mode
):
    """SC-VI-UI-017-1: page text to Nifen Art and back; no other font changes.

    A snapshot of every widget font in the window and the guide, of the
    application font and of the per-class fonts, is taken before, with the switch
    on and after switching off again. Only the page's own document font may differ.
    The control: a font change the snapshot is supposed to notice is made on the
    topic list and must show up in the difference.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    platform = app_font.platform_default_font().family()
    assert platform != NIFEN
    switch = dialog._logo_switch
    assert switch.isVisible()
    before = font_snapshot(win, dialog)
    assert page_family(dialog) == platform

    # Control: the snapshot sees a font change on a widget that is not the page.
    bold = QFont(dialog._toc_tree.font())
    bold.setBold(True)
    original = QFont(dialog._toc_tree.font())
    dialog._toc_tree.setFont(bold)
    seen = changed(before, font_snapshot(win, dialog))
    dialog._toc_tree.setFont(original)
    assert any(
        "QTreeWidget" in key for key in seen
    ), "the snapshot is blind to a font change"
    assert changed(before, font_snapshot(win, dialog)) == []

    switch.click()
    QApplication.processEvents()
    after_on = font_snapshot(win, dialog)
    say(
        capsys,
        f"[{mode}] {len(before)} fonts snapshotted; page {page_family(dialog)!r}; "
        f"{len(changed(before, after_on))} differ with the switch on",
    )
    assert len(before) > 100, "the snapshot examined almost nothing"
    assert page_family(dialog) == NIFEN
    assert facts_of(dialog._content_view.document().defaultFont()).resolved == NIFEN
    assert changed(before, after_on) == [], "a font outside the page changed"

    switch.click()
    QApplication.processEvents()
    assert page_family(dialog) == platform
    assert changed(before, font_snapshot(win, dialog)) == [], "a font did not come back"


# --------------------------------------------------------------------------- #
# SC-VI-UI-017-2: keyboard, name, ring, no label                                #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_017_2_tab_reaches_the_switch_and_enter_and_space_toggle_it(
    qtbot, mode
):
    """SC-VI-UI-017-2: Tab from the search field gets to the logo; Enter and Space toggle.

    Keys are sent as the keyboard would: Tab presses to the focused widget, then
    Enter, then Space. The page text follows each one.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    dialog.activateWindow()
    qtbot.waitUntil(dialog.isActiveWindow, timeout=2000)
    switch = dialog._logo_switch
    dialog._search_edit.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    assert QApplication.focusWidget() is dialog._search_edit
    path: List[str] = []
    # A text browser takes Tab to walk its own links first; the logo comes after.
    links = sum(
        1
        for block in _blocks(dialog._content_view)
        for fragment in _fragments(block)
        if fragment.charFormat().isAnchor()
    )
    assert links > 0
    for _ in range(links + 6):
        qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
        focus = QApplication.focusWidget()
        path.append(type(focus).__name__ if focus is not None else "none")
        if focus is switch:
            break
    assert QApplication.focusWidget() is switch, f"Tab never reached the logo: {path}"
    assert page_family(dialog) != NIFEN
    qtbot.keyClick(switch, Qt.Key.Key_Return)
    assert page_family(dialog) == NIFEN, "Enter did not toggle the page text on"
    qtbot.keyClick(switch, Qt.Key.Key_Return)
    assert page_family(dialog) != NIFEN, "Enter did not toggle the page text off"
    qtbot.keyClick(switch, Qt.Key.Key_Space)
    assert page_family(dialog) == NIFEN, "Space did not toggle the page text on"
    qtbot.keyClick(switch, Qt.Key.Key_Space)
    assert page_family(dialog) != NIFEN, "Space did not toggle the page text off"


def test_sc_vi_ui_017_2_the_switch_wears_the_focus_ring_in_rendered_pixels(
    qtbot, capsys, mode
):
    """SC-VI-UI-017-2: reaching the logo shows the focus indicator (counted pixels).

    The shared focus check: no focus-colour pixel without focus, some with it,
    none again after focus-out, and a non-zero number of pixels examined.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    evidence = assert_focus_rendered(qtbot, dialog._logo_switch, mode)
    say(capsys, f"[{mode}] {evidence.describe()}")
    assert evidence.focused_px > 0 and evidence.examined > 0


def test_sc_vi_ui_017_2_the_switch_exposes_an_accessible_name_and_shows_no_label(
    qtbot, mode
):
    """SC-VI-UI-017-2: a name that says what it does, re-set on a language change; no label.

    No text, no icon, and the page renders identically with the switch hidden and
    shown (unfocused): the logo underneath is the only thing visible.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    switch = dialog._logo_switch
    assert switch.objectName() == LOGO_SWITCH_OBJECT_NAME
    name = switch.accessibleName()
    assert name, "the switch has no accessible name"
    lowered = name.lower()
    assert "pixel font" in lowered and "guide" in lowered, name
    assert switch.text() == "" and switch.icon().isNull()
    assert switch.toolTip() == ""
    # The name comes from tr(): a language change re-sets it.
    switch.setAccessibleName("stale")
    QApplication.sendEvent(switch, QEvent(QEvent.Type.LanguageChange))
    assert switch.accessibleName() == name
    # Visible label: none. The page looks the same with the switch hidden.
    QApplication.processEvents()
    switch.clearFocus()
    QApplication.processEvents()
    shown = image_array(grab_image(dialog._content_view.viewport()))
    switch.hide()
    QApplication.processEvents()
    hidden = image_array(grab_image(dialog._content_view.viewport()))
    switch.show()
    assert shown.shape == hidden.shape
    assert np.array_equal(shown, hidden), "the switch paints something over the page"


def test_a_click_on_the_logo_toggles_the_page_text(qtbot, mode):
    """SC-VI-UI-017-1: a mouse click on the logo toggles, and a click elsewhere does not."""
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    switch = dialog._logo_switch
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert page_family(dialog) == NIFEN
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert page_family(dialog) != NIFEN
    qtbot.mouseClick(
        dialog._content_view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(300, 400)
    )
    assert page_family(dialog) != NIFEN


# --------------------------------------------------------------------------- #
# SC-VI-UI-017-3: remembered                                                    #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_017_3_the_switch_is_announced_stored_and_seen_by_the_next_guide(
    qtbot, mode
):
    """SC-VI-UI-017-3: ``pixelFontChanged``, the stored value, a second window's guide.

    The signal observer is connected before the click. The value reaches the
    store; a window built afterwards (in a process state of a new launch) opens
    its guide with the page text in Nifen Art; switching off is stored too. The
    real interpreter restart is in ``test_app_font``.
    """
    from pixelart_creator.ui.appearance_settings import (
        KEY_GUIDE_PIXEL_FONT,
        SETTINGS_GROUP,
        load_appearance,
    )
    from testing.suites.ui.test_app_font import _production_settings

    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    assert load_appearance().guide_pixel_font is False
    with qtbot.waitSignal(dialog.pixelFontChanged, timeout=1000) as on:
        dialog._logo_switch.click()
    assert on.args == [True]
    assert load_appearance().guide_pixel_font is True
    settings = _production_settings()
    settings.beginGroup(SETTINGS_GROUP)
    raw = settings.value(KEY_GUIDE_PIXEL_FONT)
    settings.endGroup()
    assert str(raw).lower() in ("true", "1"), f"stored {raw!r}"

    second = open_window(qtbot, mode, keep_store=True, fresh=False)
    guide = open_guide(second, qtbot)
    assert guide.page_uses_pixel_font() is True
    assert page_family(guide) == NIFEN
    with qtbot.waitSignal(guide.pixelFontChanged, timeout=1000) as off:
        guide._logo_switch.click()
    assert off.args == [False]
    assert load_appearance().guide_pixel_font is False


# --------------------------------------------------------------------------- #
# Where the switch sits                                                         #
# --------------------------------------------------------------------------- #


def test_the_logo_matcher_finds_the_logo_and_can_fail(qtbot):
    """Control for the geometry tests: the matcher finds the real logo, not an inverse.

    After a re-layout the logo is found at the position the layout gives it; the
    same search with the logo's colours inverted must find nothing.
    """
    win = open_window(qtbot, THEME_LIGHT)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    rect, score = painted_logo_rect(dialog._content_view)
    assert rect is not None and score == 1.0, f"the logo was not found ({score})"
    real = guide_logo_image()
    assert real is not None
    inverse = QImage(real)
    inverse.invertPixels(QImage.InvertMode.InvertRgb)
    other, other_score = painted_logo_rect(dialog._content_view, inverse)
    assert other is None, f"the matcher found an inverted logo ({other_score})"


def test_the_switch_covers_the_painted_logo_on_first_display(qtbot, capsys, mode):
    """The switch covers the logo as painted, the first time the page is shown.

    "Covers" is tested both ways: the switch's rectangle is the painted logo's
    rectangle (the part of it inside the page). The painted rectangle is found by
    matching the logo's pixels, not by asking the layout code the switch uses.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    switch = dialog._logo_switch
    painted, score = painted_logo_rect(dialog._content_view)
    assert painted is not None, f"the logo is not painted on the page (match {score})"
    viewport = dialog._content_view.viewport().rect()
    inside = painted.intersected(viewport)
    say(
        capsys,
        f"[{mode}] first display: logo painted at {painted.getRect()}, "
        f"switch at {switch.geometry().getRect()}",
    )
    assert switch.isVisible()
    assert switch.geometry().contains(inside), (
        f"the painted logo {painted.getRect()} is not covered by the switch "
        f"{switch.geometry().getRect()}"
    )


@pytest.mark.parametrize("change", ["resize", "scroll", "topic"])
def test_the_switch_follows_the_logo_after_a_layout_change(qtbot, capsys, mode, change):
    """After a re-layout, a scroll or a change of topic the switch is on the logo again."""
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    browser = dialog._content_view
    switch = dialog._logo_switch

    def on_logo() -> Tuple[QRect, QRect]:
        painted, score = painted_logo_rect(browser)
        assert painted is not None, f"the logo is not painted (match {score})"
        return painted, switch.geometry()

    painted, geometry = on_logo()
    assert (
        geometry == painted
    ), f"before the change: {painted.getRect()} / {geometry.getRect()}"
    if change == "resize":
        dialog.resize(dialog.width() + 140, dialog.height() + 30)
        QApplication.processEvents()
    elif change == "scroll":
        bar = browser.verticalScrollBar()
        assert bar.maximum() > 10, "the page is too short to scroll"
        bar.setValue(10)
        QApplication.processEvents()
    else:
        dialog.show_topic("layers")
        QApplication.processEvents()
        dialog.show_topic("app-basics")
        QApplication.processEvents()
        relayout(dialog)
    painted, geometry = on_logo()
    say(
        capsys,
        f"[{mode}] after {change}: logo {painted.getRect()}, switch {geometry.getRect()}",
    )
    assert (
        geometry == painted
    ), f"after {change}: {painted.getRect()} / {geometry.getRect()}"


def test_the_switch_is_hidden_on_a_page_with_no_logo_and_skipped_by_tab(qtbot, mode):
    """A topic page without the logo has no switch to see or to reach."""
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    switch = dialog._logo_switch
    assert switch.isVisible()
    dialog.show_topic("layers")
    QApplication.processEvents()
    assert dialog._content_view.document().toPlainText(), "the layers page is empty"
    assert _LOGO_URL not in _image_fragments(
        dialog._content_view
    ), "the layers page has the logo"
    assert not switch.isVisible(), "the switch is shown on a page with no logo"
    assert switch.focusPolicy() != Qt.FocusPolicy.NoFocus
    dialog.show_topic("app-basics")
    relayout(dialog)
    assert switch.isVisible()


def _blocks(browser: QTextBrowser):
    block = browser.document().begin()
    while block.isValid():
        yield block
        block = block.next()


def _fragments(block):
    it = block.begin()
    while not it.atEnd():
        fragment = it.fragment()
        if fragment.isValid():
            yield fragment
        it += 1


def _image_fragments(browser: QTextBrowser) -> List[str]:
    names: List[str] = []
    block = browser.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                names.append(fragment.charFormat().toImageFormat().name())
            it += 1
        block = block.next()
    return names


def test_the_switch_covers_the_alternative_text_when_the_asset_is_missing(
    qtbot, monkeypatch, mode
):
    """A missing logo asset: the importer draws the alternative text; the switch covers it.

    The asset loader is made to return nothing (the product's own degrade path).
    The page still has the image fragment, the switch is shown over its line and
    still toggles the page text.
    """
    monkeypatch.setattr(user_guide_module, "guide_logo_image", lambda: None)
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    relayout(dialog)
    switch = dialog._logo_switch
    assert _LOGO_URL in _image_fragments(dialog._content_view)
    assert switch.isVisible(), "the switch vanished with the asset"
    assert not switch.geometry().isEmpty()
    assert switch.geometry().intersects(dialog._content_view.viewport().rect())
    switch.click()
    assert page_family(dialog) == NIFEN


def test_the_page_text_follows_the_switch_state_given_at_construction(qtbot, mode):
    """A guide built with the remembered switch on starts in Nifen Art; off, in the platform font."""
    dialog = _make_dialog(qtbot, guide_pixel_font=True)
    assert dialog.page_uses_pixel_font() is True
    assert page_family(dialog) == NIFEN
    other = _make_dialog(qtbot, guide_pixel_font=False)
    assert other.page_uses_pixel_font() is False
    assert page_family(other) == app_font.platform_default_font().family() != NIFEN
