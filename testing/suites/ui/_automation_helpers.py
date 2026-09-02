"""Shared builders + drivers for the Phase-8 automation UI tests.

Kept out of ``conftest`` fixtures so the macro / script / plugin / batch /
procgen / parity / responsiveness / teardown modules share one vocabulary. The
DSL ``Op`` / ``Macro`` builders are pure ``logic`` data (Article I / S11); the
drivers exercise the frozen ``ui.automation_worker`` off-GUI-thread path exactly
as the panels do — submit the inert ops, wait on the controller's terminal
``runFinished`` signal, and (on success) the window has already pushed the one
:class:`AutomationCommand` onto the active undo stack (in-order queued delivery on
one carrier: ``finished`` → ``resultReady`` → push, then ``done`` → ``runFinished``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np

from pixelart_creator.logic.macro import Macro, Op, record
from pixelart_creator.logic.scripting import OP_BATCH_RECOLOUR, OP_PROCGEN

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)

#: The default off-thread automation run should finish well within this budget.
RUN_TIMEOUT_MS = 8000


# --------------------------------------------------------------------------- #
# DSL op / macro builders (pure logic data)                                    #
# --------------------------------------------------------------------------- #


def procgen_op(
    *, seed: int = 7, width: int = 64, height: int = 64, algorithm: str = "value_noise"
) -> Op:
    """A seeded procgen DSL op writing ``width``×``height`` of noise into frame 0."""
    return Op(
        name=OP_PROCGEN,
        params={"algorithm": algorithm, "width": width, "height": height},
        seed=seed,
    )


def batch_recolour_op(*, src=RED, dst=GREEN, frame_index: int = 0) -> Op:
    """A batch-recolour DSL op remapping ``src`` → ``dst`` across frame ``frame_index``."""
    return Op(
        name=OP_BATCH_RECOLOUR,
        params={"frame_index": frame_index, "color_map": [[list(src), list(dst)]]},
    )


def unknown_op() -> Op:
    """A DSL op whose name is not in the trusted allow-list registry."""
    return Op(name="this_op_is_not_registered", params={})


def macro_of(*ops: Op) -> Macro:
    """Record ``ops`` into a versioned :class:`Macro` (the record/replay unit)."""
    return record(list(ops))


# --------------------------------------------------------------------------- #
# Document helpers                                                              #
# --------------------------------------------------------------------------- #


def buffer_of(document, frame_index: int = 0):
    """Return the numpy RGBA data of the frame's first leaf layer buffer."""
    return document.frames[frame_index].layers[0].buffer.data


def paint(document, colour, frame_index: int = 0) -> None:
    """Fill the frame's first layer buffer with ``colour`` (deterministic content)."""
    buffer_of(document, frame_index)[:, :] = colour


# --------------------------------------------------------------------------- #
# Off-GUI-thread automation drivers (mirror the real panel → window → worker)   #
# --------------------------------------------------------------------------- #


def run_ops(qtbot, window, ops: Sequence[Op], *, timeout: int = RUN_TIMEOUT_MS) -> None:
    """Dispatch ``ops`` on the window's active document via the real off-thread worker.

    Waits on the controller's terminal ``runFinished``; on success the window has
    already pushed one :class:`AutomationCommand` (queued in-order before
    ``runFinished``), so the caller can assert on the undo stack immediately.
    """
    with qtbot.waitSignal(window._automation_controller.runFinished, timeout=timeout):
        window._run_automation_ops(list(ops), "test-run")


def replay(qtbot, window, macro: Macro, *, timeout: int = RUN_TIMEOUT_MS) -> None:
    """Replay ``macro`` on the window's active document via the real off-thread worker."""
    with qtbot.waitSignal(window._automation_controller.runFinished, timeout=timeout):
        window._on_replay_requested(macro, "test-replay")


# --------------------------------------------------------------------------- #
# Plugin manifest fixtures on disk (defensive-load / consent flow)             #
# --------------------------------------------------------------------------- #


def write_manifest(
    path: Path,
    *,
    name: str = "demo-plugin",
    version: str = "1.0",
    api_version: str = "1",
    capabilities: Sequence[str] = ("register_command", "write_via_command"),
) -> Path:
    """Write a valid plugin manifest JSON and return the path."""
    payload = {
        "name": name,
        "version": version,
        "api_version": api_version,
        "capabilities": list(capabilities),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_malformed_manifest(path: Path) -> Path:
    """Write a manifest that is well-formed JSON but violates the allow-list schema."""
    # ``capabilities`` carries a capability not in the Capability vocabulary, so
    # validate_manifest raises PluginError — defensively, never executed.
    payload = {
        "name": "evil",
        "version": "1.0",
        "api_version": "1",
        "capabilities": ["read_document", "exfiltrate_filesystem"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def arrays_equal(a: np.ndarray, b: np.ndarray) -> bool:
    """Whether two RGBA buffers are byte-identical (state-identity assertion)."""
    return bool(np.array_equal(a, b))
