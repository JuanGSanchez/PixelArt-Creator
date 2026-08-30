"""Tests for pixelart_creator.logic.content_bounds (REQ-IS-LOGIC-003).

One test per acceptance scenario ``SC-L003-1..7`` (design-docs/specs/
input-scheme/spec.md). Zero Qt; no wall-clock, no randomness, no ordering
dependence, no network.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from pixelart_creator.logic.content_bounds import ContentBoundsError, content_bounds
from pixelart_creator.logic.document import Frame, Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

_ROOT = Path(__file__).resolve().parents[3]

_OPAQUE = (255, 0, 0, 255)
_TRANSPARENT = (0, 0, 0, 0)


def _buffer(width: int, height: int, opaque_points=()) -> PixelBuffer:
    """A width x height RGBA buffer, transparent except at ``opaque_points``."""
    buf = PixelBuffer(width, height, ColorMode.RGBA)
    for x, y in opaque_points:
        buf.set_pixel(x, y, _OPAQUE)
    return buf


def _layer(width: int, height: int, opaque_points=(), **kwargs) -> Layer:
    return Layer(_buffer(width, height, opaque_points), **kwargs)


def _snapshot(buffer: PixelBuffer) -> bytes:
    """Byte snapshot of a buffer's backing array, for a before/after compare."""
    return buffer.data.tobytes()


class TestSCL0031TightestRectangle:
    """SC-L003-1: the box is the tightest rectangle around the painted pixels."""

    def test_two_points_give_the_tight_inclusive_box(self):
        layer = _layer(64, 64, opaque_points=[(10, 12), (20, 30)])
        frame = Frame([layer])

        result = content_bounds(frame, 64, 64)

        assert result == (10, 12, 20, 30)

    def test_single_painted_pixel_is_a_1x1_box(self):
        layer = _layer(16, 16, opaque_points=[(4, 7)])
        frame = Frame([layer])

        result = content_bounds(frame, 16, 16)

        assert result == (4, 7, 4, 7)


class TestSCL0032EmptyDocument:
    """SC-L003-2: a fully transparent document reports an empty box."""

    def test_no_opaque_pixel_anywhere_returns_none(self):
        layer = _layer(32, 32)
        frame = Frame([layer])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_empty_frame_with_no_layers_returns_none(self):
        frame = Frame([])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_no_exception_is_raised_on_empty_document(self):
        layer = _layer(8, 8)
        frame = Frame([layer])

        try:
            content_bounds(frame, 8, 8)
        except Exception as exc:  # pragma: no cover - failure path only
            pytest.fail(f"content_bounds raised {exc!r} on an empty document")


class TestSCL0033HiddenLayersExcluded:
    """SC-L003-3: hidden layers do not contribute."""

    def test_hidden_layer_pixels_are_excluded(self):
        hidden = _layer(32, 32, opaque_points=[(5, 5)], visible=False)
        frame = Frame([hidden])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_hidden_layer_does_not_widen_a_visible_layer_box(self):
        visible = _layer(32, 32, opaque_points=[(1, 1)], visible=True)
        hidden = _layer(32, 32, opaque_points=[(30, 30)], visible=False)
        frame = Frame([visible, hidden])

        result = content_bounds(frame, 32, 32)

        assert result == (1, 1, 1, 1)


class TestSCL0034VisibleLayersContribute:
    """SC-L003-4: all visible layers of the current frame contribute."""

    def test_two_visible_layers_union_their_extents(self):
        first = _layer(64, 64, opaque_points=[(2, 2)])
        second = _layer(64, 64, opaque_points=[(40, 40)])
        frame = Frame([first, second])

        result = content_bounds(frame, 64, 64)

        assert result == (2, 2, 40, 40)


class TestSCL0035OtherFramesExcluded:
    """SC-L003-5: other frames do not contribute."""

    def test_only_the_given_frame_is_examined(self):
        frame1 = Frame([_layer(64, 64, opaque_points=[(5, 5)])])
        frame2 = Frame([_layer(64, 64, opaque_points=[(50, 50)])])

        result = content_bounds(frame1, 64, 64)

        assert result == (5, 5, 5, 5)
        # frame2 is never passed in, so its pixel cannot appear.
        assert result != content_bounds(frame2, 64, 64)

    def test_frame2_alone_reports_its_own_pixel(self):
        frame2 = Frame([_layer(64, 64, opaque_points=[(50, 50)])])

        result = content_bounds(frame2, 64, 64)

        assert result == (50, 50, 50, 50)


class TestSCL0036FullyPaintedDocument:
    """SC-L003-6: a fully painted document reports the whole canvas."""

    def test_every_pixel_opaque_reports_whole_canvas_inclusive(self):
        buf = PixelBuffer(32, 32, ColorMode.RGBA)
        buf.fill(_OPAQUE)
        layer = Layer(buf)
        frame = Frame([layer])

        result = content_bounds(frame, 32, 32)

        # Inclusive bounds: the far edge is width-1 / height-1, not width/height.
        assert result == (0, 0, 31, 31)

    def test_boundary_touching_pixels_are_included_inclusively(self):
        # Pins the inclusive convention explicitly: opaque pixels sit exactly
        # on the buffer's last row/column, and must not be treated as
        # one-past-the-end (an exclusive convention would report x1=32/y1=32
        # or silently clip, either of which disagrees with this assertion).
        layer = _layer(32, 32, opaque_points=[(0, 0), (31, 31)])
        frame = Frame([layer])

        result = content_bounds(frame, 32, 32)

        assert result == (0, 0, 31, 31)


class TestSCL0037QtFreeAndNonMutating:
    """SC-L003-7: the computation is Qt-free and non-mutating."""

    def test_module_imports_nothing_from_pyside6(self):
        import ast

        source = (_ROOT / "pixelart_creator" / "logic" / "content_bounds.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(
                        "PySide6"
                    ), f"content_bounds.py imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(
                    "PySide6"
                ), f"content_bounds.py imports from {module}"

    def test_check_layering_passes_over_the_real_tree(self):
        script = _ROOT / "scripts" / "check_layering.py"
        assert script.is_file(), f"missing {script}"
        result = subprocess.run(
            [sys.executable, str(script), "--root", "pixelart_creator"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        combined = result.stdout + result.stderr
        assert (
            result.returncode == 0
        ), f"check_layering exited {result.returncode}\n{combined}"
        assert "clean" in combined.lower(), combined

    def test_source_buffers_are_byte_identical_after_the_call(self):
        buf1 = _buffer(32, 32, opaque_points=[(3, 3), (10, 10)])
        buf2 = _buffer(32, 32, opaque_points=[(20, 20)])
        layer1 = Layer(buf1)
        layer2 = Layer(buf2)
        frame = Frame([layer1, layer2])

        before1 = _snapshot(buf1)
        before2 = _snapshot(buf2)

        content_bounds(frame, 32, 32)

        assert _snapshot(buf1) == before1
        assert _snapshot(buf2) == before2

    def test_hidden_layer_buffer_is_also_left_byte_identical(self):
        # Non-contributing buffers must be untouched too, not merely
        # the ones that end up in the result.
        buf = _buffer(32, 32, opaque_points=[(5, 5)])
        layer = Layer(buf, visible=False)
        frame = Frame([layer])
        before = _snapshot(buf)

        content_bounds(frame, 32, 32)

        assert _snapshot(buf) == before


class TestOpacityDivergenceIsDeliberate:
    """Pin: visible=True + opacity=0.0 still contributes here (not a bug).

    This diverges from what a composite would show — a zero-opacity layer
    contributes nothing to a flattened composite — but content_bounds follows
    the shipped `visible` flag literally, per the module docstring and plan
    §3.4. A future reader who "fixes" this by gating on opacity would be
    reversing an accepted, documented design choice; this test exists so
    that reversal is caught.
    """

    def test_visible_zero_opacity_layer_still_contributes(self):
        layer = _layer(32, 32, opaque_points=[(15, 15)], visible=True, opacity=0.0)
        frame = Frame([layer])

        result = content_bounds(frame, 32, 32)

        assert result == (15, 15, 15, 15)


class TestLayerGroupVisibilityGating:
    """Pin: a hidden group hides its whole subtree (matches blend.py)."""

    def test_hidden_group_hides_a_visible_child_layer(self):
        child = _layer(32, 32, opaque_points=[(6, 6)], visible=True)
        group = LayerGroup("group", [child], visible=False)
        frame = Frame([group])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_visible_group_lets_a_visible_child_contribute(self):
        child = _layer(32, 32, opaque_points=[(6, 6)], visible=True)
        group = LayerGroup("group", [child], visible=True)
        frame = Frame([group])

        result = content_bounds(frame, 32, 32)

        assert result == (6, 6, 6, 6)

    def test_visible_group_still_hides_its_own_hidden_child(self):
        child = _layer(32, 32, opaque_points=[(6, 6)], visible=False)
        group = LayerGroup("group", [child], visible=True)
        frame = Frame([group])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_nested_group_hidden_ancestor_hides_a_deeply_nested_leaf(self):
        # Nested case: outer group hidden -> inner (visible) group's visible
        # leaf must not contribute, since effective visibility is the AND of
        # every ancestor's flag.
        leaf = _layer(32, 32, opaque_points=[(9, 9)], visible=True)
        inner = LayerGroup("inner", [leaf], visible=True)
        outer = LayerGroup("outer", [inner], visible=False)
        frame = Frame([outer])

        result = content_bounds(frame, 32, 32)

        assert result is None

    def test_nested_group_all_visible_ancestors_let_leaf_contribute(self):
        leaf = _layer(32, 32, opaque_points=[(9, 9)], visible=True)
        inner = LayerGroup("inner", [leaf], visible=True)
        outer = LayerGroup("outer", [inner], visible=True)
        frame = Frame([outer])

        result = content_bounds(frame, 32, 32)

        assert result == (9, 9, 9, 9)


class TestContentBoundsErrors:
    """Documented exceptions: mismatched mode/geometry raise ContentBoundsError."""

    def test_non_rgba_layer_buffer_raises(self):
        buf = PixelBuffer(8, 8, ColorMode.INDEXED)
        layer = Layer(buf)
        frame = Frame([layer])

        with pytest.raises(ContentBoundsError):
            content_bounds(frame, 8, 8)

    def test_mismatched_dimensions_raise(self):
        buf = PixelBuffer(8, 8, ColorMode.RGBA)
        layer = Layer(buf)
        frame = Frame([layer])

        with pytest.raises(ContentBoundsError):
            content_bounds(frame, 16, 16)


class TestSmartLayerReadsSourceBuffer:
    """A smart layer contributes its live source's pixels (effective_buffer)."""

    def test_smart_layer_reports_source_extent_not_its_own_placeholder(self):
        source_buf = _buffer(32, 32, opaque_points=[(11, 11)])
        source = Layer(source_buf, name="source")
        placeholder = _buffer(32, 32)  # empty placeholder buffer
        smart = Layer(placeholder, name="smart", smart_source=source)
        frame = Frame([smart])

        result = content_bounds(frame, 32, 32)

        assert result == (11, 11, 11, 11)
