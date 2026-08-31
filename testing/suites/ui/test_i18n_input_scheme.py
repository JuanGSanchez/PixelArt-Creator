"""T-30 (AGT-06) acceptance tests for the input-scheme catalogues (REQ-IS-BUILD-002).

Covers `SC-B002-1..3` for the eight strings T-27 wrapped, extracted and
translated: "Cursor feedback", "Add Frame", "Remove Frame", "Fit to
&Content", the last-remaining-frame status notice, the two ``tool_icons``
``ToolGlyphError`` messages, and "unknown theme: %1". Every assertion below
resolves the REAL, compiled ``pixelart_es.qm`` through the production
``LanguageManager``/``QTranslator`` path -- never a string compared to
itself -- so a missing or empty ``es`` catalogue fails these tests outright
(``manager.set_language("es")`` returns ``False`` and the following
assertion raises, or the Spanish literal simply never appears).

``pixelart_en.ts`` is a deliberately unfinished IDENTITY catalogue (0
compiled translations, source-text fallback) and is not asserted "against"
here beyond the load check T-30 requires -- an app that shows the English
source under ``en`` is correct, not a defect (see the module under test's
own docstring / the task brief).

Both themes run automatically via the suite's autouse, parametrised
``theme`` fixture (``testing/suites/ui/conftest.py``); none of these
assertions are theme-dependent (translation text, not colour/QSS), so no
test here requests ``theme`` explicitly -- the same reasoning already
recorded in ``test_cursor_feedback.py``'s module docstring.

D-12 / round-trip-untranslated: ``Shift+A`` is a key-name TOKEN, never
routed through ``tr()`` at all (``ui/main_window.py``'s tool tooltip
concatenates the translated label with the raw ``QKeySequence`` text
produced at runtime). The dedicated test below proves the installed ``es``
catalogue changes the label half and leaves the key-name half character-for-
character identical -- the two-sided guarantee D-12 rules on: a translated
modifier would neither match what the keyboard produces nor the binding
registry (``logic/binding_registry.py``) a later check compares the guide
against.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QWidget

from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui import tool_icons
from pixelart_creator.ui.cursor_feedback_overlay import Cursor_Feedback_Overlay
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.timeline_panel import Timeline_Panel
from pixelart_creator.ui.tools import PickerTool

# --------------------------------------------------------------------------- #
# Fixture: install the REAL es catalogue for one test, always revert          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def es_language(qapp):
    """Install the real ``pixelart_es.qm`` for the test body, then revert.

    Asserts the load succeeded so a missing/corrupt catalogue fails at the
    fixture boundary rather than silently leaving the app on English, which
    would make every dependent assertion below a false pass.
    """
    manager = LanguageManager(qapp)
    installed = manager.set_language("es")
    assert installed is True, "the real pixelart_es.qm catalogue failed to load"
    try:
        yield manager
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 1. Both compiled catalogues load                                            #
# --------------------------------------------------------------------------- #


def test_req_is_build_002_both_qm_catalogues_load(qapp):
    """REQ-IS-BUILD-002: both ``pixelart_es.qm`` and ``pixelart_en.qm`` load.

    ``en`` is the deliberately-unfinished identity catalogue (0 compiled
    translations -- source-text fallback is correct); it must still LOAD as
    a valid compiled ``.qm``, which is the only claim made about it here."""
    from PySide6.QtCore import QTranslator

    i18n_dir = str(_default_translations_dir())
    for code in ("es", "en"):
        translator = QTranslator()
        loaded = translator.load(f"pixelart_{code}", i18n_dir)
        assert loaded is True, f"pixelart_{code}.qm failed to load from {i18n_dir}"


# --------------------------------------------------------------------------- #
# 2. "Cursor feedback" -- Cursor_Feedback_Overlay accessible name             #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_cursor_feedback_accessible_name_resolves_under_es(qtbot, qapp):
    """SC-B002-1: the overlay's accessible name is "Retroalimentación del
    cursor" under the real es catalogue -- proven live: constructed under
    English (asserted first), THEN switched, not merely read once already-
    translated at construction time."""
    viewport = QWidget()
    qtbot.addWidget(viewport)
    overlay = Cursor_Feedback_Overlay(viewport)
    qtbot.addWidget(overlay)
    assert overlay.accessibleName() == "Cursor feedback"

    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert overlay.accessibleName() == "Retroalimentación del cursor"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 3. "Add Frame" / "Remove Frame" -- Timeline_Panel action text + tooltip,    #
#    and the pushed undo command's OWN label (self.tr() at push time)         #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_timeline_panel_frame_actions_resolve_under_es(
    qtbot, qapp, make_document
):
    """SC-B002-1: Add Frame / Remove Frame panel action text resolves under
    es and re-sets LIVE on an installed-translator LanguageChange (the panel
    is constructed under English first, proving the switch, not construction
    order, is what changes the text)."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    stack = QUndoStack()
    document = make_document()
    panel.set_context(document, stack, lambda: None)

    assert panel._add_action.text() == "Add Frame"
    assert panel._remove_action.text() == "Remove Frame"

    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert panel._add_action.text() == "Añadir fotograma"
        assert panel._remove_action.text() == "Eliminar fotograma"

        # The undoable command's own label is produced by self.tr() at PUSH
        # time (Timeline_Panel._on_add/_on_remove), not cached from
        # construction -- exercise the real push path, not the label alone.
        panel._on_add()
        assert stack.undoText() == "Añadir fotograma"
        panel._on_remove()
        assert stack.undoText() == "Eliminar fotograma"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_sc_b002_1_timeline_grid_view_remove_frame_context_resolves_under_es(
    qapp, es_language
):
    """SC-B002-1: ``Timeline_Grid_View``'s OWN "Remove Frame" catalogue entry
    (a separate context from ``Timeline_Panel``'s -- Ctrl+right-click on the
    grid pushes its own ``self.tr("Remove Frame")``, ``ui/timeline_grid_view.py``)
    resolves under es too. Uses the exact context Qt's moc generates for that
    class (its class name) -- the same lookup ``self.tr()`` performs
    internally -- rather than re-wiring the grid's document/stack binding
    just to read a label."""
    from PySide6.QtCore import QCoreApplication

    resolved = QCoreApplication.translate("Timeline_Grid_View", "Remove Frame")
    assert resolved == "Eliminar fotograma"


def test_sc_b002_1_main_window_canvas_add_frame_command_resolves_under_es(qtbot, qapp):
    """SC-B002-1: the Ctrl+left-click canvas add-frame path
    (``Main_Window._on_canvas_add_frame_requested``) pushes its OWN
    "Add Frame" catalogue entry (``ui/main_window.py`` context, distinct
    from ``Timeline_Panel``'s), and it resolves under es."""
    win = Main_Window()
    qtbot.addWidget(win)
    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        win._on_canvas_add_frame_requested()
        record = win.active_tab()
        assert record is not None
        assert record.stack.undoText() == "Añadir fotograma"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 4. "Fit to &Content" -- new View-menu entry, changeEvent/LanguageChange     #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_fit_content_action_retranslates_live_under_es(qtbot, qapp):
    """SC-B002-1 + Article V.2: the new View-menu "Fit to &Content" entry is
    re-set by ``changeEvent``/``LanguageChange`` -- constructed under
    English, THEN switched, proving the live re-set (not a string translated
    once at construction and never again, which would look correct in any
    test that never switches language, per the task brief)."""
    win = Main_Window()
    qtbot.addWidget(win)
    assert win._fit_content_action.text() == "Fit to &Content"

    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert win._fit_content_action.text() == "Ajustar al &contenido"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 5. Last-remaining-frame status notice                                       #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_last_frame_removal_notice_resolves_under_es(qtbot, qapp):
    """SC-B002-1: ``Main_Window._notify_last_frame_removal_refused``'s
    status-bar notice resolves under es. Transient (built fresh on every
    emission, like its ``_notify_layer_locked`` sibling), so es is installed
    BEFORE the call -- this is the same "re-resolve at call time" shape the
    existing ``test_d05_notice_retranslates_on_language_change`` proves for
    that sibling notice, not a persisted-label ``changeEvent`` re-set."""
    win = Main_Window()
    qtbot.addWidget(win)
    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        win._notify_last_frame_removal_refused()
        assert win.statusBar().currentMessage() == (
            "Este es el último fotograma restante; "
            "un documento debe conservar al menos uno."
        )
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 6/7/8. tool_icons.ToolGlyphError messages + theme._roles "unknown theme"   #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_unknown_tool_glyph_id_message_resolves_under_es(qapp, es_language):
    """SC-B002-1: ``tool_icons``' "unknown tool glyph id: %1" resolves under
    es with the bad id substituted after translation (``.replace("%1", ...)``,
    ``ui/tool_icons.py``)."""
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons._glyph_resource("not-a-real-tool")
    assert (
        str(excinfo.value) == "id de glifo de herramienta desconocido: not-a-real-tool"
    )


def test_sc_b002_1_missing_tool_glyph_asset_message_resolves_under_es(
    qapp, es_language, monkeypatch, tmp_path
):
    """SC-B002-1: ``tool_icons``' "missing tool glyph asset for: %1" resolves
    under es. Forces the missing-asset branch (a KNOWN id, an EMPTY glyph
    root) by monkeypatching ``_glyphs_root`` to an empty ``tmp_path`` --
    never touching the real, shipped glyph assets."""
    monkeypatch.setattr(tool_icons, "_glyphs_root", lambda: tmp_path)
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons._glyph_resource("pencil")
    assert str(excinfo.value) == "falta el recurso de glifo de herramienta para: pencil"


def test_sc_b002_1_unknown_theme_message_resolves_under_es_theme_context(
    qapp, es_language
):
    """SC-B002-1: ``ui/theme.py``'s "unknown theme: %1" (``theme`` context)
    resolves under es with the bad name substituted."""
    with pytest.raises(ValueError) as excinfo:
        theme_module._roles("not-a-real-theme")
    assert str(excinfo.value) == "tema desconocido: not-a-real-theme"


def test_sc_b002_1_unknown_theme_message_resolves_under_es_tool_icons_context(
    qapp, es_language
):
    """SC-B002-1: the SAME source text has a SECOND catalogue entry under the
    ``tool_icons`` context (``ui/tool_icons.py``'s ``_tint_colour``, reached
    through the public ``tool_icon()`` entry point) -- also resolves under
    es. Two distinct ``lupdate`` message locations for one English sentence,
    both must carry a translation, not just one."""
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons.tool_icon("pencil", theme="not-a-real-theme")
    assert str(excinfo.value) == "tema desconocido: not-a-real-theme"


# --------------------------------------------------------------------------- #
# D-12: a key-name literal round-trips UNTRANSLATED                           #
# --------------------------------------------------------------------------- #


def test_d12_shift_a_key_literal_round_trips_untranslated_under_es(qtbot, qapp):
    """D-12: ``Shift+A`` (the picker tool's shortcut) must be ``Shift+A`` in
    Spanish too -- a translated modifier would match neither what the
    keyboard actually produces nor the binding registry a later check
    compares the guide against.

    The picker tool's tooltip concatenates the translated label with the
    RAW ``QKeySequence`` text (``ui/main_window.py``, never routed through
    ``tr()``). This test would FAIL if the es catalogue were absent -- the
    label half stays "Colour picker" (English) and the two assertions on
    the Spanish label text below fail outright -- so a missing catalogue
    cannot read as a pass here."""
    win = Main_Window()
    qtbot.addWidget(win)
    picker_action = win._tool_actions[PickerTool.tool_id]
    assert picker_action.shortcut().toString() == "Shift+A"
    en_tooltip = picker_action.toolTip()
    assert en_tooltip == "Colour picker (Shift+A)"

    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        es_tooltip = picker_action.toolTip()
        # Proves the es catalogue is really active (fails if absent/empty):
        assert es_tooltip != en_tooltip
        assert "Selector de color" in es_tooltip
        # The key-name TOKEN is untouched -- untranslated, character for
        # character, exactly as ruling D-12 requires.
        assert "Shift+A" in es_tooltip
        assert es_tooltip == "Selector de color (Shift+A)"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
