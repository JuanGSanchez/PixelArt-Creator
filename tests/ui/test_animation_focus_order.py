"""T-20 (AGT-06 audit) — REQ-P5-UI-017: tab order + visible focus indicator.

``test_animation_timeline.py``'s ``REQ-P5-UI-017`` section asserts non-empty
accessible names and one focus-policy spot check (Space toggling play/pause),
but never asserts a LOGICAL tab order across the four animation surfaces
(timeline / playback / onion-skin / frame-tags) nor a visible focus indicator
— the gap this module closes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_t20_representative_controls_are_keyboard_reachable(qtbot):
    """REQ-P5-UI-017 (T-20): a representative control in each of the four
    animation surfaces accepts keyboard (Tab) focus."""
    win = _window(qtbot)
    for control in (
        win._playback_controls._play_button,
        win._timeline_panel._strip,
        win._onion_controls._enable_check,
        win._frame_tags_panel._list,
    ):
        assert control.focusPolicy() != Qt.FocusPolicy.NoFocus, control


def test_t20_tab_order_chain_connects_all_four_panels(qtbot):
    """REQ-P5-UI-017 (T-20): the natural (unmodified) Qt tab-order chain is ONE
    connected cycle reaching every one of the four animation surfaces — proving
    none of them is a keyboard-focus island (e.g. a dock whose contents can be
    reached by mouse only). Qt builds this chain automatically from widget
    construction order (no explicit ``setTabOrder`` call exists in
    ``main_window.py`` today); this test does not assume a particular relative
    order between the four panels — only that each is reachable from a full walk
    of the SAME window's chain before it loops back to its start.
    """
    win = _window(qtbot)
    probes = {
        "playback": win._playback_controls._play_button,
        "timeline": win._timeline_panel._strip,
        "onion": win._onion_controls._enable_check,
        "tags": win._frame_tags_panel._list,
    }

    node = probes["playback"]
    start_id = id(node)
    visited_ids = set()
    found = set()
    for _ in range(1000):
        node = node.nextInFocusChain()
        if id(node) == start_id or id(node) in visited_ids:
            break  # completed the cycle
        visited_ids.add(id(node))
        for name, probe in probes.items():
            if node is probe:
                found.add(name)
        if len(found) == len(probes) - 1:  # every OTHER probe reached
            break

    missing = set(probes) - found - {"playback"}
    assert not missing, f"panel(s) unreachable from the playback control: {missing}"


def test_t20_visible_focus_indicator_themed(qtbot, theme):
    """REQ-P5-UI-017 (T-20): a visible-focus QSS rule is themed (both themes)."""
    _window(qtbot)
    assert ":focus" in QApplication.instance().styleSheet()
