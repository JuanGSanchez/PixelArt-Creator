"""Catalogue-completeness test for REQ-AV-BUILD-001 (SC-AV-BUILD-001-1).

Per ``design-docs/specs/app-version/tasks.md``: every new (context,
source) message pair this feature introduced into ``pixelart_creator/ui/`` must be
present in BOTH ``.ts`` catalogues, carry a finished Spanish translation
that differs from its English source (except a declared value-string
carve-out, currently empty -- see ``_VALUE_STRING_EXCEPTIONS`` below), and
be served by the COMPILED ``pixelart_es.qm`` through a real
``QTranslator``.

**How "new" is derived (never typed).** A pair is new if it is produced by
an AST walk of a UI file this feature touched, using its CURRENT tr()/translate()/
trUtf8() literal calls (context = the innermost enclosing class name --
this is how ``pyside6-lupdate`` scopes a context, confirmed against the
shipped catalogue: e.g. every existing ``Main_Window`` message lives under
context name ``Main_Window``, not "MainWindow") but is ABSENT from that same
AST walk run over the file's content at the pre-feature commit
``a77b5c0`` (the commit the tasks.md red-first rule pins every red run
to). This is a pure source diff, not a hand-typed list, and it stays valid
once the catalogues are extracted: it depends only on git history (fixed) and the current source
tree, never on the ``.ts`` files' own state -- so it does not silently
collapse to zero once localisation extracts these strings.

Verified once by an ephemeral probe (2026-09-24, discarded): 19 pairs are
new -- 18 under a fresh ``About_Dialog`` context (the whole file is new at
``a77b5c0``: ``git show a77b5c0:pixelart_creator/ui/about_dialog.py`` ->
``fatal: path ... exists on disk, but not in 'a77b5c0'``) and 1 under the
existing ``Main_Window`` context (``&About PixelArt Creator``).
``pixelart_creator/ui/theme.py`` contributes 0: ``link_colour`` returns a
``QColor``, it wraps no user-visible string.

**Red-first (NFR-5).** Run before the tree with the new UI code has its
catalogues extracted: at that point in the workflow the ``About_Dialog`` context does
not exist in either ``.ts`` file (baseline, measured in binary 2026-09-24,
plan.md §4: ``pixelart_en.ts`` 1276 messages / 0 CRLF, ``pixelart_es.ts``
1282 messages / 0 CRLF -- re-measured identically at that stage), and the ``Main_Window`` source ``"&About PixelArt Creator"`` is
absent from the catalogue too. So every new pair fails presence, and
nothing can be finished-translated or ``.qm``-served that was never
extracted. Expected to turn green once the catalogues are extracted and translated (that
step's own done-when names this file's assertions explicitly).
"""

from __future__ import annotations

import ast
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytest
from PySide6.QtCore import QLocale, QTranslator

import pixelart_creator
from pixelart_creator.ui.i18n import _default_translations_dir


@pytest.fixture(autouse=True)
def _english_start_language():
    """Force ``QLocale.system()`` to resolve to English before every test.

    This module builds no ``Main_Window`` and loads ``pixelart_es.qm``
    directly via a standalone ``QTranslator`` (never through
    ``LanguageManager.install_from_locale()``), so none of its own
    assertions currently depend on the host OS locale. The fixture is added
    anyway, matching the other three sibling UI test files (``test_about_dialog.py``,
    ``test_window_title_version.py``, ``test_i18n_qt_base.py``) and this
    suite's own ``conftest.py`` patch, so the whole slice of tests is
    uniformly, explicitly locale-independent (F11 / portability) rather than
    leaving one file's independence implicit.
    """
    QLocale.system = staticmethod(  # type: ignore[method-assign]
        lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    )
    yield


_PKG_DIR = Path(pixelart_creator.__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent
_I18N_DIR = _PKG_DIR / "i18n"

#: The pre-feature commit every red-first run in this workflow is pinned to
#: (tasks.md header table, "Red-first rule").
_BASE_COMMIT = "a77b5c0"

#: The ui/ files this feature touched ("Files touched").
_CHANGED_UI_FILES = ("about_dialog.py", "main_window.py", "theme.py")

_TR_FUNCS = {"tr", "translate", "trUtf8"}

#: Value strings (CL-AV-5) that legitimately translate to themselves -- none
#: of this round's new pairs are one, but the carve-out plan.md/tasks.md
#: names ("except value strings") is declared here rather than silently
#: assumed away.
_VALUE_STRING_EXCEPTIONS: Set[str] = set()


class _TrCollector(ast.NodeVisitor):
    """Collect (context, source) the way ``pyside6-lupdate`` scopes a
    context: the innermost enclosing class name, for every plain
    string-literal first argument of a ``tr``/``translate``/``trUtf8``
    call."""

    def __init__(self) -> None:
        self._class_stack: List[str] = []
        self.pairs: Set[Tuple[str, str]] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        fn = node.func
        called = None
        if isinstance(fn, ast.Attribute) and fn.attr in _TR_FUNCS:
            called = fn.attr
        elif isinstance(fn, ast.Name) and fn.id in _TR_FUNCS:
            called = fn.id
        if called is not None and self._class_stack and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.pairs.add((self._class_stack[-1], first.value))
        self.generic_visit(node)


def _tr_pairs_in_text(source_text: str) -> Set[Tuple[str, str]]:
    collector = _TrCollector()
    collector.visit(ast.parse(source_text))
    return collector.pairs


def _read_at_base_commit(rel_posix_path: str) -> Optional[str]:
    """Return the file's content at ``_BASE_COMMIT``, or ``None`` if the
    file did not exist there yet (a new file: every one of its pairs counts
    as new)."""
    result = subprocess.run(
        ["git", "show", f"{_BASE_COMMIT}:{rel_posix_path}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _new_pairs() -> List[Tuple[str, str]]:
    new_pairs: Set[Tuple[str, str]] = set()
    for filename in _CHANGED_UI_FILES:
        path = _PKG_DIR / "ui" / filename
        rel_posix = path.relative_to(_REPO_ROOT).as_posix()
        current_pairs = _tr_pairs_in_text(path.read_text(encoding="utf-8"))
        old_text = _read_at_base_commit(rel_posix)
        old_pairs = _tr_pairs_in_text(old_text) if old_text is not None else set()
        new_pairs |= current_pairs - old_pairs
    return sorted(new_pairs)


def _ts_index(path: Path) -> Dict[Tuple[str, str], ET.Element]:
    """Map every (context, source) in a ``.ts`` file to its ``<message>``
    element."""
    root = ET.parse(path).getroot()
    index: Dict[Tuple[str, str], ET.Element] = {}
    for context_el in root.findall("context"):
        name_el = context_el.find("name")
        if name_el is None or name_el.text is None:
            continue
        for message_el in context_el.findall("message"):
            source_el = message_el.find("source")
            if source_el is None or source_el.text is None:
                continue
            index[(name_el.text, source_el.text)] = message_el
    return index


_NEW_PAIRS = _new_pairs()
_NEW_PAIR_IDS = [f"{ctx}::{src[:40]}" for ctx, src in _NEW_PAIRS]


def test_new_pairs_were_discovered_from_source() -> None:
    """Guard against a silently-empty parametrize (no-silent-result).

    If the AST/git diff above ever finds nothing -- a broken ``git show``,
    a moved file -- the parametrized tests below would simply not be
    collected, which is a silent, not a failing, non-result. This assertion
    makes that failure loud instead. 19 pairs were measured for this task
    (see module docstring); the assertion is deliberately looser (>0) so it
    does not itself go stale if a later change in this same slice adds one
    more string before the catalogues are extracted.
    """
    assert len(_NEW_PAIRS) > 0, (
        "expected at least one new (context, source) pair from "
        f"{_CHANGED_UI_FILES}; the AST/git diff against {_BASE_COMMIT} "
        "found none -- check git history and file paths before trusting "
        "any 'pass' below"
    )


@pytest.mark.parametrize("pair", _NEW_PAIRS, ids=_NEW_PAIR_IDS)
def test_sc_av_build_001_1_new_pair_in_both_catalogues(pair: Tuple[str, str]) -> None:
    """SC-AV-BUILD-001-1: every new pair this feature introduced is in both .ts files.

    ``before ⊆ after`` (REQ-AV-BUILD-001, NFR-6) demands the pair be
    present in ``pixelart_en.ts`` AND ``pixelart_es.ts`` once extraction has
    run; before extraction (this run) it demands the pair be ABSENT, and
    this is the assertion that shows the red failure.
    """
    context, source = pair
    en_index = _ts_index(_I18N_DIR / "pixelart_en.ts")
    es_index = _ts_index(_I18N_DIR / "pixelart_es.ts")
    assert (context, source) in en_index, (
        f"({context!r}, {source!r}) is not in pixelart_en.ts -- not yet "
        "extracted (expected before extraction; extraction must add it)"
    )
    assert (context, source) in es_index, (
        f"({context!r}, {source!r}) is not in pixelart_es.ts -- not yet "
        "extracted (expected before extraction; extraction must add it)"
    )


@pytest.mark.parametrize("pair", _NEW_PAIRS, ids=_NEW_PAIR_IDS)
def test_sc_av_build_001_1_new_pair_es_translation_finished(
    pair: Tuple[str, str],
) -> None:
    """SC-AV-BUILD-001-1: the Spanish translation is finished and real.

    "Finished" means no ``type="unfinished"`` attribute and non-empty text
    (extraction's done-when step 6). It must differ from the English source unless
    the source is a declared value-string exception (CL-AV-5) -- none of
    this round's new pairs are.
    """
    context, source = pair
    es_index = _ts_index(_I18N_DIR / "pixelart_es.ts")
    message_el = es_index.get((context, source))
    assert message_el is not None, (
        f"({context!r}, {source!r}) is not in pixelart_es.ts -- cannot "
        "check its translation (expected before extraction)"
    )
    translation_el = message_el.find("translation")
    assert translation_el is not None, f"no <translation> element for {pair!r}"
    assert translation_el.get("type") != "unfinished", (
        f"the Spanish translation of {pair!r} is still marked "
        'type="unfinished" -- not translated yet (expected before extraction)'
    )
    translated_text = translation_el.text or ""
    assert translated_text != "", (
        f"the Spanish translation of {pair!r} is empty -- not translated "
        "yet (expected before extraction)"
    )
    if source not in _VALUE_STRING_EXCEPTIONS:
        assert translated_text != source, (
            f"the Spanish translation of {pair!r} is identical to its "
            "English source and is not a declared value-string exception"
        )


@pytest.mark.parametrize("pair", _NEW_PAIRS, ids=_NEW_PAIR_IDS)
def test_sc_av_build_001_1_new_pair_served_by_compiled_qm(
    pair: Tuple[str, str], qapp
) -> None:
    """SC-AV-BUILD-001-1: the compiled ``pixelart_es.qm``, loaded by a real
    ``QTranslator``, serves the SAME translation the ``.ts`` carries.

    This is the binding check: a translated ``.ts`` entry that was never
    (re)compiled with ``pyside6-lrelease`` would still fail here, because
    ``QTranslator.translate`` reads the ``.qm``, not the ``.ts``.
    """
    context, source = pair
    es_index = _ts_index(_I18N_DIR / "pixelart_es.ts")
    message_el = es_index.get((context, source))
    assert message_el is not None, (
        f"({context!r}, {source!r}) is not in pixelart_es.ts -- cannot "
        "check the compiled .qm (expected before extraction)"
    )
    translation_el = message_el.find("translation")
    expected = (translation_el.text if translation_el is not None else None) or ""
    assert expected != "", f"no finished .ts translation to compare {pair!r} against"

    translator = QTranslator()
    loaded = translator.load("pixelart_es", str(_default_translations_dir()))
    assert loaded is True, "pixelart_es.qm failed to load"
    served = translator.translate(context, source)
    assert served == expected, (
        f"pixelart_es.qm serves {served!r} for {pair!r}, the .ts carries "
        f"{expected!r} -- the compiled catalogue is stale (re-run "
        "pyside6-lrelease)"
    )
