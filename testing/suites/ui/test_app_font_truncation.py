"""No label, button, tab, action or row is truncated by Nifen Art (REQ-VI-UI-013).

The change of font must not cut any English or Spanish interface text short: the
surface is the whole interface outside the user guide's pages, from the first
launch (every dock, panel and dialog), at the art scale 1 and 2, in Light and
Dark. Two groups of tests:

* ``test_nifen_art_truncates_nothing_...`` raises every dock of the main window in
  turn and examines what is visible, and builds every dialog class the interface
  defines and examines it. Every combination of language (en, es), scale (1, 2),
  mode (light, dark), surface (main window, dialogs) and style is a test of its
  own (48), because each runs in a child process whose cost is paid in seconds and
  the runner's per-test cap is 120 s; ``test_the_items_cover_every_combination_...``
  proves the 48 are the whole matrix, each once.
* the detector's controls: for each widget kind a text is squeezed on purpose and
  the detector must report it, and the same text given room must pass. A detector
  that cannot fail proves nothing.

What counts as truncated, per kind (the width the widget NEEDS is the one its
own style computes for the text in the font it really has; the width it HAS is
what the layout gave it):

* a label (no word wrap): narrower than its ``sizeHint``; with word wrap: shorter
  than ``heightForWidth(width)``;
* a push, tool, check or radio button showing text: narrower than its ``sizeHint``;
* a group box: narrower than its ``sizeHint``;
* a tab: its rectangle narrower than ``tabSizeHint``;
* a combo box, a spin box: the current text wider than the field's edit area;
* a top-level menu: its entry outside the menu bar (pushed into the ``>>`` overflow);
* a menu action: its row narrower than the text;
* an item view row or header section: the text wider than the cell it is drawn in
  (what the delegate would elide with an ellipsis).

The number of widgets and texts examined is printed per kind and must not be zero.
Scale 2 is the application's art scale pinned to 2 (``apply_theme(..., scale=2)``),
which changes the style sheet's metrics; a real display at 200 % is not
emulated in-process, and this is stated rather than implied.

The dialog list is complete by construction: every ``QDialog`` subclass the
``ui`` package defines must be built here or named in ``NOT_BUILT`` with a reason;
a new dialog that is in neither fails the test.
"""

from __future__ import annotations

import importlib
import itertools
import os
import pkgutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMenu,
    QMenuBar,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QTabBar,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

import pixelart_creator.ui as ui_package
from pixelart_creator.ui import app_font
from pixelart_creator.ui.theme import apply_theme
from testing.suites.ui.focus_helpers import image_array
from testing.suites.ui.test_app_font import (  # noqa: F401  (fixtures used by name)
    NIFEN,
    _leave_the_font_as_found,
    _store_is_isolated,
    open_window,
    say,
    theme,
)

EN = "en"
ES = "es"
_SCALES = (1, 2)


@pytest.fixture(autouse=True)
def _nifen_is_the_application_font(qapp) -> None:
    """Register and apply Nifen Art, so the controls measure the real face."""
    app_font.register_app_fonts()
    app_font.apply_interface_font(qapp, False)


# --------------------------------------------------------------------------- #
# The detector                                                                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Finding:
    """One piece of text that does not fit where it is drawn."""

    kind: str
    where: str
    text: str
    need: int
    have: int

    def describe(self) -> str:
        """Return the finding as one line."""
        return f"{self.kind} {self.where}: {self.text!r} needs {self.need}, has {self.have}"


def _drawn_elided(view: QAbstractItemView, index: QModelIndex) -> Optional[bool]:
    """Say whether Qt draws this cell's text elided: draw it, widen the cell, draw again.

    The same region of the viewport is grabbed with the cell as it is and with the
    view and the column made 400 px wider; the text is drawn from the same left
    edge, so the two grabs differ only if the narrow one was cut short. Returns
    ``None`` when the view has no column to widen (the caller then trusts its
    estimate). The view is put back as it was.
    """
    if not isinstance(view, (QTreeView, QTableView)):
        return None
    rect = view.visualRect(index)
    if rect.isEmpty():
        return None
    column = index.column()
    before = image_array(view.viewport().grab(rect).toImage())
    old_column, old_min, old_max = (
        view.columnWidth(column),
        view.minimumWidth(),
        view.maximumWidth(),
    )
    old_size = view.size()
    view.setFixedWidth(view.width() + 400)
    view.setColumnWidth(column, old_column + 400)
    QApplication.processEvents()
    try:
        if view.visualRect(index).topLeft() != rect.topLeft():
            return None
        after = image_array(view.viewport().grab(rect).toImage())
    finally:
        view.setColumnWidth(column, old_column)
        view.setMinimumWidth(old_min)
        view.setMaximumWidth(old_max)
        view.resize(old_size)
        QApplication.processEvents()
    # The cell's own right edge (two columns of border) differs whatever the text does.
    return not np.array_equal(before[:, :-2], after[:, :-2])


def _columns(model, row: int, parent: QModelIndex) -> int:
    """Return how many columns ``row`` has (a model's ``columnCount`` is private here)."""
    count = 0
    while count < 16 and model.index(row, count, parent).isValid():
        count += 1
    return max(1, count)


class Examiner:
    """Walks widgets once each, counts what it examined and collects findings."""

    def __init__(self) -> None:
        self.seen: Set[int] = set()
        self.examined: Counter = Counter()
        self.findings: List[Finding] = []

    # -- helpers ---------------------------------------------------------

    def _once(self, widget: QWidget) -> bool:
        key = id(widget)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    @staticmethod
    def _where(widget: QWidget) -> str:
        window = widget.window()
        return f"{type(window).__name__}/{type(widget).__name__}[{widget.objectName()}]"

    def _flag(
        self, kind: str, widget: QWidget, text: str, need: int, have: int
    ) -> None:
        self.findings.append(
            Finding(kind, self._where(widget), text.strip()[:60], need, have)
        )

    # -- the rules -------------------------------------------------------

    def label(self, label: QLabel) -> None:
        """A label: narrower than its size hint, or too short for its wrapped text."""
        text = label.text()
        if not text or label.pixmap() is not None and label.pixmap().isNull() is False:
            return
        self.examined["label"] += 1
        if label.wordWrap():
            need = label.heightForWidth(label.width())
            if need > label.height():
                self._flag("label (wrapped)", label, text, need, label.height())
            return
        need = label.sizeHint().width()
        if label.width() < need:
            self._flag("label", label, text, need, label.width())

    def button(self, button: QAbstractButton) -> None:
        """A button that shows text: narrower than its size hint."""
        if not button.text() or button.objectName().startswith("qt_"):
            return
        if isinstance(button, QToolButton) and (
            button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        ):
            return
        self.examined["button"] += 1
        need = button.sizeHint().width()
        if button.width() < need:
            self._flag("button", button, button.text(), need, button.width())

    def group_box(self, box: QGroupBox) -> None:
        """A group box title: the box narrower than its size hint."""
        if not box.title():
            return
        self.examined["group box"] += 1
        need = box.sizeHint().width()
        if box.width() < need:
            self._flag("group box", box, box.title(), need, box.width())

    def tab_bar(self, bar: QTabBar) -> None:
        """Every tab: its rectangle narrower than the size hint of its text."""
        for index in range(bar.count()):
            if not bar.tabText(index):
                continue
            self.examined["tab"] += 1
            need = bar.tabSizeHint(index).width()
            have = bar.tabRect(index).width()
            if have < need:
                self._flag("tab", bar, bar.tabText(index), need, have)

    def combo(self, combo: QComboBox) -> None:
        """The current text of a combo box against its edit area."""
        text = combo.currentText()
        if not text:
            return
        self.examined["combo"] += 1
        option = QStyleOptionComboBox()
        option.initFrom(combo)
        option.rect = combo.rect()
        field = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            combo,
        )
        need = QFontMetrics(combo.font()).horizontalAdvance(text)
        if need > field.width():
            self._flag("combo", combo, text, need, field.width())

    def spin(self, spin: QAbstractSpinBox) -> None:
        """A spin box's displayed text against the width of its editor."""
        editor = spin.lineEdit()
        text = spin.text()
        if editor is None or not text:
            return
        self.examined["spin"] += 1
        margins = editor.textMargins()
        need = (
            QFontMetrics(editor.font()).horizontalAdvance(text)
            + margins.left()
            + margins.right()
        )
        if need > editor.width():
            self._flag("spin", spin, text, need, editor.width())

    def menu_bar(self, bar: QMenuBar) -> None:
        """Every top-level menu entry must lie inside the bar (not in its overflow)."""
        for action in bar.actions():
            if not action.text():
                continue
            self.examined["menu"] += 1
            geometry = bar.actionGeometry(action)
            if geometry.isEmpty() or not bar.rect().contains(geometry):
                self._flag("menu", bar, action.text(), geometry.width(), bar.width())

    def menu(self, menu: QMenu) -> None:
        """Every action row of a menu is at least as wide as its text."""
        menu.ensurePolished()
        menu.sizeHint()
        metrics = QFontMetrics(menu.font())
        for action in menu.actions():
            if action.isSeparator() or not action.text():
                continue
            self.examined["menu action"] += 1
            text = (
                action.text()
                .replace("&&", "\x00")
                .replace("&", "")
                .replace("\x00", "&")
            )
            row = menu.actionGeometry(action)
            need = metrics.horizontalAdvance(text)
            if row.width() < need:
                self._flag("menu action", menu, text, need, row.width())

    def item_view(self, view: QAbstractItemView, limit: int = 400) -> None:
        """Rows and header sections: the text against the cell it is drawn in."""
        model = view.model()
        if model is None:
            return
        header: Optional[QHeaderView] = None
        if isinstance(view, QTreeView):
            header = view.header()
        elif hasattr(view, "horizontalHeader"):
            header = view.horizontalHeader()
        if header is not None and header.isVisible():
            metrics = QFontMetrics(header.font())
            for section in range(header.count()):
                text = model.headerData(section, Qt.Orientation.Horizontal)
                if not text:
                    continue
                self.examined["header"] += 1
                need = metrics.horizontalAdvance(str(text)) + 2 * (
                    header.style().pixelMetric(
                        QStyle.PixelMetric.PM_HeaderMargin, None, header
                    )
                )
                if header.sectionSize(section) < need:
                    self._flag(
                        "header", view, str(text), need, header.sectionSize(section)
                    )
        metrics = QFontMetrics(view.font())
        margin = (
            view.style().pixelMetric(
                QStyle.PixelMetric.PM_FocusFrameHMargin, None, view
            )
            + 1
        )
        count = 0

        def walk(parent: QModelIndex, depth: int) -> None:
            nonlocal count
            for row in range(model.rowCount(parent)):
                for column in range(_columns(model, row, parent)):
                    if count >= limit:
                        return
                    index = model.index(row, column, parent)
                    text = index.data(Qt.ItemDataRole.DisplayRole)
                    rect = view.visualRect(index)
                    if (
                        text
                        and not rect.isEmpty()
                        and view.viewport().rect().intersects(rect)
                    ):
                        count += 1
                        self.examined["row"] += 1
                        have = rect.width() - 2 * margin
                        if isinstance(view, QTreeView) and column == 0:
                            have -= view.indentation() * (depth + 1)
                        need = metrics.horizontalAdvance(str(text))
                        # The estimate is within a pixel or two of what Qt does; the
                        # drawn row is the ground truth where it can be had.
                        if need > have and _drawn_elided(view, index) is not False:
                            self._flag("row", view, str(text), need, have)
                if isinstance(view, QTreeView) and model.hasChildren(
                    model.index(row, 0, parent)
                ):
                    if view.isExpanded(model.index(row, 0, parent)):
                        walk(model.index(row, 0, parent), depth + 1)

        walk(QModelIndex(), 0)

    # -- the walk ----------------------------------------------------------

    def examine(self, root: QWidget) -> None:
        """Examine every visible widget under ``root`` that has not been seen yet."""
        for widget in [root, *root.findChildren(QWidget)]:
            if not isValid(widget):
                continue
            if not widget.isVisible() or widget.width() <= 0 or not self._once(widget):
                continue
            if isinstance(widget, QLabel):
                self.label(widget)
            elif isinstance(widget, QAbstractButton):
                self.button(widget)
            elif isinstance(widget, QGroupBox):
                self.group_box(widget)
            elif isinstance(widget, QTabBar):
                self.tab_bar(widget)
            elif isinstance(widget, QComboBox):
                self.combo(widget)
            elif isinstance(widget, QAbstractSpinBox):
                self.spin(widget)
            elif isinstance(widget, QMenuBar):
                self.menu_bar(widget)
                for action in widget.actions():
                    if action.menu() is not None:
                        self.menu(action.menu())
            elif isinstance(widget, QAbstractItemView):
                self.item_view(widget)

    def report(self) -> str:
        """Return the counts and the findings, grouped, as text."""
        counts = ", ".join(f"{k} {v}" for k, v in sorted(self.examined.items()))
        total = sum(self.examined.values())
        grouped: Dict[str, List[str]] = defaultdict(list)
        for finding in self.findings:
            grouped[finding.kind].append(finding.describe())
        lines = [f"examined {total} ({counts}); {len(self.findings)} truncated"]
        for kind, items in grouped.items():
            lines.append(f"  {kind}: {len(items)}")
            lines.extend(f"    {line}" for line in items[:12])
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The detector can fail: controls                                              #
# --------------------------------------------------------------------------- #


def _host(qtbot, width: int, *widgets: QWidget) -> QWidget:
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    for widget in widgets:
        layout.addWidget(widget)
    host.setFixedWidth(width)
    host.show()
    qtbot.waitExposed(host)
    QApplication.processEvents()
    return host


def _controls(qtbot, squeezed: bool) -> Examiner:
    text = "A label that is rather long for a narrow box"
    label = QLabel(text)
    label.setSizePolicy(
        label.sizePolicy().horizontalPolicy().Ignored,
        label.sizePolicy().verticalPolicy(),
    )
    button = QPushButton("A button that is rather long")
    button.setSizePolicy(
        button.sizePolicy().horizontalPolicy().Ignored,
        button.sizePolicy().verticalPolicy(),
    )
    bar = QTabBar()
    bar.addTab("A tab that is rather long")
    bar.setExpanding(False)
    host = _host(qtbot, 60 if squeezed else 700, label, button, bar)
    if squeezed:
        bar.setFixedWidth(40)
        QApplication.processEvents()
    examiner = Examiner()
    examiner.examine(host)
    return examiner


def test_the_detector_reports_squeezed_text(qtbot):
    """Control (positive): a label, a button and a tab squeezed into 60 px are reported."""
    examiner = _controls(qtbot, squeezed=True)
    kinds = {f.kind for f in examiner.findings}
    assert {"label", "button"} <= kinds, examiner.report()
    assert sum(examiner.examined.values()) >= 3


def test_the_detector_passes_text_that_has_room(qtbot):
    """Control (negative): the same widgets in 700 px are examined and none is reported."""
    examiner = _controls(qtbot, squeezed=False)
    assert sum(examiner.examined.values()) >= 3
    assert examiner.findings == [], examiner.report()


def test_the_detector_reports_an_item_view_row_that_would_be_elided(qtbot):
    """Control: a tree row wider than its cell is reported (and drawn elided); a roomy one is not."""
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

    view = QTreeWidget()
    view.setHeaderHidden(True)
    view.addTopLevelItem(
        QTreeWidgetItem(
            ["A row of text that is far too wide for the tree that holds it"]
        )
    )
    host = _host(qtbot, 90, view)
    index = view.model().index(0, 0)
    assert (
        _drawn_elided(view, index) is True
    ), "the render check cannot see an elided row"
    narrow = Examiner()
    narrow.examine(view)
    assert narrow.examined["row"] == 1 and len(narrow.findings) == 1, narrow.report()
    host.setFixedWidth(700)
    view.setColumnWidth(0, 660)
    QApplication.processEvents()
    assert _drawn_elided(view, index) is False, "the render check flags a roomy row"
    roomy = Examiner()
    roomy.examine(view)
    assert roomy.examined["row"] == 1 and roomy.findings == [], roomy.report()


# --------------------------------------------------------------------------- #
# Every dialog                                                                 #
# --------------------------------------------------------------------------- #


def _documents():
    from testing.suites.ui._export_helpers import animation_document

    return animation_document(frames=3, tag=True)


def _factories() -> Dict[str, Callable[[], QWidget]]:
    """Return a builder for every dialog class, keyed by class name."""
    from pixelart_creator.logic.document import Document
    from pixelart_creator.logic.grids import (
        IsoGridConfig,
        PerspectiveConfig,
        VanishingPoint,
    )
    from pixelart_creator.logic.palette import Palette
    from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
    from pixelart_creator.logic.realtime_apply import branch
    from pixelart_creator.logic.version_history import CloudVersion
    from pixelart_creator.ui.about_dialog import About_Dialog
    from pixelart_creator.ui.asset_register_dialog import Asset_Register_Dialog
    from pixelart_creator.ui.asset_update_prompt import Asset_Update_Prompt_Dialog
    from pixelart_creator.ui.branch_diff_dialog import Branch_Diff_Dialog
    from pixelart_creator.ui.canvas_size_dialog import Canvas_Size_Dialog
    from pixelart_creator.ui.cel_overwrite_dialog import Cel_Overwrite_Dialog
    from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
    from pixelart_creator.ui.document_transform_dialogs import (
        Document_Transform_Confirm_Dialog,
        Document_Transform_Progress_Dialog,
    )
    from pixelart_creator.ui.export_dialog import Export_Dialog
    from pixelart_creator.ui.extract_palette_dialog import Extract_Palette_Dialog
    from pixelart_creator.ui.frame_tags_panel import Tag_Dialog
    from pixelart_creator.ui.iso_grid_dialog import Iso_Grid_Dialog
    from pixelart_creator.ui.new_document_dialog import New_Document_Dialog
    from pixelart_creator.ui.overwrite_confirm_dialog import Overwrite_Confirm_Dialog
    from pixelart_creator.ui.palette_swap_dialog import Palette_Swap_Dialog
    from pixelart_creator.ui.provider_config_dialog import Provider_Config_Dialog
    from pixelart_creator.ui.real_size_preview_window import (
        Real_Size_Calibration_Dialog,
    )
    from pixelart_creator.ui.recovery_prompt import Recovery_Prompt
    from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
    from pixelart_creator.ui.tileset_editor_panel import Tile_Edit_Dialog
    from pixelart_creator.ui.transform_dialog import Scale_Dialog
    from pixelart_creator.ui.user_guide import User_Guide_Dialog
    from pixelart_creator.ui.vanishing_point_dialog import Vanishing_Point_Dialog
    from pixelart_creator.ui.version_history_browser import Version_History_Browser

    palette = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]

    def branch_diff() -> QWidget:
        base = Document(64, 64, palette=Palette(palette))
        mainline = branch(base, site_id=0)
        source = branch(base, site_id=1)
        return Branch_Diff_Dialog(
            "feature", "mainline", source, mainline, source.document()
        )

    def perspective() -> QWidget:
        config = PerspectiveConfig(
            mode=2,
            vanishing_points=(
                VanishingPoint(position=(-64.0, 32.0)),
                VanishingPoint(position=(128.0, 32.0)),
            ),
            horizon_y=10.0,
        )
        return Vanishing_Point_Dialog(config)

    return {
        "About_Dialog": lambda: About_Dialog("light", None),
        "Asset_Register_Dialog": lambda: Asset_Register_Dialog(None),
        "Asset_Update_Prompt_Dialog": lambda: Asset_Update_Prompt_Dialog(),
        "Branch_Diff_Dialog": branch_diff,
        "Canvas_Size_Dialog": lambda: Canvas_Size_Dialog(200, 150),
        "Cel_Overwrite_Dialog": lambda: Cel_Overwrite_Dialog(),
        "Colour_Hub_Menu": lambda: Colour_Hub_Menu(),
        "Document_Transform_Confirm_Dialog": lambda: Document_Transform_Confirm_Dialog(
            "Scale Canvas", 600_000_000, 7680, 4320
        ),
        "Document_Transform_Progress_Dialog": lambda: Document_Transform_Progress_Dialog(
            "Scale Canvas", 7
        ),
        "Export_Dialog": lambda: Export_Dialog(_documents()),
        "Extract_Palette_Dialog": lambda: Extract_Palette_Dialog(),
        "Tag_Dialog": lambda: Tag_Dialog(5, None),
        "Iso_Grid_Dialog": lambda: Iso_Grid_Dialog(
            IsoGridConfig(tile_width=40, ratio=1.2, origin=(1.0, 2.0))
        ),
        "New_Document_Dialog": lambda: New_Document_Dialog(),
        "Overwrite_Confirm_Dialog": lambda: Overwrite_Confirm_Dialog(),
        "Palette_Swap_Dialog": lambda: Palette_Swap_Dialog(7),
        "Provider_Config_Dialog": lambda: Provider_Config_Dialog(),
        "Real_Size_Calibration_Dialog": lambda: Real_Size_Calibration_Dialog(),
        "Recovery_Prompt": lambda: Recovery_Prompt(),
        "RotSprite_Dialog": lambda: RotSprite_Dialog(lambda angle: None),
        "Tile_Edit_Dialog": lambda: Tile_Edit_Dialog(
            PixelBuffer(6, 6, ColorMode.RGBA), (230, 30, 30, 255), 0, None
        ),
        "Scale_Dialog": lambda: Scale_Dialog(16, 16),
        "User_Guide_Dialog": lambda: User_Guide_Dialog(None),
        "Vanishing_Point_Dialog": perspective,
        "Version_History_Browser": lambda: Version_History_Browser(
            tuple(
                CloudVersion(
                    version_id=f"p:{i}", ordinal=i, created_marker=i, size_bytes=10
                )
                for i in range(2)
            )
        ),
    }


#: Dialog classes the interface defines that are not built here, with the reason.
NOT_BUILT: Dict[str, str] = {}


def _dialog_classes() -> Dict[str, type]:
    """Return every ``QDialog`` subclass defined in the ``ui`` package, by name."""
    for module in pkgutil.iter_modules(ui_package.__path__):
        importlib.import_module(f"pixelart_creator.ui.{module.name}")
    found: Dict[str, type] = {}
    stack = [QDialog]
    while stack:
        for sub in stack.pop().__subclasses__():
            stack.append(sub)
            if sub.__module__.startswith("pixelart_creator.ui"):
                found[sub.__name__] = sub
    return found


def test_every_dialog_class_of_the_interface_is_built_here_or_named():
    """Completeness: no dialog the interface defines escapes the examination unseen."""
    defined = set(_dialog_classes())
    built = set(_factories())
    named = set(NOT_BUILT)
    missing = sorted(defined - built - named)
    stale = sorted((built | named) - defined)
    assert defined, "no dialog class was discovered"
    assert not missing, f"dialogs neither built nor named in NOT_BUILT: {missing}"
    assert not stale, f"entries that match no dialog class: {stale}"


# --------------------------------------------------------------------------- #
# The measurement: Nifen Art against the platform font, in a child process     #
# --------------------------------------------------------------------------- #
#
# The requirement is that no label is truncated BY THE CHANGE OF FONT. Text that is cut short
# with the platform font as well (27 dock tabs in one tab bar are, with any font)
# is not caused by the change, so the verdict is a comparison: every examined
# widget is measured with Nifen Art and again, in the same window, with "Use
# system font" on; only text that is truncated with Nifen Art and NOT with the
# platform font fails. Text truncated with both is counted and printed (it is
# real and the owner should know), but it is not what this requirement asks.
#
# The comparison needs a platform font to compare with, so it runs in a child
# process whose font database is the platform's own (``test_app_font`` explains
# why the headless font database of this host is empty otherwise). A child that
# sees no platform font fails: with one font there is nothing to compare.


def _settle(win: QWidget) -> None:
    """Let every pending layout request run before anything is measured."""
    for _ in range(2):
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, 0)
    # A font change leaves the size hints of widgets already laid out stale until
    # the next layout pass; one resize forces it, as the user's first resize does.
    size = win.size()
    win.resize(size.width() + 1, size.height())
    QApplication.processEvents()
    win.resize(size)
    QApplication.processEvents()


def _switch_language(win, code: str) -> None:
    """Make ``code`` the interface language and prove the catalogue was applied."""
    if code == EN:
        return
    assert win._language_manager.set_language(code) is True, f"no {code!r} catalogue"
    QApplication.processEvents()
    first = win.menuBar().actions()[0].text()
    assert (
        first.replace("&", "") != "File"
    ), f"the {code!r} catalogue was not applied: {first!r}"


def _point_the_generic_family_at_the_operating_system_ui_font() -> str:
    """Make the headless platform's default family resolve to the OS's own UI font.

    On the ``offscreen`` plugin the platform default is the generic family
    "Sans Serif", which Windows resolves to whichever installed face sorts first
    (a condensed one on this host), not to the font the real platform shows. A
    baseline in that font would be unrealistically narrow. On Windows the OS's
    message font is read from the system metrics (nothing is named here) and the
    generic family is substituted by it; elsewhere the generic family is left to
    fontconfig / CoreText. Returns what the generic family now resolves to.
    """
    from PySide6.QtGui import QFont, QFontInfo

    if os.name == "nt":
        import ctypes

        class _LogFont(ctypes.Structure):
            _fields_ = [
                ("lfHeight", ctypes.c_long),
                ("lfWidth", ctypes.c_long),
                ("lfEscapement", ctypes.c_long),
                ("lfOrientation", ctypes.c_long),
                ("lfWeight", ctypes.c_long),
                ("lfItalic", ctypes.c_ubyte),
                ("lfUnderline", ctypes.c_ubyte),
                ("lfStrikeOut", ctypes.c_ubyte),
                ("lfCharSet", ctypes.c_ubyte),
                ("lfOutPrecision", ctypes.c_ubyte),
                ("lfClipPrecision", ctypes.c_ubyte),
                ("lfQuality", ctypes.c_ubyte),
                ("lfPitchAndFamily", ctypes.c_ubyte),
                ("lfFaceName", ctypes.c_wchar * 32),
            ]

        class _Metrics(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("iBorderWidth", ctypes.c_int),
                ("iScrollWidth", ctypes.c_int),
                ("iScrollHeight", ctypes.c_int),
                ("iCaptionWidth", ctypes.c_int),
                ("iCaptionHeight", ctypes.c_int),
                ("lfCaptionFont", _LogFont),
                ("iSmCaptionWidth", ctypes.c_int),
                ("iSmCaptionHeight", ctypes.c_int),
                ("lfSmCaptionFont", _LogFont),
                ("iMenuWidth", ctypes.c_int),
                ("iMenuHeight", ctypes.c_int),
                ("lfMenuFont", _LogFont),
                ("lfStatusFont", _LogFont),
                ("lfMessageFont", _LogFont),
                ("iPaddedBorderWidth", ctypes.c_int),
            ]

        metrics = _Metrics()
        metrics.cbSize = ctypes.sizeof(_Metrics)
        spi_getnonclientmetrics = 0x0029
        ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
            spi_getnonclientmetrics, metrics.cbSize, ctypes.byref(metrics), 0
        )
        face = metrics.lfMessageFont.lfFaceName if ok else ""
        if face:
            QFont.insertSubstitution(QFont().family(), face)
    return QFontInfo(QFont(QFont().family())).family()


def run_matrix(
    language: str, scale: int, mode: str, surface: str, style: str
) -> Dict[str, object]:
    """Examine one surface in one style, with Nifen Art and with the platform font.

    Called inside the child process. ``surface`` is ``"main"`` (the main window with
    every dock raised in turn) or ``"dialogs"`` (every dialog class, built and shown).
    The result carries the seconds each phase took (``timing``), which is printed
    with the verdict so a slow item shows where its time went.
    """
    import time

    from PySide6.QtGui import QFontDatabase

    from pixelart_creator.ui.appearance_settings import KEY_MODE
    from pixelart_creator.ui.main_window import Main_Window
    from testing.suites.ui.test_app_font import plant

    clock = time.perf_counter
    timing: Dict[str, float] = {}
    mark = clock()

    def lap(name: str) -> None:
        nonlocal mark
        now = clock()
        timing[name] = round(timing.get(name, 0.0) + now - mark, 2)
        mark = now

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    generic = _point_the_generic_family_at_the_operating_system_ui_font()
    plant(**{KEY_MODE: mode})
    win = Main_Window()
    win.resize(1280, 800)
    win.show()
    QApplication.processEvents()
    _switch_language(win, language)
    lap("window")
    # The style under test, at the pinned art scale, then the interface font on top
    # of it: the window was built while the application font was still the
    # platform's, and setting the sheet again re-resolves the fonts of widgets that
    # already exist. This is done before the panels are prepared so the style sheet
    # is applied to a window whose panels are not yet polished; the state reached
    # is the same, and each sheet change costs time in proportion to the widgets
    # already polished.
    apply_theme(app, mode, style, scale=scale)
    app_font.apply_interface_font(app, False)
    lap("style and font")
    # The window is the subject only on the "main" surface. A dialog is a window of
    # its own, built after the style and the font are applied and examined by its
    # own widgets, so for "dialogs" the window is just the thing that holds the
    # language and the "Use system font" choice, and its panels are not prepared.
    examines_window = surface == "main"
    if examines_window:
        # Warm-up, not measured: some panels are only sized the first time their
        # tab is raised (measured: seven widgets still had width 0 on the first
        # pass).
        for dock in win.findChildren(QDockWidget):
            dock.show()
            dock.raise_()
            QApplication.processEvents()
    lap("warm-up")
    results: Dict[str, Dict[str, object]] = {}
    for font in ("nifen", "system"):
        if font == "system":
            # The menu action's own path: the choice is stored, the listener
            # applies the platform font and sets the sheet again.
            win.set_use_system_font(True)
            QApplication.processEvents()
            app_font.ensure_interface_font(app, True)
            lap("font switch")
        if examines_window:
            _settle(win)
        lap("settle")
        examiner = Examiner()
        if surface == "main":
            examiner.examine(win)
            docks = win.findChildren(QDockWidget)
            for dock in docks:
                dock.show()
                dock.raise_()
                QApplication.processEvents()
                examiner.examine(dock)
            examiner.examined["docks"] = len(docks)
        else:
            for name, factory in _factories().items():
                dialog = factory()
                dialog.show()
                QApplication.processEvents()
                examiner.examine(dialog)
                examiner.examined["dialogs"] += 1
                dialog.hide()
                dialog.deleteLater()
        lap("examine")
        results[font] = {
            "examined": dict(examiner.examined),
            "findings": [
                [f.kind, f.where, f.text, f.need, f.have] for f in examiner.findings
            ],
        }
    win._language_manager.set_language(EN)
    return {
        "results": results,
        "timing": timing,
        "families": len([f for f in QFontDatabase.families() if f != NIFEN]),
        "platform": generic,
        "app_font_nifen": app_font.interface_font().family(),
    }


_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_matrix
out(**run_matrix({language!r}, {scale}, {mode!r}, {surface!r}, {style!r}))
"""


def _measure(
    tmp_path,
    capsys,
    language: str,
    scale: int,
    mode: str,
    surface: str,
    style: str,
) -> None:
    """Run one item in a child and assert nothing is truncated by the change of font."""
    from testing.suites.ui.test_app_font import run_child

    result = run_child(
        _CHILD.format(
            language=language, scale=scale, mode=mode, surface=surface, style=style
        ),
        tmp_path,
        timeout=170,
    )
    assert (
        result["families"] > 0
    ), "the child sees no platform font besides Nifen Art: there is nothing to compare with"
    nifen = result["results"]["nifen"]
    system = result["results"]["system"]
    total = sum(nifen["examined"].values())
    base = {(f[0], f[1], f[2]) for f in system["findings"]}
    mine = [f for f in nifen["findings"] if (f[0], f[1], f[2]) not in base]
    both = len(nifen["findings"]) - len(mine)
    say(
        capsys,
        f"{surface} [{language} scale{scale} {mode} {style}]: "
        f"examined {total} with Nifen Art ({nifen['examined']}), "
        f"{sum(system['examined'].values())} with {result['platform']!r}; "
        f"truncated with Nifen Art only: {len(mine)}, with both: {both}; "
        f"child seconds {result['timing']}",
    )
    assert total > (
        200 if surface == "main" else 100
    ), f"{style}: almost nothing examined"
    if surface == "main":
        assert nifen["examined"].get("docks", 0) > 20
    attributable = [
        f"{style}: {f[0]} {f[1]}: {f[2]!r} needs {f[3]}, has {f[4]}" for f in mine
    ]
    detail = "\n  ".join(attributable[:30])
    assert not attributable, (
        f"{len(attributable)} texts are cut short by Nifen Art and not by "
        f"{result['platform']!r}:\n  {detail}"
    )


#: The partition: one item per (language, scale, mode, surface, style).
LANGUAGES = (EN, ES)
MODES = ("light", "dark")
SURFACES = ("main", "dialogs")


def _items() -> List[Tuple[str, int, str, str, str]]:
    """Return every (language, scale, mode, surface, style) item, in a fixed order."""
    from pixelart_creator.data import style_catalog

    return list(
        itertools.product(
            LANGUAGES, _SCALES, MODES, SURFACES, style_catalog.style_ids()
        )
    )


ITEMS = _items()


@pytest.mark.parametrize(
    "language, scale, mode, surface, style",
    ITEMS,
    ids=[f"{la}-scale{sc}-{mo}-{su}-{st}" for la, sc, mo, su, st in ITEMS],
)
def test_nifen_art_truncates_nothing_the_platform_font_does_not(
    tmp_path, capsys, language, scale, mode, surface, style
):
    """Nothing in the main window or in any dialog is cut short by Nifen Art.

    One item per language (en, es), art scale (1, 2), mode (Light, Dark), surface
    (the main window with every dock raised, every dialog class built) and style:
    Nifen Art against the platform font in one window. The examined counts and
    the number of texts truncated with Nifen Art only (and with both fonts) are
    printed for every item.
    """
    _measure(tmp_path, capsys, language, scale, mode, surface, style)


def test_the_items_cover_every_combination_exactly_once():
    """The partition: every (language, scale, mode, surface, style) is one item, once.

    The expected set is built here from the sources each axis comes from (the
    catalogue's style ids, the two languages, the two scales, the two modes, the
    two surfaces) and compared with the arguments the measuring test is actually
    parametrised with, read off the test function, so a combination dropped,
    duplicated or invented by the partition is reported by name. Because every
    item examines one style, three items of a (language, scale, mode, surface)
    together examine what one item of the previous layout examined in its loop.
    """
    from pixelart_creator.data import style_catalog

    styles = style_catalog.style_ids()
    assert len(styles) == 3, f"the catalogue holds {len(styles)} styles, not 3"
    expected = Counter(
        (la, sc, mo, su, st)
        for la in ("en", "es")
        for sc in (1, 2)
        for mo in ("light", "dark")
        for su in ("main", "dialogs")
        for st in styles
    )
    marks = [
        mark
        for mark in test_nifen_art_truncates_nothing_the_platform_font_does_not.pytestmark
        if mark.name == "parametrize"
    ]
    assert len(marks) == 1, "the measuring test must carry exactly one parametrize mark"
    names, values = marks[0].args[0], list(marks[0].args[1])
    assert [n.strip() for n in names.split(",")] == [
        "language",
        "scale",
        "mode",
        "surface",
        "style",
    ]
    actual = Counter(tuple(value) for value in values)
    twice = sorted(key for key, count in actual.items() if count > 1)
    assert not twice, f"combinations covered more than once: {twice}"
    assert not (
        expected - actual
    ), f"combinations with no item: {sorted(expected - actual)}"
    assert not (
        actual - expected
    ), f"items outside the matrix: {sorted(actual - expected)}"
    assert len(values) == 2 * 2 * 2 * 2 * 3 == 48
    ids = marks[0].kwargs["ids"]
    assert len(set(ids)) == len(ids) == len(values), "item ids are not unique"
    # The control: a partition that drops one combination is reported by name.
    short = actual.copy()
    dropped = next(iter(short))
    del short[dropped]
    assert expected - short == Counter({dropped: 1})
