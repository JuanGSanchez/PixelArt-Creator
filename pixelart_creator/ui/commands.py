"""Qt undo bridge — the sole Qt-aware undo module (REQ-P1-UI-009, -010; C1/F1).

``PaintCommand`` wraps a Qt-free :class:`~pixelart_creator.logic.history.PixelEdit`
(captured by :func:`~pixelart_creator.logic.history.record_edit`) so a
:class:`QUndoStack` can drive it. ``redo()``/``undo()`` **delegate** to
``PixelEdit.execute()``/``PixelEdit.undo()`` — this module holds **no** domain
math (Article I); it only bridges Qt's undo framework to the logic command and
schedules a dirty-rect refresh (D5).

``QUndoStack``/``QUndoCommand`` are imported from ``PySide6.QtGui`` (moved from
``QtWidgets`` in Qt6 — F1).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QUndoCommand

from pixelart_creator.logic.history import PixelEdit

#: Called with the dirty rect (scene/pixel coords) after every apply/revert so
#: the view can repaint only the affected region (D5).
RefreshCallback = Callable[[QRectF], None]


class PaintCommand(QUndoCommand):
    """A single undoable stroke: one :class:`PixelEdit`, one dirty rect (CL-9).

    The ``edit`` has already been applied to its buffer by ``record_edit`` (it
    was built with ``execute=False`` semantics), so the first ``redo()`` — which
    :meth:`QUndoStack.push` fires automatically — must **not** re-apply it;
    subsequent redos (after an undo) re-run ``execute()``.

    Args:
        edit: The reversible pixel edit to bridge.
        refresh: Callback repainting the dirty rect (D5); receives ``dirty_rect``.
        dirty_rect: Bounding rect of the changed pixels, in scene/pixel coords.
        text: Undo-menu label; defaults to the edit's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        edit: PixelEdit,
        refresh: RefreshCallback,
        dirty_rect: QRectF,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        super().__init__(text or edit.label, parent)
        self._edit = edit
        self._refresh = refresh
        self._dirty_rect = QRectF(dirty_rect)
        self._applied = True  # record_edit already applied it once.

    def redo(self) -> None:
        """Re-apply the edit (skipping the redundant first apply-on-push)."""
        if self._applied:
            self._applied = False
        else:
            self._edit.execute()
        self._refresh(self._dirty_rect)

    def undo(self) -> None:
        """Revert exactly the pixels the edit changed, then repaint them."""
        self._edit.undo()
        self._applied = False
        self._refresh(self._dirty_rect)
