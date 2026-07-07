"""Layer panel — the layer/group tree + per-row controls (REQ-P4-UI-001..011).

``Layer_Panel`` lists the active frame's layer/group tree **top-to-bottom,
topmost-first** (CL-3, UI-001), reflecting the ``logic/document`` tree. Each row
exposes an opacity slider (UI-002), a visibility toggle (UI-003), a lock toggle
(UI-004) and a blend-mode dropdown populated by iterating ``list(BlendMode)``
(UI-005 — never a hard-coded count). A toolbar drives add / remove / duplicate
(UI-007), group / ungroup (UI-008), and the mask / reference / smart affordances
(UI-009/-010/-011). Rows are drag-reorderable, including re-parenting into and out
of groups (UI-006).

Every mutation delegates to a ``logic/document`` op wrapped as **exactly one**
:class:`~pixelart_creator.ui.commands.LayerCommand` (UI-013): the panel never
mutates the tree itself; it builds the reversible ``history.Command`` the document
returns, pushes it onto the active document's :class:`QUndoStack`, and rebuilds /
re-syncs from the document (the single source of truth). No domain maths lives
here (Article I / S11); the widget only binds to the logic layer and manages Qt.

All user-visible strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (UI-018); interactive controls carry accessible
names and are keyboard-reachable (UI-016); colours come from the active QSS theme
by role, so both themes render correctly (UI-017).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QDropEvent, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.blend import BlendMode
from pixelart_creator.logic.document import (
    Document,
    DocumentError,
    Layer,
    LayerGroup,
    LayerNode,
)
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.commands import LayerCommand

#: A node address in the frame tree — the logic index path used by the document
#: layer ops (top-level index, then indices descending through nested groups).
Path = Tuple[int, ...]

#: A fully-shown mask (opaque alpha everywhere ⇒ no modulation, LOGIC-012).
_MASK_SHOWN: tuple = (255, 255, 255, 255)


class _Node_Row(QWidget):
    """Per-node control row: visibility, lock, name, opacity, blend mode.

    Purely presentational: each control builds the reversible ``document`` op for
    its attribute and hands it to the panel to push as one command. Applies to a
    leaf :class:`Layer` and a :class:`LayerGroup` alike (both carry the same
    compositing attributes).
    """

    def __init__(
        self,
        panel: "Layer_Panel",
        node: LayerNode,
        path: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self._node = node
        self._path = path
        self._committed_opacity = node.opacity

        self._vis = QToolButton(self)
        self._vis.setCheckable(True)
        self._vis.setChecked(node.visible)
        self._lock = QToolButton(self)
        self._lock.setCheckable(True)
        self._lock.setChecked(node.locked)
        self._name = QLabel(node.name, self)
        self._badges = QLabel(self)
        self._opacity = QSlider(Qt.Orientation.Horizontal, self)
        self._opacity.setRange(0, 100)
        self._opacity.setValue(int(round(node.opacity * 100)))
        self._opacity.setFixedWidth(80)
        self._blend = QComboBox(self)
        for mode in list(BlendMode):  # iterate the enum — never a hard count.
            self._blend.addItem(panel.blend_label(mode), mode)
        blend_idx = self._blend.findData(node.blend_mode)
        if blend_idx >= 0:
            self._blend.setCurrentIndex(blend_idx)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)
        layout.addWidget(self._vis)
        layout.addWidget(self._lock)
        layout.addWidget(self._name, 1)
        layout.addWidget(self._badges)
        layout.addWidget(self._opacity)
        layout.addWidget(self._blend)

        # Connect AFTER seeding values so construction never pushes a command.
        self._vis.toggled.connect(self._on_visible)
        self._lock.toggled.connect(self._on_lock)
        self._opacity.sliderPressed.connect(self._on_opacity_pressed)
        self._opacity.valueChanged.connect(self._on_opacity_changed)
        self._opacity.sliderReleased.connect(self._on_opacity_released)
        self._blend.currentIndexChanged.connect(self._on_blend)

        self.retranslate()
        self._sync_badges()

    # -- queries ----------------------------------------------------------

    def path(self) -> Path:
        """Return this row's node address (logic index path)."""
        return self._path

    def node(self) -> LayerNode:
        """Return the node this row controls."""
        return self._node

    # -- state sync (undo/redo without recreating the widget) ------------

    def sync(self) -> None:
        """Re-read the node into every control (signals blocked)."""
        self._committed_opacity = self._node.opacity
        for control in (self._vis, self._lock, self._opacity, self._blend):
            control.blockSignals(True)
        self._vis.setChecked(self._node.visible)
        self._lock.setChecked(self._node.locked)
        self._opacity.setValue(int(round(self._node.opacity * 100)))
        idx = self._blend.findData(self._node.blend_mode)
        if idx >= 0:
            self._blend.setCurrentIndex(idx)
        for control in (self._vis, self._lock, self._opacity, self._blend):
            control.blockSignals(False)
        self._name.setText(self._node.name)
        self._sync_badges()

    def _sync_badges(self) -> None:
        marks: List[str] = []
        if getattr(self._node, "reference", False):
            marks.append(self.tr("Ref"))
        if self._node.mask is not None:
            marks.append(self.tr("Mask"))
        if isinstance(self._node, Layer) and self._node.smart_source is not None:
            marks.append(self.tr("Smart"))
        self._badges.setText(" ".join(marks))

    # -- attribute mutations (one LayerCommand each) ----------------------

    def _on_visible(self, checked: bool) -> None:
        doc = self._panel.document
        if doc is None:
            return
        cmd = doc.set_layer_visible(
            list(self._path), checked, frame_index=self._panel.frame_index
        )
        self._panel.push_attr(cmd, self.tr("Toggle Visibility"))

    def _on_lock(self, checked: bool) -> None:
        doc = self._panel.document
        if doc is None:
            return
        cmd = doc.set_layer_locked(
            list(self._path), checked, frame_index=self._panel.frame_index
        )
        self._panel.push_attr(cmd, self.tr("Toggle Lock"))

    def _on_blend(self, index: int) -> None:
        doc = self._panel.document
        if doc is None:
            return
        mode = self._blend.itemData(index)
        if not isinstance(mode, BlendMode):
            return
        cmd = doc.set_layer_blend_mode(
            list(self._path), mode, frame_index=self._panel.frame_index
        )
        self._panel.push_attr(cmd, self.tr("Set Blend Mode"))

    def _on_opacity_pressed(self) -> None:
        # Phase-12 Slice B: ask the canvas to build the drag-scoped split-cache so
        # the drag ticks render a 16 ms LOD preview (ADR-0034 §2 / FU-16b). A False
        # return (nested node / no viewport / indexed doc) keeps the shipped naive
        # throttled recomposite — the release commit is byte-exact either way.
        self._panel.begin_opacity_drag(self._path)

    def _on_opacity_changed(self, value: int) -> None:
        # Live preview while dragging (recomposite, no command); a keyboard /
        # programmatic change (slider not held down) commits immediately.
        self._node.opacity = value / 100.0
        self._panel.live_recomposite()
        if not self._opacity.isSliderDown():
            self._commit_opacity(value)

    def _on_opacity_released(self) -> None:
        self._commit_opacity(self._opacity.value())

    def _commit_opacity(self, value: int) -> None:
        doc = self._panel.document
        if doc is None:
            return
        final = value / 100.0
        # Restore the pre-drag value so the command captures the correct prior
        # state; its redo re-applies the final value (undo → exact prior, UI-013).
        self._node.opacity = self._committed_opacity
        try:
            cmd = doc.set_layer_opacity(
                list(self._path), final, frame_index=self._panel.frame_index
            )
        except DocumentError:
            return
        self._panel.push_attr(cmd, self.tr("Set Opacity"))

    # -- i18n / a11y ------------------------------------------------------

    def retranslate(self) -> None:
        """Re-set every ``tr()`` label + accessible name (UI-016/-018)."""
        self._vis.setText(self.tr("V"))
        self._vis.setToolTip(self.tr("Toggle layer visibility"))
        self._vis.setAccessibleName(self.tr("Visibility"))
        self._lock.setText(self.tr("L"))
        self._lock.setToolTip(self.tr("Lock layer against painting"))
        self._lock.setAccessibleName(self.tr("Lock"))
        self._name.setAccessibleName(self.tr("Layer name"))
        self._badges.setAccessibleName(self.tr("Layer flags"))
        self._opacity.setToolTip(self.tr("Layer opacity"))
        self._opacity.setAccessibleName(self.tr("Opacity"))
        self._blend.setToolTip(self.tr("Blend mode"))
        self._blend.setAccessibleName(self.tr("Blend mode"))
        self._sync_badges()


class _Layer_Tree(QTreeWidget):
    """Single-column layer tree; owns drag-reorder → one move command."""

    def __init__(self, panel: "Layer_Panel", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setExpandsOnDoubleClick(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt override)
        """Translate a drop into ONE ``move_layer`` command (UI-006).

        Qt is never allowed to mutate the tree — the document is the single
        source of truth; the panel builds the reversible move and rebuilds.
        """
        source = self.currentItem()
        target = self.itemAt(event.position().toPoint())
        indicator = self.dropIndicatorPosition()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        self._panel.handle_drop(source, target, indicator)


class Layer_Panel(QWidget):
    """Layer/group tree panel bound to the active document (REQ-P4-UI-001..011)."""

    #: Emitted with the selected node (``Layer`` / ``LayerGroup`` / ``None``).
    activeNodeChanged = Signal(object)
    #: Emitted when the "edit mask" toggle flips (route paint to the mask buffer).
    maskEditToggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._frame_index = 0
        self._stack: Optional[QUndoStack] = None
        self._on_tree_changed: Optional[Callable[[], None]] = None
        # D2: attribute ops recomposite only the visible viewport, not the whole
        # stack; a live opacity drag is throttled to one recomposite/frame (D3).
        self._on_attr_changed: Optional[Callable[[], None]] = None
        self._on_live_recomposite: Optional[Callable[[], None]] = None
        # Phase-12 Slice B (FU-16b): the canvas hook that builds the opacity-drag
        # split-cache on ``sliderPressed`` (ADR-0034 §2); None disables the LOD
        # preview optimisation (the naive throttled path stays correct).
        self._on_opacity_drag_begin: Optional[Callable[[Sequence[int]], bool]] = None
        self._rows: List[_Node_Row] = []
        self._updating = False

        self._toolbar = QToolBar(self)
        self._tree = _Layer_Tree(self, self)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

        self._build_actions()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._tree)

        self._retranslate()
        self._update_actions()

    # -- context ----------------------------------------------------------

    @property
    def document(self) -> Optional[Document]:
        """The document whose active-frame tree the panel reflects."""
        return self._document

    @property
    def frame_index(self) -> int:
        """The active frame index the panel operates on."""
        return self._frame_index

    def set_context(
        self,
        document: Document,
        stack: QUndoStack,
        on_tree_changed: Callable[[], None],
        on_attr_changed: Optional[Callable[[], None]] = None,
        on_live_recomposite: Optional[Callable[[], None]] = None,
        on_opacity_drag_begin: Optional[Callable[[Sequence[int]], bool]] = None,
    ) -> None:
        """Bind the panel to a document + its undo stack + recomposite hooks.

        ``on_tree_changed`` recomposites the whole stack after a **structural**
        layer op (add/remove/reorder/group/ungroup), owned by the canvas scene
        (ADR-0007). ``on_attr_changed`` recomposites only the **visible viewport**
        after an attribute op (opacity/visibility/lock/blend-mode) — the D2
        viewport-scoped path, never the whole 33 Mpx canvas. ``on_live_recomposite``
        is the throttled hook a live opacity drag calls (one recomposite per
        frame, D3). ``on_opacity_drag_begin`` is the Phase-12 Slice-B hook that
        builds the drag-scoped split-cache on ``sliderPressed`` so the drag ticks
        render a 16 ms LOD preview (ADR-0034 §2); when omitted the naive throttled
        recomposite is used (the release commit is byte-exact either way). The
        optional hooks default to ``on_tree_changed`` / ``on_attr_changed`` / no-op
        when omitted (backward-compatible). Called on document open and on every tab
        switch (state isolation, UI-014).
        """
        self._document = document
        self._frame_index = 0
        self._stack = stack
        self._on_tree_changed = on_tree_changed
        self._on_attr_changed = (
            on_attr_changed if on_attr_changed is not None else on_tree_changed
        )
        self._on_live_recomposite = (
            on_live_recomposite
            if on_live_recomposite is not None
            else self._on_attr_changed
        )
        self._on_opacity_drag_begin = on_opacity_drag_begin
        self.rebuild()

    def set_frame_index(self, index: int) -> None:
        """Point the panel at frame ``index``'s layer tree (Phase-5 timeline sync).

        The active frame is chosen on the timeline (REQ-P5-UI-001/-002); the layer
        panel must then reflect (and edit) that frame's own layer stack. Additive
        and non-undoable (selecting a frame mutates no document state, CL-13); a
        no-op when the index is unchanged or out of range.
        """
        if self._document is None:
            return
        if not 0 <= index < len(self._document.frames):
            return
        if index == self._frame_index:
            return
        self._frame_index = index
        self.rebuild()

    def blend_label(self, mode: BlendMode) -> str:
        """Return the translatable label for a blend mode (UI-005)."""
        labels: Dict[BlendMode, str] = {
            BlendMode.NORMAL: self.tr("Normal"),
            BlendMode.MULTIPLY: self.tr("Multiply"),
            BlendMode.SCREEN: self.tr("Screen"),
            BlendMode.OVERLAY: self.tr("Overlay"),
            BlendMode.DARKEN: self.tr("Darken"),
            BlendMode.LIGHTEN: self.tr("Lighten"),
            BlendMode.COLOR_DODGE: self.tr("Colour Dodge"),
            BlendMode.COLOR_BURN: self.tr("Colour Burn"),
            BlendMode.HARD_LIGHT: self.tr("Hard Light"),
            BlendMode.SOFT_LIGHT: self.tr("Soft Light"),
            BlendMode.DIFFERENCE: self.tr("Difference"),
            BlendMode.EXCLUSION: self.tr("Exclusion"),
        }
        return labels.get(mode, mode.value)

    # -- toolbar actions --------------------------------------------------

    def _build_actions(self) -> None:
        self._add_action = QAction(self)
        self._add_action.triggered.connect(self._on_add)
        self._remove_action = QAction(self)
        self._remove_action.triggered.connect(self._on_remove)
        self._duplicate_action = QAction(self)
        self._duplicate_action.triggered.connect(self._on_duplicate)
        self._group_action = QAction(self)
        self._group_action.triggered.connect(self._on_group)
        self._ungroup_action = QAction(self)
        self._ungroup_action.triggered.connect(self._on_ungroup)
        self._mask_action = QAction(self)
        self._mask_action.triggered.connect(self._on_toggle_mask)
        self._mask_edit_action = QAction(self)
        self._mask_edit_action.setCheckable(True)
        self._mask_edit_action.triggered.connect(self._on_mask_edit)
        self._reference_action = QAction(self)
        self._reference_action.setCheckable(True)
        self._reference_action.triggered.connect(self._on_reference)
        self._smart_action = QAction(self)
        self._smart_action.triggered.connect(self._on_smart)

        for action in (
            self._add_action,
            self._remove_action,
            self._duplicate_action,
            self._group_action,
            self._ungroup_action,
            self._mask_action,
            self._mask_edit_action,
            self._reference_action,
            self._smart_action,
        ):
            self._toolbar.addAction(action)

    # -- tree build -------------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the whole tree from the document (after a structural op)."""
        prev = self._selected_path()
        self._updating = True
        self._tree.clear()
        self._rows = []
        if self._document is not None:
            frame = self._document.frames[self._frame_index]
            self._add_nodes(frame.layers, None, ())
        self._updating = False
        if not self._select_path(prev):
            self._select_topmost()
        self._update_actions()

    def _add_nodes(
        self,
        container: List[LayerNode],
        parent_item: Optional[QTreeWidgetItem],
        prefix: Path,
    ) -> None:
        # Topmost-first display (CL-3): iterate the logic list high index → low.
        for logic_i in reversed(range(len(container))):
            node = container[logic_i]
            path = prefix + (logic_i,)
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            if parent_item is None:
                self._tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            row = _Node_Row(self, node, path)
            self._rows.append(row)
            self._tree.setItemWidget(item, 0, row)
            if isinstance(node, LayerGroup):
                self._add_nodes(node.children, item, path)
                item.setExpanded(True)

    def _iter_items(self) -> List[QTreeWidgetItem]:
        out: List[QTreeWidgetItem] = []

        def walk(item: Optional[QTreeWidgetItem]) -> None:
            if item is None:
                return
            out.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self._tree.topLevelItemCount()):
            walk(self._tree.topLevelItem(i))
        return out

    def _item_path(self, item: Optional[QTreeWidgetItem]) -> Optional[Path]:
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return tuple(data) if data is not None else None

    def _selected_path(self) -> Optional[Path]:
        return self._item_path(self._tree.currentItem())

    def _selected_node(self) -> Optional[LayerNode]:
        path = self._selected_path()
        if path is None or self._document is None:
            return None
        try:
            return self._document.resolve_layer(
                list(path), frame_index=self._frame_index
            )
        except DocumentError:
            return None

    def _select_path(self, path: Optional[Path]) -> bool:
        if path is None:
            return False
        for item in self._iter_items():
            if self._item_path(item) == path:
                self._tree.setCurrentItem(item)
                return True
        return False

    def _select_topmost(self) -> None:
        top = self._tree.topLevelItem(0)
        if top is not None:
            self._tree.setCurrentItem(top)

    # -- selection --------------------------------------------------------

    def _on_selection_changed(self) -> None:
        if self._updating:
            return
        self.activeNodeChanged.emit(self._selected_node())
        self._update_actions()

    # -- command plumbing (one LayerCommand per op) -----------------------

    def push_attr(self, command: Command, label: str) -> None:
        """Push an attribute op; refresh recomposites + re-syncs the rows."""
        if self._stack is None:
            return
        self._stack.push(LayerCommand(command, self._attr_refresh, label))

    def push_struct(self, command: Command, label: str) -> None:
        """Push a structural op; refresh recomposites + rebuilds the tree."""
        if self._stack is None:
            return
        self._stack.push(LayerCommand(command, self._struct_refresh, label))

    def live_recomposite(self) -> None:
        """Recomposite for a live opacity drag, throttled to one/frame (D3).

        Pushes no command; the final value commits as one ``LayerCommand`` on
        slider release (``_commit_opacity``).
        """
        if self._on_live_recomposite is not None:
            self._on_live_recomposite()

    def begin_opacity_drag(self, path: Path) -> bool:
        """Ask the canvas to build the opacity-drag split-cache (Phase-12 Slice B).

        Called on ``sliderPressed`` (ADR-0034 §2 / FU-16b). Pushes no command; the
        final value still commits as one ``LayerCommand`` on release
        (``_commit_opacity``), whose redo applies the byte-exact full-resolution
        recomposite. Returns whether the LOD-preview path was engaged (``False``
        when no hook is bound, or the canvas declines — nested node / no viewport /
        indexed doc — in which case the naive throttled recomposite is used).
        """
        if self._on_opacity_drag_begin is not None:
            return bool(self._on_opacity_drag_begin(path))
        return False

    def _attr_refresh(self) -> None:
        # D2: attribute ops recomposite only the visible viewport, not the stack.
        if self._on_attr_changed is not None:
            self._on_attr_changed()
        for row in self._rows:
            row.sync()
        self._update_actions()

    def _struct_refresh(self) -> None:
        if self._on_tree_changed is not None:
            self._on_tree_changed()
        self.rebuild()

    # -- structural / affordance actions ---------------------------------

    def _on_add(self) -> None:
        doc = self._document
        if doc is None:
            return
        path = self._selected_path()
        ref = list(path) if path is not None else None
        try:
            cmd = doc.make_add_layer_command(
                ref=ref, name=self.tr("Layer"), frame_index=self._frame_index
            )
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Add Layer"))

    def _on_remove(self) -> None:
        doc = self._document
        path = self._selected_path()
        if doc is None or path is None:
            return
        try:
            cmd = doc.make_remove_layer_command(
                list(path), frame_index=self._frame_index
            )
        except DocumentError:
            return  # last-layer removal is refused (UI-007).
        self.push_struct(cmd, self.tr("Remove Layer"))

    def _on_duplicate(self) -> None:
        doc = self._document
        path = self._selected_path()
        if doc is None or path is None:
            return
        try:
            cmd = doc.make_duplicate_layer_command(
                list(path), frame_index=self._frame_index
            )
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Duplicate Layer"))

    def _on_group(self) -> None:
        doc = self._document
        path = self._selected_path()
        if doc is None or path is None or len(path) != 1:
            return  # grouping operates on top-level nodes (LOGIC-011).
        try:
            cmd = doc.make_group_command(
                [path[0]], name=self.tr("Group"), frame_index=self._frame_index
            )
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Group Layers"))

    def _on_ungroup(self) -> None:
        doc = self._document
        path = self._selected_path()
        node = self._selected_node()
        if doc is None or path is None or not isinstance(node, LayerGroup):
            return
        try:
            cmd = doc.make_ungroup_command(list(path), frame_index=self._frame_index)
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Ungroup Layers"))

    def _on_toggle_mask(self) -> None:
        doc = self._document
        path = self._selected_path()
        node = self._selected_node()
        if doc is None or path is None or node is None:
            return
        try:
            if node.mask is None:
                mask = PixelBuffer(
                    doc.width, doc.height, ColorMode.RGBA, fill=_MASK_SHOWN
                )
                cmd = doc.make_attach_mask_command(
                    list(path), mask, frame_index=self._frame_index
                )
                label = self.tr("Add Mask")
            else:
                self._mask_edit_action.setChecked(False)
                self.maskEditToggled.emit(False)
                cmd = doc.make_detach_mask_command(
                    list(path), frame_index=self._frame_index
                )
                label = self.tr("Remove Mask")
        except DocumentError:
            return
        self.push_struct(cmd, label)

    def _on_mask_edit(self, checked: bool) -> None:
        # Not a command: a tool-target change (paint modulates the mask, UI-009).
        node = self._selected_node()
        if checked and (node is None or node.mask is None):
            self._mask_edit_action.setChecked(False)
            return
        self.maskEditToggled.emit(checked)

    def _on_reference(self, checked: bool) -> None:
        doc = self._document
        path = self._selected_path()
        if doc is None or path is None:
            return
        try:
            cmd = doc.make_set_reference_command(
                list(path), checked, frame_index=self._frame_index
            )
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Toggle Reference"))

    def _on_smart(self) -> None:
        doc = self._document
        path = self._selected_path()
        node = self._selected_node()
        if doc is None or path is None or not isinstance(node, Layer):
            return
        try:
            cmd = doc.make_smart_layer_command(
                list(path), name=self.tr("Smart"), frame_index=self._frame_index
            )
        except DocumentError:
            return
        self.push_struct(cmd, self.tr("Create Smart Layer"))

    # -- drag reorder (UI-006) -------------------------------------------

    def handle_drop(
        self,
        source: Optional[QTreeWidgetItem],
        target: Optional[QTreeWidgetItem],
        indicator: QAbstractItemView.DropIndicatorPosition,
    ) -> None:
        """Translate a drop into one ``move_layer`` command (or rebuild on error)."""
        doc = self._document
        src_path = self._item_path(source)
        if doc is None or src_path is None:
            return

        dst_container: Path
        dst_index: int
        target_path = self._item_path(target)
        if target_path is None:
            # Dropped on empty space → bottom of the top-level stack (z=0).
            dst_container, dst_index = (), 0
        else:
            target_node = self._safe_resolve(target_path)
            on_item = indicator == QAbstractItemView.DropIndicatorPosition.OnItem
            if on_item and isinstance(target_node, LayerGroup):
                dst_container = target_path
                dst_index = len(target_node.children)  # top of the group.
            else:
                dst_container = target_path[:-1]
                ti = target_path[-1]
                # Display is topmost-first; "above" in the list = higher z-order.
                if indicator == QAbstractItemView.DropIndicatorPosition.AboveItem:
                    dst_index = ti + 1
                else:
                    dst_index = ti

        # Never move a node into its own subtree (would corrupt the tree).
        if len(dst_container) >= len(src_path) and tuple(
            dst_container[: len(src_path)]
        ) == tuple(src_path):
            return
        # Same-container reorder: account for the source's own removal.
        if tuple(src_path[:-1]) == tuple(dst_container):
            if dst_index > src_path[-1]:
                dst_index -= 1
            if dst_index == src_path[-1]:
                return  # no-op move.

        to_ref = list(dst_container) + [dst_index]
        try:
            cmd = doc.make_move_layer_command(
                list(src_path), to_ref, frame_index=self._frame_index
            )
        except DocumentError:
            self.rebuild()
            return
        self.push_struct(cmd, self.tr("Move Layer"))

    def _safe_resolve(self, path: Path) -> Optional[LayerNode]:
        if self._document is None:
            return None
        try:
            return self._document.resolve_layer(
                list(path), frame_index=self._frame_index
            )
        except DocumentError:
            return None

    # -- action enablement ------------------------------------------------

    def _update_actions(self) -> None:
        node = self._selected_node()
        path = self._selected_path()
        has = node is not None
        is_group = isinstance(node, LayerGroup)
        top_level = path is not None and len(path) == 1
        has_mask = has and node is not None and node.mask is not None

        self._remove_action.setEnabled(has)
        self._duplicate_action.setEnabled(has)
        self._group_action.setEnabled(top_level)
        self._ungroup_action.setEnabled(is_group)
        self._mask_action.setEnabled(has)
        self._smart_action.setEnabled(
            isinstance(node, Layer) and node.smart_source is None
        )
        self._reference_action.setEnabled(has)
        self._reference_action.blockSignals(True)
        self._reference_action.setChecked(
            bool(getattr(node, "reference", False)) if has else False
        )
        self._reference_action.blockSignals(False)
        self._mask_edit_action.setEnabled(bool(has_mask))
        self._mask_edit_action.blockSignals(True)
        self._mask_edit_action.setChecked(
            bool(has_mask) and self._mask_edit_action.isChecked()
        )
        self._mask_edit_action.blockSignals(False)
        self._mask_action.setText(
            self.tr("Remove Mask") if has_mask else self.tr("Add Mask")
        )

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Layers panel"))
        self._toolbar.setWindowTitle(self.tr("Layer actions"))
        self._tree.setAccessibleName(self.tr("Layer tree"))
        self._tree.setAccessibleDescription(
            self.tr("Layers top-to-bottom; drag to reorder or re-parent")
        )
        self._add_action.setText(self.tr("Add Layer"))
        self._remove_action.setText(self.tr("Remove Layer"))
        self._duplicate_action.setText(self.tr("Duplicate Layer"))
        self._group_action.setText(self.tr("Group"))
        self._ungroup_action.setText(self.tr("Ungroup"))
        self._mask_edit_action.setText(self.tr("Edit Mask"))
        self._reference_action.setText(self.tr("Reference"))
        self._smart_action.setText(self.tr("Smart Layer"))
        self._mask_action.setText(self.tr("Add Mask"))
        self._update_actions()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
            if self._document is not None:
                self.rebuild()
        super().changeEvent(event)
