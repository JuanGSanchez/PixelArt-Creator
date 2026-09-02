# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pre-merge branch diff view (``REQ-P10-UI-015..019``, ``-021..026``).

``Branch_Diff_Dialog`` is a **modeless** dialog (never a dock — Qt persists dock
state in the window's saved layout, which would fight ``CL-P10D-8``: the view's
open state is not remembered across restarts). It computes **nothing** of its
own (Article I / S11): it calls
:func:`~pixelart_creator.logic.branch_diff.derive_divergence` and
:func:`~pixelart_creator.logic.branch_diff.supervise` exactly **once**, at
construction time (``REQ-P10-UI-024`` — computed once per open, never on
scroll/resize/selection), and only formats their already-computed results for
display.

The view is strictly **read-only** (``REQ-P10-UI-018``): it pushes no
``QUndoCommand``, mutates no branch, no document and no file, and offers no
per-entry accept/reject/revert affordance. It offers exactly two exits
(``REQ-P10-UI-019``): *Continue to merge* — which performs no merge itself, it
only announces the caller should run the **shipped** merge
(``Branching_Session.merge_to_mainline``, unchanged) — and *Close*, which is
the same act whether triggered by the button, Escape, or the window's own
close affordance (``QDialog.reject()`` under all three).

Every user-visible string is ``tr()``-wrapped with ``.format()`` placeholders
and re-set via :meth:`changeEvent` on ``QEvent.LanguageChange`` (``REQ-P10-UI-023``).
Every control carries an accessible name (``REQ-P10-UI-021``); colours are never
hard-coded and emphasis is never colour-only (``REQ-P10-UI-022``) — the
supervision warning is carried by wording and bold text, not by colour.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.branch_diff import (
    BranchDivergence,
    OpEntry,
    SupervisionResult,
    derive_divergence,
    supervise,
)
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import (
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    RasterOp,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import Branch

#: The four op-tier groups, fixed display order (``REQ-P10-UI-016``) — matches
#: ``branch_diff._CLASS_RANK``'s declaration order (metadata, layer_attr,
#: layer_order, raster; ``convergence.py:228``).
_GROUP_ORDER: List[str] = ["metadata", "layer_attr", "layer_order", "raster"]


class Branch_Diff_Dialog(QDialog):
    """Modeless pre-merge diff: source vs. target op-log divergence + supervision.

    Args:
        source_name: The feature branch's display name (the diff's source).
        target_name: The merge target's display name (today always the
            mainline; ``REQ-P10-UI-015``).
        source: The source branch, read-only.
        target: The target branch, read-only.
        live: The live :class:`~pixelart_creator.logic.document.Document` the
            user is actually editing on the source branch — supplied by the
            caller (``ui/main_window.py``, plan §3.2), never re-derived here.
        parent: Optional parent widget.
    """

    #: Emitted with ``source_name`` when the user activates *Continue to
    #: merge*. This view performs **no** merge itself (``REQ-P10-UI-018``) — the
    #: caller runs the unchanged ``Branching_Session.merge_to_mainline`` (the
    #: same shipped path the panel's own Merge button uses, ``REQ-P10-UI-019``).
    continueToMergeRequested = Signal(str)

    def __init__(
        self,
        source_name: str,
        target_name: str,
        source: Branch,
        target: Branch,
        live: Document,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Compute the divergence + supervision once, then build the read-only view."""
        super().__init__(parent)
        # Modeless by construction (plan §8 architecture ruling) — never a dock
        # (Qt persists dock state, fighting CL-P10D-8) and never application-modal
        # (the shipped branching surface must stay usable while this is open).
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._source_name = source_name
        self._target_name = target_name
        # Computed exactly once, here, at open time (REQ-P10-UI-024): neither
        # value is re-derived on scroll, resize or selection change.
        self._divergence: BranchDivergence = derive_divergence(source, target)
        self._supervision: SupervisionResult = supervise(source, live)

        self._basis_label = QLabel(self)
        self._basis_label.setWordWrap(True)

        self._supervision_label = QLabel(self)
        self._supervision_label.setWordWrap(True)
        supervision_font = QFont(self._supervision_label.font())
        supervision_font.setBold(True)
        self._supervision_label.setFont(supervision_font)

        self._identical_label = QLabel(self)
        self._identical_label.setWordWrap(True)

        self._groups: dict = {}
        groups_layout = QVBoxLayout()
        for group_key, group_title in self._group_titles().items():
            box = QGroupBox(group_title, self)
            box_layout = QVBoxLayout(box)
            count_label = QLabel(box)
            count_label.setWordWrap(True)
            list_widget = QListWidget(box)
            box_layout.addWidget(count_label)
            box_layout.addWidget(list_widget)
            groups_layout.addWidget(box)
            self._groups[group_key] = (box, count_label, list_widget)

        self._region_box = QGroupBox(self)
        region_layout = QVBoxLayout(self._region_box)
        self._region_granularity_label = QLabel(self._region_box)
        self._region_granularity_label.setWordWrap(True)
        self._region_list = QListWidget(self._region_box)
        region_layout.addWidget(self._region_granularity_label)
        region_layout.addWidget(self._region_list)

        self._total_label = QLabel(self)
        self._total_label.setWordWrap(True)

        self._continue_button = QPushButton(self)
        self._continue_button.clicked.connect(self._on_continue)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.reject)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._continue_button)
        button_row.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._basis_label)
        layout.addWidget(self._supervision_label)
        layout.addWidget(self._identical_label)
        layout.addLayout(groups_layout)
        layout.addWidget(self._region_box)
        layout.addWidget(self._total_label)
        layout.addLayout(button_row)

        self._populate()
        self._retranslate()

    # -- construction helpers ----------------------------------------------

    def _group_titles(self) -> "dict[str, str]":
        """Fixed-order group key -> translated title (``REQ-P10-UI-016``)."""
        return {
            "metadata": self.tr("Metadata changes"),
            "layer_attr": self.tr("Layer attribute changes"),
            "layer_order": self.tr("Layer order changes"),
            "raster": self.tr("Raster (pixel) changes"),
        }

    def _format_entry(self, entry: OpEntry) -> str:
        """Render one :class:`OpEntry` in the user's terms (``REQ-P10-UI-016``).

        Pure display formatting over already-computed data — no domain maths
        (Article I): the op's fields are read and interpolated, never
        combined or derived further.
        """
        op = entry.op
        if isinstance(op, MetadataOp):
            return self.tr("Metadata '{key}' set to '{value}'").format(
                key=op.key, value=op.value
            )
        if isinstance(op, LayerAttrOp):
            return self.tr("Frame {frame}, layer {layer}: {attr} = {value}").format(
                frame=op.frame_index, layer=op.layer_id, attr=op.attr, value=op.value
            )
        if isinstance(op, LayerOrderOp):
            return self.tr("Frame {frame}: layer order changed").format(
                frame=op.frame_index
            )
        if isinstance(op, RasterOp):
            return self.tr(
                "Frame {frame}, layer {layer}: tile ({tile_x}, {tile_y})"
            ).format(
                frame=op.frame_index,
                layer=op.layer_id,
                tile_x=op.tile_x,
                tile_y=op.tile_y,
            )
        return repr(
            op
        )  # pragma: no cover — unreachable, the four classes are exhaustive

    def _populate(self) -> None:
        """Fill the group lists + region list from the already-computed results.

        Presentation only: iterates the divergence's ``ops``/``regions``
        (already sorted deterministically by ``logic/branch_diff.py``) and
        writes list rows. No domain maths (Article I).
        """
        by_group: "dict[str, list[OpEntry]]" = {key: [] for key in _GROUP_ORDER}
        for entry in self._divergence.ops:
            by_group.setdefault(entry.op_class, []).append(entry)

        for group_key in _GROUP_ORDER:
            _box, count_label, list_widget = self._groups[group_key]
            entries = by_group.get(group_key, [])
            list_widget.clear()
            for entry in entries:
                list_widget.addItem(QListWidgetItem(self._format_entry(entry)))
            count_label.setProperty("_count", len(entries))

        self._region_list.clear()
        for region in self._divergence.regions:
            self._region_list.addItem(
                QListWidgetItem(
                    self.tr(
                        "Frame {frame}, layer {layer}: ({x}, {y}) {width}×{height}"
                    ).format(
                        frame=region.frame_index,
                        layer=region.layer_id,
                        x=region.x,
                        y=region.y,
                        width=region.width,
                        height=region.height,
                    )
                )
            )

    # -- slots ---------------------------------------------------------------

    def _on_continue(self) -> None:
        """Announce *Continue to merge*; performs no merge itself (see class doc)."""
        self.continueToMergeRequested.emit(self._source_name)
        self.accept()

    # -- i18n ------------------------------------------------------------

    def _retranslate(self) -> None:
        # Re-render the already-computed divergence/regions in the new
        # language (F5) — this re-FORMATS, it never re-derives (REQ-P10-UI-024:
        # the derivation itself stays computed exactly once, at construction).
        self._populate()
        self.setWindowTitle(
            self.tr("Diff: '{source}' vs '{target}'").format(
                source=self._source_name, target=self._target_name
            )
        )
        self.setAccessibleName(self.tr("Branch diff"))
        self._basis_label.setText(
            self.tr(
                "Comparing branch '{source}' (source) against '{target}' "
                "(target). This is a snapshot taken now — the merge has not "
                "happened yet."
            ).format(source=self._source_name, target=self._target_name)
        )
        self._basis_label.setAccessibleName(self.tr("Diff basis"))

        if self._supervision.accounted:
            self._supervision_label.setText(
                self.tr(
                    "Checked: the recorded changes account for everything on "
                    "this branch."
                )
            )
        else:
            self._supervision_label.setText(
                self.tr(
                    "Warning: some changes on this branch are not recorded "
                    "and will not be merged. {detail}"
                ).format(detail=self._supervision_detail())
            )
        self._supervision_label.setAccessibleName(self.tr("Supervision result"))
        self._supervision_label.setAccessibleDescription(
            self.tr(
                "States whether the recorded operation log explains every "
                "change on this branch's live document."
            )
        )

        if self._divergence.is_empty and self._supervision.accounted:
            self._identical_label.setText(
                self.tr("This branch has no changes to merge.")
            )
            self._identical_label.setVisible(True)
        else:
            self._identical_label.setText("")
            self._identical_label.setVisible(False)

        titles = self._group_titles()
        for group_key, (box, count_label, list_widget) in self._groups.items():
            box.setTitle(titles[group_key])
            count = int(count_label.property("_count") or 0)
            if count == 0:
                count_label.setText(self.tr("No changes."))
            else:
                count_label.setText(self.tr("{count} change(s).").format(count=count))
            list_widget.setAccessibleName(
                self.tr("{title} list").format(title=titles[group_key])
            )
            list_widget.setAccessibleDescription(
                self.tr("{count} entries.").format(count=count)
            )

        self._region_box.setTitle(self.tr("Affected regions"))
        self._region_granularity_label.setText(
            self.tr(
                "Each region is reported at the whole {tile}×{tile} pixel "
                "tile granularity — a one-pixel change still covers a full "
                "tile here."
            ).format(tile=CRDT_TILE_SIZE_PX)
        )
        self._region_list.setAccessibleName(self.tr("Affected regions list"))
        self._region_list.setAccessibleDescription(
            self.tr("{count} regions.").format(count=len(self._divergence.regions))
        )

        self._total_label.setText(
            self.tr(
                "{total} operation(s) total, across {targets} distinct target(s)."
            ).format(
                total=self._divergence.total,
                targets=self._divergence.distinct_targets,
            )
        )
        self._total_label.setAccessibleName(self.tr("Divergence total"))

        self._continue_button.setText(self.tr("Continue to Merge"))
        self._continue_button.setAccessibleName(self.tr("Continue to merge"))
        self._continue_button.setAccessibleDescription(
            self.tr(
                "Performs the same conflict-free merge as the branching "
                "panel's Merge control."
            )
        )
        self._close_button.setText(self.tr("Close"))
        self._close_button.setAccessibleName(self.tr("Close"))
        self._close_button.setAccessibleDescription(
            self.tr("Closes this view without merging or changing anything.")
        )

    def _supervision_detail(self) -> str:
        """Render the located divergence (frames/layers/attrs/keys/tiles).

        Pure formatting over the already-computed :class:`SupervisionResult`
        (Article I) — never re-derives or repairs (``REQ-P10-UI-026``).
        """
        parts: List[str] = []
        if self._supervision.frames:
            parts.append(
                self.tr("frames {frames}").format(
                    frames=", ".join(str(f) for f in self._supervision.frames)
                )
            )
        if self._supervision.layers:
            parts.append(
                self.tr("layers {layers}").format(
                    layers=", ".join(
                        f"({f}, {layer_id})" for f, layer_id in self._supervision.layers
                    )
                )
            )
        if self._supervision.attrs:
            parts.append(
                self.tr("attributes {attrs}").format(
                    attrs=", ".join(
                        f"({f}, {layer_id}, {attr})"
                        for f, layer_id, attr in self._supervision.attrs
                    )
                )
            )
        if self._supervision.metadata_keys:
            parts.append(
                self.tr("metadata keys {keys}").format(
                    keys=", ".join(self._supervision.metadata_keys)
                )
            )
        if self._supervision.tiles:
            parts.append(
                self.tr("tiles {tiles}").format(
                    tiles=", ".join(
                        f"({f}, {layer_id}, {tx}, {ty})"
                        for f, layer_id, tx, ty in self._supervision.tiles
                    )
                )
            )
        return "; ".join(parts)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Branch_Diff_Dialog"]
