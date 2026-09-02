"""Branch/edge coverage for the Phase-9 visual-aids UI (REQ-P9-UI-001..010).

Exercises the presentation-plumbing paths the acceptance tests do not force —
file-dialog save/load handlers, calibration dialog, paint/wheel/change events,
fallback branches and error surfacing — so the ui coverage gate (>=90% line /
>=80% branch) holds on the Phase-9 additions. Both themes via the autouse fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QImage,
    QMouseEvent,
    QPainter,
    QPicture,
    QPixmap,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.grids import (
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
)
from pixelart_creator.logic.guides import Guide, GuideOrientation
from pixelart_creator.ui import reference_board as rb_module
from pixelart_creator.ui import timelapse_controls as tl_module
from pixelart_creator.ui.guides_rulers_overlay import (
    Guides_Overlay,
    Guides_Rulers_Overlay,
    Ruler_Strip,
)
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.real_size_preview_window import (
    Real_Size_Calibration_Dialog,
    Real_Size_Preview_Window,
)
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls


def _wheel(
    delta_y: int, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> QWheelEvent:
    return QWheelEvent(
        QPointF(1.0, 1.0),
        QPointF(1.0, 1.0),
        QPoint(0, delta_y),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


# --------------------------------------------------------------------------- #
# iso / perspective overlay edges                                             #
# --------------------------------------------------------------------------- #


def test_iso_geometry_helpers_and_empty_exposed():
    """set_scene_rect / boundingRect / empty-exposedRect fallback are exercised."""
    overlay = Iso_Grid_Overlay(QRectF(0, 0, 100, 100), IsoGridConfig(tile_width=32))
    overlay.set_scene_rect(QRectF(0, 0, 50, 50))
    assert overlay.boundingRect() == QRectF(0, 0, 50, 50)
    # Empty exposedRect (the default) falls back to the item rect, above the LOD gate.
    picture = QPicture()
    painter = QPainter(picture)
    from PySide6.QtGui import QTransform

    painter.setWorldTransform(QTransform.fromScale(2.0, 2.0))
    option = QStyleOptionGraphicsItem()  # exposedRect defaults empty
    overlay.paint(painter, option, None)
    painter.end()
    assert not picture.boundingRect().isNull()


def test_perspective_geometry_helpers():
    """set_scene_rect / boundingRect on the perspective overlay."""
    cfg = PerspectiveConfig(
        mode=1, vanishing_points=(VanishingPoint(position=(50.0, 50.0)),)
    )
    overlay = Perspective_Grid_Overlay(QRectF(0, 0, 100, 100), cfg)
    overlay.set_scene_rect(QRectF(0, 0, 40, 40))
    assert overlay.boundingRect() == QRectF(0, 0, 40, 40)


# --------------------------------------------------------------------------- #
# guides / rulers edges                                                       #
# --------------------------------------------------------------------------- #


def test_guides_overlay_management_and_paint(qtbot):
    """add/remove/clear/set_color/set_scene_rect + paint stroke a guide."""
    overlay = Guides_Overlay(QRectF(0, 0, 100, 100))
    g = overlay.add_guide(GuideOrientation.VERTICAL, 30.0)
    overlay.add_guide(GuideOrientation.HORIZONTAL, 40.0)
    overlay.set_color(overlay._color)
    overlay.set_scene_rect(QRectF(0, 0, 120, 120))
    assert len(overlay.guides()) == 2
    picture = QPicture()
    painter = QPainter(picture)
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(0, 0, 120, 120)
    overlay.paint(painter, option, None)
    painter.end()
    assert not picture.boundingRect().isNull()
    overlay.remove_guide(g)
    overlay.remove_guide(g)  # no-op second removal
    assert len(overlay.guides()) == 1
    overlay.clear_guides()
    assert overlay.guides() == ()


def test_ruler_paint_event_and_change_event(qtbot, make_view):
    """Ruler_Strip.paintEvent renders ticks; changeEvent retranslates."""
    view, _scene, _stack = make_view(64, 64)
    ruler = Ruler_Strip(GuideOrientation.HORIZONTAL, view)
    qtbot.addWidget(ruler)
    ruler.resize(200, 20)
    ruler.sync()
    image = QImage(200, 20, QImage.Format.Format_ARGB32)
    ruler.render(image)  # drives paintEvent with non-zero axis pixels
    ruler.set_cursor_readout(10.0, 5.0)
    from PySide6.QtWidgets import QApplication

    QApplication.sendEvent(ruler, QEvent(QEvent.Type.LanguageChange))
    assert ruler.accessibleName() != ""


def test_ruler_mouse_press_emits_guide_request(qtbot, make_view):
    """Ruler_Strip.mousePressEvent emits guideCreationRequested on a left click."""
    view, _scene, _stack = make_view(64, 64)
    ruler = Ruler_Strip(GuideOrientation.VERTICAL, view)
    qtbot.addWidget(ruler)
    ruler.resize(20, 200)
    seen: list = []
    ruler.guideCreationRequested.connect(lambda o, p: seen.append((o, p)))
    evt = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5.0, 40.0),
        QPointF(5.0, 40.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mousePressEvent(evt)
    assert seen and seen[0][0] is GuideOrientation.VERTICAL
    # A non-left button is passed through (no emit).
    seen.clear()
    evt_r = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5.0, 40.0),
        QPointF(5.0, 40.0),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mousePressEvent(evt_r)
    assert seen == []


def test_guides_controller_with_plain_view_fallbacks(qtbot, make_scene):
    """A view lacking zoom/zoomChanged/mapToScene exercises the fallback branches."""
    scene = make_scene(64, 64)
    plain = QWidget()
    qtbot.addWidget(plain)
    controller = Guides_Rulers_Overlay(plain, scene, QRectF(0, 0, 64, 64))
    # No zoomChanged signal on a plain widget -> the connect branch is skipped.
    controller.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)
    # _view_zoom falls back to 1.0; snap still works via the pure logic.
    assert controller.snap(11.0, 5.0) == (10.0, 5.0)
    controller.horizontal_ruler().set_cursor_readout(5.0, 5.0)  # _doc_offset fallback


# --------------------------------------------------------------------------- #
# real-size preview + calibration edges                                       #
# --------------------------------------------------------------------------- #


def test_calibration_dialog_measured_dpi_and_retranslate(qtbot):
    """The calibration dialog derives a DPI and retranslates without error."""
    from PySide6.QtWidgets import QApplication

    dialog = Real_Size_Calibration_Dialog()
    qtbot.addWidget(dialog)
    assert dialog.measured_dpi() > 0.0
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert dialog.windowTitle() != ""


def test_preview_open_calibration_applies_manual_dpi(qtbot, make_scene, monkeypatch):
    """_open_calibration applies the dialog's measured DPI on Accept."""
    win = Real_Size_Preview_Window(make_scene(16, 16), 72.0)
    qtbot.addWidget(win)
    monkeypatch.setattr(
        Real_Size_Calibration_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        Real_Size_Calibration_Dialog, "measured_dpi", lambda self: 120.0
    )
    win._open_calibration()
    assert win._manual_dpi == 120.0


def test_preview_show_event_and_screen_changed(qtbot, make_scene):
    """showEvent + _on_screen_changed recompute the scale without error."""
    win = Real_Size_Preview_Window(make_scene(16, 16))
    qtbot.addWidget(win)
    win.showEvent(QShowEvent())
    win._on_screen_changed(None)
    assert win.current_scale() > 0.0


def test_preview_invalid_ppi_falls_back_to_unit_scale(qtbot, make_scene):
    """current_scale swallows a PreviewError (bad PPI) and returns 1.0."""
    win = Real_Size_Preview_Window(make_scene(16, 16))
    qtbot.addWidget(win)
    win._doc_ppi = 0.0  # invalid -> real_size_scale raises PreviewError
    assert win.current_scale() == 1.0
    win.set_manual_dpi(0.0)  # clears the override (0 -> None)
    assert win._manual_dpi is None


# --------------------------------------------------------------------------- #
# reference board edges (file dialogs, cap, wheel, always-on-top, errors)     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def png_path(tmp_path):
    path = tmp_path / "ref.png"
    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(0xFF3366CC)
    assert img.save(str(path), "PNG")
    return str(path)


def test_reference_board_cap_reached(qtbot, png_path, monkeypatch):
    """Adding beyond MAX_REFERENCE_IMAGES surfaces a notice and adds nothing."""
    monkeypatch.setattr(rb_module, "MAX_REFERENCE_IMAGES", 1)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    board = Reference_Board()
    qtbot.addWidget(board)
    assert board.add_image(png_path) is not None
    assert board.add_image(png_path) is None  # cap hit
    assert len(board.items()) == 1


def test_reference_board_save_load_add_handlers(qtbot, tmp_path, png_path, monkeypatch):
    """_on_save / _on_load / _on_add_image drive through monkeypatched dialogs."""
    board = Reference_Board()
    qtbot.addWidget(board)
    board.add_image(png_path)
    target = str(tmp_path / "b.pixboard")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (target, ""))
    )
    board._on_save()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (target, ""))
    )
    board._on_load()
    assert len(board.items()) == 1
    # _on_add_image via the open dialog
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (png_path, ""))
    )
    board._on_add_image()
    assert len(board.items()) == 2


def test_reference_board_dialog_cancels_are_noops(qtbot, monkeypatch):
    """Cancelling the file dialogs (empty path) is a clean no-op."""
    board = Reference_Board()
    qtbot.addWidget(board)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    board._on_save()
    board._on_load()
    board._on_add_image()
    assert board.items() == []


def test_reference_board_load_error_surfaces(qtbot, tmp_path, monkeypatch):
    """A malformed board on load surfaces a warning (never a crash)."""
    board = Reference_Board()
    qtbot.addWidget(board)
    bad = tmp_path / "bad.pixboard"
    bad.write_text("{ not json", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), ""))
    )
    board._on_load()
    assert calls, "a malformed board file must surface a user-facing warning"


def test_reference_board_save_error_surfaces(qtbot, tmp_path, png_path, monkeypatch):
    """A failing save surfaces a warning (ReferenceBoardIOError path)."""
    board = Reference_Board()
    qtbot.addWidget(board)
    board.add_image(png_path)

    def _boom(*_a, **_k):
        raise rb_module.ReferenceBoardIOError("disk full")

    monkeypatch.setattr(rb_module, "save_board", _boom)
    calls: list = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "x.pixboard"), "")),
    )
    board._on_save()
    assert calls


def test_reference_board_wheel_clear_and_always_on_top(qtbot, png_path):
    """wheelEvent zooms, clear empties, always-on-top toggles the window flag."""
    board = Reference_Board()
    qtbot.addWidget(board)
    board.add_image(png_path)
    board.wheelEvent(_wheel(120))
    board.wheelEvent(_wheel(-120))
    board._on_always_on_top(True)
    board._on_always_on_top(False)
    board.clear()
    assert board.items() == []


def test_reference_board_apply_layout_skips_unloadable(qtbot, tmp_path, monkeypatch):
    """apply_layout tolerates an entry whose image cannot be loaded (skips it)."""
    from pixelart_creator.data.reference_board_io import (
        ReferenceBoardLayout,
        ReferenceImageEntry,
    )

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    board = Reference_Board()
    qtbot.addWidget(board)
    layout = ReferenceBoardLayout(
        images=(
            ReferenceImageEntry(
                image=str(tmp_path / "missing.png"),
                transform=(1.0, 0.0, 0.0, 1.0, 5.0, 5.0),
                crop=(0.0, 0.0, 8.0, 8.0),
                z_order=0,
            ),
        ),
    )
    board.apply_layout(layout)  # unloadable image -> add_image returns None -> skipped
    assert board.items() == []


# --------------------------------------------------------------------------- #
# timelapse controls edges (save/load handlers, budget-exceeded, rebind)      #
# --------------------------------------------------------------------------- #


def test_timelapse_save_load_handlers(qtbot, tmp_path, monkeypatch, make_document):
    """_on_save / _on_load drive through monkeypatched dialogs (round-trip).

    ``bind_undo_stack`` is called with a real ``document_getter`` (matching
    every other call site, including ``Main_Window._bind_visual_aids_to_active``)
    because the schema-2 payload builder ``_on_save`` drives
    (``_build_payload_tables``) legitimately requires one — without it, it
    raises ``TimelapseError`` and ``_on_save`` correctly shows a translated
    refusal modal, which blocks forever headless (nothing to dismiss it).
    That refusal is documented, intended behaviour, not a defect; the old
    two-argument ``bind_undo_stack(stack)`` call here was simply stale.
    """
    from PySide6.QtGui import QUndoCommand, QUndoStack

    class _Noop(QUndoCommand):
        def redo(self):
            pass

        def undo(self):
            pass

    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    stack = QUndoStack()
    document = make_document()
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls._record_button.setChecked(True)
    stack.push(_Noop())
    target = str(tmp_path / "c.pixtimelapse")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (target, ""))
    )
    controls._on_save()
    controls.reset()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (target, ""))
    )
    controls._on_load()
    assert controls.frame_count() == 1


def test_timelapse_dialog_cancels_are_noops(qtbot, monkeypatch):
    """Cancelling save/load (empty path) is a clean no-op."""
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    controls._on_save()
    controls._on_load()
    assert controls.frame_count() == 0


def test_timelapse_load_error_surfaces(qtbot, tmp_path, monkeypatch):
    """A malformed manifest on load surfaces a warning (never a crash)."""
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    bad = tmp_path / "bad.pixtimelapse"
    bad.write_text("{ not json", encoding="utf-8")
    calls: list = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), ""))
    )
    controls._on_load()
    assert calls


def test_timelapse_frame_budget_exceeded_stops_recording(qtbot, monkeypatch):
    """A record_frame budget error stops recording and surfaces a notice."""
    from PySide6.QtGui import QUndoCommand, QUndoStack

    from pixelart_creator.logic.timelapse import TimelapseError

    class _Noop(QUndoCommand):
        def redo(self):
            pass

        def undo(self):
            pass

    def _boom(*_a, **_k):
        raise TimelapseError("MAX_TIMELAPSE_FRAMES")

    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    monkeypatch.setattr(tl_module, "record_frame", _boom)
    calls: list = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    stack.push(_Noop())
    assert controls.is_recording() is False
    assert calls


def test_timelapse_rebind_disconnects_previous_stack(qtbot):
    """bind_undo_stack twice disconnects the previous stack (no double-record)."""
    from PySide6.QtGui import QUndoCommand, QUndoStack

    class _Noop(QUndoCommand):
        def redo(self):
            pass

        def undo(self):
            pass

    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    first = QUndoStack()
    second = QUndoStack()
    controls.bind_undo_stack(first)
    controls.bind_undo_stack(second)  # disconnect branch on the first
    controls._record_button.setChecked(True)
    first.push(_Noop())  # the old stack is disconnected -> no frame
    assert controls.frame_count() == 0
    second.push(_Noop())
    assert controls.frame_count() == 1


# --------------------------------------------------------------------------- #
# multi-view edges (wheel, change event, single close -> _forget)             #
# --------------------------------------------------------------------------- #


def test_document_view_wheel_and_change_event(qtbot, make_view):
    """Document_View.wheelEvent zooms under Shift; changeEvent retranslates.

    INVERTED 2026-08-31 (D-16/REQ-IS-UI-008,-009): a plain wheel notch
    on an extra document view now travels Favourites instead of zooming --
    D-16 extended the wheel split to all four scrollable surfaces, not only
    the two painting surfaces D-2 originally scoped. This test's job was
    always "prove an extra view zooms on a wheel notch"; it still does that
    job, now under the modifier the gesture actually lives on. The
    plain-wheel Favourites-travel side of this surface is proven fresh in
    ``test_input_scheme_pointer.py`` (D-16 extension test), not duplicated
    here.
    """
    from PySide6.QtWidgets import QApplication

    from pixelart_creator.ui.multi_view import Multi_View

    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    v = mv.open_view()
    qtbot.addWidget(v)
    v.wheelEvent(_wheel(120, Qt.KeyboardModifier.ShiftModifier))
    assert v.transform().m11() > 1.0
    v.wheelEvent(_wheel(-120, Qt.KeyboardModifier.ShiftModifier))
    QApplication.sendEvent(v, QEvent(QEvent.Type.LanguageChange))
    assert v.accessibleName() != ""
    mv.close_all()


def test_multi_view_single_close_forgets_view(make_view):
    """Deleting one view fires destroyed -> _forget, dropping it from the list.

    Headless there is no event loop, so a ``close()`` deferred-delete never fires;
    deleting the C++ object synchronously emits ``destroyed`` deterministically and
    exercises the ``_forget`` de-registration the window relies on."""
    import shiboken6

    from pixelart_creator.ui.multi_view import Multi_View

    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    v = mv.open_view()
    assert mv.count() == 1
    shiboken6.delete(v)  # synchronous delete -> destroyed -> _forget
    assert mv.count() == 0
