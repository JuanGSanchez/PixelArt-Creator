"""Canvas-render acceptance tests (REQ-P1-UI-001..003, -007 grid) and the
shared geometry seam (REQ-CSD-UI-005, canvas-scale-defects `spec.md` §4/§6).

Scenarios SC-UI-001-1/-2, SC-UI-002-1/-2, SC-UI-003-1/-2, SC-UI-007-1/-2,
SC-CSD-U005-1/-2. Each runs under both themes via the autouse ``theme``
fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.constants import CHECKER_CELL_PX
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.transform_dialog import Scale_Dialog

RED = (255, 0, 0, 255)


def _render(scene, doc_w, doc_h, scale):
    """Render ``scene`` nearest-neighbour into an RGBA image at ``scale``."""
    img = QImage(doc_w * scale, doc_h * scale, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.render(
        painter,
        QRectF(0, 0, doc_w * scale, doc_h * scale),
        QRectF(0, 0, doc_w, doc_h),
    )
    painter.end()
    return img


def _rgba(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


# -- REQ-P1-UI-001 --------------------------------------------------------


def test_sc_ui_001_1_buffer_pixel_rendered_no_aa(make_scene):
    """SC-UI-001-1: buffer pixel (3,3)=RED renders exactly RED, no AA edge."""
    scene = make_scene(8, 8)
    scene.active_buffer().set_pixel(3, 3, RED)
    # The scene now displays the flattened composite (REQ-P4-UI-012); a direct
    # buffer poke bypasses the paint pipeline, so recomposite explicitly.
    scene.refresh_all()
    scale = 20
    img = _render(scene, 8, 8, scale)
    # Centre of the (3,3) cell is exactly RED.
    assert _rgba(img, 3 * scale + scale // 2, 3 * scale + scale // 2) == RED
    # Hard boundary: the column just outside the cell is NOT red and is uniform
    # (no anti-aliased gradient bleeding across the pixel edge).
    outside = _rgba(img, 3 * scale - 1, 3 * scale + scale // 2)
    inside = _rgba(img, 3 * scale, 3 * scale + scale // 2)
    assert inside == RED
    assert outside != RED
    assert outside == _rgba(img, 3 * scale - 1, 3 * scale + scale // 2 + 5)


def test_sc_ui_001_2_magnified_pixel_is_solid_square(make_scene):
    """SC-UI-001-2: at deep zoom a painted pixel is a solid crisp square."""
    scene = make_scene(4, 4)
    scene.active_buffer().set_pixel(1, 1, RED)
    # Recomposite after the direct poke: the scene shows the composite, not the
    # raw active buffer (REQ-P4-UI-012).
    scene.refresh_all()
    scale = 32  # 3200 %
    img = _render(scene, 4, 4, scale)
    x0, y0 = 1 * scale, 1 * scale
    # Every sampled point inside the cell is identical RED (uniform square).
    for sx in (x0 + 1, x0 + scale // 2, x0 + scale - 2):
        for sy in (y0 + 1, y0 + scale // 2, y0 + scale - 2):
            assert _rgba(img, sx, sy) == RED
    # Immediately outside the square is not red (crisp edge).
    assert _rgba(img, x0 - 1, y0 + scale // 2) != RED


# -- REQ-P1-UI-002 --------------------------------------------------------


def test_sc_ui_002_1_scene_rect_matches_document(make_scene):
    """SC-UI-002-1: a new 64x64 document yields sceneRect (0,0,64,64)."""
    scene = make_scene(64, 64)
    assert scene.sceneRect() == QRectF(0, 0, 64, 64)


def test_sc_ui_002_2_resize_updates_scene_rect(make_scene):
    """SC-UI-002-2 (legacy seam): ``on_document_resized`` also updates the scene
    rect, but this entry point is NOT called by any shipped UI action today —
    ``grep`` finds no caller of ``CanvasScene.on_document_resized`` anywhere in
    ``pixelart_creator/`` (QA audit). Kept as a direct-API regression
    guard on the method itself; the criterion's SHIPPED coverage is
    ``test_sc_ui_002_2_scale_via_shipped_on_scale_updates_scene_rect`` below,
    which drives the real ``Main_Window._on_scale`` -> ``rebind_active`` ->
    ``_apply_scene_rect`` path a user actually reaches.
    """
    scene = make_scene(64, 64)
    scene._document.resize_canvas(128, 96)
    scene.on_document_resized(128, 96)
    assert scene.sceneRect() == QRectF(0, 0, 128, 96)


def test_sc_ui_002_2_scale_via_shipped_on_scale_updates_scene_rect(qtbot, monkeypatch):
    """SC-UI-002-2 (QA audit): the scene rect updates through the
    SHIPPED, user-reachable resize path — ``Main_Window._on_scale`` accepting
    the ``Scale_Dialog`` -> ``_apply_buffer_command`` (dims-changing) ->
    ``CanvasScene.rebind_active`` -> ``CanvasScene._apply_scene_rect`` — not the
    orphaned ``on_document_resized`` direct-API call the prior test exercises.
    """
    from PySide6.QtWidgets import QDialog

    from pixelart_creator.ui.main_window import Main_Window
    from pixelart_creator.ui.transform_dialog import Scale_Dialog

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    src_w, src_h = record.document.width, record.document.height
    assert record.scene.sceneRect() == QRectF(0, 0, src_w, src_h)

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        Scale_Dialog, "target_size", lambda self: (src_w * 2, src_h * 2)
    )
    win._on_scale()

    assert record.stack.count() == 1
    assert record.scene.sceneRect() == QRectF(0, 0, src_w * 2, src_h * 2)
    record.stack.undo()
    assert record.scene.sceneRect() == QRectF(0, 0, src_w, src_h)


# -- REQ-P1-UI-003 --------------------------------------------------------


def test_sc_ui_003_1_draw_background_only_exposed_rect(make_scene):
    """SC-UI-003-1: drawBackground paints only near the exposed rect."""
    scene = make_scene(64, 64)  # scene size is immaterial to the cull (F2/D2)
    img = QImage(600, 600, QImage.Format.Format_RGBA8888)
    sentinel = Qt.GlobalColor.transparent
    img.fill(sentinel)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, 64, 64))
    painter.end()
    # A pixel inside the exposed rect was painted (opaque checker).
    assert img.pixelColor(10, 10).alpha() == 255
    # A pixel far outside the exposed rect (+ tile ring) is untouched.
    assert img.pixelColor(500, 500).alpha() == 0


def test_sc_ui_003_2_background_tiles_on_tile_size(make_scene):
    """SC-UI-003-2: superseded by REQ-CGS-UI-003 — the checker period is exactly
    CHECKER_CELL_PX (one document pixel), never a TILE_SIZE (64) multiple, and
    the checker is clipped to the document canvas rect (REQ-CGS-UI-004): it
    gives way to the workspace ground past the document's own bounds, even
    when the exposed rect extends further than that (the field defect this
    batch fixes: a whole 64x64 document used to read as a single checker cell).
    """
    doc_w, doc_h = 8, 8
    scene = make_scene(doc_w, doc_h)
    img = QImage(doc_w + 4, doc_h + 4, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    # The exposed rect deliberately extends past the document, to prove the
    # canvas clip (REQ-CGS-UI-004) alongside the period (REQ-CGS-UI-003).
    scene.drawBackground(painter, QRectF(0, 0, doc_w + 4, doc_h + 4))
    painter.end()

    # Period: the checker alternates every CHECKER_CELL_PX -- never every
    # TILE_SIZE (the conflation this fix removes) -- and repeats after exactly
    # two CHECKER_CELL_PX-wide columns. Sampled on an interior row, clear of
    # the cosmetic border stroke the canvas edge carries on every side.
    row = doc_h // 2
    x0 = 2
    col0 = img.pixelColor(x0, row)
    col1 = img.pixelColor(x0 + CHECKER_CELL_PX, row)
    col2 = img.pixelColor(x0 + 2 * CHECKER_CELL_PX, row)
    assert col0 != col1  # boundary at exactly one CHECKER_CELL_PX
    assert col0 == col2  # period repeats after exactly one CHECKER_CELL_PX

    # Clip: past the document edge (a couple of px clear of the cosmetic
    # border stroke) the checker gives way to the workspace ground colour --
    # it never continues the pattern outside the canvas.
    assert img.pixelColor(doc_w + 2, 0) == scene._workspace_color
    assert img.pixelColor(0, doc_h + 2) == scene._workspace_color


# -- REQ-P1-UI-007 (grid overlay) ----------------------------------------


def test_sc_ui_007_1_grid_on_by_default_and_user_controllable(make_scene):
    """SC-UI-007-1: superseded by REQ-CGS-UI-007 -- the per-pixel grid overlay
    is now ON by default for a new document (the old CL-4 "off by default"
    contract this test asserted meant a new user's only visible lattice was
    the meaningless 64-document-pixel checker; that field defect is the
    reason this batch exists). The default remains user-controllable: the
    overlay can still be switched off, and back on, at the scene API.
    """
    scene = make_scene(32, 32)
    assert scene.is_grid_enabled() is True

    scene.set_grid_enabled(False)
    assert scene.is_grid_enabled() is False

    scene.set_grid_enabled(True)
    assert scene.is_grid_enabled() is True


def _draw_bg_at_scale(scene, scale, size=32):
    img = QImage(size, size, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setWorldTransform(QTransform().scale(scale, scale))
    scene.drawBackground(painter, QRectF(0, 0, size, size))
    painter.end()
    return bytes(img.constBits())


def test_sc_ui_007_2_grid_appears_past_threshold(make_scene):
    """SC-UI-007-2: enabled grid shows only past GRID_MIN_PIXEL_EDGE_PX (8)."""
    scene = make_scene(32, 32)
    # Below the legibility threshold: enabling the grid changes nothing drawn.
    below_off = _draw_bg_at_scale(scene, 4)
    scene.set_grid_enabled(True)
    below_on = _draw_bg_at_scale(scene, 4)
    assert below_on == below_off  # grid suppressed at < 8 device px/pixel
    # At/above the threshold: the grid overlay is now painted (output differs).
    scene.set_grid_enabled(False)
    above_off = _draw_bg_at_scale(scene, 8)
    scene.set_grid_enabled(True)
    above_on = _draw_bg_at_scale(scene, 8)
    assert above_on != above_off  # grid visible at >= 8 device px/pixel


# -- REQ-CSD-UI-005 (document geometry is never derived from a single layer) --
#
# canvas-scale-defects `spec.md` §4.1/§6 (QA audit): the shared seam
# `CanvasScene.rebind_active` must not author `Document.width`/`height` from
# any one layer's buffer. The negative invariant rots silently if only
# pinned by a happy-path number, so SC-CSD-U005-1 below deliberately
# desynchronises a layer buffer from the document before calling the seam,
# and asserts the document's declared geometry is untouched -- exactly the
# regression a future re-introduction of
# ``self._document.width = buffer.width`` (`ui/canvas_scene.py:1766-1768` at
# HEAD `35b63bf`, still live there; removed in this worktree's uncommitted
# fix per `git diff HEAD -- pixelart_creator/ui/canvas_scene.py`) would trip.


def _build_multi_layer_document(width, height, frame_layer_counts, masks=(), mode=None):
    """Build a :class:`Document` with ``frame_layer_counts[i]`` layers in frame i.

    ``masks`` is an iterable of ``(frame_index, layer_index)`` pairs; the
    named layer gets an attached mask sized to the document (direct
    attribute assignment for test setup, not the reversible
    ``make_attach_mask_command`` path -- no ``Command`` is pushed by it).
    Mirrors the equivalent local helper in ``test_transform_actions.py`` and
    ``test_document_transform.py``; kept local here (this module's declared write
    target is this module alone) rather than imported cross-module.

    ``mode`` defaults to :attr:`ColorMode.RGBA` (the ``Document`` default)
    when omitted; SC-CSD-U005-1 below passes :attr:`ColorMode.INDEXED` for a
    reason explained in that test's docstring.
    """
    document = Document(
        width, height, mode=mode if mode is not None else ColorMode.RGBA
    )
    for _ in range(frame_layer_counts[0] - 1):
        document.add_layer(frame_index=0)
    for count in frame_layer_counts[1:]:
        document.add_frame()
        frame_index = len(document.frames) - 1
        for _ in range(count - 1):
            document.add_layer(frame_index=frame_index)
    for frame_index, layer_index in masks:
        layer = document.frames[frame_index].layers[layer_index]
        layer.mask = PixelBuffer(document.width, document.height, document.mode)
    return document


def _all_buffer_dims(document):
    """Every leaf layer's buffer dims, plus every attached mask's, in order."""
    dims = []
    for frame in document.frames:
        for layer in iter_layers(frame.layers):
            dims.append((layer.buffer.width, layer.buffer.height))
            if layer.mask is not None:
                dims.append((layer.mask.width, layer.mask.height))
    return dims


def test_sc_csd_u005_1_rebind_active_never_derives_geometry_from_one_layer(theme):
    """SC-CSD-U005-1 (REQ-CSD-UI-005, DEFECT): the seam authors nothing.

    ``CanvasScene.rebind_active`` only re-reads and re-renders the document's
    *already-current* geometry; it must never derive ``Document.width`` /
    ``height`` from any single layer's buffer, active or otherwise.

    This is the property-pinning test: the active layer's buffer is
    deliberately swapped to a size that agrees with NEITHER the document NOR
    any sibling layer -- the exact mid-operation shape a partially-applied
    whole-document transform would leave behind, and exactly what the
    pre-fix seam derived ``Document.width``/``height`` from
    (``ui/canvas_scene.py:1766-1768`` at HEAD ``35b63bf``:
    ``buffer = self._active_layer.buffer; self._document.width =
    buffer.width; self._document.height = buffer.height``). Proven to FAIL
    against that unfixed code in a throwaway ``git worktree`` at HEAD this
    session (see the QA report) -- there, this test's first assertion trips
    because the seam sets ``document.width`` to 128.

    Because every sibling buffer here stays at the *document's* original
    size while only the active layer's disagrees, a future regression that
    re-derives geometry from the active layer alone -- even one that reaches
    the seam only after a full whole-document op has otherwise completed --
    is caught here: SC-CSD-U005-2 below cannot catch it, because after a
    real whole-document operation every buffer (including the active
    layer's) already agrees with the target geometry, so a reintroduced
    active-layer derivation would coincidentally compute the same number.
    Only a deliberately-disagreeing fixture, like this one, isolates the
    seam's own authorship from the operation's correctness.

    **Why ``ColorMode.INDEXED``.** ``rebind_active`` calls
    ``_rebuild_composite`` first, which -- for an RGBA document, unrelated to
    REQ-CSD-UI-005 and unchanged by this batch (`git diff HEAD --
    pixelart_creator/logic/blend.py` is empty) -- requires EVERY leaf
    layer's buffer to already equal the canvas size
    (``logic/blend.py``'s ``_node_source_region`` raises ``BlendError``
    otherwise). A genuinely mid-operation, disagreeing buffer therefore
    cannot reach the geometry-authorship line at all on an RGBA multi-layer
    document -- compositing raises first, on BOTH the fixed and unfixed
    code (measured this session: swapping the active layer's buffer to
    128x96 on an RGBA fixture raises ``BlendError: layer buffer 128x96 does
    not match canvas 64x48`` from ``_rebuild_composite`` before the
    (fixed-code) seam ever gets a chance to not-author anything, and would
    raise the same way against the unfixed code once its geometry write had
    already run and made the OTHER, untouched sibling layers the mismatched
    ones instead). ``INDEXED`` mode makes ``_rebuild_composite`` skip
    compositing entirely (``self._compositing = self._document.mode is
    ColorMode.RGBA``), letting ``rebind_active`` reach and exercise its
    geometry-authorship line in isolation -- exactly the seam behaviour this
    test pins -- without incidentally exercising the unrelated compositor
    invariant. The removed derivation line
    (``self._document.width = buffer.width``) reads only ``buffer.width``/
    ``.height``; its behaviour has no dependency on ``ColorMode``.
    """
    document = _build_multi_layer_document(64, 48, [2, 2, 2], mode=ColorMode.INDEXED)
    scene = CanvasScene(document)
    scene.set_background_roles(*canvas_roles(theme))

    active = scene.active_layer()
    siblings = [
        layer for layer in iter_layers(document.frames[0].layers) if layer is not active
    ]
    assert siblings, "fixture must contain a second layer to disagree with"
    assert (active.buffer.width, active.buffer.height) == (64, 48)

    # Deliberately desynchronise: swap ONLY the active layer's buffer.
    active.buffer = PixelBuffer(128, 96, active.buffer.mode)

    scene.rebind_active()

    # The negative invariant: the document's declared geometry is untouched
    # by the rebind, even though the active layer's buffer now disagrees
    # with it. A regression reintroducing the removed derivation would set
    # document.width/height to (128, 96) here.
    assert document.width == 64
    assert document.height == 48
    assert (document.width, document.height) != (128, 96)
    # No sibling layer was silently resized either -- the rebind authors
    # nothing; it only re-reads and re-renders (spec.md REQ-CSD-UI-005).
    assert all(
        (layer.buffer.width, layer.buffer.height) == (64, 48) for layer in siblings
    )


def test_sc_csd_u005_2_geometry_matches_every_buffer_after_the_seam_runs(
    qtbot, monkeypatch
):
    """SC-CSD-U005-2 (REQ-CSD-UI-005): after a real seam-reaching operation,
    document geometry equals every layer buffer and every attached mask, in
    every frame -- driven through the SHIPPED ``Main_Window`` path (the same
    one ``test_sc_csd_u001_1_scale_reaches_every_layer_frame_and_mask`` and
    ``test_sc_csd_u006_1_non_square_rotate_cw_rotates_whole_document`` in
    ``test_transform_actions.py`` use), first a whole-document scale then a
    whole-document rotate, so the seam runs twice in the same document's
    lifetime.

    This is a POSITIVE integration confirmation of REQ-CSD-UI-005's second
    paragraph, not a second DEFECT proof: ``logic/doc_transform.py`` and
    ``ui/document_transform_runner.py`` are new modules that do not exist at
    all before this batch, so running this test's body against the pre-fix
    ``HEAD`` raises ``ImportError``/``ModuleNotFoundError`` at collection,
    not a targeted assertion failure -- that is not a meaningful DEFECT
    proof for this scenario, and the DEFECT proof for REQ-CSD-UI-005 rests
    on SC-CSD-U005-1 above (verified in the throwaway worktree). Also note
    (per this test's own docstring above) that this scenario alone would NOT
    catch a reintroduced active-layer-only derivation, since every buffer
    already agrees with the target size once a whole-document op completes.
    """
    win = Main_Window()
    qtbot.addWidget(win)
    document = _build_multi_layer_document(64, 48, [2, 2, 2], masks=[(1, 1)])
    record = win.active_tab()
    record.document = document
    record.scene.set_document(document)
    record.view.clear_selection()

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (256, 192))
    win._on_scale()

    dims = _all_buffer_dims(document)
    assert len(dims) == 7  # 6 layer buffers + 1 mask
    assert all(d == (256, 192) for d in dims)
    assert document.width == 256 and document.height == 192

    win._on_rotate_cw()

    dims = _all_buffer_dims(document)
    assert all(d == (192, 256) for d in dims)
    assert document.width == 192 and document.height == 256
