# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""In-app User Guide viewer (REQ-UG-UI-003..011; ADR-0029).

``User_Guide_Dialog`` is the navigable, **read-only**, fully **offline** guide
surface: a table-of-contents :class:`QTreeWidget` (sections → topics, built from
the pure :class:`~pixelart_creator.logic.guide_model.GuideModel`), a
:class:`QTextBrowser` content pane that renders the bundled Markdown via
``setMarkdown`` (never executed — Article VII), and a search
:class:`QLineEdit` driving the pure
:func:`~pixelart_creator.logic.guide_search.query` with a results list that jumps
to a topic.

Layer boundary (Article I / S11): this widget is presentation only. It **binds to
the logic/data abstractions** — it calls
:func:`~pixelart_creator.data.guide_content.load_manifest` /
:func:`~pixelart_creator.data.guide_content.read_content` (the defensive reader)
and :func:`~pixelart_creator.logic.guide_model.build_model` /
:func:`~pixelart_creator.logic.guide_model.resolve_content_ref` /
:func:`~pixelart_creator.logic.guide_search.query`. It **hard-codes no ToC**, does
**no filesystem access of its own**, implements **no search matching**, and does
**no colour maths**. The reader/model are injectable for headless tests.

Content safety (REQ-UG-UI-005/-007): external links are disabled
(``setOpenExternalLinks(False)`` / ``setOpenLinks(False)``) and every clicked
anchor is resolved **within the guide** (to another topic) — no network fetch, no
filesystem read. A content-load error surfaces a user-facing message, never a
crash. Content is localised via the model's locale resolution (the active UI
locale is requested from an injected provider) with fallback to the default
locale (REQ-UG-UI-011 / CL-3); the **chrome** strings are ``tr()``-wrapped and
re-set on :data:`QEvent.Type.LanguageChange` (Article V / F5).

Teardown: content loading is **synchronous** from the committed bundle — this
widget introduces **NO** off-thread worker, timer, or network client, so it needs
no ``shutdown_*``/``closeEvent`` wiring. It is an ordinary disposable
:class:`QDialog` (parented to the main window when opened from the menu, so it is
disposed with its parent; AGT-06 also registers it in the UI drain fixture).
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.guide_content import (
    GuideContentError,
    available_locales,
    load_manifest,
    read_content,
)
from pixelart_creator.logic.guide_model import (
    DEFAULT_GUIDE_LOCALE,
    GuideModel,
    GuideModelError,
    build_model,
    resolve_content_ref,
)
from pixelart_creator.logic.guide_search import query

#: Qt roles that would resolve an anchor to the network or the local filesystem;
#: the viewer is fully offline (REQ-UG-UI-007), so a click on such a link is a
#: no-op — it is never fetched.
_EXTERNAL_SCHEMES = frozenset({"http", "https", "ftp", "ftps", "file", "mailto"})

#: The UserRole slot carrying a topic id on a ToC / results item.
_TOPIC_ID_ROLE = Qt.ItemDataRole.UserRole

#: A reader callable: a bundle-relative content ref -> the Markdown text. Defaults
#: to the defensive ``data`` reader; injectable so headless tests can substitute a
#: fixture reader without touching the real bundle.
Reader = Callable[[str], str]

#: A locale provider: returns the active UI locale code (e.g. ``"en"``). Defaults
#: to the guide's default locale; the main window passes the LanguageManager's
#: ``current_language`` so content follows the UI language (REQ-UG-UI-011 / CL-3).
LocaleProvider = Callable[[], str]


class User_Guide_Dialog(QDialog):
    """The navigable in-app User Guide (ToC tree + content pane + search)."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        model: Optional[GuideModel] = None,
        reader: Optional[Reader] = None,
        content_locales: Optional[Iterable[str]] = None,
        locale_provider: Optional[LocaleProvider] = None,
    ) -> None:
        """Build the guide window and populate the ToC from the content model.

        Args:
            parent: Optional Qt parent (the main window when opened from Help).
            model: A pre-built model (tests inject a fixture model). When ``None``
                the model is built from the committed bundle via
                :func:`load_manifest` + :func:`build_model`; a malformed/missing
                bundle degrades to an on-screen error message, never a crash.
            reader: The content reader (ref -> Markdown text). Defaults to the
                defensive :func:`read_content`.
            content_locales: The locale codes with bundled content (drives locale
                resolution). Defaults to the bundle's :func:`available_locales`.
            locale_provider: Returns the active UI locale code. Defaults to the
                guide default locale.
        """
        super().__init__(parent)
        self._reader: Reader = reader if reader is not None else read_content
        self._locale_provider: LocaleProvider = (
            locale_provider
            if locale_provider is not None
            else (lambda: DEFAULT_GUIDE_LOCALE)
        )
        # topic_id -> its ToC tree item, so a search jump / anchor click can select
        # the matching ToC entry (built once from the model).
        self._toc_items: Dict[str, QTreeWidgetItem] = {}
        self._current_topic_id: Optional[str] = None
        # Guards the currentItemChanged <-> show_topic feedback loop.
        self._suppress_nav = False

        self._model, self._content_locales, self._load_error = self._resolve_model(
            model, content_locales
        )

        self._build_ui()
        self._populate_toc()
        self._retranslate()
        # Select the first topic (or show the load error) once the tree is built.
        self._show_initial()

    # -- construction helpers --------------------------------------------

    @staticmethod
    def _resolve_model(
        model: Optional[GuideModel],
        content_locales: Optional[Iterable[str]],
    ) -> tuple[Optional[GuideModel], frozenset[str], Optional[str]]:
        """Return ``(model, content_locales, error)`` — building from the bundle.

        A missing/malformed bundle is caught and reported as an error string (shown
        in the content pane), so opening the guide never raises (REQ-UG-UI-005).
        """
        if model is not None:
            locales = (
                frozenset(content_locales)
                if content_locales is not None
                else frozenset({DEFAULT_GUIDE_LOCALE})
            )
            return model, locales, None
        try:
            built = build_model(load_manifest())
            locales = (
                frozenset(content_locales)
                if content_locales is not None
                else available_locales()
            )
            return built, locales, None
        except (GuideContentError, GuideModelError) as exc:
            return None, frozenset(), str(exc)

    def _build_ui(self) -> None:
        """Assemble the search box, ToC/results stack, and content pane."""
        self._search_edit = QLineEdit(self)
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search)

        self._toc_tree = QTreeWidget(self)
        self._toc_tree.setHeaderHidden(True)
        self._toc_tree.setColumnCount(1)
        self._toc_tree.currentItemChanged.connect(self._on_toc_current_changed)

        self._results_list = QListWidget(self)
        self._results_list.currentItemChanged.connect(self._on_result_current_changed)

        # The left pane swaps between the ToC (empty search) and the search results.
        self._left_stack = QStackedWidget(self)
        self._left_stack.addWidget(self._toc_tree)
        self._left_stack.addWidget(self._results_list)
        self._left_stack.setCurrentWidget(self._toc_tree)

        left_container = QWidget(self)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._left_stack, 1)

        self._content_view = QTextBrowser(self)
        # Fully offline + safe: never open a link externally or read the filesystem;
        # anchor clicks are routed to _on_anchor_clicked and resolved in-guide only.
        self._content_view.setOpenExternalLinks(False)
        self._content_view.setOpenLinks(False)
        self._content_view.setSearchPaths([])
        self._content_view.anchorClicked.connect(self._on_anchor_clicked)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(left_container)
        self._splitter.addWidget(self._content_view)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._splitter)

        # Logical focus order (a11y, REQ-UG-UI-009): search -> ToC -> content.
        self.setTabOrder(self._search_edit, self._toc_tree)
        self.setTabOrder(self._toc_tree, self._content_view)
        self._search_edit.setFocus()

    def _populate_toc(self) -> None:
        """Fill the ToC tree from the model's ordered sections → topics.

        Section/topic titles come from the content model (authored data, localised
        via the manifest), not ``tr()`` — only the surrounding chrome is translated.
        """
        self._toc_tree.clear()
        self._toc_items.clear()
        if self._model is None:
            return
        for section in self._model.sections:
            section_item = QTreeWidgetItem([section.title])
            # Sections are not selectable targets (no topic id) but stay expandable.
            self._toc_tree.addTopLevelItem(section_item)
            for topic in section.topics:
                topic_item = QTreeWidgetItem([topic.title])
                topic_item.setData(0, _TOPIC_ID_ROLE, topic.id)
                section_item.addChild(topic_item)
                self._toc_items[topic.id] = topic_item
        self._toc_tree.expandAll()

    def _show_initial(self) -> None:
        """Render the first topic, or the load-error message if the bundle failed."""
        if self._model is None:
            self._show_load_error()
            return
        topics = self._model.topics()
        if topics:
            self.show_topic(topics[0].id)

    # -- public API -------------------------------------------------------

    def show_topic(self, topic_id: str) -> None:
        """Navigate the ToC + content pane to ``topic_id`` (no-op if unknown)."""
        if self._model is None:
            return
        try:
            topic = self._model.topic(topic_id)
        except GuideModelError:
            return
        self._current_topic_id = topic_id
        self._render_topic(topic_id)
        self._select_in_toc(topic_id)
        # Reflect the topic's own title in the pane's accessible name for AT users.
        self._content_view.setAccessibleName(topic.title)

    def current_topic_id(self) -> Optional[str]:
        """Return the id of the topic currently shown (or ``None``)."""
        return self._current_topic_id

    # -- rendering --------------------------------------------------------

    def _render_topic(self, topic_id: str) -> None:
        """Resolve + render the topic's Markdown for the active locale."""
        assert self._model is not None
        locale = self._locale_provider()
        try:
            ref = resolve_content_ref(
                self._model,
                topic_id,
                locale,
                available_locales=self._content_locales,
            )
            text = self._reader(ref)
        except (GuideModelError, GuideContentError) as exc:
            # A content-load error surfaces a user-facing message, not a crash
            # (REQ-UG-UI-005). setPlainText never interprets markup. The message is
            # a single translatable unit with a ``%1`` placeholder (no '+'-join of a
            # translated string — word order stays under the translator's control).
            self._content_view.setPlainText(
                self.tr("Could not load this topic:\n\n%1").replace("%1", str(exc))
            )
            return
        self._content_view.setMarkdown(text)

    def _show_load_error(self) -> None:
        """Show the bundle load-error message and disable navigation controls."""
        self._search_edit.setEnabled(False)
        if self._load_error:
            message = self.tr(
                "The User Guide content could not be loaded:\n\n%1"
            ).replace("%1", self._load_error)
        else:
            message = self.tr("The User Guide content could not be loaded.")
        self._content_view.setPlainText(message)

    def _select_in_toc(self, topic_id: str) -> None:
        """Select the ToC entry for ``topic_id`` without re-triggering navigation."""
        item = self._toc_items.get(topic_id)
        if item is None:
            return
        self._suppress_nav = True
        try:
            self._toc_tree.setCurrentItem(item)
        finally:
            self._suppress_nav = False

    # -- search -----------------------------------------------------------

    def _on_search(self, text: str) -> None:
        """Filter to matching topics (empty term shows the ToC)."""
        if self._model is None:
            return
        if not text.strip():
            self._left_stack.setCurrentWidget(self._toc_tree)
            return
        self._suppress_nav = True
        try:
            self._results_list.clear()
            for topic in query(self._model, text):
                item = QListWidgetItem(topic.title)
                item.setData(_TOPIC_ID_ROLE, topic.id)
                self._results_list.addItem(item)
        finally:
            self._suppress_nav = False
        self._left_stack.setCurrentWidget(self._results_list)

    def _on_result_current_changed(
        self,
        current: Optional[QListWidgetItem],
        _previous: Optional[QListWidgetItem] = None,
    ) -> None:
        """Open the highlighted search result (keyboard arrows + click both work)."""
        if self._suppress_nav or current is None:
            return
        topic_id = current.data(_TOPIC_ID_ROLE)
        if isinstance(topic_id, str):
            self.show_topic(topic_id)

    # -- ToC navigation ---------------------------------------------------

    def _on_toc_current_changed(
        self,
        current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem] = None,
    ) -> None:
        """Show the selected ToC topic (section rows carry no topic id → no-op)."""
        if self._suppress_nav or current is None:
            return
        topic_id = current.data(0, _TOPIC_ID_ROLE)
        if isinstance(topic_id, str):
            self.show_topic(topic_id)

    # -- in-guide links ---------------------------------------------------

    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Resolve a clicked anchor to another topic — never fetch externally.

        External/filesystem schemes are ignored (offline + safe, REQ-UG-UI-007). An
        in-guide link may be ``topic:<id>``, a ``#<id>`` fragment, or a bare id; the
        target is matched against a known topic id and navigated to, else ignored.
        """
        if url.scheme().lower() in _EXTERNAL_SCHEMES:
            return
        candidate = url.path() or url.fragment() or url.toString()
        candidate = candidate.lstrip("#/").strip()
        # A ``.md`` suffix (a docs-style relative link) maps to a topic content stem.
        if candidate.endswith(".md"):
            stem = candidate.rsplit("/", 1)[-1][: -len(".md")]
            candidate = self._topic_id_for_stem(stem) or candidate
        if candidate in self._toc_items:
            self.show_topic(candidate)

    def _topic_id_for_stem(self, stem: str) -> Optional[str]:
        """Return the topic id whose content_ref matches ``stem`` (or ``None``)."""
        if self._model is None:
            return None
        for topic in self._model.topics():
            if topic.content_ref == stem:
                return topic.id
        return None

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("User Guide"))
        self.setAccessibleName(self.tr("User Guide"))
        self._search_edit.setPlaceholderText(self.tr("Search the guide…"))
        self._search_edit.setAccessibleName(self.tr("Search the guide"))
        self._toc_tree.setAccessibleName(self.tr("Guide contents"))
        self._results_list.setAccessibleName(self.tr("Search results"))
        self._content_view.setAccessibleName(self.tr("Guide content"))
        # Re-render the current topic so the content follows the active UI locale on
        # a language change (localised-if-present, else default — CL-3), and refresh
        # the load-error text if the bundle failed to load.
        if self._model is None:
            self._show_load_error()
        elif self._current_topic_id is not None:
            self._render_topic(self._current_topic_id)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["User_Guide_Dialog", "Reader", "LocaleProvider"]
