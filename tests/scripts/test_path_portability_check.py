"""Contract tests for ``scripts/path_portability_check.py`` (ADR-0047 tranche 2).

Contract asserted here, taken verbatim from the script's own header::

    ENTRYPOINT: python scripts/path_portability_check.py [--root .]
                [--include pixelart_creator scripts tests]
    OUTPUTS: stdout: JSON {"findings":[{file,line,kind,text}], "scanned":N}.
    EXIT CODES: 0 clean -> COMPLETED ; 1 findings -> FAILED (blocks "done") ;
        2 error -> BLOCKED.

Every fixture is a hand-built tiny package tree written under ``tmp_path`` and
passed to the script via its own ``--root``/``--include`` flags. The real
``pixelart_creator``/``scripts``/``tests`` trees are never scanned by these
tests.

FINDING (reported, not silently absorbed): the script's own in-source comment
(lines ~54-65, dated 2026-08-02) cites ``tests/deploy/test_path_portability_
check.py`` as already covering the regex-pattern-argument false-positive
exemption "see tests/deploy/test_path_portability_check.py for both
directions". That file does not exist anywhere in this working tree (verified
by directory listing of ``tests/deploy/`` this session: it holds
``__init__.py``, ``conftest.py``, ``test_nginx_wss_localhost.py``,
``test_run_ci_router.py`` and ``test_vps_localhost.py`` -- no
``test_path_portability_check.py``). The exemption behaviour the comment
describes is real (see ``test_regex_pattern_argument_is_exempt_from_the_
backslash_check`` below) -- only the citation to a pre-existing test module is
stale/incorrect, and this tranche is what actually first covers it.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import run_script

SCRIPT = "path_portability_check.py"


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# The essential pair: a clean tree exits 0, a deliberately broken tree exits 1.
# --------------------------------------------------------------------------- #
def test_clean_tree_exits_0(tmp_path):
    root = tmp_path / "repo"
    _write(
        root,
        "pkg/clean.py",
        'import os\n\nX = os.path.join("a", "b")\n',
    )

    result = run_script(SCRIPT, ["--root", str(root), "--include", "pkg"])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []
    assert payload["scanned"] == 1


def test_broken_tree_exits_1_with_three_kinds_of_finding(tmp_path):
    """Deliberately broken fixture: one file carrying all three literal-path
    defects the header names -- a Windows drive-letter absolute path, a
    hardcoded POSIX absolute root, and a bare backslash-separated literal --
    plus one exempted regex-pattern literal and one ``# portability: ok``
    marked line, both of which must NOT appear in ``findings``."""
    root = tmp_path / "repo"
    _write(
        root,
        "pkg/broken.py",
        "\n".join(
            [
                'DRIVE = "C:\\\\Users\\\\bob\\\\logs"',
                'POSIX = "/home/bob/file"',
                'BACKSLASH = "assets\\\\icons\\\\a.png"',
                "import re",
                'PATTERN = re.compile(r"[A-Za-z0-9_\\-]+")',  # portability: ok
                'MARKED = "weird\\\\path"  # portability: ok',
                "",
            ]
        ),
    )

    result = run_script(SCRIPT, ["--root", str(root), "--include", "pkg"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    kinds = [f["kind"] for f in payload["findings"]]
    assert kinds == [
        "drive-letter-absolute-path",
        "hardcoded-posix-absolute-path",
        "backslash-separator-in-literal",
    ]
    assert payload["findings"][0]["line"] == 1
    assert payload["findings"][0]["text"] == "C:\\Users\\bob\\logs"  # portability: ok
    assert payload["findings"][1]["line"] == 2
    assert payload["findings"][2]["line"] == 3


def test_regex_pattern_argument_is_exempt_from_the_backslash_check(tmp_path):
    """The AST-position-scoped exemption (module comment, ~line 50-65): a
    string passed as the ``pattern`` argument of ``re.compile``/``re.match``/
    etc must NOT be flagged even though it contains an escaped hyphen that
    reads like ``word`` + backslash + ``word`` to ``BACKSLASH_SEP``."""
    root = tmp_path / "repo"
    _write(
        root,
        "pkg/only_regex.py",
        'import re\n\nPATTERN = re.compile(r"[A-Za-z0-9_\\-]+")\n',  # portability: ok
    )

    result = run_script(SCRIPT, ["--root", str(root), "--include", "pkg"])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []


def test_marked_line_is_skipped(tmp_path):
    root = tmp_path / "repo"
    _write(
        root,
        "pkg/marked.py",
        'MARKED = "weird\\\\path"  # portability: ok\n',
    )

    result = run_script(SCRIPT, ["--root", str(root), "--include", "pkg"])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []


# --------------------------------------------------------------------------- #
# BLOCKED path (exit 2): missing root, unparseable module.
# --------------------------------------------------------------------------- #
def test_missing_root_exits_2(tmp_path):
    missing = tmp_path / "does-not-exist"
    result = run_script(SCRIPT, ["--root", str(missing)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "root-not-found"


def test_unparseable_module_exits_2(tmp_path):
    root = tmp_path / "repo"
    _write(root, "pkg/broken_syntax.py", "def f(:\n    pass\n")

    result = run_script(SCRIPT, ["--root", str(root), "--include", "pkg"])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert "error" in payload


# --------------------------------------------------------------------------- #
# Structured-output contract: --include controls scan scope.
# --------------------------------------------------------------------------- #
def test_include_flag_limits_the_scan_to_named_subdirs(tmp_path):
    root = tmp_path / "repo"
    _write(root, "scanned/in_scope.py", 'X = "/home/bob/file"\n')
    _write(root, "ignored/out_of_scope.py", 'Y = "/home/bob/other"\n')

    result = run_script(SCRIPT, ["--root", str(root), "--include", "scanned"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["scanned"] == 1
    assert [f["file"] for f in payload["findings"]] == ["scanned/in_scope.py"]
