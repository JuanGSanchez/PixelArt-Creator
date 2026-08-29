"""Contract tests for ``scripts/string_audit_check.py`` (ADR-0047 tranche 2).

Contract asserted here, taken verbatim from the script's own header::

    ENTRYPOINT: python scripts/string_audit_check.py [paths ...]
                [--root pixelart_creator/ui]
    OUTPUTS: stdout: JSON {"findings":[{file,line,kind,text}], "scanned":N}.
    EXIT CODES: 0 clean -> COMPLETED ; 1 findings (report) -> reported to
        AGT-07, maps to PARTIAL for the audited change (report-not-fix) ;
        2 error -> BLOCKED.

Every fixture is a hand-built tiny ``ui/``-shaped tree written under
``tmp_path`` and passed to the script via its own ``--root`` flag (or as
explicit positional paths). The real ``pixelart_creator/ui`` tree is never
scanned by these tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import run_script

SCRIPT = "string_audit_check.py"


def _write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# The essential pair: a clean ui/ tree exits 0, a deliberately broken one
# exits 1 and names AGT-07 in its own stderr summary (report-not-fix, header).
# --------------------------------------------------------------------------- #
def test_clean_tree_exits_0(tmp_path):
    root = tmp_path / "ui"
    _write(
        root,
        "clean_widget.py",
        "class CleanWidget:\n"
        "    def __init__(self):\n"
        '        self.setText(self.tr("Hello"))\n'
        '        self.setWindowTitle(self.tr("Title"))\n',
    )

    result = run_script(SCRIPT, ["--root", str(root)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []
    assert payload["scanned"] == 1


def test_unwrapped_setter_and_tr_concatenation_exit_1(tmp_path):
    """Deliberately broken fixture: one file carrying both defect kinds the
    header/module name -- an unwrapped ``setText`` literal (a user-facing Qt
    setter, per the ``USER_FACING_SETTERS`` set) and a ``tr()`` + ``tr()``
    string concatenation (breaks translated word order) -- plus a clean
    sibling call that must NOT be swept into the findings."""
    root = tmp_path / "ui"
    _write(
        root,
        "broken_widget.py",
        "class BrokenWidget:\n"
        "    def __init__(self):\n"
        '        self.setText("Unwrapped literal")\n'
        '        greeting = self.tr("Hello") + self.tr("World")\n'
        "        self.setToolTip(greeting)\n"
        '        self.setWindowTitle(self.tr("Fine"))\n',
    )

    result = run_script(SCRIPT, ["--root", str(root)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    kinds = [f["kind"] for f in payload["findings"]]
    assert kinds == ["unwrapped-string", "tr-concatenation"]
    assert payload["findings"][0]["line"] == 3
    assert payload["findings"][0]["text"] == "Unwrapped literal"
    assert payload["findings"][1]["line"] == 4


def test_every_user_facing_setter_in_the_declared_set_is_flagged(tmp_path):
    """Read the setter roster from the script's own ``USER_FACING_SETTERS``
    constant (via ``importlib``, matching the ``check_layering`` pattern
    already used in this test root for a ``scripts/*.py`` module with no
    package to import through) -- not a duplicated literal list -- so this
    test tracks the script's actual declared roster instead of silently
    drifting from it."""
    import importlib.util
    import sys as _sys

    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    spec = importlib.util.spec_from_file_location(
        "string_audit_check", scripts_dir / "string_audit_check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    _sys.modules.setdefault("string_audit_check", module)
    spec.loader.exec_module(module)
    setters = sorted(module.USER_FACING_SETTERS)

    root = tmp_path / "ui"
    lines = ["class W:", "    def __init__(self):"]
    for i, setter in enumerate(setters):
        lines.append(f'        self.{setter}("literal-{i}")')
    _write(root, "all_setters.py", "\n".join(lines) + "\n")

    result = run_script(SCRIPT, ["--root", str(root)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["findings"]) == len(setters)


# --------------------------------------------------------------------------- #
# Explicit-paths mode (the ``paths`` positional argument overrides --root).
# --------------------------------------------------------------------------- #
def test_explicit_paths_argument_overrides_root(tmp_path):
    root = tmp_path / "ui"
    in_scope = _write(root, "changed.py", 'self.setText("Loose")\n')
    _write(root, "untouched.py", 'self.setText("Also loose")\n')

    result = run_script(SCRIPT, [str(in_scope)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["scanned"] == 1
    assert len(payload["findings"]) == 1


def test_nonexistent_explicit_path_is_silently_dropped_not_an_error(tmp_path):
    """Documented behaviour, not a header claim: ``collect()`` filters
    ``paths`` through ``os.path.isfile``, so a path that does not exist
    yields zero scanned files and exit 0 -- never a crash and never exit 2."""
    missing = tmp_path / "nope.py"
    result = run_script(SCRIPT, [str(missing)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["scanned"] == 0
    assert payload["findings"] == []


# --------------------------------------------------------------------------- #
# BLOCKED path (exit 2): unparseable module.
# --------------------------------------------------------------------------- #
def test_unparseable_module_exits_2(tmp_path):
    root = tmp_path / "ui"
    _write(root, "broken_syntax.py", "def f(:\n    pass\n")

    result = run_script(SCRIPT, ["--root", str(root)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert "error" in payload
