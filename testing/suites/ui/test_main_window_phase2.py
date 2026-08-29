"""Main-window Phase-2 wiring: guards, dialog paths, previews (REQ-P2-UI-008..015).

Covers the shell's Phase-2 control branches that the per-scenario acceptance tests
do not reach: no-open-document guards, cancelled transform/RotSprite dialogs, the
scale-error path, the tolerance/symmetry slots, invert-with-nothing-selected, the
RotSprite preview rendering (RGBA + indexed buffers, thumbnail down-scale), and the
Scale dialog factor<->size synchronisation. Both themes via the autouse fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox

from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui import main_window as mw
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
from pixelart_creator.ui.transform_dialog import Scale_Dialog

RED = (230, 30, 30, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_transform_slots_guard_when_no_document(qtbot):
    """With every tab closed, the transform/selection slots no-op safely."""
    win = _window(qtbot)
    win.close_document(0)  # close the sole document
    assert win.active_tab() is None
    # None of these should raise despite there being no active document.
    win._on_flip_horizontal()
    win._on_flip_vertical()
    win._on_rotate_cw()
    win._on_rotate_ccw()
    win._on_scale()
    win._on_rotsprite()
    win._on_select_all()
    win._on_deselect()
    win._on_invert_selection()
    win._on_clear_selection()
    assert win._rotsprite_preview(30.0) is None  # preview also guards


def test_cancelled_dialogs_push_no_command(qtbot, monkeypatch):
    """Cancelling the scale / RotSprite dialog makes no change (rejected path)."""
    win = _window(qtbot)
    record = win.active_tab()
    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(
        RotSprite_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    win._on_scale()
    win._on_rotsprite()
    assert record.stack.count() == 0


def test_scale_error_is_reported_not_raised(qtbot, monkeypatch):
    """A non-positive scale target is caught and surfaced, not raised."""
    win = _window(qtbot)
    record = win.active_tab()
    warnings = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (0, 0))
    win._on_scale()  # scale_nearest(0,0) -> TransformError -> warning
    assert warnings  # the error was reported
    assert record.stack.count() == 0  # nothing committed


def test_tolerance_and_symmetry_slots(qtbot):
    """The tolerance spin + symmetry combo drive their shell slots."""
    win = _window(qtbot)
    win._on_tolerance_changed(42)
    assert win._wand_tool.tolerance == 42
    win._on_symmetry_axis_changed(SymmetryAxis.BOTH)
    assert win.active_tab().view.symmetry_axis() is SymmetryAxis.BOTH


def test_invert_with_nothing_selected_selects_all(qtbot):
    """Inverting when nothing is selected yields a full-buffer selection."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.view.active_selection() is None
    win._on_invert_selection()
    mask = record.view.active_selection()
    buf = record.scene.active_buffer()
    assert mask is not None and mask.count() == buf.width * buf.height


def test_rotsprite_preview_renders_rgba(qtbot):
    """The RotSprite preview renders a non-null QImage for the active RGBA buffer."""
    win = _window(qtbot)
    win.active_tab().scene.active_buffer().set_pixel(2, 2, RED)
    image = win._rotsprite_preview(20.0)
    assert image is not None and not image.isNull()


def test_buffer_to_qimage_handles_indexed_and_thumbnail_downscale(qtbot):
    """Indexed -> RGBA image conversion and >128px thumbnail down-scale are covered."""
    _win = _window(qtbot)
    indexed = PixelBuffer(4, 4, ColorMode.INDEXED)
    indexed.set_pixel(0, 0, 1)
    image = Main_Window._buffer_to_qimage(indexed, [(0, 0, 0, 255), (255, 0, 0, 255)])
    assert not image.isNull()
    big = PixelBuffer(200, 20, ColorMode.RGBA)  # longest edge > 128 -> down-scaled
    thumb = Main_Window._preview_thumbnail(big)
    assert max(thumb.width, thumb.height) <= 128


def test_scale_dialog_factor_size_sync(qtbot):
    """The scale dialog keeps factor and width/height in sync (both directions)."""
    dialog = Scale_Dialog(16, 16)
    qtbot.addWidget(dialog)
    dialog._factor.setValue(2.0)  # factor -> size
    assert dialog.target_size() == (32, 32)
    dialog._width.setValue(8)  # size -> factor
    assert abs(dialog._factor.value() - 0.5) < 1e-6
    assert dialog.accessibleName() != ""


# =========================================================================== #
# REQ-CSD-UI-004 (canvas-scale-defects `tasks.md` T16, DEFECT):               #
# the Scale dialog's factor and target fields never contradict each other     #
# =========================================================================== #


def test_sc_csd_u004_1_the_8k_ceiling_factor_agrees_with_the_target(qtbot):
    """SC-CSD-U004-1 (DEFECT): seeded at 64x64, typing 7680 into the width
    field yields a factor of EXACTLY 120.0 (not clamped), and `target_size()`
    returns width 7680 -- the two never disagree.

    Pre-change: `SCALE_MAX_FACTOR = 64.0` capped the factor spin box, so the
    displayed factor silently clamped to 64.00 while `target_size()` still
    (correctly) returned the width field's 7680 -- a dialog that visibly
    disagreed with what it was about to submit. Asserted on `spin.value()`,
    not rendered text (`plan.md` §5.5, `analysis.md` F-2: the factor now
    carries 4 decimals, so "reads 120.00" describes the NUMBER 120, not a
    2-decimal string).
    """
    dialog = Scale_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._width.setValue(7680)
    assert abs(dialog._factor.value() - 120.0) < 1e-6
    assert dialog.target_size()[0] == 7680


def test_sc_csd_u004_2_a_factor_reaching_the_ceiling_is_selectable(qtbot):
    """SC-CSD-U004-2 (DEFECT): seeded at 64x64, setting the factor to 67.50
    yields target fields of EXACTLY 4320 x 4320 (the real 8K-height ceiling
    from this source), not the old factor-capped 4096 x 4096.

    Pre-change: the factor spin box's maximum was `SCALE_MAX_FACTOR = 64.0`,
    so Qt clamped 67.50 down to 64.00 and the target fields read 4096 x 4096
    instead of 4320 x 4320.
    """
    dialog = Scale_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._factor.setValue(67.5)
    assert dialog._width.value() == 4320
    assert dialog._height.value() == 4320


def test_sc_csd_u004_range_covers_the_full_ceiling_for_the_default_document(qtbot):
    """The factor range itself reaches the platform ceiling from the default
    64x64 document (`MAX_CANVAS_WIDTH / 64 == 120.0`) -- the range is not
    merely reachable by an off-range setValue clamp trick."""
    from pixelart_creator.logic.constants import MAX_CANVAS_WIDTH

    dialog = Scale_Dialog(64, 64)
    qtbot.addWidget(dialog)
    assert dialog._factor.maximum() >= MAX_CANVAS_WIDTH / 64
