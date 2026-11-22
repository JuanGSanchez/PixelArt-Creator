"""Repeated live language switching on ONE window, through the real selector.

REQ-L10N-UI-001 / SC-L10N-UI-001-2: switching through the shipped languages in
sequence on one live main window, and then back to English, raises no error,
and afterwards the interface is in the last language chosen.

The sequence is built from the languages the Language menu actually offers, so
it grows with the catalogues: with English and Spanish shipped it is
``en -> es -> en -> es -> en``; with every shipped language it visits each one
and returns to English, twice. Each switch goes through the real selector -- the
menu entry itself, either activated (``QAction.trigger``, the keyboard and
accessibility path) or clicked in the opened menu -- never through
``LanguageManager.set_language`` directly.

Instrument and controls
-----------------------
A probe that reports "nothing happened" is only worth something if it would
have reported a failure. The cycle reads one watcher, and before the cycle runs
the ``instrument_proven`` fixture shows that watcher each failure channel:

* a ``SystemError`` raised from a Python ``eventFilter`` while an event is
  delivered, which Qt hands back to the Python caller that dispatched the event
  (the failure mode that was once observed on repeated switching);
* an exception raised in a callback that Qt's own event loop invokes, which
  pytest-qt captures from the exception hook;
* an exception that escapes where nothing can catch it (``__del__``), which only
  the unraisable-exception hook sees;
* and silence: the same deliveries with nothing planted report nothing.

The cycle carries one more control. Every switch must change the visible text
(action texts, tool tips and accessible names), and revisiting a language must
restore exactly what that language showed the first time. A cycle whose
switches changed nothing would otherwise pass vacuously; this one fails.

What the cycle must NOT do, and why. The window's menus are never read through
``QAction.menu()``. Measured with PySide6 6.11.1 in a bare ``QMainWindow`` (no
product code): for a menu created with ``QMenuBar.addMenu(str)``, calling
``QAction.menu()`` and dropping the returned wrapper deletes the underlying
``QMenu`` although its owner still holds a reference. A window whose menus were
deleted that way fails on the next language change, and that failure has been
mistaken for a defect of the switching. The snapshot below walks
``findChildren`` instead, which leaves every menu alive.
"""

from __future__ import annotations

import contextlib
import gc
import sys
import traceback
from collections import Counter
from types import TracebackType
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple, TypeVar

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractButton, QApplication, QDockWidget, QWidget
from pytestqt.exceptions import capture_exceptions

from pixelart_creator.logic.language_names import selector_entries
from pixelart_creator.ui.main_window import Main_Window

_Result = TypeVar("_Result")

#: The source language: the window starts here and every cycle returns here.
_SOURCE_LANGUAGE = "en"

#: How many times the whole round trip (every other language, then back to the
#: source language) is repeated on the one window. Two is the smallest number
#: that repeats a switch; the failure that prompted this module needed it.
_ROUND_TRIPS = 2

_Snapshot = Counter


# --------------------------------------------------------------------------- #
# The watcher: every channel a failure of a language switch can arrive on     #
# --------------------------------------------------------------------------- #


class _Watch:
    """What escaped while a block ran, by the channel it escaped on."""

    def __init__(self) -> None:
        """Start empty; :func:`_watching` and :meth:`run` fill the three channels."""
        self.raised: List[str] = []
        self.captured: List[
            Tuple[type[BaseException], BaseException, Optional[TracebackType]]
        ] = []
        self.unraisable: List[str] = []

    @property
    def hooked(self) -> List[str]:
        """Return the callback exceptions captured so far, with tracebacks."""
        return [
            f"{kind.__name__}: {value}\n"
            + "".join(traceback.format_exception(kind, value, tb))
            for kind, value, tb in self.captured
        ]

    def run(self, step: Callable[[], _Result]) -> Optional[_Result]:
        """Run ``step``; record, instead of propagating, what it raises.

        Qt hands an exception raised in a Python override back to the Python
        caller that dispatched the event, so it surfaces here and not in a hook.
        """
        try:
            return step()
        except Exception as error:  # noqa: BLE001 (recorded, never hidden)
            self.raised.append(
                f"{type(error).__name__}: {error}\n" + traceback.format_exc()
            )
            return None

    @property
    def problems(self) -> List[str]:
        """Return one readable entry per thing that escaped, on any channel."""
        return self.raised + self.hooked + self.unraisable

    def kinds(self) -> List[str]:
        """Return the exception class names that escaped, in order."""
        return [entry.split(":", 1)[0] for entry in self.problems]


@contextlib.contextmanager
def _watching() -> Iterator[_Watch]:
    """Collect every exception that escapes inside the block.

    Besides what :meth:`_Watch.run` records, this collects exceptions raised in
    callbacks Qt's event loop invokes (pytest-qt's capture, which keeps them from
    failing the test later) and unraisable exceptions (``sys.unraisablehook``). A
    collection pass runs before the block closes so a due finaliser reports
    inside the block.
    """
    watch = _Watch()
    previous_hook = sys.unraisablehook

    def _record(unraisable: "sys.UnraisableHookArgs") -> None:
        watch.unraisable.append(
            f"{type(unraisable.exc_value).__name__}: {unraisable.exc_value}"
            f" (unraisable, {unraisable.err_msg})"
        )

    sys.unraisablehook = _record
    try:
        with capture_exceptions() as captured:
            watch.captured = captured
            try:
                yield watch
            finally:
                gc.collect()
            watch.captured = list(captured)
    finally:
        sys.unraisablehook = previous_hook


# --------------------------------------------------------------------------- #
# Known-true controls for the watcher                                         #
# --------------------------------------------------------------------------- #


class _PlantedFilter(QObject):
    """An application-wide filter that raises ``SystemError`` on a language change."""

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        """Raise for ``LanguageChange``; ignore everything else."""
        if event.type() == QEvent.Type.LanguageChange:
            raise SystemError("planted: the failure the watcher must see")
        return False


class _PlantedUnraisable:
    """An object whose finaliser raises, which nothing can catch."""

    def __del__(self) -> None:
        """Raise from the finaliser."""
        raise RuntimeError("planted: the failure the watcher must see")


def _plant_boom() -> None:
    """Raise from a callback that Qt's event loop invokes."""
    raise ValueError("planted: the failure the watcher must see")


def _deliver_language_change(target: QWidget) -> None:
    """Send and post a ``LanguageChange`` to ``target`` and run the event loop."""
    QApplication.sendEvent(target, QEvent(QEvent.Type.LanguageChange))
    QApplication.postEvent(target, QEvent(QEvent.Type.LanguageChange))
    QApplication.processEvents()


def _watch_planted_filter(qapp, target: QWidget) -> _Watch:
    """Plant a raising event filter, deliver the event, return what was seen."""
    planted = _PlantedFilter()
    qapp.installEventFilter(planted)
    try:
        with _watching() as watch:
            watch.run(lambda: _deliver_language_change(target))
    finally:
        qapp.removeEventFilter(planted)
    return watch


def _watch_planted_callback() -> _Watch:
    """Plant a raising callback for Qt's event loop, return what was seen."""
    with _watching() as watch:
        QTimer.singleShot(0, _plant_boom)
        watch.run(QApplication.processEvents)
    return watch


def _watch_planted_unraisable() -> _Watch:
    """Create and drop an object with a raising finaliser, return what was seen."""
    with _watching() as watch:
        planted = _PlantedUnraisable()
        del planted
    return watch


def _watch_quiet_delivery(target: QWidget) -> _Watch:
    """Deliver the same event with nothing planted, return what was seen."""
    with _watching() as watch:
        watch.run(lambda: _deliver_language_change(target))
        watch.run(QApplication.processEvents)
    return watch


@pytest.fixture
def instrument_proven(qapp, qtbot) -> bool:
    """Prove the watcher sees each planted failure and stays silent otherwise.

    Runs before any cycle that depends on it, in the same process, so the
    verdict of a cycle is never read from a watcher that was not shown to work.
    """
    target = QWidget()
    qtbot.addWidget(target)

    filtered = _watch_planted_filter(qapp, target)
    assert "SystemError" in filtered.kinds(), (
        f"the watcher did not see a planted SystemError (saw {filtered.kinds()!r}): "
        "its silence over the cycle would mean nothing"
    )
    callback = _watch_planted_callback()
    assert callback.kinds() == ["ValueError"], (
        f"the watcher did not see a planted callback exception (saw "
        f"{callback.kinds()!r}): its silence over the cycle would mean nothing"
    )
    unraisable = _watch_planted_unraisable()
    assert unraisable.kinds() == ["RuntimeError"], (
        f"the watcher did not see a planted unraisable exception (saw "
        f"{unraisable.kinds()!r}): its silence over the cycle would mean nothing"
    )
    quiet = _watch_quiet_delivery(target)
    assert (
        quiet.problems == []
    ), f"the watcher spoke with nothing planted: {quiet.problems!r}"
    return True


def test_watcher_sees_a_planted_system_error(qapp, qtbot) -> None:
    """A ``SystemError`` raised in an event filter is reported to the caller."""
    target = QWidget()
    qtbot.addWidget(target)
    watch = _watch_planted_filter(qapp, target)
    assert "SystemError" in watch.kinds()
    assert any("planted" in entry for entry in watch.raised)


def test_watcher_sees_a_planted_callback_exception(qapp) -> None:
    """An exception raised in a callback run by Qt's event loop is captured."""
    assert _watch_planted_callback().kinds() == ["ValueError"]


def test_watcher_sees_a_planted_unraisable_exception(qapp) -> None:
    """An exception that escapes a finaliser is captured."""
    assert _watch_planted_unraisable().kinds() == ["RuntimeError"]


def test_watcher_is_silent_when_nothing_is_planted(qapp, qtbot) -> None:
    """The same deliveries with nothing planted report nothing."""
    target = QWidget()
    qtbot.addWidget(target)
    assert _watch_quiet_delivery(target).problems == []


def test_planted_filter_is_removed_after_the_control(qapp, qtbot) -> None:
    """The planted filter does not outlive its control and poison later tests."""
    target = QWidget()
    qtbot.addWidget(target)
    _watch_planted_filter(qapp, target)
    assert _watch_quiet_delivery(target).problems == []


# --------------------------------------------------------------------------- #
# What the user can see, read without touching QAction.menu()                 #
# --------------------------------------------------------------------------- #


def _settle(window: Main_Window) -> None:
    """Deliver the deletions a running event loop would already have delivered.

    The window replaces some widgets (the layer rows) on a language change and
    deletes the old ones with ``deleteLater``. A real application delivers that
    on its next loop turn; ``processEvents`` outside a loop never does, so the
    replaced rows stay behind, hidden, still carrying the previous language, and
    would be read as text the window shows. Only the objects of this window are
    flushed, never the whole application.
    """
    QApplication.processEvents()
    for child in [window, *window.findChildren(QObject)]:
        if shiboken6.isValid(child):
            QApplication.sendPostedEvents(child, QEvent.Type.DeferredDelete)


def _snapshot(window: Main_Window) -> _Snapshot:
    """Return a multiset of the visible texts of ``window``.

    Action texts and tool tips, plus widget tool tips and accessible names and
    descriptions, empty ones left out (an empty string is not text, and counting
    them would count widgets). A multiset, because the order of children is not
    part of what a user sees; read through ``findChildren`` so no menu is ever
    deleted. Call :func:`_settle` first.
    """
    seen: _Snapshot = Counter()
    texts = [
        ("action text", action.text()) for action in window.findChildren(QAction)
    ] + [
        ("action tool tip", action.toolTip()) for action in window.findChildren(QAction)
    ]
    for widget in window.findChildren(QWidget):
        texts.append(("tool tip", widget.toolTip()))
        texts.append(("accessible name", widget.accessibleName()))
        texts.append(("accessible description", widget.accessibleDescription()))
    for kind, text in texts:
        if text:
            seen[(kind, text)] += 1
    return seen


def _differences(before: _Snapshot, after: _Snapshot) -> int:
    """Return how many visible entries differ between two snapshots."""
    return sum(((before - after) + (after - before)).values())


# --------------------------------------------------------------------------- #
# The real selector                                                           #
# --------------------------------------------------------------------------- #


def _selector_entries(window: Main_Window) -> Dict[str, QAction]:
    """Return ``{language code: menu entry}`` for the Language menu, in order."""
    return {
        entry.data(): entry
        for entry in window._language_menu.actions()
        if not entry.isSeparator()
    }


def _select(window: Main_Window, qtbot, code: str, route: str) -> None:
    """Choose ``code`` through the Language menu entry, by ``route``.

    ``action`` activates the entry (what the keyboard and assistive technology
    do); ``menu`` opens the menu and clicks the entry with the mouse.
    """
    entry = _selector_entries(window)[code]
    if route == "action":
        entry.trigger()
        return
    menu = window._language_menu
    menu.popup(window.mapToGlobal(QPoint(8, 8)))
    try:
        qtbot.waitExposed(menu)
        qtbot.mouseClick(
            menu,
            Qt.MouseButton.LeftButton,
            pos=menu.actionGeometry(entry).center(),
        )
    finally:
        menu.hide()


def _cycle(codes: Sequence[str]) -> List[str]:
    """Return the languages to choose, in order, after the window starts in English.

    Every non-English language and then English, repeated :data:`_ROUND_TRIPS`
    times: ``es, en, es, en`` when only Spanish is shipped besides English.
    """
    others = [code for code in codes if code != _SOURCE_LANGUAGE]
    return (others + [_SOURCE_LANGUAGE]) * _ROUND_TRIPS


def test_cycle_is_en_es_en_es_en_for_the_two_shipped_languages() -> None:
    """With only English and Spanish the cycle is exactly en, es, en, es, en."""
    assert [_SOURCE_LANGUAGE] + _cycle(["en", "es"]) == ["en", "es", "en", "es", "en"]


def test_cycle_visits_every_language_and_returns_to_english() -> None:
    """With more languages the cycle visits each and ends on English, twice."""
    steps = _cycle(["en", "es", "fr", "de"])
    assert steps == ["es", "fr", "de", "en"] * _ROUND_TRIPS
    assert steps[-1] == _SOURCE_LANGUAGE


@pytest.mark.parametrize("route", ["action", "menu"])
def test_switching_every_shipped_language_twice_on_one_window_raises_nothing(
    qapp, qtbot, instrument_proven, route
) -> None:
    """SC-L10N-UI-001-2: repeated switching through the real selector raises nothing.

    Starts in English, chooses each other shipped language and then English,
    twice, on one live window. Each step must emit the language change for the
    chosen code, leave that code active, change what the window shows (and show
    exactly what that language showed the first time it was chosen), and let
    nothing escape the watcher. The window ends in English.
    """
    assert instrument_proven
    window = Main_Window()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    manager = window._language_manager
    try:
        shipped = manager.available_languages()
        entries = list(_selector_entries(window))
        # The menu lists the SAME languages the manager reports (set equality,
        # so a dropped or invented language fails) in the user-ruled selector
        # order, not in the manager's alphabetical discovery order (REQ-L10N-UI-003).
        # Order equality is exact, not a subset check.
        assert set(entries) == set(shipped) and len(entries) == len(shipped), (
            f"the Language menu offers {entries!r} but the manager reports "
            f"{shipped!r}: the two do not list the same languages"
        )
        expected_order = [code for code, _ in selector_entries(shipped)]
        assert entries == expected_order, (
            f"the Language menu offers {entries!r} but the selector order for "
            f"{shipped!r} is {expected_order!r}"
        )
        assert len(shipped) >= 2, f"only {shipped!r} is shipped: nothing to switch"
        assert shipped[0] == _SOURCE_LANGUAGE
        assert manager.current_language() == _SOURCE_LANGUAGE

        _settle(window)
        shown: Dict[str, _Snapshot] = {_SOURCE_LANGUAGE: _snapshot(window)}
        steps = _cycle(shipped)
        previous = _SOURCE_LANGUAGE
        with _watching() as watch:
            for number, code in enumerate(steps, start=1):
                where = f"step {number} of {len(steps)} ({previous} -> {code})"
                before = _snapshot(window)

                def _switch() -> Tuple[object, ...]:
                    with qtbot.waitSignal(
                        manager.languageChanged, timeout=2000
                    ) as signalled:
                        _select(window, qtbot, code, route)
                    _settle(window)
                    return tuple(signalled.args)

                heard = watch.run(_switch)
                assert (
                    not watch.problems
                ), f"{where}: an exception escaped the switch:\n" + "\n".join(
                    watch.problems
                )
                assert heard == (code,), f"{where}: signalled {heard!r}"
                assert manager.current_language() == code, where
                after = _snapshot(window)
                assert _differences(before, after) > 0, (
                    f"{where}: the switch changed nothing the user can see, so "
                    "this cycle would pass without switching anything"
                )
                if code in shown:
                    assert after == shown[code], (
                        f"{where}: returning to {code!r} does not show what "
                        f"{code!r} showed the first time "
                        f"({_differences(shown[code], after)} entries differ)"
                    )
                else:
                    shown[code] = after
                previous = code

        assert watch.problems == [], (
            f"{len(watch.problems)} exception(s) escaped during {len(steps)} "
            "switches through the real selector:\n" + "\n".join(watch.problems)
        )
        assert manager.current_language() == _SOURCE_LANGUAGE
        assert shiboken6.isValid(window)
        assert shiboken6.isValid(window._language_menu)
        assert set(shown) == set(shipped), "a shipped language was never shown"
    finally:
        if shiboken6.isValid(manager):
            manager.set_language(_SOURCE_LANGUAGE)
            QApplication.processEvents()


# --------------------------------------------------------------------------- #
# The dock title-bar buttons: Qt's own names and descriptions follow the       #
# language (REQ-L10N-UI-001 accessible names, REQ-L10N-UI-005 Qt's own text)  #
# --------------------------------------------------------------------------- #
#
# A dock's close and float buttons are Qt's. Qt builds their accessible names and
# descriptions from its own catalogue when the dock is made and keeps them across a
# language switch, so a window that does nothing shows a stale language on them.
# The four existing cases above catch it only as a count of differing entries; this
# one reads the texts themselves against the catalogue of the language chosen.

#: Qt's object name of each title-bar button, and the (context, source) pairs of
#: Qt's catalogue that give its accessible name and its accessible description.
_DOCK_BUTTON_TEXTS = {
    "qt_dockwidget_closebutton": (
        ("QDockWidget", "Close"),
        ("QDockWidget", "Closes the dock widget"),
    ),
    "qt_dockwidget_floatbutton": (
        ("QDockWidget", "Float"),
        ("QDockWidget", "Undocks and re-attaches the dock widget"),
    ),
}


def _dock_texts_wanted() -> Dict[str, Tuple[str, str]]:
    """Return what Qt's catalogue gives each button for the language now active.

    Read with the translators the product has installed (the application's and Qt's
    own base catalogue), and never from a dock: a dock's buttons are what is checked.
    English is what Qt returns when no translator knows the pair.
    """
    return {
        name: (
            QCoreApplication.translate(*name_pair),
            QCoreApplication.translate(*description_pair),
        )
        for name, (name_pair, description_pair) in _DOCK_BUTTON_TEXTS.items()
    }


def _dock_button_problems(
    window: Main_Window, wanted: Dict[str, Tuple[str, str]]
) -> Tuple[int, int, List[str]]:
    """Return ``(docks, buttons, problems)`` for every dock the window holds.

    Every ``QDockWidget`` below the window, found by walking; for each, the close and
    float buttons' accessible name and description against ``wanted``. A dock that
    lacks a button is a problem, so a button that is missing cannot pass unseen.
    """
    docks = window.findChildren(QDockWidget)
    problems: List[str] = []
    buttons = 0
    for index, dock in enumerate(docks):
        label = f"dock {index} {dock.windowTitle()!r}"
        found = {
            button.objectName(): button
            for button in dock.findChildren(QAbstractButton)
            if button.objectName() in wanted
        }
        for object_name, (name, description) in wanted.items():
            button = found.get(object_name)
            if button is None:
                problems.append(f"{label}: no {object_name}")
                continue
            buttons += 1
            if button.accessibleName() != name:
                problems.append(
                    f"{label} {object_name} accessible name "
                    f"{button.accessibleName()!r}, wanted {name!r}"
                )
            if button.accessibleDescription() != description:
                problems.append(
                    f"{label} {object_name} accessible description "
                    f"{button.accessibleDescription()!r}, wanted {description!r}"
                )
    return len(docks), buttons, problems


def _walk_dock_buttons(
    window: Main_Window,
    qtbot,
    theme: str,
    sequence: Optional[Sequence[str]] = None,
) -> Tuple[int, int, List[str], List[Tuple[str, List[str]]]]:
    """Switch through every language and back to English; check the docks each step.

    One window, in ``theme`` (read back from the window), through the real selector
    action, in the order of the cycle (every other language in the selector's order,
    then English), or in ``sequence`` when one is given. The window starts in
    English. The texts wanted are those of the language chosen, read from the
    catalogue after the switch; for a language other than English they must differ
    from English, or the check would compare English with English. Returns the docks
    and buttons examined at the last step, the steps taken, and the failures as
    ``(step description, problems)``.
    """
    window.set_mode(theme)
    window.show()
    qtbot.waitExposed(window)
    assert window.current_mode() == theme, "the window is not in the mode under test"
    manager = window._language_manager
    offered = list(_selector_entries(window))
    steps = list(sequence) if sequence else _cycle(offered)[: len(offered)]
    assert set(steps) <= set(offered) and len(steps) >= 2
    assert manager.current_language() == _SOURCE_LANGUAGE
    _settle(window)
    english = _dock_texts_wanted()
    docks, buttons, problems = _dock_button_problems(window, english)
    failures: List[Tuple[str, List[str]]] = []
    if problems:
        failures.append((f"start ({_SOURCE_LANGUAGE})", problems))
    previous = _SOURCE_LANGUAGE
    for number, code in enumerate(steps, start=1):
        where = f"step {number} of {len(steps)} ({previous} -> {code})"
        with qtbot.waitSignal(manager.languageChanged, timeout=2000):
            _select(window, qtbot, code, "action")
        _settle(window)
        assert manager.current_language() == code, where
        wanted = _dock_texts_wanted()
        if code != _SOURCE_LANGUAGE:
            for object_name, texts in wanted.items():
                assert all(
                    got != was for got, was in zip(texts, english[object_name])
                ), f"{where}: Qt's catalogue gives {object_name} the English text"
        docks, buttons, problems = _dock_button_problems(window, wanted)
        if problems:
            failures.append((where, problems))
        previous = code
    return docks, buttons, steps, failures


def _say_ascii(capsys: pytest.CaptureFixture, text: str) -> None:
    """Print ``text`` past the capture, with any non-ASCII character escaped."""
    with capsys.disabled():
        shown = text.encode("ascii", "backslashreplace").decode("ascii")
        print("\n[dock buttons] " + shown, flush=True)


def test_dock_title_bar_buttons_follow_the_language_through_the_selector(
    qapp, qtbot, theme, capsys
) -> None:
    """REQ-L10N-UI-001 / REQ-L10N-UI-005: the dock buttons' names follow the language.

    On one window, through the real selector action, for every shipped language in
    the cycle's order and back to English, in the mode under test: every
    ``QDockWidget``'s close and float buttons' accessible name and description equal
    what Qt's catalogue gives for the language chosen, computed here with the
    product's translators installed. The docks examined are printed, and more than
    none is asserted, so a window with no docks cannot pass.
    """
    window = Main_Window()
    qtbot.addWidget(window)
    manager = window._language_manager
    try:
        docks, buttons, steps, failures = _walk_dock_buttons(window, qtbot, theme)
        _say_ascii(
            capsys,
            f"[{theme}] {docks} docks, {buttons} buttons examined at each of "
            f"{len(steps)} steps ({' -> '.join([_SOURCE_LANGUAGE, *steps])}), "
            f"{len(failures)} failing steps",
        )
        assert docks > 0 and buttons == 2 * docks, (docks, buttons)
        assert not failures, "\n".join(
            f"{where}: {len(problems)} differ, first: {problems[:2]}"
            for where, problems in failures
        )
    finally:
        if shiboken6.isValid(manager):
            manager.set_language(_SOURCE_LANGUAGE)
            QApplication.processEvents()


def test_dock_button_check_fails_when_the_re_set_is_neutralised(
    qapp, qtbot, theme, capsys, monkeypatch
) -> None:
    """Control: with the window's re-set of the dock buttons a no-op, the check fails.

    The slot that names the dock buttons on a language change is replaced by one
    that does nothing before the window is built, which is how the window behaved
    before the fix. Qt itself re-labels the buttons on the way to Japanese and
    Korean (a font re-application makes it rebuild them), and never again, so the
    check has to fail by the step to Russian, and on the way back to English, naming
    dock buttons only. It is run on the cycle's own order and on the order Japanese,
    Korean, Russian, English, in which the stale Korean names show at Russian. The
    failures are printed.
    """
    monkeypatch.setattr(
        Main_Window, "_on_language_dock_buttons", lambda self, _code: None
    )
    window = Main_Window()
    qtbot.addWidget(window)
    manager = window._language_manager
    try:
        docks, buttons, steps, failures = _walk_dock_buttons(window, qtbot, theme)
        failed_at = [where for where, _ in failures]
        first = failures[0][1][:2] if failures else None
        _say_ascii(
            capsys,
            f"[{theme}] control, re-set neutralised: {len(failures)} failing steps "
            f"of {len(steps)}: {failed_at}; first: {first}",
        )
        assert failures, "the check passed with the re-set neutralised: it is blind"
        assert any(f"-> {_SOURCE_LANGUAGE})" in where for where in failed_at), failed_at
        for _, problems in failures:
            assert all("qt_dockwidget_" in problem for problem in problems), problems
        # The order of the field defect: the names follow Japanese and Korean (Qt
        # rebuilds them then) and stay Korean at Russian.
        _, _, steps, failures = _walk_dock_buttons(
            window, qtbot, theme, ["ja", "ko", "ru", _SOURCE_LANGUAGE]
        )
        failed_at = [where for where, _ in failures]
        first = failures[0][1][:2] if failures else None
        _say_ascii(
            capsys,
            f"[{theme}] control, re-set neutralised, {' -> '.join(steps)}: "
            f"failing steps {failed_at}; first: {first}",
        )
        assert any("(ko -> ru)" in where for where in failed_at), failed_at
        for _, problems in failures:
            assert all("qt_dockwidget_" in problem for problem in problems), problems
    finally:
        if shiboken6.isValid(manager):
            manager.set_language(_SOURCE_LANGUAGE)
            QApplication.processEvents()


# --------------------------------------------------------------------------- #
# The slot that names the dock buttons leaves nothing behind                  #
# --------------------------------------------------------------------------- #
#
# On every language change the window builds a throwaway dock to read Qt's own
# texts for the title-bar buttons. A dock made without a parent is a top-level
# window, and a queued deletion is only carried out by a running event loop; a
# test, like the window code under it, runs none. So the dock has to be gone when
# the slot returns, by how it is made and not by anything a caller does later.

#: How many language changes are made in the leak check. One change can move a
#: count once; three or more show a count that keeps growing.
_LEAK_SWITCHES = 4


def _parentless_docks() -> List[QDockWidget]:
    """Return every top-level ``QDockWidget`` that has no parent, alive now."""
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QDockWidget) and widget.parent() is None
    ]


def test_language_changes_leave_no_parentless_dock_behind(qapp, qtbot) -> None:
    """REQ-L10N-UI-001 / REQ-L10N-UI-005: naming the dock buttons leaks no dock.

    On one window, through the real selector action, the language is changed
    several times. The number of parentless top-level docks alive after each change
    equals the number alive before the first, so the slot that names the dock
    buttons leaves no window behind per change. Nothing in this test runs the
    event loop between the changes and the counts: a stray dock is not hidden by
    a flush the product does not make, and the check fails while one is left.
    """
    window = Main_Window()
    qtbot.addWidget(window)
    manager = window._language_manager
    try:
        shipped = list(_selector_entries(window))
        assert len(shipped) >= 2, f"only {shipped!r} is shipped: nothing to switch"
        steps = _cycle(shipped)[:_LEAK_SWITCHES]
        assert len(steps) >= 3, steps
        before = len(_parentless_docks())
        counts: List[int] = []
        for code in steps:
            _select(window, qtbot, code, "action")
            assert manager.current_language() == code, steps
            counts.append(len(_parentless_docks()))
        assert counts == [before] * len(steps), (
            f"{before} parentless top-level docks before, and {counts} after each of "
            f"the language changes {steps}: the slot that names the dock buttons "
            "leaves a window behind per change"
        )
    finally:
        if shiboken6.isValid(manager):
            manager.set_language(_SOURCE_LANGUAGE)
