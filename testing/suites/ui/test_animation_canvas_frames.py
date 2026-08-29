"""Phase-5 canvas frame-navigation / onion / pre-warm UI coverage (both themes).

Drives the ``CanvasScene`` frame-switch, onion-overlay and off-thread warm branches
that back the timeline seams (REQ-P5-UI-002/-011/-012 and the AGT-05 streaming
pre-warm), so the ``pixelart_creator.ui`` branch gate holds (FU-9). UI-level only —
the onion/composite maths live in ``logic`` (Article I). Modest 64x64 canvases.
"""

from __future__ import annotations

import pytest
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.theme import canvas_roles

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]
RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _rgba_doc(frames: int = 3) -> Document:
    doc = Document(64, 64, palette=Palette(STARTER))
    for _ in range(frames - 1):
        doc.add_frame()
    for i, colour in enumerate((RED, GREEN, BLUE, GREEN, RED)[:frames]):
        doc.frames[i].layers[0].buffer.fill_rect(0, 0, 64, 64, colour)
    return doc


@pytest.fixture
def make_scene(theme):
    def _make(doc: Document) -> CanvasScene:
        scene = CanvasScene(doc)
        scene.set_background_roles(*canvas_roles(theme))
        return scene

    return _make


def test_scene_reselect_same_frame_refreshes_onion(make_scene):
    """Re-selecting the active frame refreshes onion when settled, skips it on scrub."""
    scene = make_scene(_rgba_doc(3))
    scene.set_onion_settings(True, 1, 1, RED, BLUE)
    assert scene.set_frame_index(1) is True  # real switch to the middle frame
    assert len(scene._onion_item._ghosts) == 2
    # Re-select the same frame, settled -> onion recomputed (still shown).
    assert scene.set_frame_index(1, scrub=False) is True
    assert len(scene._onion_item._ghosts) == 2
    # Re-select the same frame while scrubbing -> fast path, no onion recompute.
    assert scene.set_frame_index(1, scrub=True) is True


def test_scene_set_frame_out_of_range(make_scene):
    """An out-of-range frame index is rejected (returns False, no switch)."""
    scene = make_scene(_rgba_doc(2))
    assert scene.set_frame_index(99) is False
    assert scene.frame_index == 0


def test_scene_scrub_switch_suppresses_onion(make_scene):
    """A scrub switch clears the onion overlay (kept off the interactive budget)."""
    scene = make_scene(_rgba_doc(3))
    scene.set_onion_settings(True, 1, 1, RED, BLUE)
    scene.set_frame_index(1)
    assert len(scene._onion_item._ghosts) == 2
    scene.set_frame_index(2, scrub=True)  # scrub clears onion
    assert scene._onion_item._ghosts == []


def test_scene_cache_hit_roundtrip(make_scene):
    """Switching away and back to a frame serves it from the per-frame cache."""
    scene = make_scene(_rgba_doc(3))
    scene.set_frame_index(1)
    scene.set_frame_index(0)
    assert scene.set_frame_index(1) is True  # cache hit
    assert scene.frame_index == 1


def test_scene_cold_playback_advance_is_async(qtbot, make_scene):
    """A cold playback advance (block_on_miss=False) holds display + warms off-thread."""
    scene = make_scene(_rgba_doc(4))
    # Frame 2 is cold (only the active frame 0 is warm at construction).
    assert scene.is_frame_warm(2) is False
    shown = scene.set_frame_index(2, scrub=True, block_on_miss=False)
    assert shown is False  # not displayed synchronously; warmed off-thread
    assert scene.frame_index == 0  # display held on the current frame
    scene.shutdown_prewarm()


def test_scene_refresh_frames_with_index(make_scene):
    """refresh_frames(index) rebinds the active frame after a structural op."""
    scene = make_scene(_rgba_doc(3))
    scene.refresh_frames(2)
    assert scene.frame_index == 2


def test_scene_indexed_doc_no_onion_no_warm(make_scene):
    """An indexed document skips compositing: always warm, no onion, warm is a no-op."""
    doc = Document(32, 32, mode=ColorMode.INDEXED, palette=Palette(STARTER))
    doc.add_frame()
    scene = make_scene(doc)
    assert scene.is_frame_warm(0) is True and scene.is_frame_warm(1) is True
    scene.set_onion_settings(True, 1, 1, RED, BLUE)  # non-compositing -> no ghosts
    assert scene._onion_item._ghosts == []
    scene.prewarm_frames([1])  # non-compositing -> no-op (no warm session)
    assert scene._warming is False
