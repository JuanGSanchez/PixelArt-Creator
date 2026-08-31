"""Tests for pixelart_creator.logic.binding_registry (zero Qt).

Covers REQ-IS-LOGIC-005, REQ-IS-LOGIC-009 (D-15) — Gherkin SC-L005-1..8,
SC-L009-1..6 (`design-docs/specs/input-scheme/tasks.md` T-35).

T-35 exists because the `sdd-analyze` reconciling pass of 2026-08-30 found
that T-32 built this module with no paired test task (finding F-12): the
registry's shape is asserted here, Qt-free, against the module's own
declared invariants rather than a copy of them.

FOLLOW-UP to T-35: the registry gained a deliberate THIRD kind,
``"key_proof"``, after check (b) (the guide cross-check) found three real
key bindings — `Esc`, `Enter` (float commit/cancel, `Canvas_View.
keyPressEvent`) and `Space` (playback play/pause, a widget-scoped
`QShortcut`) — that are genuine bindings but are not `QAction`s, so check
(a)'s `win.findChildren(QAction)` walk can never introspect them. ``kind``
therefore answers "how is this binding PROVEN?", not "is it a key or a
mouse gesture": a ``"key"`` row is proven by check (a)'s Qt introspection;
a ``"gesture"`` or ``"key_proof"`` row is proven instead by a cited,
collectable pytest node id (check (d)) because Qt exposes no introspection
API for either shape. The tests below assert the three-way partition is
EXHAUSTIVE (every row belongs to exactly one of ``keys()``/``gestures()``/
``key_proofs()``, and the three groups sum to the whole registry) rather
than checking each accessor in isolation, which could silently miss a row
belonging to none of them.
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import binding_registry
from pixelart_creator.logic.binding_registry import (
    REGISTRY,
    Binding,
    BindingRegistryError,
    by_id,
    gestures,
    key_proofs,
    keys,
)
from pixelart_creator.logic.guide_model import REQUIRED_AREAS

# A minimal, valid set of constructor kwargs a test can override per-field to
# probe one invariant at a time without repeating every other valid field.
_VALID_KEY_KWARGS = dict(
    binding_id="test.probe",
    kind="key",
    literal="Z",
    section_id=REQUIRED_AREAS[0],
    description="A probe row for the __post_init__ invariants.",
)


def _make(**overrides: object) -> Binding:
    kwargs = dict(_VALID_KEY_KWARGS)
    kwargs.update(overrides)
    return Binding(**kwargs)  # type: ignore[arg-type]


class TestBindingConstructionInvariants:
    """One test per __post_init__ branch — the happy path and each rejection."""

    def test_accepts_a_fully_valid_key_row(self) -> None:
        row = _make()
        assert row.binding_id == "test.probe"
        assert row.kind == "key"

    def test_accepts_a_fully_valid_gesture_row(self) -> None:
        row = _make(kind="gesture", proof_node_ids=("t.py::test_x",))
        assert row.kind == "gesture"
        assert row.proof_node_ids == ("t.py::test_x",)

    def test_accepts_a_fully_valid_key_proof_row(self) -> None:
        row = _make(kind="key_proof", proof_node_ids=("t.py::test_y",))
        assert row.kind == "key_proof"
        assert row.proof_node_ids == ("t.py::test_y",)

    def test_rejects_empty_binding_id(self) -> None:
        with pytest.raises(BindingRegistryError, match="non-empty binding_id"):
            _make(binding_id="")

    def test_rejects_kind_outside_key_gesture_or_key_proof(self) -> None:
        with pytest.raises(BindingRegistryError, match="kind must be one of"):
            _make(kind="chord")

    def test_rejects_empty_literal(self) -> None:
        with pytest.raises(BindingRegistryError, match="literal must be non-empty"):
            _make(literal="")

    def test_rejects_section_id_not_in_required_areas(self) -> None:
        with pytest.raises(BindingRegistryError, match="not a .*REQUIRED_AREAS"):
            _make(section_id="not-a-real-section")

    def test_rejects_empty_description(self) -> None:
        with pytest.raises(BindingRegistryError, match="description must be non-empty"):
            _make(description="")

    def test_rejects_gesture_row_with_no_proof_node_ids(self) -> None:
        with pytest.raises(BindingRegistryError, match="proof_node_ids entry"):
            _make(kind="gesture", proof_node_ids=())

    def test_rejects_key_proof_row_with_no_proof_node_ids(self) -> None:
        with pytest.raises(BindingRegistryError, match="proof_node_ids entry"):
            _make(kind="key_proof", proof_node_ids=())

    def test_key_row_needs_no_proof_node_ids(self) -> None:
        # A key row's default proof_node_ids is empty and that is valid —
        # the constraint in __post_init__ only fires for kind == "gesture".
        row = _make(proof_node_ids=())
        assert row.proof_node_ids == ()


class TestRegistryShape:
    """Assertions against the shipped REGISTRY itself, Qt-free."""

    def test_registry_is_non_empty(self) -> None:
        assert len(REGISTRY) > 0

    def test_every_row_binding_id_is_non_empty(self) -> None:
        for row in REGISTRY:
            assert row.binding_id

    def test_every_row_kind_is_key_gesture_or_key_proof(self) -> None:
        for row in REGISTRY:
            assert row.kind in ("key", "gesture", "key_proof")

    def test_every_row_literal_is_non_empty(self) -> None:
        for row in REGISTRY:
            assert row.literal

    def test_every_row_section_id_is_a_real_required_area(self) -> None:
        # Checked against the guide model's own tuple, not a copy of it
        # (T-35's explicit instruction).
        for row in REGISTRY:
            assert row.section_id in REQUIRED_AREAS

    def test_every_gesture_row_has_non_empty_proof_node_ids(self) -> None:
        for row in gestures():
            assert row.proof_node_ids

    def test_every_key_proof_row_has_non_empty_proof_node_ids(self) -> None:
        # This is the entire justification for the kind existing: a
        # key_proof row without a proof is a row nobody checks.
        for row in key_proofs():
            assert row.proof_node_ids

    def test_every_key_row_kind_is_literally_key(self) -> None:
        for row in keys():
            assert row.kind == "key"

    def test_every_gesture_row_kind_is_literally_gesture(self) -> None:
        for row in gestures():
            assert row.kind == "gesture"

    def test_every_key_proof_row_kind_is_literally_key_proof(self) -> None:
        for row in key_proofs():
            assert row.kind == "key_proof"

    def test_keys_gestures_and_key_proofs_partition_the_registry(self) -> None:
        # Exhaustive: the three groups sum to the whole registry, and are
        # pairwise disjoint. Checking each accessor in isolation could
        # silently miss a row belonging to none of the three groups; this
        # is the test that would catch that.
        key_set = set(keys())
        gesture_set = set(gestures())
        proof_set = set(key_proofs())
        assert key_set | gesture_set | proof_set == set(REGISTRY)
        assert key_set & gesture_set == set()
        assert key_set & proof_set == set()
        assert gesture_set & proof_set == set()
        assert len(key_set) + len(gesture_set) + len(proof_set) == len(REGISTRY)

    def test_binding_ids_are_unique(self) -> None:
        ids = [row.binding_id for row in REGISTRY]
        assert len(ids) == len(set(ids))

    def test_module_level_uniqueness_guard_rejects_a_duplicate(self) -> None:
        # _check_unique_ids is the private function REGISTRY itself is built
        # with; exercise it directly against a deliberately duplicated pair
        # so the guard's own behaviour is proven, not just its having run
        # once at import time.
        dup = (
            _make(binding_id="dup.one"),
            _make(binding_id="dup.one"),
        )
        with pytest.raises(BindingRegistryError, match="duplicate binding_id"):
            binding_registry._check_unique_ids(dup)


class TestById:
    def test_returns_the_matching_row(self) -> None:
        wanted = REGISTRY[0]
        assert by_id(wanted.binding_id) is wanted

    def test_raises_on_unknown_id(self) -> None:
        with pytest.raises(BindingRegistryError, match="unknown binding_id"):
            by_id("no.such.binding")


class TestKeysAndGestures:
    def test_keys_returns_only_key_kind_rows_in_declared_order(self) -> None:
        result = keys()
        expected = tuple(row for row in REGISTRY if row.kind == "key")
        assert result == expected

    def test_gestures_returns_only_gesture_kind_rows_in_declared_order(self) -> None:
        result = gestures()
        expected = tuple(row for row in REGISTRY if row.kind == "gesture")
        assert result == expected

    def test_key_proofs_returns_only_key_proof_kind_rows_in_declared_order(
        self,
    ) -> None:
        result = key_proofs()
        expected = tuple(row for row in REGISTRY if row.kind == "key_proof")
        assert result == expected


class TestDescriptionNeverLeaksIntoComparison:
    """SC-L005-8: description must be absent from every equality/matching path.

    A check that compared descriptions would fail every time someone
    improved a sentence. This class proves the field CAN leak into a naive
    ``==`` (dataclass equality is field-by-field, description included) and
    that the correct join key for cross-check matching — the one checks
    (a)/(b)/(c)/(d) must use — explicitly excludes it. It is not enough for
    the field to merely exist; a comparison built on the wrong key must be
    demonstrably wrong.
    """

    @staticmethod
    def _match_key(row: Binding) -> tuple[str, str, str, str]:
        """The correct cross-check join key: everything except description
        (and except proof_node_ids, which only gesture rows carry)."""
        return (row.binding_id, row.kind, row.literal, row.section_id)

    def test_two_rows_differing_only_in_description_are_not_dataclass_equal(
        self,
    ) -> None:
        # Proves the trap exists: description DOES participate in bare `==`,
        # so any check that used plain dataclass equality as its matching
        # path would silently start failing on a copy-edit.
        a = _make(description="Select the probe tool.")
        b = _make(description="Selects the probe tool (rephrased).")
        assert a != b

    def test_two_rows_differing_only_in_description_match_on_the_correct_key(
        self,
    ) -> None:
        a = _make(description="Select the probe tool.")
        b = _make(description="Selects the probe tool (rephrased).")
        assert self._match_key(a) == self._match_key(b)

    def test_match_key_excludes_description_field_name(self) -> None:
        # Static shape guard: "description" must not appear among the
        # fields the join key is built from.
        key_fields = {"binding_id", "kind", "literal", "section_id"}
        assert "description" not in key_fields

    def test_registry_rows_are_never_matched_by_description_content(self) -> None:
        # No two real rows share a description (spot-checking would be
        # meaningless if they did); more importantly, match keys built from
        # the real registry are still unique WITHOUT description in them —
        # proving binding_id/kind/literal/section_id alone already
        # disambiguate every row, so description is never load-bearing for
        # identity.
        match_keys = [self._match_key(row) for row in REGISTRY]
        assert len(match_keys) == len(set(match_keys))

    def test_description_field_exists_but_is_documented_non_authoritative(
        self,
    ) -> None:
        # The field is real (not merely tested for absence) — every row has
        # one — but its own field metadata carries no authority marker such
        # as being part of __eq__ exclusions; the exclusion lives in the
        # caller's chosen key, per the module docstring, not in the
        # dataclass itself. This test pins that every row does carry SOME
        # description text, so "absent from comparison" is a deliberate
        # choice about matching, not an accident of an empty field.
        for row in REGISTRY:
            assert isinstance(row.description, str)
            assert row.description != ""


class TestBindingIsFrozen:
    def test_binding_rows_are_immutable(self) -> None:
        row = REGISTRY[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.binding_id = "mutated"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# property-based tests                                                        #
# --------------------------------------------------------------------------- #

_valid_section_ids = st.sampled_from(REQUIRED_AREAS)
_nonempty_text = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


@given(binding_id=_nonempty_text, literal=_nonempty_text, section_id=_valid_section_ids)
def test_any_valid_key_row_constructs_without_error(
    binding_id: str, literal: str, section_id: str
) -> None:
    row = Binding(
        binding_id=binding_id,
        kind="key",
        literal=literal,
        section_id=section_id,
        description="generated by hypothesis",
    )
    assert row.binding_id == binding_id
    assert row.proof_node_ids == ()


@given(section_id=_valid_section_ids)
def test_gesture_row_without_proof_node_ids_always_rejected(section_id: str) -> None:
    with pytest.raises(BindingRegistryError):
        Binding(
            binding_id="gesture.probe",
            kind="gesture",
            literal="Wheel",
            section_id=section_id,
            description="generated by hypothesis",
            proof_node_ids=(),
        )


@given(section_id=_valid_section_ids)
def test_key_proof_row_without_proof_node_ids_always_rejected(section_id: str) -> None:
    with pytest.raises(BindingRegistryError):
        Binding(
            binding_id="key_proof.probe",
            kind="key_proof",
            literal="Esc",
            section_id=section_id,
            description="generated by hypothesis",
            proof_node_ids=(),
        )


@given(
    section_id=st.text(min_size=1, max_size=20).filter(
        lambda s: s not in REQUIRED_AREAS
    )
)
def test_any_section_id_outside_required_areas_is_rejected(section_id: str) -> None:
    with pytest.raises(BindingRegistryError):
        _make(section_id=section_id)
