"""Off-GUI-thread composite warming for playback pre-warm (D1/D2).

Pressing **Play** on a cold N-frame range used to fire N synchronous
``composite_stack`` flattens on the GUI thread (a ~20 s 8K flatten per frame), so
the window froze for the whole cold pass. This module moves each cold-frame
flatten **off** the GUI thread:

* :class:`FrameCompositeWarmRunnable` is a :class:`~PySide6.QtCore.QRunnable` that
  calls the **Qt-free** :func:`~pixelart_creator.logic.blend.composite_stack` on a
  frame's source nodes on a worker thread and emits the resulting
  :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`; it never touches any
  Qt / QGraphics object.
* :class:`CompositeWarmSignals` is a GUI-thread-affine signal carrier: because it
  lives on the GUI thread, the ``frameReady`` emission from the worker is
  delivered through an **auto/queued** connection, so the scene only ever *owns*
  the produced buffer inside its GUI-thread slot — no cross-thread QGraphics
  access and no shared-state race (the source buffers are read-only off-thread and
  the scene cancels any in-flight warm on an edit).

A shared :class:`threading.Event` gives a best-effort early exit (checked before
and after the flatten); correctness on cancel/supersede is guaranteed by a warm
**token** carried in the signal and validated by the scene, so a stale result is
dropped even if its flatten had already begun.
"""

from __future__ import annotations

import threading
from typing import Sequence

from PySide6.QtCore import QObject, QRunnable, Signal

from pixelart_creator.logic.blend import CompositeNode, composite_stack


class CompositeWarmSignals(QObject):
    """GUI-thread-affine carrier for the worker's ``frameReady`` signal (D2)."""

    #: ``(token, frame_index, PixelBuffer)`` — a warmed composite, delivered queued
    #: to the GUI thread. The buffer is a fresh, worker-allocated object; the scene
    #: takes ownership only in the connected GUI-thread slot.
    frameReady = Signal(int, int, object)


class FrameCompositeWarmRunnable(QRunnable):
    """Flatten one frame's layer stack off the GUI thread (D2)."""

    def __init__(
        self,
        token: int,
        index: int,
        nodes: Sequence[CompositeNode],
        width: int,
        height: int,
        cancel: threading.Event,
        signals: CompositeWarmSignals,
    ) -> None:
        """Capture the job: ``token``, frame ``index``, source ``nodes`` + geometry.

        ``cancel`` is the scene's shared cancellation event (checked before and
        after the flatten); ``signals`` is the GUI-thread carrier the result is
        emitted through. ``nodes`` are the frame's live source layer nodes, read
        **read-only** by the Qt-free compositor.
        """
        super().__init__()
        self._token = int(token)
        self._index = int(index)
        self._nodes = nodes
        self._width = int(width)
        self._height = int(height)
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Composite the frame off-thread and emit it (unless cancelled)."""
        if self._cancel.is_set():
            return
        result = composite_stack(self._nodes, self._width, self._height)
        if self._cancel.is_set():
            return
        # ``composite_stack`` returns a freshly allocated PixelBuffer that shares no
        # memory with the source buffers, so it is safe to hand across the queued
        # connection to the GUI thread as-is (no extra copy).
        self._signals.frameReady.emit(self._token, self._index, result)
