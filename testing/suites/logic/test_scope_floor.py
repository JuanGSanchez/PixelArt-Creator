"""Tests for pixelart_creator.logic.scope_floor (zero Qt).

Covers REQ-IS-LOGIC-005, REQ-IS-LOGIC-009 (D-15) — Gherkin SC-L005-6,
SC-L009-1..6 (`design-docs/specs/input-scheme/tasks.md` T-35).

Besides the floor's own contract (return-silently / raise-on-zero /
distinguish missing-root from existing-but-empty), SC-L009-3 requires this
suite to assert the IMPORT-AND-CALL of ``require_non_empty_scope`` in all
four D-15 guide-enforcement check modules, because the other five D-15
requirements depend on the floor actually being invoked — a floor nobody
calls is decoration.

As of this task's authoring (T-35, wave 10) NONE of the four check modules
have landed yet: check (a) is T-33 (wave 10, AGT-06), checks (b)/(c) are
T-29 (wave 11, AGT-04) and check (d) is T-34 (wave 11, AGT-04) — all three
depend on T-32 and, per `tasks.md`, land in later waves than this one. This
suite does NOT skip that gap quietly: :class:`TestFloorIsCalledByEveryCheckModule`
enumerates all four expected paths, asserts explicitly (in the pytest
output, not via ``pytest.skip``) which are present versus not-yet-landed,
and — for every module that IS present — proves the import and the call.
Once a module lands, this same test starts verifying it with no edit
required here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import scope_floor
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

# Repo root: this file lives at <root>/testing/suites/logic/test_scope_floor.py
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The four D-15 guide-enforcement check modules that MUST import and call
# require_non_empty_scope before reporting a verdict (module docstring;
# tasks.md T-33/T-29/T-34). Path is relative to the repo root.
_EXPECTED_CHECK_MODULES: dict[str, Path] = {
    "check-a-registry-to-reality": Path(
        "testing/suites/ui/test_binding_registry_reality.py"
    ),
    "check-b-registry-to-guide": Path("testing/suites/data/test_guide_bindings.py"),
    "check-c-en-es-lockstep": Path("testing/suites/data/test_guide_locale_parity.py"),
    "check-d-gesture-proof-links": Path(
        "testing/suites/data/test_binding_gesture_links.py"
    ),
}


class TestReturnsSilentlyOnPositiveCount:
    def test_returns_none_for_a_positive_count(self) -> None:
        assert require_non_empty_scope("probe-check", 1, of="things") is None

    def test_returns_none_for_a_large_positive_count(self) -> None:
        assert require_non_empty_scope("probe-check", 10_000, of="things") is None

    def test_does_not_touch_the_filesystem_when_root_is_omitted(self) -> None:
        # No root given -> no existence check at all; a positive count alone
        # is sufficient to pass silently.
        require_non_empty_scope("probe-check", 3, of="rows")


class TestRaisesEmptyScopeOnZero:
    def test_zero_examined_raises_scope_floor_error(self) -> None:
        with pytest.raises(ScopeFloorError):
            require_non_empty_scope("probe-check", 0, of="rows")

    def test_negative_examined_also_raises_scope_floor_error(self) -> None:
        with pytest.raises(ScopeFloorError):
            require_non_empty_scope("probe-check", -1, of="rows")

    def test_error_carries_the_empty_scope_code(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("probe-check", 0, of="rows")
        assert excinfo.value.error == "empty-scope"

    def test_error_text_contains_the_literal_substring(self) -> None:
        with pytest.raises(ScopeFloorError, match="error: empty-scope"):
            require_non_empty_scope("probe-check", 0, of="rows")

    def test_error_names_the_check(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("registry-to-guide", 0, of="registry entries")
        assert excinfo.value.check_name == "registry-to-guide"

    def test_error_names_what_was_counted(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("registry-to-guide", 0, of="registry entries")
        assert excinfo.value.of == "registry entries"

    def test_error_carries_the_examined_count(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("registry-to-guide", 0, of="registry entries")
        assert excinfo.value.examined == 0

    def test_error_root_is_none_for_an_empty_scope_failure(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("registry-to-guide", 0, of="registry entries")
        assert excinfo.value.root is None

    def test_as_dict_omits_root_for_an_empty_scope_failure(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("registry-to-guide", 0, of="registry entries")
        payload = excinfo.value.as_dict()
        assert payload == {
            "error": "empty-scope",
            "check": "registry-to-guide",
            "of": "registry entries",
            "examined": 0,
        }
        assert "root" not in payload


class TestDistinguishesMissingRootFromEmptyScope:
    """A missing root and an existing-but-empty scope are different failures
    with different fixes; collapsing them would send someone hunting a typo
    when the real answer is 'the directory is there and has nothing in it'.
    """

    def test_missing_root_raises_root_not_found_before_examined_is_checked(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist"
        assert not missing.exists()
        with pytest.raises(ScopeFloorError) as excinfo:
            # examined=0 too, but the missing root must win: the error
            # explains "the root moved", not "the scope is empty".
            require_non_empty_scope("check-a", 0, of="rows", root=missing)
        assert excinfo.value.error == "root-not-found"

    def test_existing_but_empty_root_raises_empty_scope_not_root_not_found(
        self, tmp_path: Path
    ) -> None:
        empty_dir = tmp_path / "exists-but-empty"
        empty_dir.mkdir()
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("check-a", 0, of="rows", root=empty_dir)
        assert excinfo.value.error == "empty-scope"

    def test_existing_root_with_positive_examined_passes_silently(
        self, tmp_path: Path
    ) -> None:
        present = tmp_path / "exists-and-has-content"
        present.mkdir()
        assert require_non_empty_scope("check-a", 5, of="rows", root=present) is None

    def test_missing_root_error_carries_the_root_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("check-a", 0, of="rows", root=missing)
        assert excinfo.value.root == str(missing)

    def test_missing_root_error_text_contains_root_not_found(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(ScopeFloorError, match="error: root-not-found"):
            require_non_empty_scope("check-a", 0, of="rows", root=missing)

    def test_as_dict_omits_examined_for_a_root_not_found_failure(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "gone"
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("check-a", 0, of="rows", root=missing)
        payload = excinfo.value.as_dict()
        assert payload == {
            "error": "root-not-found",
            "check": "check-a",
            "of": "rows",
            "root": str(missing),
        }
        assert "examined" not in payload

    def test_root_accepts_a_string_path_too(self, tmp_path: Path) -> None:
        missing = tmp_path / "gone-as-string"
        with pytest.raises(ScopeFloorError) as excinfo:
            require_non_empty_scope("check-a", 0, of="rows", root=str(missing))
        assert excinfo.value.error == "root-not-found"


class TestScopeFloorErrorIsAValueError:
    def test_scope_floor_error_subclasses_value_error(self) -> None:
        assert issubclass(ScopeFloorError, ValueError)


class TestFloorIsCalledByEveryCheckModule:
    """SC-L009-3: assert the import-and-call in all four check modules.

    The other five D-15 requirements depend on the floor actually being
    invoked; this verifies it rather than assumes it. Every expected module
    is enumerated explicitly below — none is silently passed over.
    """

    @staticmethod
    def _imports_and_calls_require_non_empty_scope(source: str) -> tuple[bool, bool]:
        """Return (imports_it, calls_it) via an AST walk of ``source``.

        Accepts either ``from pixelart_creator.logic.scope_floor import
        require_non_empty_scope`` (direct call as
        ``require_non_empty_scope(...)``) or ``from pixelart_creator.logic
        import scope_floor`` (call as ``scope_floor.require_non_empty_scope(...)``).
        """
        tree = ast.parse(source)
        imports_it = False
        calls_it = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in (
                "pixelart_creator.logic.scope_floor",
                "pixelart_creator.logic",
            ):
                names = {alias.name for alias in node.names}
                if "require_non_empty_scope" in names or "scope_floor" in names:
                    imports_it = True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pixelart_creator.logic.scope_floor":
                        imports_it = True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "require_non_empty_scope":
                    calls_it = True
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "require_non_empty_scope"
                ):
                    calls_it = True
        return imports_it, calls_it

    @pytest.mark.parametrize(
        "check_name,relative_path",
        sorted(_EXPECTED_CHECK_MODULES.items()),
    )
    def test_check_module_imports_and_calls_the_floor(
        self, check_name: str, relative_path: Path
    ) -> None:
        full_path = _REPO_ROOT / relative_path

        if not full_path.exists():
            # Explicit, visible statement of the gap — deliberately NOT
            # pytest.skip(): a skipped test vanishes from the summary line
            # and reports the run as uniformly green, which is exactly how
            # this class of gap survives unnoticed (five times, per D-15's
            # own history). xfail is the honest middle ground: it shows up
            # in the pytest summary as an explicit, named "xfailed" entry
            # with this reason attached — visible, not swept under a
            # "passed" count — while still letting the suite exit 0 for a
            # gap that is EXPECTED and RECORDED (T-33/T-29/T-34 all depend
            # on T-32 and land in later waves than T-35, per tasks.md).
            # Once the module lands, this same assertion starts verifying
            # its import-and-call automatically — nothing here needs an
            # edit.
            pytest.xfail(
                reason=(
                    f"{check_name}: {relative_path} does not exist yet "
                    f"(its owning task has not landed as of T-35, "
                    f"tasks.md wave ordering — NOT a defect in this test)"
                )
            )

        source = full_path.read_bytes().decode("utf-8")
        imports_it, calls_it = self._imports_and_calls_require_non_empty_scope(source)
        assert imports_it, (
            f"{relative_path} does not import require_non_empty_scope / " f"scope_floor"
        )
        assert calls_it, (
            f"{relative_path} imports the floor but never calls "
            f"require_non_empty_scope(...) before reporting its verdict"
        )

    def test_all_four_d15_checks_are_enumerated(self) -> None:
        # Pins the denominator of the parametrised test above so a future
        # edit cannot silently drop a module from the enumeration.
        assert len(_EXPECTED_CHECK_MODULES) == 4
        assert set(_EXPECTED_CHECK_MODULES) == {
            "check-a-registry-to-reality",
            "check-b-registry-to-guide",
            "check-c-en-es-lockstep",
            "check-d-gesture-proof-links",
        }


class TestScopeFloorModuleIsQtFree:
    def test_no_qt_import_in_scope_floor_source(self) -> None:
        source = Path(scope_floor.__file__).read_bytes().decode("utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("PySide6", "PyQt5", "PyQt6"))
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    ("PySide6", "PyQt5", "PyQt6")
                )


# --------------------------------------------------------------------------- #
# property-based tests                                                        #
# --------------------------------------------------------------------------- #


@given(examined=st.integers(min_value=1, max_value=1_000_000))
def test_any_positive_examined_count_passes_silently(examined: int) -> None:
    assert require_non_empty_scope("prop-check", examined, of="rows") is None


@given(examined=st.integers(max_value=0))
def test_any_non_positive_examined_count_raises_empty_scope(examined: int) -> None:
    with pytest.raises(ScopeFloorError) as excinfo:
        require_non_empty_scope("prop-check", examined, of="rows")
    assert excinfo.value.error == "empty-scope"


@given(check_name=st.text(min_size=1, max_size=30), of=st.text(min_size=1, max_size=30))
def test_error_always_echoes_check_name_and_of(check_name: str, of: str) -> None:
    with pytest.raises(ScopeFloorError) as excinfo:
        require_non_empty_scope(check_name, 0, of=of)
    assert excinfo.value.check_name == check_name
    assert excinfo.value.of == of
