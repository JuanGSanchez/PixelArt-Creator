"""Nifen Art in the interface: the font each role resolves to (REQ-VI-UI-013..016).

What is covered, by scenario id (the visual-identity feature's scenarios):

* **SC-VI-UI-013-1** menus, the menu bar, dock titles, dock tabs and button labels
  are set in Nifen Art, the dock title in the Bold weight;
* **SC-VI-UI-013-2** the guide's page text starts in the platform font while the
  guide window's topic list and search field are Nifen Art;
* **SC-VI-UI-013-3** the content of docks, panels and dialogs, a tool tip and the
  status bar are Nifen Art by default;
* **SC-VI-UI-014-2** the 14 px line box of a dock title lies inside the plate's band,
  over all six style x mode combinations;
* **SC-VI-UI-015-1** a character Nifen Art lacks falls back alone, with no box;
* **SC-VI-UI-016-1 / -2** "Use system font" returns the whole interface to the
  platform font, wins over the guide's hidden switch and is remembered;
* the smoke line ``interface-font: <family>`` (REQ-VI-BUILD-006);
* the platform's per-class fonts: item views, menus and dock titles keep the
  application font after a style sheet is applied (the cause of the item-view
  colour fringe on native Windows).

The truncation check is ``test_app_font_truncation.py``; the hidden switch is
``test_guide_logo_switch.py``; the guide page text and its headings are in
``test_user_guide.py``.

How the font is asked for, and why "resolved" alone is not enough
-----------------------------------------------------------------
Every role is checked in two ways. ``QFontInfo`` gives the family Qt actually
resolved. The widget's own ``QFont`` gives the family it was *given*. Both must
say Nifen Art. The second one is not redundant: the headless ``offscreen``
platform of a machine that has no system fonts has exactly one font, the
registered one, so *any* request resolves to it and ``QFontInfo`` cannot tell a
widget in the platform font from a widget in Nifen Art. (Measured: on this host
``QFontDatabase.families()`` is empty under ``offscreen`` until Nifen is
registered; with ``QT_QPA_FONTDIR`` pointing at the Windows font folder the same
window resolves its menu bar to another family.) The declared family does not
depend on which fonts exist, so it makes the headless run informative on any
host. The tests that need to *tell the platform font from Nifen Art* by what
Qt resolved (015-1, the restart, the smoke line) run in a child process whose
font database is the platform's: ``QT_QPA_FONTDIR`` on Windows (the folder the
screenshot generator uses), the system fonts elsewhere. A child whose database
turns out empty reports it and the test FAILS: zero fonts cannot show anything.

A fresh process, not a warmed-up one. A window built when the application font is
*already* Nifen Art (because an earlier window in the same process set it) starts
from the right font and hides what the first window of a real launch sees. Every
window here is therefore built from the state a just-started process is in: no
style sheet and the platform's own application font. That is
:func:`start_like_a_new_process`; it is undone after each test.

Isolation. Every test runs under the suite's autouse ``settings_store`` redirect
and asserts it first, so the real store is neither read nor written; the child
processes redirect their own store with the same helper into ``tmp_path``.

Both modes. The window restores the *stored* mode at construction and ignores the
conftest's, so the mode under test is planted in the store and read back from the
window (``open_window`` asserts it): a test that thought it ran Dark and ran Light
would pass for the wrong reason.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtGui import (
    QFont,
    QFontInfo,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QPainter,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QDockWidget,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QMenu,
    QStyleOptionViewItem,
    QTabBar,
    QTableWidget,
    QToolButton,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from pixelart_creator.data import style_catalog
from pixelart_creator.ui import app_font
from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
from pixelart_creator.ui.appearance_settings import (
    KEY_GUIDE_PIXEL_FONT,
    KEY_MODE,
    KEY_STYLE,
    KEY_USE_SYSTEM_FONT,
    SETTINGS_GROUP,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
)
from testing.suites.ui.conftest import assert_settings_isolated
from testing.suites.ui.test_theme import _COMBO_IDS, COMBOS, Combo, _agree, _composed

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The family the bundled faces register under.
NIFEN = app_font.NIFEN_ART_FAMILY

#: The em of the typeface in logical pixels.
EM = app_font.NIFEN_ART_EM_PX

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture with one known starting sheet.

    A ``Main_Window`` restores the stored combination and ignores this one; the
    modes under test are parametrised below (``mode``, ``combo``) and planted in
    the store instead.
    """
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store: Path) -> Path:
    """Fail BEFORE any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)
    return settings_store


@pytest.fixture(autouse=True)
def _leave_the_font_as_found(qapp):
    """Put the interface font back after the test, whatever the test did to it."""
    yield
    # Only the application font is put back. Re-setting the style sheet here (what
    # ``apply_interface_font`` also does) would repolish widgets that are being
    # torn down and crashed Qt natively (measured: an access violation).
    qapp.setFont(app_font._target_font(False))


@pytest.fixture(params=[THEME_LIGHT, THEME_DARK])
def mode(request: pytest.FixtureRequest) -> str:
    """Light, then Dark: the mode planted in the store and read back from the window."""
    chosen: str = request.param
    return chosen


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest) -> Combo:
    """One style x mode combination (six)."""
    chosen: Combo = request.param
    return chosen


# --------------------------------------------------------------------------- #
# Building windows from a just-started process                                 #
# --------------------------------------------------------------------------- #


def start_like_a_new_process(app: QApplication) -> None:
    """Return the application to what a just-started process shows.

    No style sheet, the platform's own application font and the platform's own
    per-class fonts (the snapshot the product took before it changed anything).
    The snapshot is taken here first when nothing has taken it yet.
    """
    app_font.capture_platform_font()
    app.setStyleSheet("")
    app.setFont(app_font.platform_default_font())
    classes = app_font._platform["classes"]
    if isinstance(classes, dict):
        for name, font in classes.items():
            app.setFont(font, name)


def _production_settings() -> QSettings:
    """The four-argument form ``ui/appearance_settings.py`` uses."""
    return QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        ORGANIZATION_NAME,
        APPLICATION_NAME,
    )


def plant(**values: object) -> None:
    """Write ``values`` into the ``appearance`` group of the isolated store."""
    settings = _production_settings()
    settings.beginGroup(SETTINGS_GROUP)
    for key, value in values.items():
        settings.setValue(key, value)
    settings.endGroup()
    settings.sync()


def open_window(
    qtbot,
    mode: str = THEME_LIGHT,
    style: str = DEFAULT_STYLE,
    *,
    use_system_font: bool = False,
    guide_pixel_font: bool = False,
    fresh: bool = True,
    show: bool = True,
    settle: bool = True,
    keep_store: bool = False,
) -> Main_Window:
    """Build a ``Main_Window`` showing ``(style, mode)`` the way a new launch does.

    The mode and the style are planted in the store and read back from the
    window: the window must really show them or the test stops here.

    ``keep_store`` builds the window from whatever the store already holds (a
    restart) instead of planting the arguments first.

    ``settle`` applies the interface font once more after construction. A window
    built from a fresh process keeps the platform font on a platform that gives
    widget classes no fonts of their own (see
    ``test_a_just_launched_window_and_its_children_are_nifen_art``); every test
    that asks a DIFFERENT question (which role resolves to which face, how the
    plate fits) settles first, so one cause does not turn all of them red and
    hide what each of them can say. The first-launch tests pass ``settle=False``.
    """
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    if not keep_store:
        plant(
            **{
                KEY_STYLE: style,
                KEY_MODE: mode,
                KEY_USE_SYSTEM_FONT: use_system_font,
                KEY_GUIDE_PIXEL_FONT: guide_pixel_font,
            }
        )
    if fresh:
        live = [w for w in QApplication.topLevelWidgets() if isinstance(w, Main_Window)]
        # Clearing the style sheet under a live window crashes Qt later (measured:
        # an access violation in the next ``apply_theme``): a second window is
        # built with ``fresh=False``.
        assert not live, "a fresh start was asked for with a live Main_Window"
        start_like_a_new_process(app)
    win = Main_Window()
    qtbot.addWidget(win)
    assert (win.current_style(), win.current_mode()) == (style, mode), (
        "the window shows "
        f"{win.current_style()}/{win.current_mode()}, not {style}/{mode}"
    )
    if settle:
        app_font.apply_interface_font(app, use_system_font)
    if show:
        win.resize(1200, 800)
        win.show()
        qtbot.waitExposed(win)
        QApplication.processEvents()
    return win


def open_guide(win: Main_Window, qtbot, topic: str = "app-basics"):
    """Open the user guide from the window's own entry point on ``topic``."""
    win._on_user_guide()
    dialog = win._user_guide_dialog
    assert dialog is not None
    dialog.resize(900, 700)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.show_topic(topic)
    QApplication.processEvents()
    assert dialog.current_topic_id() == topic
    return dialog


def say(capsys: pytest.CaptureFixture, text: str) -> None:
    """Print a line that reaches the terminal even without ``-s``."""
    with capsys.disabled():
        print(f"\n[font] {text}", flush=True)


# --------------------------------------------------------------------------- #
# What a font is: declared and resolved                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Facts:
    """One widget font, as given and as Qt resolved it."""

    declared: str
    resolved: str
    style: str
    weight: int
    pixel: int
    no_smoothing: bool
    no_hinting: bool

    def describe(self) -> str:
        """Return the facts as one readable string."""
        return (
            f"declared {self.declared!r} resolved {self.resolved!r} "
            f"{self.style} {self.weight} {self.pixel}px "
            f"NoAA={self.no_smoothing} NoHint={self.no_hinting}"
        )


def facts_of(font: QFont) -> Facts:
    """Return the :class:`Facts` of ``font``."""
    info = QFontInfo(font)
    return Facts(
        declared=font.family(),
        resolved=info.family(),
        style=info.styleName(),
        weight=info.weight(),
        pixel=info.pixelSize(),
        no_smoothing=font.styleStrategy() == QFont.StyleStrategy.NoAntialias,
        no_hinting=font.hintingPreference() == QFont.HintingPreference.PreferNoHinting,
    )


def nifen_problems(label: str, font: QFont, *, bold: bool = False) -> List[str]:
    """Return what is wrong with ``font`` for a role that must be Nifen Art.

    Empty when the family was given AND resolved as Nifen Art, at one em, with
    smoothing and hinting off, in the weight the role asks for.
    """
    f = facts_of(font)
    wrong: List[str] = []
    if f.declared != NIFEN:
        wrong.append(f"{label}: given {f.declared!r}, not {NIFEN!r}")
    if f.resolved != NIFEN:
        wrong.append(f"{label}: Qt resolved {f.resolved!r}, not {NIFEN!r}")
    if f.pixel != EM:
        wrong.append(f"{label}: {f.pixel} px, not {EM}")
    if not f.no_smoothing:
        wrong.append(f"{label}: smoothing is not switched off")
    if not f.no_hinting:
        wrong.append(f"{label}: hinting is not switched off")
    want = (700, "Bold") if bold else (400, "Regular")
    if (f.weight, f.style) != want:
        wrong.append(f"{label}: weight/style {(f.weight, f.style)}, wanted {want}")
    return wrong


def assert_roles(capsys, title: str, roles: Sequence[Tuple[str, QFont, bool]]) -> None:
    """Assert every ``(label, font, bold)`` is Nifen Art; print how many were examined.

    Problems are grouped by what is wrong, so one cause is read once, with a count
    and the first few roles it touches.
    """
    assert roles, f"{title}: no role was examined - the test saw nothing"
    groups: Dict[str, List[str]] = {}
    for label, font, bold in roles:
        for problem in nifen_problems(label, font, bold=bold):
            kind = problem.split(": ", 1)[1]
            groups.setdefault(kind, []).append(label)
    say(capsys, f"{title}: {len(roles)} roles examined, {len(groups)} kinds of problem")
    lines = [
        f"{kind}: {len(labels)} roles, first {labels[:4]}"
        for kind, labels in groups.items()
    ]
    assert not groups, f"{title}: {len(roles)} roles examined\n  " + "\n  ".join(lines)


def named(widget: QWidget) -> str:
    """Return a label for ``widget`` that says what it is."""
    text = ""
    for getter in ("text", "windowTitle", "title"):
        fn = getattr(widget, getter, None)
        if callable(fn):
            try:
                text = str(fn())
            except TypeError:
                text = ""
            if text:
                break
    return f"{type(widget).__name__}[{widget.objectName() or text[:24]!r}]"


# --------------------------------------------------------------------------- #
# SC-VI-UI-013-1: menus, titles, dock tabs and buttons                          #
# --------------------------------------------------------------------------- #


def _menu_roles(win: Main_Window) -> List[Tuple[str, QFont, bool]]:
    roles: List[Tuple[str, QFont, bool]] = [("menu bar", win.menuBar().font(), False)]
    for top in win.menuBar().actions():
        menu = top.menu()
        if menu is None:
            continue
        menu.ensurePolished()
        roles.append((f"menu {top.text()!r}", menu.font(), False))
        for action in menu.actions():
            if action.isSeparator() or not action.text():
                continue
            roles.append((f"item {action.text()!r}", action.font(), False))
    return roles


def test_sc_vi_ui_013_1_menus_dock_titles_tabs_and_buttons_are_nifen_art(
    qtbot, capsys, mode
):
    """SC-VI-UI-013-1: menu items, the Layers dock title, dock tabs and buttons.

    First launch, "Use system font" off. The File menu's items and every other
    menu's, the menu bar, the Layers dock title (in the Bold weight), the labels of
    the dock tabs and the button labels all resolve to Nifen Art at one em.
    """
    win = open_window(qtbot, mode)
    roles = _menu_roles(win)
    assert any(label.startswith("item") for label, _f, _b in roles), "no menu item"

    dock = win._layer_dock
    assert dock.isVisible() and not dock.isFloating()
    roles.append(("Layers dock title", dock.font(), True))
    for dock_widget in win.findChildren(QDockWidget):
        roles.append((f"dock {dock_widget.windowTitle()!r}", dock_widget.font(), True))

    tab_bars = [t for t in win.findChildren(QTabBar) if t.count() > 0]
    assert tab_bars, "the window shows no dock tab bar"
    for bar in tab_bars:
        for index in range(bar.count()):
            assert bar.tabText(index), "a dock tab has no label"
        roles.append((f"dock tabs {bar.tabText(0)!r}...", bar.font(), False))

    buttons = [b for b in win.findChildren(QAbstractButton) if b.text()]
    assert buttons, "the window shows no labelled button"
    for button in buttons:
        roles.append((named(button), button.font(), False))

    assert_roles(capsys, f"013-1 [{mode}]", roles)


def test_sc_vi_ui_013_1_the_dock_title_is_bold_and_everything_else_regular(
    qtbot, capsys, mode
):
    """The Bold dock title is accepted by a resolved-font assertion, not by a style rule.

    Dock title: family Nifen Art, style Bold, weight 700, 12 px, no smoothing, no
    hinting adjustments. Body, label, button, line edit and list: Regular, 400. The
    style sheet carries no ``font-family`` and no ``font-size`` (the portability
    constraint), so the weight is the only thing it may say about the font.
    """
    win = open_window(qtbot, mode)
    dock = win._layer_dock
    samples: List[Tuple[str, QFont, bool]] = [("dock title", dock.font(), True)]
    body = dock.widget()
    assert body is not None
    samples.append(("dock body", body.font(), False))
    kinds = (
        (QLabel, "label"),
        (QToolButton, "button"),
        (QLineEdit, "line edit"),
        (QListView, "list"),
        (QTreeWidget, "tree"),
    )
    for cls, name in kinds:
        # The dock's own float/close buttons belong to its (Bold) title bar.
        found = [
            w
            for w in win.findChildren(cls)
            if isinstance(w, cls) and not w.objectName().startswith("qt_dock")
        ]
        assert found, f"the window has no {name} to examine"
        samples.append((name, found[0].font(), False))
    assert_roles(capsys, f"013-1 weights [{mode}]", samples)
    qss = QApplication.instance().styleSheet().lower()
    assert "font-family" not in qss and "font-size" not in qss


def _ink(image: QImage, blank: QImage) -> int:
    """Return how many pixels differ between a titled and an untitled rendering."""
    a = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
        image.height(), image.bytesPerLine()
    )
    b = np.frombuffer(blank.constBits(), dtype=np.uint8).reshape(
        blank.height(), blank.bytesPerLine()
    )
    assert a.shape == b.shape, "the title changed the size of the dock"
    return int(
        (a[:, : image.width() * 4] != b[:, : blank.width() * 4])
        .reshape(image.height(), image.width(), 4)[..., :3]
        .any(axis=2)
        .sum()
    )


def _reference_ink(text: str, weight: QFont.Weight) -> int:
    """Return the ink (lit pixels) of ``text`` drawn in Nifen Art in ``weight``."""
    font = app_font.interface_font()
    font.setWeight(weight)
    metrics = QFontMetrics(font)
    image = QImage(metrics.horizontalAdvance(text) + 8, 20, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(0xFF000000)
    painter.drawText(4, 4 + metrics.ascent(), text)
    painter.end()
    raw = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
        image.height(), image.bytesPerLine()
    )
    px = raw[:, : image.width() * 4].reshape(image.height(), image.width(), 4)[..., :3]
    return int((px != 255).any(axis=2).sum())


def test_sc_vi_ui_013_1_the_dock_title_ink_is_the_bold_face_not_the_regular(
    qtbot, capsys, mode
):
    """Ink check: the rendered title has the Bold reference's pixel count.

    The title text is the pixels that change when the title is removed. The same
    word drawn in Nifen Art Regular and in Bold gives two different counts (the
    control: the references must differ, or the check could not tell the faces
    apart); the dock's own title must match the Bold one and not the Regular one.
    """
    win = open_window(qtbot, mode)
    dock = win._layer_dock
    title = dock.windowTitle()
    assert title
    with_title = dock.grab().toImage()
    dock.setWindowTitle("")
    QApplication.processEvents()
    without = dock.grab().toImage()
    dock.setWindowTitle(title)
    ink = _ink(with_title, without)
    regular = _reference_ink(title, QFont.Weight.Normal)
    bold = _reference_ink(title, QFont.Weight.Bold)
    say(
        capsys,
        f"title {title!r} [{mode}]: dock ink {ink}, Regular ref {regular}, Bold ref {bold}",
    )
    assert regular > 0 and bold > 0, "a reference rendered nothing"
    assert (
        regular != bold
    ), "the references do not differ: the check cannot tell the faces apart"
    assert ink > 0, "the dock title drew no ink"
    assert (
        ink == bold
    ), f"dock title ink {ink} is not the Bold face ({bold}; Regular is {regular})"


# --------------------------------------------------------------------------- #
# SC-VI-UI-013-2: the guide's page starts in the platform font                  #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_013_2_the_guide_page_starts_in_the_platform_font(qtbot, capsys, mode):
    """SC-VI-UI-013-2: page text in the platform font; topic list and search in Nifen Art.

    "Use system font" off, the hidden switch never used. The page's document default
    font is the platform's own default font (given as the platform's family, never
    Nifen Art); the guide window's topic list and search field are Nifen Art.
    """
    win = open_window(qtbot, mode)
    dialog = open_guide(win, qtbot)
    platform = app_font.platform_default_font()
    assert platform.family() != NIFEN, "the platform snapshot is already Nifen Art"
    page = dialog._content_view.document().defaultFont()
    say(
        capsys,
        f"[{mode}] page font {facts_of(page).describe()}; platform {platform.family()!r}",
    )
    assert dialog.page_uses_pixel_font() is False
    assert (
        page.family() == platform.family()
    ), f"the page text is {page.family()!r}, the platform font is {platform.family()!r}"
    assert page.family() != NIFEN
    assert page == platform
    assert_roles(
        capsys,
        f"013-2 guide controls [{mode}]",
        [
            ("topic list", dialog._toc_tree.font(), False),
            ("search field", dialog._search_edit.font(), False),
        ],
    )
    # Control: with the switch on the same reading flips, so it can tell them apart.
    dialog._logo_switch.click()
    QApplication.processEvents()
    assert dialog._content_view.document().defaultFont().family() == NIFEN


# --------------------------------------------------------------------------- #
# SC-VI-UI-013-3: dock, panel and dialog content, tool tip, status bar          #
# --------------------------------------------------------------------------- #


def _tip_label() -> Optional[QWidget]:
    for widget in QApplication.allWidgets():
        if widget.metaObject().className() == "QTipLabel":
            return widget
    return None


def _option_font(view: QAbstractItemView) -> QFont:
    """Return the font the view's delegate would draw a row in."""
    model = view.model()
    assert model is not None and model.rowCount() > 0, "the view has no row"
    option = QStyleOptionViewItem()
    view.itemDelegate().initStyleOption(option, model.index(0, 0))
    return QFont(option.font)


def test_sc_vi_ui_013_3_dock_rows_dialog_tooltip_and_status_bar_are_nifen_art(
    qtbot, capsys, mode
):
    """SC-VI-UI-013-3: layer rows, a dialog's labels and fields, a tool tip, the status bar.

    The scenario names a "New Layer dialog". The product has no such dialog (layers
    are added from the panel), so the nearest "new" dialog stands in for it: the New
    Document dialog. That substitution is stated here and in the report; it is not
    a verification of the dialog as written.
    """
    from pixelart_creator.ui.new_document_dialog import New_Document_Dialog

    win = open_window(qtbot, mode)
    roles: List[Tuple[str, QFont, bool]] = []

    tree = win._layer_panel._tree
    assert tree.topLevelItemCount() > 0, "the Layers dock shows no layer row"
    roles.append(("layer tree", tree.font(), False))
    for row in win._layer_panel._rows:
        roles.append((f"layer row {row._name.text()!r}", row._name.font(), False))
        roles.append(
            (f"layer row {row._name.text()!r} blend box", row._blend.font(), False)
        )
    for view in win._layer_panel.findChildren(QAbstractItemView):
        roles.append((f"layer panel {named(view)}", view.font(), False))
    for widget in win._layer_panel.findChildren(QWidget):
        if isinstance(widget, (QLabel, QAbstractButton, QLineEdit)):
            roles.append((f"layer panel {named(widget)}", widget.font(), False))

    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    inner = [
        w
        for w in dialog.findChildren(QWidget)
        if isinstance(w, (QLabel, QAbstractButton, QLineEdit))
    ]
    assert inner, "the dialog has no label, button or field"
    for widget in inner:
        roles.append((f"dialog {named(widget)}", widget.font(), False))
    roles.append(("dialog", dialog.font(), False))

    QToolTip.showText(QPoint(20, 20), "a tool tip", win)
    QApplication.processEvents()
    tip = _tip_label()
    assert tip is not None, "no tool tip was created"
    roles.append(("tool tip", tip.font(), False))
    QToolTip.hideText()

    win.statusBar().showMessage("status message")
    QApplication.processEvents()
    roles.append(("status bar", win.statusBar().font(), False))
    for label in win.statusBar().findChildren(QLabel):
        roles.append((f"status bar {named(label)}", label.font(), False))

    assert_roles(capsys, f"013-3 [{mode}]", roles)


# --------------------------------------------------------------------------- #
# The platform's per-class fonts (the cause of the item-view colour fringe)     #
# --------------------------------------------------------------------------- #


#: The widget classes whose rows/titles the platform theme may give a font of
#: their own; a fresh instance of each is built and examined.
def _fresh_widgets(_parent: Optional[QWidget] = None) -> List[Tuple[str, QWidget]]:
    """Build one parentless widget of each class (no window font to inherit)."""
    lst = QListWidget()
    lst.addItem("row")
    tree = QTreeWidget()
    tree.setHeaderLabels(["h"])
    tree.addTopLevelItem(QTreeWidgetItem(["row"]))
    table = QTableWidget(1, 1)
    menu = QMenu("m")
    menu.addAction("item")
    menu.ensurePolished()
    dock = QDockWidget("title")
    widgets = [
        ("list", lst),
        ("tree", tree),
        ("table", table),
        ("menu", menu),
        ("dock", dock),
    ]
    for _label, widget in widgets:
        widget.ensurePolished()
    return widgets


def class_font_problems(app: QApplication, parent: QWidget) -> List[str]:
    """Return what is wrong with the per-class fonts and with fresh widgets of those classes."""
    wrong: List[str] = []
    base = app.font()
    for name in app_font._PLATFORM_CLASS_FONTS:
        class_font = app.font(name)  # type: ignore[call-overload]
        if class_font.family() != NIFEN or QFontInfo(class_font).family() != NIFEN:
            wrong.append(f"class {name}: font {class_font.family()!r}, not {NIFEN!r}")
        elif class_font != base:
            wrong.append(f"class {name}: its font differs from the application font")
    for label, widget in _fresh_widgets(parent):
        font = widget.font()
        bold = label == "dock"
        wrong.extend(nifen_problems(f"fresh {label}", font, bold=bold))
        if isinstance(widget, QAbstractItemView) and widget.model().rowCount() > 0:
            wrong.extend(
                nifen_problems(f"fresh {label} row font", _option_font(widget))
            )
    return wrong


def test_item_views_menus_and_dock_titles_keep_nifen_art_after_every_style_sheet(
    qtbot, capsys, combo
):
    """Class-font regression: no per-class font survives a style sheet being applied.

    The platform theme can give item views, menus, the menu bar, the status bar,
    tool tips and dock titles a font of their own, and installing a style sheet
    (or a style) writes those back over the application font. Fresh widgets of
    those classes, and the per-class font table itself, are examined after the
    window is built and after each switch of style and mode.
    """
    win = open_window(qtbot, combo.mode, combo.style, settle=False)
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    examined = len(app_font._PLATFORM_CLASS_FONTS)
    assert examined > 0
    wrong = class_font_problems(app, win)
    for style, mode in ((c.style, c.mode) for c in COMBOS):
        win.set_style(style)
        win.set_mode(mode)
        QApplication.processEvents()
        wrong.extend(
            f"after {style}/{mode}: {p}" for p in class_font_problems(app, win)
        )
    say(
        capsys,
        f"{combo.label()}: {examined} class fonts + 5 fresh widgets per step; {len(wrong)} problems",
    )
    assert not wrong, "\n  ".join(wrong[:25])


def test_the_class_font_regression_check_fires_when_the_platform_fonts_come_back(
    qtbot, capsys
):
    """Control: put per-class fonts back, as the platform does, and the check must fail.

    The font is re-installed for the item views, menus and dock titles exactly as
    ``setStyle`` or a first style sheet would; the very check the regression test
    uses has to flag it, and ``ensure_interface_font`` has to undo it.
    """
    win = open_window(qtbot, THEME_LIGHT)
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    platform = app_font.platform_default_font()
    platform.setPixelSize(15)
    for name in ("QAbstractItemView", "QMenu", "QDockWidgetTitle"):
        app.setFont(platform, name)
    wrong = class_font_problems(app, win)
    say(capsys, f"control: {len(wrong)} problems after the platform fonts came back")
    assert any("class QAbstractItemView" in p for p in wrong)
    assert any("class QMenu" in p for p in wrong)
    assert any("class QDockWidgetTitle" in p for p in wrong)
    app_font.ensure_interface_font(app, False)
    after = [p for p in class_font_problems(app, win) if p.startswith("class ")]
    assert after == [], f"ensure_interface_font left class fonts behind: {after}"


# --------------------------------------------------------------------------- #
# The font of the window right after construction (the first launch)            #
# --------------------------------------------------------------------------- #


def test_a_just_launched_window_and_its_children_are_nifen_art(qtbot, capsys, mode):
    """Every widget of a freshly built window was GIVEN Nifen Art, not just resolved to it.

    The application font is changed while the window is being built. Qt tells
    already-existing top-level windows about an application font change only once
    the event loop runs, so a window that exists before the change keeps the old
    font and its children inherit it. On a platform that gives widget classes no
    fonts of their own there is nothing else to put it right. This test names the
    widgets that were left in the platform font.
    """
    win = open_window(qtbot, mode, settle=False)
    stale = [
        named(w)
        for w in [win, *win.findChildren(QWidget)]
        if not isinstance(w, QMenu) and w.font().family() != NIFEN
    ]
    total = len(win.findChildren(QWidget)) + 1
    say(capsys, f"[{mode}] {total} widgets examined, {len(stale)} not given {NIFEN!r}")
    assert total > 50
    assert not stale, (
        f"{len(stale)} of {total} widgets were not given {NIFEN!r} "
        f"(the application font is {QApplication.font().family()!r}); first: {stale[:8]}"
    )


# --------------------------------------------------------------------------- #
# SC-VI-UI-014-2: a dock title line fits its plate                              #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_014_2_the_dock_title_line_lies_inside_the_plate_band(
    qtbot, capsys, combo
):
    """SC-VI-UI-014-2: the 14 px line box of the title is inside the plate's band.

    Located from pixels. The plate's height is the one for which the composed
    ``dock_title`` template agrees with the dock's own top rows on every column
    away from the text and the buttons (the negative control: one row more or less
    must NOT agree). The line box is placed from the title's ink against the same
    word drawn in a 14 px line box of known position. The band is the template's
    stretching middle, between its top and bottom slices. Six-way.
    """
    win = open_window(qtbot, combo.mode, combo.style)
    dock = win._layer_dock
    assert dock.isVisible() and not dock.isFloating()
    title = dock.windowTitle()
    assert title
    grabbed = dock.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = grabbed.width(), grabbed.height()
    arr = (
        np.frombuffer(grabbed.constBits(), dtype=np.uint8)
        .reshape(height, grabbed.bytesPerLine())[:, : width * 4]
        .reshape(height, width, 4)
        .copy()
    )

    # Columns that hold no title text and no title-bar button: the left slice of the
    # plate and a band across the middle of its width.
    template = style_catalog.template_set(combo.style).get("dock_title")
    wanted = np.zeros(width, dtype=bool)
    wanted[: template.slices.left] = True
    wanted[width // 3 : 2 * width // 3] = True

    def agreement(rows: int, other: Combo = combo) -> float:
        expected = _composed(other, "dock_title", width, rows)
        mask = np.zeros((rows, width), dtype=bool)
        mask[:, wanted] = True
        share, examined = _agree(arr[:rows], expected, mask)
        assert examined > 0
        return share

    body = dock.widget()
    assert body is not None
    plate_rows = body.y()
    scores = {rows: agreement(rows) for rows in range(plate_rows - 2, plate_rows + 3)}
    wrong_style = COMBOS[(COMBOS.index(combo) + 1) % len(COMBOS)]
    control = agreement(plate_rows, wrong_style)
    say(
        capsys,
        f"{combo.label()}: the dock body starts at row {plate_rows}; the composed plate "
        f"agrees {scores[plate_rows]:.3f} (by height "
        f"{{{', '.join(f'{r}: {v:.3f}' for r, v in scores.items())}}}); the plate of "
        f"{wrong_style.label()} agrees {control:.3f}",
    )
    # The plate's height is the layout's: where the dock body starts. Its pixels
    # are the template's (positive control); another combination's plate is not
    # (negative control: the comparison can fail). The agreement by height is
    # printed, not asserted: where the seam row and the title fill share a colour
    # a plate one row taller agrees too, which is a property of the art.
    assert (
        scores[plate_rows] == 1.0
    ), "the composed plate does not agree with the dock's top"
    assert (
        control < 1.0
    ), "the comparison is blind: another combination's plate agrees too"

    band_top, band_bottom = template.slices.top, plate_rows - template.slices.bottom

    with_title = arr
    dock.setWindowTitle("")
    QApplication.processEvents()
    blank_image = dock.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    blank = (
        np.frombuffer(blank_image.constBits(), dtype=np.uint8)
        .reshape(height, blank_image.bytesPerLine())[:, : width * 4]
        .reshape(height, width, 4)
        .copy()
    )
    dock.setWindowTitle(title)
    ink_rows = np.nonzero(
        (with_title[:plate_rows, :, :3] != blank[:plate_rows, :, :3])
        .any(axis=2)
        .any(axis=1)
    )[0]
    assert ink_rows.size > 0, "the title drew no ink"

    font = app_font.interface_font()
    font.setWeight(QFont.Weight.Bold)
    metrics = QFontMetrics(font)
    line_height = metrics.height()
    assert (
        line_height == 14
    ), f"the line box is {line_height} px, not the 14 px of the grid contract"
    ref = QImage(
        metrics.horizontalAdvance(title) + 8, line_height, QImage.Format.Format_RGB32
    )
    ref.fill(0xFFFFFFFF)
    painter = QPainter(ref)
    painter.setFont(font)
    painter.setPen(0xFF000000)
    painter.drawText(4, metrics.ascent(), title)
    painter.end()
    raw = np.frombuffer(ref.constBits(), dtype=np.uint8).reshape(
        ref.height(), ref.bytesPerLine()
    )
    ref_px = raw[:, : ref.width() * 4].reshape(ref.height(), ref.width(), 4)[..., :3]
    ref_rows = np.nonzero((ref_px != 255).any(axis=2).any(axis=1))[0]
    assert ref_rows.size > 0
    assert (
        ink_rows.max() - ink_rows.min() == ref_rows.max() - ref_rows.min()
    ), "the title's ink is not the reference word"
    line_top = int(ink_rows.min() - ref_rows.min())
    line_bottom = line_top + line_height
    say(
        capsys,
        f"{combo.label()}: band rows [{band_top}, {band_bottom}), line box rows [{line_top}, {line_bottom})",
    )
    assert (
        band_top <= line_top
    ), f"the line box starts at row {line_top}, above the band ({band_top})"
    assert (
        line_bottom <= band_bottom
    ), f"the line box ends at row {line_bottom}, below the band ({band_bottom})"


# --------------------------------------------------------------------------- #
# SC-VI-UI-016-1 / -2: "Use system font"                                       #
# --------------------------------------------------------------------------- #


def _every_widget(win: Main_Window) -> List[QWidget]:
    return [win, *win.findChildren(QWidget)]


def test_sc_vi_ui_016_1_use_system_font_returns_the_interface_to_the_platform_font(
    qtbot, capsys, mode
):
    """SC-VI-UI-016-1: with the switch on, the application font is the platform's.

    Turned on at run time and from the stored setting at launch. The application
    font family is the platform font's, not Nifen Art; menus, item views and dock
    titles (the per-class fonts) follow; turning it off brings Nifen Art back.
    """
    win = open_window(qtbot, mode, use_system_font=True)
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    platform = app_font.platform_default_font()
    assert platform.family() != NIFEN
    assert win.use_system_font() is True
    say(
        capsys,
        f"[{mode}] switch on at launch: application font {app.font().family()!r}",
    )
    assert app.font().family() == platform.family() != NIFEN
    for name in app_font._PLATFORM_CLASS_FONTS:
        assert app.font(name).family() != NIFEN, f"class {name} is Nifen Art"  # type: ignore[call-overload]
    assert win.menuBar().font().family() != NIFEN

    win.set_use_system_font(False)
    QApplication.processEvents()
    assert app.font().family() == NIFEN
    assert not class_font_problems(app, win)
    win.set_use_system_font(True)
    QApplication.processEvents()
    assert app.font().family() == platform.family()
    # The platform's per-class fonts are what they were before the product touched anything.
    classes = app_font._platform["classes"]
    assert isinstance(classes, dict)
    for name, font in classes.items():
        assert app.font(name) == font, f"class {name}: not restored"  # type: ignore[call-overload]
    say(capsys, f"[{mode}] {len(classes)} captured per-class fonts compared")


def test_use_system_font_survives_a_style_switch_and_a_mode_switch(qtbot, mode):
    """The platform font stays in force across the style sheet being re-applied."""
    win = open_window(qtbot, mode, use_system_font=True)
    platform = app_font.platform_default_font().family()
    for style in style_catalog.style_ids():
        win.set_style(style)
        win.set_mode(THEME_DARK if mode == THEME_LIGHT else THEME_LIGHT)
        QApplication.processEvents()
        assert QApplication.font().family() == platform, f"after {style}"
        assert win.menuBar().font().family() != NIFEN


def test_sc_vi_ui_016_2_the_system_font_wins_over_the_hidden_switch(
    qtbot, capsys, mode
):
    """SC-VI-UI-016-2 (in one process): switch on, then "Use system font" wins everywhere.

    The hidden switch has put the guide's page in Nifen Art. Checking "Use system
    font" puts all interface text, dock and panel content and the guide's page text
    in the platform font; the switch's own state is kept and the guide returns to
    Nifen Art when "Use system font" is cleared. The restart is the child-process
    test below.
    """
    win = open_window(qtbot, mode, guide_pixel_font=True)
    dialog = open_guide(win, qtbot)
    assert dialog.page_uses_pixel_font() is True
    assert dialog._content_view.document().defaultFont().family() == NIFEN
    win.set_use_system_font(True)
    QApplication.processEvents()
    platform = app_font.platform_default_font().family()
    page = dialog._content_view.document().defaultFont().family()
    say(
        capsys,
        f"[{mode}] system font on: page {page!r}, application {QApplication.font().family()!r}",
    )
    assert dialog.page_uses_pixel_font() is False
    assert dialog.guide_pixel_font() is True, "the switch's own state was lost"
    assert page == platform != NIFEN
    assert QApplication.font().family() == platform
    assert dialog._toc_tree.font().family() != NIFEN
    win.set_use_system_font(False)
    QApplication.processEvents()
    assert dialog.page_uses_pixel_font() is True
    assert dialog._content_view.document().defaultFont().family() == NIFEN


# --------------------------------------------------------------------------- #
# Child processes: a fresh start, with the platform's own fonts                  #
# --------------------------------------------------------------------------- #


def _platform_is_native() -> bool:
    """Whether the running Qt platform plugin is a real display (not headless)."""
    return QGuiApplication.platformName() not in {
        "offscreen",
        "minimal",
        "minimalegl",
        "vnc",
        "webgl",
    }


def platform_font_dir() -> str:
    """Return the platform's font folder to hand ``QT_QPA_FONTDIR``, or ``""``.

    Windows only: the ``offscreen`` plugin finds no system font there unless told
    where they are (the screenshot generator does the same, from ``SystemRoot``).
    macOS and Linux find theirs without help.
    """
    root = os.environ.get("SystemRoot", "")
    return str(Path(root) / "Fonts") if root and os.name == "nt" else ""


def _child_env(
    profile: Path, *, native: bool = False, fonts: bool = True
) -> Dict[str, str]:
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
    )
    if not native:
        env["QT_QPA_PLATFORM"] = "offscreen"
        if fonts and platform_font_dir():
            env["QT_QPA_FONTDIR"] = platform_font_dir()
        else:
            env.pop("QT_QPA_FONTDIR", None)
    return env


_PRELUDE = """
import json, sys
from pathlib import Path
from testing.suites.ui.conftest import redirect_settings_store, assert_settings_isolated
root = Path(sys.argv[1]); redirect_settings_store(root); assert_settings_isolated(root)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontInfo, QFontDatabase
app = QApplication([])
from pixelart_creator.ui import app_font
app_font.capture_platform_font()
def out(**kw):
    print("RESULT " + json.dumps(kw), flush=True)
"""


def run_child(
    script: str,
    tmp_path: Path,
    *,
    native: bool = False,
    fonts: bool = True,
    timeout: int = 100,
) -> Dict[str, Any]:
    """Run ``script`` in a fresh interpreter and return its ``RESULT`` JSON line.

    The child redirects the settings store to ``tmp_path`` and uses temporary
    profile directories, so it can neither read nor write a real user's settings.
    """
    profile = tmp_path / "profile"
    profile.mkdir(exist_ok=True)
    done = subprocess.run(
        [sys.executable, "-B", "-c", _PRELUDE + script, str(tmp_path / "qs-root")],
        cwd=str(_REPO_ROOT),
        env=_child_env(profile, native=native, fonts=fonts),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, f"the child printed no RESULT line:\n{done.stdout}\n{done.stderr}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    return result


def test_sc_vi_ui_015_1_a_missing_character_falls_back_alone_with_no_box(
    tmp_path, capsys
):
    """SC-VI-UI-015-1: "Capa 森" - "Capa " in Nifen Art, the ideograph from a fallback, no box.

    Runs in a child process whose font database is the platform's own. The
    character is chosen at run time from candidates that Nifen Art lacks and that
    some installed font covers (scripts first, then Latin Extended-B, IPA, box
    drawing and math symbols that a stock Linux font has). None found is a FAILURE
    (nothing can be shown) on Windows and macOS; on Linux it is a skip that prints the
    font census, or a failure when PIXELART_REQUIRE_FALLBACK_FONT is set. The
    layer row's own font is shaped with ``QTextLayout`` and each glyph run is
    read: its raw font family and whether it holds glyph 0, the missing-glyph box.
    A control shapes a code point no font has and must be reported as a box.
    """
    result = run_child(
        """
from PySide6.QtCore import Qt
from PySide6.QtGui import QRawFont, QTextLayout, QFont
from pixelart_creator.ui.main_window import Main_Window
w = Main_Window(); w.resize(1100, 700); w.show(); app.processEvents()
app_font.apply_interface_font(app, False)   # settled: the first-launch defect has its own test
doc = w.active_document()
doc.frames[0].layers[0].name = "Capa X"
families = [f for f in QFontDatabase.families() if f != "Nifen Art"]
nifen = QRawFont.fromFont(app_font.interface_font())
# QRawFont.supportsCharacter(<one-character str>) is wrong on Linux. Measured there (offscreen,
# PySide6 6.11.1, DejaVu Sans): it answers True for "A" and False for U+00E9 and U+2500, which
# the font holds, while the integer code point answers True for them and False for U+10FFFD.
# That is what turned "DejaVu Sans covers U+2500" into "no font" in CI (Windows answers the
# str form correctly, so only Linux shows it). Every coverage question below passes ord(ch).
# One face per family, resolved by the database with the family's own first style and
# accepted only if Qt really resolved THAT family: a request the platform answered with a
# different face (an alias such as "Monospace", a missing family) is not a family's coverage.
faces = []
for fam in families:
    styles = QFontDatabase.styles(fam)
    face = QFontDatabase.font(fam, styles[0], 12) if styles else QFont(fam)
    face.setPixelSize(12)
    raw = QRawFont.fromFont(face)
    if raw.isValid() and QFontInfo(face).family() == fam:
        faces.append((fam, raw))
def covers_elsewhere(ch):
    for fam, raw in faces:
        if raw.supportsCharacter(ord(ch)):
            return fam
    return None
# Controls (a probe must show a known-true and a known-false signal before it is believed):
# an ASCII letter must be found in some face, and a code point no font has must not be.
probe_control = {"positive": covers_elsewhere("A"), "negative": covers_elsewhere("\\U0010fffd")}
chosen = None; fallback_family = None; candidates = 0; table = []
# Scripts first (what a user's layer names look like), then characters that a stock Linux
# font (DejaVu, Liberation) covers and Nifen Art lacks in both weights: Latin Extended-B,
# IPA, box drawing, a math sum and root, a shade, a face, a house.
for ch in ["\\u68ee", "\\u6f22", "\\u5b57", "\\u65e5", "\\uc0b0", "\\u0e01", "\\u05d0", "\\u0639", "\\u0915",
           "\\u0192", "\\u0259", "\\u2500", "\\u2211", "\\u221a", "\\u2592", "\\u263a", "\\u2302"]:
    if nifen.supportsCharacter(ord(ch)):
        table.append("U+%04X nifen" % ord(ch))
        continue
    fam = covers_elsewhere(ch)
    table.append("U+%04X %s" % (ord(ch), repr(fam) if fam else "no font"))
    if fam:
        candidates += 1
        if chosen is None:
            chosen, fallback_family = ch, fam
name = "Capa " + (chosen or "?")
doc.frames[0].layers[0].name = name
w._layer_panel.rebuild(); app.processEvents()
label = w._layer_panel._rows[0]._name
row_text = label.text()
def shape(text, font):
    lay = QTextLayout(text, font); lay.beginLayout(); line = lay.createLine(); line.setLineWidth(10000); lay.endLayout()
    runs = []
    for run in lay.glyphRuns():
        raw = run.rawFont()
        runs.append({"family": raw.familyName(), "glyphs": len(run.glyphIndexes()), "notdef": 0 in list(run.glyphIndexes())})
    return runs
runs = shape(row_text, label.font())
control = shape("\\U0010fffd", label.font())
import os
out(families=len(families), faces=len(faces), probe_control=probe_control, chosen=chosen, fallback=fallback_family, candidates=candidates,
    platform=app.platformName(), fontdir=os.environ.get("QT_QPA_FONTDIR", ""), table=table,
    family_names=sorted(families)[:60],
    row_text=row_text, runs=runs, control=control, row_font=label.font().family(),
    nifen_runs=[r for r in runs if r["family"] == "Nifen Art"])
""",
        tmp_path,
    )
    say(
        capsys,
        f"015-1: fonts in the child's database {result['families']}, candidates "
        f"{result['candidates']}, chose {result['chosen']!r} (covered by {result['fallback']!r}); "
        f"runs {result['runs']}; control {result['control']}",
    )
    # What the database holds, so the log of a failing or skipped run shows why.
    census = (
        f"Qt platform {result['platform']!r}, QT_QPA_FONTDIR {result['fontdir']!r}, "
        f"{result['families']} families besides Nifen Art "
        f"({result['faces']} resolved to their own face; probe controls {result['probe_control']}) "
        f"(first {len(result['family_names'])}): {result['family_names']}; "
        f"candidates: {result['table']}"
    )
    say(capsys, f"015-1 census: {census}")
    assert result["families"] > 0, (
        "the child's font database holds no font besides Nifen Art; " + census
    )
    # The coverage probe must see before it may say "no font": a letter every font holds is
    # found, and a code point no font holds is not. Otherwise "no candidate" below would be
    # the probe's blindness and not the environment's font database.
    assert result["probe_control"]["positive"], (
        "the coverage probe is blind: no installed face reports the letter A; " + census
    )
    assert result["probe_control"]["negative"] is None, (
        "the coverage probe is credulous: a face reports U+10FFFD; " + census
    )
    if result["candidates"] == 0:
        # Nothing can be shown, so the scenario cannot be proved here. On Windows and
        # macOS that is a failure (both ship fonts for the candidates). A bare Linux
        # image may ship none: there it is a counted skip that names its reason, unless
        # PIXELART_REQUIRE_FALLBACK_FONT is set (CI sets it once its job installs a font
        # such as fonts-dejavu-core), which turns the skip into the failure it hides.
        why = (
            "SC-VI-UI-015-1 NOT PROVED: no candidate character is covered by any font "
            "besides Nifen Art in this environment's font database; " + census
        )
        if sys.platform.startswith("linux") and not os.environ.get(
            "PIXELART_REQUIRE_FALLBACK_FONT"
        ):
            pytest.skip(why)
        pytest.fail(why)
    assert result["row_text"].startswith("Capa ") and result["row_text"] != "Capa ?"
    assert result["row_font"] == NIFEN, f"the layer row font is {result['row_font']!r}"
    runs = result["runs"]
    assert len(runs) >= 2, f"the row was not split into runs: {runs}"
    # Qt lists a layout's glyph runs by font, not in text order: what matters is
    # how many glyphs each face drew. "Capa " is five glyphs in Nifen Art, the
    # ideograph one glyph from a fallback.
    prefix = len("Capa ")
    in_nifen = sum(r["glyphs"] for r in runs if r["family"] == NIFEN)
    elsewhere = sum(r["glyphs"] for r in runs if r["family"] != NIFEN)
    assert in_nifen == prefix, f"{in_nifen} glyphs in Nifen Art, not {prefix}: {runs}"
    assert (
        elsewhere == len(result["row_text"]) - prefix == 1
    ), f"the ideograph was not drawn by a fallback font alone: {runs}"
    assert not any(r["notdef"] for r in runs), f"a missing-glyph box appears: {runs}"
    assert any(
        r["notdef"] for r in result["control"]
    ), "the box detector is blind: its control was not a box"


def test_sc_vi_ui_016_2_and_017_3_the_choices_survive_a_real_restart(tmp_path, capsys):
    """SC-VI-UI-016-2 / 017-3 across real interpreter boundaries (four processes).

    P1 turns the hidden switch on. P2 (a restart) opens the guide: the page is still
    in Nifen Art; then it checks "Use system font". P3 (a restart) shows the whole
    interface and the guide page in the platform font and "Use system font" still
    checked; it clears the switch. P4 shows Nifen Art again with the hidden switch
    still remembered. Each child redirects the settings store to ``tmp_path``.
    """
    open_guide_js = """
w._on_user_guide(); d = w._user_guide_dialog; d.resize(900, 700); d.show(); app.processEvents()
d.show_topic("app-basics"); app.processEvents()
"""
    head = """
from pixelart_creator.ui.main_window import Main_Window
w = Main_Window(); w.resize(1100, 700); w.show(); app.processEvents()
"""
    state = """
page = d._content_view.document().defaultFont()
out(app=app.font().family(), menu=QFontInfo(w.menuBar().font()).family(),
    page=page.family(), page_resolved=QFontInfo(page).family(),
    page_pixel=d.page_uses_pixel_font(), switch=d.guide_pixel_font(),
    toc=QFontInfo(d._toc_tree.font()).family(), system=w.use_system_font(),
    action=w._use_system_font_action.isChecked(), platform=app_font.platform_default_font().family(),
    platform_resolved=QFontInfo(app_font.platform_default_font()).family(),
    families=len(QFontDatabase.families()))
"""
    p1 = run_child(
        head + open_guide_js + "d._logo_switch.click(); app.processEvents()\n" + state,
        tmp_path,
    )
    assert p1["page_pixel"] is True and p1["switch"] is True
    p2 = run_child(
        head
        + open_guide_js
        + state.replace("out(", "first = dict(")
        + "\nw.set_use_system_font(True); app.processEvents()\nout(first=first, system_after=w.use_system_font())\n",
        tmp_path,
    )
    first = p2["first"]
    say(capsys, f"P2 (restart after the switch): {first}")
    assert (
        first["switch"] is True and first["page_pixel"] is True
    ), "017-3: the switch was not remembered"
    assert first["page"] == NIFEN and first["page_resolved"] == NIFEN
    assert p2["system_after"] is True
    p3 = run_child(head + open_guide_js + state, tmp_path)
    say(capsys, f"P3 (restart after 'Use system font'): {p3}")
    assert (
        p3["families"] > 1
    ), "the child's font database holds no font besides Nifen Art"
    assert p3["platform"] != NIFEN and p3["platform_resolved"] != NIFEN
    assert (
        p3["system"] is True and p3["action"] is True
    ), "'Use system font' was not remembered"
    assert p3["switch"] is True, "the hidden switch's state was lost"
    assert p3["page_pixel"] is False
    assert (
        p3["page"] == p3["platform"] and p3["page_resolved"] == p3["platform_resolved"]
    )
    assert p3["app"] == p3["platform"]
    assert (
        p3["menu"] == p3["platform_resolved"] != NIFEN
    ), "the menu bar is not in the platform font"
    assert p3["toc"] == p3["platform_resolved"] != NIFEN
    p4 = run_child(
        head
        + open_guide_js
        + "w.set_use_system_font(False); app.processEvents()\n"
        + state,
        tmp_path,
    )
    assert p4["system"] is False and p4["page_pixel"] is True and p4["switch"] is True
    assert p4["page"] == NIFEN and p4["app"] == NIFEN


def test_smoke_mode_prints_the_interface_font_nifen_art(tmp_path, capsys):
    """REQ-VI-BUILD-006: the smoke launch prints ``interface-font: Nifen Art``.

    The product is launched as the installer smoke check launches it
    (``PIXELART_SMOKE_EXIT_MS``), in a child process whose font database is the
    platform's own. The control counts the fonts that child can see: with none, the
    family it prints could only ever be the registered one and the line would prove
    nothing, so the test fails.
    """
    profile = tmp_path / "profile"
    profile.mkdir()
    native = _platform_is_native()
    env = _child_env(profile, native=native)
    env["PIXELART_SMOKE_EXIT_MS"] = "400"
    probe = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "from PySide6.QtWidgets import QApplication;"
            "from PySide6.QtGui import QFontDatabase;"
            "a = QApplication([]); print('FAMILIES', len(QFontDatabase.families()))",
        ],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    families = int(probe.stdout.split("FAMILIES")[-1].strip())
    # The launcher's own entry point (what ``python -m pixelart_creator`` calls),
    # with the settings store redirected so a real user's choices are not read.
    launch = (
        "import sys; from pathlib import Path;"
        "from testing.suites.ui.conftest import redirect_settings_store;"
        "redirect_settings_store(Path(sys.argv[1]));"
        "from pixelart_creator.ui.app import main; raise SystemExit(main([]))"
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", launch, str(tmp_path / "qs-root")],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=100,
    )
    say(
        capsys,
        f"smoke: {families} platform fonts visible; stdout {done.stdout.strip()!r}",
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
    assert (
        families > 0
    ), "the child sees no platform font: the smoke line could not fail"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("interface-font:")]
    assert lines == ["interface-font: Nifen Art"], f"smoke output: {done.stdout!r}"


def test_the_platform_font_directory_is_one_the_child_can_use():
    """The helper that finds the platform's fonts returns an existing folder or nothing."""
    folder = platform_font_dir()
    assert folder == "" or Path(folder).is_dir()
    if os.name == "nt":
        assert folder, "SystemRoot is not set: the child would see no system font"


# --------------------------------------------------------------------------- #
# The combo box's point-sized font (the "Point size <= 0" warning, OF7 ruling)   #
# --------------------------------------------------------------------------- #

_COMBO_FONT_CHILD = """
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontInfo
from pixelart_creator.ui.theme import DEFAULT_STYLE, THEME_LIGHT, apply_theme
style = @STYLE@
app_font._platform["style"] = style      # what capture_platform_font read at launch
def state():
    f = QApplication.font("QComboBox")
    return dict(
        point=f.pointSizeF(), px_resolved=QFontInfo(f).pixelSize(),
        family=f.family(), app_family=QApplication.font().family(),
        platform_family=app_font.platform_default_font().family(),
        platform_point=app_font.platform_default_font().pointSizeF(),
        platform_px=app_font.platform_default_font().pixelSize(),
    )
app_font.prepare_interface_font(app, False)
nifen = state()
apply_theme(app, THEME_LIGHT, DEFAULT_STYLE)
after_sheet = state()
app_font.ensure_interface_font(app, False)
ensured = state()
app_font.apply_interface_font(app, True)
system = state()
out(style=style, nifen=nifen, after_sheet=after_sheet, ensured=ensured, system=system)
"""


def test_the_combo_box_gets_a_point_sized_interface_font(tmp_path: Path):
    """On the ``windows11`` style a combo box gets Nifen Art in POINTS, same pixels.

    Qt's ``windows11`` style reads ``widget.font().pointSize()`` for a combo box,
    which is ``-1`` for a pixel-sized font and made Qt print ``QFont::setPointSize:
    Point size <= 0 (-1)``. This is the unit-level half of that fix, and it runs
    on every platform because it forces the style name the product captured
    (``app_font._platform["style"]``) in a child process; whether Qt itself still
    prints the warning is ``test_point_size_warning.py`` (native Windows only).

    Checked: a positive point size that resolves to the interface font's own pixel
    size (12 px), the same family, kept after a style sheet and
    :func:`ensure_interface_font`, and equal to the platform font for "Use system
    font". The control: on any other style (``fusion``) the class font is left
    alone (still pixel-sized), so the entry is not set where it is not needed.
    """
    fixed = run_child(_COMBO_FONT_CHILD.replace("@STYLE@", repr("windows11")), tmp_path)
    nifen, ensured, system = fixed["nifen"], fixed["ensured"], fixed["system"]
    assert nifen["point"] > 0, nifen
    assert nifen["px_resolved"] == EM, nifen
    assert nifen["family"] == NIFEN == nifen["app_family"], nifen
    assert ensured["point"] > 0 and ensured["px_resolved"] == EM, fixed
    assert ensured["family"] == NIFEN, ensured
    assert system["family"] == system["platform_family"], system
    assert system["point"] == system["platform_point"], system
    other = run_child(_COMBO_FONT_CHILD.replace("@STYLE@", repr("fusion")), tmp_path)
    assert other["nifen"]["point"] <= 0, other["nifen"]
    assert other["nifen"]["px_resolved"] == EM, other["nifen"]
    assert other["nifen"]["family"] == NIFEN, other["nifen"]
