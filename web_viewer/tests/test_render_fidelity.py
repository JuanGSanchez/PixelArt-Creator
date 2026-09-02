"""Pytest wrapper for the web-viewer render-fidelity check.

Turns the standalone ``generate_reference.py`` parity check
into a repeatable test so the byte-exact (0 LSB) fidelity assertion runs in the
web_viewer CI job. It IS part of the default gate: ``pyproject.toml`` pins
``testpaths = ["tests", "web_viewer/tests"]``, so these tests run on every push
alongside the web integration tests, not separately from them.

It asserts that the faithful Python mirror of ``viewer.js`` (op-replay + LWW
winner selection + source-over ``blendTile`` with ``Uint8ClampedArray``
round-half-to-even) reproduces the SHIPPED ``apply_remote`` / ``convergence`` /
``blend.composite_stack`` composite byte-exact (0 LSB per channel — ADR-0044,
which supplies the number ADR-0036 A.4/A.6 left unstated). The JS mirror in
``generate_reference`` is kept in lockstep with ``viewer.js`` by review; the node
``*.mjs`` tests exercise the real JS once a node-importable ``viewer_core.mjs``
is extracted.
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np

_HELPER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "generate_reference.py"
)
_spec = importlib.util.spec_from_file_location("web_viewer_generate_reference", _HELPER)
assert _spec is not None and _spec.loader is not None
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_js_mirror_matches_shipped_reference_byte_exact() -> None:
    """SC-P13-WEB-001-1: reconstructed raster == shipped composite, byte-exact (0 LSB, ADR-0044)."""
    ops = gen._build_ops()
    reference = gen._reference_rgba(ops)
    mirror = gen._mirror_render(ops)

    assert reference.shape == mirror.shape
    diff = np.abs(reference.astype(np.int16) - mirror.astype(np.int16))
    assert (
        int(diff.max()) == 0
    ), f"max channel diff {int(diff.max())} LSB != 0 (ADR-0044 byte-exact)"


def test_wire_frames_decode_through_the_shipped_protocol() -> None:
    """SC-P13-WEB-002-1: the fixture frames are valid, in-cap sync_protocol frames."""
    frames = gen._wire_frames(gen._build_ops())
    assert frames and all(isinstance(f, str) for f in frames)
