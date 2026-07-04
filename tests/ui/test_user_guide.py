"""In-app User Guide UI/integration acceptance tests (REQ-UG-UI-001..011).

One test per acceptance criterion (Gherkin scenarios SC-U001..U011 in
``specs/user-guide/spec.md`` §11), driving the PySide6 viewer headlessly
(``QT_QPA_PLATFORM=offscreen``) via the ``qtbot`` fixture. Every test runs twice
— once per theme — via the autouse ``theme`` fixture in ``conftest.py``
(REQ-UG-UI-010), so both light and dark are exercised for free; the tests that
make an explicit theme-parity or a11y assertion take the ``theme`` param.

Layer boundary: the viewer binds to the pure ``logic``/``data`` guide model +
defensive reader (both **injectable** — AGT-05 test seams), so most UI tests drive
a deterministic fixture model/reader; the coverage-contract + content-present tests
exercise the **real committed bundle** at the UI/integration boundary (mirroring the
logic check of REQ-UG-LOGIC-005). Content is rendered as text/markup and never
executed (Article VII); the guide is fully offline (no network object exists).
"""

from __future__ import annotations

from typing import Dict

import pytest
from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QListWidget, QTextBrowser, QTreeWidget

from pixelart_creator.data.guide_content import GuideContentError
from pixelart_creator.logic.guide_model import (
    REQUIRED_AREAS,
    GuideModel,
    GuideSection,
    GuideTopic,
    Manifest,
    build_model,
    content_ref_path,
    missing_required_areas,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.user_guide import User_Guide_Dialog

# --------------------------------------------------------------------------- #
# Deterministic fixture model + reader (the AGT-05 injectable test seams).      #
# --------------------------------------------------------------------------- #


def _fixture_manifest() -> Manifest:
    """A small, deterministic section→topic manifest for headless nav tests."""
    return Manifest(
        schema_version=1,
        default_locale="en",
        sections=(
            GuideSection(
                id="layers",
                title="Layers",
                topics=(
                    GuideTopic(
                        id="layers",
                        title="The layer panel",
                        content_ref="layers",
                        keywords=("layer", "opacity", "mask"),
                        summary="the non-destructive layer system",
                    ),
                    GuideTopic(
                        id="blend-modes",
                        title="Blend modes",
                        content_ref="blend-modes",
                        keywords=("blend", "multiply", "screen"),
                        summary="the twelve blend modes",
                    ),
                ),
            ),
            GuideSection(
                id="export-and-pipeline",
                title="Export & Pipeline",
                topics=(
                    GuideTopic(
                        id="export-and-pipeline",
                        title="Export & pipeline integration",
                        content_ref="export-and-pipeline",
                        keywords=("export", "sprite sheet", "atlas"),
                        summary="exporting your work",
                    ),
                ),
            ),
        ),
    )


def _fixture_model() -> GuideModel:
    return build_model(_fixture_manifest())


def _fixture_reader(ref: str) -> str:
    """Return deterministic Markdown text keyed by the resolved content path.

    The path encodes the locale (``content/<locale>/<stem>.md``), so a locale
    switch produces observably different text (exercises SC-U011-3).
    """
    return f"# Rendered {ref}\n\nBody text for {ref}."


def _make_dialog(qtbot, **kwargs) -> User_Guide_Dialog:
    """Build a standalone guide dialog over the fixture seams unless overridden."""
    kwargs.setdefault("model", _fixture_model())
    kwargs.setdefault("reader", _fixture_reader)
    kwargs.setdefault("content_locales", frozenset({"en"}))
    dialog = User_Guide_Dialog(None, **kwargs)
    qtbot.addWidget(dialog)
    return dialog


def _real_dialog(qtbot) -> User_Guide_Dialog:
    """Build a guide dialog over the REAL committed bundle (model=None)."""
    dialog = User_Guide_Dialog(None)
    qtbot.addWidget(dialog)
    return dialog


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --------------------------------------------------------------------------- #
# REQ-UG-UI-001 — Help ▸ User Guide opens the guide.                            #
# --------------------------------------------------------------------------- #


def test_sc_u001_1_help_menu_opens_guide(qtbot):
    """SC-U001-1: Help ▸ User Guide opens the guide with a ToC + content pane."""
    win = _window(qtbot)
    # The Help menu hosts the User Guide action (discoverable entry point).
    assert win._help_menu is not None
    assert win._user_guide_action in win._help_menu.actions()
    assert win._user_guide_dialog is None  # built lazily

    win._on_user_guide()

    dialog = win._user_guide_dialog
    assert isinstance(dialog, User_Guide_Dialog)
    assert dialog.isVisible()
    # The opened surface shows a ToC tree AND a content pane (REQ-UG-UI-003).
    assert isinstance(dialog._toc_tree, QTreeWidget)
    assert isinstance(dialog._content_view, QTextBrowser)


def test_sc_u001_2_reopen_reuses_single_dialog(qtbot):
    """SC-U001-1 (lazy/reuse): re-triggering reuses the one lazily-built dialog."""
    win = _window(qtbot)
    win._on_user_guide()
    first = win._user_guide_dialog
    win._on_user_guide()
    assert win._user_guide_dialog is first  # no second instance leaked


# --------------------------------------------------------------------------- #
# REQ-UG-UI-002 — F1 opens the guide.                                          #
# --------------------------------------------------------------------------- #


def test_sc_u002_1_f1_shortcut_opens_guide(qtbot):
    """SC-U002-1: the User Guide action is bound to F1 and opens the same surface."""
    win = _window(qtbot)
    assert win._user_guide_action.shortcut() == QKeySequence(Qt.Key.Key_F1)
    # Firing the action (the F1 target) opens the guide.
    win._user_guide_action.trigger()
    assert isinstance(win._user_guide_dialog, User_Guide_Dialog)
    assert win._user_guide_dialog.isVisible()


# --------------------------------------------------------------------------- #
# REQ-UG-UI-003 — Navigable window: ToC tree + content pane.                   #
# --------------------------------------------------------------------------- #


def test_sc_u003_1_shows_toc_tree_and_content_pane(qtbot):
    """SC-U003-1: the guide shows a ToC tree (sections→topics) and a content pane."""
    dialog = _make_dialog(qtbot)
    # Two sections, each with its topics as children (built from the model).
    assert dialog._toc_tree.topLevelItemCount() == 2
    section = dialog._toc_tree.topLevelItem(0)
    assert section.text(0) == "Layers"
    assert section.childCount() == 2
    assert isinstance(dialog._content_view, QTextBrowser)
    # The first topic is auto-shown on open.
    assert dialog.current_topic_id() == "layers"


# --------------------------------------------------------------------------- #
# REQ-UG-UI-004 — ToC navigation shows the selected topic.                     #
# --------------------------------------------------------------------------- #


def test_sc_u004_1_selecting_toc_entry_shows_topic(qtbot):
    """SC-U004-1: selecting a ToC entry shows that topic's page."""
    dialog = _make_dialog(qtbot)
    # Select the "Blend modes" topic item (section 0, child 1).
    item = dialog._toc_items["blend-modes"]
    dialog._toc_tree.setCurrentItem(item)
    assert dialog.current_topic_id() == "blend-modes"
    assert "blend-modes" in dialog._content_view.toPlainText()


def test_sc_u004_2_toc_reflects_model_order_not_hardcoded(qtbot):
    """SC-U004-2: the ToC order mirrors the model's section/topic order."""
    model = _fixture_model()
    dialog = _make_dialog(qtbot, model=model)
    toc_section_titles = [
        dialog._toc_tree.topLevelItem(i).text(0)
        for i in range(dialog._toc_tree.topLevelItemCount())
    ]
    assert toc_section_titles == [s.title for s in model.sections]
    # Topic order within the first section matches the model too.
    first = dialog._toc_tree.topLevelItem(0)
    child_titles = [first.child(i).text(0) for i in range(first.childCount())]
    assert child_titles == [t.title for t in model.sections[0].topics]


# --------------------------------------------------------------------------- #
# REQ-UG-UI-005 — Content rendered as text/markup, in-guide links, no exec.    #
# --------------------------------------------------------------------------- #


def test_sc_u005_1_topic_renders_as_markup(qtbot, theme):
    """SC-U005-1: a topic renders as text/markup in the content pane (both themes)."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("layers")
    # setMarkdown parsed the heading -> the body text is present as rendered text.
    assert "Body text" in dialog._content_view.toPlainText()
    assert dialog._content_view.toPlainText().strip() != ""


def test_sc_u005_2_in_guide_link_navigates_within_guide(qtbot):
    """SC-U005-2: a ``topic:`` / ``.md`` link navigates within the guide."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("layers")
    # A topic: scheme link jumps to the target topic.
    dialog._on_anchor_clicked(QUrl("topic:export-and-pipeline"))
    assert dialog.current_topic_id() == "export-and-pipeline"
    # A docs-style .md relative link maps to the topic content stem and navigates.
    dialog._on_anchor_clicked(QUrl("blend-modes.md"))
    assert dialog.current_topic_id() == "blend-modes"


def test_sc_u005_2b_external_link_is_a_noop(qtbot):
    """SC-U005-2 (offline/safe): an external/file link is a no-op (never fetched)."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("layers")
    for external in ("https://example.com/x", "file:///etc/passwd", "mailto:x@y.z"):
        dialog._on_anchor_clicked(QUrl(external))
        assert dialog.current_topic_id() == "layers"  # unchanged, no navigation


def test_sc_u005_3_content_load_error_surfaces_message_no_crash(qtbot):
    """SC-U005-3: a content-load error surfaces a user-facing message, not a crash."""

    def _raising_reader(ref: str) -> str:
        raise GuideContentError(f"boom: {ref}")

    dialog = _make_dialog(qtbot, reader=_raising_reader)
    # No exception was raised building/showing; the pane holds the error message
    # rendered as PLAIN text (never interpreted as markup).
    text = dialog._content_view.toPlainText()
    assert "Could not load this topic" in text
    assert "boom" in text


def test_sc_u005_3b_malformed_bundle_degrades_to_error_screen(qtbot, monkeypatch):
    """SC-U005-3: a malformed bundle opens to an error screen (search disabled)."""
    import pixelart_creator.ui.user_guide as ug

    def _boom_manifest():
        raise GuideContentError("no manifest")

    monkeypatch.setattr(ug, "load_manifest", _boom_manifest)
    # model=None forces the bundle-load path, which is caught and reported.
    dialog = User_Guide_Dialog(None)
    qtbot.addWidget(dialog)
    assert "could not be loaded" in dialog._content_view.toPlainText()
    assert not dialog._search_edit.isEnabled()


# --------------------------------------------------------------------------- #
# REQ-UG-UI-006 — In-guide search finds and jumps to a topic.                  #
# --------------------------------------------------------------------------- #


def test_sc_u006_1_search_lists_results_and_jump_opens(qtbot):
    """SC-U006-1: typing a term shows matches; selecting a result opens the topic."""
    dialog = _make_dialog(qtbot)
    dialog._search_edit.setText("export")
    # Results pane is now shown with the matching topic.
    assert dialog._left_stack.currentWidget() is dialog._results_list
    assert dialog._results_list.count() >= 1
    titles = [
        dialog._results_list.item(i).text() for i in range(dialog._results_list.count())
    ]
    assert "Export & pipeline integration" in titles
    # Jumping to a result opens that topic in the content pane.
    dialog._results_list.setCurrentRow(0)
    assert dialog.current_topic_id() == "export-and-pipeline"


def test_sc_u006_2_search_finds_a_known_topic(qtbot):
    """SC-U006-2 (owner-required): a known keyword resolves to its topic."""
    dialog = _make_dialog(qtbot)
    dialog._search_edit.setText("multiply")  # a blend-modes keyword
    ids = {
        dialog._results_list.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dialog._results_list.count())
    }
    assert "blend-modes" in ids


def test_sc_u006_3_empty_search_restores_toc(qtbot):
    """SC-U006 (CL-2): clearing the search restores the ToC view."""
    dialog = _make_dialog(qtbot)
    dialog._search_edit.setText("export")
    assert dialog._left_stack.currentWidget() is dialog._results_list
    dialog._search_edit.setText("   ")  # whitespace-only -> treated as empty
    assert dialog._left_stack.currentWidget() is dialog._toc_tree


# --------------------------------------------------------------------------- #
# REQ-UG-UI-007 — Fully offline: no network object; renders from the bundle.   #
# --------------------------------------------------------------------------- #


def test_sc_u007_1_offline_no_network_object(qtbot):
    """SC-U007-1: the viewer holds no network client and disables external links."""
    dialog = _real_dialog(qtbot)
    # The content browser never opens links externally or reads the filesystem.
    assert dialog._content_view.openExternalLinks() is False
    assert dialog._content_view.openLinks() is False
    assert dialog._content_view.searchPaths() == []
    # No QNetwork* / socket attribute exists on the viewer (fully offline).
    assert not any(
        "network" in name.lower() or "socket" in name.lower() for name in vars(dialog)
    )
    # It still renders a real topic entirely from bundled content.
    assert dialog._content_view.toPlainText().strip() != ""


# --------------------------------------------------------------------------- #
# REQ-UG-UI-008 — Cloud & collaboration + every area present (REAL bundle).    #
# --------------------------------------------------------------------------- #


def test_sc_u008_1_cloud_collaboration_section_present(qtbot):
    """SC-U008-1: the ToC includes the cloud & collaboration section with content."""
    dialog = _real_dialog(qtbot)
    section_ids_by_title = {
        dialog._toc_tree.topLevelItem(i).text(0): dialog._toc_tree.topLevelItem(i)
        for i in range(dialog._toc_tree.topLevelItemCount())
    }
    assert "Cloud & Collaboration" in section_ids_by_title
    cloud = section_ids_by_title["Cloud & Collaboration"]
    assert cloud.childCount() >= 1
    # The collaboration topic renders real prose covering presence + branching.
    dialog.show_topic("collaboration")
    text = dialog._content_view.toPlainText().lower()
    assert "presence" in text
    assert "branch" in text


def test_sc_u008_2_content_present_for_every_required_area(qtbot):
    """SC-U008-2 (owner-required): every required area has ≥1 readable topic.

    Mirrors the REQ-UG-LOGIC-005 coverage contract at the UI/integration boundary
    over the REAL shipped bundle.
    """
    dialog = _real_dialog(qtbot)
    assert dialog._model is not None
    # Coverage-contract sanity: no required area is missing.
    assert missing_required_areas(dialog._model) == ()
    # Each required section id is present in the ToC and each of its topics renders
    # non-stub content.
    section_ids = {section.id for section in dialog._model.sections}
    for area in REQUIRED_AREAS:
        assert area in section_ids, f"required area missing from ToC: {area}"
    for topic in dialog._model.topics():
        dialog.show_topic(topic.id)
        rendered = dialog._content_view.toPlainText().strip()
        assert len(rendered) > 40, f"topic {topic.id!r} rendered stub/empty content"


# --------------------------------------------------------------------------- #
# REQ-UG-UI-009 — Accessibility (keyboard, names, focus order, Esc-close).     #
# --------------------------------------------------------------------------- #


def test_sc_u009_1_keyboard_navigable_with_accessible_names(qtbot, theme):
    """SC-U009-1/-2: interactive controls are keyboard-reachable with a11y names."""
    dialog = _make_dialog(qtbot)
    # Accessible names on every interactive control (screen-reader labels).
    assert dialog.accessibleName() != ""
    assert dialog._search_edit.accessibleName() != ""
    assert dialog._toc_tree.accessibleName() != ""
    assert dialog._results_list.accessibleName() != ""
    # The content pane's accessible name reflects the open topic's title (AT users).
    dialog.show_topic("blend-modes")
    assert dialog._content_view.accessibleName() == "Blend modes"
    # ToC / results / search are keyboard-focusable (arrows/Enter operate them).
    assert dialog._toc_tree.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert dialog._results_list.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert dialog._search_edit.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_sc_u009_1b_keyboard_arrows_navigate_toc(qtbot):
    """SC-U009-1: arrow-key navigation of the ToC opens the highlighted topic."""
    dialog = _make_dialog(qtbot)
    # Programmatically drive the same currentItemChanged path the keyboard uses.
    dialog._toc_tree.setCurrentItem(dialog._toc_items["export-and-pipeline"])
    assert dialog.current_topic_id() == "export-and-pipeline"


def test_sc_u009_1c_escape_closes_the_dialog(qtbot):
    """SC-U009-1: Esc closes the guide (QDialog reject)."""
    dialog = _make_dialog(qtbot)
    dialog.show()
    assert dialog.isVisible()
    dialog.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert not dialog.isVisible()


# --------------------------------------------------------------------------- #
# REQ-UG-UI-010 — Both themes render correctly and legibly.                    #
# --------------------------------------------------------------------------- #


def test_sc_u010_1_renders_in_both_themes(qtbot, theme):
    """SC-U010-1: the guide renders (no hard-coded colour) in both themes.

    Runs once per theme via the autouse fixture; the app applies a non-empty
    role-based QSS and the dialog inherits it (never sets a per-widget colour).
    """
    dialog = _make_dialog(qtbot)
    dialog.show()
    assert QApplication.instance().styleSheet() != ""
    # The dialog sets no inline stylesheet of its own (colours by role only).
    assert dialog.styleSheet() == ""
    # Content is legible: the topic rendered non-empty under this theme.
    dialog.show_topic("layers")
    assert dialog._content_view.toPlainText().strip() != ""


# --------------------------------------------------------------------------- #
# REQ-UG-UI-011 — Chrome retranslates; content follows locale resolution.      #
# --------------------------------------------------------------------------- #


def test_sc_u011_2_chrome_retranslates_on_language_change(qtbot):
    """SC-U011-2: a LanguageChange event re-runs _retranslate on the chrome."""
    dialog = _make_dialog(qtbot)
    dialog.setWindowTitle("XXX")
    dialog._search_edit.setPlaceholderText("XXX")
    dialog._toc_tree.setAccessibleName("XXX")
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert dialog.windowTitle() == "User Guide"
    assert dialog._search_edit.placeholderText() == "Search the guide…"
    assert dialog._toc_tree.accessibleName() == "Guide contents"


def test_sc_u011_3_content_follows_locale_resolution(qtbot):
    """SC-U011-3 (CL-3): content re-renders via the model's locale resolution.

    A localised doc is used when present for the active locale, and the content
    re-renders on a language change.
    """
    state = {"loc": "en"}
    captured: Dict[str, str] = {}

    def _locale_reader(ref: str) -> str:
        captured["last"] = ref
        return f"# {ref}"

    dialog = _make_dialog(
        qtbot,
        reader=_locale_reader,
        content_locales=frozenset({"en", "es"}),
        locale_provider=lambda: state["loc"],
    )
    dialog.show_topic("layers")
    # Active locale en -> the en content path is resolved + read.
    assert captured["last"] == content_ref_path("layers", "en")

    # Switch the UI language to Spanish and deliver LanguageChange: the content
    # re-renders via the es path (localised-if-present).
    state["loc"] = "es"
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert captured["last"] == content_ref_path("layers", "es")


def test_sc_u011_3b_locale_falls_back_to_default(qtbot):
    """SC-U011-3 (CL-3): an absent locale falls back to the default-locale content."""
    captured: Dict[str, str] = {}

    def _locale_reader(ref: str) -> str:
        captured["last"] = ref
        return f"# {ref}"

    # Active locale "es" but only "en" content ships -> fall back to en.
    dialog = _make_dialog(
        qtbot,
        reader=_locale_reader,
        content_locales=frozenset({"en"}),
        locale_provider=lambda: "es",
    )
    dialog.show_topic("layers")
    assert captured["last"] == content_ref_path("layers", "en")


def test_sc_u011_2b_load_error_message_retranslates(qtbot, monkeypatch):
    """SC-U011-2: the bundle load-error screen also refreshes on LanguageChange."""
    import pixelart_creator.ui.user_guide as ug

    monkeypatch.setattr(
        ug, "load_manifest", lambda: (_ for _ in ()).throw(GuideContentError("x"))
    )
    dialog = User_Guide_Dialog(None)
    qtbot.addWidget(dialog)
    dialog._content_view.setPlainText("XXX")
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert "could not be loaded" in dialog._content_view.toPlainText()


# --------------------------------------------------------------------------- #
# Unknown-topic / guard edges (defensive paths, no-op on bad input).           #
# --------------------------------------------------------------------------- #


def test_show_topic_unknown_id_is_noop(qtbot):
    """show_topic with an unknown id is a safe no-op (guarded by the model)."""
    dialog = _make_dialog(qtbot)
    before = dialog.current_topic_id()
    dialog.show_topic("does-not-exist")
    assert dialog.current_topic_id() == before


def test_anchor_to_unknown_topic_is_noop(qtbot):
    """An in-guide anchor to an unknown topic id navigates nowhere."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("layers")
    dialog._on_anchor_clicked(QUrl("topic:nope"))
    assert dialog.current_topic_id() == "layers"


def test_unknown_md_stem_link_is_noop(qtbot):
    """An in-guide ``.md`` link with an unknown stem navigates nowhere."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("layers")
    dialog._on_anchor_clicked(QUrl("does-not-exist.md"))
    assert dialog.current_topic_id() == "layers"


def test_selecting_section_header_is_noop(qtbot):
    """Selecting a section header row (no topic id) does not change the topic."""
    dialog = _make_dialog(qtbot)
    dialog.show_topic("blend-modes")
    dialog._toc_tree.setCurrentItem(dialog._toc_tree.topLevelItem(0))  # a section row
    assert dialog.current_topic_id() == "blend-modes"  # unchanged


def test_empty_section_model_shows_no_topic(qtbot):
    """A model with an empty section opens with no topic auto-shown (no crash)."""
    model = build_model(
        Manifest(
            schema_version=1,
            default_locale="en",
            sections=(GuideSection(id="empty", title="Empty", topics=()),),
        )
    )
    dialog = _make_dialog(qtbot, model=model)
    assert dialog.current_topic_id() is None
    assert dialog._toc_tree.topLevelItemCount() == 1
    assert dialog._toc_tree.topLevelItem(0).childCount() == 0
