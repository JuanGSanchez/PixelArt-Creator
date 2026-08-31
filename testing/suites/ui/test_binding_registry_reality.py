"""Check (a) — the binding registry equals reality, in both directions.

``tasks.md`` T-33 (AGT-06), ``REQ-IS-UI-031``, ``SC-U031-1..6``
(``design-docs/specs/input-scheme/spec.md`` §9). This is the check that makes
``pixelart_creator/logic/binding_registry.py`` (T-32, AGT-03) trustworthy
without rebuilding the UI on top of it: the registry was deliberately NOT
made the construction source for ``Main_Window``'s ``QAction``s (68 actions
vs. ~30 documented bindings — see that module's own docstring, "ruling 2"),
so nothing stops the two from drifting apart except a check that actually
builds the real window and compares.

**Both directions, unconditionally.** A binding present in the real app that
the registry does not declare FAILS; a ``key`` row the registry declares
that the app does not bind FAILS. One-directional containment would let the
registry silently rot (rows nobody removes) or silently lag (bindings nobody
adds) while still reading green.

**Two things this module gets right on purpose:**

1. It reads ``action.shortcuts()`` (plural), not only ``action.shortcut()``.
   ``Main_Window._clear_action`` carries BOTH ``Shift+Q`` and ``Delete``
   (``REQ-IS-UI-005``) — a collector that only read ``.shortcut()`` (the
   *primary* sequence) would see one of the two and falsely flag the other
   as a registry-only orphan against a registry that is, on that point,
   correct. ``test_clear_selection_carries_both_shortcuts_via_plural_api``
   pins this directly.
2. Gestures are OUT OF SCOPE here, by construction, not by oversight: Qt
   exposes no introspection API for "middle-click on ``Canvas_View``" or
   "Ctrl+wheel". Every call into the comparison logic below prints that
   limit into the test's own captured output (not only into this docstring),
   so a reader of a green — or a red — run sees it without having to know to
   look for a comment. Gesture coverage is check (d), ``REQ-IS-LOGIC-008``,
   owned elsewhere.

**Design: the real assertion is kept separate from the check's own
correctness.** ``SC-U031-1`` is the actual product claim ("the app and the
registry agree") and is run for real, against the real ``Main_Window`` and
the real, unmodified ``REGISTRY`` — this project's five recorded false-clean
gates are exactly why that comparison is never smoothed over here (see this
module's own report for what it found). ``SC-U031-2``, ``SC-U031-3``,
``SC-U031-4`` and ``SC-U031-6`` instead prove the COMPARISON LOGIC ITSELF is
correct, using a locally built fixture list of ``Binding`` rows compared
against the real window's real actions — never a mutated copy of the product
module, per the hard rule against mutating a real artefact under test.

Runs headless (``QT_QPA_PLATFORM=offscreen``, forced by this suite's own
``conftest.py``) and both themes (the suite's autouse ``theme`` fixture) —
shortcuts do not depend on QSS, but the suite-wide contract of "no UI
criterion verified in only one theme" is honoured for free rather than
opted out of.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtGui import QAction, QKeySequence

from pixelart_creator.logic import binding_registry
from pixelart_creator.logic.binding_registry import Binding
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope
from pixelart_creator.ui.main_window import Main_Window

#: The gesture-scope disclosure required by ``REQ-IS-UI-031`` / ``SC-U031-4``,
#: printed by every call into :func:`check_registry_equals_reality` — on a
#: pass AND on a failure, since the print happens before any assertion.
_GESTURE_SCOPE_NOTE = (
    "Gestures are NOT covered by this check -- Qt exposes no introspection "
    "API for a pointer gesture (e.g. a middle-click or a wheel step); "
    "gesture coverage is check (d)'s responsibility (REQ-IS-LOGIC-008), not "
    "this one."
)


@dataclass(frozen=True)
class _RealityCheckResult:
    """The outcome of one registry-to-reality comparison (check (a))."""

    actions_examined: int
    bindings_compared: int
    app_only: frozenset[str]
    registry_only: frozenset[str]

    @property
    def ok(self) -> bool:
        """True iff both directions of the set-equality hold exactly."""
        return not self.app_only and not self.registry_only


def _normalize(literal: str) -> str:
    """Canonicalise a key literal through ``QKeySequence`` so that spellings
    Qt itself treats as identical (``"Delete"`` vs. ``"Del"``) compare equal.

    A prior draft of this module compared raw registry ``literal`` strings
    against raw ``QKeySequence.toString()`` output and reported
    ``action.clear_selection.delete``'s ``"Delete"`` as a registry-only
    mismatch against the app's ``"Del"`` -- a false positive of this test's
    OWN making, not a product defect: ``QKeySequence("Delete") ==
    QKeySequence("Del")`` is ``True`` in Qt (probed this session), so both
    sides are routed through this one normaliser before any set operation.
    That finding is WITHDRAWN here, not merely fixed silently.
    """
    return QKeySequence(literal).toString()


def _collect_app_shortcuts(actions: Sequence[QAction]) -> set[str]:
    """Read every non-empty key sequence bound to ``actions``.

    Reads BOTH ``action.shortcut()`` (the primary sequence) and
    ``action.shortcuts()`` (the full list) per action, and asserts the
    former is always a member of the latter -- Qt's own documented
    invariant. Using ``.shortcuts()`` as the actual collection source is
    what keeps a two-shortcut action (``Main_Window._clear_action``: both
    ``Shift+Q`` and ``Delete``) from losing one of its two bindings here.
    """
    found: set[str] = set()
    for action in actions:
        primary = action.shortcut()
        all_sequences = action.shortcuts()
        if not primary.isEmpty():
            assert primary in all_sequences, (
                f"action {action.text()!r}: shortcut() {primary.toString()!r} "
                f"is not a member of its own shortcuts() "
                f"{[s.toString() for s in all_sequences]!r} -- violates Qt's "
                "documented shortcut()/shortcuts() invariant"
            )
        for sequence in all_sequences:
            if not sequence.isEmpty():
                found.add(sequence.toString())
    return found


def check_registry_equals_reality(
    actions: Sequence[QAction],
    key_rows: Sequence[Binding],
) -> _RealityCheckResult:
    """Check (a)'s comparison logic (``REQ-IS-UI-031``): pure, reusable,
    Qt-object-consuming but never window-owning.

    Callable against the real ``Main_Window``'s real actions and the real,
    unmodified registry (the product claim, ``SC-U031-1``) OR against a
    caller-built fixture list of :class:`Binding` rows compared against the
    real window's real actions (the check's OWN correctness,
    ``SC-U031-2/3/4/6``) -- the two questions stay separable this way.

    Calls :func:`require_non_empty_scope` FIRST (``REQ-IS-LOGIC-009``,
    ``SC-U031-6``): an empty ``actions`` sequence raises
    :class:`ScopeFloorError` carrying ``"error: empty-scope"`` before any
    comparison is attempted, so a check that was handed nothing to look at
    cannot read as a clean pass.
    """
    require_non_empty_scope(
        "registry-to-reality",
        len(actions),
        of="actions introspected",
    )
    app_set = _collect_app_shortcuts(actions)
    registry_set = {_normalize(row.literal) for row in key_rows}
    result = _RealityCheckResult(
        actions_examined=len(actions),
        bindings_compared=len(registry_set),
        app_only=frozenset(app_set - registry_set),
        registry_only=frozenset(registry_set - app_set),
    )
    print(
        f"[check (a) -- registry-to-reality] {result.actions_examined} "
        f"actions introspected, {result.bindings_compared} key bindings "
        f"compared. {_GESTURE_SCOPE_NOTE}"
    )
    return result


def _build_window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# ============================================================================
# SC-U031-1 -- the real product claim: app and registry agree, exactly.
# ============================================================================


def test_sc_u031_1_app_shortcuts_equal_registry_key_rows_exactly(qtbot):
    """SC-U031-1: collecting shortcut()/shortcuts() across every real action
    on a real Main_Window must equal, exactly, the set of literals in the
    real, unmodified registry's key rows -- in both directions.

    This is the actual product assertion, run for real against unmodified
    code; it is not softened, scoped down, or marked xfail if it disagrees
    with reality -- a disagreement here is exactly the signal this module
    exists to raise, and it is reported honestly rather than absorbed.
    """
    win = _build_window(qtbot)
    actions = win.findChildren(QAction)
    result = check_registry_equals_reality(actions, list(binding_registry.keys()))
    assert result.ok, (
        "check (a) FAILS: the app and the registry disagree.\n"
        f"  app has, registry lacks ({len(result.app_only)}): "
        f"{sorted(result.app_only)!r}\n"
        f"  registry has, app lacks ({len(result.registry_only)}): "
        f"{sorted(result.registry_only)!r}"
    )


# ============================================================================
# SC-U031-2/3/4/6 -- the check's OWN correctness, via a local fixture list.
# None of these mutate pixelart_creator.logic.binding_registry.REGISTRY;
# each builds its own tuple of Binding rows and passes it directly.
# ============================================================================


def test_sc_u031_2_a_binding_in_the_app_the_registry_lacks_fails(qtbot):
    """SC-U031-2: with one real key row removed from a fixture registry, the
    check FAILS and names the binding the (fixture) registry now lacks.

    ``tool.pencil`` ("A") is chosen because the real app unconditionally
    binds it (``REQ-IS-UI-001``) regardless of any other drift SC-U031-1 may
    have found -- so this scenario is provable in isolation from that
    question.
    """
    win = _build_window(qtbot)
    actions = win.findChildren(QAction)
    removed = binding_registry.by_id("tool.pencil")
    fixture_rows = [
        row for row in binding_registry.keys() if row.binding_id != removed.binding_id
    ]

    result = check_registry_equals_reality(actions, fixture_rows)

    assert not result.ok
    assert _normalize(removed.literal) in result.app_only, (
        f"expected {removed.literal!r} (removed row {removed.binding_id!r}) "
        f"to be reported as app-only; got app_only={sorted(result.app_only)!r}"
    )


def test_sc_u031_3_a_registry_row_the_app_lacks_fails(qtbot):
    """SC-U031-3: with one extra, unbound key row added to a fixture
    registry, the check FAILS and names the row the app lacks.
    """
    win = _build_window(qtbot)
    actions = win.findChildren(QAction)
    extra = Binding(
        binding_id="fixture.sc_u031_3.unbound_row",
        kind="key",
        literal="Ctrl+Alt+Shift+F12",
        section_id="app-basics",
        description=(
            "Fixture-only row for SC-U031-3 -- the real app binds nothing to "
            "this sequence, by construction of the test."
        ),
    )
    fixture_rows = [*binding_registry.keys(), extra]

    result = check_registry_equals_reality(actions, fixture_rows)

    assert not result.ok
    assert _normalize(extra.literal) in result.registry_only, (
        f"expected {extra.literal!r} (fixture row {extra.binding_id!r}) to be "
        f"reported as registry-only; got registry_only="
        f"{sorted(result.registry_only)!r}"
    )


def test_sc_u031_4_a_clean_pass_states_the_gesture_scope_limit(qtbot, capsys):
    """SC-U031-4: when the check runs and PASSES, its captured output states
    that gestures are not Qt-introspectable and that gesture coverage is
    check (d)'s responsibility.

    The fixture registry here is built FROM the real window's own
    introspected shortcuts (not the product ``REGISTRY``), which
    deterministically produces a clean pass regardless of anything
    SC-U031-1 finds -- isolating "does the PASS path disclose the gesture
    limit" from "is the real registry complete", which is a separate
    question this module answers in SC-U031-1.
    """
    win = _build_window(qtbot)
    actions = win.findChildren(QAction)
    app_literals = sorted(_collect_app_shortcuts(actions))
    self_consistent_rows = tuple(
        Binding(
            binding_id=f"fixture.sc_u031_4.self_consistent.{index}",
            kind="key",
            literal=literal,
            section_id="app-basics",
            description="Fixture row mirroring the app's own shortcut set, "
            "built only to exercise the check's PASS output (SC-U031-4).",
        )
        for index, literal in enumerate(app_literals)
    )

    capsys.readouterr()  # discard anything buffered before this point
    result = check_registry_equals_reality(actions, self_consistent_rows)
    captured = capsys.readouterr()

    assert result.ok, (
        "a fixture registry built from the app's own shortcuts must pass; "
        f"app_only={sorted(result.app_only)!r} "
        f"registry_only={sorted(result.registry_only)!r}"
    )
    assert "gesture" in captured.out.lower()
    assert "check (d)" in captured.out
    assert "REQ-IS-LOGIC-008" in captured.out


def test_sc_u031_6_zero_actions_raises_the_empty_scope_floor():
    """SC-U031-6: handed zero actions, the check raises ScopeFloorError
    carrying the literal substring ``"error: empty-scope"`` -- it does not
    read a zero-action scope as a clean pass.
    """
    with pytest.raises(ScopeFloorError) as exc_info:
        check_registry_equals_reality([], list(binding_registry.keys()))
    assert "error: empty-scope" in str(exc_info.value)


def test_sc_u031_6b_this_module_imports_and_calls_the_scope_floor():
    """SC-U031-6 (second half): this check module itself imports
    ``require_non_empty_scope`` and calls it -- provable by reading this
    module's own source, the same convention ``SC-L009-3`` uses for the
    other three guide-enforcement check modules.
    """
    source = Path(__file__).read_bytes().decode("utf-8")
    assert "from pixelart_creator.logic.scope_floor import" in source
    assert "require_non_empty_scope" in source
    assert source.count("require_non_empty_scope(") >= 1


# ============================================================================
# The two things T-33 calls out to get right, pinned directly.
# ============================================================================


def test_clear_selection_carries_both_shortcuts_via_plural_api(qtbot):
    """A collector reading only ``action.shortcut()`` would see exactly one
    of clear-selection's two bound sequences (``REQ-IS-UI-005``: ``Shift+Q``
    added, ``Delete`` kept) and would then report a false mismatch against a
    registry that, on this row, is correct. This module's own collector
    reads ``.shortcuts()`` and must see both.
    """
    win = _build_window(qtbot)
    actions = win.findChildren(QAction)
    collected = _collect_app_shortcuts(actions)

    assert _normalize("Shift+Q") in collected
    assert _normalize("Delete") in collected
    assert len(win._clear_action.shortcuts()) == 2


def test_delete_and_del_literals_are_the_same_qt_key_sequence():
    """Documents, as an executable assertion, the normalisation this module
    depends on: Qt treats the registry's ``"Delete"`` literal
    (``action.clear_selection.delete``) and the app's own
    ``QKeySequence.toString()`` rendering ``"Del"`` as the identical key
    sequence. Without this normalisation step, ``check_registry_equals_reality``
    would report a false registry/app mismatch on a row that is, in fact,
    correct -- exactly the false positive withdrawn from an earlier draft of
    this module (see ``_normalize``'s own docstring).
    """
    assert QKeySequence("Delete") == QKeySequence("Del")
    assert _normalize("Delete") == _normalize("Del")
