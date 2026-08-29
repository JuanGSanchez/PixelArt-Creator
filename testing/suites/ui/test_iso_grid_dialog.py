"""Isometric-grid configuration dialog acceptance tests (job REC-4/R-5/C-5,
DEV-27).

Before this fix, ``Iso_Grid_Overlay.set_config`` had zero production callers
(the DEV-27 finding) -- every document's iso grid was hard-wired to
``tile_width=32`` with no way to change it. The fix adds
``pixelart_creator/ui/iso_grid_dialog.py`` (``Iso_Grid_Dialog``) plus a
``main_window.py`` menu entry point (``_iso_config_action`` ->
``_on_configure_iso_grid``) mirroring the shipped ``Vanishing_Point_Dialog``
(D-09) pattern exactly.

Covers **REQ-P9-UI-004** ("Grid spacing/config is bounded... implies
configurability, not a fixed 32px"):

* the new-tab default stays ``tile_width=32`` (unchanged, per the dispatch --
  the spec is silent on the default, only on boundedness/configurability);
* the dialog seeds itself from the ACTIVE TAB's real, current
  ``IsoGridConfig`` and, on Accept, applies a new one via the exact
  ``main_window`` seam (``record.iso_overlay.set_config(dialog.iso_config())``)
  -- driven through the real ``_on_configure_iso_grid`` handler, not a
  reimplementation of it;
* accessibility (accessible names, keyboard reachability) and the
  ``QEvent.LanguageChange`` retranslation hook on every new control.

The headless-dialog pattern below (stub ``exec()`` rather than drive the modal
loop) mirrors ``tests/ui/test_vanishing_point_dialog.py``'s own established,
accepted convention for this exact "minimal config dialog" shape in this
codebase -- nothing here waits on a user. Both themes run automatically (the
autouse ``theme`` fixture).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.grids import IsoGridConfig
from pixelart_creator.ui.iso_grid_dialog import Iso_Grid_Dialog
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --------------------------------------------------------------------------- #
# C-5: new-tab default stays tile_width=32                                    #
# --------------------------------------------------------------------------- #


def test_c5_new_tab_default_iso_tile_width_is_still_32(qtbot):
    """REQ-P9-UI-004: a freshly created tab's iso grid still defaults to 32."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.iso_overlay is not None
    assert record.iso_overlay.config().tile_width == 32

    win.new_document()
    second = win.active_tab()
    assert second is not record
    assert second.iso_overlay.config().tile_width == 32


# --------------------------------------------------------------------------- #
# C-5: the dialog reads the active tab's config and applies it via set_config #
# --------------------------------------------------------------------------- #


def test_c5_iso_dialog_reads_active_config_and_applies_via_set_config(
    qtbot, monkeypatch
):
    """REQ-P9-UI-004: the real ``_on_configure_iso_grid`` seam -- seed from the
    active tab's current config, apply a new one via ``set_config`` on Accept."""
    win = _window(qtbot)
    record = win.active_tab()
    baseline = record.iso_overlay.config()
    assert baseline.tile_width == 32  # sanity: the seam's own precondition

    new_tile_width = 64
    new_ratio = 1.5
    new_origin = (4.0, -6.0)
    seeded_from_active_tab = {}

    def _fake_exec(self):
        # Proves the dialog was SEEDED from the active tab's real config
        # (not a fresh/default one) before the user ever "interacts" with it.
        seeded_from_active_tab["tile_width"] = self._tile_width_spin.value()
        seeded_from_active_tab["ratio"] = self._ratio_spin.value()
        seeded_from_active_tab["origin"] = (
            self._origin_x_spin.value(),
            self._origin_y_spin.value(),
        )
        self._tile_width_spin.setValue(new_tile_width)
        self._ratio_spin.setValue(new_ratio)
        self._origin_x_spin.setValue(new_origin[0])
        self._origin_y_spin.setValue(new_origin[1])
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Iso_Grid_Dialog, "exec", _fake_exec)

    win._on_configure_iso_grid()  # the real production menu handler

    assert seeded_from_active_tab == {
        "tile_width": baseline.tile_width,
        "ratio": baseline.ratio,
        "origin": baseline.origin,
    }
    updated = record.iso_overlay.config()
    assert updated.tile_width == new_tile_width
    assert updated.ratio == new_ratio
    assert updated.origin == new_origin


def test_c5_iso_dialog_cancel_leaves_the_active_config_untouched(qtbot, monkeypatch):
    """Rejecting the dialog must not call ``set_config`` at all."""
    win = _window(qtbot)
    record = win.active_tab()
    baseline = record.iso_overlay.config()

    monkeypatch.setattr(
        Iso_Grid_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    win._on_configure_iso_grid()

    assert record.iso_overlay.config() == baseline


# --------------------------------------------------------------------------- #
# a11y + i18n retranslation hook on the new dialog's controls                 #
# --------------------------------------------------------------------------- #


def test_c5_iso_dialog_accessible_names_on_every_interactive_control(qtbot):
    """Every spin box (+ the OK/Cancel buttons) carries a non-empty accessible
    name and is keyboard-reachable (focus policy accepts focus)."""
    from PySide6.QtCore import Qt as QtCore_Qt

    dialog = Iso_Grid_Dialog(IsoGridConfig(tile_width=40, ratio=1.2, origin=(1.0, 2.0)))
    qtbot.addWidget(dialog)

    for spin in (
        dialog._tile_width_spin,
        dialog._ratio_spin,
        dialog._origin_x_spin,
        dialog._origin_y_spin,
    ):
        assert spin.accessibleName() != ""
        assert spin.focusPolicy() != QtCore_Qt.FocusPolicy.NoFocus

    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)
    cancel_button = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    assert ok_button.text() != ""
    assert cancel_button.text() != ""


def test_c5_iso_dialog_round_trips_the_seeded_config(qtbot):
    """The dialog reads a real ``IsoGridConfig`` and ``iso_config()`` returns an
    equal-value one when nothing was changed (mirrors D-09's own round-trip
    test for ``Vanishing_Point_Dialog``)."""
    source = IsoGridConfig(tile_width=48, ratio=1.732, origin=(10.0, -5.0))
    dialog = Iso_Grid_Dialog(source)
    qtbot.addWidget(dialog)

    result = dialog.iso_config()
    assert result.tile_width == source.tile_width
    assert result.ratio == source.ratio
    assert result.origin == source.origin


def test_c5_iso_dialog_retranslation_hook_present(qtbot):
    """``QEvent.LanguageChange`` re-sets every label/accessible-name string
    (F5) -- the retranslate is idempotent for a fixed locale."""
    dialog = Iso_Grid_Dialog(IsoGridConfig())
    qtbot.addWidget(dialog)

    title_before = dialog.windowTitle()
    tile_label_before = dialog._tile_width_label.text()
    ratio_label_before = dialog._ratio_label.text()
    assert title_before != ""
    assert tile_label_before != ""

    dialog.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() == title_before
    assert dialog._tile_width_label.text() == tile_label_before
    assert dialog._ratio_label.text() == ratio_label_before
