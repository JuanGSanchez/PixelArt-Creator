"""Automation panel edge branches — enablement, retranslate, dialogs, guards.

Covers the main-thread branches the acceptance tests do not exercise: ``set_busy``
enablement, ``changeEvent`` retranslate (F5), colour-picking, list add/remove
guards, parse-error paths, and inert refresh/disable — so the Phase-8 automation
UI modules meet the coverage gate (≥90 line / ≥80 branch) without worker-thread
blind spots. Headless; both themes.

REQ-P8-UI-014 (R-25, AGT-06 audit): the ``_lang_change(widget)`` calls above are
bare smoke-only invocations (they prove ``changeEvent`` does not raise, never
that a retranslated string is actually non-empty). The ``test_t25_*`` section
below (T-25) supplies REAL post-condition assertions for the four automation
panels that previously had none — closing REQ-P8-UI-014's i18n-retranslate gap
for this UI family — including the new Cancel button's retranslation (C-07).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFileDialog, QMessageBox

from pixelart_creator.ui.batch_recolour_panel import (
    _MODE_COLOUR,
    _MODE_INDEX,
    Batch_Recolour_Panel,
)
from pixelart_creator.ui.macro_controls import Macro_Controls
from pixelart_creator.ui.plugin_manager_panel import Plugin_Manager_Panel
from pixelart_creator.ui.procgen_panel import Procgen_Panel
from pixelart_creator.ui.script_runner_panel import Script_Runner_Panel
from tests.ui._automation_helpers import (
    GREEN,
    RED,
    macro_of,
    procgen_op,
    write_manifest,
)


def _lang_change(widget) -> None:
    widget.changeEvent(QEvent(QEvent.Type.LanguageChange))


# -- macro controls ---------------------------------------------------------


def test_macro_controls_set_busy_and_guards(qtbot):
    c = Macro_Controls()
    qtbot.addWidget(c)
    c.set_busy(True)
    assert not c._record_button.isEnabled() and not c._replay_button.isEnabled()
    c.set_busy(False)
    assert c._record_button.isEnabled()
    # add_recorded_ops is a no-op when not recording; replay/save with no selection.
    c.add_recorded_ops([procgen_op(seed=1)])
    c._on_replay()  # no selection → no signal
    c._on_save()  # no selection → returns
    c._on_remove()  # empty list → returns
    _lang_change(c)  # retranslate branch


def test_macro_controls_empty_recording_banks_nothing(qtbot):
    c = Macro_Controls()
    qtbot.addWidget(c)
    c._record_button.setChecked(True)
    c._record_button.setChecked(False)  # stop with nothing captured
    assert c._list.count() == 0


def test_macro_controls_save_cancel_and_load_cancel(qtbot, monkeypatch):
    c = Macro_Controls()
    qtbot.addWidget(c)
    c._add_macro(macro_of(procgen_op(seed=1)), "m")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    c._on_save()  # cancelled dialog → returns without writing
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    c._on_load()  # cancelled dialog → returns
    assert c._list.count() == 1
    c._on_remove()  # remove the one selected macro
    assert c._list.count() == 0


# -- script runner ----------------------------------------------------------


def test_script_runner_set_busy_and_parse_errors(qtbot, mute_message_boxes):
    p = Script_Runner_Panel()
    qtbot.addWidget(p)
    p.set_busy(True)
    assert not p._run_button.isEnabled()
    p.set_busy(False)

    # Empty text → no-op.
    p._editor.setPlainText("   ")
    p._on_run()
    # Non-array JSON.
    p._editor.setPlainText('{"name": "x"}')
    p._on_run()
    # Entry missing name / wrong types.
    p._editor.setPlainText("[123]")
    p._on_run()
    p._editor.setPlainText('[{"name": 5}]')
    p._on_run()
    p._editor.setPlainText('[{"name": "x", "params": 5}]')
    p._on_run()
    _lang_change(p)
    assert len(mute_message_boxes) >= 4  # each malformed script surfaced an error


# -- batch recolour ---------------------------------------------------------


def test_batch_recolour_colour_pick_and_pair_guards(qtbot, monkeypatch):
    p = Batch_Recolour_Panel()
    qtbot.addWidget(p)
    p.set_busy(True)
    assert not p._apply_button.isEnabled()
    p.set_busy(False)
    p.set_frame_count(3)
    assert p._frame_spin.maximum() == 2

    # Colour mode + a valid pick, then add + remove a pair.
    p._mode_combo.setCurrentIndex(_MODE_COLOUR)
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor(*GREEN))
    )
    p._pick_src_colour()
    p._pick_dst_colour()
    assert p._src_colour == GREEN
    p._on_add_pair()
    assert p._list.count() == 1
    p._list.setCurrentRow(0)
    p._on_remove_pair()
    assert p._list.count() == 0
    # Invalid pick returns the current colour unchanged.
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor())
    )
    keep = p._src_colour
    p._pick_src_colour()
    assert p._src_colour == keep
    # Apply with no pairs → no-op; index-mode add path.
    p._on_apply()
    p._mode_combo.setCurrentIndex(_MODE_INDEX)
    p._src_index.setValue(1)
    p._dst_index.setValue(2)
    p._on_add_pair()
    assert p._list.count() == 1
    _lang_change(p)


# -- plugin manager ---------------------------------------------------------


def test_plugin_manager_refresh_disable_and_no_manifest(qtbot, monkeypatch):
    p = Plugin_Manager_Panel()
    qtbot.addWidget(p)
    p._on_refresh()  # inert discovery (no load/run)
    p._on_disable()  # nothing selected/enabled → no-op

    # Install cancel path.
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    p._on_install()

    # A discovered/empty-manifest plugin cannot be enabled (no declared caps).
    from pixelart_creator.logic.plugins import PluginManifest

    inert = PluginManifest(name="inert", version="1", api_version="1", capabilities=())
    p._add_manifest_item(inert)
    calls = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: calls.append(a) or QMessageBox.StandardButton.Ok),
    )
    p._on_enable()  # capabilities empty → informational "No Manifest", not enabled
    assert calls and "inert" not in p._handles
    _lang_change(p)


def test_plugin_manager_refresh_preserves_installed_manifest(qtbot):
    """_on_refresh keeps an installed (capability-bearing) manifest across a rescan."""
    from pixelart_creator.logic.plugins import Capability, PluginManifest

    p = Plugin_Manager_Panel()
    qtbot.addWidget(p)
    installed = PluginManifest(
        name="kept",
        version="1",
        api_version="1",
        capabilities=(Capability.READ_DOCUMENT,),
    )
    p._add_manifest_item(installed)
    p._on_refresh()  # exercises the installed-preservation branch + inert discovery
    names = {p._manifest_at(row).name for row in range(p._list.count())}
    assert "kept" in names


def test_plugin_manager_enable_failure_surfaces_error(
    qtbot, monkeypatch, tmp_path, mute_message_boxes, plugin_isolation
):
    """A PluginError from enable surfaces a graceful warning; the plugin stays disabled."""
    import pixelart_creator.ui.plugin_manager_panel as pmp
    from pixelart_creator.logic.plugins import PluginError

    p = Plugin_Manager_Panel()
    qtbot.addWidget(p)
    manifest = write_manifest(
        tmp_path / "m.json", name="boom", capabilities=["read_document"]
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(manifest), "")),
    )
    p._on_install()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    def _raise(*a, **k):
        raise PluginError("nope")

    monkeypatch.setattr(pmp, "enable", _raise)
    p._on_enable()
    assert "boom" not in p._handles
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_plugin_manager_enable_then_reenable_noop_then_disable(
    qtbot, monkeypatch, tmp_path, plugin_isolation
):
    """A second enable of an already-enabled plugin is a no-op; disable frees it."""
    p = Plugin_Manager_Panel()
    qtbot.addWidget(p)
    manifest = write_manifest(
        tmp_path / "m.json", name="once", capabilities=["read_document"]
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(manifest), "")),
    )
    p._on_install()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    p._on_enable()
    assert "once" in p._handles
    p._on_enable()  # already enabled → early return (no second grant)
    assert list(p._handles) == ["once"]
    p._on_disable()  # handle present → unregister + free slot
    assert "once" not in p._handles


# -- procgen ----------------------------------------------------------------


def test_procgen_retranslate_branch(qtbot):
    p = Procgen_Panel()
    qtbot.addWidget(p)
    _lang_change(p)  # covers the changeEvent retranslate path
    assert p._generate_button.text() != ""


# --------------------------------------------------------------------------- #
# T-25 (AGT-06 audit) — REAL LanguageChange post-condition assertions, the     #
# four automation panels that previously only had a bare smoke call above.    #
# Labelled SC-UI-014-1 (REQ-P8-UI-014, R-25). Includes the new Cancel         #
# button's retranslation (pairs with C-07).                                   #
# --------------------------------------------------------------------------- #


def test_sc_ui_014_1_macro_controls_retranslate_incl_cancel_button(qtbot):
    """SC-UI-014-1: every persistent Macro_Controls string re-populates on a
    real ``QEvent.LanguageChange`` — including the new Cancel button (C-07),
    both its text AND its accessible name/description."""
    c = Macro_Controls()
    qtbot.addWidget(c)
    _lang_change(c)
    assert c.accessibleName() != ""
    assert c._record_button.accessibleName() != ""
    assert c._replay_button.accessibleName() != ""
    assert c._save_button.text() != "" and c._save_button.accessibleName() != ""
    assert c._load_button.text() != "" and c._load_button.accessibleName() != ""
    assert c._remove_button.text() != "" and c._remove_button.accessibleName() != ""
    assert c._cancel_button.text() != ""
    assert c._cancel_button.accessibleName() != ""
    assert c._cancel_button.accessibleDescription() != ""


def test_sc_ui_014_1_script_runner_retranslates(qtbot):
    """SC-UI-014-1: Script_Runner_Panel's label + run button re-populate."""
    p = Script_Runner_Panel()
    qtbot.addWidget(p)
    _lang_change(p)
    assert p.accessibleName() != ""
    assert p._run_button.text() != ""
    assert p._run_button.accessibleName() != ""
    assert p._editor.accessibleName() != ""


def test_sc_ui_014_1_batch_recolour_retranslates(qtbot):
    """SC-UI-014-1: Batch_Recolour_Panel's editors + apply button re-populate."""
    p = Batch_Recolour_Panel()
    qtbot.addWidget(p)
    _lang_change(p)
    assert p.accessibleName() != ""
    assert p._add_button.text() != "" and p._add_button.accessibleName() != ""
    assert p._remove_button.text() != "" and p._remove_button.accessibleName() != ""
    assert p._apply_button.text() != "" and p._apply_button.accessibleName() != ""
    assert p._mode_combo.accessibleName() != ""


def test_sc_ui_014_1_plugin_manager_retranslates(qtbot):
    """SC-UI-014-1: Plugin_Manager_Panel's list/permissions/action strings
    re-populate."""
    p = Plugin_Manager_Panel()
    qtbot.addWidget(p)
    _lang_change(p)
    assert p.accessibleName() != ""
    assert p._refresh_button.text() != "" and p._refresh_button.accessibleName() != ""
    assert p._install_button.text() != "" and p._install_button.accessibleName() != ""
    assert p._enable_button.text() != "" and p._enable_button.accessibleName() != ""
    assert p._disable_button.text() != "" and p._disable_button.accessibleName() != ""
    assert p._list.accessibleName() != ""
    assert p._permissions.accessibleName() != ""
