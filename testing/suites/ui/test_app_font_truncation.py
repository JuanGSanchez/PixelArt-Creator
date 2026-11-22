"""No label, button, tab, action or row is cut short (REQ-VI-UI-013, REQ-L10N-UI-013).

The change of font must not cut any interface text short, and no translation may
cut off a label that English shows in full. The surface is the whole interface
outside the user guide's pages, from the first launch (every dock, panel and
dialog), at the art scale 1 and 2, in Light and Dark, in every compiled language.

Two criteria judge each item, side by side. A label fails if either makes it a
finding:

* **Nifen Art against the platform font** (``REQ-VI-UI-013``, unchanged). Every
  examined widget is measured with Nifen Art and again, in the same window, with
  "Use system font" on; only text truncated with Nifen Art and not with the
  platform font fails.
* **A language against English** (``REQ-L10N-UI-013``, the differential rule). For
  each compiled language L other than English, each label is measured in L and in
  English under the same font case, scale, mode, style and surface. It is a finding
  when it is truncated or elided in L and the same label is not truncated or elided
  in English. A label truncated in English as well is not a finding: it is counted
  and printed per language, with its widget, never hidden. English is the
  reference, not a language under test.

"The same label" is matched by the widget's language-independent identity and
never by its text: the key of a measured piece of text is its kind, the surface it
lives on and the widget's object path (class, object name and position among its
same-class siblings, from the window down), plus the index of a tab, a menu row, a
header section or an item-view cell. No key holds any text. A key examined in L and
not in English cannot be judged; each is counted and printed, and the item fails
rather than compare by position.

The groups of tests:

* ``test_nifen_art_truncates_nothing_...`` is one item per (language, scale, mode,
  surface, style). Each item runs in a child process whose cost is paid in seconds
  and the runner's per-test cap is 120 s. An item of a language other than English
  also needs the English child of the same (scale, mode, surface, style) as its
  reference: the first worker to need it measures it and publishes it in a folder
  the session's workers share, so it is measured once per session where they share
  and at most once per worker where they do not.
  ``test_the_items_cover_every_combination_...`` proves the items are the whole
  matrix, each once, for the compiled languages discovered at run time.
* ``test_a_label_truncated_in_...`` are the two planted cases of
  SC-L10N-UI-013-2, each built inside the test with a translation planted in a
  scratch catalogue compiled for the purpose, and a broken copy of the comparison
  (one that drops the English side) that must fail the second.
* the vertical check: with "Use system font" on and a Han-capable platform family
  forced (a registered stand-in), each label class is also measured for height: the
  height of its text in the platform font must not exceed the height its widget
  gives it. If the application has not yet put a family list on the platform font,
  the list the plan prescribes for a Han-capable platform family (the CJK families
  first) is built with the application's own ``family_chain`` and ``chain_font`` and
  applied app-wide, and every line says ``modelled``; when the application does it
  itself the line says ``product``. The height a text needs is the line box of the
  family that really draws each DISPLAYED character (rich-text markup removed), read
  one character at a time in the widget's own font: a text with a Latin letter, a
  digit or a space is judged at the platform font's height, a text drawn wholly by a
  CJK face at that face's own, shorter, height. A planted widget one pixel too short
  fails, for a Latin label and for a label drawn wholly by a CJK face.
* the user guide's page: with the same platform family, one rendered topic per
  language is laid out and no line is shorter than the tallest glyph drawn on it.
* the detector's controls: for each widget kind a text is squeezed on purpose and
  the detector must report it, and the same text given room must pass. A detector
  that cannot fail proves nothing.

What counts as truncated, per kind (the width the widget NEEDS is the one its
own style computes for the text in the font it really has; the width it HAS is
what the layout gave it):

* a label (no word wrap): narrower than its ``sizeHint``; with word wrap: shorter
  than ``heightForWidth(width)``;
* a push, tool, check or radio button showing text: narrower than its ``sizeHint``;
* a group box: its title reaching past the box's edge (the title's own rectangle,
  as the box's style computes it; never the box's contents, which a ``sizeHint``
  would include);
* a tab: its rectangle narrower than ``tabSizeHint``;
* a dock title: the title wider than the text rectangle the style gives the title
  bar (what Qt elides with an ellipsis);
* a combo box, a spin box: the current text wider than the field's edit area;
* a top-level menu: its entry outside the menu bar (pushed into the ``>>`` overflow);
* a menu action, in a menu or in any submenu: its row narrower than the text;
* an item view row or header section: the text wider than the cell it is drawn in
  (what the delegate would elide with an ellipsis).

The number of widgets and texts examined is printed per kind and must not be zero.
Art scale 1 is 100 %. Art scale 2 is the pixel-perfect scale (the whole-number
scale "Pixel-perfect interface" produces above 100 %), pinned with
``apply_theme(..., scale=2)``, which changes the style sheet's metrics; a real
display at 200 % is not emulated in-process, and this is stated rather than
implied.

The dialog list is complete by construction: every ``QDialog`` subclass the
``ui`` package defines must be built here or named in ``NOT_BUILT`` with a reason;
a new dialog that is in neither fails the test.

Every family a verdict depends on is registered by the test and the run is
offscreen. The user-visible code points are probed as integers. Which family drew a
character is read one character at a time, never from the position of a glyph run
in a multi-run layout, whose order differs between processes on identical input.
Run with ``-rP`` to read what every item printed, including each label that is
truncated in English as well.
"""

from __future__ import annotations

import importlib
import itertools
import json
import os
import pkgutil
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    cast,
)

import numpy as np
import pytest
import shiboken6
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from PySide6 import QtGui
from PySide6.QtCore import (
    QByteArray,
    QCoreApplication,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextLayout,
    QUndoCommand,
)
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
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionDockWidget,
    QStyleOptionGroupBox,
    QTabBar,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

import pixelart_creator.logic.font_chain as font_chain
import pixelart_creator.ui as ui_package
from pixelart_creator.ui import app_font
from pixelart_creator.ui.theme import DEFAULT_STYLE, apply_theme
from testing.suites.ui.focus_helpers import image_array
from testing.suites.ui.test_app_font import (  # noqa: F401  (fixtures used by name)
    NIFEN,
    _leave_the_font_as_found,
    _store_is_isolated,
    open_window,
    say,
    theme,
)
from testing.suites.ui.test_font_family_chain_mechanism import (
    _ADVANCE,
    _BITS_CJK,
    _BITS_LATIN,
    _CODEPAGE_CJK,
    _CODEPAGE_LATIN,
    _PX,
    _UPEM,
    FACES,
    N_TILDE,
    _range_words,
    build_face,
)

EN = "en"
_SCALES = (1, 2)

#: The two font cases of one item: the application's own font and "Use system font".
FONT_CASES = ("nifen", "system")


def _report(capsys, text: str) -> None:
    """Print ``text`` on the terminal and into the test's captured output.

    ``say`` reaches the terminal of a serial run; a pytest-xdist worker's direct
    output is lost, so the same line is also printed into the captured output that
    ``-rP`` shows.
    """
    say(capsys, text)
    print(text)


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
    """One piece of text that does not fit where it is drawn.

    ``key`` is the language-independent identity of the widget (and cell) the text
    is drawn in; it holds no text.
    """

    kind: str
    where: str
    text: str
    need: int
    have: int
    key: str = ""

    def describe(self) -> str:
        """Return the finding as one line."""
        return (
            f"{self.kind} {self.where}: {self.text!r} "
            f"needs {self.need}, has {self.have}"
        )


_VERTICAL_SHAPES = (
    QTabBar.Shape.RoundedWest,
    QTabBar.Shape.RoundedEast,
    QTabBar.Shape.TriangularWest,
    QTabBar.Shape.TriangularEast,
)


def _drawn_elided(view: QAbstractItemView, index: QModelIndex) -> Optional[bool]:
    """Say whether Qt draws this cell's text elided: draw it, widen the cell, draw
    again.

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
    """Return how many columns ``row`` has (a model's ``columnCount`` is private
    here).
    """
    count = 0
    while count < 16 and model.index(row, count, parent).isValid():
        count += 1
    return max(1, count)


def displayed_text(widget: QWidget, text: str) -> str:
    """Return the text ``widget`` DISPLAYS for ``text``, rich-text markup removed.

    A label whose text is rich (its format says so, or ``Auto`` and the text looks
    like it) shows the text of the document, not the tags and attribute values
    around it: ``<a href="https://example.org">저장소</a>`` displays ``저장소``. Any
    other widget shows its text as it is.
    """
    if isinstance(widget, QLabel):
        format_ = widget.textFormat()
        rich = format_ == Qt.TextFormat.RichText or (
            format_ == Qt.TextFormat.AutoText and QtGui.Qt.mightBeRichText(text)
        )
        if rich:
            document = QTextDocument()
            document.setHtml(text)
            return document.toPlainText().replace(" ", "\n").replace(" ", "\n")
    return text


class Examiner:
    """Walks widgets once each, counts what it examined and collects findings.

    ``prefix`` names the surface a widget belongs to (the main window, or the
    dialog being examined); it is part of every key, so two dialogs that build
    the same widgets do not collide. When ``vfont`` is set the walk also takes the
    vertical measure of each text: the height of the text in that font against the
    height its widget gives it.
    """

    def __init__(self, vfont: Optional[QFont] = None) -> None:
        self.seen: Set[int] = set()
        self.examined: Counter = Counter()
        self.findings: List[Finding] = []
        self.keys: Dict[str, List[str]] = defaultdict(list)
        self.prefix = ""
        self.vfont = vfont
        self.vexamined: Counter = Counter()
        self.vskipped: Counter = Counter()
        self.vfindings: List[Finding] = []
        self._ids: Dict[int, str] = {}
        self._heights: Dict[Tuple[object, int], int] = {}
        self._menus: Set[int] = set()
        # Strong references: a widget's wrapper that is freed lets Python reuse its
        # id() for another widget, which the ``seen`` test would then skip.
        self._keep: List[object] = []

    # -- helpers ---------------------------------------------------------

    def _once(self, widget: QWidget) -> bool:
        key = id(widget)
        if key in self.seen:
            return False
        self.seen.add(key)
        self._keep.append(widget)
        return True

    @staticmethod
    def _where(widget: QWidget) -> str:
        window = widget.window()
        return f"{type(window).__name__}/{type(widget).__name__}[{widget.objectName()}]"

    def identity(self, node: QObject) -> str:
        """Return the widget's object path: class, object name and sibling index.

        The index among same-class, same-name siblings is added only when there is
        more than one. Nothing translated is read.
        """
        cached = self._ids.get(id(node))
        if cached is not None:
            return cached
        parts: List[str] = []
        current: Optional[QObject] = node
        while current is not None:
            parent = current.parent()
            name = f"{type(current).__name__}[{current.objectName()}]"
            if parent is not None:
                twins = [
                    child
                    for child in parent.children()
                    if type(child) is type(current)
                    and child.objectName() == current.objectName()
                ]
                if len(twins) > 1:
                    position = next(
                        index for index, twin in enumerate(twins) if twin is current
                    )
                    name += f"#{position}"
            parts.append(name)
            current = parent
        path = "/".join(reversed(parts))
        self._ids[id(node)] = path
        self._keep.append(node)
        return path

    def _note(self, kind: str, trail: str) -> str:
        """Record that a text of ``kind`` was examined at ``trail``; return its key."""
        key = f"{kind}|{self.prefix}|{trail}"
        self.keys[kind].append(key)
        return key

    def _flag(
        self, kind: str, widget: QWidget, text: str, need: int, have: int, key: str
    ) -> None:
        self.findings.append(
            Finding(kind, self._where(widget), text.strip()[:60], need, have, key)
        )

    def _vertical(
        self,
        kind: str,
        key: str,
        widget: QWidget,
        text: str,
        given: int,
    ) -> None:
        """Compare the height of the DISPLAYED ``text`` with the height given.

        The height a text needs is the line height of the family that really draws
        each of its characters in the widget's own font (see :meth:`text_height`),
        never the line height of one family assumed for the whole text.
        """
        if self.vfont is None:
            return
        shown = displayed_text(widget, text)
        if "\n" in text or "\n" in shown or given <= 0 or not shown.strip():
            self.vskipped[kind] += 1
            return
        self.vexamined[kind] += 1
        need = self.text_height(widget.font(), shown)
        if need > given:
            self.vfindings.append(
                Finding(kind, self._where(widget), shown.strip()[:60], need, given, key)
            )

    def text_height(self, font: QFont, shown: str) -> int:
        """Return the height ``shown`` needs when drawn in ``font``.

        Each displayed character is attributed to the family that draws it
        (:func:`drawing_family`, read one character at a time), and the text needs
        the tallest line box among those families. The line box of a family is
        measured by laying the character out in ``font`` narrowed to that family
        alone, so it is that family's own metric and not a constant. A text drawn
        by two families needs the taller of the two, so a label with a space, a
        digit or a Latin letter among Hangul is still judged at the platform
        font's height; a text drawn wholly by a face with a shorter line box is
        judged at that face's height. When no family can be read for a character,
        the platform font (``vfont``) is taken, which is the taller and stricter.
        """
        assert self.vfont is not None
        base = (
            tuple(font.families()),
            font.family(),
            font.pixelSize(),
            font.weight(),
            font.italic(),
            font.styleStrategy(),
        )
        need = 0
        for code_point in sorted({ord(ch) for ch in shown if ord(ch) >= 0x20}):
            cached = self._heights.get((base, code_point))
            if cached is None:
                family = drawing_family(font, code_point) or self.vfont.family()
                narrowed = QFont(font)
                narrowed.setFamilies([family])
                narrowed.setFamily(family)
                cached = QFontMetrics(narrowed).boundingRect(chr(code_point)).height()
                self._heights[(base, code_point)] = cached
            need = max(need, cached)
        return need

    # -- the rules -------------------------------------------------------

    def label(self, label: QLabel) -> None:
        """A label: narrower than its size hint, or too short for its wrapped text."""
        text = label.text()
        if not text or label.pixmap() is not None and label.pixmap().isNull() is False:
            return
        self.examined["label"] += 1
        key = self._note("label", self.identity(label))
        if label.wordWrap():
            need = label.heightForWidth(label.width())
            if need > label.height():
                self._flag("label (wrapped)", label, text, need, label.height(), key)
            return
        need = label.sizeHint().width()
        if label.width() < need:
            self._flag("label", label, text, need, label.width(), key)
        self._vertical("label", key, label, text, label.contentsRect().height())

    def button(self, button: QAbstractButton) -> None:
        """A button that shows text: narrower than its size hint."""
        if not button.text() or button.objectName().startswith("qt_"):
            return
        if isinstance(button, QToolButton) and (
            button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        ):
            return
        self.examined["button"] += 1
        key = self._note("button", self.identity(button))
        need = button.sizeHint().width()
        if button.width() < need:
            self._flag("button", button, button.text(), need, button.width(), key)
        self._vertical("button", key, button, button.text(), button.height())

    def group_box(self, box: QGroupBox) -> None:
        """A group box title: the title reaches past the edge of the box that holds it.

        Only the title is measured, never what the box contains. The rectangle the
        title needs is the one the box's own style computes for it in the font it
        really has (the text, the indicator of a checkable box, the style's padding,
        the alignment); the title is cut when that rectangle ends beyond the box's
        width, or starts before its left edge. ``need`` is the extent of the title
        measured from the box's left edge (or from the title's own left edge when
        that lies outside) and ``have`` is the width of the box. The box's
        ``sizeHint`` is not used: it is the larger of the title and the contents, so
        a box narrower than the default hint of a list inside it would be reported
        with every title intact.
        """
        if not box.title():
            return
        self.examined["group box"] += 1
        key = self._note("group box", self.identity(box))
        option = QStyleOptionGroupBox()
        box.initStyleOption(option)
        label = box.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox,
            option,
            QStyle.SubControl.SC_GroupBoxLabel,
            box,
        )
        need = label.right() + 1 - min(label.left(), 0)
        if label.left() < 0 or label.right() + 1 > box.width():
            self._flag("group box", box, box.title(), need, box.width(), key)
        if self.vfont is not None:
            self._vertical(
                "group box",
                key,
                box,
                box.title(),
                label.height() or box.contentsMargins().top(),
            )

    def tab_bar(self, bar: QTabBar) -> None:
        """Every tab: its rectangle narrower than the size hint of its text."""
        for index in range(bar.count()):
            if not bar.tabText(index):
                continue
            self.examined["tab"] += 1
            key = self._note("tab", f"{self.identity(bar)}#{index}")
            need = bar.tabSizeHint(index).width()
            have = bar.tabRect(index).width()
            if have < need:
                self._flag("tab", bar, bar.tabText(index), need, have, key)
            rect = bar.tabRect(index)
            given = rect.width() if bar.shape() in _VERTICAL_SHAPES else rect.height()
            self._vertical("tab", key, bar, bar.tabText(index), given)

    def dock_title(self, dock: QDockWidget) -> None:
        """A dock title: wider than the text rectangle the style gives the title bar."""
        title = dock.windowTitle()
        if not title:
            return
        self.examined["dock title"] += 1
        key = self._note("dock title", self.identity(dock))
        option = QStyleOptionDockWidget()
        dock.initStyleOption(option)
        text_rect = dock.style().subElementRect(
            QStyle.SubElement.SE_DockWidgetTitleBarText, option, dock
        )
        sideways = bool(
            dock.features() & QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        )
        have = text_rect.height() if sideways else text_rect.width()
        need = QFontMetrics(dock.font()).horizontalAdvance(title)
        if need > have:
            self._flag("dock title", dock, title, need, have, key)
        bar = option.rect
        self._vertical(
            "dock title", key, dock, title, bar.width() if sideways else bar.height()
        )

    def combo(self, combo: QComboBox) -> None:
        """The current text of a combo box against its edit area."""
        text = combo.currentText()
        if not text:
            return
        self.examined["combo"] += 1
        key = self._note("combo", self.identity(combo))
        option = QStyleOptionComboBox()
        option.initFrom(combo)
        option.rect = combo.rect()
        field_rect = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            combo,
        )
        need = QFontMetrics(combo.font()).horizontalAdvance(text)
        if need > field_rect.width():
            self._flag("combo", combo, text, need, field_rect.width(), key)
        self._vertical("combo", key, combo, text, field_rect.height())

    def spin(self, spin: QAbstractSpinBox) -> None:
        """A spin box's displayed text against the width of its editor."""
        editor = spin.lineEdit()
        text = spin.text()
        if editor is None or not text:
            return
        self.examined["spin"] += 1
        key = self._note("spin", self.identity(spin))
        margins = editor.textMargins()
        need = (
            QFontMetrics(editor.font()).horizontalAdvance(text)
            + margins.left()
            + margins.right()
        )
        if need > editor.width():
            self._flag("spin", spin, text, need, editor.width(), key)
        self._vertical("spin", key, spin, text, editor.height())

    def menu_bar(self, bar: QMenuBar) -> None:
        """Every top-level menu entry must lie inside the bar (not in its overflow)."""
        trail = self.identity(bar)
        for index, action in enumerate(bar.actions()):
            if not action.text():
                continue
            self.examined["menu"] += 1
            key = self._note("menu", f"{trail}#{index}")
            geometry = bar.actionGeometry(action)
            if geometry.isEmpty() or not bar.rect().contains(geometry):
                self._flag(
                    "menu", bar, action.text(), geometry.width(), bar.width(), key
                )
            elif self.vfont is not None:
                self._vertical("menu", key, bar, action.text(), geometry.height())
        for index, action in enumerate(bar.actions()):
            if action.menu() is not None:
                self.menu(cast(QMenu, action.menu()), f"{trail}#{index}")

    def menu(self, menu: QMenu, trail: str) -> None:
        """Every action row of a menu, and of its submenus, is as wide as its text."""
        if id(menu) in self._menus:
            return
        self._menus.add(id(menu))
        self._keep.append(menu)
        menu.ensurePolished()
        menu.sizeHint()
        metrics = QFontMetrics(menu.font())
        for index, action in enumerate(menu.actions()):
            if not action.isSeparator() and action.text():
                self.examined["menu action"] += 1
                key = self._note("menu action", f"{trail}.{index}")
                text = (
                    action.text()
                    .replace("&&", "\x00")
                    .replace("&", "")
                    .replace("\x00", "&")
                )
                row = menu.actionGeometry(action)
                need = metrics.horizontalAdvance(text)
                if row.width() < need:
                    self._flag("menu action", menu, text, need, row.width(), key)
                self._vertical("menu action", key, menu, text, row.height())
            if action.menu() is not None:
                self.menu(cast(QMenu, action.menu()), f"{trail}.{index}")

    def item_view(self, view: QAbstractItemView, limit: int = 400) -> None:
        """Rows and header sections: the text against the cell it is drawn in."""
        model = view.model()
        if model is None:
            return
        trail = self.identity(view)
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
                key = self._note("header", f"{trail}#{section}")
                need = metrics.horizontalAdvance(str(text)) + 2 * (
                    header.style().pixelMetric(
                        QStyle.PixelMetric.PM_HeaderMargin, None, header
                    )
                )
                if header.sectionSize(section) < need:
                    self._flag(
                        "header",
                        view,
                        str(text),
                        need,
                        header.sectionSize(section),
                        key,
                    )
                self._vertical("header", key, view, str(text), header.height())
        metrics = QFontMetrics(view.font())
        margin = (
            view.style().pixelMetric(
                QStyle.PixelMetric.PM_FocusFrameHMargin, None, view
            )
            + 1
        )
        count = 0

        def walk(parent: QModelIndex, depth: int, path: str) -> None:
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
                        key = self._note("row", f"{trail}@{path}{row}:{column}")
                        have = rect.width() - 2 * margin
                        if isinstance(view, QTreeView) and column == 0:
                            have -= view.indentation() * (depth + 1)
                        need = metrics.horizontalAdvance(str(text))
                        # The estimate is within a pixel or two of what Qt does; the
                        # drawn row is the ground truth where it can be had.
                        if need > have and _drawn_elided(view, index) is not False:
                            self._flag("row", view, str(text), need, have, key)
                        self._vertical("row", key, view, str(text), rect.height())
                if isinstance(view, QTreeView) and model.hasChildren(
                    model.index(row, 0, parent)
                ):
                    if view.isExpanded(model.index(row, 0, parent)):
                        walk(model.index(row, 0, parent), depth + 1, f"{path}{row}.")

        walk(QModelIndex(), 0, "")

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
            elif isinstance(widget, QDockWidget):
                self.dock_title(widget)
            elif isinstance(widget, QComboBox):
                self.combo(widget)
            elif isinstance(widget, QAbstractSpinBox):
                self.spin(widget)
            elif isinstance(widget, QMenuBar):
                self.menu_bar(widget)
            elif isinstance(widget, QAbstractItemView):
                self.item_view(widget)

    def duplicate_keys(self) -> List[str]:
        """Return the keys that identify more than one examined text (none, ideally)."""
        every = [key for keys in self.keys.values() for key in keys]
        return sorted(key for key, count in Counter(every).items() if count > 1)

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

    def dump(self) -> Dict[str, object]:
        """Return everything the parent process needs, as JSON-able data."""
        return {
            "examined": dict(self.examined),
            "findings": [
                [f.kind, f.where, f.text, f.need, f.have, f.key] for f in self.findings
            ],
            "keys": {kind: list(keys) for kind, keys in self.keys.items()},
            "duplicate_keys": self.duplicate_keys(),
            "vertical": {
                "examined": dict(self.vexamined),
                "skipped": dict(self.vskipped),
                "findings": [
                    [f.kind, f.where, f.text, f.need, f.have, f.key]
                    for f in self.vfindings
                ],
            },
        }


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
    """Control (positive): a label, a button and a tab squeezed into 60 px are
    reported.
    """
    examiner = _controls(qtbot, squeezed=True)
    kinds = {f.kind for f in examiner.findings}
    assert {"label", "button"} <= kinds, examiner.report()
    assert sum(examiner.examined.values()) >= 3


def test_the_detector_passes_text_that_has_room(qtbot):
    """Control (negative): the same widgets in 700 px are examined and none is
    reported.
    """
    examiner = _controls(qtbot, squeezed=False)
    assert sum(examiner.examined.values()) >= 3
    assert examiner.findings == [], examiner.report()


def test_the_detector_reports_an_item_view_row_that_would_be_elided(qtbot):
    """Control: a tree row wider than its cell is reported (and drawn elided); a
    roomy one is not.
    """
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


_GROUP_TITLE = "A group box title that is rather long"

#: The two modes the group-box controls run in (the module's own sheet is Light).
_CONTROL_MODES = ("light", "dark")

#: The width of a box that shows any title of these controls whole.
_ROOMY_PX = 700


def _group_box(
    qtbot, title: str, width: int, contents: Optional[QWidget] = None
) -> QGroupBox:
    """Return a shown group box of exactly ``width`` px, with ``contents`` if given."""
    box = QGroupBox(title)
    if contents is not None:
        QVBoxLayout(box).addWidget(contents)
    box.setFixedWidth(width)
    cast(Any, box)._host = _host(qtbot, width + 40, box)
    return box


def _title_is_drawn_past(qtbot, title: str, edge: int) -> bool:
    """Say whether Qt draws ``title`` beyond ``edge`` px from the box's left side.

    The same box is rendered wide enough to show the title whole, once with the
    title and once with a blank one, and the rows of the title strip right of
    ``edge`` are compared: they differ only if the title (or the gap it leaves in
    the frame) is drawn there. This is what Qt draws, not what the detector
    computes, so it is the control's own ground truth.
    """
    shown = _group_box(qtbot, title, _ROOMY_PX)
    blank = _group_box(qtbot, " ", _ROOMY_PX)
    option = QStyleOptionGroupBox()
    shown.initStyleOption(option)
    rows = (
        shown.style()
        .subControlRect(
            QStyle.ComplexControl.CC_GroupBox,
            option,
            QStyle.SubControl.SC_GroupBoxLabel,
            shown,
        )
        .height()
        + 2
    )
    with_title = image_array(shown.grab().toImage())[:rows, edge:]
    without = image_array(blank.grab().toImage())[:rows, edge:]
    return not np.array_equal(with_title, without)


@pytest.mark.parametrize("mode", _CONTROL_MODES)
def test_the_detector_reports_a_group_box_title_cut_by_the_box(qapp, qtbot, mode):
    """Control (positive): a title wider than its 60 px box is reported, and drawn cut.

    The ground truth is the rendering: the same title in a wide box has ink beyond
    60 px. The detector must then report the box, with the title's extent beyond
    the width the box has.
    """
    apply_theme(qapp, mode, DEFAULT_STYLE)
    assert _title_is_drawn_past(qtbot, _GROUP_TITLE, 60), "the title fits in 60 px"
    box = _group_box(qtbot, _GROUP_TITLE, 60)
    examiner = Examiner()
    examiner.examine(box)
    assert examiner.examined["group box"] == 1, examiner.report()
    assert len(examiner.findings) == 1, examiner.report()
    found = examiner.findings[0]
    assert found.kind == "group box" and found.text == _GROUP_TITLE
    assert found.have == 60 and found.need > found.have, examiner.report()


@pytest.mark.parametrize("mode", _CONTROL_MODES)
def test_the_detector_passes_a_group_box_whose_title_has_room(qapp, qtbot, mode):
    """Control (negative): the same title in a box that shows it whole passes."""
    apply_theme(qapp, mode, DEFAULT_STYLE)
    box = _group_box(qtbot, _GROUP_TITLE, _ROOMY_PX)
    examiner = Examiner()
    examiner.examine(box)
    assert examiner.examined["group box"] == 1, examiner.report()
    assert examiner.findings == [], examiner.report()


@pytest.mark.parametrize("mode", _CONTROL_MODES)
def test_the_detector_passes_a_group_box_squeezed_below_its_contents_hint(
    qapp, qtbot, mode
):
    """Control (negative): a short title is not cut because the contents want more room.

    A list's default size hint is wide. The box is made narrower than that hint (the
    condition the earlier rule, a comparison with the box's size hint, reported) and
    wider than its short title. Qt draws the title whole, so nothing is reported.
    """
    from PySide6.QtWidgets import QListWidget

    apply_theme(qapp, mode, DEFAULT_STYLE)
    title = "Short"
    view = QListWidget()
    probe = QGroupBox(title)
    QVBoxLayout(probe).addWidget(view)
    narrow = 90
    assert probe.sizeHint().width() > narrow, "the contents do not ask for more room"
    box = _group_box(qtbot, title, narrow, QListWidget())
    assert (
        box.width() < box.sizeHint().width()
    ), "the box is not squeezed below its hint"
    assert not _title_is_drawn_past(qtbot, title, narrow), "the short title is cut"
    examiner = Examiner()
    examiner.examine(box)
    assert examiner.examined["group box"] == 1, examiner.report()
    assert examiner.findings == [], examiner.report()


#: Width at the right of a dock's title bar left out of the text comparison: the
#: float and close buttons.
_TITLE_BUTTONS_PX = 50


def _title_strip(dock: QDockWidget) -> np.ndarray:
    """Return the pixels of the dock's title bar, as Qt drew them."""
    option = QStyleOptionDockWidget()
    dock.initStyleOption(option)
    return image_array(dock.grab(option.rect).toImage())


def _docked(qtbot, title: str, width: int) -> Tuple[QMainWindow, QDockWidget]:
    """Return a shown window whose left dock, titled ``title``, is ``width`` wide."""
    window = QMainWindow()
    window.setCentralWidget(QLabel("central"))
    dock = QDockWidget(title)
    dock.setObjectName("planted_dock")
    dock.setWidget(QLabel("body"))
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    qtbot.addWidget(window)
    window.resize(1000, 300)
    window.show()
    qtbot.waitExposed(window)
    window.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
    QApplication.processEvents()
    return window, dock


def test_the_detector_reports_a_dock_title_that_the_title_bar_would_elide(qtbot):
    """Control: a long title in a narrow dock is reported, and Qt draws it elided.

    The rule compares the title with the text rectangle the style gives the title
    bar. The render check proves the rule matches what Qt draws: the left part of
    the title bar differs between the narrow dock and the same dock made wide
    exactly when the title is elided. The same title with room is not reported.
    """
    title = "A dock title that is far too long for the bar that holds it"
    window, dock = _docked(qtbot, title, 140)
    narrow = Examiner()
    narrow.examine(dock)
    assert narrow.examined["dock title"] == 1, narrow.report()
    assert [f.kind for f in narrow.findings] == ["dock title"], narrow.report()
    before = _title_strip(dock)
    text_part = before.shape[1] - _TITLE_BUTTONS_PX
    window.resizeDocks([dock], [700], Qt.Orientation.Horizontal)
    QApplication.processEvents()
    after = _title_strip(dock)
    assert after.shape[1] > before.shape[1], "the dock did not grow"
    assert not np.array_equal(
        before[:, :text_part], after[:, :text_part]
    ), "the render check cannot see an elided dock title"
    roomy = Examiner()
    roomy.examine(dock)
    assert roomy.examined["dock title"] == 1 and roomy.findings == [], roomy.report()


def test_the_detector_keeps_a_dock_title_that_has_room_and_draws_it_whole(qtbot):
    """Control (negative): a short title in a wide dock is not reported or elided."""
    window, dock = _docked(qtbot, "Palette", 400)
    examiner = Examiner()
    examiner.examine(dock)
    assert examiner.examined["dock title"] == 1 and examiner.findings == []
    before = _title_strip(dock)
    text_part = before.shape[1] - _TITLE_BUTTONS_PX
    window.resizeDocks([dock], [700], Qt.Orientation.Horizontal)
    QApplication.processEvents()
    after = _title_strip(dock)
    assert after.shape[1] > before.shape[1], "the dock did not grow"
    assert np.array_equal(
        before[:, :text_part], after[:, :text_part]
    ), "a title with room was drawn differently in a wider dock"


def test_a_key_names_the_widget_and_never_its_text(qtbot):
    """A key is stable across a change of text and tells same-class siblings apart."""
    first, second = QLabel("One"), QLabel("Two")
    first.setObjectName("same")
    second.setObjectName("same")
    host = _host(qtbot, 400, first, second)
    examiner = Examiner()
    examiner.prefix = "host"
    examiner.examine(host)
    before = list(examiner.keys["label"])
    assert len(before) == 2 and len(set(before)) == 2, before
    assert examiner.duplicate_keys() == []
    first.setText("Un texte tout à fait différent")
    second.setText("Zwei")
    QApplication.processEvents()
    again = Examiner()
    again.prefix = "host"
    again.examine(host)
    assert again.keys["label"] == before, "the key changed with the text"
    assert not any("One" in key or "Zwei" in key for key in before)


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
        "Document_Transform_Progress_Dialog": lambda: (
            Document_Transform_Progress_Dialog("Scale Canvas", 7)
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
# The prompts: message boxes the interface raises                              #
# --------------------------------------------------------------------------- #
#
# A message box is a ``QMessageBox`` and not a ``QDialog`` subclass of the ``ui``
# package, so the completeness test above cannot find it. Each prompt that shows
# words of the interface on buttons is listed here instead, and each row is
# examined as the dialogs are, on the "dialogs" surface, by the same detector and
# the same rule (a language against English, by widget identity). A row is opened by
# the interface's own handler, so what is measured is the box the user sees and not
# a copy of it: the handler blocks in its modal loop, and a timer reads the box while
# it is open, then closes it.

PROMPT_POLL_MS = 5
PROMPT_WATCHDOG_MS = 8000


def _open_unsaved_changes_prompt(win: QWidget) -> None:
    """Drop a project onto a window whose document has unsaved changes."""
    tab = cast(Any, win).active_tab()
    assert tab is not None, "the window has no open document"
    if tab.stack.isClean():
        tab.stack.push(QUndoCommand("edit"))
    cast(Any, win)._import_project_drop("dropped-project.pixproj")


def _open_plugin_consent_prompt(win: QWidget) -> None:
    """Press Enable on a plugin that declares two permissions."""
    from pixelart_creator.logic.plugins import validate_manifest
    from pixelart_creator.ui.plugin_manager_panel import Plugin_Manager_Panel

    panel = Plugin_Manager_Panel()
    try:
        panel._add_manifest_item(
            validate_manifest(
                {
                    "name": "lang-probe",
                    "version": "1.0",
                    "api_version": "1",
                    "capabilities": ["read_document", "write_via_command"],
                }
            )
        )
        assert panel._enable_button.isEnabled(), "Enable is not available"
        panel._enable_button.click()
    finally:
        if isValid(panel):
            shiboken6.delete(panel)


#: The inventory: prompt name -> the opener that makes the interface raise it. The
#: name is the first part of every key of the row's texts.
PROMPTS: Dict[str, Callable[[QWidget], None]] = {
    "Unsaved_Changes_Prompt": _open_unsaved_changes_prompt,
    "Plugin_Consent_Prompt": _open_plugin_consent_prompt,
}

#: The fewest button texts each row must show, as measured: the unsaved-changes
#: prompt's Save, Discard and Cancel, and the consent prompt's two answers.
PROMPT_BUTTONS: Dict[str, int] = {
    "Unsaved_Changes_Prompt": 3,
    "Plugin_Consent_Prompt": 2,
}


def examine_prompt(
    win: QWidget,
    name: str,
    examiner: "Examiner",
    tweak: Optional[Callable[[QMessageBox], None]] = None,
) -> QMessageBox:
    """Open the prompt ``name``, examine its box while it is on screen, close it.

    ``tweak`` is called on the open box before the examination (a planted control
    uses it to give a button less room than its text needs). Returns the box, which
    is gone when the handler built it as a static call does; an error raised while
    examining is carried out of the Qt loop and raised here, and a box that stays on
    screen is closed by a watchdog and reported.
    """
    opened: List[QMessageBox] = []
    problem: List[BaseException] = []
    started = time.monotonic()
    timer = QTimer()
    timer.setInterval(PROMPT_POLL_MS)

    def poll() -> None:
        boxes = [
            widget
            for widget in QApplication.topLevelWidgets()
            if isinstance(widget, QMessageBox) and widget.isVisible()
        ]
        if not boxes:
            return
        box = boxes[0]
        if opened:
            if (time.monotonic() - started) * 1000 > PROMPT_WATCHDOG_MS:
                problem.append(AssertionError(f"{name}: a box stayed on screen"))
                box.done(int(QMessageBox.StandardButton.Cancel))
            return
        opened.append(box)
        try:
            if tweak is not None:
                tweak(box)
            QApplication.processEvents()
            examiner.prefix = name
            examiner.examine(box)
            examiner.examined["prompts"] += 1
        except BaseException as exc:  # carried out of the Qt loop, then raised
            problem.append(exc)
        finally:
            box.done(int(QMessageBox.StandardButton.Cancel))

    timer.timeout.connect(poll)
    timer.start()
    try:
        PROMPTS[name](win)
    finally:
        timer.stop()
    if problem:
        raise problem[0]
    assert len(opened) == 1, f"{name}: {len(opened)} message boxes were opened, not 1"
    box = opened[0]
    if isValid(box):
        shiboken6.delete(box)
    return box


def prompt_rows(keys: Dict[str, List[str]]) -> Dict[str, Dict[str, int]]:
    """Count the texts examined on each prompt row, by kind, from the item's keys."""
    rows: Dict[str, Dict[str, int]] = {name: {} for name in PROMPTS}
    for kind, found in keys.items():
        for key in found:
            prefix = key.split("|", 2)[1]
            if prefix in rows:
                rows[prefix][kind] = rows[prefix].get(kind, 0) + 1
    return rows


def test_the_prompt_inventory_names_the_two_prompts():
    """REQ-L10N-UI-013: the inventory holds the unsaved-changes and consent prompts."""
    assert set(PROMPTS) == {"Unsaved_Changes_Prompt", "Plugin_Consent_Prompt"}
    assert set(PROMPT_BUTTONS) == set(PROMPTS)
    assert PROMPT_BUTTONS["Unsaved_Changes_Prompt"] == 3


def test_a_prompt_is_examined_with_its_buttons_and_its_text(qtbot):
    """REQ-L10N-UI-013: each prompt row yields its buttons and its message.

    The real handler of each prompt is run in the test's own window; the examiner
    reads the open box. Each row must show at least its buttons, and its message
    text is a label examined besides. A prompt the handler never opens fails.
    """
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    win.show()
    QApplication.processEvents()
    examiner = Examiner()
    for name in PROMPTS:
        examine_prompt(win, name, examiner)
    rows = prompt_rows(examiner.keys)
    assert examiner.examined["prompts"] == len(PROMPTS)
    for name, buttons in PROMPT_BUTTONS.items():
        assert rows[name].get("button", 0) >= buttons, (name, rows[name])
        assert rows[name].get("label", 0) >= 1, (name, rows[name])
    assert not examiner.duplicate_keys()


# --------------------------------------------------------------------------- #
# The faces the instruments stand on                                           #
# --------------------------------------------------------------------------- #
#
# The vertical check and the guide-page check depend on WHICH family draws a
# glyph, so they judge families the test registers itself, on the offscreen
# platform:
#
# * a stand-in for a Han-capable platform UI font: Latin, Cyrillic, punctuation,
#   every Han and Hangul character any catalogue holds, and the characters of the
#   bundled CJK faces. Every glyph is a plain box 12 px above the baseline and 3
#   below, in a line box of 13 and 3 (Nifen Art's line box is 11 and 3), so a line
#   box shorter than the glyphs is possible to detect. No outline is taken from
#   any font.
# * the bundled CJK faces, registered from the package files;
# * a Latin-only face without the n-tilde, for the positive control.

STANDIN_FAMILY = "Probe Platform UI Han"
_STANDIN_ASCENT_PX = 13
_STANDIN_DESCENT_PX = 3
_I18N_DIR = Path(ui_package.__file__).resolve().parent.parent / "i18n"
_FONTS_PACKAGE = "pixelart_creator"


def _standin_code_points() -> List[int]:
    """Return the code points the stand-in holds (integers, BMP only)."""
    held: Set[int] = set(range(0x20, 0x7F))
    for first, last in (
        (0xA0, 0x17F),  # Latin-1 and Latin Extended-A
        (0x400, 0x45F),  # Cyrillic
        (0x2000, 0x206F),  # general punctuation
        (0x2190, 0x21FF),  # arrows
        (0x3000, 0x303F),  # CJK symbols and punctuation
        (0xFF00, 0xFF5F),  # full-width forms
    ):
        held.update(range(first, last + 1))
    for catalogue in sorted(_I18N_DIR.glob("pixelart_*.ts")):
        held.update(
            ord(ch)
            for ch in catalogue.read_text(encoding="utf-8")
            if 0x20 <= ord(ch) <= 0xFFFF and not 0xD800 <= ord(ch) <= 0xDFFF
        )
    fonts = Path(ui_package.__file__).resolve().parent.parent / "fonts"
    for face in sorted(fonts.glob("NifenArtCJK*.ttf")):
        held.update(
            cp
            for cp in cast(Dict[int, str], TTFont(str(face)).getBestCmap())
            if cp <= 0xFFFF
        )
    return sorted(held)


def build_standin_face(path: Path) -> Path:
    """Write the Han-capable platform stand-in as a TrueType file; return ``path``."""
    cps = _standin_code_points()
    names = {cp: f"uni{cp:04X}" for cp in cps}
    box = TTGlyphPen(None)
    # The glyph reaches the bottom of the line box and stops one pixel short of its
    # top, as a font's ink stays inside its line box; a face whose glyphs fill the
    # box exactly would be "taller" than its line as soon as a bold is synthesised.
    top, bottom = (_STANDIN_ASCENT_PX - 1) * _PX, -_STANDIN_DESCENT_PX * _PX
    box.moveTo((0, bottom))
    box.lineTo((0, top))
    box.lineTo((11 * _PX, top))
    box.lineTo((11 * _PX, bottom))
    box.closePath()
    full = box.glyph()
    empty = TTGlyphPen(None).glyph()
    blank = {0x20, 0xA0}
    order = [".notdef"] + [names[cp] for cp in cps]
    glyphs = {".notdef": full}
    glyphs.update({names[cp]: (empty if cp in blank else full) for cp in cps})
    builder = FontBuilder(_UPEM, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({cp: names[cp] for cp in cps})
    builder.setupGlyf(glyphs)
    table = builder.font["glyf"]
    builder.setupHorizontalMetrics(
        {name: (_ADVANCE, table[name].xMin) for name in order}
    )
    ascent, descent = _STANDIN_ASCENT_PX * _PX, _STANDIN_DESCENT_PX * _PX
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    builder.setupNameTable({"familyName": STANDIN_FAMILY, "styleName": "Regular"})
    builder.setupOS2(
        version=4,
        sTypoAscender=ascent,
        sTypoDescender=-descent,
        sTypoLineGap=0,
        usWinAscent=ascent,
        usWinDescent=descent,
        fsSelection=0xC0,
        usWeightClass=400,
    )
    os2 = builder.font["OS/2"]
    (
        os2.ulUnicodeRange1,
        os2.ulUnicodeRange2,
        os2.ulUnicodeRange3,
        os2.ulUnicodeRange4,
    ) = _range_words(_BITS_LATIN + _BITS_CJK, 4)
    os2.ulCodePageRange1, os2.ulCodePageRange2 = _range_words(
        _CODEPAGE_LATIN + _CODEPAGE_CJK, 2
    )
    builder.setupPost()
    builder.save(str(path))
    return path


@pytest.fixture(scope="session")
def instrument_faces(tmp_path_factory) -> Dict[str, str]:
    """Build the stand-in and the Latin-only face once per worker; return the paths."""
    folder = tmp_path_factory.mktemp("instrument-faces")
    return {
        "standin": str(build_standin_face(folder / "standin.ttf")),
        "latin_only": str(build_face(FACES["L"], folder / "latin-only.ttf")),
    }


def drawing_family(font: QFont, code_point: int) -> str:
    """Return the family that draws ``code_point`` in ``font``, one character at a time.

    A multi-run layout's ``glyphRuns()`` come back in an order that differs between
    processes on identical input, so the family is never read from a run's index.
    """
    layout = QTextLayout(chr(code_point), font)
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(100000)
    layout.endLayout()
    runs = layout.glyphRuns()
    return str(runs[0].rawFont().familyName()) if runs else ""


def register_instruments(standin_path: str, latin_only_path: str) -> List[str]:
    """Register the stand-in, the Latin-only face and the bundled CJK faces.

    Everything is registered before the first drawing that depends on it, because a
    registration clears Qt's font cache. Returns the bundled CJK families found.
    The CJK faces are registered the way the application registers its own faces:
    from the package's bytes, one by one.
    """
    from importlib import resources

    # The application's own start-up order: Nifen Art registered, the platform font
    # captured, the substitutions installed (each a no-op when already done).
    app_font.register_app_fonts()
    app_font.capture_platform_font()
    app_font.install_font_substitutions()
    cjk: List[str] = []
    for path in (standin_path, latin_only_path):
        font_id = QFontDatabase.addApplicationFont(path)
        assert font_id >= 0, f"Qt rejected the instrument face {path}"
    for node in sorted(
        (resources.files(_FONTS_PACKAGE) / "fonts").iterdir(), key=lambda n: n.name
    ):
        if node.name.startswith("NifenArtCJK") and node.name.endswith(".ttf"):
            font_id = QFontDatabase.addApplicationFontFromData(
                QByteArray(node.read_bytes())
            )
            if font_id >= 0:
                for family in QFontDatabase.applicationFontFamilies(font_id):
                    if family not in cjk:
                        cjk.append(family)
    return cjk


def standin_font() -> QFont:
    """Return the stand-in at the interface's size, the way the interface draws."""
    font = QFont(STANDIN_FAMILY)
    font.setPixelSize(app_font.NIFEN_ART_EM_PX)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def positive_control() -> str:
    """Fail, naming the plugin, unless the next family draws what the first lacks.

    A character the first family does not hold (the n-tilde, absent from the
    Latin-only face) must be drawn by the next registered family. If it is not,
    this platform cannot tell registered families apart and no verdict that
    follows can be read from it.
    """
    latin_only = FACES["L"].family
    font = QFont(latin_only)
    font.setFamilies([latin_only, app_font.NIFEN_ART_FAMILY])
    font.setPixelSize(app_font.NIFEN_ART_EM_PX)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    drew = drawing_family(font, N_TILDE)
    plugin = QGuiApplication.platformName()
    assert drew == app_font.NIFEN_ART_FAMILY, (
        f"the positive control FAILED on the {plugin!r} plugin: U+{N_TILDE:04X} in "
        f"{[latin_only, app_font.NIFEN_ART_FAMILY]} was drawn by {drew!r}, not by the "
        f"next registered family {app_font.NIFEN_ART_FAMILY!r}. This plugin cannot "
        "tell registered families apart, so no verdict below can be read from it."
    )
    return plugin


def force_platform_font(font: QFont) -> None:
    """Make ``font`` what the application takes for the platform's own font.

    The sibling font tests reset the same snapshot (``start_like_a_new_process``);
    the per-class fonts are emptied so every class follows the application font.
    """
    app_font.capture_platform_font()
    app_font._platform["font"] = QFont(font)
    app_font._platform["classes"] = {}


def han_capable_platform(app: QApplication, language: str) -> Dict[str, object]:
    """Force the stand-in as the platform family and apply "Use system font".

    The product's own detector must call the stand-in Han-capable (it holds a
    character a bundled CJK face holds). Then the application font is read: if the
    product already puts a family list on the platform font, that is what is
    measured (``source`` ``"product"``). If it does not yet, the list the plan
    prescribes for a Han-capable platform family, the CJK families first, is built
    with the product's own ``family_chain`` and ``chain_font`` and applied
    app-wide (``source`` ``"modelled"``), so the line-metric cost of that order is
    measured now and not only after the application adopts it.
    """
    plain = standin_font()
    force_platform_font(plain)
    holds = app_font.primary_holds_cjk(STANDIN_FAMILY)
    assert holds, (
        f"the product's detector says {STANDIN_FAMILY!r} holds no shipped Han or "
        "Hangul character: the stand-in is not a Han-capable platform family"
    )
    app_font.apply_interface_font(app, True)
    source = "product"
    if len(app.font().families()) < 2:
        chain = font_chain.family_chain(STANDIN_FAMILY, language, language, holds)
        force_platform_font(app_font.chain_font(plain, chain))
        app_font.apply_interface_font(app, True)
        source = "modelled"
    return {
        "source": source,
        "chain": list(app.font().families()) or [app.font().family()],
        "primary_holds_cjk": holds,
    }


# --------------------------------------------------------------------------- #
# The measurement: Nifen Art against the platform font, in a child process     #
# --------------------------------------------------------------------------- #
#
# The requirement is that no label is truncated BY THE CHANGE OF FONT. Text that
# is cut short with the platform font as well (27 dock tabs in one tab bar are,
# with any font) is not caused by the change, so the verdict is a comparison: every
# examined widget is measured with Nifen Art and again, in the same window, with "Use
# system font" on; only text that is truncated with Nifen Art and NOT with the
# platform font fails. Text truncated with both is counted and printed (it is
# real and the owner should know), but it is not what this requirement asks.
#
# The comparison needs a platform font to compare with, so it runs in a child
# process whose font database is the platform's own (``test_app_font`` explains
# why the headless font database of this host is empty otherwise). A child that
# sees no platform font fails: with one font there is nothing to compare.
#
# On top of it, an item of a language other than English runs the English child of
# the same (scale, mode, surface, style) and compares the two by widget identity.


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
    from PySide6.QtGui import QFontInfo

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
        windll = getattr(ctypes, "windll")  # Windows only; absent elsewhere
        ok = windll.user32.SystemParametersInfoW(
            spi_getnonclientmetrics, metrics.cbSize, ctypes.byref(metrics), 0
        )
        face = metrics.lfMessageFont.lfFaceName if ok else ""
        if face:
            QFont.insertSubstitution(QFont().family(), face)
    return QFontInfo(QFont(QFont().family())).family()


def _examine_surface(win: QWidget, surface: str, examiner: Examiner) -> None:
    """Examine one surface: the main window with every dock raised, or every dialog.

    The "dialogs" surface also opens each prompt of :data:`PROMPTS`.
    """
    if surface == "main":
        examiner.prefix = "main"
        examiner.examine(win)
        docks = win.findChildren(QDockWidget)
        for dock in docks:
            dock.show()
            dock.raise_()
            QApplication.processEvents()
            examiner.examine(dock)
        examiner.examined["docks"] = len(docks)
        return
    for name, factory in _factories().items():
        examiner.prefix = name
        dialog = factory()
        dialog.show()
        QApplication.processEvents()
        examiner.examine(dialog)
        examiner.examined["dialogs"] += 1
        dialog.hide()
        dialog.deleteLater()
    for name in PROMPTS:
        examine_prompt(win, name, examiner)


def run_matrix(
    language: str,
    scale: int,
    mode: str,
    surface: str,
    style: str,
    standin: str = "",
    latin_only: str = "",
) -> Dict[str, object]:
    """Examine one surface in one style, with Nifen Art and with the platform font.

    Called inside the child process. ``surface`` is ``"main"`` (the main window with
    every dock raised in turn) or ``"dialogs"`` (every dialog class, built and shown).
    When the paths of the two instrument faces are given, a third pass follows the
    two font cases: the vertical check, with "Use system font" on and the Han-capable
    stand-in as the platform family. The result carries the seconds each phase took
    (``timing``), which is printed with the verdict so a slow item shows where its
    time went.
    """
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
    for font in FONT_CASES:
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
        _examine_surface(win, surface, examiner)
        lap("examine")
        results[font] = examiner.dump()
    vertical: Optional[Dict[str, object]] = None
    if standin:
        # After the two font cases, so that registering the instrument faces cannot
        # change what the platform-font comparison saw.
        register_instruments(standin, latin_only)
        plugin = positive_control()
        platform = han_capable_platform(app, language)
        if examines_window:
            _settle(win)
        examiner = Examiner(vfont=standin_font())
        _examine_surface(win, surface, examiner)
        dumped = examiner.dump()
        vertical = dict(
            platform, plugin=plugin, **cast(Dict[str, object], dumped["vertical"])
        )
        lap("vertical")
    win._language_manager.set_language(EN)
    return {
        "results": results,
        "vertical": vertical,
        "timing": timing,
        "families": len([f for f in QFontDatabase.families() if f != NIFEN]),
        "platform": generic,
        "app_font_nifen": app_font.interface_font().family(),
    }


_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_matrix
out(**run_matrix(
    {language!r}, {scale}, {mode!r}, {surface!r}, {style!r}, {standin!r}, {latin_only!r}
))
"""


# --------------------------------------------------------------------------- #
# The verdict                                                                  #
# --------------------------------------------------------------------------- #


#: Kinds whose examined set may differ between two languages without the key being
#: unstable. A cell is examined only if the view shows it, and what a view shows
#: depends on the width the language's text gave the window (measured: a column that
#: is inside the viewport in Korean and outside it in English). Such a cell that is
#: truncated in L still counts as a finding, because English has no truncation to
#: share; the count of cells with no English counterpart is printed for every item.
VIEWPORT_DEPENDENT_KINDS = frozenset({"row"})

Comparison = Callable[
    [List[Finding], List[Finding]], Tuple[List[Finding], List[Finding]]
]


def differential(
    language_findings: List[Finding], english_findings: List[Finding]
) -> Tuple[List[Finding], List[Finding]]:
    """Split L's truncations into findings and those English has as well.

    A truncation in L is a finding unless the same widget (the same key) is
    truncated in English. Returns ``(findings, truncated_in_english_too)``.
    """
    english = {finding.key for finding in english_findings}
    findings = [f for f in language_findings if f.key not in english]
    shared = [f for f in language_findings if f.key in english]
    return findings, shared


def judge_language_alone(
    language_findings: List[Finding], english_findings: List[Finding]
) -> Tuple[List[Finding], List[Finding]]:
    """The broken copy: drop the English side and judge L alone (the absolute rule)."""
    return list(language_findings), []


def _findings(rows: Iterable[Sequence[object]]) -> List[Finding]:
    return [Finding(*cast(Any, row)) for row in rows]


@dataclass
class Verdict:
    """What one item decided: the findings, and everything counted and printed."""

    language: str
    examined: Dict[str, int] = field(default_factory=dict)
    reference_examined: int = 0
    platform_only: List[Finding] = field(default_factory=list)
    both_fonts: int = 0
    against_english: Dict[str, List[Finding]] = field(default_factory=dict)
    english_too: Dict[str, List[Finding]] = field(default_factory=dict)
    unmatched: Dict[str, Dict[str, int]] = field(default_factory=dict)
    clipped: List[Finding] = field(default_factory=list)
    vertical_examined: int = 0
    vertical_source: str = ""

    @property
    def failures(self) -> List[Tuple[str, str, Finding]]:
        """Return every finding that fails the item: (criterion, font case, finding)."""
        out: List[Tuple[str, str, Finding]] = [
            ("nifen-vs-platform", "nifen", f) for f in self.platform_only
        ]
        for case, found in self.against_english.items():
            out.extend(("language-vs-english", case, f) for f in found)
        out.extend(("vertical", "system", f) for f in self.clipped)
        return out

    @property
    def exit_status(self) -> int:
        """Return 0 when nothing fails and 1 otherwise, as the check's exit status."""
        return 1 if self.failures else 0

    def report(self) -> str:
        """Return the failures, each naming the label, the widget and the language."""
        lines = [f"{len(self.failures)} finding(s) in {self.language}:"]
        for criterion, case, finding in self.failures:
            lines.append(
                f"  [{criterion}, {case} font] language {self.language}: "
                f"{finding.describe()}"
            )
        return "\n".join(lines)

    def english_report(self) -> str:
        """Return the labels truncated in English as well, one per line."""
        lines = []
        for case, found in self.english_too.items():
            for finding in found:
                lines.append(
                    f"  [{case} font] truncated in English as well, for "
                    f"{self.language}: {finding.describe()}"
                )
        return "\n".join(lines)


def judge(
    language: str,
    child: Dict[str, object],
    reference: Optional[Dict[str, object]],
    compare: Comparison = differential,
) -> Verdict:
    """Judge one language's child result, against English when a reference is given.

    ``compare`` is the rule that splits L's truncations against English's; the
    broken copy is :func:`judge_language_alone`. The Nifen-against-platform
    criterion and the vertical check do not need the reference.
    """
    results = child["results"]
    assert isinstance(results, dict)
    verdict = Verdict(language)
    for case, data in results.items():
        duplicates = data["duplicate_keys"]
        assert not duplicates, (
            f"{language}: {len(duplicates)} keys identify more than one text, so the "
            f"widget identity is not stable: {duplicates[:5]}"
        )
    nifen, system = results["nifen"], results.get("system")
    verdict.examined = {
        case: sum(data["examined"].values()) for case, data in results.items()
    }
    if system is not None:
        base = {(f[0], f[1], f[2]) for f in system["findings"]}
        verdict.platform_only = [
            f
            for f in _findings(nifen["findings"])
            if (f.kind, f.where, f.text) not in base
        ]
        verdict.both_fonts = len(nifen["findings"]) - len(verdict.platform_only)
    if reference is not None:
        ref_results = reference["results"]
        assert isinstance(ref_results, dict)
        verdict.reference_examined = sum(
            sum(data["examined"].values()) for data in ref_results.values()
        )
        for case, data in results.items():
            ref = ref_results[case]
            found, shared = compare(
                _findings(data["findings"]), _findings(ref["findings"])
            )
            verdict.against_english[case] = found
            verdict.english_too[case] = shared
            english_keys = {k for keys in ref["keys"].values() for k in keys}
            missing: Dict[str, int] = {}
            for kind, keys in data["keys"].items():
                lost = sum(1 for key in keys if key not in english_keys)
                if lost:
                    missing[kind] = lost
            verdict.unmatched[case] = missing
    vertical = child.get("vertical")
    if isinstance(vertical, dict):
        verdict.clipped = _findings(vertical["findings"])
        verdict.vertical_examined = sum(vertical["examined"].values())
        verdict.vertical_source = str(vertical["source"])
    return verdict


# --------------------------------------------------------------------------- #
# Running an item                                                              #
# --------------------------------------------------------------------------- #

#: The English child of one (scale, mode, surface, style), kept for the worker's life.
_ENGLISH_REFERENCE: Dict[Tuple[int, str, str, str], Dict[str, object]] = {}


@pytest.fixture(scope="session")
def reference_dir(tmp_path_factory) -> Path:
    """Return a folder the workers of one session share, for the English references.

    Under pytest-xdist the session root is the parent of each worker's own base
    folder; serially it is the base folder. The folder belongs to this session
    alone, so a reference left by an earlier run cannot be read.
    """
    base = tmp_path_factory.getbasetemp()
    shared = base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base
    folder = shared / "english-references"
    folder.mkdir(exist_ok=True)
    return folder


def _reference_file(folder: Path, key: Tuple[int, str, str, str]) -> Path:
    return folder / ("-".join(str(part) for part in key) + ".json")


def _store_reference(
    folder: Path, key: Tuple[int, str, str, str], result: Dict[str, object]
) -> None:
    """Publish an English child's result to the other workers (atomically)."""
    target = _reference_file(folder, key)
    scratch = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    scratch.write_text(json.dumps(result), encoding="utf-8")
    os.replace(scratch, target)


def _run_child(
    tmp_path: Path,
    faces: Dict[str, str],
    language: str,
    scale: int,
    mode: str,
    surface: str,
    style: str,
) -> Dict[str, object]:
    """Run one matrix child and return its result."""
    from testing.suites.ui.test_app_font import run_child

    result = run_child(
        _CHILD.format(
            language=language,
            scale=scale,
            mode=mode,
            surface=surface,
            style=style,
            standin=faces["standin"],
            latin_only=faces["latin_only"],
        ),
        tmp_path,
        timeout=170,
    )
    assert result["families"] > 0, (
        "the child sees no platform font besides Nifen Art: "
        "there is nothing to compare with"
    )
    return result


def _english_reference(
    tmp_path: Path,
    faces: Dict[str, str],
    shared: Path,
    scale: int,
    mode: str,
    surface: str,
    style: str,
) -> Dict[str, object]:
    """Return the English child of this (scale, mode, surface, style).

    Run once per session when the workers get to share it (another worker's result
    is read from ``shared``), and at most once per worker otherwise. English is
    measured by the same child as any language, so the reference is exactly what an
    English item of that key would have measured.
    """
    key = (scale, mode, surface, style)
    if key not in _ENGLISH_REFERENCE:
        stored = _reference_file(shared, key)
        if stored.is_file():
            _ENGLISH_REFERENCE[key] = json.loads(stored.read_text(encoding="utf-8"))
        else:
            folder = tmp_path / "english-reference"
            folder.mkdir(exist_ok=True)
            _ENGLISH_REFERENCE[key] = _run_child(
                folder, faces, EN, scale, mode, surface, style
            )
            _store_reference(shared, key, _ENGLISH_REFERENCE[key])
    return _ENGLISH_REFERENCE[key]


def _measure(
    tmp_path: Path,
    capsys,
    faces: Dict[str, str],
    shared: Path,
    language: str,
    scale: int,
    mode: str,
    surface: str,
    style: str,
) -> None:
    """Run one item in a child and assert nothing is cut short, by either criterion."""
    folder = tmp_path / "item"
    folder.mkdir(exist_ok=True)
    result = _run_child(folder, faces, language, scale, mode, surface, style)
    if language == EN:
        key = (scale, mode, surface, style)
        if key not in _ENGLISH_REFERENCE:
            _ENGLISH_REFERENCE[key] = result
            _store_reference(shared, key, result)
        reference = None
    else:
        reference = _english_reference(
            tmp_path, faces, shared, scale, mode, surface, style
        )
    verdict = judge(language, result, reference)
    results = cast(Dict[str, Dict[str, Any]], result["results"])
    nifen = results["nifen"]
    system = results["system"]
    vertical = cast(Dict[str, Any], result["vertical"])
    total = sum(nifen["examined"].values())
    found = {c: len(f) for c, f in verdict.against_english.items()}
    both = {c: len(f) for c, f in verdict.english_too.items()}
    english = (
        ""
        if reference is None
        else "; against English (reference examined "
        f"{verdict.reference_examined}): findings {found}, truncated in English as "
        f"well {both}, no English counterpart {verdict.unmatched}"
    )
    _report(
        capsys,
        f"{surface} [{language} scale{scale} {mode} {style}]: "
        f"examined {total} with Nifen Art ({nifen['examined']}), "
        f"{sum(system['examined'].values())} with {result['platform']!r}; "
        f"truncated with Nifen Art only: {len(verdict.platform_only)}, with both: "
        f"{verdict.both_fonts}{english}; vertical ({verdict.vertical_source} chain "
        f"{vertical['chain']}): examined {verdict.vertical_examined}, "
        f"clipped {len(verdict.clipped)}; child seconds {result['timing']}",
    )
    if verdict.english_too:
        print(verdict.english_report())
    if surface == "dialogs":
        rows = prompt_rows(nifen["keys"])
        _report(
            capsys,
            f"prompt rows [{language} scale{scale} {mode} {style}]: "
            + "; ".join(f"{name} {kinds}" for name, kinds in rows.items()),
        )
        for name, buttons in PROMPT_BUTTONS.items():
            assert rows[name].get("button", 0) >= buttons, (
                f"{language}: the {name} row examined {rows[name]}, "
                f"fewer than {buttons} buttons"
            )
            assert rows[name].get("label", 0) >= 1, f"{name}: no message examined"
    assert total > (
        200 if surface == "main" else 100
    ), f"{style}: almost nothing examined"
    if surface == "main":
        assert nifen["examined"].get("docks", 0) > 20
        assert nifen["examined"].get("dock title", 0) > 20, "dock titles not measured"
    if reference is not None:
        assert verdict.reference_examined > 0, "the English reference examined nothing"
        lost = {
            case: {k: n for k, n in kinds.items() if k not in VIEWPORT_DEPENDENT_KINDS}
            for case, kinds in verdict.unmatched.items()
        }
        lost = {case: kinds for case, kinds in lost.items() if kinds}
        assert not lost, (
            f"{language}: texts examined in {language} with no English counterpart "
            f"cannot be judged, and are not compared by position: {lost}"
        )
    assert verdict.vertical_examined > 0, "the vertical check examined nothing"
    assert verdict.exit_status == 0, (
        f"{len(verdict.failures)} texts fail ({surface} {language} scale{scale} "
        f"{mode} {style}):\n" + verdict.report()
    )


#: The partition: one item per (language, scale, mode, surface, style).
def _discover_languages() -> Tuple[str, ...]:
    """Return the compiled languages the interface can switch to, English first."""
    from pixelart_creator.ui.i18n import LanguageManager

    manager = LanguageManager(cast(QCoreApplication, QCoreApplication.instance()))
    return tuple(manager.available_languages())


#: The discovered compiled languages (a ``pixelart_<code>.qm`` beside English).
LANGUAGES = _discover_languages()
MODES = ("light", "dark")
SURFACES = ("main", "dialogs")

#: The number of languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: Switch for the language-count floor. ``False`` holds it: the floor in force is 1,
#: so the zero-examined guard still bites, and every run prints ``HELD`` and how many
#: of the eight were discovered. The commit that compiles the eighth catalogue flips
#: it to ``True``.
EIGHT_LANGUAGE_FLOOR_ENFORCED = True


def active_language_floor() -> int:
    """Return the language-count floor in force: 8 once enforced, else 1."""
    return EXPECTED_LANGUAGE_COUNT if EIGHT_LANGUAGE_FLOOR_ENFORCED else 1


def _items() -> List[Tuple[str, int, str, str, str]]:
    """Return every (language, scale, mode, surface, style) item, in a fixed order.

    The language is the innermost axis, so the items that share an English
    reference sit next to each other and a worker that runs one has the other's
    reference already.
    """
    from pixelart_creator.data import style_catalog

    return [
        (language, scale, mode, surface, style)
        for scale, mode, surface, style in itertools.product(
            _SCALES, MODES, SURFACES, style_catalog.style_ids()
        )
        for language in LANGUAGES
    ]


ITEMS = _items()


@pytest.mark.parametrize(
    "language, scale, mode, surface, style",
    ITEMS,
    ids=[f"{la}-scale{sc}-{mo}-{su}-{st}" for la, sc, mo, su, st in ITEMS],
)
def test_nifen_art_truncates_nothing_the_platform_font_does_not(
    tmp_path,
    capsys,
    instrument_faces,
    reference_dir,
    language,
    scale,
    mode,
    surface,
    style,
):
    """Nothing in the main window or a dialog is cut short by the font or a translation.

    One item per compiled language, art scale (1, 2), mode (Light, Dark), surface
    (the main window with every dock raised, every dialog class built) and style.
    Two criteria judge it: Nifen Art against the platform font in one window, and
    (for every language but English) the language against English under the same
    font case, by widget identity. The examined counts, the number of texts
    truncated with Nifen Art only, with both fonts, and in English as well are
    printed for every item.
    """
    _measure(
        tmp_path,
        capsys,
        instrument_faces,
        reference_dir,
        language,
        scale,
        mode,
        surface,
        style,
    )


def _compiled_catalogue_languages() -> List[str]:
    """Return the languages with a compiled catalogue on disk, read independently."""
    return sorted(
        path.stem[len("pixelart_") :] for path in _I18N_DIR.glob("pixelart_*.qm")
    )


def test_the_items_cover_every_combination_exactly_once():
    """The partition: every (language, scale, mode, surface, style) is one item, once.

    The expected set is built here from the sources each axis comes from (the
    catalogue's style ids, the compiled catalogues found on disk, the two scales,
    the two modes, the two surfaces) and compared with the arguments the measuring
    test is actually parametrised with, read off the test function, so a
    combination dropped, duplicated or invented by the partition is reported by
    name. The cost is printed: how many items, and how many child processes they
    start. Because every item examines one style, three items of a (language,
    scale, mode, surface) together examine what one item of the earliest layout
    examined in its loop.
    """
    from pixelart_creator.data import style_catalog

    styles = style_catalog.style_ids()
    assert len(styles) == 3, f"the catalogue holds {len(styles)} styles, not 3"
    on_disk = _compiled_catalogue_languages()
    assert EN in on_disk, "English has no compiled catalogue"
    assert sorted(LANGUAGES) == on_disk, (
        f"the discovered languages {sorted(LANGUAGES)} are not the compiled "
        f"catalogues {on_disk}"
    )
    expected = Counter(
        (la, sc, mo, su, st)
        for la in on_disk
        for sc in (1, 2)
        for mo in ("light", "dark")
        for su in ("main", "dialogs")
        for st in styles
    )
    marks = [
        mark
        for mark in (
            test_nifen_art_truncates_nothing_the_platform_font_does_not.pytestmark
        )
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
    assert len(values) == len(on_disk) * 2 * 2 * 2 * len(styles)
    ids = marks[0].kwargs["ids"]
    assert len(set(ids)) == len(ids) == len(values), "item ids are not unique"
    # Selecting one language's items by "<code>-scale" must find that language's
    # items and no other's (a style or surface name must not contain it).
    for code in on_disk:
        picked = [item for item in ids if f"{code}-scale" in item]
        assert len(picked) == sum(1 for v in values if v[0] == code), code
    most = sum(1 if v[0] == EN else 2 for v in values)
    keys = len(values) // len(on_disk)
    full = 8 * keys
    print(
        f"[partition] {len(values)} items = {len(on_disk)} languages x 2 scales x "
        f"2 modes x 2 surfaces x {len(styles)} styles, between {len(values)} child "
        f"processes (every English child shared by the session's workers) and {most} "
        f"(none shared: an item of a language other than English also needs the "
        f"English child of its scale, mode, surface and style); at the finished "
        f"product's 8 languages: {full} items, between {full} and "
        f"{full + 7 * keys} children"
    )
    # The control: a partition that drops one combination is reported by name.
    short = actual.copy()
    dropped = next(iter(short))
    del short[dropped]
    assert expected - short == Counter({dropped: 1})


def test_the_eight_language_floor_is_written_and_held():
    """The floor of eight compiled languages is written here and held."""
    floor = active_language_floor()
    held = "ENFORCED" if EIGHT_LANGUAGE_FLOOR_ENFORCED else "HELD"
    print(
        f"[language floor] {held}: {len(LANGUAGES)} of {EXPECTED_LANGUAGE_COUNT} "
        f"languages discovered ({', '.join(LANGUAGES)}); floor in force: {floor}"
    )
    assert len(LANGUAGES) >= floor, (
        f"{len(LANGUAGES)} compiled languages discovered, the floor in force is "
        f"{floor}"
    )
    assert EN in LANGUAGES


def test_the_floor_is_one_while_held_and_eight_once_switched_on(monkeypatch):
    """Control: held, the floor is 1; switched on, it is 8 and three languages fail."""
    this = sys.modules[__name__]
    monkeypatch.setattr(this, "EIGHT_LANGUAGE_FLOOR_ENFORCED", False)
    assert active_language_floor() == 1
    monkeypatch.setattr(this, "EIGHT_LANGUAGE_FLOOR_ENFORCED", True)
    assert active_language_floor() == EXPECTED_LANGUAGE_COUNT == 8
    assert len(("en", "es", "ko")) < active_language_floor()


# --------------------------------------------------------------------------- #
# SC-L10N-UI-013-2: the check fails only on what the translation cut off       #
# --------------------------------------------------------------------------- #
#
# Each case plants one label inside the test, at art scale 1, in Nifen mode, on one
# surface (a host window) and one style. Its English source text and its French
# translation, planted in a scratch catalogue compiled for the purpose, are the
# only things that differ; the check that judges it is the same judge() the matrix
# uses, so the case asserts the check's verdict and not a copy of it.

#: case -> (English source text, planted French translation, how the label is sized)
PLANTED_CASES: Dict[str, Tuple[str, str, str]] = {
    # English fits its widget exactly; the French needs far more room.
    "fr-only": (
        "Save",
        "Enregistrer le projet sous un autre nom",
        "english-fits",
    ),
    # English already does not fit its widget (it gets half the width it needs),
    # and the French does not fit either.
    "fr-and-english": (
        "Save the project under another name today",
        "Enregistrer le projet sous un autre nom aujourd hui meme, sans faute",
        "english-squeezed",
    ),
    # Negative control: both fit, so the check must stay silent.
    "fits-in-both": ("Save", "Ok", "english-fits"),
}


def _lrelease() -> str:
    """Return the path of Qt's catalogue compiler, or fail naming where it looked."""
    found = shutil.which("pyside6-lrelease")
    if found:
        return found
    import PySide6

    folder = Path(PySide6.__file__).resolve().parent
    for candidate in (
        folder / "lrelease.exe",
        folder / "lrelease",
        folder / "Qt" / "libexec" / "lrelease",
    ):
        if candidate.is_file():
            return str(candidate)
    raise AssertionError(
        "pyside6-lrelease is not on PATH and PySide6 ships no lrelease in "
        f"{folder}: the planted catalogue cannot be compiled"
    )


def _plant_catalogue(
    folder: Path, source: str, translation: str, context: str = "Planted"
) -> Path:
    """Write and compile a scratch ``pixelart_fr.qm`` holding one planted message."""
    folder.mkdir(parents=True, exist_ok=True)
    ts = folder / "pixelart_fr.ts"
    ts.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
        '<TS version="2.1" language="fr_FR">\n<context>\n'
        f"    <name>{context}</name>\n    <message>\n"
        f"        <source>{source}</source>\n"
        f"        <translation>{translation}</translation>\n"
        "    </message>\n</context>\n</TS>\n",
        encoding="utf-8",
    )
    done = subprocess.run(
        [_lrelease(), str(ts), "-qm", str(folder / "pixelart_fr.qm")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (
        done.returncode == 0 and (folder / "pixelart_fr.qm").is_file()
    ), f"lrelease exited {done.returncode}: {done.stdout}{done.stderr}"
    return folder


class _PlantedHost(QWidget):
    """A host window with one planted label that retranslates on a language change."""

    def __init__(self, source: str) -> None:
        super().__init__()
        from PySide6.QtWidgets import QHBoxLayout

        self._source = source
        self.label = QLabel()
        self.label.setObjectName("planted_label")
        layout = QHBoxLayout(self)
        layout.addWidget(self.label)
        layout.addStretch(1)
        self.setFixedWidth(900)
        self._retranslate()

    def _retranslate(self) -> None:
        self.label.setText(QCoreApplication.translate("Planted", self._source))

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Re-translate the planted label when the language changes."""
        if event.type() == event.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


def run_planted(case: str, catalogue_dir: str) -> Dict[str, object]:
    """Measure one planted label in English, then in French; return both results.

    Called inside the child process. Art scale 1, Nifen mode, one style, the host
    window as the one surface, the same ``Examiner`` as the matrix.
    """
    from pixelart_creator.data import style_catalog
    from pixelart_creator.ui.i18n import LanguageManager

    source, _translation, sizing = PLANTED_CASES[case]
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    app_font.register_app_fonts()
    apply_theme(app, "light", style_catalog.style_ids()[0], scale=1)
    app_font.apply_interface_font(app, False)
    manager = LanguageManager(app, Path(catalogue_dir))
    host = _PlantedHost(source)
    host.show()
    QApplication.processEvents()
    hint = host.label.sizeHint().width()
    host.label.setFixedWidth(hint if sizing == "english-fits" else hint // 2)
    QApplication.processEvents()

    def measure() -> Dict[str, object]:
        _settle(host)
        examiner = Examiner()
        examiner.prefix = "planted"
        examiner.examine(host)
        return {"results": {"nifen": examiner.dump()}}

    english = measure()
    assert manager.set_language("fr") is True, "the planted catalogue did not load"
    QApplication.processEvents()
    french = measure()
    shown = host.label.text()
    manager.set_language(EN)
    return {"en": english, "fr": french, "french_text": shown}


_PLANTED_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_planted
out(**run_planted({case!r}, {folder!r}))
"""


def _run_planted_case(tmp_path: Path, case: str) -> Dict[str, object]:
    """Compile the case's scratch catalogue and measure the planted label in a child."""
    from testing.suites.ui.test_app_font import run_child

    source, translation, _sizing = PLANTED_CASES[case]
    folder = _plant_catalogue(tmp_path / "catalogue", source, translation)
    result = run_child(
        _PLANTED_CHILD.format(case=case, folder=str(folder)), tmp_path, timeout=120
    )
    assert result["french_text"] == translation, (
        "the planted translation was not applied: the label shows "
        f"{result['french_text']!r}"
    )
    return result


def test_a_label_truncated_in_french_only_fails_naming_label_widget_and_language(
    tmp_path, capsys
):
    """SC-L10N-UI-013-2 row "fr only": a finding, a non-zero exit, and its three names.

    The English source text fits its widget exactly. The French planted in the
    scratch catalogue does not. The check must report it and exit non-zero, naming
    the label, the widget and the language.
    """
    planted = _run_planted_case(tmp_path, "fr-only")
    verdict = judge("fr", planted["fr"], planted["en"])
    _report(capsys, f"planted fr-only: exit {verdict.exit_status}\n{verdict.report()}")
    assert verdict.examined["nifen"] == 1, "the planted label was not examined"
    assert verdict.exit_status != 0, "the check passed a label only French cuts off"
    report = verdict.report()
    assert "Enregistrer le projet sous un autre nom" in report, report
    assert "_PlantedHost/QLabel[planted_label]" in report, report
    assert "language fr" in report, report
    assert verdict.english_too["nifen"] == []


def test_a_label_truncated_in_french_and_in_english_passes_and_is_printed(
    tmp_path, capsys
):
    """SC-L10N-UI-013-2 row "fr and in English": exit zero, the label printed for fr.

    The English source text already does not fit its widget, and neither does the
    planted French. English is the reference: the label is not a finding. It is
    counted and printed among those truncated in English as well, for ``fr``.
    """
    planted = _run_planted_case(tmp_path, "fr-and-english")
    english = planted["en"]["results"]["nifen"]
    assert len(english["findings"]) == 1, "English must already truncate the label"
    verdict = judge("fr", planted["fr"], planted["en"])
    _report(
        capsys,
        f"planted fr-and-english: exit {verdict.exit_status}\n"
        f"{verdict.english_report()}",
    )
    assert verdict.examined["nifen"] == 1
    assert verdict.exit_status == 0, verdict.report()
    printed = verdict.english_report()
    assert "truncated in English as well, for fr" in printed, printed
    assert "Enregistrer le projet sous un autre nom" in printed, printed
    assert len(verdict.english_too["nifen"]) == 1


def test_a_comparison_that_judges_the_language_alone_fails_the_second_case(tmp_path):
    """The broken copy of the comparison, run against the second case, fails it.

    The correct comparison passes the "fr and in English" case; the copy that
    drops the English side and judges French alone exits non-zero on the same
    measurements. That proves the case tells the differential rule from the
    absolute one.
    """
    planted = _run_planted_case(tmp_path, "fr-and-english")
    right = judge("fr", planted["fr"], planted["en"])
    broken = judge("fr", planted["fr"], planted["en"], compare=judge_language_alone)
    assert right.exit_status == 0, right.report()
    assert broken.exit_status != 0, (
        "the copy that judges the language alone passed the case: the case cannot "
        "tell the differential rule from the absolute one"
    )
    assert "Enregistrer" in broken.report()


def test_a_label_that_fits_in_both_languages_passes_with_nothing_to_print(tmp_path):
    """Control (negative): a label that fits in English and French is not reported."""
    planted = _run_planted_case(tmp_path, "fits-in-both")
    verdict = judge("fr", planted["fr"], planted["en"])
    assert verdict.examined["nifen"] == 1
    assert verdict.exit_status == 0, verdict.report()
    assert verdict.english_too["nifen"] == [] and verdict.english_report() == ""


# --------------------------------------------------------------------------- #
# SC-L10N-UI-013-2 on a prompt row: the same planted cases, on a real prompt   #
# --------------------------------------------------------------------------- #
#
# The unsaved-changes prompt is opened by the interface's own handler in a window
# of its own. Its Discard button is the planted label: the French translation is
# planted in a scratch catalogue under the context the window's strings belong to,
# and the button is given a fixed width, so that English fits it (or does not) and
# the planted French does not. The judge is the same ``judge()`` the matrix uses.

#: case -> (English source text of the button, planted French translation, sizing)
PLANTED_PROMPT_CASES: Dict[str, Tuple[str, str, str]] = {
    "fr-only": (
        "Discard",
        "Abandonner les modifications et ouvrir quand même",
        "english-fits",
    ),
    "fr-and-english": (
        "Discard",
        "Abandonner les modifications et ouvrir quand même",
        "english-squeezed",
    ),
    "fits-in-both": ("Discard", "Ok", "english-fits"),
}


def run_planted_prompt(case: str, catalogue_dir: str) -> Dict[str, object]:
    """Measure the planted Discard button in English, then in French.

    Called inside the child process. Art scale 1, Light, one style, the prompt row
    "Unsaved_Changes_Prompt" as the one surface, the same ``Examiner`` as the matrix.
    The width the English button is given in the first measurement is the width the
    French button is given in the second.
    """
    from pixelart_creator.data import style_catalog
    from pixelart_creator.ui.appearance_settings import KEY_MODE
    from pixelart_creator.ui.i18n import LanguageManager
    from pixelart_creator.ui.main_window import Main_Window
    from testing.suites.ui.test_app_font import plant

    _source, _translation, sizing = PLANTED_PROMPT_CASES[case]
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    app_font.register_app_fonts()
    plant(**{KEY_MODE: "light"})
    win = Main_Window()
    win.resize(1280, 800)
    win.show()
    QApplication.processEvents()
    apply_theme(app, "light", style_catalog.style_ids()[0], scale=1)
    app_font.apply_interface_font(app, False)
    manager = LanguageManager(app, Path(catalogue_dir))
    given: Dict[str, int] = {}
    shown: Dict[str, str] = {}

    def discard_of(box: QMessageBox) -> QAbstractButton:
        role = QMessageBox.ButtonRole.DestructiveRole
        return next(b for b in box.buttons() if box.buttonRole(b) == role)

    def give_width(box: QMessageBox) -> None:
        button = discard_of(box)
        if "width" not in given:
            hint = button.sizeHint().width()
            given["width"] = hint if sizing == "english-fits" else hint // 2
        button.setFixedWidth(given["width"])
        shown["text"] = button.text()

    def measure() -> Dict[str, object]:
        examiner = Examiner()
        examine_prompt(win, "Unsaved_Changes_Prompt", examiner, tweak=give_width)
        return {"results": {"nifen": examiner.dump()}}

    english = measure()
    assert manager.set_language("fr") is True, "the planted catalogue did not load"
    QApplication.processEvents()
    french = measure()
    manager.set_language(EN)
    return {"en": english, "fr": french, "french_text": shown["text"]}


_PLANTED_PROMPT_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_planted_prompt
out(**run_planted_prompt({case!r}, {folder!r}))
"""


def _run_planted_prompt_case(tmp_path: Path, case: str) -> Dict[str, object]:
    """Compile the case's scratch catalogue and measure the prompt in a child."""
    from testing.suites.ui.test_app_font import run_child

    source, translation, _sizing = PLANTED_PROMPT_CASES[case]
    folder = _plant_catalogue(
        tmp_path / "catalogue", source, translation, context="Main_Window"
    )
    result = run_child(
        _PLANTED_PROMPT_CHILD.format(case=case, folder=str(folder)),
        tmp_path,
        timeout=150,
    )
    assert result["french_text"] == translation, (
        "the planted translation was not applied: the button shows "
        f"{result['french_text']!r}"
    )
    return result


def test_a_prompt_button_truncated_in_french_only_fails_naming_label_widget_language(
    tmp_path, capsys
):
    """SC-L10N-UI-013-2 on a prompt: a button only French cuts off is a finding.

    The unsaved-changes prompt is opened by the interface's own handler. English
    fits the Discard button's width, the planted French does not: a non-zero exit
    naming the button's text, its widget and the language.
    """
    planted = _run_planted_prompt_case(tmp_path, "fr-only")
    verdict = judge("fr", planted["fr"], planted["en"])
    _report(
        capsys,
        f"planted prompt fr-only: examined {verdict.examined['nifen']}, "
        f"exit {verdict.exit_status}\n{verdict.report()}",
    )
    assert verdict.examined["nifen"] >= 4, "the prompt's texts were not examined"
    assert verdict.exit_status != 0, "the check passed a button only French cuts off"
    report = verdict.report()
    assert "Abandonner les modifications et ouvrir quand même" in report, report
    assert "QMessageBox/QPushButton[]" in report, report
    assert "language fr" in report, report
    assert verdict.english_too["nifen"] == []


def test_a_prompt_button_truncated_in_french_and_in_english_passes_and_is_printed(
    tmp_path, capsys
):
    """SC-L10N-UI-013-2 on a prompt: a button English cuts off too is printed.

    The Discard button is given half the width English needs, so English cuts it
    off and so does the planted French. It is not a finding; it is counted and
    printed among those truncated in English as well, for ``fr``.
    """
    planted = _run_planted_prompt_case(tmp_path, "fr-and-english")
    english = planted["en"]["results"]["nifen"]
    assert len(english["findings"]) == 1, "English must already cut the button off"
    verdict = judge("fr", planted["fr"], planted["en"])
    _report(
        capsys,
        f"planted prompt fr-and-english: exit {verdict.exit_status}\n"
        f"{verdict.english_report()}",
    )
    assert verdict.exit_status == 0, verdict.report()
    printed = verdict.english_report()
    assert "truncated in English as well, for fr" in printed, printed
    assert "Abandonner les modifications et ouvrir quand même" in printed, printed
    assert len(verdict.english_too["nifen"]) == 1


def test_a_prompt_button_that_fits_in_both_languages_is_not_reported(tmp_path):
    """Control (negative): a Discard button that fits in both languages is silent."""
    planted = _run_planted_prompt_case(tmp_path, "fits-in-both")
    verdict = judge("fr", planted["fr"], planted["en"])
    assert verdict.examined["nifen"] >= 4
    assert verdict.exit_status == 0, verdict.report()
    assert verdict.english_too["nifen"] == [] and verdict.english_report() == ""


# --------------------------------------------------------------------------- #
# The vertical check's own control                                             #
# --------------------------------------------------------------------------- #


def run_vertical_control(standin: str, latin_only: str) -> Dict[str, object]:
    """Plant widgets one pixel too short and just tall enough; return what is reported.

    Called inside the child process, with the stand-in as the platform font. For
    each class (a label, a button) one widget is given a fixed height equal to the
    height of its text in the platform font, and one a fixed height one pixel
    less.
    """
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    register_instruments(standin, latin_only)
    plugin = positive_control()
    han_capable_platform(app, EN)
    font = standin_font()
    height = QFontMetrics(font).boundingRect("Hello").height()
    out: Dict[str, object] = {"plugin": plugin, "text_height": height}
    for label, short in (("exact", 0), ("short", 1)):
        host = QWidget()
        layout = QVBoxLayout(host)
        planted_label = QLabel("Hello")
        planted_label.setObjectName("planted_label")
        planted_label.setFixedHeight(height - short)
        planted_button = QPushButton("Hello")
        planted_button.setObjectName("planted_button")
        planted_button.setFixedHeight(height - short)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(planted_label)
        layout.addWidget(planted_button)
        host.setFixedWidth(300)
        host.show()
        QApplication.processEvents()
        examiner = Examiner(vfont=font)
        examiner.prefix = "planted"
        examiner.examine(host)
        out[label] = examiner.dump()["vertical"]
        host.close()
    return out


_VERTICAL_CONTROL_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_vertical_control
out(**run_vertical_control({standin!r}, {latin_only!r}))
"""


def test_the_vertical_check_fails_a_widget_one_pixel_too_short_and_passes_one_that_fits(
    tmp_path, instrument_faces
):
    """Control: a label and a button one pixel short are reported; exact ones are not.

    The text height is the one the platform font (the registered Han-capable
    stand-in, 13 px above the baseline and 3 below) gives the text. The widgets
    are planted with a fixed height of that height and of one pixel less.
    """
    from testing.suites.ui.test_app_font import run_child

    result = run_child(
        _VERTICAL_CONTROL_CHILD.format(
            standin=instrument_faces["standin"],
            latin_only=instrument_faces["latin_only"],
        ),
        tmp_path,
        timeout=120,
        fonts=False,
    )
    height = result["text_height"]
    assert height == _STANDIN_ASCENT_PX + _STANDIN_DESCENT_PX, height
    exact, short = result["exact"], result["short"]
    assert sum(exact["examined"].values()) == 2, exact
    assert sum(short["examined"].values()) == 2, short
    assert exact["findings"] == [], exact["findings"]
    kinds = sorted(f[0] for f in short["findings"])
    assert kinds == ["button", "label"], short["findings"]
    for row in short["findings"]:
        assert (row[3], row[4]) == (height, height - 1), row


# The vertical check measures each text in the family that DRAWS it. A CJK face has
# a shorter line box (11 above, 3 below, 14 in all) than the platform stand-in
# (13 and 3, 16 in all), so a label made only of characters a CJK face holds is
# laid out 14 px high and must be judged at 14, not at the stand-in's 16. Three
# controls keep that from becoming a way to excuse real clipping:
#
# * a label drawn wholly by the CJK face, one pixel below that face's line box,
#   is reported (a check that never fails proves nothing);
# * a label with a Latin letter or a space among the CJK characters is still
#   judged at the stand-in's 16, and so is a link label whose DISPLAYED text is
#   Latin even though its markup is not;
# * the measure this check had before (the stand-in alone, on the raw text) is run
#   on the same exact-fit label and must report it, so a check that fell back to
#   it is caught by the first control.
#
# The families are the shipped faces and the characters are read from each face's
# own cmap, so the control follows the coverage: Korean today, Japanese and Chinese
# on the characters their faces already hold, and every Han the faces gain later.

_CJK_FACE_FILES = {
    "ko": "NifenArtCJKKR-Regular.ttf",
    "ja": "NifenArtCJKJP-Regular.ttf",
    "zh_CN": "NifenArtCJKSC-Regular.ttf",
}
_LINK = '<a href="https://example.org/a/path?x=1">{}</a>'


def _face_facts(file_name: str) -> Tuple[str, int, str]:
    """Return a shipped CJK face's family, line box in px and three characters.

    Read from the file with fontTools, not from Qt: the line box is the font's
    ascent minus descent in em units (the descent is negative), scaled to the
    interface's pixel em.
    """
    fonts = Path(ui_package.__file__).resolve().parent.parent / "fonts"
    face = TTFont(str(fonts / file_name))
    units_per_px = cast(Any, face["head"]).unitsPerEm / app_font.NIFEN_ART_EM_PX
    hhea = face["hhea"]
    line_box = (hhea.ascent - hhea.descent) / units_per_px
    assert line_box == int(line_box), (file_name, line_box)
    letters = "".join(
        chr(cp)
        for cp in sorted(cast(Dict[int, str], face.getBestCmap()))
        if cp >= 0x3400
    )[:3]
    assert len(letters) == 3, f"{file_name} holds fewer than three characters"
    return cast(str, face["name"].getDebugName(1)), int(line_box), letters


class _PlatformFontAloneExaminer(Examiner):
    """The broken copy: the measure this check had before it followed the family.

    The height needed is the stand-in's line box for any text, measured on the raw
    text of the widget with its markup.
    """

    def _vertical(
        self, kind: str, key: str, widget: QWidget, text: str, given: int
    ) -> None:
        assert self.vfont is not None
        if "\n" in text or given <= 0:
            self.vskipped[kind] += 1
            return
        self.vexamined[kind] += 1
        need = QFontMetrics(self.vfont).boundingRect(text).height()
        if need > given:
            self.vfindings.append(
                Finding(kind, self._where(widget), text.strip()[:60], need, given, key)
            )


def run_vertical_script_control(
    standin: str, latin_only: str, language: str, face_file: str
) -> Dict[str, object]:
    """Plant labels and buttons at, and one pixel below, the height their text needs.

    Called inside the child process, with the stand-in as the platform font and
    ``language`` the active interface language, made so through the product's own
    language manager. The Han form of the application font follows the active
    language (REQ-L10N-UI-012), so the chain measured is the one the product builds
    for it, and a product that gave the wrong form for ``language`` fails the
    premise below.
    Every plant is measured by the real examiner; the ones that fit are measured
    by the broken copy as well.
    """
    from pixelart_creator.ui import i18n

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    register_instruments(standin, latin_only)
    plugin = positive_control()
    manager = i18n.LanguageManager(app)
    assert manager.set_language(language) is True, f"no {language!r} catalogue"
    assert i18n.current_ui_language() == language, (
        f"the interface language is {i18n.current_ui_language()!r}, "
        f"not {language!r}"
    )
    chained = han_capable_platform(app, language)
    assert chained["source"] == "product", (
        f"the application font carries {chained['chain']!r}: the product put no "
        "family list on it, so nothing of the product was measured"
    )
    family, face_box, pure = _face_facts(face_file)
    # The premise of every case: the pure text really is drawn by the CJK face, and
    # a Latin letter and a space really are not. A control whose premise does not
    # hold would prove nothing, so it stops here.
    for letter in pure:
        drew = drawing_family(app.font(), ord(letter))
        assert drew == family, f"{letter!r} is drawn by {drew!r}, not by {family!r}"
    for other in "A ":
        drew = drawing_family(app.font(), ord(other))
        assert drew == STANDIN_FAMILY, f"{other!r} is drawn by {drew!r}"
    standin_box = QFontMetrics(standin_font()).boundingRect("Hello").height()
    # (name, widget classes, text, the height the text needs, the text displayed)
    cases = [
        ("pure", (QLabel, QPushButton), pure, face_box, pure),
        ("mixed", (QLabel, QPushButton), f"{pure} A", standin_box, f"{pure} A"),
        ("pure link", (QLabel,), _LINK.format(pure), face_box, pure),
        ("latin link", (QLabel,), _LINK.format("Docs"), standin_box, "Docs"),
    ]
    results: Dict[str, Dict[str, object]] = {}
    for name, classes, text, needed, displayed in cases:
        entry: Dict[str, object] = {
            "needs": needed,
            "displayed": displayed,
            "widgets": len(classes),
        }
        for variant, short, examiner_class in (
            ("exact", 0, Examiner),
            ("short", 1, Examiner),
            ("exact, broken copy", 0, _PlatformFontAloneExaminer),
        ):
            host = QWidget()
            layout = QVBoxLayout(host)
            layout.setContentsMargins(0, 0, 0, 0)
            for widget_class in classes:
                planted = widget_class(text)
                planted.setObjectName("planted")
                planted.setFixedHeight(needed - short)
                layout.addWidget(planted)
            host.setFixedWidth(300)
            host.show()
            QApplication.processEvents()
            examiner = examiner_class(vfont=standin_font())
            examiner.prefix = "planted"
            examiner.examine(host)
            entry[variant] = examiner.dump()["vertical"]
            host.close()
        results[name] = entry
    return {
        "plugin": plugin,
        "family": family,
        "face_box": face_box,
        "standin_box": standin_box,
        "pure": pure,
        "cases": results,
    }


_VERTICAL_SCRIPT_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_vertical_script_control
out(**run_vertical_script_control({standin!r}, {latin_only!r}, {language!r}, {face!r}))
"""


@pytest.mark.parametrize("language", sorted(_CJK_FACE_FILES))
def test_the_vertical_check_judges_a_text_by_the_family_that_draws_it(
    tmp_path, instrument_faces, language, capsys
):
    """Control: a text wholly in a CJK face is judged at that face's line box, no lower.

    Korean, Japanese and Chinese, each on the characters its shipped face holds. A
    label of those characters fits at the face's line box (14) and is reported one
    pixel below it (13): the check still catches real clipping of CJK text. A label
    with a Latin letter and a space among them, and a link label whose displayed
    text is Latin, are judged at the stand-in's 16; a link label whose displayed
    text is CJK is judged by that text, not by the Latin URL in its markup. The
    measure the check used before (the stand-in alone, on the raw text) reports
    the labels that fit.
    """
    from testing.suites.ui.test_app_font import run_child

    result = run_child(
        _VERTICAL_SCRIPT_CHILD.format(
            standin=instrument_faces["standin"],
            latin_only=instrument_faces["latin_only"],
            language=language,
            face=_CJK_FACE_FILES[language],
        ),
        tmp_path,
        timeout=120,
        fonts=False,
    )
    face_box, standin_box = result["face_box"], result["standin_box"]
    _report(
        capsys,
        f"[vertical control {language}] {result['family']}: line box {face_box} px; "
        f"stand-in line box {standin_box} px; characters {result['pure']!r}",
    )
    assert standin_box == _STANDIN_ASCENT_PX + _STANDIN_DESCENT_PX, standin_box
    assert face_box < standin_box, (face_box, standin_box)
    for name, case in result["cases"].items():
        needs, widgets = case["needs"], case["widgets"]
        for variant in ("exact", "short", "exact, broken copy"):
            assert sum(case[variant]["examined"].values()) == widgets, (name, case)
        assert case["exact"]["findings"] == [], (name, case["exact"]["findings"])
        short = case["short"]["findings"]
        assert len(short) == widgets, (name, short)
        for row in short:
            assert (row[3], row[4]) == (needs, needs - 1), (name, row)
            assert row[2] == case["displayed"].strip(), (name, row)
            assert "href" not in row[2], (name, row)
    pure_broken = result["cases"]["pure"]["exact, broken copy"]["findings"]
    link_broken = result["cases"]["pure link"]["exact, broken copy"]["findings"]
    assert len(pure_broken) == 2, pure_broken
    assert len(link_broken) == 1 and "href" in link_broken[0][2], link_broken
    for name in ("mixed", "latin link"):
        assert result["cases"][name]["exact, broken copy"]["findings"] == [], name


# --------------------------------------------------------------------------- #
# The user guide's page: a line is as tall as the glyphs drawn on it           #
# --------------------------------------------------------------------------- #
#
# With "Use system font" on and a Han-capable platform family (the stand-in), the
# guide's page text, whose default font is the platform font, takes whatever the
# application gives the platform font. Whether QTextDocument takes a line's height
# from the first family of the list or from the family that draws the glyphs is
# not assumed: the outcome is measured. For every line of the first blocks of one
# rendered topic, the line height is not smaller than the tallest glyph drawn on
# the line (read from the glyph's own outline), and no two consecutive lines'
# glyph boxes overlap.

GUIDE_TOPIC = "app-basics"
GUIDE_FIRST_BLOCKS = 12
_EPSILON = 1e-6


def measure_lines(
    document: QTextDocument, first_blocks: int = GUIDE_FIRST_BLOCKS
) -> List[Dict[str, float]]:
    """Return, per line of the first text blocks, its height and its glyph boxes.

    Each row holds the line's ``height``, the ``top`` and ``bottom`` of its glyph
    boxes in document coordinates and the ``tallest`` glyph's height. Glyph boxes
    come from the outlines (``QRawFont.pathForGlyph``), whose bounds are exact, and
    are aggregated over all runs of the line (a maximum and a union, which do not
    depend on the order the runs come back in). A line with no glyph (an inline
    image) is not returned.
    """
    layout = document.documentLayout()
    rows: List[Dict[str, float]] = []
    block = document.begin()
    taken = 0
    while block.isValid() and taken < first_blocks:
        text_layout = block.layout()
        if text_layout is not None and text_layout.lineCount() > 0:
            taken += 1
            origin = layout.blockBoundingRect(block).top()
            for index in range(text_layout.lineCount()):
                line = text_layout.lineAt(index)
                tops: List[float] = []
                bottoms: List[float] = []
                tallest = 0.0
                for run in line.glyphRuns():
                    raw = run.rawFont()
                    for glyph, position in zip(run.glyphIndexes(), run.positions()):
                        box = raw.pathForGlyph(glyph).boundingRect()
                        if box.height() <= 0:
                            continue
                        tops.append(origin + position.y() + box.top())
                        bottoms.append(origin + position.y() + box.bottom())
                        tallest = max(tallest, box.height())
                if tops:
                    rows.append(
                        {
                            "block": taken,
                            "line": index,
                            "height": line.height(),
                            "top": min(tops),
                            "bottom": max(bottoms),
                            "tallest": tallest,
                        }
                    )
        block = block.next()
    return rows


def line_problems(rows: Sequence[Dict[str, float]]) -> List[str]:
    """Return every line shorter than its tallest glyph and every neighbour overlap."""
    problems: List[str] = []
    for row in rows:
        if row["height"] + _EPSILON < row["tallest"]:
            problems.append(
                f"block {row['block']} line {row['line']}: line height "
                f"{row['height']} is smaller than the tallest glyph drawn on it "
                f"({row['tallest']})"
            )
    for above, below in zip(rows, rows[1:]):
        if above["bottom"] > below["top"] + _EPSILON:
            problems.append(
                f"block {above['block']} line {above['line']} and the next line: "
                f"glyph boxes overlap by {above['bottom'] - below['top']:.1f}"
            )
    return problems


def _planted_document(line_height: Optional[float]) -> QTextDocument:
    """Return a multi-line paragraph in the stand-in, optionally at a fixed height."""
    document = QTextDocument()
    document.setDefaultFont(standin_font())
    document.setPlainText("one two three four five six seven eight nine ten eleven")
    document.setTextWidth(110)
    if line_height is not None:
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(
            line_height, QTextBlockFormat.LineHeightTypes.FixedHeight.value
        )
        cursor.setBlockFormat(block_format)
    document.documentLayout().documentSize()
    return document


def run_guide(language: str, standin: str, latin_only: str) -> Dict[str, object]:
    """Lay out one guide topic with the Han-capable platform font; return the measure.

    Called inside the child process. The planted controls (a line height of the
    tallest glyph, and one pixel less) run first, in the same process.
    """
    from pixelart_creator.data import guide_content
    from pixelart_creator.ui.user_guide import User_Guide_Dialog

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    register_instruments(standin, latin_only)
    plugin = positive_control()
    platform = han_capable_platform(app, language)
    natural = measure_lines(_planted_document(None))
    tallest = max(row["tallest"] for row in natural)
    exact_rows = measure_lines(_planted_document(tallest))
    short_rows = measure_lines(_planted_document(tallest - 1))
    dialog = User_Guide_Dialog(None, locale_provider=lambda: language)
    dialog.resize(900, 700)
    dialog.show()
    QApplication.processEvents()
    dialog.show_topic(GUIDE_TOPIC)
    QApplication.processEvents()
    assert dialog.current_topic_id() == GUIDE_TOPIC
    document = dialog._content_view.document()
    rows = measure_lines(document)
    probes = {
        "latin A": drawing_family(document.defaultFont(), 0x41),
        "hangul": drawing_family(document.defaultFont(), 0xD55C),
        "han": drawing_family(document.defaultFont(), 0x5B57),
    }
    return {
        "plugin": plugin,
        "platform": platform,
        "page_font": list(document.defaultFont().families())
        or [document.defaultFont().family()],
        "content_languages": sorted(guide_content.available_locales()),
        "rows": rows,
        "problems": line_problems(rows),
        "probes": probes,
        "control_exact": {
            "tallest": tallest,
            "rows": len(exact_rows),
            "problems": line_problems(exact_rows),
        },
        "control_short": {
            "rows": len(short_rows),
            "problems": line_problems(short_rows),
        },
    }


_GUIDE_CHILD = """
from testing.suites.ui.test_app_font_truncation import run_guide
out(**run_guide({language!r}, {standin!r}, {latin_only!r}))
"""


@pytest.mark.parametrize("language", LANGUAGES, ids=list(LANGUAGES))
def test_guide_page_lines_are_as_tall_as_the_glyphs_drawn_on_them(
    tmp_path, capsys, instrument_faces, language
):
    """The guide's page text, in the platform font, is not clipped or overlapped.

    With the Han-capable stand-in as the platform family, one topic of the guide is
    laid out; for every line of its first blocks the line height is not smaller than
    the tallest glyph drawn on that line, and no two consecutive lines' glyph boxes
    overlap. The lines examined are printed per language and zero fails. The planted
    controls run in the same process: a fixed line height of the tallest glyph passes,
    and one pixel less fails (as a short line and as an overlap).
    """
    from testing.suites.ui.test_app_font import run_child

    result = run_child(
        _GUIDE_CHILD.format(
            language=language,
            standin=instrument_faces["standin"],
            latin_only=instrument_faces["latin_only"],
        ),
        tmp_path,
        timeout=120,
        fonts=False,
    )
    rows = result["rows"]
    page = (
        f"English page (no {language} tree yet)"
        if language not in result["content_languages"]
        else f"page in {language}"
    )
    first = rows[0] if rows else {}
    _report(
        capsys,
        f"guide [{language}]: {len(rows)} lines examined over the first "
        f"{GUIDE_FIRST_BLOCKS} blocks of {GUIDE_TOPIC!r} ({page}); platform font "
        f"{result['platform']['source']}, page font {result['page_font']}; drawn "
        f"by {result['probes']}; first line height {first.get('height')}, tallest "
        f"glyph {first.get('tallest')}; control exact: "
        f"{result['control_exact']['rows']} lines, "
        f"{len(result['control_exact']['problems'])} problems; control one pixel "
        f"short: {result['control_short']['rows']} lines, "
        f"{len(result['control_short']['problems'])} problems",
    )
    control_exact, control_short = result["control_exact"], result["control_short"]
    assert control_exact["rows"] >= 3 and control_exact["problems"] == [], control_exact
    assert control_short["problems"], (
        "a planted line height one pixel short was not reported: the line check "
        f"cannot fail ({control_short})"
    )
    assert result["probes"]["latin A"] == STANDIN_FAMILY, (
        "the Latin text is not drawn by the platform stand-in, so the check does "
        f"not see the platform font's glyphs: {result['probes']}"
    )
    assert rows, f"{language}: no guide line was examined"
    assert not result["problems"], f"{language}: " + "; ".join(result["problems"][:10])
