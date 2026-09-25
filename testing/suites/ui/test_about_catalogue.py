"""Catalogue-completeness test for REQ-AV-BUILD-001 (SC-AV-BUILD-001-1).

Per the feature's task breakdown: every new (context,
source) message pair this feature introduced into ``pixelart_creator/ui/`` must be
present in BOTH ``.ts`` catalogues, carry a finished Spanish translation
that differs from its English source (except a declared value-string
carve-out, currently empty -- see ``_VALUE_STRING_EXCEPTIONS`` below), and
be served by the COMPILED ``pixelart_es.qm`` through a real
``QTranslator``.

**How "new" is derived (never typed, and never a git diff).** Two sources,
both found by AST, both read with an EXPLICIT ``encoding="utf-8"``:

1. Every (context, source) pair in ``about_dialog.py``'s CURRENT AST
   (context = the innermost enclosing class name -- this is how
   ``pyside6-lupdate`` scopes a context, confirmed against the shipped
   catalogue: e.g. every existing ``Main_Window`` message lives under
   context name ``Main_Window``, not "MainWindow"). The WHOLE file counts,
   because the whole file is new (the pre-feature commit ``a77b5c0`` has no
   such path at all -- ``git show a77b5c0:pixelart_creator/ui/about_dialog.py``
   -> ``fatal: path ... exists on disk, but not in 'a77b5c0'``, verified once).
2. The single (context, source) pair for the pre-existing ``Main_Window``
   context's About action, found NARROWLY by ``_AboutActionTextCollector``
   -- the one ``self._about_action.setText(self.tr(...))`` call -- rather
   than by diffing the whole of ``main_window.py`` against any base commit.

**A whole-file diff against a base commit was the ORIGINAL method here and
was replaced** (measured failure, Windows CI, 2026-09-25): reading a base
commit's content via ``git show <commit>:<path>`` through
``subprocess.run(..., text=True)`` with no explicit ``encoding=`` decodes
with the PLATFORM'S preferred encoding, which is ``cp1252`` on that runner,
not UTF-8. ``main_window.py`` carries a pre-existing, unrelated
``self.tr("Floyd–Steinberg")`` call (an en dash, U+2013, encoded in git
history as the UTF-8 bytes ``\xe2\x80\x93``); decoded as ``cp1252`` that
becomes the mojibake string ``"Floydâ€“Steinberg"``, which
does not equal the CURRENT tree's correctly-``utf-8``-decoded
``"Floyd–Steinberg"`` -- so the diff-based method saw the (unchanged,
byte-identical-at-both-commits, unrelated) pair as "new" and pulled it into
this feature's set. The AST-only method above depends on no subprocess call,
no git history, and no locale-dependent decoding at all -- only the CURRENT
source tree, read explicitly as UTF-8, plus the ONE-TIME-VERIFIED fact that
``about_dialog.py`` did not exist at ``a77b5c0`` (a fact about the file's
own history, not a repeated diff of its content) and that the About action's
``setText`` call is the feature's only addition to ``Main_Window``.

Verified once by an ephemeral probe (2026-09-24, discarded; re-confirmed
2026-09-25 against the AST-only method): 19 pairs are new -- 18 under
``about_dialog.py``'s ``About_Dialog`` context and 1 under the existing
``Main_Window`` context (``&About PixelArt Creator``).
``pixelart_creator/ui/theme.py`` is not walked at all any more (it
contributed 0 under the old method too: ``link_colour`` returns a
``QColor``, it wraps no user-visible string).

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
_I18N_DIR = _PKG_DIR / "i18n"

#: The two source files the deterministic, AST-only derivation reads --
#: never a git diff, never any other commit (module docstring).
_ABOUT_DIALOG_PATH = _PKG_DIR / "ui" / "about_dialog.py"
_MAIN_WINDOW_PATH = _PKG_DIR / "ui" / "main_window.py"

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


class _AboutActionTextCollector(ast.NodeVisitor):
    """Find the single ``self._about_action.setText(self.tr(<source>))``
    call and record its (enclosing class name, source) pair.

    Deliberately NARROW, unlike ``_TrCollector`` (which the ``about_dialog.py``
    sweep uses to collect EVERY ``tr()`` call in that whole-new file): this
    visitor matches only the one call chain that sets the About action's
    text, because that is this feature's only contribution to the
    pre-existing ``Main_Window`` context, and identifying it this way needs
    no diff against any other commit (module docstring).
    """

    def __init__(self) -> None:
        self._class_stack: List[str] = []
        self.pair: Optional[Tuple[str, str]] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        fn = node.func
        is_about_action_set_text = (
            isinstance(fn, ast.Attribute)
            and fn.attr == "setText"
            and isinstance(fn.value, ast.Attribute)
            and fn.value.attr == "_about_action"
        )
        if is_about_action_set_text and node.args and self._class_stack:
            arg = node.args[0]
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and arg.func.attr in _TR_FUNCS
                and arg.args
                and isinstance(arg.args[0], ast.Constant)
                and isinstance(arg.args[0].value, str)
            ):
                self.pair = (self._class_stack[-1], arg.args[0].value)
        self.generic_visit(node)


def _about_action_pair(source_text: str) -> Tuple[str, str]:
    """Return the one (context, source) pair for ``Main_Window``'s About
    action, found by ``_AboutActionTextCollector`` (never a diff)."""
    collector = _AboutActionTextCollector()
    collector.visit(ast.parse(source_text))
    assert collector.pair is not None, (
        "no self._about_action.setText(self.tr(...)) call found in "
        f"{_MAIN_WINDOW_PATH} -- the About action's text-setting call moved "
        "or was renamed; update _AboutActionTextCollector to match"
    )
    return collector.pair


def _new_pairs() -> List[Tuple[str, str]]:
    """Deterministic, git-free derivation (module docstring: "How 'new' is
    derived"). Every pair in ``about_dialog.py``'s current AST (the whole
    file is new) plus the one About-action pair in ``main_window.py``,
    both files read with an explicit ``encoding="utf-8"``."""
    about_dialog_pairs = _tr_pairs_in_text(
        _ABOUT_DIALOG_PATH.read_text(encoding="utf-8")
    )
    about_action_pair = _about_action_pair(
        _MAIN_WINDOW_PATH.read_text(encoding="utf-8")
    )
    return sorted(about_dialog_pairs | {about_action_pair})


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

    If the AST derivation above ever finds nothing -- a moved/renamed file,
    a moved ``_about_action`` -- the parametrized tests below would simply
    not be collected, which is a silent, not a failing, non-result. This
    assertion makes that failure loud instead. 19 pairs were measured for
    this task (see module docstring); the assertion is deliberately looser
    (>0) so it does not itself go stale if a later change in this same slice
    adds one more string before the catalogues are extracted.
    """
    assert len(_NEW_PAIRS) > 0, (
        "expected at least one new (context, source) pair from "
        f"{_ABOUT_DIALOG_PATH} and the About action in {_MAIN_WINDOW_PATH} "
        "-- found none; check that both files and the "
        "self._about_action.setText(self.tr(...)) call still exist before "
        "trusting any 'pass' below"
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
