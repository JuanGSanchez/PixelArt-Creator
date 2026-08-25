"""Tests for the canvas-grid-semantics constants added to
``pixelart_creator.logic.constants`` (REQ-CGS-UI-003, REQ-CGS-UI-010).

Regression context: the transparency checker was previously drawn at
``TILE_SIZE`` (=64) document px per square, conflating a viewport-culling
render edge with a transparency-checker quantity. A default 64x64 document
was therefore exactly ONE checker square, so a user drew inside what they
took to be a cell and coloured 1/4096th of it (field defect). These tests
assert the distinctness that prevents that conflation recurring, and make
the LOD bound (REQ-CGS-UI-010 / SC-CGS-UI-003-3) machine-checkable rather
than merely documented in prose.

Qt-free: no PySide6 import anywhere in this module (tests/logic is the
Qt-free root).
"""

from pixelart_creator.logic.constants import (
    CANVAS_BORDER_WIDTH_PX,
    CHECKER_CELL_PX,
    CHECKER_MIN_ON_SCREEN_EDGE_PX,
    CRDT_TILE_SIZE_PX,
    DEFAULT_TILE_HEIGHT,
    DEFAULT_TILE_WIDTH,
    HARMONY_TETRADIC_DEG,
    TILE_SIZE,
    ZOOM_MIN,
)


class TestCheckerCellPx:
    """CHECKER_CELL_PX is the transparency-checker's own scalar (SC-CGS-UI-003-3)."""

    def test_value_is_one_document_pixel(self):
        assert CHECKER_CELL_PX == 1, (
            "CHECKER_CELL_PX must be 1 document px so one checker square is "
            "one document pixel (REQ-CGS-UI-003); got "
            f"{CHECKER_CELL_PX!r}."
        )

    def test_distinct_from_every_other_tile_quantity(self):
        conflated_with = {
            "TILE_SIZE (viewport-cull render edge)": TILE_SIZE,
            "DEFAULT_TILE_WIDTH (tileset content tile)": DEFAULT_TILE_WIDTH,
            "DEFAULT_TILE_HEIGHT (tileset content tile)": DEFAULT_TILE_HEIGHT,
            "CRDT_TILE_SIZE_PX (collaboration transport tile)": CRDT_TILE_SIZE_PX,
        }
        collisions = {
            name: value
            for name, value in conflated_with.items()
            if value == CHECKER_CELL_PX
        }
        assert not collisions, (
            "CHECKER_CELL_PX must stay numerically distinct from every other "
            "tile-shaped constant, or the field defect (a document-sized "
            "default appearing to be exactly one checker square) can recur "
            f"silently. Colliding constants: {collisions!r}."
        )


class TestUnrelatedTileConstantsUnchanged:
    """This batch moved neither TILE_SIZE nor the default tile dimensions."""

    def test_tile_size_unchanged(self):
        assert TILE_SIZE == 64, (
            "TILE_SIZE (viewport-cull render edge) must remain 64; the "
            "canvas-grid-semantics batch must not have moved it. Got "
            f"{TILE_SIZE!r}."
        )

    def test_default_tile_width_unchanged(self):
        assert DEFAULT_TILE_WIDTH == 16, (
            "DEFAULT_TILE_WIDTH (tileset content tile) must remain 16; the "
            "canvas-grid-semantics batch must not have moved it. Got "
            f"{DEFAULT_TILE_WIDTH!r}."
        )

    def test_default_tile_height_unchanged(self):
        assert DEFAULT_TILE_HEIGHT == 16, (
            "DEFAULT_TILE_HEIGHT (tileset content tile) must remain 16; the "
            "canvas-grid-semantics batch must not have moved it. Got "
            f"{DEFAULT_TILE_HEIGHT!r}."
        )

    def test_default_tile_width_equals_height(self):
        assert DEFAULT_TILE_WIDTH == DEFAULT_TILE_HEIGHT, (
            "DEFAULT_TILE_WIDTH and DEFAULT_TILE_HEIGHT must stay equal "
            f"(square default tile); got {DEFAULT_TILE_WIDTH!r} and "
            f"{DEFAULT_TILE_HEIGHT!r}."
        )


class TestCheckerLodBound:
    """REQ-CGS-UI-010: the LOD-degrade threshold must never fire at the 1:1
    zoom floor, or the checker silently repeals "one square is one document
    pixel" at the product's most common zoom.
    """

    def test_lod_threshold_does_not_exceed_cell_size_at_zoom_floor(self):
        bound = CHECKER_CELL_PX * ZOOM_MIN
        assert CHECKER_MIN_ON_SCREEN_EDGE_PX <= bound, (
            "CHECKER_MIN_ON_SCREEN_EDGE_PX "
            f"({CHECKER_MIN_ON_SCREEN_EDGE_PX!r} device px) exceeds "
            f"CHECKER_CELL_PX * ZOOM_MIN ({bound!r} device px). At the 1:1 "
            "zoom floor a checker cell renders at exactly "
            f"{bound!r} device px; a threshold greater than that fires at "
            "the floor and degrades the checker to a flat blend at the "
            "product's MOST COMMON zoom, silently repealing 'one alternating "
            "square is one document pixel' (REQ-CGS-UI-010). This is not "
            "hypothetical: an earlier draft proposed 3.0 for "
            "CHECKER_MIN_ON_SCREEN_EDGE_PX and was caught only at the "
            "requirements gate — this assertion is what stops a future "
            "regression instead of trusting a docstring to be read."
        )


class TestHarmonyTetradicDeg:
    """HARMONY_TETRADIC_DEG is the colour-harmony tetradic-relationship angle."""

    def test_value_is_ninety_degrees(self):
        assert (
            HARMONY_TETRADIC_DEG == 90
        ), f"HARMONY_TETRADIC_DEG must be 90 degrees; got {HARMONY_TETRADIC_DEG!r}."


class TestCanvasBorderWidthPx:
    """CANVAS_BORDER_WIDTH_PX exists, is a screen-space (device px) scalar,
    and stays distinct by unit from the checker's own two scalars.
    """

    def test_value_is_one_device_pixel(self):
        assert CANVAS_BORDER_WIDTH_PX == 1, (
            "CANVAS_BORDER_WIDTH_PX must be 1 device px; got "
            f"{CANVAS_BORDER_WIDTH_PX!r}."
        )
