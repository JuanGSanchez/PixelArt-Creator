# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers of the redraw and visual-reference tests of this root.

The five modules that use it are ``test_redraw_set.py``, ``test_redraw_records.py``,
``test_foreign_fonts.py``, ``test_font_documentation.py`` and
``test_donor_gate_visual_reference.py`` (REQ-L10N-BUILD-010 and REQ-L10N-BUILD-002).
This module holds no test and no typeface name: the visual reference's names come
from the fixture ``fixtures/visual_reference_names.tsv`` and the tools' own constants.

Test seam, the same as ``test_build_nifen_art.py``'s: ``NIFEN_TOOLS_ROOT`` points
every module at a COPY of the layout (``scripts/font``, ``fonts-src``,
``pixelart_creator/fonts``, ``NOTICE``, and a git repository for the two cases that
read ``git ls-files``). It exists so each case can be shown to fail against a broken
copy of the tool it tests; it is unset in normal runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Mapping, NamedTuple, Optional, Sequence

from .conftest import REPO_ROOT

TOOLS_ROOT = Path(os.environ.get("NIFEN_TOOLS_ROOT") or REPO_ROOT).resolve()
FONT_SCRIPTS = TOOLS_ROOT / "scripts" / "font"
CJK_REL = ("fonts-src", "nifen-art-cjk")
CJK_SOURCES = TOOLS_ROOT.joinpath(*CJK_REL)
FONT_DIR = TOOLS_ROOT / "pixelart_creator" / "fonts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NAMES_FIXTURE = FIXTURES / "visual_reference_names.tsv"
BLOCK_FIXTURE = FIXTURES / "visual_reference_block.txt"

#: The product's own scripts that the tests run as real subprocesses.
REDRAW_SET = "redraw_set.py"
REDRAW_RECORDS = "check_redraw_records.py"
FOREIGN_FONTS = "check_foreign_fonts.py"


class Run(NamedTuple):
    """The outcome of one child process."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout + self.stderr


class RepositoryError(AssertionError):
    """A case that needs ``git ls-files`` could not get it.

    It is an ``AssertionError`` on purpose: the case ERRORS (fails) and is never
    skipped, because a skipped -4 or -6 case would read as a pass where nothing was
    examined.
    """


class NameRow(NamedTuple):
    """One row of the visual-reference fixture (a regional build of the reference)."""

    form_set: str
    label: str
    family: str
    style: str
    version: str
    owner: str


def child_env(scratch: Path, extra: Optional[Mapping[str, str]] = None) -> dict:
    """The environment of a child: UTF-8 output, temp folders inside the scratch."""
    proc_tmp = scratch / "proc-tmp"
    proc_tmp.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "TMP": str(proc_tmp),
            "TEMP": str(proc_tmp),
            "TMPDIR": str(proc_tmp),
        }
    )
    env.pop("PYTHONHASHSEED", None)
    if extra:
        env.update(extra)
    return env


def run_font_tool(
    script: str,
    args: Sequence[object],
    scratch: Path,
    *,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: int = 300,
) -> Run:
    """Run ``scripts/font/<script>`` as a real subprocess (its documented entry)."""
    done = subprocess.run(
        [sys.executable, "-B", str(FONT_SCRIPTS / script), *[str(a) for a in args]],
        cwd=str(cwd or TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=child_env(scratch, env),
    )
    return Run(done.returncode, done.stdout, done.stderr)


def load_tool(script: str) -> ModuleType:
    """Import ``scripts/font/<script>`` by path, for its constants, without bytecode."""
    sys.dont_write_bytecode = True
    path = FONT_SCRIPTS / script
    name = "_redraw_tool_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    # A dataclass in the script looks its module up by name while the class is made.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_names() -> List[NameRow]:
    """The rows of the visual-reference fixture, with the header checked."""
    text = NAMES_FIXTURE.read_bytes().decode("utf-8")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    assert lines[0].split("\t") == list(NameRow._fields), lines[0]
    rows = []
    for line in lines[1:]:
        fields = line.split("\t")
        assert len(fields) == len(NameRow._fields), line
        assert all(fields), line
        rows.append(NameRow(*fields))
    assert len(rows) > 0, "the visual-reference fixture holds no row"
    return rows


def read_block() -> str:
    """The notice block of the visual references, as the fixture holds it."""
    return BLOCK_FIXTURE.read_bytes().decode("utf-8")


def tracked_files(root: Path, env: Optional[Mapping[str, str]] = None) -> List[str]:
    """Every path ``git ls-files`` lists under ``root``, in the order git gives.

    Raises ``RepositoryError`` when git cannot run, when ``root`` is not inside a
    repository or when the list is empty: never a skip, never an empty population.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            timeout=120,
            env=dict(os.environ, **(env or {})),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RepositoryError("git ls-files could not run: %s" % exc) from exc
    if done.returncode != 0:
        raise RepositoryError(
            "git ls-files exited %d under %s: %s"
            % (done.returncode, root, done.stderr.decode("utf-8", "replace").strip())
        )
    names = [n.decode("utf-8") for n in done.stdout.split(b"\0") if n]
    if not names:
        raise RepositoryError("git ls-files listed no file under %s" % root)
    return names


def make_repo(folder: Path, files: Mapping[str, object]) -> Path:
    """A scratch git repository whose index holds exactly ``files`` (never committed).

    Used by the cases that need a repository of their own: the root of the real run
    is never changed. ``files`` maps a repository-relative path to its text or bytes.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            content if isinstance(content, bytes) else str(content).encode("utf-8")
        )
    for args in (["init", "-q"], ["add", "-A", "--", "."]):
        done = subprocess.run(
            ["git", "-C", str(folder), "-c", "core.autocrlf=false", *args],
            capture_output=True,
            timeout=120,
        )
        assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    return folder


def data_lines(path: Path) -> List[str]:
    """The lines of a tab-separated product file that are not comments or blank."""
    text = path.read_bytes().decode("utf-8")
    return [
        ln.rstrip("\r")
        for ln in text.split("\n")
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def count_after(text: str, label: str) -> Optional[int]:
    """The integer on a line of ``text`` that reads ``<label>: <integer>`` alone."""
    prefix = label + ":"
    for line in text.split("\n"):
        body = line.strip()
        if body.startswith(prefix) and body[len(prefix) :].strip().isdigit():
            return int(body[len(prefix) :].strip())
    return None


def printed(**counts: object) -> None:
    """Print the figures a case measured, so the run shows them (``-s``)."""
    print(
        "  " + ", ".join("%s %s" % (k.replace("_", " "), v) for k, v in counts.items())
    )
