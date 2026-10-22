"""No ``QFont::setPointSize: Point size <= 0`` message from a combo box (OF7 ruling).

The defect
----------
Qt's ``windows11`` style sizes a combo box's drop-down arrow and its popup from
``widget.font().pointSize()``. The interface font is set by PIXEL size, so that
is ``-1`` and Qt printed ``QFont::setPointSize: Point size <= 0 (-1), must be
greater than 0`` the first time a combo box was measured (start-up: the Symmetry
panel's combo) or opened (any drop-down, with the style sheet in force). The fix
is in ``ui/app_font.py`` (a point-sized per-class font for ``QComboBox`` on that
style only). These tests are its regression guard.

Where the warning CAN fire, and where it cannot
-----------------------------------------------
Only on a native Windows 11 Qt platform: the ``windows`` platform plugin with the
``windows11`` style. ``offscreen`` uses the Fusion style, which never asks for the
point size, so a green headless run of the *scenario* says nothing about this
defect and is never read as coverage of it. The scenario tests therefore start
their own child process on the ``windows`` plugin (whatever platform the suite
itself runs on) and report ``SKIPPED`` with the measured reason when:

* the host is not Windows (no ``windows`` plugin exists), or
* the child reports a style other than ``windows11`` (Windows 10, an older Qt, or
  a style forced from outside).

A child that cannot start or crashes FAILS the test; that is information, not a
reason to skip.

The handler must be live
------------------------
A message handler that is not installed, or that something replaced, would let
the defect through in silence. So:

* ``test_the_handler_sees_a_deliberate_point_size_warning`` (runs on every
  platform) installs the same kind of handler in this process and checks it
  captures ``QFont().setPointSize(-1)``, and that it stays quiet for a valid size
  (so the pattern is not "any message");
* the child scenario fires the same deliberate warning BEFORE the scenario and
  AFTER it, and the parent fails unless both were captured: the handler was live
  at the start and still live at the end.

The unit-level check that also runs headless (the per-class combo font the fix
sets) is ``test_app_font.py::test_the_combo_box_gets_a_point_sized_interface_font``.

The whole-window walk (a guard against the NEXT widget of the same family)
--------------------------------------------------------------------------
The fix is class-specific (``QComboBox``). Measured on Windows 11, Qt 6.11.1, the
same message is still printed by a ``QPushButton`` with ``setMenu``, a
``QToolButton`` in ``MenuButtonPopup`` mode with a menu, a ``QDateEdit`` /
``QDateTimeEdit`` with ``setCalendarPopup(True)`` and a ``QCommandLinkButton`` with
a menu, once the style draws or measures them. None of them exists in the product
today, so the combo scenarios above cannot see the day one is added.
``test_walking_the_real_main_window_prints_no_point_size_warning`` is the guard:
it builds the real main window in a child process on the native platform, then
renders everything reachable without a user file (every dock docked and floated,
every tab and stacked page, every widget through ``grab()``, every menu, every
combo popup, the colour hub, every enabled menu-bar action with the modal
dialogs shown instead of run, and all six style x mode combinations) and fails on
any ``Point size <= 0`` message, naming the stage that printed it. Its handler is
proved live on both sides, like the scenarios above. Its reach is checked too: the
test fails unless fixed floors of widgets, docks, menus, combos and actions were
walked and a named set of dialogs was opened.

What the walk does NOT reach: a dialog or panel that needs a user file or a
signed-in service; the native file / colour / input dialogs (refused, not shown,
and measured clean in the original sweep); anything an action opens only on a
second step.

Isolation: every child redirects the settings store and the profile directories
into ``tmp_path`` (nothing of a real user's is read or written).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QFont

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: What the message says, whichever setter printed it (``setPointSize`` or
#: ``setPointSizeF``): the ruling is "any ``Point size <= 0`` message".
NEEDLE = "Point size <= 0"

#: The style Qt's Windows 11 look reports, and the only one that asks for the size.
WINDOWS11_STYLE = "windows11"


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture: each scenario sets its own."""
    return "none"


# --------------------------------------------------------------------------- #
# The handler, proved live in this process                                     #
# --------------------------------------------------------------------------- #


def _collect(action) -> List[str]:
    """Run ``action`` under a handler that records every Qt message; restore after."""
    seen: List[str] = []

    def handler(kind: QtMsgType, context: object, text: str) -> None:
        seen.append(text)

    previous = qInstallMessageHandler(handler)
    try:
        action()
    finally:
        qInstallMessageHandler(previous)
    return seen


def test_the_handler_sees_a_deliberate_point_size_warning() -> None:
    """Positive and negative control of the handler this module relies on."""
    caught = _collect(lambda: QFont().setPointSize(-1))
    assert any(NEEDLE in text for text in caught), (
        "the handler did not capture QFont().setPointSize(-1): it is not live, "
        f"so a green scenario would prove nothing (captured {caught!r})"
    )
    quiet = _collect(lambda: QFont().setPointSize(10))
    assert not any(
        NEEDLE in text for text in quiet
    ), f"the pattern matched a valid size: it matches too much ({quiet!r})"


# --------------------------------------------------------------------------- #
# The scenario, in a child process on the native Windows platform              #
# --------------------------------------------------------------------------- #

#: argv: settings root, scenario name. Prints one ``RESULT <json>`` line.
_CHILD = r"""
import json, os, sys, time
from pathlib import Path
from testing.suites.ui.conftest import redirect_settings_store, assert_settings_isolated
root = Path(sys.argv[1]); scenario = sys.argv[2]
redirect_settings_store(root); assert_settings_isolated(root)

from PySide6.QtCore import qInstallMessageHandler, qVersion
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QComboBox

stage = ["install"]
messages = []

def handler(kind, context, text):
    messages.append([stage[0], str(text)])

qInstallMessageHandler(handler)

def control(tag):
    # A deliberate warning: the handler must capture it (the parent checks both).
    stage[0] = tag
    QFont().setPointSize(-1)

def pump(app):
    for _ in range(3):
        app.processEvents()

control("control-before")

from pixelart_creator.ui import app_font
from pixelart_creator.ui.theme import DEFAULT_STYLE, THEME_LIGHT, apply_theme

popups = []

def combo_cycle(app, tag, parent=None):
    stage[0] = tag
    combo = QComboBox(parent)
    for text in ("one", "two", "three"):
        combo.addItem(text)
    combo.show(); pump(app)
    combo.showPopup()
    # The popup is shown a moment later on this style: wait (bounded) for it.
    deadline = time.monotonic() + 3.0
    while not combo.view().isVisible() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(0.01)
    pump(app)
    popups.append([tag, bool(combo.view().isVisible())])
    combo.hidePopup(); pump(app)
    combo.close(); combo.deleteLater(); pump(app)

stage[0] = "start-up"
# The style is read straight from Qt, before any style sheet wraps it, and not
# from the product's own bookkeeping: the measurement must not depend on the code
# under test (a build without the fix has no such record).
app = QApplication([])
style = app.style().objectName()
if scenario == "window":
    # The real launch: create_app reuses this application and builds the shown main
    # window (the Symmetry panel's combo is measured here, before the sheet is in
    # force).
    from pixelart_creator.ui.app import create_app
    app, window = create_app([])
    pump(app)
    family_on = QApplication.font().family()
    combo_cycle(app, "combo-after-start-up")
    combo_cycle(app, "combo-child-of-window", window)
    stage[0] = "system-font-on"
    window.set_use_system_font(True); pump(app)
    family_system = QApplication.font().family()
    combo_cycle(app, "combo-system-font")
    stage[0] = "system-font-off"
    window.set_use_system_font(False); pump(app)
    family_back = QApplication.font().family()
    combo_cycle(app, "combo-after-system-font-off")
    window.close(); pump(app)
else:
    # No main window: the style sheet comes first and only then a combo is opened.
    app_font.prepare_interface_font(app, False)
    stage[0] = "theme"
    # The sequence ``Main_Window`` runs after every theme change: the sheet wipes
    # the per-class fonts, ``ensure_interface_font`` puts them back.
    apply_theme(app, THEME_LIGHT, DEFAULT_STYLE)
    app_font.ensure_interface_font(app, False); pump(app)
    family_on = QApplication.font().family()
    family_system = family_back = family_on
    combo_cycle(app, "combo-with-sheet-in-force")
    combo_cycle(app, "second-combo")

control("control-after")
print("RESULT " + json.dumps(dict(
    platform=app.platformName(), style=style, qt=qVersion(),
    app_style_now=app.style().objectName(),
    family_on=family_on, family_system=family_system, family_back=family_back,
    popups=popups, messages=messages,
)), flush=True)
"""


#: argv: settings root, scenario name (unused). Prints one ``RESULT <json>`` line.
_WALK_CHILD = r"""
import json, os, sys, time, traceback
from pathlib import Path
from testing.suites.ui.conftest import redirect_settings_store, assert_settings_isolated
root = Path(sys.argv[1])
redirect_settings_store(root); assert_settings_isolated(root)

from PySide6.QtCore import QPoint, qInstallMessageHandler, qVersion
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QDockWidget, QFileDialog,
    QInputDialog, QMenu, QMessageBox, QStackedWidget, QTabWidget, QWidget,
)

stage = ["install"]
messages = []

def handler(kind, context, text):
    messages.append([stage[0], str(text)])

qInstallMessageHandler(handler)

def control(tag):
    # A deliberate warning: the handler must capture it (the parent checks both).
    stage[0] = tag
    QFont().setPointSize(-1)

def pump(n=3, nap=0.0):
    for _ in range(n):
        app.processEvents()
        if nap:
            time.sleep(nap)

control("control-before")

app = QApplication([])
style = app.style().objectName()
if style != "windows11":
    # Only that style reads the point size: report it and spare the long walk.
    print("RESULT " + json.dumps(dict(
        platform=app.platformName(), style=style, qt=qVersion(),
    )), flush=True)
    os._exit(0)

errors = []
# Wrappers that menuBar() / actions() / menu() hand out must outlive the walk: let
# one go and shiboken deletes the C++ menu under it (measured, see the report).
keep = []

def hook(kind, value, tb):
    text = "".join(traceback.format_exception_only(kind, value)).strip()
    errors.append([stage[0], text])
    sys.__excepthook__(kind, value, tb)

sys.excepthook = hook

timing = {}
t_zero = time.monotonic()

def lap(name):
    timing[name] = round(time.monotonic() - t_zero, 1)

walked = dict(
    dialogs=[], message_boxes=[], static_dialogs=[], top_levels=set(), menus=0,
    combos=0, docks=0, widgets=0, pages=0, actions=0, appearances=0, hub=False,
    converted_then_undone=0,
)

def settle(widget):
    t0 = time.monotonic()
    while not widget.isVisible() and time.monotonic() - t0 < 2.0:
        app.processEvents(); time.sleep(0.01)
    pump(2)

def shown_exec(self):
    # What ``exec()`` would have done, without blocking: show it, draw it, refuse it.
    walked["dialogs"].append(type(self).__name__)
    self.show(); settle(self)
    self.grab(); pump(2)
    if isinstance(self, QDialog):
        self.reject()
    else:
        self.close()
    pump(2)
    return 0

QDialog.exec = shown_exec
QMessageBox.exec = shown_exec

def shown_box(name):
    def run(parent, title, text, *args, **kwargs):
        walked["message_boxes"].append(name)
        box = QMessageBox(parent)
        box.setWindowTitle(str(title)); box.setText(str(text))
        box.show(); settle(box); box.grab(); box.close(); pump(2)
        return QMessageBox.StandardButton.Ok
    return run

for name in ("information", "warning", "critical", "question"):
    setattr(QMessageBox, name, staticmethod(shown_box(name)))

def refused(name, value):
    def run(*args, **kwargs):
        walked["static_dialogs"].append(name)
        return value
    return staticmethod(run)

QInputDialog.getText = refused("getText", ("", False))
QInputDialog.getItem = refused("getItem", ("", False))
QInputDialog.getInt = refused("getInt", (0, False))
QInputDialog.getDouble = refused("getDouble", (0.0, False))
QColorDialog.getColor = refused("getColor", QColor())
QFileDialog.getOpenFileName = refused("getOpenFileName", ("", ""))
QFileDialog.getOpenFileNames = refused("getOpenFileNames", ([], ""))
QFileDialog.getSaveFileName = refused("getSaveFileName", ("", ""))
QFileDialog.getExistingDirectory = refused("getExistingDirectory", "")

stage[0] = "start-up"
from pixelart_creator.data import style_catalog
from pixelart_creator.ui.app import create_app
app, window = create_app([])
pump(4, 0.02)
lap("start-up")

def note_and_close_top_levels():
    for top in QApplication.topLevelWidgets():
        if top is not window and top.isVisible():
            walked["top_levels"].add(type(top).__name__)
            if isinstance(top, QDialog):
                top.close()
    pump(2)

def open_combos():
    count = 0
    for combo in window.findChildren(QComboBox):
        if not combo.isVisible():
            continue
        combo.showPopup()
        t0 = time.monotonic()
        while not combo.view().isVisible() and time.monotonic() - t0 < 1.5:
            app.processEvents(); time.sleep(0.01)
        pump(2); combo.hidePopup(); pump(2)
        count += 1
    return count

stage[0] = "document"
if window.active_tab() is None:
    window.new_document(); pump(3)

# 1. every dock shown, docked and floated; every tab page and stacked page visited
docks = window.findChildren(QDockWidget); keep.append(docks)
for dock in docks:
    stage[0] = "dock:" + (dock.objectName() or dock.windowTitle())
    dock.show(); dock.raise_(); pump(2)
    dock.grab()
    dock.setFloating(True); pump(2); dock.grab(); dock.setFloating(False); pump(2)
walked["docks"] = len(docks)
lap("docks")
stage[0] = "pages"
for tabs in window.findChildren(QTabWidget):
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index); pump(1); walked["pages"] += 1
for stack in window.findChildren(QStackedWidget):
    for index in range(stack.count()):
        stack.setCurrentIndex(index); pump(1); walked["pages"] += 1

# 2. every widget rendered: grab() goes through the style's draw path
stage[0] = "grab-window"
window.grab(); pump(2)
stage[0] = "grab-widgets"
widgets = window.findChildren(QWidget); keep.append(widgets)
for widget in widgets:
    if widget.isVisibleTo(window):
        stage[0] = "grab:" + type(widget).__name__ + ":" + (widget.objectName() or "-")
        widget.grab(); walked["widgets"] += 1
pump(2)
lap("grab")

# 3. every menu popped, every visible combo opened
stage[0] = "menus"
menus = window.findChildren(QMenu); keep.append(menus)
for menu in menus:
    menu.popup(QPoint(80, 80)); pump(2); menu.hide(); walked["menus"] += 1
stage[0] = "combos"
walked["combos"] = open_combos()

lap("menus-combos")

# 4. the colour hub, the right-click menu of the canvas
stage[0] = "colour-hub"
window._open_colour_hub(0, 0); pump(3)
walked["hub"] = bool(window._colour_hub.isVisible())
window._colour_hub.grab(); window._colour_hub.hide(); pump(2)

# 5. every enabled leaf action of the menu bar, a checkable one toggled back again
def leaves(menu):
    keep.append(menu)
    for action in menu.actions():
        keep.append(action)
        if action.isSeparator():
            continue
        sub = action.menu()
        keep.append(sub)
        if sub is not None:
            yield from leaves(sub)
        else:
            yield action

SKIP = ("close", "quit", "exit")
bar = window.menuBar(); keep.append(bar)
for action in list(leaves(bar)):
    if not action.isEnabled():
        continue
    label = action.text().replace("&", "")
    if label.lower().startswith(SKIP):
        continue
    stage[0] = "action:" + label
    # Palette > Convert to Indexed maps every pixel of the blank, fully transparent
    # start-up document to palette entry 0, which is opaque black, so every later
    # stage would draw a black document (the pixels really are black: data, not
    # paint -- undo restores the checker). It is undoable, so it is undone right
    # away and the rest of the walk sees the document it started with.
    is_convert = action is window._to_indexed_action
    if is_convert:
        convert_record = window.active_tab()
        index_before = convert_record.stack.index()
    action.trigger(); pump(3); note_and_close_top_levels(); walked["actions"] += 1
    if is_convert and convert_record.stack.index() == index_before + 1:
        convert_record.stack.undo(); pump(3)
        assert convert_record.stack.index() == index_before
        walked["converted_then_undone"] += 1
    if action.isCheckable():
        stage[0] = "action-back:" + label
        action.trigger(); pump(3); note_and_close_top_levels()

lap("actions")

# 6. every style x mode: the sheet is re-applied, then drawn and a drop-down opened
for style_id in style_catalog.style_ids():
    for mode in ("light", "dark"):
        stage[0] = "appearance:" + style_id + "/" + mode
        window._switch_appearance(style_id, mode); pump(3)  # one sheet per pair
        window.grab(); open_combos(); walked["appearances"] += 1

lap("appearances")
control("control-after")
walked["top_levels"] = sorted(walked["top_levels"])
print("RESULT " + json.dumps(dict(
    platform=app.platformName(), style=style, qt=qVersion(),
    walked=walked, errors=errors, messages=messages, timing=timing,
)), flush=True)
os._exit(0)
"""


def _windows_child_env(profile: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env.update(
        PYTHONPATH=os.pathsep.join(
            [str(_REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        ),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
        QT_QPA_PLATFORM="windows",
    )
    # Anything that would change the style or mute the messages from outside.
    for name in ("QT_STYLE_OVERRIDE", "QT_LOGGING_RULES", "QT_QPA_FONTDIR"):
        env.pop(name, None)
    return env


def _run_scenario(
    tmp_path: Path, scenario: str, script: str = _CHILD, timeout: int = 150
) -> Dict[str, Any]:
    """Run ``scenario`` on the ``windows`` platform plugin; return its result."""
    if os.name != "nt":
        pytest.skip(
            "the defect needs Qt's windows11 style, which exists only on the "
            f"native 'windows' platform plugin; this host is os.name={os.name!r} "
            f"(sys.platform={sys.platform!r}), so the scenario cannot fire here"
        )
    profile = tmp_path / "profile"
    profile.mkdir(exist_ok=True)
    done = subprocess.run(
        [sys.executable, "-B", "-c", script, str(tmp_path / "qs-root"), scenario],
        cwd=str(_REPO_ROOT),
        env=_windows_child_env(profile),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert (
        done.returncode == 0
    ), f"the {scenario} child exited {done.returncode}\n{done.stdout}\n{done.stderr}"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, f"the child printed no RESULT line:\n{done.stdout}\n{done.stderr}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    assert result["platform"] == "windows", (
        f"the child was asked for the 'windows' plugin and ran on "
        f"{result['platform']!r}: the scenario did not run where it can fire"
    )
    if result["style"] != WINDOWS11_STYLE:
        pytest.skip(
            f"Qt {result['qt']} on the 'windows' plugin started in the style "
            f"{result['style']!r}, not {WINDOWS11_STYLE!r}: only the windows11 "
            "style reads the point size, so the scenario cannot fire here"
        )
    return result


def _messages_in(result: Dict[str, Any], stages: List[str]) -> List[List[str]]:
    return [m for m in result["messages"] if m[0] in stages]


def _assert_handler_was_live(result: Dict[str, Any]) -> None:
    """Both deliberate warnings must have been captured, or the run proves nothing."""
    for tag in ("control-before", "control-after"):
        captured = [m for m in _messages_in(result, [tag]) if NEEDLE in m[1]]
        assert captured, (
            f"the deliberate QFont().setPointSize(-1) at {tag!r} was NOT captured: "
            "the message handler is dead, so a clean scenario would prove nothing. "
            f"All captured messages: {result['messages']!r}"
        )


def _assert_no_point_size_message(result: Dict[str, Any]) -> None:
    scenario_stages = [
        m
        for m in result["messages"]
        if m[0] not in ("install", "control-before", "control-after")
    ]
    offending = [m for m in scenario_stages if NEEDLE in m[1]]
    assert not offending, (
        f"{len(offending)} 'Point size <= 0' message(s) from the scenario "
        f"(stage, text): {offending!r}"
    )


def test_a_launch_and_every_combo_box_print_no_point_size_warning(
    tmp_path: Path,
) -> None:
    """A real launch, drop-downs opened, "Use system font" toggled: no warning.

    Native Windows 11 only (see the module docstring); skipped elsewhere with the
    measured reason. Covers the start-up measurement of the Symmetry panel's combo
    (``Main_Window`` construction) and every later ``showPopup``.
    """
    result = _run_scenario(tmp_path, "window")
    _assert_handler_was_live(result)
    # The scenario really ran: each popup was open, and the toggle really changed
    # the application font (a no-op toggle would test nothing).
    assert len(result["popups"]) == 4 and all(
        shown for _, shown in result["popups"]
    ), f"a drop-down did not open: {result['popups']!r}"
    assert result["family_on"] == "Nifen Art"
    assert result["family_system"] != "Nifen Art", result["family_system"]
    assert result["family_back"] == "Nifen Art"
    _assert_no_point_size_message(result)


def test_a_drop_down_opened_with_the_style_sheet_in_force_prints_no_warning(
    tmp_path: Path,
) -> None:
    """No main window: the first combo is opened only after the theme is applied.

    The second trigger of the defect (the popup, delegated to the base style),
    isolated from the start-up measurement the first test already covers.
    """
    result = _run_scenario(tmp_path, "bare")
    _assert_handler_was_live(result)
    assert len(result["popups"]) == 2 and all(
        shown for _, shown in result["popups"]
    ), f"a drop-down did not open: {result['popups']!r}"
    assert result["family_on"] == "Nifen Art"
    _assert_no_point_size_message(result)


#: What the walk must at least have reached (measured 2026-10-22 on the real window:
#: 623 widgets, 34 docks, 23 menus, 10 combos, 104 actions, 9 dialogs run through
#: ``exec``; the floors sit well under that, so a normal product change does not
#: trip them, while a walk that silently stopped doing its work does).
_WALK_FLOORS = dict(widgets=400, docks=30, menus=15, combos=8, actions=80, pages=3)

#: Dialogs the actions open through ``exec()``: if one of these disappears from the
#: walk, the walk lost its way to it.
_WALK_EXPECTED_DIALOGS = (
    "New_Document_Dialog",
    "Export_Dialog",
    "Scale_Dialog",
    "Canvas_Size_Dialog",
    "RotSprite_Dialog",
    "Extract_Palette_Dialog",
    "Iso_Grid_Dialog",
    "Vanishing_Point_Dialog",
)
#: Windows the actions show without ``exec()`` (``open()`` / ``show()``).
_WALK_EXPECTED_TOP_LEVELS = ("About_Dialog", "User_Guide_Dialog")


@pytest.mark.timeout(480)  # CI caps a test at 120 s; the walk is one long child
def test_walking_the_real_main_window_prints_no_point_size_warning(
    tmp_path: Path,
) -> None:
    """Every widget, menu, popup and dialog of the real window: no warning.

    The guard against the NEXT widget of the family the combo fix does not cover
    (``QPushButton`` + ``setMenu``, ``QToolButton`` in ``MenuButtonPopup`` mode with
    a menu, ``QDateEdit`` calendar popup, ``QCommandLinkButton`` + menu). Native
    Windows 11 only (see the module docstring); skipped elsewhere with the measured
    reason.
    """
    result = _run_scenario(tmp_path, "walk", _WALK_CHILD, timeout=420)
    walked = result["walked"]
    # The denominator, printed (pytest shows it on a failure or with ``-s``).
    print(
        "walk examined:",
        {k: (len(v) if isinstance(v, list) else v) for k, v in walked.items()},
        "timing (s, cumulative):",
        result.get("timing"),
    )
    _assert_handler_was_live(result)
    # The walk really walked: a floor on every count, and the named dialogs.
    for key, floor in _WALK_FLOORS.items():
        assert walked[key] >= floor, (
            f"the walk reached only {walked[key]} {key} (floor {floor}): it "
            f"stopped doing its work, so a clean run proves nothing. {walked!r}"
        )
    missing = [n for n in _WALK_EXPECTED_DIALOGS if n not in walked["dialogs"]]
    assert not missing, f"the walk never opened {missing!r}: {walked['dialogs']!r}"
    missing = [n for n in _WALK_EXPECTED_TOP_LEVELS if n not in walked["top_levels"]]
    assert not missing, f"the walk never showed {missing!r}: {walked['top_levels']!r}"
    assert walked["hub"], "the colour hub did not open"
    assert walked["converted_then_undone"] == 1, (
        "Palette > Convert to Indexed was not run and undone exactly once "
        f"({walked['converted_then_undone']}): either the walk no longer reaches it, "
        "or it stopped being one undoable command -- and a converted blank document "
        "is opaque black for every later stage of the walk"
    )
    assert walked["appearances"] >= 6, walked["appearances"]
    _assert_no_point_size_message(result)
