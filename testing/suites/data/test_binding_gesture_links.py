"""Check (d) -- every gesture row's proof_node_ids is a COLLECTABLE pytest id.

``REQ-IS-LOGIC-008``, ``REQ-IS-LOGIC-009`` (D-15,
the input-scheme task list). Check (a)
(``testing/suites/ui/test_binding_registry_reality.py``) proves the
registry's ``key`` rows equal the app's real ``QAction`` shortcuts, but Qt
exposes no introspection API for a pointer gesture -- "middle-click on
``Canvas_View``" or "Ctrl+wheel" is not a ``QAction`` and never will be. That
leaves the nine ``gesture`` rows in
``pixelart_creator/logic/binding_registry.py`` unverified by anything except
this check: without it, a gesture deleted from the product tomorrow would
leave the registry and the shipped user guide agreeing with each other,
forever, about a gesture that no longer exists.

**What this proves, and the hard limit on what it does not.** Every
``gesture`` row's ``proof_node_ids`` are proven collectable by pytest's own
collection machinery -- a REAL ``pytest --collect-only`` subprocess against
each cited node id, whose OWN exit code decides the verdict, never a string
search of a file's contents (which would happily pass against a
commented-out test). **This is a link to evidence, not the evidence
itself**: a collectable node id proves *a test with that id exists*; it does
NOT prove the test's body asserts the gesture it is cited for. Stating that
only here, in a docstring, would leave a reader of a green run believing
more was proven than was -- so :data:`_LIMIT_NOTE` is printed by
:func:`check_gesture_proof_links` itself, on every call, pass or fail, into
the test's own captured output.

**The floor.** :func:`check_gesture_proof_links` calls
``require_non_empty_scope`` (``pixelart_creator.logic.scope_floor``) twice --
once over the gesture rows handed in, once over the de-duplicated node ids
gathered from them -- before reporting any verdict, and prints the
denominator ("N gesture rows checked, M node ids collected") on every
successful call. An empty scope raises :class:`ScopeFloorError` carrying the
literal substring ``"error: empty-scope"`` rather than reading as a clean
pass; this project has five recorded gates that passed while unable to
answer their own question, and the floor is what stops a sixth
(``REQ-IS-LOGIC-009``).

**The control.** ``TestControlProvesTheCheckCanFail`` points the check at
deliberately bogus node ids -- one naming a real file but a test name that
does not exist, one naming a file that does not exist at all -- and asserts
it reports each as uncollectable. A collectability check that has never been
seen to reject anything has not been shown to work; this project has three
recorded false diagnoses from instruments nobody controlled.

**Zero Qt in this module or its subprocess invocations' own process.** This
file lives in ``testing/suites/data`` and imports nothing from
``PySide6``. It DOES shell out to a real ``pytest --collect-only`` subprocess
to check node ids that live in ``testing/suites/ui`` (which does import Qt to
collect) -- ``QT_QPA_PLATFORM=offscreen`` is set on that subprocess's own
environment so the collection import succeeds headlessly; the Qt import
happens in the CHILD process, never in this one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pytest

from pixelart_creator.logic import binding_registry
from pixelart_creator.logic.binding_registry import Binding
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

# Repo root: this file lives at <root>/testing/suites/data/test_binding_gesture_links.py
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The check's own stated limit, printed into every call's captured output
#: (pass or fail) -- never stated only in this module's docstring.
_LIMIT_NOTE = (
    "LIMIT: this check proves a pytest node id with this exact string is "
    "COLLECTABLE. It does NOT prove the collected test's body asserts the "
    "gesture it is cited for -- it is a link to evidence, not the evidence "
    "itself (REQ-IS-LOGIC-008)."
)


@dataclass(frozen=True)
class _CollectabilityResult:
    """The outcome of asking pytest's own collector about one node id."""

    node_id: str
    collectable: bool
    exit_code: int
    detail: str


def _check_node_id_collectable(
    node_id: str, *, basetemp: Path
) -> _CollectabilityResult:
    """Ask a REAL ``pytest --collect-only`` subprocess whether ``node_id``
    exists -- never a string comparison against a file's contents, which
    would pass on a commented-out test.

    The subprocess's OWN exit code decides the verdict (captured directly
    from ``subprocess.run``, never through a shell pipe): ``0`` means pytest
    collected at least one test under that node id; any other code (``4`` --
    usage error / no match -- is what an unknown node id or an unknown file
    actually returns, probed directly against this repository's own pytest
    before this module was written) means it is not collectable.
    """
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={basetemp}",
            node_id,
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    exit_code = proc.returncode  # the subprocess's OWN exit code, read directly
    return _CollectabilityResult(
        node_id=node_id,
        collectable=(exit_code == 0),
        exit_code=exit_code,
        detail=(proc.stdout + proc.stderr)[-2000:],
    )


@dataclass(frozen=True)
class _GestureLinkCheckResult:
    """The outcome of checking one set of gesture rows' proof_node_ids."""

    gesture_rows_examined: int
    node_ids_examined: int
    uncollectable: tuple[_CollectabilityResult, ...]

    @property
    def ok(self) -> bool:
        """True iff every de-duplicated proof node id was collectable."""
        return not self.uncollectable


def check_gesture_proof_links(
    gesture_rows: Sequence[Binding], *, basetemp: Path
) -> _GestureLinkCheckResult:
    """Check (d)'s comparison logic (``REQ-IS-LOGIC-008``): pure orchestration
    over a real ``pytest --collect-only`` subprocess per de-duplicated node
    id.

    Calls :func:`require_non_empty_scope` TWICE before reporting any verdict
    (``REQ-IS-LOGIC-009``): once over ``gesture_rows`` itself (a caller that
    hands this nothing to check must not read as a clean pass), and once over
    the de-duplicated ``proof_node_ids`` gathered from them (a set of gesture
    rows that collectively name zero node ids -- impossible via the real
    registry's own constructor invariant, but not impossible for a caller-
    built fixture -- must not read as a clean pass either).

    Prints the denominator and :data:`_LIMIT_NOTE` on every call that reaches
    a verdict, whether that verdict is a pass or a fail.
    """
    require_non_empty_scope(
        "gesture-proof-node-links",
        len(gesture_rows),
        of="gesture rows",
    )
    node_ids: list[str] = []
    seen: set[str] = set()
    for row in gesture_rows:
        for node_id in row.proof_node_ids:
            if node_id not in seen:
                seen.add(node_id)
                node_ids.append(node_id)
    require_non_empty_scope(
        "gesture-proof-node-links",
        len(node_ids),
        of="proof node ids",
    )

    results = tuple(
        _check_node_id_collectable(node_id, basetemp=basetemp) for node_id in node_ids
    )
    uncollectable = tuple(result for result in results if not result.collectable)

    print(
        f"[check (d) -- gesture-proof-node-links] {len(gesture_rows)} gesture "
        f"rows checked, {len(node_ids)} node ids collected "
        f"({len(node_ids) - len(uncollectable)} collectable, "
        f"{len(uncollectable)} NOT collectable). {_LIMIT_NOTE}"
    )
    return _GestureLinkCheckResult(
        gesture_rows_examined=len(gesture_rows),
        node_ids_examined=len(node_ids),
        uncollectable=uncollectable,
    )


# ============================================================================
# The real product claim: every gesture row in the real, unmodified registry
# cites only collectable proof node ids.
# ============================================================================


def test_every_real_gesture_proof_node_id_is_collectable(tmp_path: Path) -> None:
    """The actual product assertion (``REQ-IS-LOGIC-008``): run for real,
    against the real, unmodified ``binding_registry.gestures()`` -- not
    softened, not scoped down, and not skipped if it disagrees with reality.
    A gesture row citing an uncollectable node id is exactly the drift this
    check exists to catch, and it is reported honestly here rather than
    absorbed.
    """
    result = check_gesture_proof_links(binding_registry.gestures(), basetemp=tmp_path)
    assert result.ok, (
        "check (d) FAILS: the following gesture proof_node_ids are NOT "
        "collectable by pytest (finding for the owning teams, not a defect to "
        "repair here):\n"
        + "\n".join(
            f"  {item.node_id!r} (subprocess exit {item.exit_code})\n"
            f"    {item.detail}"
            for item in result.uncollectable
        )
    )


def test_the_real_registry_has_nine_gesture_rows() -> None:
    """Pins the denominator this module's docstring and report both quote --
    a change to the gesture-row count is a signal this suite's own numbers
    need re-stating, not a silent drift.
    """
    assert len(binding_registry.gestures()) == 9


def test_a_clean_real_pass_states_its_own_limit_and_denominator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A green run of the real check states, in its OWN printed output (not
    only in this module's docstring): how many gesture rows and node ids it
    examined, AND that collectability is not proof of assertion.
    """
    capsys.readouterr()  # discard anything buffered before this point
    result = check_gesture_proof_links(binding_registry.gestures(), basetemp=tmp_path)
    captured = capsys.readouterr()

    assert result.ok
    assert "9 gesture rows checked" in captured.out
    assert f"{result.node_ids_examined} node ids collected" in captured.out
    assert "does NOT prove" in captured.out
    assert "REQ-IS-LOGIC-008" in captured.out


# ============================================================================
# The floor: REQ-IS-LOGIC-009, require_non_empty_scope, called before either
# verdict can be reported.
# ============================================================================


class TestScopeFloor:
    def test_zero_gesture_rows_raises_the_empty_scope_floor(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            check_gesture_proof_links([], basetemp=tmp_path)
        assert "error: empty-scope" in str(excinfo.value)
        assert excinfo.value.check_name == "gesture-proof-node-links"
        assert excinfo.value.of == "gesture rows"

    def test_gesture_rows_present_but_zero_node_ids_raises_the_empty_scope_floor(
        self, tmp_path: Path
    ) -> None:
        # A "key" row (default proof_node_ids=()) is a valid Binding on its
        # own -- unlike a "gesture" row, whose constructor forbids an empty
        # proof_node_ids tuple -- so this exercises the SECOND floor call
        # (over the de-duplicated node ids) independently of the first.
        key_row = binding_registry.by_id("tool.pencil")
        assert key_row.proof_node_ids == ()

        with pytest.raises(ScopeFloorError) as excinfo:
            check_gesture_proof_links([key_row], basetemp=tmp_path)
        assert "error: empty-scope" in str(excinfo.value)
        assert excinfo.value.of == "proof node ids"

    def test_this_module_imports_and_calls_the_scope_floor(self) -> None:
        """SC-L009-3's convention: provable by reading this module's own
        source, not merely asserted in prose.
        """
        source = Path(__file__).read_bytes().decode("utf-8")
        assert "from pixelart_creator.logic.scope_floor import" in source
        assert "require_non_empty_scope" in source
        assert source.count("require_non_empty_scope(") >= 2


# ============================================================================
# The control: prove the check can actually FAIL. An instrument that has
# never been seen to reject anything has not been shown to work.
# ============================================================================


class TestControlProvesTheCheckCanFail:
    """Two bogus fixtures, two different flavours of "not collectable":
    a real file with a test name pytest has never heard of, and a file path
    that does not exist at all. Neither mutates the real registry -- each
    builds its own local :class:`Binding` fixture.
    """

    def _fixture_gesture_row(self, *, proof_node_id: str) -> Binding:
        real_gesture = binding_registry.by_id("gesture.wheel.favourites")
        return Binding(
            binding_id="fixture.control.bogus_gesture",
            kind="gesture",
            literal="Fixture-only",
            section_id=real_gesture.section_id,
            description=(
                "Control fixture for TestControlProvesTheCheckCanFail -- "
                "deliberately cites a proof_node_ids entry pytest cannot "
                "collect, to prove this check actually rejects a bad link "
                "rather than passing everything handed to it."
            ),
            proof_node_ids=(proof_node_id,),
        )

    def test_a_nonexistent_test_name_in_a_real_file_is_reported_uncollectable(
        self, tmp_path: Path
    ) -> None:
        bogus_node_id = (
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_this_test_name_does_not_exist_in_this_file"
        )
        bogus_row = self._fixture_gesture_row(proof_node_id=bogus_node_id)

        result = check_gesture_proof_links([bogus_row], basetemp=tmp_path)

        assert not result.ok
        assert result.node_ids_examined == 1
        assert len(result.uncollectable) == 1
        assert result.uncollectable[0].node_id == bogus_node_id
        assert result.uncollectable[0].exit_code != 0

    def test_a_nonexistent_test_file_is_reported_uncollectable(
        self, tmp_path: Path
    ) -> None:
        bogus_node_id = (
            "testing/suites/ui/test_this_file_does_not_exist_at_all.py::test_foo"
        )
        bogus_row = self._fixture_gesture_row(proof_node_id=bogus_node_id)

        result = check_gesture_proof_links([bogus_row], basetemp=tmp_path)

        assert not result.ok
        assert result.uncollectable[0].node_id == bogus_node_id

    def test_a_real_collectable_node_id_control_pairs_against_the_above(
        self, tmp_path: Path
    ) -> None:
        """The other half of the control: the SAME machinery, pointed at a
        node id known to exist, must report it collectable -- proving the
        rejections above are about the id, not about the machinery always
        saying no.
        """
        real_gesture = binding_registry.by_id("gesture.wheel.favourites")
        real_node_id = real_gesture.proof_node_ids[0]
        fixture_row = self._fixture_gesture_row(proof_node_id=real_node_id)

        result = check_gesture_proof_links([fixture_row], basetemp=tmp_path)

        assert result.ok
        assert not result.uncollectable
