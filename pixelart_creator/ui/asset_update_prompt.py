# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Library-edit prompt — pick up or keep, per asset (REQ-P11-UI-022, -023).

``Asset_Update_Prompt_Dialog`` is shown when the library asset a project
**references** has been edited since the project last resolved it — the
choice is per asset: **pick up the change** (start resolving the new
content) or **keep the referenced version** (go on resolving exactly what
was referenced). It is a blocking, cancellable modal
(:class:`~PySide6.QtWidgets.QDialog`), following this codebase's existing
``Cel_Overwrite_Dialog`` shape: two named outcome buttons instead of a bare
Yes/Cancel, plus one "Don't ask again" checkbox.

**What this file builds, precisely (T14's Done-when, phase-11-asset-ingress
``tasks.md:560-570``):**

- The dialog itself: message + two outcome buttons + the checkbox — pure
  presentation, no domain logic (Article I / S11).
- :meth:`Asset_Update_Prompt_Dialog.decide` — the one place this prompt
  **consults and writes** the three-state
  :data:`~pixelart_creator.logic.asset_references.ASSET_LIBRARY_EDIT`
  preference through ``logic/project_prefs.py``'s registered read/write seam
  (:func:`~pixelart_creator.logic.project_prefs.get` /
  :func:`~pixelart_creator.logic.project_prefs.with_value`, ADR-0056): when
  the remembered value is not ``"ask"`` the dialog is skipped entirely and
  the remembered outcome is returned; otherwise the dialog is shown, and a
  decided choice with the checkbox ticked is written back using **the
  domain value matching the choice made in this same interaction** — never
  a bare boolean, because a boolean cannot say which of the two outcomes to
  stop asking about (``REQ-P11-DATA-010``). Cancelling or closing the dialog
  writes nothing and resolves as :data:`OUTCOME_KEEP` — the project keeps
  resolving the referenced version until an explicit pick-up, exactly the
  "asked before anything about the project changes ... until they choose,
  the project keeps resolving the version it references" contract.

**What this file deliberately does NOT build (boundary applied, T15/T11
split):**

- *The three-state rendering inside the* ``&Edit → Project confirmations``
  *submenu* is **T15**'s, under ruling P11-R2 (plan §3.4) — it extends
  ``ui/project_prefs_actions.py``'s renderer generically by domain size.
  This prompt's own "Don't ask again" checkbox is a **separate** suppression
  surface for the same registry key, exactly as ``Cel_Overwrite_Dialog``'s
  checkbox is separate from that key's submenu entry; the two write the same
  preference through the same seam and neither depends on the other
  existing.
- *The per-asset "don't ask again for THIS edit, but a further edit asks
  again" memory* **is** built here (DEV-40, corrective unit under
  ``20260821-reachability-remediation``) — see
  :meth:`Asset_Update_Prompt_Dialog.decide`'s own docstring for the
  session-memory shape and its disclosed limitation. What remains **not**
  built here is *detecting* that a library asset has been edited a
  *second* time (a fresh content-hash) — that predicate does not exist yet
  for a project's :class:`~pixelart_creator.logic.asset_references.ReferenceSet`
  (:func:`~pixelart_creator.logic.asset_references.resolve_states` collapses
  "missing" and "edited" into one boolean; a genuinely new content hash for
  an already-decided ``asset_id`` is indistinguishable, from this module's
  side, from "the same edit asked about before"). The caller is still
  responsible for the eventual content-hash-scoped identity via
  :meth:`decide`'s optional ``edit_token`` — see below.
  **Update (T50, ADR-0062, ruling P11-R13):** this per-process session
  memory was, until this task, the *only* home this decision had — closing
  the tab discarded it, unticked and ticked alike, even though the user's
  ruling requires both branches to be saved automatically. It is no longer
  the only home: the unticked half now also lands in the durable, per-edit
  ledger built by T47 (:mod:`pixelart_creator.logic.asset_edit_decisions`)
  and T48/T49 (the write-ahead journal and project-file persistence). This
  module's own session bucket is now a **runtime cache** in front of that
  ledger, seeded from it by :meth:`Asset_Update_Prompt_Dialog.prime_session`
  and observed, on every fresh decision, through :meth:`decide`'s optional
  ``on_decided`` callback — the caller is the one that writes the callback's
  payload into the durable ledger; this module still performs no I/O of its
  own (see below).
- *Computing which reference is "edited" in the first place* (the
  hash-mismatch predicate) is **T13**'s resolve-state surface
  (``ui/asset_reuse_panel.py``) plus T11's ``resolve_states`` /
  :class:`~pixelart_creator.logic.asset_references.AssetReference` model —
  this dialog is handed an already-identified ``asset_id`` and display name
  by its caller; it derives nothing about resolve state itself.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent``
retranslate (F5); every interactive control carries an accessible name and
is keyboard-reachable; no colour is hard-coded — the dialog uses only the
active QSS theme's default palette, so both themes render correctly with no
per-widget colour. Synchronous, in-memory, no worker thread or timer, and
nothing to tear down.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple, Union

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetCatalog
from pixelart_creator.logic.asset_edit_decisions import (
    DECISION_KEEP,
    DECISION_PICK_UP,
    AssetEditDecisions,
)
from pixelart_creator.logic.asset_references import (
    ASSET_LIBRARY_EDIT,
    STATE_EDITED,
    AssetReference,
    ReferenceSet,
    edit_tokens,
    reference_states,
)
from pixelart_creator.logic.project_prefs import ProjectPrefs
from pixelart_creator.logic.project_prefs import get as prefs_get
from pixelart_creator.logic.project_prefs import with_value as prefs_with_value

#: This dialog's own outcome vocabulary — distinct from the *persisted*
#: three-value preference domain (``"ask"`` / ``"always_pick_up"`` /
#: ``"always_keep_referenced"``, declared in
#: ``logic/asset_references.ASSET_LIBRARY_EDIT``): an outcome is what THIS
#: prompt resolved to for ONE edit; the preference is what to do about
#: FUTURE edits without asking.
#:
#: **Promoted aliases (T50, ADR-0062, ruling P11-R13 — same "one definition of
#: a control, aliases kept so no call site moves" move ruling P11-R11 made for
#: ``data/asset_catalog_io.py``'s ``_safe_asset_id`` / ``_resolve_within``,
#: applied here in the other direction):** the canonical outcome domain now
#: lives in the logic layer,
#: :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_PICK_UP` /
#: :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_KEEP`, at
#: byte-identical values — these two names are retained, unchanged, as
#: aliases so every existing reference in this module and its callers still
#: resolves without moving.
OUTCOME_PICK_UP = DECISION_PICK_UP
OUTCOME_KEEP = DECISION_KEEP

#: The two non-default members of ``ASSET_LIBRARY_EDIT.domain`` this prompt
#: writes through :func:`~pixelart_creator.logic.project_prefs.with_value`
#: (the registered seam validates membership; nothing here re-derives the
#: domain).
_PREF_ALWAYS_PICK_UP = "always_pick_up"
_PREF_ALWAYS_KEEP = "always_keep_referenced"

#: One session-memory entry key: ``(asset_id, edit_token)``. ``edit_token`` is
#: ``None`` when the caller has no content-hash identity to hand yet (see
#: :meth:`Asset_Update_Prompt_Dialog.decide`) — two ``None``-token calls with
#: the same ``asset_id`` are therefore treated as the SAME edit, which is the
#: exact, disclosed limit of this session memory absent a real per-edit
#: identity (module docstring boundary note).
_EditKey = Tuple[str, Optional[str]]


class Asset_Update_Prompt_Dialog(QDialog):
    """Ask, per asset, whether to pick up a library edit or keep the reference."""

    #: Emitted once a button is clicked, before the dialog closes:
    #: ``(outcome, dont_ask_again)``. For a caller driving the dialog
    #: non-modally (``open()``); :meth:`decide` does not need it.
    decided = Signal(str, bool)

    #: **Per-edit session memory** (DEV-40, extended by plan §3.11 (2b) /
    #: DEV-40a): "the same edit does not ask again" for :meth:`decide`
    #: (``REQ-P11-UI-022``'s own acceptance clause), scoped to one project's
    #: session bucket so a different project (:data:`ProjectPrefs`,
    #: ``SC-P11-UI-023-3``) is never affected by another project's session
    #: memory. Keyed by ``id(prefs)`` -> ``(prefs, {edit_key: outcome})`` when
    #: no ``project_key`` is supplied (today's byte-for-byte behaviour — the
    #: snapshot itself is held strongly alongside its id so a *live* entry's
    #: id can never be reused by an unrelated, later ``ProjectPrefs`` object,
    #: an ``is`` check on lookup is the defensive second line); keyed by the
    #: caller-supplied ``project_key`` (a ``str``) instead when one is given
    #: — the production route (``ui/main_window.py``, plan §3.11 (2b)),
    #: because ``document.prefs`` is *replaced* on any confirmation-preference
    #: toggle (``ui/project_prefs_actions.py:165/175``), which would silently
    #: orphan an ``id(prefs)``-keyed bucket. This dict itself is still
    #: in-memory, per-process runtime state — it is never itself written to
    #: disk, and it is never written through ``logic/project_prefs.py`` (that
    #: seam is reserved for the "Don't ask again" preference,
    #: ``REQ-P11-UI-023``, a materially different, explicit, durable choice).
    #: **Corrected (T50, ADR-0062, ruling P11-R13):** this bucket is no longer
    #: the *only* record of an unticked decision — it can be **hydrated** at
    #: the start of a session from the durable, per-edit ledger
    #: (:class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`,
    #: T47) via :meth:`prime_session`, and every fresh decision made through
    #: :meth:`decide` is handed to that method's optional ``on_decided``
    #: callback so the caller can persist it (T48's write-ahead journal /
    #: T49's project-file save) — this module performs no I/O of its own;
    #: it only calls out. Disclosed cost, unchanged: a decided
    #: ``ProjectPrefs`` snapshot (or a live ``project_key`` bucket) is
    #: retained for the life of the process; call :meth:`forget_session` when
    #: a project closes to release it.
    _SESSION_MEMORY: Dict[Union[int, str], Tuple[ProjectPrefs, Dict[_EditKey, str]]] = (
        {}
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the message, the two outcome buttons, and the checkbox."""
        super().__init__(parent)
        self.setModal(True)
        self._asset_id: str = ""
        self._display_name: str = ""
        self._outcome: Optional[str] = None

        self._message = QLabel(self)
        self._message.setWordWrap(True)
        self._dont_ask = QCheckBox(self)

        self._pick_up_button = QPushButton(self)
        self._keep_button = QPushButton(self)
        self._buttons = QDialogButtonBox(self)
        self._buttons.addButton(
            self._pick_up_button, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._buttons.addButton(
            self._keep_button, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._pick_up_button.clicked.connect(self._on_pick_up)
        self._keep_button.clicked.connect(self._on_keep)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message)
        layout.addWidget(self._dont_ask)
        layout.addWidget(self._buttons)

        self._retranslate()

    # -- binding ------------------------------------------------------

    def set_asset(self, asset_id: str, display_name: str) -> None:
        """Set which asset this prompt is asking about (display-only name)."""
        self._asset_id = asset_id
        self._display_name = display_name or asset_id
        self._retranslate()

    # -- outcome (read after exec()/open()) ----------------------------

    def outcome(self) -> str:
        """Return the resolved outcome.

        :data:`OUTCOME_KEEP` until a button is clicked — "the project keeps
        resolving the version it references" is the default, not an
        exception, so a cancelled/closed dialog reads the same as an
        explicit "keep".
        """
        return self._outcome if self._outcome is not None else OUTCOME_KEEP

    def decided_explicitly(self) -> bool:
        """Return whether a button was clicked (``False`` on cancel/close).

        :meth:`dont_ask_again` is only meaningful when this is ``True`` —
        mirrors ``Cel_Overwrite_Dialog.dont_ask_again``'s own rule: "ticking
        and cancelling records nothing".
        """
        return self._outcome is not None

    def dont_ask_again(self) -> bool:
        """Return whether "Don't ask again" was ticked."""
        return self._dont_ask.isChecked()

    # -- button handlers ------------------------------------------------

    def _on_pick_up(self) -> None:
        self._outcome = OUTCOME_PICK_UP
        self.decided.emit(self._outcome, self._dont_ask.isChecked())
        self.accept()

    def _on_keep(self) -> None:
        self._outcome = OUTCOME_KEEP
        self.decided.emit(self._outcome, self._dont_ask.isChecked())
        self.accept()

    def reject(self) -> None:  # noqa: N802 (Qt override)
        """Close (Esc / window close) without recording a decision."""
        self._outcome = None
        super().reject()

    # -- per-edit session memory (DEV-40) --------------------------------

    @classmethod
    def _session_bucket(
        cls, prefs: ProjectPrefs, project_key: Optional[str] = None
    ) -> Dict[_EditKey, str]:
        """Return the session-memory bucket, creating it if new.

        When ``project_key`` is supplied the bucket is keyed by it — stable
        across a later ``document.prefs`` replacement (plan §3.11 (2b)), which
        is the whole reason the parameter exists. The stored ``prefs`` is
        refreshed to the latest snapshot seen but never used to invalidate
        the bucket in this mode. When ``project_key`` is ``None`` the bucket
        is keyed by ``id(prefs)``, with ``prefs`` held alongside it — see
        :data:`_SESSION_MEMORY`'s own docstring for why that makes an
        ``id()`` collision with a different, live snapshot impossible. This
        is today's behaviour, preserved byte-for-byte.
        """
        if project_key is not None:
            entry = cls._SESSION_MEMORY.get(project_key)
            bucket = entry[1] if entry is not None else {}
            cls._SESSION_MEMORY[project_key] = (prefs, bucket)
            return bucket
        key: Union[int, str] = id(prefs)
        entry = cls._SESSION_MEMORY.get(key)
        if entry is None or entry[0] is not prefs:
            entry = (prefs, {})
            cls._SESSION_MEMORY[key] = entry
        return entry[1]

    @classmethod
    def forget_session(
        cls, prefs: ProjectPrefs, project_key: Optional[str] = None
    ) -> None:
        """Release the session memory for ``prefs`` (or ``project_key``).

        Call this when a project closes. A no-op when nothing was decided
        this session. Not required for correctness — only to bound the
        session memory's retention. When ``project_key`` is supplied it is
        the lookup key (matching the scoping :meth:`decide` used); ``None``
        preserves the original ``id(prefs)``-keyed lookup.
        """
        if project_key is not None:
            cls._SESSION_MEMORY.pop(project_key, None)
            return
        cls._SESSION_MEMORY.pop(id(prefs), None)

    @classmethod
    def prime_session(
        cls,
        project_key: str,
        prefs: ProjectPrefs,
        decisions: AssetEditDecisions,
    ) -> None:
        """Seed ``project_key``'s session bucket from a durable ledger (ADR-0062).

        For every ``(asset_id, edit_token, outcome)`` row
        :meth:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions.entries`
        returns, the session bucket gains that entry under the exact
        ``(asset_id, edit_token)`` key :meth:`decide` already looks up —
        :meth:`decide`'s own ``if edit_key in bucket`` lookup is unchanged and
        needs no knowledge that a hydrated entry looks any different from a
        live one.

        **Idempotent:** calling this twice with the same ``decisions`` leaves
        the bucket exactly as the first call did — a row already present is
        never rewritten with an identical value.

        **A live decision beats a hydrated one:** a bucket entry recorded
        *during this session* (a real dialog answer, cached by :meth:`decide`
        itself) is never overwritten by a hydrated row for the same
        ``(asset_id, edit_token)`` key, whichever order the two calls happen
        in — this method only ever fills a key that is still absent.

        Args:
            project_key: The same stable project identity :meth:`decide` is
                called with, so the seeded rows land in the bucket
                :meth:`decide` will actually consult.
            prefs: The project's confirmation-preferences snapshot, threaded
                through to :meth:`_session_bucket` exactly as :meth:`decide`
                threads it — this method mints or reuses no bucket of its
                own.
            decisions: The durable ledger to hydrate from (T47's
                :class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`,
                loaded by T49's ``load_project_bundle``/
                ``parse_asset_edit_decisions``).
        """
        bucket = cls._session_bucket(prefs, project_key)
        for asset_id, edit_token, outcome in decisions.entries():
            edit_key: _EditKey = (asset_id, edit_token)
            bucket.setdefault(edit_key, outcome)

    # -- the whole ask-or-remember flow (consults + writes the seam) ----

    @classmethod
    def decide(
        cls,
        asset_id: str,
        display_name: str,
        prefs: ProjectPrefs,
        parent: Optional[QWidget] = None,
        edit_token: Optional[str] = None,
        project_key: Optional[str] = None,
        on_decided: Optional[
            Callable[[str, Optional[str], str, bool, ProjectPrefs], None]
        ] = None,
    ) -> Tuple[str, ProjectPrefs]:
        """Resolve one library-edit prompt end to end; return ``(outcome, prefs)``.

        Reads the remembered :data:`ASSET_LIBRARY_EDIT` value through
        :func:`~pixelart_creator.logic.project_prefs.get` first
        (``REQ-P11-UI-023``). When it is not ``"ask"`` the dialog is
        **skipped** and the remembered outcome is returned with ``prefs``
        unchanged.

        Otherwise this **edit** — ``(asset_id, edit_token)``, scoped to
        ``prefs``'s own project (``SC-P11-UI-023-3``) — is checked against
        this session's in-memory decision cache (DEV-40,
        ``REQ-P11-UI-022``'s "that same edit does not ask again" clause). A
        cache hit skips the dialog and returns the cached outcome with
        ``prefs`` unchanged. A cache miss shows the dialog modally; a
        decision made **without** ticking "Don't ask again" is cached here
        for this ``(asset_id, edit_token)`` pair, for this ``prefs`` only.
        This module still writes nothing to disk and still never calls
        ``logic/project_prefs.py`` for it — but (T50, ADR-0062, ruling
        P11-R13) that unticked decision is no longer *undurable* by
        construction: it is handed, alongside the ticked branch, to the
        optional ``on_decided`` callback below, and the caller (T48's
        write-ahead journal / T49's project-file save) is the one that
        actually persists it, matching the user's ruling that both the
        ticked and the unticked choice are saved automatically. Ticking it,
        instead, writes the outcome back through
        :func:`~pixelart_creator.logic.project_prefs.with_value`
        (``REQ-P11-DATA-010``) as before — a *durable*, cross-session
        record, which supersedes the in-memory cache for every future edit
        of this project. Cancelling / closing caches and writes nothing and
        resolves as :data:`OUTCOME_KEEP` (``SC-P11-UI-023-4``: "ticking
        without choosing records nothing" — the session cache honours the
        same rule); ``on_decided`` is **not** invoked for a dismissal, nor
        when a remembered "always" preference short-circuits the dialog
        entirely — both cases record nothing new, so there is nothing for
        the callback to carry.

        Args:
            edit_token: An optional identity for *this specific* edit (e.g.
                a content hash), when the caller has one. ``None`` (the
                default) falls back to treating every call for the same
                ``asset_id`` as the same edit — see the module docstring's
                boundary note on why a *further* edit of the same asset
                cannot be told apart from a repeat of the one already
                decided without a caller-supplied token.
            project_key: An optional stable identity for the *project*
                (plan §3.11 (2b)) that scopes the session bucket instead of
                ``id(prefs)`` when supplied. ``None`` (the default) leaves
                today's ``id(prefs)``-keyed behaviour byte-for-byte — the
                production caller (``ui/main_window.py``) always supplies
                this, because ``document.prefs`` is *replaced* on any
                confirmation-preference toggle, which would otherwise
                silently drop the session memory.
            on_decided: An optional
                ``(asset_id, edit_token, outcome, remembered_always,
                prefs_after) -> None`` callback, invoked **exactly once,
                synchronously**, after the outcome is recorded (either into
                the session bucket or, when "Don't ask again" was ticked,
                into ``prefs``) and **before** this method returns. Never
                invoked for a session-cache hit (nothing new was recorded),
                a dismissal, or a remembered-"always" short-circuit — see
                above. ``remembered_always`` is ``True`` exactly when
                ``prefs_after`` carries the new "always" preference;
                ``prefs_after`` is this call's returned ``prefs``. This
                method never persists anything itself; the callback is the
                caller's own seam for doing so (T48/T49).

        The caller is responsible for invoking this **before** applying any
        project-side effect of the edit (``REQ-P11-UI-022``'s ordering
        clause).
        """
        remembered = prefs_get(prefs, ASSET_LIBRARY_EDIT)
        if remembered == _PREF_ALWAYS_PICK_UP:
            return OUTCOME_PICK_UP, prefs
        if remembered == _PREF_ALWAYS_KEEP:
            return OUTCOME_KEEP, prefs

        edit_key: _EditKey = (asset_id, edit_token)
        bucket = cls._session_bucket(prefs, project_key)
        if edit_key in bucket:
            return bucket[edit_key], prefs

        dialog = cls(parent)
        dialog.set_asset(asset_id, display_name)
        dialog.exec()
        outcome = dialog.outcome()
        if dialog.decided_explicitly():
            remembered_always = dialog.dont_ask_again()
            if remembered_always:
                value = (
                    _PREF_ALWAYS_PICK_UP
                    if outcome == OUTCOME_PICK_UP
                    else _PREF_ALWAYS_KEEP
                )
                prefs = prefs_with_value(prefs, ASSET_LIBRARY_EDIT, value)
            else:
                bucket[edit_key] = outcome
            if on_decided is not None:
                on_decided(asset_id, edit_token, outcome, remembered_always, prefs)
        return outcome, prefs

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Library Asset Updated"))
        self.setAccessibleName(self.tr("Library asset updated confirmation"))
        name = self._display_name or self.tr("this asset")
        self._message.setText(
            self.tr(
                'The library asset "%1" has changed since your project last '
                "referenced it. Pick up the change, or keep the version "
                "your project already references?"
            ).replace("%1", name)
        )
        self._message.setAccessibleName(self.tr("Library edit notice"))
        self._dont_ask.setText(self.tr("Don't ask again"))
        self._dont_ask.setAccessibleName(
            self.tr("Remember this choice for future edits of this asset")
        )
        self._pick_up_button.setText(self.tr("Pick Up the Change"))
        self._pick_up_button.setAccessibleName(
            self.tr("Pick up the library asset's change")
        )
        self._keep_button.setText(self.tr("Keep the Referenced Version"))
        self._keep_button.setAccessibleName(
            self.tr("Keep the version this project already references")
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the prompt's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


def resolve_library_edits(
    reference_set: ReferenceSet,
    catalog: AssetCatalog,
    prefs: ProjectPrefs,
    project_key: str,
    parent: Optional[QWidget] = None,
    on_decided: Optional[
        Callable[[str, Optional[str], str, bool, ProjectPrefs], None]
    ] = None,
) -> Tuple[ReferenceSet, ProjectPrefs]:
    """Run :meth:`Asset_Update_Prompt_Dialog.decide` over every edited reference.

    ``decide()``'s **one production caller** (DEV-40a, plan §3.11 (2)/(2b),
    ``tasks.md`` T31). Iterates ``reference_set.entries()`` in its
    deterministic ``asset_id`` order (so the prompt order is testable) and
    calls :meth:`Asset_Update_Prompt_Dialog.decide` **once** for each
    :data:`~pixelart_creator.logic.asset_references.STATE_EDITED` reference,
    with ``edit_token=`` that entry's current ``content_hash``
    (:func:`~pixelart_creator.logic.asset_references.edit_tokens`) and
    ``project_key=`` this project's own key. A
    :data:`~pixelart_creator.logic.asset_references.STATE_RESOLVED` or
    :data:`~pixelart_creator.logic.asset_references.STATE_MISSING` reference
    is **never** passed to :meth:`~Asset_Update_Prompt_Dialog.decide` — the
    missing-asset path (``REQ-P11-UI-021``) stays untouched by this pass.

    :data:`OUTCOME_PICK_UP` rebuilds that one member via two shipped pure
    calls — ``reference_set.remove(asset_id).add(AssetReference(...))`` — no
    :meth:`~pixelart_creator.logic.asset_references.ReferenceSet.replace` is
    minted. The rebuilt member's ``content_hash`` becomes the catalog entry's
    current one and its display-only ``last_known_name`` is refreshed from
    the catalog entry's ``name`` as a side effect of rebuilding, never used
    to resolve. :data:`OUTCOME_KEEP` and a dismissal (cancel/close) leave the
    set exactly as it was for that member.

    **Membership invariant (part of Done-when, not a hope):**
    ``out.asset_ids() == in.asset_ids()`` for every outcome and every mix of
    states — a pick-up changes one member's ``content_hash`` (and its
    display-only ``last_known_name``); nothing is added, removed or
    substituted, so a :data:`STATE_MISSING` reference always passes through
    to be named and counted by the reuse panel exactly as before
    (``SC-P11-UI-021-5``).

    **Ordering clause, satisfied by the caller, not this function:**
    ``Main_Window.open_document`` must call this exactly once, after the tab
    exists (so the dialog has a parent and the user can see which project is
    asking) and **before** the loaded set is bound to the tab, bound to the
    reuse panel, or used to resolve anything (plan §3.11 (2)). This function
    performs no binding itself — it only returns the pair the caller writes
    back (``record.reference_set = …``, ``document.prefs = …``).

    Pure aside from the modal dialogs :meth:`Asset_Update_Prompt_Dialog.decide`
    may raise; performs no I/O of its own.

    Args:
        reference_set: The project's reference set, as loaded (T30).
        catalog: The local library catalog to classify references against.
        prefs: The project's confirmation-preferences snapshot.
        project_key: This project's stable, unique key (plan §3.11 (2b)) —
            scopes both the "always" preference lookup's session cache and
            the reuse panel's shared-state bucket; minted by the caller.
        parent: The dialog's Qt parent, so a raised prompt is anchored to the
            project asking about it.
        on_decided: Forwarded unchanged, per edited reference, to
            :meth:`Asset_Update_Prompt_Dialog.decide` — see that method's own
            ``on_decided`` doc for exactly when it fires (T50, ADR-0062).

    Returns:
        ``(reference_set, prefs)`` — the pair to write back onto the tab.
    """
    states = reference_states(reference_set, catalog)
    tokens = edit_tokens(reference_set, catalog)
    for reference in reference_set.entries():
        asset_id = reference.asset_id
        if states.get(asset_id) != STATE_EDITED:
            continue
        entry = catalog.get(asset_id)
        assert entry is not None  # STATE_EDITED implies a catalog entry exists
        outcome, prefs = Asset_Update_Prompt_Dialog.decide(
            asset_id,
            entry.name,
            prefs,
            parent,
            edit_token=tokens[asset_id],
            project_key=project_key,
            on_decided=on_decided,
        )
        if outcome == OUTCOME_PICK_UP:
            reference_set = reference_set.remove(asset_id).add(
                AssetReference(asset_id, entry.content_hash, entry.kind, entry.name)
            )
    return reference_set, prefs
