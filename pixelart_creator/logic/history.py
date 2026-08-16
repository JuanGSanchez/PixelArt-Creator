"""Reversible-command undo/redo stack (zero Qt, S11).

This is the pure-Python core of the command pattern (Architecture §2.1). The Qt
``QUndoCommand`` bridge lives in ``ui/commands.py`` (the sole Qt file outside
``ui/``, S11) and delegates to these reversible commands, so undo semantics are
defined and tested once, headlessly.
"""

from __future__ import annotations

import abc
from typing import Callable, List, Optional, Tuple, Union

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue

#: One recorded pixel change: ``(x, y, old_value, new_value)``.
PixelChange = Tuple[int, int, PixelValue, PixelValue]


class Command(abc.ABC):
    """A reversible operation with symmetric :meth:`execute` / :meth:`undo`."""

    #: Human-readable label (used by the UI undo menu).
    label: str = "command"

    @abc.abstractmethod
    def execute(self) -> None:
        """Apply the change (also used for redo)."""

    @abc.abstractmethod
    def undo(self) -> None:
        """Revert the change applied by :meth:`execute`."""


class PixelEdit(Command):
    """A batch of pixel changes on one buffer, replayable both ways."""

    __slots__ = ("_buffer", "_changes", "label")

    def __init__(
        self,
        buffer: PixelBuffer,
        changes: List[PixelChange],
        label: str = "draw",
    ) -> None:
        """Store the target `buffer`, the recorded `changes`, and the undo `label`."""
        self._buffer = buffer
        self._changes = changes
        self.label = label

    def __len__(self) -> int:
        """Return the number of recorded pixel changes."""
        return len(self._changes)

    def execute(self) -> None:
        """Apply every recorded change's new value, in order."""
        for x, y, _old, new in self._changes:
            self._buffer.set_pixel(x, y, new)

    def undo(self) -> None:
        """Restore every recorded change's old value, in reverse order."""
        for x, y, old, _new in reversed(self._changes):
            self._buffer.set_pixel(x, y, old)


class FunctionCommand(Command):
    """Adapter wrapping arbitrary ``do`` / ``undo`` callables."""

    __slots__ = ("_do", "_undo", "label")

    def __init__(
        self, do: Callable[[], None], undo: Callable[[], None], label: str = "command"
    ) -> None:
        """Store the `do`/`undo` callables and the undo-menu `label`."""
        self._do = do
        self._undo = undo
        self.label = label

    def execute(self) -> None:
        """Invoke the wrapped `do` callable."""
        self._do()

    def undo(self) -> None:
        """Invoke the wrapped `undo` callable."""
        self._undo()


class GroupCommand(Command):
    """A composite of ordered sub-commands applied/reverted as one unit.

    ``execute`` runs each child's :meth:`Command.execute` in order;
    ``undo`` runs each child's :meth:`Command.undo` in reverse order — so the
    whole group is a single reversible step (``apply ∘ undo = identity`` when
    every child is). This is the grouping primitive the Phase-8 DSL dispatcher
    (``logic/scripting.dispatch``) and batch recolour (``logic/batch_ops``)
    return so ``ui/commands.py`` can wrap an entire automation edit — a script
    run, a macro replay, a batch — as one ``QUndoCommand`` (REQ-P8-UI-009), and
    so the CLI applies it headlessly identically (REQ-P8-LOGIC-006/-014).
    """

    __slots__ = ("_commands", "label")

    def __init__(
        self, commands: "List[Command]", label: str = "grouped command"
    ) -> None:
        """Wrap an ordered list of sub-commands as one reversible unit."""
        self._commands = list(commands)
        self.label = label

    def __len__(self) -> int:
        """Return the number of sub-commands in the group."""
        return len(self._commands)

    @property
    def commands(self) -> "Tuple[Command, ...]":
        """Return the ordered sub-commands as a read-only tuple view."""
        return tuple(self._commands)

    def execute(self) -> None:
        """Run each sub-command's :meth:`Command.execute` in order."""
        for command in self._commands:
            command.execute()

    def undo(self) -> None:
        """Run each sub-command's :meth:`Command.undo` in reverse order."""
        for command in reversed(self._commands):
            command.undo()


class History:
    """A bounded undo/redo stack of :class:`Command` objects."""

    __slots__ = ("_undo", "_redo", "_limit")

    def __init__(self, limit: Optional[int] = None) -> None:
        """Create an empty history.

        Args:
            limit: Maximum retained undo steps (oldest dropped past it). ``None``
                means unbounded. Must be a positive int if given.
        """
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f"history limit must be a positive int, got {limit!r}")
        self._undo: List[Command] = []
        self._redo: List[Command] = []
        self._limit = limit

    def push(self, command: Command, *, execute: bool = True) -> None:
        """Record ``command`` (running it unless already applied).

        Pushing a new command clears the redo stack (standard linear history).
        """
        if execute:
            command.execute()
        self._undo.append(command)
        self._redo.clear()
        if self._limit is not None and len(self._undo) > self._limit:
            del self._undo[0 : len(self._undo) - self._limit]

    @property
    def can_undo(self) -> bool:
        """Whether an undo step is available."""
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """Whether a redo step is available."""
        return bool(self._redo)

    def undo(self) -> Optional[Command]:
        """Undo and return the last command, or ``None`` if nothing to undo."""
        if not self._undo:
            return None
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return command

    def redo(self) -> Optional[Command]:
        """Redo and return the next command, or ``None`` if nothing to redo."""
        if not self._redo:
            return None
        command = self._redo.pop()
        command.execute()
        self._undo.append(command)
        return command

    def clear(self) -> None:
        """Discard all history."""
        self._undo.clear()
        self._redo.clear()

    @property
    def undo_depth(self) -> int:
        """Number of available undo steps."""
        return len(self._undo)

    @property
    def redo_depth(self) -> int:
        """Number of available redo steps."""
        return len(self._redo)


def record_edit(
    buffer: PixelBuffer,
    operation: Callable[[PixelBuffer], List[Tuple[int, int]]],
    *,
    label: str = "draw",
) -> PixelEdit:
    """Run a drawing ``operation`` and capture it as a reversible :class:`PixelEdit`.

    The operation mutates ``buffer`` and returns the coordinates it changed
    (the ``logic/drawing.py`` contract). A transient snapshot captures the old
    values so the resulting command stores only the touched pixels — not the
    whole buffer.

    Returns:
        A :class:`PixelEdit` already applied to ``buffer`` (push it with
        ``execute=False``).
    """
    before = buffer.copy()
    coords = operation(buffer)
    changes: List[PixelChange] = []
    seen: set[Tuple[int, int]] = set()
    for x, y in coords:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        old: Union[RGBA, int] = before.get_pixel(x, y)
        new: Union[RGBA, int] = buffer.get_pixel(x, y)
        if old != new:
            changes.append((x, y, old, new))
    return PixelEdit(buffer, changes, label=label)
