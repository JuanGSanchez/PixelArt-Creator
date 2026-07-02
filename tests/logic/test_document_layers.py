"""Tests for the Phase-4 layer model of pixelart_creator.logic.document (T5).

Covers the extended :class:`Layer` / :class:`LayerGroup`, node addressing
(``resolve_layer`` / ``layer_count`` / ``iter_layers`` through nested groups),
the reversible attribute + structural + mask/reference/smart commands
(``apply ∘ undo == identity``), the editability guard, and the
``MAX_LAYERS_PER_FRAME`` / ``MAX_GROUP_NESTING_DEPTH`` bounds.

Maps to REQ-P4-LOGIC-008..014 (and -015 bounds).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.blend import BlendMode, composite_stack
from pixelart_creator.logic.constants import (
    MAX_GROUP_NESTING_DEPTH,
    MAX_LAYERS_PER_FRAME,
)
from pixelart_creator.logic.document import (
    Document,
    DocumentError,
    Layer,
    LayerGroup,
    ensure_editable,
    iter_layers,
)
from pixelart_creator.logic.pixel_buffer import PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _doc(layers: int = 1) -> Document:
    doc = Document(4, 4)
    for i in range(layers - 1):
        doc.add_layer(f"L{i}")
    return doc


def _apply_undo_snapshot(doc: Document):
    """Capture a comparable snapshot of the top-level tree structure."""

    def _describe(node):
        if isinstance(node, LayerGroup):
            return ("group", node.name, [_describe(c) for c in node.children])
        return ("layer", node.name, id(node))

    return [_describe(n) for n in doc.frames[0].layers]


# --------------------------------------------------------------------------- #
# Layer / LayerGroup attributes.                                              #
# --------------------------------------------------------------------------- #


def test_layer_defaults_and_effective_buffer():
    buf = PixelBuffer(4, 4)
    layer = Layer(buf, "L")
    assert layer.blend_mode is BlendMode.NORMAL
    assert layer.mask is None and layer.reference is False
    assert layer.smart_source is None
    assert layer.effective_buffer() is buf


def test_layer_blend_mode_validation():
    layer = Layer(PixelBuffer(2, 2))
    layer.blend_mode = BlendMode.MULTIPLY
    assert layer.blend_mode is BlendMode.MULTIPLY
    with pytest.raises(DocumentError):
        layer.blend_mode = "multiply"  # type: ignore[assignment]


def test_layergroup_defaults_validation_and_repr():
    group = LayerGroup("G", [Layer(PixelBuffer(2, 2))])
    assert group.opacity == 1.0 and group.blend_mode is BlendMode.NORMAL
    assert group.visible is True and group.locked is False
    assert "LayerGroup(" in repr(group)
    with pytest.raises(DocumentError):
        group.opacity = 2.0
    with pytest.raises(DocumentError):
        group.blend_mode = 5  # type: ignore[assignment]


def test_smart_layer_effective_buffer_mirrors_source():
    # LOGIC-014: a smart layer reads its source's current pixels.
    src_buf = PixelBuffer(4, 4)
    src_buf.set_pixel(0, 0, RED)
    source = Layer(src_buf, "src")
    smart = Layer(PixelBuffer(4, 4), "smart", smart_source=source)
    assert smart.effective_buffer() is src_buf
    src_buf.set_pixel(1, 1, BLUE)  # later edit visible through the smart layer
    assert smart.effective_buffer().get_pixel(1, 1) == BLUE


# --------------------------------------------------------------------------- #
# iter_layers / resolve_layer / layer_count over nested groups.               #
# --------------------------------------------------------------------------- #


def test_iter_layers_walks_leaves_through_nested_groups():
    a = Layer(PixelBuffer(2, 2), "a")
    b = Layer(PixelBuffer(2, 2), "b")
    c = Layer(PixelBuffer(2, 2), "c")
    inner = LayerGroup("inner", [b, c])
    outer = LayerGroup("outer", [a, inner])
    leaves = iter_layers([outer])
    assert leaves == [a, b, c]
    assert all(isinstance(x, Layer) for x in leaves)


def test_resolve_layer_by_index_and_path():
    doc = _doc(1)
    leaf = doc.frames[0].layers[0]
    grp = LayerGroup("G", [Layer(PixelBuffer(4, 4), "inner")])
    doc.frames[0].layers.append(grp)
    assert doc.resolve_layer(0) is leaf
    assert doc.resolve_layer(1) is grp
    assert doc.resolve_layer([1, 0]).name == "inner"


def test_resolve_layer_errors():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.resolve_layer(9)
    with pytest.raises(DocumentError):
        doc.resolve_layer([])  # empty ref
    with pytest.raises(DocumentError):
        doc.resolve_layer([0, 0])  # descends into a leaf
    with pytest.raises(DocumentError):
        doc.resolve_layer([True])  # type: ignore[list-item]  bool is not an int index


def test_layer_count_counts_leaves():
    doc = _doc(1)
    grp = LayerGroup("G", [Layer(PixelBuffer(4, 4)), Layer(PixelBuffer(4, 4))])
    doc.frames[0].layers.append(grp)
    assert doc.layer_count() == 3  # 1 top-level leaf + 2 group leaves


# --------------------------------------------------------------------------- #
# Reversible attribute ops: apply ∘ undo == identity.                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "make, attr, new_value",
    [
        ("set_layer_opacity", "opacity", 0.25),
        ("set_layer_visible", "visible", False),
        ("set_layer_locked", "locked", True),
        ("set_layer_blend_mode", "blend_mode", BlendMode.SCREEN),
    ],
)
def test_attribute_command_reversible(make, attr, new_value):
    doc = _doc(1)
    node = doc.frames[0].layers[0]
    old = getattr(node, attr)
    cmd = getattr(doc, make)(0, new_value)
    cmd.execute()
    assert getattr(node, attr) == new_value
    cmd.undo()
    assert getattr(node, attr) == old


def test_set_opacity_validates_before_command():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.set_layer_opacity(0, 5.0)


def test_set_blend_mode_validates_before_command():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.set_layer_blend_mode(0, "screen")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Reversible structural ops: apply ∘ undo == identity (index + parent).       #
# --------------------------------------------------------------------------- #


def test_add_layer_command_reversible():
    doc = _doc(1)
    before = _apply_undo_snapshot(doc)
    cmd = doc.make_add_layer_command(name="New")
    cmd.execute()
    assert len(doc.frames[0].layers) == 2
    cmd.undo()
    assert _apply_undo_snapshot(doc) == before


def test_add_layer_command_above_ref():
    doc = _doc(2)
    ref_node = doc.frames[0].layers[0]
    cmd = doc.make_add_layer_command(ref=0, name="Above")
    cmd.execute()
    assert doc.frames[0].layers[1].name == "Above"
    assert doc.frames[0].layers[0] is ref_node


def test_remove_layer_command_restores_index_and_contents():
    doc = _doc(3)
    target = doc.frames[0].layers[1]
    target.buffer.set_pixel(2, 2, RED)
    cmd = doc.make_remove_layer_command(1)
    cmd.execute()
    assert doc.frames[0].layers[1] is not target
    cmd.undo()
    assert doc.frames[0].layers[1] is target
    assert doc.frames[0].layers[1].buffer.get_pixel(2, 2) == RED


def test_remove_last_top_level_layer_refused():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.make_remove_layer_command(0)


def test_move_layer_command_reversible():
    doc = _doc(3)
    node = doc.frames[0].layers[0]
    cmd = doc.make_move_layer_command(0, 2)
    cmd.execute()
    assert doc.frames[0].layers[2] is node
    cmd.undo()
    assert doc.frames[0].layers[0] is node


def test_move_layer_reparent_into_group_reversible():
    doc = _doc(1)
    leaf = doc.frames[0].layers[0]
    grp = LayerGroup("G", [Layer(PixelBuffer(4, 4), "inner")])
    doc.frames[0].layers.append(grp)
    # Move top-level leaf (index 0) into the group at path [1, 0].
    cmd = doc.make_move_layer_command(0, [1, 0])
    cmd.execute()
    assert grp.children[0] is leaf
    assert leaf not in doc.frames[0].layers
    cmd.undo()
    assert doc.frames[0].layers[0] is leaf
    assert leaf not in grp.children


def test_duplicate_layer_command_reversible_and_independent():
    doc = _doc(1)
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, RED)
    before = _apply_undo_snapshot(doc)
    cmd = doc.make_duplicate_layer_command(0)
    cmd.execute()
    assert len(doc.frames[0].layers) == 2
    copy = doc.frames[0].layers[1]
    assert copy.buffer.get_pixel(0, 0) == RED
    # Independent copy: mutating the copy does not touch the original.
    copy.buffer.set_pixel(1, 1, BLUE)
    assert doc.frames[0].layers[0].buffer.get_pixel(1, 1) == (0, 0, 0, 0)
    cmd.undo()
    assert _apply_undo_snapshot(doc) == before


def test_group_command_reversible():
    doc = _doc(3)
    l0, l1, l2 = doc.frames[0].layers
    cmd = doc.make_group_command([0, 1], name="G")
    cmd.execute()
    assert isinstance(doc.frames[0].layers[0], LayerGroup)
    assert doc.frames[0].layers[0].children == [l0, l1]
    assert doc.frames[0].layers[1] is l2
    cmd.undo()
    assert doc.frames[0].layers == [l0, l1, l2]


def test_group_command_errors():
    doc = _doc(2)
    with pytest.raises(DocumentError):
        doc.make_group_command([])  # empty selection
    with pytest.raises(DocumentError):
        doc.make_group_command([9])  # out of range
    with pytest.raises(DocumentError):
        doc.make_group_command([[0]])  # non-top-level (path) ref


def test_ungroup_command_reversible():
    doc = _doc(1)
    a = Layer(PixelBuffer(4, 4), "a")
    b = Layer(PixelBuffer(4, 4), "b")
    grp = LayerGroup("G", [a, b])
    doc.frames[0].layers.append(grp)
    cmd = doc.make_ungroup_command(1)
    cmd.execute()
    assert doc.frames[0].layers[1] is a
    assert doc.frames[0].layers[2] is b
    cmd.undo()
    assert doc.frames[0].layers[1] is grp


def test_ungroup_non_group_raises():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.make_ungroup_command(0)


# --------------------------------------------------------------------------- #
# Mask / reference / smart commands: reversible.                              #
# --------------------------------------------------------------------------- #


def test_attach_and_detach_mask_reversible():
    doc = _doc(1)
    node = doc.frames[0].layers[0]
    mask = PixelBuffer(4, 4)
    attach = doc.make_attach_mask_command(0, mask)
    attach.execute()
    assert node.mask is mask
    attach.undo()
    assert node.mask is None

    node.mask = mask
    detach = doc.make_detach_mask_command(0)
    detach.execute()
    assert node.mask is None
    detach.undo()
    assert node.mask is mask


def test_attach_mask_geometry_and_type_guards():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.make_attach_mask_command(0, PixelBuffer(2, 2))  # wrong geometry
    with pytest.raises(DocumentError):
        doc.make_attach_mask_command(0, object())  # type: ignore[arg-type]


def test_set_reference_command_reversible():
    doc = _doc(1)
    node = doc.frames[0].layers[0]
    cmd = doc.make_set_reference_command(0, True)
    cmd.execute()
    assert node.reference is True
    cmd.undo()
    assert node.reference is False


def test_smart_layer_command_reversible_and_mirrors_source():
    doc = _doc(1)
    source = doc.frames[0].layers[0]
    source.buffer.set_pixel(0, 0, RED)
    cmd = doc.make_smart_layer_command(0, name="Smart")
    cmd.execute()
    smart = doc.frames[0].layers[1]
    assert smart.smart_source is source
    assert smart.effective_buffer().get_pixel(0, 0) == RED
    cmd.undo()
    assert len(doc.frames[0].layers) == 1


def test_smart_layer_source_must_be_leaf():
    doc = _doc(1)
    doc.frames[0].layers.append(LayerGroup("G", [Layer(PixelBuffer(4, 4))]))
    with pytest.raises(DocumentError):
        doc.make_smart_layer_command(1)  # source is a group


# --------------------------------------------------------------------------- #
# ensure_editable guard (LOGIC-010/013).                                      #
# --------------------------------------------------------------------------- #


def test_ensure_editable_raises_on_locked():
    layer = Layer(PixelBuffer(4, 4), locked=True)
    with pytest.raises(DocumentError):
        ensure_editable(layer)


def test_ensure_editable_raises_on_reference():
    layer = Layer(PixelBuffer(4, 4), reference=True)
    with pytest.raises(DocumentError):
        ensure_editable(layer)


def test_ensure_editable_passes_for_plain_layer():
    ensure_editable(Layer(PixelBuffer(4, 4)))  # no raise


def test_locked_layer_attributes_still_changeable():
    # CL-11: lock guards *pixels*, not visibility/opacity/mode/order.
    doc = _doc(1)
    doc.frames[0].layers[0].locked = True
    doc.set_layer_visible(0, False).execute()
    doc.set_layer_opacity(0, 0.5).execute()
    doc.set_layer_blend_mode(0, BlendMode.SCREEN).execute()
    node = doc.frames[0].layers[0]
    assert node.visible is False and node.opacity == 0.5
    assert node.blend_mode is BlendMode.SCREEN


# --------------------------------------------------------------------------- #
# Bounds: MAX_LAYERS_PER_FRAME / MAX_GROUP_NESTING_DEPTH.                      #
# --------------------------------------------------------------------------- #


def test_add_layer_at_max_layers_raises():
    doc = _doc(1)
    # Fill up to the cap using direct appends (fast, avoids per-command churn).
    while doc.layer_count() < MAX_LAYERS_PER_FRAME:
        doc.frames[0].layers.append(Layer(PixelBuffer(4, 4)))
    assert doc.layer_count() == MAX_LAYERS_PER_FRAME
    with pytest.raises(DocumentError):
        doc.make_add_layer_command()


def test_duplicate_at_max_layers_raises():
    doc = _doc(1)
    while doc.layer_count() < MAX_LAYERS_PER_FRAME:
        doc.frames[0].layers.append(Layer(PixelBuffer(4, 4)))
    with pytest.raises(DocumentError):
        doc.make_duplicate_layer_command(0)


def test_smart_layer_at_max_layers_raises():
    doc = _doc(1)
    while doc.layer_count() < MAX_LAYERS_PER_FRAME:
        doc.frames[0].layers.append(Layer(PixelBuffer(4, 4)))
    with pytest.raises(DocumentError):
        doc.make_smart_layer_command(0)


def _nest(depth: int) -> LayerGroup:
    """Build a chain of nested groups of the given depth with a leaf at bottom."""
    node: LayerGroup = LayerGroup("g", [Layer(PixelBuffer(4, 4))])
    for _ in range(depth - 1):
        node = LayerGroup("g", [node])
    return node


def test_group_command_over_depth_raises():
    doc = _doc(1)
    # A near-max nested group at top level; grouping it again overflows depth.
    deep = _nest(MAX_GROUP_NESTING_DEPTH)
    doc.frames[0].layers.append(deep)
    with pytest.raises(DocumentError):
        doc.make_group_command([1])  # wrapping adds one more level -> over cap


def test_move_over_depth_raises():
    doc = _doc(1)
    deep = _nest(MAX_GROUP_NESTING_DEPTH)  # top-level group already at the cap
    doc.frames[0].layers.append(deep)
    empty = LayerGroup("dst", [Layer(PixelBuffer(4, 4))])
    doc.frames[0].layers.append(empty)
    # Move the max-depth group into dst -> exceeds MAX_GROUP_NESTING_DEPTH.
    with pytest.raises(DocumentError):
        doc.make_move_layer_command(1, [2, 0])


def test_resize_canvas_recurses_groups_and_masks():
    doc = _doc(1)
    inner = Layer(PixelBuffer(4, 4), "inner")
    inner.mask = PixelBuffer(4, 4)
    grp = LayerGroup("G", [inner])
    doc.frames[0].layers.append(grp)
    doc.resize_canvas(8, 8)
    assert inner.buffer.width == 8 and inner.buffer.height == 8
    assert inner.mask.width == 8 and inner.mask.height == 8


# --------------------------------------------------------------------------- #
# T13 D4 / B5 — group-composite cache invalidation (SC-UI-012-2).             #
#                                                                             #
# The cache is populated by blend._flatten_group during composite_stack and   #
# invalidated (set to None) up the ancestor chain by the reversible ops. A    #
# stale cache must never serve a wrong composite, on both do AND undo.        #
# --------------------------------------------------------------------------- #


def _grouped_doc():
    """Document with base leaf + outer[ inner[ leaf ] ] nested groups.

    Addresses: base=0, outer=1, inner=[1, 0], leaf=[1, 0, 0].
    """
    doc = Document(4, 4)
    leaf = Layer(PixelBuffer(4, 4), "leaf")
    inner = LayerGroup("inner", [leaf])
    outer = LayerGroup("outer", [inner])
    doc.frames[0].layers.append(outer)
    return doc, outer, inner, leaf


def _populate_caches(doc):
    """Run a full-canvas composite so every group's cache is populated."""
    composite_stack(doc.frames[0].layers, doc.width, doc.height)


def test_composite_populates_nested_group_caches():
    doc, outer, inner, _leaf = _grouped_doc()
    assert outer._composite_cache is None and inner._composite_cache is None
    _populate_caches(doc)
    assert outer._composite_cache is not None
    assert inner._composite_cache is not None


def test_invalidate_caches_ref_clears_ancestor_chain():
    # Public pixel-edit hook: invalidate_caches(ref of the edited leaf) clears
    # every ancestor group cache (outer + inner) so a same-region recomposite
    # cannot serve a stale flatten (SC-UI-012-2).
    doc, outer, inner, _leaf = _grouped_doc()
    _populate_caches(doc)
    doc.invalidate_caches([1, 0, 0])  # ref of the leaf inside inner inside outer
    assert outer._composite_cache is None
    assert inner._composite_cache is None


def test_invalidate_caches_none_clears_whole_frame():
    doc, outer, inner, _leaf = _grouped_doc()
    _populate_caches(doc)
    doc.invalidate_caches()  # ref=None -> clear the whole frame
    assert outer._composite_cache is None
    assert inner._composite_cache is None


def test_invalidate_caches_ref_of_group_clears_group_and_ancestors():
    doc, outer, inner, _leaf = _grouped_doc()
    _populate_caches(doc)
    doc.invalidate_caches([1, 0])  # ref of the inner group itself
    assert inner._composite_cache is None  # the group node itself
    assert outer._composite_cache is None  # and its ancestor


@pytest.mark.parametrize(
    "make, value",
    [
        ("set_layer_opacity", 0.25),
        ("set_layer_visible", False),
        ("set_layer_locked", True),
        ("set_layer_blend_mode", BlendMode.SCREEN),
    ],
)
def test_child_attribute_op_invalidates_ancestors_on_do_and_undo(make, value):
    # B5/SC-UI-012-2: an attribute change on a leaf inside groups clears the
    # ancestor caches on execute AND on undo (an undo also changes the composite).
    doc, outer, inner, _leaf = _grouped_doc()
    cmd = getattr(doc, make)([1, 0, 0], value)
    _populate_caches(doc)
    cmd.execute()
    assert outer._composite_cache is None and inner._composite_cache is None
    _populate_caches(doc)  # repopulate
    cmd.undo()
    assert outer._composite_cache is None and inner._composite_cache is None


def test_group_own_attribute_op_keeps_its_children_cache():
    # B5: a group's OWN opacity/blend/visible/mask change invalidates only its
    # ANCESTORS -- its own children-cache stays valid (the common opacity-slider
    # case re-blends the group into the stack, not its children).
    doc, outer, inner, _leaf = _grouped_doc()
    cmd = doc.set_layer_opacity([1, 0], 0.5)  # change inner group's own opacity
    _populate_caches(doc)
    cmd.execute()
    assert outer._composite_cache is None  # ancestor cleared
    assert inner._composite_cache is not None  # own children-cache preserved


def test_mask_attach_detach_invalidates_ancestors_on_do_and_undo():
    doc, outer, inner, _leaf = _grouped_doc()
    mask = PixelBuffer(4, 4)
    cmd = doc.make_attach_mask_command([1, 0, 0], mask)
    _populate_caches(doc)
    cmd.execute()
    assert outer._composite_cache is None and inner._composite_cache is None
    _populate_caches(doc)
    cmd.undo()
    assert outer._composite_cache is None and inner._composite_cache is None


def test_structural_ops_invalidate_ancestors_on_do_and_undo():
    # add / remove / duplicate a layer inside the inner group -> clears the
    # owning-group chain (outer + inner) on execute and undo.
    for make in ("add", "remove", "duplicate"):
        doc, outer, inner, _leaf = _grouped_doc()
        inner.children.append(Layer(PixelBuffer(4, 4), "extra"))  # give remove room
        if make == "add":
            cmd = doc.make_add_layer_command(ref=[1, 0, 0], name="new")
        elif make == "remove":
            cmd = doc.make_remove_layer_command([1, 0, 0])
        else:
            cmd = doc.make_duplicate_layer_command([1, 0, 0])
        _populate_caches(doc)
        cmd.execute()
        assert outer._composite_cache is None and inner._composite_cache is None
        _populate_caches(doc)
        cmd.undo()
        assert outer._composite_cache is None and inner._composite_cache is None


def test_move_layer_invalidates_both_source_and_destination_chains():
    # Reorder within the inner group -> the owning chain caches clear (do+undo).
    doc, outer, inner, _leaf = _grouped_doc()
    inner.children.append(Layer(PixelBuffer(4, 4), "extra"))
    cmd = doc.make_move_layer_command([1, 0, 0], [1, 0, 1])
    _populate_caches(doc)
    cmd.execute()
    assert outer._composite_cache is None and inner._composite_cache is None
    _populate_caches(doc)
    cmd.undo()
    assert outer._composite_cache is None and inner._composite_cache is None


def test_ungroup_invalidates_owning_chain_on_do_and_undo():
    doc, outer, inner, _leaf = _grouped_doc()
    cmd = doc.make_ungroup_command([1, 0])  # dissolve the inner group
    _populate_caches(doc)
    cmd.execute()
    assert outer._composite_cache is None  # owning ancestor cleared
    _populate_caches(doc)
    cmd.undo()
    assert outer._composite_cache is None


def test_duplicated_group_starts_uncached():
    # D4: a copied group must NOT carry the source's cache (constructor resets
    # it to None) -- the cache is transient, never copied or serialised.
    doc, _outer, inner, _leaf = _grouped_doc()
    _populate_caches(doc)
    assert inner._composite_cache is not None
    cmd = doc.make_duplicate_layer_command([1, 0])  # duplicate the inner group
    cmd.execute()
    dup = doc.resolve_layer([1, 1])  # the duplicate sits above the original
    assert isinstance(dup, LayerGroup)
    assert dup._composite_cache is None


def test_stale_cache_never_serves_wrong_composite_through_document():
    # End-to-end SC-UI-012-2: edit a child pixel, invalidate via the document
    # hook, recomposite -> the composite reflects the edit (never the stale one).
    doc, _outer, inner, leaf = _grouped_doc()
    leaf.buffer.fill((0, 0, 255, 255))  # BLUE
    first = composite_stack(doc.frames[0].layers, 4, 4, region=(0, 0, 2, 2))
    assert first.get_pixel(0, 0) == (0, 0, 255, 255)
    leaf.buffer.set_pixel(0, 0, (0, 255, 0, 255))  # edit to GREEN
    doc.invalidate_caches([1, 0, 0])  # pixel-edit hook clears the ancestor chain
    updated = composite_stack(doc.frames[0].layers, 4, 4, region=(0, 0, 2, 2))
    assert updated.get_pixel(0, 0) == (0, 255, 0, 255)
