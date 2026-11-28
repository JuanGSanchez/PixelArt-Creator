"""Shared support for the soft-line-break tests. No Qt.

This module is a helper, not a test module: its name does not start with
``test_`` so pytest does not collect it. It holds four things that both
``test_guide_softbreak.py`` and ``test_guide_softbreak_tables.py`` need:

* the loader of the module under test, which can be pointed at a mutated copy
  (the broken-copy proof, ``_softbreak_mutants.py``) through the environment
  variable ``SOFTBREAK_MUTANT_FILE``;
* a reference oracle for the rule, written straight from the spec's clause list
  (the specification's clause list) and from properties that do not come from the
  module's own tables: East Asian Width and the general category from
  ``unicodedata``, the Script property from ``fontTools.unicodedata``;
* the discovery of the GIT-TRACKED guide trees and the floor guard
  (a tree that ships must never be skipped);
* the temporary git repository of the planted-tree control.

Nothing here reads or writes the product tree except by ``git ls-files`` and by
reading tracked pages.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from fontTools import unicodedata as _ft_unicodedata

MODULE_NAME = "pixelart_creator.logic.guide_softbreak"
MUTANT_ENV = "SOFTBREAK_MUTANT_FILE"

#: The product repository under test (the folder that holds ``pixelart_creator``).
REPO_ROOT = Path(__file__).resolve().parents[3]

#: The guide trees, relative to the product repository's root.
TREE_REL = "pixelart_creator/userguide_content/content"

#: The eight guide languages and their two families.
ALL_LOCALES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "ko", "ja", "zh_CN")
NON_CJK_LOCALES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "ko")
CJ_LOCALES: Tuple[str, ...] = ("ja", "zh_CN")

#: The pages of the discovery are Markdown pages only.
PAGE_SUFFIX = ".md"

ZWSP = "​"


# --------------------------------------------------------------------------
# The module under test (optionally a mutated copy)
# --------------------------------------------------------------------------


def load_softbreak() -> ModuleType:
    """Return the module under test.

    With ``SOFTBREAK_MUTANT_FILE`` set, the file at that path is executed as
    ``pixelart_creator.logic.guide_softbreak`` and registered under that name, so
    the whole suite runs against the broken copy. Otherwise the real module is
    imported. A mutated copy is loaded once per process.
    """
    override = os.environ.get(MUTANT_ENV)
    if not override:
        return importlib.import_module(MODULE_NAME)
    path = str(Path(override).resolve())
    existing = sys.modules.get(MODULE_NAME)
    if existing is not None and getattr(existing, "__file__", None) == path:
        return existing
    spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def module_source_path(module: ModuleType) -> Path:
    """Return the file the loaded module came from."""
    return Path(str(module.__file__))


# --------------------------------------------------------------------------
# The reference oracle (from the spec, not from the module)
# --------------------------------------------------------------------------

#: Characters that carry the Unicode property Emoji, used by the oracle for the
#: characters the property tests draw. The list is a fixed sample: every member
#: is Emoji=Yes in emoji-data.txt 15.1.0 (the ASCII ones, the copyright, the
#: trademark and the double exclamation mark are the research finding's own
#: verbatim lines). A character outside this set is a non-member for the oracle,
#: so the property tests draw only characters whose status is known by design.
EMOJI_ORACLE: frozenset = frozenset(
    "\U0001f600\U0001f601\U0001f389\U0001f680"  # 😀 😁 🎉 🚀
    "✨⭐⌚☀❤ℹ"  # ✨ ⭐ ⌚ ☀ ❤ ℹ
    "©®™‼⁉"  # © ® ™ ‼ ⁉
    "#*0123456789"
)


def eaw(char: str) -> str:
    """East Asian Width of ``char`` in the running interpreter's database."""
    return unicodedata.east_asian_width(char)


def is_hangul(char: str) -> bool:
    """Script=Hangul, from fontTools (an independent source)."""
    return _ft_unicodedata.script(char) == "Hang"


def is_latin_letter(char: str) -> bool:
    """General category L and Script=Latin."""
    return (
        unicodedata.category(char).startswith("L")
        and _ft_unicodedata.script(char) == "Latn"
    )


def is_decimal_digit(char: str) -> bool:
    """General category Nd."""
    return unicodedata.category(char) == "Nd"


def effective_width(char: str) -> str:
    """Width for clauses 2 and 3: an Emoji of width W or N counts as A."""
    width = eaw(char)
    if char in EMOJI_ORACLE and width in ("W", "N"):
        return "A"
    return width


def _fwh_not_hangul(char: str) -> bool:
    return effective_width(char) in ("F", "W", "H") and not is_hangul(char)


def _ambiguous_punct_or_symbol(char: str) -> bool:
    return unicodedata.category(char)[0] in ("P", "S") and effective_width(char) == "A"


def oracle_clause(
    before: str,
    after: str,
    language: str,
    *,
    marks: Sequence[str] = ("、", "。"),
    clause3_languages: Iterable[str] = CJ_LOCALES,
    clause4_languages: Iterable[str] = CJ_LOCALES,
) -> int:
    """Return the number (1 to 5) of the spec clause that decides the pair."""
    if before == ZWSP or after == ZWSP:
        return 1
    if (
        effective_width(before) in ("F", "W", "H")
        and effective_width(after) in ("F", "W", "H")
        and not is_hangul(before)
        and not is_hangul(after)
    ):
        return 2
    if language in tuple(clause3_languages):
        if (_ambiguous_punct_or_symbol(before) and _fwh_not_hangul(after)) or (
            _ambiguous_punct_or_symbol(after) and _fwh_not_hangul(before)
        ):
            return 3
    if language in tuple(clause4_languages):
        for mark_side, other in ((before, after), (after, before)):
            if mark_side in marks and (
                is_latin_letter(other) or is_decimal_digit(other)
            ):
                return 4
    return 5


# --------------------------------------------------------------------------
# The tracked guide trees
# --------------------------------------------------------------------------


class GitListingError(RuntimeError):
    """``git`` could not list the tracked pages (no repository, or no ``git``)."""


def _git_env(extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    if extra:
        env.update(extra)
    return env


def git_tracked_pages(
    root: Path,
    locale: str,
    *,
    git: str = "git",
    env: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Return the git-tracked ``.md`` pages of ``locale``, as paths under ``root``.

    Uses ``git ls-files -z -- <TREE_REL>/<locale>/`` at ``root``. Raises
    :class:`GitListingError` when git cannot list (no repository, no ``git``).
    """
    try:
        done = subprocess.run(
            [git, "-C", str(root), "ls-files", "-z", "--", f"{TREE_REL}/{locale}/"],
            capture_output=True,
            check=False,
            env=_git_env(env),
        )
    except OSError as error:
        raise GitListingError(
            f"cannot list the git-tracked guide pages: git could not run ({error})"
        ) from error
    if done.returncode != 0:
        stderr = done.stderr.decode("utf-8", "replace").strip()
        raise GitListingError(
            f"cannot list the git-tracked guide pages: git ls-files exited "
            f"{done.returncode} ({stderr})"
        )
    names = [n for n in done.stdout.decode("utf-8").split("\0") if n]
    return sorted(n for n in names if n.endswith(PAGE_SUFFIX))


def tracked_trees(root: Path, **kwargs) -> Dict[str, List[str]]:
    """Map each of the eight locales to its tracked pages (possibly empty)."""
    return {loc: git_tracked_pages(root, loc, **kwargs) for loc in ALL_LOCALES}


def untracked_present(root: Path, tracked: Mapping[str, Sequence[str]]) -> List[str]:
    """Return the locales whose folder holds pages on disk but none tracked."""
    out = []
    for loc in ALL_LOCALES:
        folder = root / TREE_REL / loc
        if not tracked.get(loc) and folder.is_dir():
            if any(p.suffix == PAGE_SUFFIX for p in folder.rglob("*")):
                out.append(loc)
    return out


def guard_problems(
    tracked: Mapping[str, Sequence[str]],
    non_cjk_trees: Sequence[str],
    cj_trees: Sequence[str],
) -> List[str]:
    """Return the problems of the floors; empty means the guard passes.

    A locale is listed if and only if its tree is tracked and non-empty, and it
    is listed in the tuple of its own family. Every message names the locale.
    """
    problems: List[str] = []
    for loc in non_cjk_trees:
        if loc not in NON_CJK_LOCALES:
            problems.append(
                f"{loc}: listed in REQUIRED_NON_CJK_TREES "
                "but it is not a non-CJK locale"
            )
    for loc in cj_trees:
        if loc not in CJ_LOCALES:
            problems.append(
                f"{loc}: listed in REQUIRED_CJ_TREES but it is not ja or zh_CN"
            )
    for loc in ALL_LOCALES:
        has = bool(tracked.get(loc))
        own = "REQUIRED_CJ_TREES" if loc in CJ_LOCALES else "REQUIRED_NON_CJK_TREES"
        own_tuple = cj_trees if loc in CJ_LOCALES else non_cjk_trees
        other_tuple = non_cjk_trees if loc in CJ_LOCALES else cj_trees
        if has and loc not in own_tuple and loc not in other_tuple:
            problems.append(
                f"{loc}: the tree is tracked ({len(tracked[loc])} pages) "
                f"but {loc} is not in {own}"
            )
        if not has and (loc in own_tuple or loc in other_tuple):
            problems.append(
                f"{loc}: listed in a REQUIRED_* tuple "
                f"but no tracked non-empty {loc} tree exists"
            )
    return problems


def read_page(root: Path, relative: str) -> str:
    """Read a tracked page as UTF-8, with no newline translation."""
    return (root / relative).read_bytes().decode("utf-8")


# --------------------------------------------------------------------------
# The planted-tree control: a temporary git repository
# --------------------------------------------------------------------------


def scratch_base(fallback: Optional[Path] = None) -> Path:
    """The folder the suite configures for temporary files (``ORCH_TEST_TMP``)."""
    root = os.environ.get("ORCH_TEST_TMP")
    if root:
        base = Path(root) / "softbreak-tests"
        base.mkdir(parents=True, exist_ok=True)
        return base
    if fallback is not None:
        return fallback
    return Path(tempfile.gettempdir())


def make_scratch(fallback: Optional[Path] = None) -> Path:
    """Create a private folder under the configured temp root."""
    return Path(tempfile.mkdtemp(prefix="sb-", dir=str(scratch_base(fallback))))


def remove_scratch(folder: Path) -> None:
    """Delete a folder made by :func:`make_scratch`, read-only git objects included."""

    def _retry(func: Callable, path: str, _exc) -> None:
        os.chmod(path, 0o700)
        func(path)

    shutil.rmtree(folder, onexc=_retry)


def planted_git_env(folder: Path) -> Dict[str, str]:
    """Environment that isolates a planted repository from every git config."""
    return {
        "GIT_CONFIG_GLOBAL": str(folder / "no-global-gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(folder.parent),
    }


def _run_git(root: Path, env: Mapping[str, str], *args: str) -> None:
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
        env=_git_env(env),
    )
    if done.returncode != 0:
        raise RuntimeError(
            f"planted-repository setup failed: git {' '.join(args)}: "
            f"{done.stderr.decode('utf-8', 'replace')}"
        )


def make_planted_repo(folder: Path) -> Tuple[Path, Dict[str, str]]:
    """Build the control repository: ``ja`` committed, ``zh_CN`` untracked.

    Returns the repository root and the git environment to use with it.
    """
    root = folder / "repo"
    root.mkdir()
    env = planted_git_env(folder)
    _run_git(root, env, "-c", "init.defaultBranch=main", "init", "-q")
    ja = root / TREE_REL / "ja" / "a.md"
    ja.parent.mkdir(parents=True)
    ja.write_bytes("日本\n語\n".encode("utf-8"))
    _run_git(root, env, "add", "--", f"{TREE_REL}/ja/a.md")
    _run_git(
        root,
        env,
        "-c",
        "user.name=planted-control",
        "-c",
        "user.email=planted-control@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "planted",
    )
    zh = root / TREE_REL / "zh_CN" / "b.md"
    zh.parent.mkdir(parents=True)
    zh.write_bytes("图层\n面板\n".encode("utf-8"))
    return root, env
