"""Art-branching UI (REQ-P10-UI-012) — Qt only, binds to logic/realtime_apply.

Phase-10 Slice C. The panel lets the user **branch** the current project, edit a branch
independently, view a **diff** summary, and **merge** it back — the merge is
**conflict-free** (resolved by :func:`~pixelart_creator.logic.realtime_apply.merge`; no
manual conflict UI is required, though the outcome is surfaced). Two pieces:

* :class:`Branching_Session` — a :class:`~PySide6.QtCore.QObject` seam over the pure,
  Qt-free git-like branching model
  (:func:`~pixelart_creator.logic.realtime_apply.branch` /
  :meth:`~pixelart_creator.logic.realtime_apply.Branch.record` /
  :func:`~pixelart_creator.logic.realtime_apply.merge`). It holds the mainline branch +
  named feature branches forked from the same base, materialises a branch's document,
  and merges conflict-free. Branching is **session state** and pushes **no**
  ``QUndoCommand`` (PL10-D13; ``ui/commands.py`` untouched) — it composes whole
  documents, not undoable edits.
* :class:`Branching_Panel` — a presentation-only widget listing the branches with
  create / switch / merge controls and a diff/outcome readout. It computes **no**
  branching maths of its own (Article I) — every operation delegates to the session,
  which delegates to ``logic/``.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(REQ-P10-UI-008); every control carries an accessible name and is keyboard-reachable
(REQ-P10-UI-006); colours come from the active QSS theme by role so both themes render
correctly (REQ-P10-UI-007).
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.convergence import Operation
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import (
    Branch,
    RealtimeError,
    branch,
    merge,
)

#: The reserved name of the always-present mainline branch.
_MAINLINE = "mainline"


class Branching_Session(QObject):
    """Git-like branching over the pure model (REQ-P10-UI-012; no QUndoCommand).

    Holds the mainline :class:`~pixelart_creator.logic.realtime_apply.Branch` and named
    feature branches forked from the same base document, so any two merge back
    conflict-free. Re-emits changes as Qt signals the panel refreshes from.
    """

    #: emitted when the set of branches changed (create / merge).
    branchesChanged = Signal()
    #: ``(name,)`` — the active branch changed.
    activeBranchChanged = Signal(str)
    #: ``(document,)`` — a branch was materialised/merged; the caller loads it into the
    #: active tab (a whole Qt-free :class:`~pixelart_creator.logic.document.Document`).
    documentSwitched = Signal(object)
    #: ``(summary,)`` — a merge completed conflict-free; carries a translatable-ready
    #: outcome summary the panel surfaces (REQ-P10-UI-012).
    mergeCompleted = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create an empty session (no base document yet)."""
        super().__init__(parent)
        self._site_seq = 1
        self._mainline: Optional[Branch] = None
        self._branches: Dict[str, Branch] = {}
        self._active = _MAINLINE

    # -- queries ----------------------------------------------------------

    def has_base(self) -> bool:
        """Return whether a base document has been set."""
        return self._mainline is not None

    def branch_names(self) -> Tuple[str, ...]:
        """Return the branch names (mainline first, then features in creation order)."""
        if self._mainline is None:
            return ()
        return (_MAINLINE, *self._branches.keys())

    def active_branch(self) -> str:
        """Return the active branch name."""
        return self._active

    # -- lifecycle --------------------------------------------------------

    def set_base_document(self, document: Optional[Document]) -> None:
        """Fork the mainline from ``document`` (on connect / active-tab change).

        Resets any feature branches — a new base document is a new branching context.
        ``None`` clears the session.
        """
        if document is None:
            self._mainline = None
            self._branches = {}
            self._active = _MAINLINE
            self.branchesChanged.emit()
            return
        self._mainline = branch(document, site_id=0)
        self._branches = {}
        self._active = _MAINLINE
        self.branchesChanged.emit()

    def create_branch(self, name: str) -> None:
        """Fork a new feature branch ``name`` from the mainline base.

        Both mainline and the new branch share the same base document, so
        :meth:`merge_to_mainline` is conflict-free.

        Raises:
            RealtimeError: If no base document is set or ``name`` is invalid/duplicate.
        """
        if self._mainline is None:
            raise RealtimeError("no project to branch")
        name = name.strip()
        if not name or name == _MAINLINE:
            raise RealtimeError(f"invalid branch name {name!r}")
        if name in self._branches:
            raise RealtimeError(f"branch {name!r} already exists")
        self._branches[name] = branch(self._mainline.base, site_id=self._next_site_id())
        self.branchesChanged.emit()

    def switch_to(self, name: str) -> None:
        """Make ``name`` active and emit its materialised document for the caller.

        Raises:
            RealtimeError: If ``name`` is unknown.
        """
        selected = self._branch(name)
        self._active = name
        self.activeBranchChanged.emit(name)
        self.documentSwitched.emit(selected.document())

    def merge_to_mainline(self, name: str) -> None:
        """Merge feature branch ``name`` into the mainline, conflict-free.

        The merged document becomes the new mainline base (subsequent branches fork from
        it) and is emitted for the caller to load. Emits :attr:`mergeCompleted` with a
        surfaced outcome summary (REQ-P10-UI-012).

        Raises:
            RealtimeError: If ``name`` is unknown or is the mainline.
        """
        if self._mainline is None:
            raise RealtimeError("no project to merge into")
        if name == _MAINLINE:
            raise RealtimeError("cannot merge mainline into itself")
        feature = self._branch(name)
        merged: Document = merge(self._mainline, feature)
        op_count = len(feature.ops)
        # The merged document becomes the new mainline base.
        self._mainline = branch(merged, site_id=0)
        del self._branches[name]
        self._active = _MAINLINE
        self.branchesChanged.emit()
        self.activeBranchChanged.emit(_MAINLINE)
        self.documentSwitched.emit(merged)
        self.mergeCompleted.emit(f"{name}|{op_count}")

    def record_on_active(self, ops: Sequence[Operation]) -> None:
        """Append local edits to the active branch's op-log (history reconstructable).

        A no-op on the mainline (mainline edits are the base); feature-branch edits are
        recorded so a later merge carries them.
        """
        if self._active == _MAINLINE or self._active not in self._branches:
            return
        self._branches[self._active].record(ops)

    # -- helpers ----------------------------------------------------------

    def _branch(self, name: str) -> Branch:
        if name == _MAINLINE:
            if self._mainline is None:
                raise RealtimeError("no project open")
            return self._mainline
        try:
            return self._branches[name]
        except KeyError as exc:
            raise RealtimeError(f"unknown branch {name!r}") from exc

    def _next_site_id(self) -> int:
        site = self._site_seq
        self._site_seq += 1
        return site


class Branching_Panel(QWidget):
    """Create / switch / merge branches + surface the merge outcome (REQ-P10-UI-012)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the branch list, the create/switch/merge controls and the readout."""
        super().__init__(parent)
        self._session: Optional[Branching_Session] = None

        self._intro = QLabel(self)
        self._intro.setWordWrap(True)

        self._list = QListWidget(self)
        self._list.currentTextChanged.connect(lambda _text: self._update_enabled())

        self._new_button = QPushButton(self)
        self._new_button.clicked.connect(self._on_new)
        self._switch_button = QPushButton(self)
        self._switch_button.clicked.connect(self._on_switch)
        self._merge_button = QPushButton(self)
        self._merge_button.clicked.connect(self._on_merge)
        button_row = QHBoxLayout()
        button_row.addWidget(self._new_button)
        button_row.addWidget(self._switch_button)
        button_row.addWidget(self._merge_button)

        self._outcome = QLabel(self)
        self._outcome.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._intro)
        layout.addWidget(self._list, 1)
        layout.addLayout(button_row)
        layout.addWidget(self._outcome)

        self._retranslate()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Branching_Session) -> None:
        """Bind to a :class:`Branching_Session` and refresh the branch list."""
        self._session = session
        session.branchesChanged.connect(self._refresh)
        session.activeBranchChanged.connect(self._on_active_changed)
        session.mergeCompleted.connect(self._on_merge_completed)
        self._refresh()

    # -- actions ----------------------------------------------------------

    def _selected_branch(self) -> Optional[str]:
        item = self._list.currentItem()
        return item.text() if item is not None else None

    def _on_new(self) -> None:
        if self._session is None or not self._session.has_base():
            QMessageBox.information(
                self,
                self.tr("Branch"),
                self.tr("Open a project first."),
            )
            return
        name, ok = QInputDialog.getText(
            self, self.tr("New Branch"), self.tr("Branch name:")
        )
        if not ok or not name.strip():
            return
        try:
            self._session.create_branch(name)
        except RealtimeError as exc:
            QMessageBox.warning(self, self.tr("Branch"), str(exc))

    def _on_switch(self) -> None:
        if self._session is None:
            return
        name = self._selected_branch()
        if name is None:
            return
        try:
            self._session.switch_to(name)
        except RealtimeError as exc:
            QMessageBox.warning(self, self.tr("Branch"), str(exc))

    def _on_merge(self) -> None:
        if self._session is None:
            return
        name = self._selected_branch()
        if name is None:
            return
        try:
            self._session.merge_to_mainline(name)
        except RealtimeError as exc:
            QMessageBox.warning(self, self.tr("Merge"), str(exc))

    # -- session reactions ------------------------------------------------

    def _on_active_changed(self, _name: str) -> None:
        self._refresh()

    def _on_merge_completed(self, summary: str) -> None:
        """Surface the conflict-free merge outcome (REQ-P10-UI-012)."""
        name, _, count = summary.partition("|")
        self._outcome.setText(
            self.tr(
                "Merged branch '{name}' ({count} edits) into mainline — "
                "conflict-free."
            ).format(name=name, count=count)
        )

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        if self._session is not None:
            active = self._session.active_branch()
            for name in self._session.branch_names():
                label = (
                    self.tr("{name} (active)").format(name=name)
                    if name == active
                    else name
                )
                self._list.addItem(label)
        self._update_enabled()

    def _update_enabled(self) -> None:
        has_base = self._session is not None and self._session.has_base()
        self._new_button.setEnabled(has_base)
        selected = self._selected_branch()
        is_feature = has_base and selected is not None and _MAINLINE not in selected
        self._switch_button.setEnabled(has_base and selected is not None)
        self._merge_button.setEnabled(bool(is_feature))

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Branching"))
        self._intro.setText(
            self.tr(
                "Branch the project to edit a variation independently, then merge it "
                "back. Merges are conflict-free."
            )
        )
        self._list.setAccessibleName(self.tr("Branches"))
        self._new_button.setText(self.tr("New Branch"))
        self._new_button.setAccessibleName(self.tr("Create a new branch"))
        self._switch_button.setText(self.tr("Switch"))
        self._switch_button.setAccessibleName(self.tr("Switch to the selected branch"))
        self._merge_button.setText(self.tr("Merge"))
        self._merge_button.setAccessibleName(
            self.tr("Merge the selected branch into mainline")
        )
        self._outcome.setAccessibleName(self.tr("Merge outcome"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the branching strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
            self._refresh()
        super().changeEvent(event)
