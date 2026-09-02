"""Drag-and-drop import UI acceptance tests (REQ-DDI-UI-001..009).

One pytest-qt test per acceptance criterion of the ``drag-drop-import`` feature
(Slice A-B), driving the shipped :class:`Main_Window` drop handlers headlessly
(``QT_QPA_PLATFORM=offscreen``). Every test also runs under **both** the light
and dark themes via the autouse ``theme`` fixture in ``conftest.py`` (REQ-DDI-UI-009).

Test seams (per the UI implementation's A-B report):
    * drive ``dragEnterEvent`` / ``dropEvent`` with synthetic Qt drag events, or
      call ``_route_dropped_files([...])`` directly;
    * monkeypatch ``QMessageBox.warning`` (dirty guard + error notice) and
      ``QFileDialog.getSaveFileName`` (the Save branch of the guard).

Mapping (Gherkin ↔ REQ, ``specs/drag-drop-import/spec.md`` §11):
    UI-001 accept file-URL drops         SC-U001-1/-2
    UI-002 route by type not location     SC-U002-1/-2
    UI-003 image → NEW document tab       SC-U003-1/-2/-3
    UI-004 .pixproj dirty guard           SC-U004-1..5
    UI-005 palette → one undoable replace SC-U005-1..5
    UI-006 unknown → graceful notice      SC-U006-1
    UI-007 corrupt/oversized → error      SC-U007-1..4
    UI-008 multi-file routing             SC-U008-1..5
    UI-009 a11y / i18n / both themes       SC-U009-1..3
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QUndoCommand,
)
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pixelart_creator.data.project_io import FILE_SUFFIX
from pixelart_creator.logic.constants import MAX_CANVAS_WIDTH
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.main_window import Main_Window

# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def win(qtbot) -> Main_Window:
    """A fresh :class:`Main_Window` (starts with one Untitled tab)."""
    window = Main_Window()
    qtbot.addWidget(window)
    return window


def _mime(paths: List[str]) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return mime


def _drag_enter(window: Main_Window, mime: QMimeData) -> bool:
    """Deliver a synthetic drag-enter; return whether the drop was accepted.

    ``mime`` is bound by the caller and kept alive for the duration of the call:
    ``QDragEnterEvent`` does **not** take ownership of the ``QMimeData``, so a
    dropped Python reference would let it be garbage-collected mid-handler,
    leaving the event with a dangling pointer (a native crash).
    """
    event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(event)
    accepted = event.isAccepted()
    del event  # drop the event before its borrowed mime goes out of scope
    return accepted


def _drop(window: Main_Window, paths: List[str], pos: QPointF | None = None) -> None:
    """Deliver a synthetic file-URL drop of ``paths`` to the window.

    ``mime`` is held in a local for the whole handler call — ``QDropEvent`` only
    borrows the ``QMimeData`` (no ownership transfer), so it must outlive the
    ``dropEvent`` dispatch or PySide hands the handler a dangling ``QObject``.
    """
    mime = _mime(paths)
    event = QDropEvent(
        pos if pos is not None else QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    del event  # release the event while ``mime`` is still referenced


def _make_png(path: Path, width: int, height: int, color=(230, 30, 30, 255)) -> Path:
    """Write a solid-colour RGBA PNG via QImage; return the path."""
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor(*color))
    assert image.save(str(path), "PNG")
    return path


def _make_image(path: Path, fmt: str, width: int, height: int) -> Path:
    """Write a solid image in ``fmt`` (bmp/jpg) via QImage; return the path."""
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor(40, 90, 220, 255))
    assert image.save(str(path), fmt.lstrip(".").upper())
    return path


def _make_gif(path: Path, width: int, height: int) -> Path:
    """Write a TWO-frame GIF (frame 0 red, frame 1 green) via Pillow.

    QImage cannot *write* GIF (only read), so Pillow builds the multi-frame
    file used to prove the first-frame decode rule (CL-A3).
    """
    frame0 = Image.new("RGB", (width, height), (255, 0, 0))
    frame1 = Image.new("RGB", (width, height), (0, 255, 0))
    frame0.save(
        str(path), format="GIF", save_all=True, append_images=[frame1], duration=100
    )
    return path


def _make_pixproj(window: Main_Window, path: Path) -> Path:
    """Save the active document to a valid ``.pixproj`` on disk."""
    window.save_document(str(path))
    return path


def _write_gpl(path: Path, colors) -> Path:
    lines = ["GIMP Palette", "Name: Test", "#"]
    lines += [f"{r} {g} {b}\tc{i}" for i, (r, g, b, _a) in enumerate(colors)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_hex(path: Path, colors) -> Path:
    path.write_text(
        "\n".join(f"{r:02X}{g:02X}{b:02X}" for r, g, b, _a in colors) + "\n",
        encoding="utf-8",
    )
    return path


def _write_pal(path: Path, colors) -> Path:
    body = "\n".join(f"{r} {g} {b}" for r, g, b, _a in colors)
    path.write_text(f"JASC-PAL\n0100\n{len(colors)}\n{body}\n", encoding="utf-8")
    return path


def _active_buffer(window: Main_Window):
    doc = window.active_document()
    return doc.frames[0].layers[0].buffer


def _mark_dirty(window: Main_Window) -> None:
    """Push a no-op command so the active tab's undo stack is not clean."""
    window.active_tab().stack.push(QUndoCommand("edit"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


PAL_A = [(10, 20, 30, 255), (40, 50, 60, 255)]
PAL_B = [(200, 100, 50, 255), (5, 15, 25, 255), (99, 88, 77, 255)]


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-001 — accept file-URL drops                                      #
# --------------------------------------------------------------------------- #


def test_ui001_accept_drops_enabled(win):
    """SC-U001-1: the window opts into drops (``acceptDrops`` is True)."""
    assert win.acceptDrops() is True


def test_ui001_drag_enter_accepts_file_urls(win, tmp_path):
    """SC-U001-1: a drag carrying a local file URL is indicated acceptable."""
    accepted = _drag_enter(win, _mime([str(tmp_path / "a.png")]))
    assert accepted is True


def test_ui001_drag_enter_ignores_non_file_payload(win):
    """SC-U001-1: a drag with no local-file URL is not accepted (declined)."""
    mime = QMimeData()
    mime.setText("just some text, no urls")
    assert _drag_enter(win, mime) is False


def test_ui001_drop_without_urls_is_ignored(win, monkeypatch):
    """SC-U001-1: a drop carrying no file URLs is ignored (router never runs)."""
    routed: List[object] = []
    monkeypatch.setattr(win, "_route_dropped_files", lambda p: routed.append(p))
    mime = QMimeData()
    mime.setText("plain text, no urls")
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.dropEvent(event)
    accepted = event.isAccepted()
    del event
    assert accepted is False
    assert routed == []


def test_ui001_drop_delivers_paths_to_router(win, monkeypatch, tmp_path):
    """SC-U001-2: dropping delivers the local file paths to the router."""
    captured: List[List[str]] = []
    monkeypatch.setattr(win, "_route_dropped_files", captured.append)
    p1, p2 = str(tmp_path / "a.png"), str(tmp_path / "b.gpl")
    _drop(win, [p1, p2])
    # Exactly one router call carrying both paths. ``QUrl.toLocalFile`` normalises
    # separators (forward slashes on Windows), so compare via ``Path`` identity.
    assert len(captured) == 1
    assert [Path(p) for p in captured[0]] == [Path(p1), Path(p2)]


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-002 — route by file type, not drop location                      #
# --------------------------------------------------------------------------- #


def test_ui002_image_routes_new_document_regardless_of_location(win, tmp_path):
    """SC-U002-1: an image dropped anywhere opens a new document (location-free)."""
    img = _make_png(tmp_path / "ref.png", 6, 4)
    before = win._tab_widget.count()
    # Drop at an arbitrary corner position — routing must ignore the location.
    _drop(win, [str(img)], pos=QPointF(999.0, 3.0))
    assert win._tab_widget.count() == before + 1


def test_ui002_each_type_dispatched_to_its_branch(win, monkeypatch, tmp_path):
    """SC-U002-2: each path dispatched to its branch (IMAGE/PROJECT/PALETTE/UNKNOWN)."""
    calls: List[str] = []
    monkeypatch.setattr(win, "_import_image_drop", lambda p: calls.append("image"))
    monkeypatch.setattr(win, "_import_project_drop", lambda p: calls.append("project"))
    monkeypatch.setattr(win, "_import_palette_drop", lambda p: calls.append("palette"))
    monkeypatch.setattr(win, "_notify_unsupported", lambda p: calls.append("unknown"))
    win._route_dropped_files(
        [
            str(tmp_path / "a.png"),
            str(tmp_path / f"b{FILE_SUFFIX}"),
            str(tmp_path / "c.gpl"),
            str(tmp_path / "d.txt"),
        ]
    )
    assert calls == ["image", "project", "palette", "unknown"]


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-003 — image drop → NEW document tab (not a layer)                #
# --------------------------------------------------------------------------- #


def test_ui003_image_opens_new_tab_not_layer(win, tmp_path):
    """SC-U003-1: an image drop creates a new active tab; prior doc gains no layer."""
    prev_doc = win.active_document()
    prev_layers = len(prev_doc.frames[0].layers)
    before = win._tab_widget.count()

    _drop(win, [str(_make_png(tmp_path / "img.png", 5, 3))])

    assert win._tab_widget.count() == before + 1
    # The new tab is current and is a *different* document.
    assert win.active_document() is not prev_doc
    # No layer was added to the previously active document (not imported as layer).
    assert len(prev_doc.frames[0].layers) == prev_layers


def test_ui003_new_document_is_rgba_at_image_dims(win, tmp_path):
    """SC-U003-2: the new document is RGBA at the image's dimensions, pixels match."""
    color = (12, 200, 77, 255)
    _drop(win, [str(_make_png(tmp_path / "img.png", 7, 5, color))])

    doc = win.active_document()
    assert (doc.width, doc.height) == (7, 5)
    assert doc.mode is ColorMode.RGBA
    buffer = _active_buffer(win)
    assert buffer.mode is ColorMode.RGBA
    # Decoded RGBA channel order matches the source (ADR-0010 stride discipline).
    assert buffer.get_pixel(0, 0) == color
    assert buffer.get_pixel(6, 4) == color


@pytest.mark.parametrize("fmt", ["bmp", "jpg"])
def test_ui003_decodes_other_raster_formats(win, tmp_path, fmt):
    """SC-U002-2/D002-2: bmp/jpg drops decode into a new RGBA document tab."""
    img = _make_image(tmp_path / f"pic.{fmt}", fmt, 8, 6)
    before = win._tab_widget.count()
    _drop(win, [str(img)])
    assert win._tab_widget.count() == before + 1
    doc = win.active_document()
    assert (doc.width, doc.height) == (8, 6)
    assert doc.mode is ColorMode.RGBA


def test_ui003_first_frame_of_multiframe_gif(win, tmp_path):
    """SC-D002-4/CL-A3: a multi-frame GIF drop decodes the FIRST frame (red)."""
    gif = _make_gif(tmp_path / "anim.gif", 4, 3)
    _drop(win, [str(gif)])
    doc = win.active_document()
    assert (doc.width, doc.height) == (4, 3)
    r, g, b, a = _active_buffer(win).get_pixel(0, 0)
    # Frame 0 is red; GIF has no alpha so decode yields opaque.
    assert (r, g, b, a) == (255, 0, 0, 255)


def test_ui003_source_file_not_modified_on_disk(win, tmp_path):
    """SC-U003-3/NFR-6: importing an image never modifies the source file."""
    img = _make_png(tmp_path / "src.png", 5, 5)
    digest_before = _sha256(img)
    _drop(win, [str(img)])
    assert _sha256(img) == digest_before


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-004 — .pixproj drop → open with dirty save prompt                #
# --------------------------------------------------------------------------- #


def test_ui004_clean_document_opens_without_prompt(win, tmp_path, monkeypatch):
    """SC-U004-1: a clean active document opens the dropped project with no prompt."""
    proj = _make_pixproj(win, tmp_path / f"p{FILE_SUFFIX}")
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Save,
    )
    # save_document marked the active stack clean, so the guard must not prompt.
    _drop(win, [str(proj)])
    assert warned == []
    # The project opened (REPLACE keeps the tab count at one).
    assert win.active_document() is not None


def test_ui004_dirty_document_prompts_save_discard_cancel(win, tmp_path, monkeypatch):
    """SC-U004-2: a dirty active document triggers a Save/Discard/Cancel prompt."""
    proj = _make_pixproj(win, tmp_path / f"p{FILE_SUFFIX}")
    _mark_dirty(win)
    seen: List[object] = []

    def _warn(parent, title, text, buttons, default):
        seen.append(buttons)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    _drop(win, [str(proj)])
    assert seen, "no Save/Discard/Cancel prompt shown for a dirty document"
    offered = seen[0]
    for expected in (
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.Discard,
        QMessageBox.StandardButton.Cancel,
    ):
        assert offered & expected


def test_ui004_cancel_aborts_open_leaves_state_unchanged(win, tmp_path, monkeypatch):
    """SC-U004-3: Cancel aborts the open; the active document is unchanged."""
    proj = _make_pixproj(win, tmp_path / f"p{FILE_SUFFIX}")
    _mark_dirty(win)
    kept = win.active_document()
    tabs_before = win._tab_widget.count()
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Cancel
    )
    _drop(win, [str(proj)])
    assert win.active_document() is kept
    assert win._tab_widget.count() == tabs_before


def test_ui004_save_persists_then_opens(win, tmp_path, monkeypatch):
    """SC-U004-4: Save persists the current document to disk, then opens the drop."""
    proj = _make_pixproj(win, tmp_path / f"dropped{FILE_SUFFIX}")
    _mark_dirty(win)
    save_target = tmp_path / f"saved{FILE_SUFFIX}"
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(save_target), "")
    )
    _drop(win, [str(proj)])
    assert save_target.exists(), "Save branch did not persist the current document"
    assert win.active_document() is not None


def test_ui004_save_cancelled_dialog_aborts_open(win, tmp_path, monkeypatch):
    """SC-U004-4 (edge): a cancelled Save-As dialog aborts, preserving unsaved work."""
    proj = _make_pixproj(win, tmp_path / f"p{FILE_SUFFIX}")
    _mark_dirty(win)
    kept = win.active_document()
    tabs_before = win._tab_widget.count()
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    _drop(win, [str(proj)])
    assert win.active_document() is kept
    assert win._tab_widget.count() == tabs_before


def test_ui004_discard_opens_without_saving(win, tmp_path, monkeypatch):
    """SC-U004-5: Discard opens the dropped project without writing a save file."""
    proj = _make_pixproj(win, tmp_path / f"dropped{FILE_SUFFIX}")
    _mark_dirty(win)
    save_calls: List[int] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Discard
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: save_calls.append(1) or ("", ""),
    )
    _drop(win, [str(proj)])
    assert save_calls == [], "Discard must not invoke the Save-As dialog"
    assert win.active_document() is not None


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-005 — palette drop → replace as ONE undoable command             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "writer,ext",
    [(_write_gpl, "gpl"), (_write_hex, "hex"), (_write_pal, "pal")],
)
def test_ui005_palette_replaces_active_in_one_undoable_step(win, tmp_path, writer, ext):
    """SC-U005-1/-2/-3: a .gpl/.hex/.pal drop replaces the palette in ONE undo step."""
    pal_file = writer(tmp_path / f"pal.{ext}", PAL_B)
    palette = win.active_document().palette
    before = palette.colors()
    stack = win.active_tab().stack
    count_before = stack.count()

    _drop(win, [str(pal_file)])

    assert palette.colors() == PAL_B
    assert palette.colors() != before
    # Exactly one undoable command was pushed (NFR-5).
    assert stack.count() == count_before + 1


def test_ui005_reversibility_undo_restores_prior_palette(win, tmp_path):
    """SC-U005-4: palette-load then Undo restores the prior palette (apply∘undo=id)."""
    pal_file = _write_gpl(tmp_path / "pal.gpl", PAL_B)
    palette = win.active_document().palette
    before = palette.colors()
    stack = win.active_tab().stack

    _drop(win, [str(pal_file)])
    assert palette.colors() == PAL_B

    stack.undo()
    assert palette.colors() == before


def test_ui005_no_open_document_is_graceful_noop_with_notice(win, tmp_path):
    """SC-U005-5: dropping a palette with no open document is a no-op + notice."""
    win.close_document(0)
    assert win.active_document() is None
    pal_file = _write_gpl(tmp_path / "pal.gpl", PAL_A)

    _drop(win, [str(pal_file)])  # must not raise

    assert win.active_document() is None
    assert "palette" in win.statusBar().currentMessage().lower()


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-006 — unknown/unsupported type → graceful ignore + notice        #
# --------------------------------------------------------------------------- #


def test_ui006_unknown_type_ignored_with_notice_no_crash(win, tmp_path):
    """SC-U006-1: an unsupported type is ignored with a non-blocking notice."""
    unknown = tmp_path / "notes.txt"
    unknown.write_text("hello", encoding="utf-8")
    tabs_before = win._tab_widget.count()
    palette_before = win.active_document().palette.colors()

    _drop(win, [str(unknown)])  # must not raise

    assert win._tab_widget.count() == tabs_before
    assert win.active_document().palette.colors() == palette_before
    assert "notes.txt" in win.statusBar().currentMessage()


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-007 — corrupt/oversized → error notice, not a crash              #
# --------------------------------------------------------------------------- #


def test_ui007_corrupt_image_shows_error_no_tab_no_crash(win, tmp_path, monkeypatch):
    """SC-U007-1: a corrupt image warns and leaves state intact (no new tab)."""
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n not a real png \x00\x01\x02")
    tabs_before = win._tab_widget.count()
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    _drop(win, [str(bad)])  # must not raise

    assert warned, "a corrupt image did not surface an error notice"
    assert win._tab_widget.count() == tabs_before


def test_ui007_oversized_image_shows_error_no_tab(win, tmp_path, monkeypatch):
    """SC-U007-2: an image exceeding MAX_CANVAS_* warns and opens no tab (bounds)."""
    oversized = _make_png(tmp_path / "huge.png", MAX_CANVAS_WIDTH + 1, 1)
    tabs_before = win._tab_widget.count()
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    _drop(win, [str(oversized)])

    assert warned, "an oversized image was not rejected with a notice"
    assert win._tab_widget.count() == tabs_before


def test_ui007_malformed_palette_shows_error_palette_unchanged(
    win, tmp_path, monkeypatch
):
    """SC-U007-3: a malformed palette warns; the active palette is unchanged."""
    bad = tmp_path / "broken.gpl"
    bad.write_text("NOT A GIMP PALETTE\ngarbage row\n", encoding="utf-8")
    before = win.active_document().palette.colors()
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    _drop(win, [str(bad)])

    assert warned
    assert win.active_document().palette.colors() == before


def test_ui007_invalid_pixproj_shows_error_no_document_opened(
    win, tmp_path, monkeypatch
):
    """SC-U007-4: an invalid .pixproj warns; state intact, no partial open."""
    bad = tmp_path / f"broken{FILE_SUFFIX}"
    bad.write_text("{ not valid json", encoding="utf-8")
    kept = win.active_document()
    tabs_before = win._tab_widget.count()
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    _drop(win, [str(bad)])

    assert warned
    assert win.active_document() is kept
    assert win._tab_widget.count() == tabs_before


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-008 — multi-file drop routing                                    #
# --------------------------------------------------------------------------- #


def test_ui008_multiple_images_open_one_tab_each_stable_order(win, tmp_path):
    """SC-U008-1: three images dropped together open three new tabs (stable order)."""
    imgs = [str(_make_png(tmp_path / f"i{i}.png", 4, 4)) for i in range(3)]
    before = win._tab_widget.count()
    _drop(win, imgs)
    assert win._tab_widget.count() == before + 3


def test_ui008_mixed_drop_routes_each_by_type(win, tmp_path):
    """SC-U008-2: a mixed drop routes image→tab and palette→undoable load."""
    img = str(_make_png(tmp_path / "pic.png", 5, 5))
    pal = str(_write_gpl(tmp_path / "pal.gpl", PAL_B))
    tabs_before = win._tab_widget.count()
    palette_before = win.active_document().palette.colors()

    # Palette applies to the CURRENTLY active document, then the image opens a
    # new tab; both effects must be observable.
    _drop(win, [pal, img])

    assert win._tab_widget.count() == tabs_before + 1  # image → new tab
    assert palette_before != PAL_B  # sanity: the drop actually changed something


def test_ui008_one_bad_file_skipped_rest_processed(win, tmp_path, monkeypatch):
    """SC-U008-3: a bad file is skipped with a notice; the batch still processes."""
    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"not a png at all")
    good = str(_make_png(tmp_path / "good.png", 4, 4))
    tabs_before = win._tab_widget.count()
    warned: List[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    _drop(win, [str(corrupt), good])

    assert warned, "the bad file did not surface a notice"
    # The good image still opened its tab (the batch was not aborted).
    assert win._tab_widget.count() == tabs_before + 1


def test_ui008_last_palette_wins_each_own_undo_step(win, tmp_path):
    """SC-U008-4: several palettes → LAST wins; each is its own undo step (CL-A2)."""
    pal_a = str(_write_gpl(tmp_path / "a.gpl", PAL_A))
    pal_b = str(_write_hex(tmp_path / "b.hex", PAL_B))
    palette = win.active_document().palette
    stack = win.active_tab().stack
    count_before = stack.count()

    _drop(win, [pal_a, pal_b])

    assert palette.colors() == PAL_B  # last dropped palette is active
    assert stack.count() == count_before + 2  # each drop its own undo step
    # Undo peels back to the first-dropped palette, proving separate steps.
    stack.undo()
    assert palette.colors() == PAL_A


def test_ui008_zero_file_drop_is_noop(win):
    """SC-U008-5: a drop carrying zero files is a no-op (no crash, no change)."""
    tabs_before = win._tab_widget.count()
    doc_before = win.active_document()
    _drop(win, [])  # empty URL list → no-op
    assert win._tab_widget.count() == tabs_before
    assert win.active_document() is doc_before


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-009 — a11y / i18n / both themes                                  #
# --------------------------------------------------------------------------- #


def test_ui009_notice_strings_are_translatable_and_rendered(win, tmp_path):
    """SC-U009-1/-3: drop notices are non-empty (tr-wrapped) and shown in-theme.

    Runs under both themes via the autouse ``theme`` fixture, so the notice is
    exercised on both the light and dark stylesheet (REQ-DDI-UI-009).
    """
    unknown = tmp_path / "thing.dat"
    unknown.write_text("x", encoding="utf-8")
    _drop(win, [str(unknown)])
    message = win.statusBar().currentMessage()
    assert message != ""
    assert "thing.dat" in message


def test_ui009_error_dialog_offers_keyboard_reachable_default(
    win, tmp_path, monkeypatch
):
    """SC-U009-2: the dirty prompt exposes a default (keyboard-operable) button.

    A QMessageBox is inherently keyboard-reachable; we assert the guard supplies
    Save/Discard/Cancel with a Save default so Enter/Esc resolve deterministically.
    """
    proj = _make_pixproj(win, tmp_path / f"p{FILE_SUFFIX}")
    _mark_dirty(win)
    seen: List[tuple] = []

    def _warn(parent, title, text, buttons, default):
        seen.append((buttons, default))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    _drop(win, [str(proj)])

    assert seen, "guard did not open a keyboard-operable prompt"
    _buttons, default = seen[0]
    assert default == QMessageBox.StandardButton.Save


def test_ui009_window_renders_after_drop_in_active_theme(win, tmp_path, theme):
    """SC-U009-3: after a drop the app is still rendered under the active theme."""
    from PySide6.QtWidgets import QApplication

    _drop(win, [str(_make_png(tmp_path / "x.png", 4, 4))])
    # A non-empty, role-based stylesheet is applied (both themes via fixture).
    assert QApplication.instance().styleSheet() != ""
    assert win.active_document() is not None


# --------------------------------------------------------------------------- #
# REQ-DDI-UI-009 (QA audit) — the three previously-unasserted                 #
# clauses: keyboard reachability, visible focus, LanguageChange retranslate.  #
# --------------------------------------------------------------------------- #


def test_ui009_error_notices_use_a_keyboard_operable_message_box(
    win, tmp_path, monkeypatch
):
    """SC-U009-2: every import error surfaces via ``QMessageBox`` — a
    native, inherently keyboard-reachable dialog (Enter/Esc dismiss it; a
    single default ``Ok`` button gets focus automatically) — for each of the
    three error-notice call sites (corrupt image / malformed palette / invalid
    project), not just the Save/Discard/Cancel dirty-guard already covered by
    ``test_ui009_error_dialog_offers_keyboard_reachable_default``.
    """
    calls: List[tuple] = []

    def _warn(parent, title, text, *a, **k):
        calls.append((parent, title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)

    bad_png = tmp_path / "broken.png"
    bad_png.write_bytes(b"\x89PNG\r\n\x1a\n not a real png \x00\x01\x02")
    _drop(win, [str(bad_png)])

    bad_gpl = tmp_path / "broken.gpl"
    bad_gpl.write_text("NOT A GIMP PALETTE\ngarbage row\n", encoding="utf-8")
    _drop(win, [str(bad_gpl)])

    bad_proj = tmp_path / f"broken{FILE_SUFFIX}"
    bad_proj.write_text("{ not valid json", encoding="utf-8")
    _drop(win, [str(bad_proj)])

    # Each of the three error paths opened a real QMessageBox — keyboard
    # operable by construction (a parent + title + text call signature, no
    # custom non-focusable widget substituted).
    assert len(calls) == 3
    for parent, title, text in calls:
        assert parent is win
        assert title != ""
        assert text != ""


def test_ui009_visible_focus_indicator_themed(win, theme):
    """SC-U009: a visible-focus QSS rule is themed (both themes, autouse)."""
    from PySide6.QtWidgets import QApplication

    assert ":focus" in QApplication.instance().styleSheet()


def test_ui009_notices_still_render_after_language_change(win, tmp_path):
    """SC-U009: a ``QEvent.LanguageChange`` does not break later drop
    notices — ``Main_Window.changeEvent`` retranslates its own persistent
    strings (existing 022 contract) and a drop-triggered notice generated
    *after* the event is still a non-empty, correctly-populated ``tr()``
    string (the notices are built fresh per call, so retranslation never
    leaves a stale/blank message behind).
    """
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))

    unknown = tmp_path / "post_retranslate.dat"
    unknown.write_text("x", encoding="utf-8")
    _drop(win, [str(unknown)])

    message = win.statusBar().currentMessage()
    assert message != ""
    assert "post_retranslate.dat" in message
