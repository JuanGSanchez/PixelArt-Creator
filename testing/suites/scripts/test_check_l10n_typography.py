"""Contract tests for ``scripts/check_l10n_typography.py`` (ADR-0047).

Contract asserted here, taken from the script's own header::

    check_l10n_typography.py [--root DIR] [--catalogues DIR] [--guide-root DIR]
                             [--surface catalogue|guide|both] [--languages a,b]
                             [--json]
    check_l10n_typography.py --worklist FILE [--root DIR] [--json]
    EXIT CODES: 0 clean ; 1 a finding, or a rule that applied examined nothing,
        or nothing at all was examined ; 2 an input is missing or unreadable.

Scenarios bound here: SC-L10N-DATA-004-2 (French marks), -3 (no U+202F), -4
(ellipsis), -5 (Korean, no Han), -6 (Simplified Chinese, no full-width marks),
-7 (the French U+00A0 inside the guillemets), -8 (marks and guillemet sides as
two sub-counts of one rule) and -9 (no U+0022 in Russian prose), each on the
surfaces it names, and the ``--worklist`` input that applies the catalogue
rules to a worklist before it is imported.

Method. The script reads the language self-names from
``pixelart_creator/logic/language_names.py`` of the ROOT it is given, and exits
2 on a root without it. So every case builds its own scratch root under
``tmp_path`` that holds a small ``language_names.py`` of its own (an
``ENDONYMS`` mapping with a Han and a Hangul self-name), a catalogue folder and
a guide tree, and passes ``--root``: the module does not depend on the product's
own file being committed, and the tracked catalogues and guide are never read.
Fixtures that depend on a particular space or quotation character are written
with ``\\u`` escapes so the character is visible in the test.

Each REGRESSION CASE drives the script through a clean fixture (exit 0, the
examined count printed) and a failing one (exit 1, the finding and the place
named, JSON parsed by field) and is registered with MUTANTS: copies of the
script, made under ``tmp_path`` together with the catalogue reader it loads from
its own folder, with one guarded line altered so that the rule the case defends
is gone. The module's generic tests run every case against the real script (it
must hold) and against each broken copy (it must raise an ``AssertionError``).
The registry, the scratch-catalogue writer, the worklist builders and the edit
types are imported from the sibling module for ``check_catalogues.py``.

The four Simplified Chinese guide-page rules (a space between Han and a Latin
letter or digit; a space between a full-width mark and a Latin letter, a digit
or a number's symbol; a number written closed against a listed unit; a space
after a number's trailing symbol before Han and before a symbol that opens a
number) read the shown text the way the guide's soft-line-break module reads
it, and the script loads that module from the ROOT it is given. So every
fixture that holds a ``zh_CN`` page gets the module and the constants it
imports copied into its scratch root (:func:`provide_softbreak`). Those rules
exit 1 on a run that reaches the guide surface and finds no ``zh_CN`` page, so
every other guide fixture that expects exit 0 also holds one clean ``zh_CN``
page (:meth:`Tree.chinese_page`).

A verbatim quotation of an interface message is exempt from all four of those
rules (SC-L10N-DATA-004-16, ``REQ-L10N-DATA-004``): the script reads the
``zh_CN`` catalogue of the catalogue folder it is given, and the cases plant the
scenario's four finished messages there (:data:`QUOTE_MESSAGES`), put each of
the scenario's eight lines on a ``zh_CN`` page, and judge the exit code, the
findings and the quotations the report lists with their page, line and source
text, in the JSON and in the text report.
"""

from __future__ import annotations

import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR, ScriptRun
from .test_check_catalogues import (
    CHECK,
    Case,
    Edit,
    Msg,
    Mutant,
    Registry,
    Tools,
    entry,
    mutant,
    put,
    worklist_document,
)

TYPO = "check_l10n_typography.py"
SCRIPT_NAMES = (TYPO, CHECK)
REGISTRY = Registry()

NBSP = "\u00a0"
NNBSP = "\u202f"
ELLIPSIS = "\u2026"
OPEN = "\u00ab"
CLOSE = "\u00bb"

HAN_KAI = "\u958b"
JA_ENDONYM = "\u65e5\u672c\u8a9e"
ZH_ENDONYM = "\u7b80\u4f53\u4e2d\u6587"
KO_ENDONYM = "\ud55c\uad6d\uc5b4"
ENDONYMS = {
    "en": "English",
    "es": "Espa\u00f1ol",
    "fr": "Fran\u00e7ais",
    "de": "Deutsch",
    "ru": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    "zh_CN": ZH_ENDONYM,
    "ja": JA_ENDONYM,
    "ko": KO_ENDONYM,
}
KO_OPEN = "\ud30c\uc77c \uc5f4\uae30"
KO_HANJA = f"\ud30c\uc77c {HAN_KAI}\uae30"
ZH_OPEN = "\u6253\u5f00\u6587\u4ef6"

CAT_DIR = "pixelart_creator/i18n"
GUIDE_DIR = "pixelart_creator/userguide_content/content"
ZH_LANGUAGE = "zh_CN"
#: The product files the soft-line-break module needs beside it in a scratch root.
SOFTBREAK_FILES = ("guide_softbreak.py", "constants.py")
#: A ``zh_CN`` page every Chinese rule reads and none of them objects to.
CLEAN_ZH_PAGE = "# 标题\n\n使用 F1 键。\n"


def ty(old: str, new: str) -> Edit:
    """Build an edit of ``check_l10n_typography.py``."""
    return Edit(TYPO, old, new)


def make_broken(folder: Path, broken: Mutant) -> Tools:
    """Copy the script and its catalogue reader into ``folder``; apply the edits.

    Files are read and written as bytes. An anchor that is not found exactly
    once, or an edit that leaves a script that does not compile, raises: a
    control must fail for the reason it names and for no other.
    """
    folder.mkdir(parents=True)
    for name in SCRIPT_NAMES:
        shutil.copyfile(SCRIPTS_DIR / name, folder / name)
    for item in broken.edits:
        target = folder / item.script
        data = target.read_bytes()
        old, new = item.old.encode("utf-8"), item.new.encode("utf-8")
        if b"\r\n" in data:
            old, new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
        found = data.count(old)
        assert found == 1, f"{broken.label}: anchor found {found}x in {item.script}"
        data = data.replace(old, new)
        compile(data, item.script, "exec")
        target.write_bytes(data)
    return Tools(folder)


# --------------------------------------------------------------------------- #
# The scratch root.
# --------------------------------------------------------------------------- #
class Tree(NamedTuple):
    """A scratch product root holding its own ``language_names.py``."""

    work: Path
    root: Path

    def catalogue(self, code: str, messages: list[Msg], **options) -> Path:
        """Write ``pixelart_<code>.ts`` into the default catalogue folder."""
        return put(self.root, CAT_DIR, code, messages, **options)

    def page(self, language: str, name: str, text: str) -> Path:
        """Write one guide page of ``language`` as UTF-8 bytes.

        A ``zh_CN`` page is read through the soft-line-break module, so the
        first one written also makes that module reachable from the root.
        """
        if language == ZH_LANGUAGE:
            provide_softbreak(self.root)
        path = self.root / GUIDE_DIR / language / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def chinese_page(self) -> Path:
        """Write one clean ``zh_CN`` page, so the Chinese rules have a page to read."""
        return self.page(ZH_LANGUAGE, "companion.md", CLEAN_ZH_PAGE)


def provide_softbreak(root: Path) -> None:
    """Make the product's soft-line-break module importable from a scratch root.

    The script loads ``pixelart_creator/logic/guide_softbreak.py`` by path from
    the root it is given and that module imports the product's constants, so
    both are copied (as bytes) beside empty package markers. A copy of the
    script made elsewhere cannot fall back on the product that holds it, which
    is why the fixture carries its own.
    """
    package = root / "pixelart_creator"
    logic = package / "logic"
    logic.mkdir(parents=True, exist_ok=True)
    for folder in (package, logic):
        marker = folder / "__init__.py"
        if not marker.exists():
            marker.write_bytes(b"")
    for name in SOFTBREAK_FILES:
        target = logic / name
        if not target.exists():
            shutil.copyfile(REPO_ROOT / "pixelart_creator" / "logic" / name, target)


def endonym_module(endonyms: dict[str, str]) -> str:
    """Return the text of a ``language_names.py`` holding ``endonyms``."""
    body = json.dumps(endonyms, indent=4, ensure_ascii=True)
    return f'"""Scratch language self-names."""\n\nENDONYMS = {body}\n'


def build_tree(work: Path, endonyms: dict[str, str] | None = None) -> Tree:
    """Build a scratch root whose ``language_names.py`` holds ``endonyms``.

    ``None`` stands for the standard table of this module. A root without the
    file at all is :func:`bare_tree`.
    """
    root = work / "root"
    path = root / "pixelart_creator" / "logic" / "language_names.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    table = ENDONYMS if endonyms is None else endonyms
    path.write_bytes(endonym_module(table).encode("utf-8"))
    return Tree(work, root)


def bare_tree(work: Path) -> Tree:
    """Build a scratch root WITHOUT ``language_names.py``."""
    root = work / "root"
    root.mkdir(parents=True, exist_ok=True)
    return Tree(work, root)


def scan(tools: Tools, tree: Tree, *args: str) -> tuple[ScriptRun, dict]:
    """Run the check with ``--json`` over ``tree`` and parse the report."""
    run = tools.run(TYPO, ["--root", str(tree.root), *args, "--json"], tree.work)
    try:
        payload = json.loads(run.stdout)
    except ValueError:
        raise AssertionError(
            f"stdout is not JSON: exit {run.returncode}, stdout "
            f"{run.stdout[:300]!r}, stderr {run.stderr[:300]!r}"
        ) from None
    assert isinstance(payload, dict), payload
    assert payload["exit"] == run.returncode, (payload["exit"], run.returncode)
    return run, payload


def text_of(tools: Tools, tree: Tree, *args: str) -> ScriptRun:
    """Run the check without ``--json`` and return the printed report."""
    return tools.run(TYPO, ["--root", str(tree.root), *args], tree.work)


def row(payload: dict, rule: str, surface: str, language: str) -> dict:
    """Return the one report row of a (rule, surface, language) unit."""
    wanted = (rule, surface, language)
    found = [
        r
        for r in payload["rules"]
        if (r["rule"], r["surface"], r["language"]) == wanted
    ]
    assert len(found) == 1, (
        wanted,
        [(r["rule"], r["surface"]) for r in payload["rules"]],
    )
    return found[0]


def has_row(payload: dict, rule: str, surface: str, language: str) -> bool:
    """Return whether the report has a row for a (rule, surface, language) unit."""
    wanted = (rule, surface, language)
    return any(
        (r["rule"], r["surface"], r["language"]) == wanted for r in payload["rules"]
    )


def details(unit: dict) -> list[str]:
    """Return the detail text of every finding of a row, in report order."""
    return [finding["detail"] for finding in unit["findings"]]


def assert_clean(run: ScriptRun, payload: dict) -> None:
    """Assert exit 0, no finding and no rule that examined nothing."""
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert payload["findings_total"] == 0, payload["rules"]
    assert payload["rules_examining_nothing"] == 0, payload["rules"]
    assert payload["examined_total"] > 0


def only_catalogue(
    tools: Tools, work: Path, label: str, code: str, messages: list[Msg], *args: str
) -> tuple[ScriptRun, dict]:
    """Scan a root holding one catalogue and nothing else."""
    tree = build_tree(work / label)
    tree.catalogue(code, messages)
    return scan(tools, tree, *args)


def only_page(
    tools: Tools, work: Path, label: str, language: str, text: str, *args: str
) -> tuple[ScriptRun, dict]:
    """Scan a root holding one guide page of ``language`` and nothing else.

    The Chinese rules fail a guide run that has no ``zh_CN`` page, so a page of
    another language comes with one clean ``zh_CN`` page beside it.
    """
    tree = build_tree(work / label)
    tree.page(language, "index.md", text)
    if language != ZH_LANGUAGE:
        tree.chinese_page()
    return scan(tools, tree, *args)


def line_of(path: Path, char: str) -> int:
    """Return the 1-based line of ``path`` holding ``char``."""
    lines = path.read_bytes().decode("utf-8").split("\n")
    return next(n for n, line in enumerate(lines, 1) if char in line)


# --------------------------------------------------------------------------- #
# French marks, both surfaces (SC-L10N-DATA-004-2).
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "no-space-passes",
        ty(
            "            problems.append((start,"
            ' f"{match.group()!r} has no space before it"))\n',
            "            pass\n",
        ),
    ),
    mutant(
        "ordinary-space-passes",
        ty("        elif before.isspace():\n", "        elif before == NARROW_NBSP:\n"),
    ),
    mutant(
        "narrow-space-unnamed",
        ty(
            '            shown = "U+202F" if before =='
            ' NARROW_NBSP else "an ordinary space"\n',
            '            shown = "an ordinary space"\n',
        ),
    ),
    mutant(
        "correct-mark-not-counted",
        ty(
            "        if before == NBSP:\n            examined += 1\n",
            "        if before == NBSP:\n            pass\n",
        ),
    ),
    mutant("guide-not-scanned", ty('    if lang == "fr":\n', '    if lang == "xx":\n')),
)
def case_french_marks_need_one_no_break_space_on_both_surfaces(
    tools: Tools, work: Path
) -> None:
    """A ``? ! ; :`` after a word needs exactly one U+00A0, on both surfaces.

    SC-L10N-DATA-004-2: the number examined is printed and is non-zero, a
    time such as 12:30 is not a site, and each wrong spacing is named.
    """
    clean = [
        Msg("Open the file?", f"Ouvrir le fichier{NBSP}?"),
        Msg("Layer: %1", f"Calque{NBSP}: %1"),
        Msg("Meet at 12:30", "Rendez-vous \u00e0 12:30"),
    ]
    run, payload = only_catalogue(tools, work, "cat-clean", "fr", clean)
    assert_clean(run, payload)
    unit = row(payload, "fr-nbsp", "catalogue", "fr")
    assert unit["examined"] == 2
    assert unit["sub_counts"] == {"guillemet sides": 0, "marks": 2}
    text = f"# Aide\n\nOuvrir le fichier{NBSP}?\n"
    run, payload = only_page(tools, work, "guide-clean", "fr", text)
    assert_clean(run, payload)
    assert row(payload, "fr-nbsp", "guide", "fr")["examined"] == 1

    wrong = {
        "no space": ("Ouvrir le fichier?", "'?' has no space before it"),
        "ordinary space": (
            "Ouvrir le fichier ?",
            "'?' is preceded by an ordinary space",
        ),
        "narrow space": (f"Ouvrir le fichier{NNBSP}?", "'?' is preceded by U+202F"),
    }
    for label, (translation, detail) in wrong.items():
        messages = [Msg("Open the file?", translation)]
        run, payload = only_catalogue(tools, work, f"cat-{label}", "fr", messages)
        assert run.returncode == 1, (label, run.stdout, run.stderr)
        unit = row(payload, "fr-nbsp", "catalogue", "fr")
        assert details(unit) == [detail], (label, unit)
        assert "pixelart_fr.ts [Panel] Open the file?" in unit["findings"][0]["where"]
        page = f"# Aide\n\n{translation}\n"
        run, payload = only_page(tools, work, f"guide-{label}", "fr", page)
        assert run.returncode == 1, (label, run.stdout, run.stderr)
        unit = row(payload, "fr-nbsp", "guide", "fr")
        assert details(unit) == [detail], (label, unit)
        assert unit["findings"][0]["where"] == "fr/index.md:3"


# --------------------------------------------------------------------------- #
# The inside of the guillemets (SC-L10N-DATA-004-7).
# --------------------------------------------------------------------------- #
SIDE_AFTER_NONE = f"{OPEN} after has no space (needs one U+00A0)"
SIDE_AFTER_PLAIN = f"{OPEN} after is an ordinary space (needs one U+00A0)"
SIDE_BEFORE_NARROW = f"{CLOSE} before is U+202F (needs one U+00A0)"
SIDE_BEFORE_NONE = f"{CLOSE} before has no space (needs one U+00A0)"
SIDE_BEFORE_TWO = f"{CLOSE} before has more than one space"

#: (surface, inside of the quotation, the details expected, as in the scenario).
GUILLEMET_ROWS = [
    ("catalogue", f"{OPEN}{NBSP}texte{NBSP}{CLOSE}", []),
    ("catalogue", f"{OPEN}texte{NBSP}{CLOSE}", [SIDE_AFTER_NONE]),
    ("guide", f"{OPEN} texte{NBSP}{CLOSE}", [SIDE_AFTER_PLAIN]),
    ("guide", f"{OPEN}{NBSP}texte{NNBSP}{CLOSE}", [SIDE_BEFORE_NARROW]),
    ("catalogue", f"{OPEN}{NBSP}texte {NBSP}{CLOSE}", [SIDE_BEFORE_TWO]),
    ("catalogue", f"{OPEN}texte{CLOSE}", [SIDE_AFTER_NONE, SIDE_BEFORE_NONE]),
    ("guide", f"{OPEN}{NBSP}texte{NBSP}{CLOSE}", []),
]


@REGISTRY.regression(
    mutant(
        "extra-space-passes",
        ty("        if rest and rest[0].isspace():\n", "        if False:\n"),
    ),
    mutant(
        "missing-space-passes",
        ty(
            '    return f"{glyph} {side} has no space (needs one U+00A0)"\n',
            '    return ""\n',
        ),
    ),
    mutant(
        "ordinary-space-unnamed",
        ty("    if space.isspace():\n", "    if False:\n"),
    ),
    mutant(
        "opening-not-examined",
        ty("        if char == OPENING:\n", "        if False:\n"),
    ),
    mutant(
        "side-misnamed",
        ty(
            '            detail = _inner_space("after", OPENING, rest[0], rest[1:])\n',
            '            detail = _inner_space("before", OPENING, rest[0], rest[1:])\n',
        ),
    ),
)
def case_french_guillemets_need_one_no_break_space_inside(
    tools: Tools, work: Path
) -> None:
    """Exactly one U+00A0 after ``\u00ab`` and before ``\u00bb``; the side is named.

    SC-L10N-DATA-004-7, the pass and fail rows of the scenario on both
    surfaces, plus a quotation whose two sides are both wrong (two findings,
    one per side).
    """
    for number, (surface, inside, expected) in enumerate(GUILLEMET_ROWS):
        label = f"row{number}"
        quoted = f"Voir {inside} ici."
        if surface == "catalogue":
            run, payload = only_catalogue(
                tools, work, label, "fr", [Msg("See it here", quoted)]
            )
            unit = row(payload, "fr-nbsp", "catalogue", "fr")
        else:
            run, payload = only_page(tools, work, label, "fr", f"# Aide\n\n{quoted}\n")
            unit = row(payload, "fr-nbsp", surface, "fr")
        assert unit["sub_counts"] == {"guillemet sides": 2, "marks": 0}, (label, unit)
        assert details(unit) == expected, (label, unit)
        if expected:
            assert run.returncode == 1, (label, run.stdout, run.stderr)
        else:
            assert_clean(run, payload)


# --------------------------------------------------------------------------- #
# One rule, two sub-counts (SC-L10N-DATA-004-8).
# --------------------------------------------------------------------------- #
#: (surface, French content, marks, sides, exit), after the scenario's rows.
SUB_COUNT_ROWS = [
    ("catalogue", f"Calque{NBSP}: %1", 1, 0, 0),
    ("guide", f"Cliquez sur {OPEN}{NBSP}Ouvrir{NBSP}{CLOSE} pour continuer.", 0, 2, 0),
    ("catalogue", f"Supprimer {OPEN}{NBSP}%1{NBSP}{CLOSE}{NBSP}?", 1, 2, 0),
    ("guide", f"Voici {OPEN}\ntexte\n{CLOSE} fin.", 0, 0, 1),
    ("guide", f"Tapez `{OPEN}texte{CLOSE}` ici.", 0, 0, 1),
    ("catalogue", f'<span title="{OPEN}">Fichier</span>', 0, 0, 1),
]


@REGISTRY.regression(
    mutant(
        "catalogue-sides-uncounted",
        ty(
            '            tally.credit(target, "guillemet sides", sides)\n',
            '            tally.credit(target, "guillemet sides", 0)\n',
        ),
    ),
    mutant(
        "guide-sides-uncounted",
        ty(
            '        tally.credit(unit, "guillemet sides", sides)\n',
            '        tally.credit(unit, "guillemet sides", 0)\n',
        ),
    ),
    mutant(
        "sub-counts-not-printed",
        ty(
            '        split = f" ({parts})" if'
            ' row["rule"] == "fr-nbsp" and parts else ""\n',
            '        split = ""\n',
        ),
    ),
    mutant(
        "line-end-opening-examined",
        ty(
            "            if not rest.strip():\n                continue\n",
            '            if not rest.strip():\n                rest = "x"\n',
        ),
    ),
    mutant(
        "line-start-closing-examined",
        ty(
            "            if not head.strip():\n                continue\n",
            '            if not head.strip():\n                head = "x"\n',
        ),
    ),
    mutant(
        "code-span-examined",
        ty('    re.compile(r"`[^`\\n]*`"),\n', ""),
    ),
    mutant(
        "markup-examined",
        ty(
            '    return catalogues.TAG.sub("", catalogues.ENTITY.sub("", text))\n',
            "    return text\n",
        ),
    ),
    mutant(
        "blind-rule-passes",
        ty(
            "    code = EXIT_FINDINGS if total or"
            " blind or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
)
def case_the_french_rule_counts_marks_and_guillemet_sides_together(
    tools: Tools, work: Path
) -> None:
    """The marks and the guillemet sides are two sub-counts of one rule.

    SC-L10N-DATA-004-8, the six rows of the scenario. The two sub-counts are
    printed and add up to the examined count; a ``\u00ab`` that ends a line, a
    ``\u00bb`` that starts one and a guillemet inside a code span or markup are
    not examined, so content with neither a mark nor a quotation exits 1.
    """
    for number, (surface, content, marks, sides, code) in enumerate(SUB_COUNT_ROWS):
        label = f"row{number}"
        if surface == "catalogue":
            tree = build_tree(work / label)
            tree.catalogue("fr", [Msg("Source", content)])
        else:
            tree = build_tree(work / label)
            tree.page("fr", "index.md", f"# Aide\n\n{content}\n")
            tree.chinese_page()
        run, payload = scan(tools, tree)
        unit = row(payload, "fr-nbsp", surface, "fr")
        assert unit["sub_counts"] == {"guillemet sides": sides, "marks": marks}, label
        assert unit["examined"] == marks + sides, (label, unit)
        assert unit["findings"] == [], (label, unit)
        assert unit["nothing_examined"] is (code == 1), (label, unit)
        assert run.returncode == code, (label, run.stdout, run.stderr)
        text = text_of(tools, tree)
        assert text.returncode == code, (label, text.stdout, text.stderr)
        line = (
            f"fr-nbsp [{surface}] fr: examined {marks + sides} item(s) "
            f"(guillemet sides {sides}, marks {marks}), 0 finding(s)"
        )
        assert line in text.stdout, (label, text.stdout)
        if code == 1:
            assert f"{line}\n  nothing examined\n" in text.stdout, (label, text.stdout)


# --------------------------------------------------------------------------- #
# No narrow no-break space (SC-L10N-DATA-004-3).
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "catalogue-not-scanned",
        ty("enumerate(raw) if c == NARROW_NBSP", "enumerate(raw) if False"),
    ),
    mutant(
        "guide-not-scanned",
        ty("enumerate(text) if c == NARROW_NBSP", "enumerate(text) if False"),
    ),
)
def case_no_narrow_no_break_space_anywhere(tools: Tools, work: Path) -> None:
    """A U+202F in any file of any language exits 1, with its place named.

    SC-L10N-DATA-004-3: the number of files scanned is printed and is
    non-zero.
    """
    tree = build_tree(work / "clean")
    tree.catalogue("de", [Msg("Open", "\u00d6ffnen")])
    tree.catalogue("es", [Msg("Open", "Abrir")])
    tree.page("de", "index.md", "# Hilfe\n\nText.\n")
    tree.chinese_page()
    run, payload = scan(tools, tree)
    assert_clean(run, payload)
    assert row(payload, "no-u202f", "catalogue", "de")["files"] == 1
    assert row(payload, "no-u202f", "catalogue", "es")["examined"] == 1
    assert row(payload, "no-u202f", "guide", "de")["examined"] == 1
    text = text_of(tools, tree)
    assert "no-u202f [catalogue] de: examined 1 file(s), 0 finding(s)" in text.stdout

    dirty = build_tree(work / "catalogue")
    path = dirty.catalogue("de", [Msg("Open", f"\u00d6ffnen{NNBSP}x")])
    run, payload = scan(tools, dirty)
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "no-u202f", "catalogue", "de")
    assert details(unit) == ["U+202F"]
    assert unit["findings"][0]["where"] == f"pixelart_de.ts:{line_of(path, NNBSP)}"

    guide = build_tree(work / "guide")
    page = guide.page("de", "index.md", f"# Hilfe\n\nEin{NNBSP}Text.\n")
    guide.chinese_page()
    run, payload = scan(tools, guide)
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "no-u202f", "guide", "de")
    assert details(unit) == ["U+202F"]
    assert unit["findings"][0]["where"] == f"de/index.md:{line_of(page, NNBSP)}"


# --------------------------------------------------------------------------- #
# No narrow no-break space, in any spelling (SC-L10N-DATA-004-3).
#
# A catalogue is XML and a guide page is Markdown, and both resolve a numeric
# character reference, so ``&#x202f;`` puts U+202F on the screen exactly as the
# character itself does. The rule must see it in every spelling: hexadecimal or
# decimal, either case of the ``x`` and of the digit, leading zeros. A reference
# to another code point, or one that is not closed by a semicolon, is not U+202F.
# --------------------------------------------------------------------------- #
NNBSP_REFERENCES = (
    "&#x202f;",
    "&#8239;",
    "&#X202f;",
    "&#x202F;",
    "&#x0202f;",
    "&#008239;",
)
#: XML allows only a lower-case ``x`` in a reference, so a catalogue cannot hold
#: ``&#X202f;``: it would not parse and the run would exit 2.
NNBSP_XML_REFERENCES = tuple(
    each for each in NNBSP_REFERENCES if not each.startswith("&#X")
)
#: Spellings that must NOT be read as U+202F: the neighbouring code points in both
#: bases (U+2020, U+2030, U+202FB, U+14186, U+473F), and, on a page, a hexadecimal
#: reference with no semicolon (CommonMark leaves that as text).
NNBSP_LOOKALIKES = ("&#x2020;", "&#8240;", "&#x202fb;", "&#82390;", "&#18239;")
NNBSP_UNCLOSED = "&#x202f"
#: A reference to an ampersand followed by literal text that looks like a reference.
NNBSP_LITERAL = "&amp;#x202f;"
NNBSP_REFERENCE_REGEX = 'r"&#(?:[xX]0*202[fF]|0*8239);"'


def reference_regex(replacement: str) -> Edit:
    """Edit the script's reference pattern into ``replacement`` (a regex literal)."""
    return ty(NNBSP_REFERENCE_REGEX, replacement)


@REGISTRY.regression(
    mutant(
        "catalogue-references-not-scanned",
        ty(
            "    for offset in sorted(spelled + narrow_nbsp_references(raw)):\n",
            "    for offset in sorted(spelled):\n",
        ),
    ),
    mutant(
        "guide-references-not-scanned",
        ty(
            "    for offset in sorted(spelled + narrow_nbsp_references(text)):\n",
            "    for offset in sorted(spelled):\n",
        ),
    ),
    mutant(
        "decimal-reference-not-seen",
        reference_regex('r"&#(?:[xX]0*202[fF]);"'),
    ),
    mutant(
        "hexadecimal-reference-not-seen",
        reference_regex('r"&#(?:0*8239);"'),
    ),
    mutant(
        "capital-x-not-seen",
        reference_regex('r"&#(?:x0*202[fF]|0*8239);"'),
    ),
    mutant(
        "capital-f-not-seen",
        reference_regex('r"&#(?:[xX]0*202f|0*8239);"'),
    ),
    mutant(
        "leading-zeros-not-seen",
        reference_regex('r"&#(?:[xX]202[fF]|8239);"'),
    ),
    mutant(
        "semicolon-not-required",
        reference_regex('r"&#(?:[xX]0*202[fF]|0*8239);?"'),
    ),
    mutant(
        "every-code-point-taken",
        reference_regex('r"&#(?:[xX][0-9a-fA-F]+|[0-9]+);"'),
    ),
)
def case_a_narrow_no_break_space_is_found_in_every_spelling(
    tools: Tools, work: Path
) -> None:
    """The character and each reference to it are findings; look-alikes are not.

    A catalogue and a guide page each hold the raw U+202F and the spellings of a
    reference to it that the format allows (the page also the capital ``X`` that
    XML forbids), on lines of their own: every one is a ``no-u202f`` finding
    with the place named, in file order, and the one file is counted once. A
    second fixture holds references to other code points and an unclosed one,
    and exits 0.
    """
    bodies = [f"Ein{NNBSP}Text", *(f"Ein{each}Text" for each in NNBSP_XML_REFERENCES)]
    plain = len(bodies)

    tree = build_tree(work / "catalogue")
    path = tree.catalogue(
        "de", [Msg(f"Plant {n}", raw=body) for n, body in enumerate(bodies)]
    )
    run, payload = scan(tools, tree, "--surface", "catalogue")
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "no-u202f", "catalogue", "de")
    assert (unit["files"], unit["examined"]) == (1, 1), unit
    assert details(unit) == ["U+202F"] * plain, unit
    wanted = [f"pixelart_de.ts:{line_of(path, body)}" for body in bodies]
    assert len(set(wanted)) == plain, wanted
    assert [item["where"] for item in unit["findings"]] == wanted, unit
    text = text_of(tools, tree, "--surface", "catalogue")
    head = f"no-u202f [catalogue] de: examined 1 file(s), {plain} finding(s)"
    assert head in text.stdout, text.stdout

    guide = build_tree(work / "guide")
    bodies = [f"Ein{NNBSP}Text", *(f"Ein{each}Text" for each in NNBSP_REFERENCES)]
    plain = len(bodies)
    lines = "\n\n".join(f"{body}." for body in bodies)
    page = guide.page("de", "index.md", f"# Hilfe\n\n{lines}\n")
    guide.chinese_page()
    run, payload = scan(tools, guide, "--surface", "guide")
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "no-u202f", "guide", "de")
    assert (unit["files"], unit["examined"]) == (1, 1), unit
    assert details(unit) == ["U+202F"] * plain, unit
    wanted = [f"de/index.md:{line_of(page, body)}" for body in bodies]
    assert len(set(wanted)) == plain, wanted
    assert [item["where"] for item in unit["findings"]] == wanted, unit
    text = text_of(tools, guide, "--surface", "guide")
    head = f"no-u202f [guide] de: examined 1 file(s), {plain} finding(s)"
    assert head in text.stdout, text.stdout

    near = [*NNBSP_LOOKALIKES, NNBSP_LITERAL]
    clean = build_tree(work / "lookalikes")
    clean.catalogue(
        "de", [Msg(f"Near {n}", raw=f"Ein{each}Text") for n, each in enumerate(near)]
    )
    lines = "\n\n".join(f"Ein{each}Text." for each in [*near, NNBSP_UNCLOSED])
    clean.page("de", "index.md", f"# Hilfe\n\n{lines}\n")
    clean.chinese_page()
    run, payload = scan(tools, clean)
    assert_clean(run, payload)
    assert row(payload, "no-u202f", "catalogue", "de")["examined"] == 1
    assert row(payload, "no-u202f", "guide", "de")["examined"] == 1


# --------------------------------------------------------------------------- #
# Ellipsis (SC-L10N-DATA-004-4).
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant("count-not-compared", ty("    if wanted != found:\n", "    if False:\n")),
    mutant(
        "space-before-passes",
        ty("    if SPACE_BEFORE_ELLIPSIS.search(form):\n", "    if False:\n"),
    ),
    mutant(
        "three-periods-pass",
        ty(
            "    if THREE_PERIODS.search(form) and not THREE_PERIODS.search(source):\n",
            "    if False:\n",
        ),
    ),
    mutant(
        "unfinished-examined",
        ty(
            '        if message.kind == "unfinished" or not forms or not all(forms):\n',
            "        if False:\n",
        ),
    ),
    mutant(
        "source-language-examined",
        ty(
            "    if catalogue.identity:\n        return language\n",
            "    if False:\n        return language\n",
        ),
    ),
)
def case_a_translation_keeps_the_sources_ellipses(tools: Tools, work: Path) -> None:
    """As many U+2026 as the source, no space before one, no stray periods.

    SC-L10N-DATA-004-4: only finished translations are compared with their
    source, the source-language catalogue is not compared with itself, and
    the number of messages examined is printed and is non-zero.
    """
    clean = [
        Msg(f"Loading{ELLIPSIS}", f"Cargando{ELLIPSIS}"),
        Msg("Wait...", "Espere..."),
        Msg("Open", "Abrir"),
        Msg(f"Skipped{ELLIPSIS}", "Omitido", kind="unfinished"),
    ]
    tree = build_tree(work / "clean")
    tree.catalogue("es", clean)
    run, payload = scan(tools, tree)
    assert_clean(run, payload)
    assert row(payload, "ellipsis", "catalogue", "es")["examined"] == 3
    text = text_of(tools, tree)
    assert "ellipsis [catalogue] es: examined 3 item(s), 0 finding(s)" in text.stdout

    wrong = {
        "dropped": (
            f"Loading{ELLIPSIS}",
            "Cargando",
            "0 U+2026 where the source has 1",
        ),
        "added": ("Loading", f"Cargando{ELLIPSIS}", "1 U+2026 where the source has 0"),
        "space": (
            f"Loading{ELLIPSIS}",
            f"Cargando {ELLIPSIS}",
            "a space before U+2026",
        ),
        "no-break": (
            f"Loading{ELLIPSIS}",
            f"Cargando{NBSP}{ELLIPSIS}",
            "a space before U+2026",
        ),
        "periods": ("Open", "Abrir...", "three periods where the source has none"),
    }
    for label, (source, translation, detail) in wrong.items():
        run, payload = only_catalogue(
            tools, work, label, "es", [Msg(source, translation)]
        )
        assert run.returncode == 1, (label, run.stdout, run.stderr)
        unit = row(payload, "ellipsis", "catalogue", "es")
        assert details(unit) == [detail], (label, unit)
        assert f"pixelart_es.ts [Panel] {source}" in unit["findings"][0]["where"]

    same = [Msg(f"Loading{ELLIPSIS}", "Loading...")]
    run, payload = only_catalogue(tools, work, "identity", "en", same)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert not has_row(payload, "ellipsis", "catalogue", "en")


# --------------------------------------------------------------------------- #
# Korean, no Han (SC-L10N-DATA-004-5).
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "han-not-found",
        ty(
            "    found = [(m.start(), m.group()) for m in HAN.finditer(text)]\n",
            "    found = []\n",
        ),
    ),
    mutant(
        "endonyms-not-stripped",
        ty(
            '        text = text.replace(name, "\\u0000" * len(name))\n',
            "        text = text\n",
        ),
    ),
    mutant(
        "endonyms-not-read",
        ty(
            "    return tuple(sorted(set(module.ENDONYMS.values()),"
            " key=len, reverse=True))\n",
            "    return ()\n",
        ),
    ),
    mutant(
        "catalogue-not-scanned",
        ty('"ko-no-han": unit("ko-no-han", "ko"),', '"ko-no-han": 0,'),
    ),
    mutant("guide-not-scanned", ty('    if lang == "ko":\n', '    if lang == "xx":\n')),
)
def case_korean_text_contains_no_han_outside_the_endonyms(
    tools: Tools, work: Path
) -> None:
    """A Han character in Korean text exits 1; the fixed self-names are exempt.

    SC-L10N-DATA-004-5, both surfaces. The self-names come from the
    ``language_names.py`` of the root that is scanned: with a table that lacks
    the Han ones the same text fails.
    """
    exempt = f"\uc5b8\uc5b4: {JA_ENDONYM} / {ZH_ENDONYM} / {KO_ENDONYM}"
    clean = [Msg("Open file", KO_OPEN), Msg("Language", exempt)]
    run, payload = only_catalogue(tools, work, "cat-clean", "ko", clean)
    assert_clean(run, payload)
    assert row(payload, "ko-no-han", "catalogue", "ko")["examined"] == 2
    page = f"# \ud30c\uc77c\n\n{KO_OPEN}\n\n{exempt}\n"
    run, payload = only_page(tools, work, "guide-clean", "ko", page)
    assert_clean(run, payload)
    assert row(payload, "ko-no-han", "guide", "ko")["examined"] == 1

    run, payload = only_catalogue(
        tools, work, "cat-han", "ko", [Msg("Open file", KO_HANJA)]
    )
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "ko-no-han", "catalogue", "ko")
    assert details(unit) == [f"Han character U+958B {HAN_KAI}"]
    assert "pixelart_ko.ts [Panel] Open file" in unit["findings"][0]["where"]
    run, payload = only_page(
        tools, work, "guide-han", "ko", f"# \ud30c\uc77c\n\n{KO_HANJA}\n"
    )
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "ko-no-han", "guide", "ko")
    assert details(unit) == [f"Han character U+958B {HAN_KAI}"]
    assert unit["findings"][0]["where"] == "ko/index.md:3"

    without = {
        code: name for code, name in ENDONYMS.items() if code not in ("ja", "zh_CN")
    }
    tree = build_tree(work / "without", without)
    tree.catalogue("ko", clean)
    run, payload = scan(tools, tree)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert len(row(payload, "ko-no-han", "catalogue", "ko")["findings"]) == len(
        JA_ENDONYM + ZH_ENDONYM
    )


# --------------------------------------------------------------------------- #
# Simplified Chinese, half-width marks in the catalogue (SC-L10N-DATA-004-6).
# --------------------------------------------------------------------------- #
FULLWIDTH = {
    "\uff1a": "U+FF1A",
    "\uff01": "U+FF01",
    "\uff1f": "U+FF1F",
    "\uff08": "U+FF08",
    "\uff09": "U+FF09",
}


@REGISTRY.regression(
    mutant(
        "marks-not-found",
        ty(
            "    found = [(i, c) for i, c in enumerate(text) if c in ZH_FULLWIDTH]\n",
            "    found = []\n",
        ),
    ),
    mutant(
        "catalogue-rule-absent",
        ty('"zh-fullwidth": unit("zh-fullwidth", "zh"),', '"zh-fullwidth": 0,'),
    ),
    mutant(
        "guide-exclusion-unreported",
        ty('if primary(language) == "zh":', "if False:"),
    ),
)
def case_simplified_chinese_catalogue_takes_half_width_marks(
    tools: Tools, work: Path
) -> None:
    """Each of the five full-width marks in a ``zh_CN`` message exits 1.

    SC-L10N-DATA-004-6: the number of messages scanned is printed and is
    non-zero, and the ``zh_CN`` guide pages are not part of this scan: they
    take the full-width marks and the report says they were excluded.
    """
    clean = [Msg("Open file", ZH_OPEN), Msg("Note", f"{ZH_OPEN}: (%1)!?")]
    run, payload = only_catalogue(tools, work, "clean", "zh_CN", clean)
    assert_clean(run, payload)
    assert row(payload, "zh-fullwidth", "catalogue", "zh_CN")["examined"] == 2
    for number, (mark, name) in enumerate(FULLWIDTH.items()):
        messages = [Msg("Open file", f"{ZH_OPEN}{mark}")]
        run, payload = only_catalogue(tools, work, f"bad{number}", "zh_CN", messages)
        assert run.returncode == 1, (name, run.stdout, run.stderr)
        unit = row(payload, "zh-fullwidth", "catalogue", "zh_CN")
        assert details(unit) == [f"full-width mark {name} {mark}"], (name, unit)

    tree = build_tree(work / "guide")
    tree.page(
        "zh_CN", "index.md", f"# {ZH_OPEN}\n\n{ZH_OPEN}\uff1a\uff08\uff01\uff09\uff1f\n"
    )
    run, payload = scan(tools, tree)
    assert_clean(run, payload)
    assert not has_row(payload, "zh-fullwidth", "guide", "zh_CN")
    assert payload["excluded"] == ["zh-fullwidth [guide] zh_CN: not scanned by design"]
    text = text_of(tools, tree)
    assert "excluded: zh-fullwidth [guide] zh_CN: not scanned by design" in text.stdout


# --------------------------------------------------------------------------- #
# Russian, no U+0022 in prose (SC-L10N-DATA-004-9).
# --------------------------------------------------------------------------- #
# "Add label %1", "Save", "Help", "Open <a>file</a>" in Russian, as escapes.
RU_QUOTED = (
    f"\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c"
    f" \u043c\u0435\u0442\u043a\u0443 {OPEN}%1{CLOSE}"
)
RU_STRAIGHT = RU_QUOTED.replace(OPEN, '"').replace(CLOSE, '"')
RU_SAVE = "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c"
RU_QUOTE_DETAIL = f"U+0022 used as a quotation mark (Russian takes {OPEN} {CLOSE})"
RU_PAGE_HEAD = "# \u041f\u043e\u043c\u043e\u0449\u044c\n\n"
RU_MARKUP = (
    "\u041e\u0442\u043a\u0440\u044b\u0442\u044c"
    ' <a href="x">\u0444\u0430\u0439\u043b</a>'
)


@REGISTRY.regression(
    mutant("straight-quote-passes", ty("if char == STRAIGHT", "if False")),
    mutant(
        "catalogue-rule-absent",
        ty(
            '"ru-no-straight-quote": unit("ru-no-straight-quote", "ru"),',
            '"ru-no-straight-quote": 0,',
        ),
    ),
    mutant("guide-not-scanned", ty('    if lang == "ru":\n', '    if lang == "xx":\n')),
    mutant(
        "markup-attribute-examined",
        ty(
            '    return catalogues.TAG.sub("", catalogues.ENTITY.sub("", text))\n',
            "    return text\n",
        ),
    ),
    mutant("code-span-examined", ty('    re.compile(r"`[^`\\n]*`"),\n', "")),
    mutant("link-target-examined", ty('    re.compile(r"\\]\\([^)\\n]*\\)"),\n', "")),
)
def case_russian_text_carries_no_straight_quotation_mark(
    tools: Tools, work: Path
) -> None:
    """A U+0022 in Russian prose exits 1 on both surfaces; \u00ab \u00bb pass.

    SC-L10N-DATA-004-9, the rows of the scenario: a message or page with no
    quotation at all is examined (and passes); markup attributes, code spans
    and link targets are not prose; the rule belongs to Russian alone. The
    number of messages or pages examined is printed and is non-zero.
    """
    clean = [Msg("Add label %1", RU_QUOTED), Msg("Save", RU_SAVE)]
    run, payload = only_catalogue(tools, work, "cat-clean", "ru", clean)
    assert_clean(run, payload)
    unit = row(payload, "ru-no-straight-quote", "catalogue", "ru")
    assert unit["examined"] == 2 and unit["sub_counts"] == {"messages": 2}

    markup = [Msg("Open", RU_MARKUP)]
    run, payload = only_catalogue(tools, work, "cat-markup", "ru", markup)
    assert_clean(run, payload)

    run, payload = only_catalogue(
        tools, work, "cat-bad", "ru", [Msg("Add label %1", RU_STRAIGHT)]
    )
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "ru-no-straight-quote", "catalogue", "ru")
    assert details(unit) == [RU_QUOTE_DETAIL] * 2
    assert "pixelart_ru.ts [Panel] Add label %1" in unit["findings"][0]["where"]

    page = f"{RU_PAGE_HEAD}{RU_QUOTED}\n"
    run, payload = only_page(tools, work, "guide-clean", "ru", page)
    assert_clean(run, payload)
    unit = row(payload, "ru-no-straight-quote", "guide", "ru")
    assert unit["examined"] == 1 and unit["sub_counts"] == {"pages": 1}
    run, payload = only_page(
        tools, work, "guide-bad", "ru", f"{RU_PAGE_HEAD}{RU_STRAIGHT}\n"
    )
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "ru-no-straight-quote", "guide", "ru")
    assert details(unit) == [RU_QUOTE_DETAIL] * 2
    assert unit["findings"][0]["where"] == "ru/index.md:3"

    for label, body in {
        "code-span": f'{RU_SAVE} `a"b` {RU_SAVE}',
        "link-target": f'{RU_SAVE} [{RU_SAVE}](pages/a"b.md)',
    }.items():
        run, payload = only_page(
            tools, work, f"guide-{label}", "ru", f"{RU_PAGE_HEAD}{body}\n"
        )
        assert_clean(run, payload)

    run, payload = only_catalogue(
        tools, work, "other", "de", [Msg("Quote", 'Das "Wort"')]
    )
    assert_clean(run, payload)
    assert not has_row(payload, "ru-no-straight-quote", "catalogue", "de")


# --------------------------------------------------------------------------- #
# --worklist.
# --------------------------------------------------------------------------- #
#: (rule, language, source, clean form, bad form, the detail expected).
WORKLIST_RULES = [
    (
        "fr-nbsp",
        "fr",
        "Open?",
        f"Ouvrir{NBSP}?",
        "Ouvrir?",
        "'?' has no space before it",
    ),
    (
        "fr-nbsp",
        "fr",
        "See it",
        f"Voir {OPEN}{NBSP}x{NBSP}{CLOSE}",
        f"Voir {OPEN}x{NBSP}{CLOSE}",
        SIDE_AFTER_NONE,
    ),
    ("no-u202f", "de", "Open", "\u00d6ffnen", f"\u00d6ffnen{NNBSP}x", "U+202F"),
    (
        "ellipsis",
        "es",
        "Loading",
        "Cargando",
        f"Cargando{ELLIPSIS}",
        "1 U+2026 where the source has 0",
    ),
    (
        "ru-no-straight-quote",
        "ru",
        "Add label %1",
        RU_QUOTED,
        RU_STRAIGHT,
        [RU_QUOTE_DETAIL] * 2,
    ),
    (
        "ko-no-han",
        "ko",
        "Open file",
        KO_OPEN,
        KO_HANJA,
        f"Han character U+958B {HAN_KAI}",
    ),
    (
        "zh-fullwidth",
        "zh_CN",
        "Open file",
        ZH_OPEN,
        f"{ZH_OPEN}\uff1a",
        "full-width mark U+FF1A \uff1a",
    ),
]


def write_worklist(
    tree: Tree, language: str, entries: list, name: str = "w.json"
) -> Path:
    """Write a worklist of ``entries`` for ``language`` into the scratch work folder."""
    document = worklist_document(entries, language=language)
    path = tree.work / name
    path.write_bytes(json.dumps(document, ensure_ascii=True).encode("utf-8"))
    return path


@REGISTRY.regression(
    mutant(
        "fr-nbsp-not-run", ty('    target = units["fr-nbsp"]\n', "    target = 0\n")
    ),
    mutant(
        "no-u202f-not-run",
        ty("            if NARROW_NBSP in form:\n", "            if False:\n"),
    ),
    mutant(
        "ellipsis-not-run",
        ty(
            "        for detail in ellipsis_problems(source, form):\n",
            "        for detail in []:\n",
        ),
    ),
    mutant(
        "ru-not-run",
        ty('    target = units["ru-no-straight-quote"]\n', "    target = 0\n"),
    ),
    mutant(
        "ko-not-run",
        ty(
            "        target = units[rule]\n",
            '        target = units[rule] if rule != "ko-no-han" else 0\n',
        ),
    ),
    mutant(
        "zh-not-run",
        ty(
            "        target = units[rule]\n",
            '        target = units[rule] if rule != "zh-fullwidth" else 0\n',
        ),
    ),
    mutant(
        "language-not-read",
        ty('    language = document["language"]\n', '    language = "fr"\n'),
    ),
)
def case_a_worklist_is_checked_with_one_bad_entry_per_catalogue_rule(
    tools: Tools, work: Path
) -> None:
    """Each catalogue rule runs over a worklist's entries and names the bad one.

    SC-L10N-DATA-004-2, -3, -4, -5, -6 and -9 through the ``--worklist``
    input. The language comes from the worklist's own ``language`` field, and
    the report gives the entries, the filled ones and the unfilled ones.
    """
    for number, (rule, language, source, good, bad, detail) in enumerate(
        WORKLIST_RULES
    ):
        tree = build_tree(work / f"rule{number}")
        path = write_worklist(
            tree, language, [entry("Fine", [good]), entry(source, [bad])]
        )
        run, payload = scan(tools, tree, "--worklist", str(path))
        assert run.returncode == 1, (rule, run.stdout, run.stderr)
        unit = row(payload, rule, "worklist", language)
        expected = detail if isinstance(detail, list) else [detail]
        assert details(unit) == expected, (rule, unit)
        assert f"w.json entry 2 [Panel] {source}" in unit["findings"][0]["where"]
        assert (
            payload["worklist"]["entries"] == 2 and payload["worklist"]["filled"] == 2
        )
        assert payload["worklist"]["language"] == language
        text = text_of(tools, tree, "--worklist", str(path))
        assert (
            text.returncode == 1
            and f"w.json entry 2 [Panel] {source}: {expected[0]}" in text.stdout
        )
        passing = write_worklist(tree, language, [entry(source, [good])], "ok.json")
        run, payload = scan(tools, tree, "--worklist", str(passing))
        assert_clean(run, payload)
        assert row(payload, rule, "worklist", language)["examined"] >= 1

    # The same text under another language is judged by that language's rules.
    tree = build_tree(work / "other-language")
    path = write_worklist(tree, "de", [entry("Open?", ["Ouvrir?"])])
    run, payload = scan(tools, tree, "--worklist", str(path))
    assert_clean(run, payload)
    assert not has_row(payload, "fr-nbsp", "worklist", "de")


@REGISTRY.regression(
    mutant(
        "partial-entry-examined",
        ty(
            "        or not all(isinstance(f, str) and f for f in forms)\n",
            "        or False\n",
        ),
    ),
    mutant(
        "blind-rule-passes",
        ty(
            "    code = EXIT_FINDINGS if total or"
            " blind or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant(
        "blind-rule-unnamed",
        ty('        if row["nothing_examined"]:\n', "        if False:\n"),
    ),
    mutant(
        "empty-report-unnamed",
        ty(
            '    if report["examined_total"] == 0 or not report["rules"]:\n',
            "    if False:\n",
        ),
    ),
)
def case_a_worklist_counts_its_entries_and_fails_when_none_is_filled(
    tools: Tools, work: Path
) -> None:
    """Only entries with every form filled are examined; none filled is exit 1.

    SC-L10N-DATA-004-2 through the ``--worklist`` input: the report prints
    the examined count beside the worklist's entry count and its unfilled
    count, a partly filled numerus entry is unfilled, and a worklist with no
    filled entry examines nothing and says so.
    """
    tree = build_tree(work / "mixed")
    entries = [
        entry("Open?", [f"Ouvrir{NBSP}?"]),
        entry("Close?", [""]),
        entry("%n layer(s)", ["Ouvrir?", ""], numerus=True),
        {**entry("Save?", ["x"]), "translation": None},
    ]
    path = write_worklist(tree, "fr", entries)
    run, payload = scan(tools, tree, "--worklist", str(path))
    assert_clean(run, payload)
    assert payload["worklist"]["entries"] == 4
    assert payload["worklist"]["filled"] == 1
    assert payload["worklist"]["unfilled"] == 3
    assert row(payload, "fr-nbsp", "worklist", "fr")["examined"] == 1
    assert row(payload, "no-u202f", "worklist", "fr")["examined"] == 1
    text = text_of(tools, tree, "--worklist", str(path))
    assert (
        "worklist w.json [fr]: 4 entr(ies), 1 filled and examined, 3 unfilled"
        in text.stdout
    )
    assert "no-u202f [worklist] fr: examined 1 item(s), 0 finding(s)" in text.stdout

    for label, items in {
        "none-filled": [entry("Open?", [""]), entry("Close?", [""])],
        "no-entries": [],
    }.items():
        empty = build_tree(work / label)
        path = write_worklist(empty, "fr", items)
        run, payload = scan(tools, empty, "--worklist", str(path))
        assert run.returncode == 1, (label, run.stdout, run.stderr)
        assert payload["examined_total"] == 0
        assert payload["worklist"]["filled"] == 0
        assert all(r["nothing_examined"] for r in payload["rules"])
        text = text_of(tools, empty, "--worklist", str(path))
        assert text.returncode == 1
        assert text.stdout.rstrip("\n").endswith("nothing examined"), text.stdout
        assert "  nothing examined\n" in text.stdout


@REGISTRY.regression(
    mutant(
        "combination-accepted",
        ty(
            "        if args.surface or args.catalogues or args.guide_root:\n",
            "        if False:\n",
        ),
    ),
    mutant(
        "not-a-worklist-accepted",
        ty(
            "    if not isinstance(document, dict) or not"
            ' isinstance(document.get("entries"), list):\n',
            "    if False:\n",
        ),
    ),
    mutant(
        "no-language-accepted",
        ty(
            '    if not isinstance(document.get("language"),'
            ' str) or not document["language"]:\n',
            "    if False:\n",
        ),
    ),
    mutant(
        "language-filter-ignored",
        ty(
            '        if keep is not None and info["language"] not in keep:\n',
            "        if False:\n",
        ),
    ),
    mutant(
        "unreadable-accepted",
        ty(
            "    except ValueError as exc:\n"
            '        raise TypographyError(f"{path}: {exc}") from exc\n',
            "    except ValueError:\n        document = []\n",
        ),
    ),
)
def case_a_worklist_that_cannot_be_checked_exits_2(tools: Tools, work: Path) -> None:
    """A worklist that is not one, names no language, or is combined, exits 2."""
    tree = build_tree(work / "w")
    good = write_worklist(tree, "fr", [entry("Open?", [f"Ouvrir{NBSP}?"])])
    for flag in (
        ["--surface", "catalogue"],
        ["--catalogues", str(tree.work)],
        ["--guide-root", str(tree.work)],
    ):
        run = text_of(tools, tree, "--worklist", str(good), *flag)
        assert run.returncode == 2, (flag, run.stdout, run.stderr)
        assert "--worklist cannot be combined" in run.stderr
    run = text_of(tools, tree, "--worklist", str(good), "--languages", "de")
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "excludes the worklist's language" in run.stderr

    bad = {
        "not-an-object": ("[]", "not a worklist"),
        "no-entries-list": ('{"language": "fr"}', "not a worklist"),
        "no-language": ('{"entries": []}', "names no language"),
        "not-json": ("{oops", "Expecting property name"),
    }
    for label, (body, message) in bad.items():
        path = tree.work / f"{label}.json"
        path.write_bytes(body.encode("utf-8"))
        run = text_of(tools, tree, "--worklist", str(path))
        assert run.returncode == 2, (label, run.stdout, run.stderr)
        assert message in run.stderr, (label, run.stderr)
    run = text_of(tools, tree, "--worklist", str(tree.work / "missing.json"))
    assert run.returncode == 2, (run.stdout, run.stderr)


# --------------------------------------------------------------------------- #
# Nothing examined, the surfaces, the inputs.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "blind-rule-passes",
        ty(
            "    code = EXIT_FINDINGS if total or"
            " blind or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant(
        "empty-report-unnamed",
        ty(
            '    if report["examined_total"] == 0 or not report["rules"]:\n',
            "    if False:\n",
        ),
    ),
)
def case_a_rule_or_a_run_that_examined_nothing_exits_1(
    tools: Tools, work: Path
) -> None:
    """French content with neither a mark nor a quotation is blind: exit 1.

    The rule that applied and examined nothing is named, and a root with no
    catalogue folder and no guide tree examines nothing at all.
    """
    run, payload = only_catalogue(tools, work, "blind", "fr", [Msg("Open", "Ouvrir")])
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["rules_examining_nothing"] == 1
    assert row(payload, "fr-nbsp", "catalogue", "fr")["nothing_examined"] is True
    assert row(payload, "ellipsis", "catalogue", "fr")["examined"] == 1

    only_unfinished = [Msg("Open", "Ouvrir", kind="unfinished")]
    run, payload = only_catalogue(tools, work, "unfinished", "es", only_unfinished)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert row(payload, "ellipsis", "catalogue", "es")["nothing_examined"] is True

    tree = build_tree(work / "empty")
    run, payload = scan(tools, tree)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["examined_total"] == 0 and payload["rules"] == []
    assert len(payload["skipped"]) == 2
    text = text_of(tools, tree)
    assert text.returncode == 1
    assert text.stdout.rstrip("\n").endswith("nothing examined"), text.stdout


@REGISTRY.regression(
    mutant(
        "languages-ignored",
        ty("    return keep is None or language in keep\n", "    return True\n"),
    ),
    mutant(
        "catalogue-always-scanned",
        ty('    if args.surface in ("catalogue", "both"):\n', "    if True:\n"),
    ),
    mutant(
        "guide-always-scanned",
        ty('    if args.surface in ("guide", "both"):\n', "    if True:\n"),
    ),
    mutant(
        "named-catalogue-folder-skipped",
        ty("        elif args.catalogues:\n", "        elif False:\n"),
    ),
    mutant(
        "named-guide-folder-skipped",
        ty("        elif args.guide_root:\n", "        elif False:\n"),
    ),
    mutant(
        "default-folder-not-reported",
        ty(
            '            skipped.append(f"catalogue'
            ' surface: {folder} does not exist")\n',
            "            pass\n",
        ),
    ),
)
def case_the_surface_and_the_languages_select_what_is_scanned(
    tools: Tools, work: Path
) -> None:
    """``--surface`` and ``--languages`` narrow the scan; named folders must exist."""
    tree = build_tree(work / "both")
    tree.catalogue("fr", [Msg("Open?", f"Ouvrir{NBSP}?")])
    tree.catalogue("de", [Msg("Open", "\u00d6ffnen")])
    tree.page("fr", "index.md", "# Aide\n\nOuvrir?\n")
    tree.chinese_page()
    run, payload = scan(tools, tree)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert details(row(payload, "fr-nbsp", "guide", "fr")) == [
        "'?' has no space before it"
    ]
    assert payload["surfaces"] == ["catalogue", "guide"]

    run, payload = scan(tools, tree, "--surface", "catalogue")
    assert_clean(run, payload)
    assert payload["surfaces"] == ["catalogue"]
    assert not has_row(payload, "fr-nbsp", "guide", "fr")
    run, payload = scan(tools, tree, "--surface", "guide")
    assert run.returncode == 1 and payload["surfaces"] == ["guide"]
    assert not has_row(payload, "no-u202f", "catalogue", "de")

    run, payload = scan(tools, tree, "--surface", "catalogue", "--languages", "de")
    assert_clean(run, payload)
    assert not has_row(payload, "fr-nbsp", "catalogue", "fr")
    assert has_row(payload, "no-u202f", "catalogue", "de")
    run, payload = scan(tools, tree, "--languages", "fr")
    assert run.returncode == 1
    assert not has_row(payload, "no-u202f", "catalogue", "de")

    only_guide = build_tree(work / "guide-only")
    only_guide.page("fr", "index.md", f"# Aide\n\nOuvrir{NBSP}?\n")
    only_guide.chinese_page()
    run, payload = scan(tools, only_guide)
    assert_clean(run, payload)
    assert payload["surfaces"] == ["guide"]
    assert payload["skipped"] == [
        f"catalogue surface: {only_guide.root / CAT_DIR} does not exist"
    ]
    text = text_of(tools, only_guide)
    assert (
        f"skipped: catalogue surface: {only_guide.root / CAT_DIR} does not exist"
        in text.stdout
    )

    for flag in ("--catalogues", "--guide-root"):
        run = text_of(tools, only_guide, flag, str(only_guide.work / "nowhere"))
        assert run.returncode == 2, (flag, run.stdout, run.stderr)
        assert "not a folder" in run.stderr


@REGISTRY.regression(
    mutant(
        "invalid-utf8-accepted",
        ty(
            '            return handle.read().decode("utf-8")\n',
            '            return handle.read().decode("utf-8", "replace")\n',
        ),
    ),
    mutant(
        "malformed-catalogue-crashes",
        ty(
            "    except (TypographyError, _catalogue_error()) as exc:\n",
            "    except TypographyError as exc:\n",
        ),
    ),
)
def case_an_unreadable_input_exits_2(tools: Tools, work: Path) -> None:
    """A page that is not UTF-8 or a catalogue that is not XML exits 2."""
    page = build_tree(work / "page")
    path = page.page("fr", "index.md", "# Aide\n")
    path.write_bytes(b"# Aide\n\nOuvrir\xe9?\n")
    run = text_of(tools, page)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "index.md" in run.stderr

    catalogue = build_tree(work / "catalogue")
    folder = catalogue.root / CAT_DIR
    folder.mkdir(parents=True)
    (folder / "pixelart_fr.ts").write_bytes(b"<TS><context>")
    run = text_of(tools, catalogue)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "pixelart_fr.ts" in run.stderr


# --------------------------------------------------------------------------- #
# The endonym table the script loads by path from the root it is given.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "absent-module-crashes",
        ty(
            "    if spec is None or spec.loader is None or not os.path.isfile(path):\n",
            "    if spec is None or spec.loader is None:\n",
        ),
    ),
)
def case_a_root_without_the_endonym_module_exits_2_naming_it(
    tools: Tools, work: Path
) -> None:
    """No ``language_names.py`` under the root: exit 2, the file named.

    The control is the same root once the module is there: exit 0. Both the
    folders and the ``--worklist`` input need the table, so both exit 2.
    """
    bare = bare_tree(work / "bare")
    folder = bare.root / CAT_DIR
    put(bare.root, CAT_DIR, "fr", [Msg("Open?", f"Ouvrir{NBSP}?")])
    assert folder.is_dir()
    run = text_of(tools, bare)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "cannot load" in run.stderr and "language_names.py" in run.stderr
    assert run.stdout == ""
    path = write_worklist(bare, "fr", [entry("Open?", [f"Ouvrir{NBSP}?"])])
    run = text_of(tools, bare, "--worklist", str(path))
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "language_names.py" in run.stderr

    control = build_tree(work / "control")
    control.catalogue("fr", [Msg("Open?", f"Ouvrir{NBSP}?")])
    run, payload = scan(tools, control)
    assert_clean(run, payload)


# --------------------------------------------------------------------------- #
# French number and unit (fr-num-unit; fr.md 5.1, 5.4).
# --------------------------------------------------------------------------- #
DEGREE = "\u00b0"
UNIT_OCTET = "octet/octets/octet(s)"
UNIT_MILLI = "milliseconde/millisecondes/milliseconde(s)"
UNIT_SECOND = "seconde/secondes/seconde(s)"
UNIT_FRAMES = "image(s) par seconde"

#: The unit list the rule prints, in the order the script defines it.
NUM_UNIT_LABELS = [
    "px",
    "ms",
    "mm",
    "cm",
    "PPI",
    "%",
    DEGREE,
    UNIT_OCTET,
    "Ko",
    "Mo",
    "Go",
    UNIT_MILLI,
    UNIT_SECOND,
    UNIT_FRAMES,
]

#: The exact source line of each entry of ``UNITS`` (one mutant drops each).
UNIT_SOURCE_LINES = (
    '    ("px", r"px"),\n',
    '    ("ms", r"ms"),\n',
    '    ("mm", r"mm"),\n',
    '    ("cm", r"cm"),\n',
    '    ("PPI", r"PPI"),\n',
    '    ("%", r"%"),\n',
    r'    ("\u00b0", r"\u00b0"),' + "\n",
    '    ("octet/octets/octet(s)", r"octets?(?:\\(s\\))?"),\n',
    '    ("Ko", r"Ko"),\n',
    '    ("Mo", r"Mo"),\n',
    '    ("Go", r"Go"),\n',
    '    ("milliseconde/millisecondes/milliseconde(s)",'
    ' r"millisecondes?(?:\\(s\\))?"),\n',
    '    ("seconde/secondes/seconde(s)", r"secondes?(?:\\(s\\))?"),\n',
    '    ("image(s) par seconde", r"images?(?:\\(s\\))? par seconde"),\n',
)

#: (unit label, number, unit text): every entry of ``UNITS`` at least once, in
#: each spelling its pattern accepts, and every kind of number the rule takes.
UNIT_SAMPLES = [
    ("px", "5", "px"),
    ("ms", "250", "ms"),
    ("mm", "12", "mm"),
    ("cm", "3,5", "cm"),
    ("PPI", "300", "PPI"),
    ("%", "50", "%"),
    (DEGREE, "90", DEGREE),
    (UNIT_OCTET, "1", "octet"),
    (UNIT_OCTET, "2", "octets"),
    (UNIT_OCTET, "3", "octet(s)"),
    ("Ko", "4", "Ko"),
    ("Mo", "5", "Mo"),
    ("Go", "6", "Go"),
    (UNIT_MILLI, "7", "milliseconde"),
    (UNIT_MILLI, "8", "millisecondes"),
    (UNIT_MILLI, "9", "milliseconde(s)"),
    (UNIT_SECOND, "1", "seconde"),
    (UNIT_SECOND, "2", "secondes"),
    (UNIT_SECOND, "3", "seconde(s)"),
    (UNIT_FRAMES, "30", "images par seconde"),
    (UNIT_FRAMES, "1", "image par seconde"),
    (UNIT_FRAMES, "5", "image(s) par seconde"),
    ("px", "1.5", "px"),
    ("px", "%n", "px"),
    ("px", "%1", "px"),
    ("px", "%L2", "px"),
    ("px", "{width}", "px"),
    ("PPI", "{0:.0f}", "PPI"),
]

#: Text after a number that is NOT a unit: a count noun, or a word that only
#: begins like a unit. None of them is a pair, with any space.
NOT_A_UNIT = ["5 pxl", "5 msg", "%n images", "3 points", "8 Gomme"]

NUM_UNIT_MESSAGE = "Size: 5 px"
ORDINARY = " "
DOUBLED = "  "


def gap_detail(number: str, unit: str, shown: str) -> str:
    """Return the finding text of a wrong space between ``number`` and ``unit``."""
    return f"{number} {unit}: {shown} between number and unit (needs one U+00A0)"


def num_unit_line(
    surface: str, examined: int, word: str, pairs: int | None, findings: int = 0
) -> str:
    """Return the text-report line of the ``fr-num-unit`` unit of ``surface``."""
    split = "" if pairs is None else f" (pairs {pairs})"
    return (
        f"fr-num-unit [{surface}] fr: examined {examined} {word}{split}, "
        f"{findings} finding(s)"
    )


def forms_entry(source: str, translation) -> dict:
    """Build a worklist entry; a worklist holds its forms as a list."""
    forms = translation if isinstance(translation, list) else [translation]
    return entry(source, forms, numerus=len(forms) > 1)


def french_runs(
    tools: Tools, work: Path, label: str, rows: list
) -> list[tuple[str, Tree, list[str], ScriptRun, dict]]:
    """Scan the same French rows as a catalogue and as a worklist.

    ``rows`` holds ``(source, translation)``; a list of forms makes the entry
    a numerus one. Returns ``(surface, tree, extra arguments, run, report)``.
    """
    runs: list[tuple[str, Tree, list[str], ScriptRun, dict]] = []
    folder = build_tree(work / f"{label}-catalogue")
    folder.catalogue(
        "fr", [Msg(src, tr, numerus=isinstance(tr, list)) for src, tr in rows]
    )
    run, payload = scan(tools, folder)
    runs.append(("catalogue", folder, [], run, payload))
    listing = build_tree(work / f"{label}-worklist")
    path = write_worklist(
        listing,
        "fr",
        [forms_entry(src, tr) for src, tr in rows],
    )
    args = ["--worklist", str(path)]
    run, payload = scan(tools, listing, *args)
    runs.append(("worklist", listing, args, run, payload))
    return runs


def num_unit_rows(payload: dict) -> list:
    """Return the report rows of the ``fr-num-unit`` rule, whatever the surface."""
    return [r for r in payload["rules"] if r["rule"] == "fr-num-unit"]


@REGISTRY.regression(
    mutant(
        "rule-not-run-on-entries",
        ty('    target = units["fr-num-unit"]\n', "    target = 0\n"),
    ),
    mutant(
        "entry-counted-per-form",
        ty(
            '        target["examined"] += 1\n'
            "        for form in forms:\n"
            "            pairs, problems = num_unit_problems("
            "markup_free(form, catalogues))\n",
            "        for form in forms:\n"
            '            target["examined"] += 1\n'
            "            pairs, problems = num_unit_problems("
            "markup_free(form, catalogues))\n",
        ),
    ),
    mutant(
        "pairs-are-the-denominator",
        ty(
            '        target["examined"] += 1\n'
            "        for form in forms:\n"
            "            pairs, problems = num_unit_problems("
            "markup_free(form, catalogues))\n"
            '            target["sub"]["pairs"] = target["sub"].get("pairs", 0)'
            " + pairs\n",
            "        for form in forms:\n"
            "            pairs, problems = num_unit_problems("
            "markup_free(form, catalogues))\n"
            '            target["sub"]["pairs"] = target["sub"].get("pairs", 0)'
            " + pairs\n"
            '            target["examined"] += pairs\n',
        ),
    ),
    mutant(
        "pairs-keep-the-last-form",
        ty(
            '            target["sub"]["pairs"] = target["sub"].get("pairs", 0)'
            " + pairs\n",
            '            target["sub"]["pairs"] = pairs\n',
        ),
    ),
    mutant(
        "pairs-not-printed",
        ty(
            '        if row["rule"] in ("fr-num-unit", *ZH_RULE_NAMES) and parts:\n',
            '        if row["rule"] in ZH_RULE_NAMES and parts:\n',
        ),
    ),
    mutant(
        "catalogue-says-pages",
        ty(
            '            unit = "page(s)" if row["surface"] == "guide"'
            ' else "entr(ies)"\n',
            '            unit = "page(s)"\n',
        ),
    ),
    mutant(
        "rule-not-limited-to-french",
        ty(
            '        "fr-num-unit": unit("fr-num-unit", "fr"),\n',
            '        "fr-num-unit": tally.unit("fr-num-unit", surface, language),\n',
        ),
    ),
    mutant(
        "units-key-always-present",
        ty(
            '    if any(r["rule"] == "fr-num-unit" for r in rows):\n',
            "    if True:\n",
        ),
    ),
)
def case_the_french_number_unit_rule_examines_entries_and_counts_pairs_apart(
    tools: Tools, work: Path
) -> None:
    """The examined count is the French entries scanned; the pairs are a sub-count.

    A batch with entries and no number+unit pair is clean (exit 0), so a French
    batch with no unit is not blind. A numerus entry counts once however many
    forms it has, and its pairs are summed over its forms; the count nouns
    ``%n images`` and ``%n points`` are not units. The text row names the
    entries and prints the pairs. No other language gets the rule.
    """
    quiet = [
        ("Open?", f"Ouvrir{NBSP}?"),
        ("%n images", ["%n image", "%n images"]),
        ("%n points", ["%n point", "%n points"]),
    ]
    for surface, tree, args, run, payload in french_runs(tools, work, "none", quiet):
        assert_clean(run, payload)
        unit = row(payload, "fr-num-unit", surface, "fr")
        assert unit["examined"] == 3, (surface, unit)
        assert unit["sub_counts"] == {"pairs": 0}, (surface, unit)
        assert unit["nothing_examined"] is False, (surface, unit)
        assert unit["findings"] == [], (surface, unit)
        text = text_of(tools, tree, *args)
        assert text.returncode == 0, (surface, text.stdout, text.stderr)
        assert num_unit_line(surface, 3, "entr(ies)", 0) in text.stdout, text.stdout

    held = [
        (NUM_UNIT_MESSAGE, f"Taille{NBSP}: 5{NBSP}px"),
        ("%n s", [f"%n{NBSP}seconde", f"%n{NBSP}secondes"]),
    ]
    for surface, tree, args, run, payload in french_runs(tools, work, "held", held):
        assert_clean(run, payload)
        unit = row(payload, "fr-num-unit", surface, "fr")
        assert unit["examined"] == 2, (surface, unit)
        assert unit["sub_counts"] == {"pairs": 3}, (surface, unit)
        assert unit["findings"] == [], (surface, unit)
        assert payload.get("fr_num_unit_units") == NUM_UNIT_LABELS
        # The rules that were there are counted as before.
        marks = row(payload, "fr-nbsp", surface, "fr")
        assert marks["sub_counts"] == {"guillemet sides": 0, "marks": 1}, marks
        assert row(payload, "ellipsis", surface, "fr")["examined"] == 2
        stray = row(payload, "no-u202f", surface, "fr")
        assert stray["examined"] == (1 if surface == "catalogue" else 2), stray
        assert payload["examined_total"] == sum(r["examined"] for r in payload["rules"])
        text = text_of(tools, tree, *args)
        assert num_unit_line(surface, 2, "entr(ies)", 3) in text.stdout, text.stdout

    # Another language adds no row, no key and no line, spaces or not.
    other = build_tree(work / "de")
    other.catalogue("de", [Msg("Size", "Gr\u00f6\u00dfe 5 px")])
    other.page("de", "index.md", "# Hilfe\n\nBreite 5 px.\n")
    other.chinese_page()
    run, payload = scan(tools, other)
    assert_clean(run, payload)
    assert num_unit_rows(payload) == [], payload["rules"]
    assert "fr_num_unit_units" not in payload
    assert "fr-num-unit" not in text_of(tools, other).stdout
    listing = build_tree(work / "de-worklist")
    path = write_worklist(listing, "de", [entry("Size", ["Gr\u00f6\u00dfe 5 px"])])
    run, payload = scan(tools, listing, "--worklist", str(path))
    assert_clean(run, payload)
    assert num_unit_rows(payload) == [] and "fr_num_unit_units" not in payload


@REGISTRY.regression(
    mutant(
        "blind-rule-passes",
        ty(
            "    code = EXIT_FINDINGS if total or"
            " blind or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant(
        "blind-rule-unnamed",
        ty('        if row["nothing_examined"]:\n', "        if False:\n"),
    ),
    mutant(
        "empty-not-detected",
        ty('        empty = unit["examined"] == 0\n', "        empty = False\n"),
    ),
    mutant(
        "unfinished-examined",
        ty(
            '        if message.kind == "unfinished" or not forms or not all(forms):\n',
            "        if not forms or not all(forms):\n",
        ),
    ),
    mutant(
        "partial-entry-examined",
        ty(
            "        or not all(isinstance(f, str) and f for f in forms)\n",
            "        or False\n",
        ),
    ),
)
def case_a_french_batch_with_no_finished_entry_examines_no_number_unit(
    tools: Tools, work: Path
) -> None:
    """No finished French entry: ``fr-num-unit`` examined 0, says so, exit 1.

    An unfinished message, an unfilled worklist entry and a partly filled
    numerus entry are not entries scanned; beside a finished one they leave
    the count at one and the run clean.
    """
    unfinished = [Msg("Open?", "Ouvrir", kind="unfinished")]
    run, payload = only_catalogue(tools, work, "unfinished", "fr", unfinished)
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "fr-num-unit", "catalogue", "fr")
    assert unit["examined"] == 0 and unit["sub_counts"] == {}, unit
    assert unit["nothing_examined"] is True, unit
    tree = build_tree(work / "unfinished-text")
    tree.catalogue("fr", unfinished)
    text = text_of(tools, tree)
    line = num_unit_line("catalogue", 0, "entr(ies)", None)
    assert f"{line}\n  nothing examined\n" in text.stdout, text.stdout

    unfilled = build_tree(work / "unfilled")
    path = write_worklist(unfilled, "fr", [entry("Open?", [""]), entry("Save?", [""])])
    run, payload = scan(tools, unfilled, "--worklist", str(path))
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "fr-num-unit", "worklist", "fr")
    assert unit["examined"] == 0 and unit["nothing_examined"] is True, unit
    text = text_of(tools, unfilled, "--worklist", str(path))
    line = num_unit_line("worklist", 0, "entr(ies)", None)
    assert f"{line}\n  nothing examined\n" in text.stdout, text.stdout

    beside = [
        Msg("Open?", f"Ouvrir{NBSP}?"),
        Msg("Close", "Fermer", kind="unfinished"),
    ]
    run, payload = only_catalogue(tools, work, "beside", "fr", beside)
    assert_clean(run, payload)
    unit = row(payload, "fr-num-unit", "catalogue", "fr")
    assert unit["examined"] == 1 and unit["sub_counts"] == {"pairs": 0}, unit

    tree = build_tree(work / "beside-worklist")
    listing = [
        entry("Open?", [f"Ouvrir{NBSP}?"]),
        entry("%n s", ["%n seconde", ""], numerus=True),
        entry("Save", [""]),
    ]
    path = write_worklist(tree, "fr", listing)
    run, payload = scan(tools, tree, "--worklist", str(path))
    assert_clean(run, payload)
    unit = row(payload, "fr-num-unit", "worklist", "fr")
    assert unit["examined"] == 1 and unit["sub_counts"] == {"pairs": 0}, unit


@REGISTRY.regression(
    mutant(
        "ordinary-space-passes",
        ty("        if gap == NBSP:\n", '        if gap == NBSP or gap == " ":\n'),
    ),
    mutant(
        "narrow-space-passes",
        ty("        if gap == NBSP:\n", "        if gap in (NBSP, NARROW_NBSP):\n"),
    ),
    mutant(
        "doubled-space-passes",
        ty("        if gap == NBSP:\n", "        if gap == NBSP or len(gap) > 1:\n"),
    ),
    mutant(
        "doubled-space-misnamed",
        ty(
            '        shown = "more than one space character"\n',
            "        shown = _space_name(gap[0])\n",
        ),
    ),
    mutant(
        "ordinary-space-not-matched",
        ty('(?P<gap>[ " + NBSP', '(?P<gap>[" + NBSP'),
    ),
    mutant(
        "narrow-space-not-matched",
        ty('" + NBSP + NARROW_NBSP + r"]+)"', '" + NBSP + r"]+)"'),
    ),
    mutant(
        "pairs-not-counted",
        ty(
            '            target["sub"]["pairs"] = target["sub"].get("pairs", 0)'
            " + pairs\n",
            '            target["sub"]["pairs"] = target["sub"].get("pairs", 0)\n',
        ),
    ),
)
def case_a_number_and_its_unit_need_exactly_one_no_break_space(
    tools: Tools, work: Path
) -> None:
    """``5 px`` with U+0020, U+202F or a doubled space is a finding; U+00A0 is not.

    On the catalogue and the worklist: one finding per pair, named by the
    pair and by the kind of space, at the entry that holds it.
    """
    planted = [
        ("ordinary", ORDINARY, "an ordinary space"),
        ("narrow", NNBSP, "U+202F"),
        ("doubled", DOUBLED, "more than one space character"),
    ]
    wheres = {
        "catalogue": f"pixelart_fr.ts [Panel] {NUM_UNIT_MESSAGE}",
        "worklist": f"w.json entry 1 [Panel] {NUM_UNIT_MESSAGE}",
    }
    for label, gap, shown in planted:
        rows = [(NUM_UNIT_MESSAGE, f"Taille{NBSP}: 5{gap}px")]
        for surface, tree, args, run, payload in french_runs(tools, work, label, rows):
            case = (label, surface)
            assert run.returncode == 1, (case, run.stdout, run.stderr)
            unit = row(payload, "fr-num-unit", surface, "fr")
            detail = gap_detail("5", "px", shown)
            assert details(unit) == [detail], (case, unit)
            assert unit["findings"][0]["where"] == wheres[surface], (case, unit)
            assert unit["examined"] == 1 and unit["sub_counts"] == {"pairs": 1}, case
            # A U+202F is also a finding of the rule that bans it, once.
            expected = 2 if label == "narrow" else 1
            assert payload["findings_total"] == expected, (case, payload["rules"])
            text = text_of(tools, tree, *args)
            assert text.returncode == 1, (case, text.stdout, text.stderr)
            assert f"  {wheres[surface]}: {detail}\n" in text.stdout, text.stdout
            line = num_unit_line(surface, 1, "entr(ies)", 1, findings=1)
            assert line in text.stdout, (case, text.stdout)

    clean = [(NUM_UNIT_MESSAGE, f"Taille{NBSP}: 5{NBSP}px")]
    for surface, _tree, _args, run, payload in french_runs(tools, work, "ok", clean):
        assert_clean(run, payload)
        unit = row(payload, "fr-num-unit", surface, "fr")
        assert unit["findings"] == [] and unit["sub_counts"] == {"pairs": 1}, unit

    two = [("Size 5 px, delay 3 ms", "Taille 5 px, d\u00e9lai 3 ms")]
    for surface, _tree, _args, run, payload in french_runs(tools, work, "two", two):
        assert run.returncode == 1, (surface, run.stdout, run.stderr)
        unit = row(payload, "fr-num-unit", surface, "fr")
        assert details(unit) == [
            gap_detail("5", "px", "an ordinary space"),
            gap_detail("3", "ms", "an ordinary space"),
        ], (surface, unit)
        assert unit["examined"] == 1 and unit["sub_counts"] == {"pairs": 2}, unit


@REGISTRY.regression(
    mutant(
        "guide-says-entries",
        ty(
            '            unit = "page(s)" if row["surface"] == "guide"'
            ' else "entr(ies)"\n',
            '            unit = "entr(ies)"\n',
        ),
    ),
    mutant("guide-not-scanned", ty('    if lang == "fr":\n', '    if lang == "xx":\n')),
    mutant(
        "guide-rule-not-limited-to-french",
        ty('    if lang == "fr":\n', '    if lang in ("fr", "de"):\n'),
    ),
    mutant(
        "guide-pages-are-pairs",
        ty(
            '        unit["examined"] += 1\n'
            "        pairs, problems = num_unit_problems(prose)\n",
            "        pairs, problems = num_unit_problems(prose)\n"
            '        unit["examined"] += pairs\n',
        ),
    ),
    mutant(
        "guide-pairs-not-counted",
        ty(
            '        unit["sub"]["pairs"] = unit["sub"].get("pairs", 0) + pairs\n',
            '        unit["sub"]["pairs"] = unit["sub"].get("pairs", 0)\n',
        ),
    ),
    mutant(
        "guide-line-wrong",
        ty(
            '        unit["sub"]["pairs"] = unit["sub"].get("pairs", 0) + pairs\n'
            "        for offset, detail in problems:\n"
            '            tally.add(unit, f"{rel}:{_line_of(prose, offset)}", detail)\n',
            '        unit["sub"]["pairs"] = unit["sub"].get("pairs", 0) + pairs\n'
            "        for offset, detail in problems:\n"
            '            tally.add(unit, f"{rel}:{_line_of(prose, 0)}", detail)\n',
        ),
    ),
    mutant("code-span-examined", ty('    re.compile(r"`[^`\\n]*`"),\n', "")),
    mutant("link-target-examined", ty('    re.compile(r"\\]\\([^)\\n]*\\)"),\n', "")),
    mutant(
        "fenced-block-examined",
        ty(
            '    re.compile(r"^(```|~~~).*?^\\1[^\\n]*$", re.DOTALL | re.MULTILINE),\n',
            "",
        ),
    ),
)
def case_the_french_guide_counts_pages_and_names_the_line_of_a_number_unit(
    tools: Tools, work: Path
) -> None:
    """On the guide the examined count is pages; the pairs are a sub-count.

    A French page with no unit is examined and clean; a pair spelled with
    U+0020 is a finding at ``<page>:<line>``; a pair inside a code span, a link
    target or a fenced block is not prose. A non-French tree has no such row.
    """
    quiet = build_tree(work / "quiet")
    quiet.page("fr", "index.md", f"# Aide\n\nOuvrir le fichier{NBSP}?\n")
    quiet.page("fr", "tools/pen.md", f"# Crayon\n\nFermer{NBSP}!\n")
    quiet.chinese_page()
    run, payload = scan(tools, quiet)
    assert_clean(run, payload)
    unit = row(payload, "fr-num-unit", "guide", "fr")
    assert unit["examined"] == 2 and unit["files"] == 2, unit
    assert unit["sub_counts"] == {"pairs": 0}, unit
    assert unit["nothing_examined"] is False and unit["findings"] == [], unit
    text = text_of(tools, quiet)
    assert num_unit_line("guide", 2, "page(s)", 0) in text.stdout, text.stdout

    held = build_tree(work / "held")
    held.page("fr", "index.md", f"# Aide\n\nEpaisseur{NBSP}: 5{NBSP}px.\n")
    held.page("fr", "tools/code.md", f"# Code\n\nTapez `5 px` ici{NBSP}!\n")
    held.page("fr", "tools/link.md", "# Lien\n\nVoir [la page](a 5 px b).\n")
    held.page("fr", "tools/fence.md", "# Bloc\n\n```\nlargeur 5 px\n```\n")
    held.chinese_page()
    run, payload = scan(tools, held)
    assert_clean(run, payload)
    unit = row(payload, "fr-num-unit", "guide", "fr")
    assert unit["examined"] == 4 and unit["sub_counts"] == {"pairs": 1}, unit
    assert payload.get("fr_num_unit_units") == NUM_UNIT_LABELS
    text = text_of(tools, held)
    assert num_unit_line("guide", 4, "page(s)", 1) in text.stdout, text.stdout

    planted = build_tree(work / "planted")
    planted.page("fr", "index.md", f"# Aide\n\nTaille{NBSP}: 5 px\n")
    planted.page(
        "fr", "z.md", f"# Zone\n\nLargeur{NBSP}: 2{NBSP}cm\n\nHauteur{NBSP}: 4  mm\n"
    )
    run, payload = scan(tools, planted)
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "fr-num-unit", "guide", "fr")
    assert unit["examined"] == 2 and unit["sub_counts"] == {"pairs": 3}, unit
    assert details(unit) == [
        gap_detail("5", "px", "an ordinary space"),
        gap_detail("4", "mm", "more than one space character"),
    ], unit
    assert [f["where"] for f in unit["findings"]] == ["fr/index.md:3", "fr/z.md:5"]
    text = text_of(tools, planted)
    assert text.returncode == 1, (text.stdout, text.stderr)
    line = num_unit_line("guide", 2, "page(s)", 3, findings=2)
    assert line in text.stdout, text.stdout
    assert f"  fr/index.md:3: {unit['findings'][0]['detail']}\n" in text.stdout

    other = build_tree(work / "other")
    other.page("de", "index.md", "# Hilfe\n\nBreite 5 px.\n")
    other.chinese_page()
    run, payload = scan(tools, other)
    assert_clean(run, payload)
    assert num_unit_rows(payload) == [], payload["rules"]
    assert "fr_num_unit_units" not in payload


def unit_removed(label: str, line: str):
    """Return the mutant that deletes one entry of the script's ``UNITS``."""
    return mutant(f"unit-dropped-{label}", ty(line, ""))


@REGISTRY.regression(
    *(
        unit_removed(str(number), line)
        for number, line in enumerate(UNIT_SOURCE_LINES, start=1)
    ),
    mutant(
        "placeholder-not-a-number",
        ty(
            r'    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|%L?(?:n|[1-9])|\{[^{}\n]*\})"'
            + "\n",
            r'    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|\{[^{}\n]*\})"' + "\n",
        ),
    ),
    mutant(
        "field-not-a-number",
        ty(
            r'    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|%L?(?:n|[1-9])|\{[^{}\n]*\})"'
            + "\n",
            r'    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|%L?(?:n|[1-9]))"' + "\n",
        ),
    ),
    mutant(
        "decimal-not-a-number",
        ty(
            r'    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|%L?(?:n|[1-9])|\{[^{}\n]*\})"'
            + "\n",
            r'    r"(?P<num>(?<![\w%{.,])\d+|%L?(?:n|[1-9])|\{[^{}\n]*\})"' + "\n",
        ),
    ),
    mutant(
        "unit-boundary-dropped",
        ty(
            r'    r"(?P<unit>(?:" + _UNIT_ALTERNATIVES + r")(?![\w]))"' + "\n",
            r'    r"(?P<unit>(?:" + _UNIT_ALTERNATIVES + r"))"' + "\n",
        ),
    ),
    mutant(
        "count-noun-is-a-unit",
        ty('    ("px", r"px"),\n', '    ("px", r"px"),\n    ("image", r"images?"),\n'),
    ),
    mutant(
        "points-is-a-unit",
        ty('    ("px", r"px"),\n', '    ("px", r"px"),\n    ("point", r"points?"),\n'),
    ),
    mutant(
        "units-key-missing",
        ty(
            '        report["fr_num_unit_units"] = '
            "[label for label, _pattern in UNITS]\n",
            "        pass\n",
        ),
    ),
    mutant(
        "units-line-never-printed",
        ty(
            '    if any(row["rule"] == "fr-num-unit" for row in report["rules"]):\n',
            "    if False:\n",
        ),
    ),
    mutant(
        "units-line-always-printed",
        ty(
            '    if any(row["rule"] == "fr-num-unit" for row in report["rules"]):\n',
            "    if True:\n",
        ),
    ),
)
def case_every_listed_unit_and_number_form_is_matched_and_no_count_noun_is(
    tools: Tools, work: Path
) -> None:
    """Each entry of ``UNITS`` is a unit after a digit run, a placeholder or a field.

    The unit list and its count are printed with the rule and exposed as the
    ``fr_num_unit_units`` key, for French only. A count noun (``%n images``,
    ``3 points``) and a word that only begins like a unit (``5 pxl``) are not
    pairs, with any space.
    """
    assert set(label for label, _n, _u in UNIT_SAMPLES) == set(NUM_UNIT_LABELS)
    sentinel = [("Open?", f"Ouvrir{NBSP}?")]
    absent = [
        (f"Not a unit {n}", f"Valeur {text}") for n, text in enumerate(NOT_A_UNIT)
    ]

    def rows(gap: str) -> list:
        """Return the sentinel, one row per sample and the non-units."""
        samples = [
            (f"Sample {n}", f"Valeur {number}{gap}{text}")
            for n, (_label, number, text) in enumerate(UNIT_SAMPLES)
        ]
        return sentinel + samples + absent

    tree = build_tree(work / "wrong")
    path = write_worklist(
        tree, "fr", [entry(src, [tr]) for src, tr in rows(ORDINARY)], "wrong.json"
    )
    run, payload = scan(tools, tree, "--worklist", str(path))
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "fr-num-unit", "worklist", "fr")
    wanted = [
        gap_detail(number, text, "an ordinary space")
        for _label, number, text in UNIT_SAMPLES
    ]
    assert details(unit) == wanted, details(unit)
    assert unit["examined"] == len(rows(ORDINARY)), unit
    assert unit["sub_counts"] == {"pairs": len(UNIT_SAMPLES)}, unit
    assert payload.get("fr_num_unit_units") == NUM_UNIT_LABELS
    text = text_of(tools, tree, "--worklist", str(path))
    header = f"fr-num-unit units ({len(NUM_UNIT_LABELS)}): " + ", ".join(
        NUM_UNIT_LABELS
    )
    assert header + "\n" in text.stdout, text.stdout

    tree = build_tree(work / "right")
    path = write_worklist(
        tree, "fr", [entry(src, [tr]) for src, tr in rows(NBSP)], "right.json"
    )
    run, payload = scan(tools, tree, "--worklist", str(path))
    assert_clean(run, payload)
    unit = row(payload, "fr-num-unit", "worklist", "fr")
    assert unit["findings"] == [], unit
    assert unit["sub_counts"] == {"pairs": len(UNIT_SAMPLES)}, unit

    other = build_tree(work / "other")
    other.catalogue("de", [Msg("Size", "Gr\u00f6\u00dfe 5 px")])
    run, payload = scan(tools, other)
    assert_clean(run, payload)
    assert "fr_num_unit_units" not in payload
    assert "fr-num-unit" not in text_of(tools, other).stdout


# --------------------------------------------------------------------------- #
# Simplified Chinese guide pages: the four half-width space rules.
#
# Each example below is one fixture page: line 3 holds the text, the run covers
# the guide surface, and the page's findings are judged rule by rule. A space
# that matters is written with a name (NBSP, IDEOGRAPHIC, DOUBLED); an ordinary
# space is an ordinary space. ``\n`` in a text is a soft line break.
# --------------------------------------------------------------------------- #
IDEOGRAPHIC = "\u3000"
FULLWIDTH_THREE = "\uff13"
FULLWIDTH_RGBA = "\uff32\uff27\uff22\uff21"
FULLWIDTH_CTRL = "\uff23\uff54\uff52\uff4c"
ZH_HEAD = "# \u6807\u9898\n\n"
ZH_PAGE = "page.md"
ZH_WHERE = f"{ZH_LANGUAGE}/{ZH_PAGE}"

ZH_HAN_LATIN = "zh-space-han-latin"
ZH_MARK_LATIN = "zh-space-mark-latin"
ZH_UNIT = "zh-num-unit-closed"
ZH_SYMBOL = "zh-space-symbol"
ZH_RULE_ROWS = (ZH_HAN_LATIN, ZH_MARK_LATIN, ZH_UNIT, ZH_SYMBOL)

ZH_UNIT_LIST = ["px"]
ZH_TRAILING_LIST = ["%", "\u00b0"]
ZH_OPENING_LIST = ["\u00b1"]

#: A backslash and the letter ``u``: how the script's own source spells a code
#: point. The anchors that quote that source join it to the digits, so that this
#: file holds no word-backslash-word text for the path-portability check to read
#: as a path separator.
ESCAPE_U = "\\u"

NOTHING_BETWEEN = "nothing stands between them"
MORE_THAN_ONE = "more than one space character"
HIDES = "the guide hides"
SHOWN_AS_SPACE = "shows as a space"


class Found(NamedTuple):
    """A finding an example expects: its rule and the words of its detail, in order."""

    rule: str
    words: tuple[str, ...]


class Example(NamedTuple):
    """One example: line 3 of the page, its findings and the edges it must count."""

    text: str
    found: tuple[Found, ...]
    counts: tuple[int, ...]


class Scenario(NamedTuple):
    """What a group of examples measures: a rule, its sub-counts and printed lists.

    ``summed`` says that the examples give one number, the total of the rule's
    sub-counts, instead of one number per sub-count.
    """

    rule: str
    parts: tuple[str, ...]
    summed: bool = False
    lists: tuple[tuple[str, list[str]], ...] = ()


def ok(text: str, *counts: int) -> Example:
    """Build an example the rules accept, with the edges they must count."""
    return Example(text, (), counts)


def bad(text: str, counts: tuple[int, ...], *found: Found) -> Example:
    """Build an example that exits 1 with exactly ``found``."""
    return Example(text, found, counts)


def at(rule: str, *words: str) -> Found:
    """Build a finding of ``rule`` whose detail holds ``words``, in this order."""
    return Found(rule, words)


def in_order(detail: str, words: tuple[str, ...]) -> bool:
    """Return whether every word occurs in ``detail``, each after the one before."""
    start = 0
    for word in words:
        start = detail.find(word, start)
        if start < 0:
            return False
        start += len(word)
    return True


# Simplified Chinese guide pages put one space between a Han character and a
# Latin letter or a digit. Counts: the edges.
HAN_LATIN_SCENARIO = Scenario(ZH_HAN_LATIN, ("edges",))
HAN_LATIN_EXAMPLES = [
    ok("使用 **F1** 键", 2),
    ok("RGBA 值", 1),
    ok("共 3 个", 2),
    ok("共\n3 个", 2),
    ok("使用 `RGBA` 值", 2),
    bad(
        "使用**F1**键",
        (2,),
        at(ZH_HAN_LATIN, "用", "F", NOTHING_BETWEEN),
        at(ZH_HAN_LATIN, "1", "键", NOTHING_BETWEEN),
    ),
    bad(f"RGBA{DOUBLED}值", (1,), at(ZH_HAN_LATIN, "A", "值", MORE_THAN_ONE)),
    bad(f"RGBA{NBSP}值", (1,), at(ZH_HAN_LATIN, "A", "值", "U+00A0")),
    bad(f"RGBA{IDEOGRAPHIC}值", (1,), at(ZH_HAN_LATIN, "A", "值", "U+3000")),
    bad(
        "使用`RGBA`值",
        (2,),
        at(ZH_HAN_LATIN, "用", "R", NOTHING_BETWEEN),
        at(ZH_HAN_LATIN, "A", "值", NOTHING_BETWEEN),
    ),
    ok(f"共 {FULLWIDTH_THREE} 个", 2),
    ok(f"使用 {FULLWIDTH_RGBA} 值", 2),
    bad(
        f"共{FULLWIDTH_THREE}个",
        (2,),
        at(ZH_HAN_LATIN, "共", FULLWIDTH_THREE, NOTHING_BETWEEN),
        at(ZH_HAN_LATIN, FULLWIDTH_THREE, "个", NOTHING_BETWEEN),
    ),
    bad(
        f"共\n{FULLWIDTH_THREE} 个",
        (2,),
        at(ZH_HAN_LATIN, "共", FULLWIDTH_THREE, HIDES),
    ),
]

# ... between a full-width mark and a Latin letter or a digit. Counts: the mark
# edges and the symbol edges together.
MARK_LATIN_SCENARIO = Scenario(
    ZH_MARK_LATIN, ("mark edges", "symbol edges"), summed=True
)
MARK_LATIN_EXAMPLES = [
    ok("撤销， Ctrl+Y 重做", 1),
    ok("颜色模式（ RGBA ）", 2),
    ok("“ RGBA ”", 2),
    ok("第 1 、 2 步", 2),
    ok("撤销， **Ctrl+Y**", 1),
    ok(f"撤销， {FULLWIDTH_CTRL}", 1),
    ok("的，然后", 0),
    ok("选择 ‘RGBA’ 模式", 0),
    bad("撤销，Ctrl+Y 重做", (1,), at(ZH_MARK_LATIN, "，", "C", NOTHING_BETWEEN)),
    bad(
        "颜色模式（RGBA）",
        (2,),
        at(ZH_MARK_LATIN, "（", "R", NOTHING_BETWEEN),
        at(ZH_MARK_LATIN, "A", "）", NOTHING_BETWEEN),
    ),
    bad(
        "（3）",
        (2,),
        at(ZH_MARK_LATIN, "（", "3", NOTHING_BETWEEN),
        at(ZH_MARK_LATIN, "3", "）", NOTHING_BETWEEN),
    ),
    bad(f"撤销，{NBSP}Ctrl+Y", (1,), at(ZH_MARK_LATIN, "，", "C", "U+00A0")),
    bad(f"撤销，{IDEOGRAPHIC}Ctrl+Y", (1,), at(ZH_MARK_LATIN, "，", "C", "U+3000")),
    bad(f"撤销，{DOUBLED}Ctrl+Y", (1,), at(ZH_MARK_LATIN, "，", "C", MORE_THAN_ONE)),
    bad("撤销，`Ctrl+Y`", (1,), at(ZH_MARK_LATIN, "，", "C", NOTHING_BETWEEN)),
    bad(
        "撤销，\nCtrl+Y 重做",
        (1,),
        at(ZH_MARK_LATIN, "，", "C", HIDES, "clause 4"),
    ),
    bad(
        f"撤销，\n{FULLWIDTH_CTRL}",
        (1,),
        at(ZH_MARK_LATIN, "，", FULLWIDTH_CTRL[0], HIDES, "clause 2"),
    ),
    ok("设为 100% ，然后", 1),
    ok("（ 100% ）", 2),
    bad("设为 100%，然后", (1,), at(ZH_MARK_LATIN, "%", "，", NOTHING_BETWEEN)),
    bad(
        "（±5）",
        (2,),
        at(ZH_MARK_LATIN, "（", "±", NOTHING_BETWEEN),
        at(ZH_MARK_LATIN, "5", "）", NOTHING_BETWEEN),
    ),
]

# ... a number is written closed against a unit of the printed list (px). Counts:
# the number+unit pairs.
UNIT_SCENARIO = Scenario(
    ZH_UNIT, ("pairs",), lists=(("zh_num_unit_units", ZH_UNIT_LIST),)
)
UNIT_EXAMPLES = [
    ok("宽度 3px", 1),
    ok("宽度 1.5px", 1),
    ok("宽度 3 像素", 0),
    bad("宽度 3 px", (1,), at(ZH_UNIT, "3 px", "U+0020")),
    bad(f"宽度 3{NBSP}px", (1,), at(ZH_UNIT, "3", "px", "U+00A0")),
    bad("宽度 3\npx", (1,), at(ZH_UNIT, "3", "px", SHOWN_AS_SPACE)),
    ok("宽度 `3 px`", 0),
    ok("宽度 3 个", 0),
]

# ... one space after a number's trailing symbol before Han, and before a symbol
# that opens a number. Counts: the trailing-symbol edges, the opening-symbol edges.
SYMBOL_SCENARIO = Scenario(
    ZH_SYMBOL,
    ("trailing-symbol edges", "opening-symbol edges"),
    lists=(
        ("zh_trailing_symbols", ZH_TRAILING_LIST),
        ("zh_opening_symbols", ZH_OPENING_LIST),
    ),
)
SYMBOL_EXAMPLES = [
    ok("设为 100% 的不透明度", 1, 0),
    ok("旋转 90° 后", 1, 0),
    ok("设为 100%\n的不透明度", 1, 0),
    bad("设为 100%的不透明度", (1, 0), at(ZH_SYMBOL, "%", "的", NOTHING_BETWEEN)),
    bad("旋转 90°后", (1, 0), at(ZH_SYMBOL, "°", "后", NOTHING_BETWEEN)),
    bad(f"设为 100%{NBSP}的", (1, 0), at(ZH_SYMBOL, "%", "的", "U+00A0")),
    bad(f"设为 100%{IDEOGRAPHIC}的", (1, 0), at(ZH_SYMBOL, "%", "的", "U+3000")),
    bad("宽 3px的画笔", (0, 0), at(ZH_HAN_LATIN, "x", "的", NOTHING_BETWEEN)),
    bad("旋转 90°\n后", (1, 0), at(ZH_SYMBOL, "°", "后", HIDES, "clause 3")),
    bad("误差约\n±5", (0, 1), at(ZH_SYMBOL, "约", "±", HIDES, "clause 3")),
    ok("误差约 ±5", 0, 1),
    bad("误差约±5", (0, 1), at(ZH_SYMBOL, "约", "±", NOTHING_BETWEEN)),
]


def check_example(
    tools: Tools, work: Path, scenario: Scenario, example: Example
) -> None:
    """Run the guide surface over one page and judge the report against ``example``.

    Exit code, the findings of each of the four rules (the rule, the page, the
    line, the words naming the edge), one page examined by every rule, the
    sub-counts of the scenario's own rule and the printed lists.
    """
    tree = build_tree(work)
    tree.page(ZH_LANGUAGE, ZH_PAGE, f"{ZH_HEAD}{example.text}\n")
    run, payload = scan(tools, tree, "--surface", "guide")
    expected = len(example.found)
    assert run.returncode == (1 if expected else 0), (run.stdout, run.stderr)
    assert payload["findings_total"] == expected, payload["rules"]
    assert payload["rules_examining_nothing"] == 0, payload["rules"]
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit["examined"] == 1 and unit["files"] == 1, unit
        assert unit["nothing_examined"] is False, unit
        wanted = [item for item in example.found if item.rule == rule]
        assert len(unit["findings"]) == len(wanted), (rule, unit["findings"])
        for finding, want in zip(unit["findings"], wanted):
            place, _, line = finding["where"].rpartition(":")
            assert place == ZH_WHERE, finding
            assert 3 <= int(line) <= 3 + example.text.count("\n"), finding
            if "\n" not in example.text:
                assert int(line) == 3, finding
            assert in_order(finding["detail"], want.words), (want.words, finding)
    sub = row(payload, scenario.rule, "guide", ZH_LANGUAGE)["sub_counts"]
    if scenario.summed:
        assert set(scenario.parts) <= set(sub), sub
        assert (sum(sub.values()),) == example.counts, sub
    else:
        assert set(sub) == set(scenario.parts), sub
        assert tuple(sub[part] for part in scenario.parts) == example.counts, sub
    for key, listed in scenario.lists:
        assert payload[key] == listed, (key, payload.get(key))


def check_examples(
    tools: Tools,
    work: Path,
    label: str,
    scenario: Scenario,
    examples: list[Example],
) -> None:
    """Judge every example, in parallel, and name every one that fails.

    One report per scenario instead of one failure at the first example makes a
    broken copy name all the rows it breaks.
    """

    def one(item: tuple[int, Example]) -> str:
        number, example = item
        try:
            check_example(tools, work / f"{label}-{number}", scenario, example)
        except Exception as error:  # every kind of failure is a failed example
            return f"example {number} {example.text!r}: {str(error)[:260]}"
        return ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [text for text in pool.map(one, enumerate(examples, 1)) if text]
    assert not failures, f"{len(failures)} example(s) failed:\n" + "\n".join(failures)


def judged(rule: str, count: str) -> str:
    """Return the line of the script that judges an edge counted under ``count``."""
    return f'                self.judge("{rule}", "{count}", left, right, gap)\n'


def counted(count: str) -> str:
    """Return a line that counts the edge and never judges it."""
    return f'                self.counts["{count}"] += 1\n'


#: The mutants that damage the shared reading of a gap, whichever rule asks.
NBSP_ACCEPTED = mutant(
    "no-break-space-accepted",
    ty(
        '    if cell.kind == "soft" or cell.char == ZH_SPACE:\n',
        '    if cell.kind == "soft" or cell.char in (ZH_SPACE, "\\u00a0"):\n',
    ),
)
IDEOGRAPHIC_ACCEPTED = mutant(
    "ideographic-space-accepted",
    ty(
        '    if cell.kind == "soft" or cell.char == ZH_SPACE:\n',
        '    if cell.kind == "soft" or cell.char in (ZH_SPACE, "\\u3000"):\n',
    ),
)
DOUBLED_ACCEPTED = mutant(
    "doubled-space-accepted",
    ty("\n    if len(gap) > 1:\n", "\n    if len(gap) > 5:\n"),
)
HIDDEN_BREAKS_IGNORED = mutant(
    "hidden-breaks-read-as-shown-spaces",
    ty(
        "            hidden = soft is not None and soft.removed\n",
        "            hidden = False\n",
    ),
)
EVERY_BREAK_HIDDEN = mutant(
    "every-break-hidden",
    ty(
        "            hidden = soft is not None and soft.removed\n",
        "            hidden = soft is not None\n",
    ),
)
OTHER_LANGUAGES_BREAKS = mutant(
    "breaks-decided-for-another-language",
    ty(
        "        b.line: b for b in module.apply_soft_break_rule("
        "text, ZH_LANGUAGE).breaks\n",
        "        b.line: b for b in module.apply_soft_break_rule("
        'text, "en").breaks\n',
    ),
)
CODE_SPAN_EDGES_NOT_TEXT = mutant(
    "code-span-edges-not-text",
    ty('                kinds[at] = "T"\n', '                kinds[at] = "M"\n'),
)
FULLWIDTH_DIGIT_NOT_DIGIT = mutant(
    "full-width-digit-not-a-digit",
    ty(
        '    return unicodedata.category(char) == "Nd"\n',
        '    return unicodedata.category(char) == "Nd" and char.isascii()\n',
    ),
)
FULLWIDTH_LATIN_NOT_LATIN = mutant(
    "full-width-latin-not-latin",
    ty(
        "        return index >= 0 and code <= self.latin[index][1]\n",
        "        return index >= 0 and code <= self.latin[index][1]"
        " and char.isascii()\n",
    ),
)


@REGISTRY.regression(
    mutant(
        "han-latin-edges-not-judged",
        ty(
            judged("zh-space-han-latin", "edges"),
            counted("edges"),
        ),
    ),
    HIDDEN_BREAKS_IGNORED,
    EVERY_BREAK_HIDDEN,
    CODE_SPAN_EDGES_NOT_TEXT,
    FULLWIDTH_DIGIT_NOT_DIGIT,
    FULLWIDTH_LATIN_NOT_LATIN,
    NBSP_ACCEPTED,
    IDEOGRAPHIC_ACCEPTED,
    DOUBLED_ACCEPTED,
)
def case_a_chinese_page_puts_one_space_between_han_and_a_latin_letter_or_digit(
    tools: Tools, work: Path
) -> None:
    """Han beside a Latin letter or a digit takes exactly one U+0020, either order.

    The fourteen examples of the scenario, one page each: the spaced forms exit
    0 (a soft line break the guide shows counts as the one space, a full-width
    letter or digit is a Latin letter or a digit); the others exit 1 naming the
    page, line 3 and the edge, and the kind of gap (nothing, two spaces,
    U+00A0, U+3000, a code span's first or last character, a soft line break
    the guide hides). The edges found are the rule's sub-count.
    """
    assert len(HAN_LATIN_EXAMPLES) == 14
    check_examples(tools, work, "han", HAN_LATIN_SCENARIO, HAN_LATIN_EXAMPLES)


@REGISTRY.regression(
    mutant(
        "mark-edges-not-judged",
        ty(
            judged("zh-space-mark-latin", "mark edges"),
            counted("mark edges"),
        ),
    ),
    mutant(
        "symbol-edges-not-judged",
        ty(
            judged("zh-space-mark-latin", "symbol edges"),
            counted("symbol edges"),
        ),
    ),
    mutant(
        "curly-quotes-not-marks",
        ty(
            "    if char in ZH_QUOTES:\n        return True\n",
            "    if False:\n        return True\n",
        ),
    ),
    mutant(
        "single-quotes-are-marks",
        ty(
            f'ZH_QUOTES = "{ESCAPE_U}201c{ESCAPE_U}201d"\n',
            f'ZH_QUOTES = "{ESCAPE_U}201c{ESCAPE_U}201d{ESCAPE_U}2018{ESCAPE_U}2019"\n',
        ),
    ),
    HIDDEN_BREAKS_IGNORED,
    OTHER_LANGUAGES_BREAKS,
    CODE_SPAN_EDGES_NOT_TEXT,
    FULLWIDTH_LATIN_NOT_LATIN,
    NBSP_ACCEPTED,
    IDEOGRAPHIC_ACCEPTED,
    DOUBLED_ACCEPTED,
)
def case_a_chinese_page_spaces_a_full_width_mark_from_a_latin_letter_or_digit(
    tools: Tools, work: Path
) -> None:
    """A full-width mark beside Latin, a digit or a number's symbol takes one space.

    The twenty-one examples of the scenario. The curly double quotes are marks
    for this rule and the single ones are not; there is no rule between a mark
    and Han; emphasis delimiters are not characters; a code span's first
    character is text; a soft line break the guide hides after a mark (by the
    mark's own clause, or by the full-width letter's) is a finding; a number's
    symbol beside a mark takes the space as well.
    """
    assert len(MARK_LATIN_EXAMPLES) == 21
    check_examples(tools, work, "mark", MARK_LATIN_SCENARIO, MARK_LATIN_EXAMPLES)


@REGISTRY.regression(
    mutant(
        "pair-spacing-passes",
        ty(
            "            if not gap:\n                continue\n",
            "            continue\n",
        ),
    ),
    mutant("unit-list-empty", ty('ZH_NUM_UNITS = ("px",)\n', "ZH_NUM_UNITS = ()\n")),
    mutant(
        "pairs-inside-a-code-span-examined",
        ty(
            "            if len(owners) == 1 and 0 not in owners:\n",
            "            if False:\n",
        ),
    ),
    EVERY_BREAK_HIDDEN,
)
def case_a_chinese_page_writes_a_number_closed_against_a_listed_unit(
    tools: Tools, work: Path
) -> None:
    """``3px`` is closed; any space inside it, or a shown soft break, is a finding.

    The eight examples of the scenario. The unit list (px) is printed, a unit
    written in Han takes the Han rule's space instead, a Han classifier is not
    a unit (0 pairs), and the inside of a code span is not examined.
    """
    assert len(UNIT_EXAMPLES) == 8
    check_examples(tools, work, "unit", UNIT_SCENARIO, UNIT_EXAMPLES)


@REGISTRY.regression(
    mutant(
        "trailing-symbol-edges-not-judged",
        ty(
            judged("zh-space-symbol", "trailing-symbol edges"),
            counted("trailing-symbol edges"),
        ),
    ),
    mutant(
        "opening-symbol-edges-not-judged",
        ty(
            judged("zh-space-symbol", "opening-symbol edges"),
            counted("opening-symbol edges"),
        ),
    ),
    mutant(
        "degree-not-a-trailing-symbol",
        ty(
            'ZH_TRAILING_SYMBOLS = ("%", "\\u00b0")\n',
            'ZH_TRAILING_SYMBOLS = ("%",)\n',
        ),
    ),
    mutant(
        "plus-minus-not-an-opening-symbol",
        ty('ZH_OPENING_SYMBOLS = ("\\u00b1",)\n', "ZH_OPENING_SYMBOLS = ()\n"),
    ),
    mutant(
        "han-latin-edges-not-judged",
        ty(
            judged("zh-space-han-latin", "edges"),
            counted("edges"),
        ),
    ),
    HIDDEN_BREAKS_IGNORED,
    EVERY_BREAK_HIDDEN,
    NBSP_ACCEPTED,
    IDEOGRAPHIC_ACCEPTED,
)
def case_a_chinese_page_spaces_a_numbers_symbols_from_the_han_beside_them(
    tools: Tools, work: Path
) -> None:
    """One space after ``%`` or ``\u00b0`` before Han, and before ``\u00b1`` after Han.

    The twelve examples of the scenario. Both symbol lists are printed. A Latin
    unit before Han (``3px`` then Han) is the Han rule's edge, not this
    rule's. A soft line break the guide hides at a spaced edge is a finding and
    one it shows counts as the space.
    """
    assert len(SYMBOL_EXAMPLES) == 12
    check_examples(tools, work, "symbol", SYMBOL_SCENARIO, SYMBOL_EXAMPLES)


# --------------------------------------------------------------------------- #
# The scope of the four rules, and what they print.
# --------------------------------------------------------------------------- #
#: The text of the four scenarios' first failing rows, which a page that is not
#: ``zh_CN`` or a catalogue message may hold without a finding.
OFFENDING = ["使用**F1**键", "撤销，Ctrl+Y", "宽度 3 px", "设为 100%的不透明度"]


@REGISTRY.regression(
    mutant(
        "ja-pages-also-scanned",
        ty(
            "    if language == ZH_LANGUAGE:\n"
            "        scan_zh_page(text, rel, tally, root)\n",
            '    if language in (ZH_LANGUAGE, "ja"):\n'
            "        scan_zh_page(text, rel, tally, root)\n",
        ),
    ),
    mutant(
        "every-language-scanned",
        ty(
            "    if language == ZH_LANGUAGE:\n"
            "        scan_zh_page(text, rel, tally, root)\n",
            "    if True:\n        scan_zh_page(text, rel, tally, root)\n",
        ),
    ),
)
def case_the_chinese_rules_read_zh_cn_guide_pages_only(
    tools: Tools, work: Path
) -> None:
    """A ``ja`` page, a page of another language or a ``zh_CN`` message is not examined.

    The same text that fails on a ``zh_CN`` guide page (the first failing row
    of each of the four scenarios) sits in a ``ja`` page, an English page, a
    Spanish page and two ``zh_CN`` catalogue messages: exit 0, and every
    Chinese rule examined exactly the one ``zh_CN`` page.
    """
    tree = build_tree(work / "scope")
    tree.chinese_page()
    prose = "\n\n".join(OFFENDING)
    for language in ("ja", "en", "es"):
        tree.page(language, "index.md", f"{ZH_HEAD}{prose}\n")
    messages = [Msg(f"Text {n}", text) for n, text in enumerate(OFFENDING[:2])]
    tree.catalogue(ZH_LANGUAGE, messages)
    run, payload = scan(tools, tree)
    assert_clean(run, payload)
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit["examined"] == 1 and unit["files"] == 1, unit
        assert unit["findings"] == [], unit
    stray = [
        (r["rule"], r["surface"], r["language"])
        for r in payload["rules"]
        if r["rule"] in ZH_RULE_ROWS
        and (r["surface"], r["language"]) != ("guide", "zh_CN")
    ]
    assert stray == [], stray
    assert row(payload, "zh-fullwidth", "catalogue", ZH_LANGUAGE)["examined"] == 2


@REGISTRY.regression(
    mutant(
        "chinese-rules-not-declared",
        ty("                declare_zh_units(tally)\n", "                pass\n"),
    ),
    mutant(
        "blind-rule-passes",
        ty(
            "    code = EXIT_FINDINGS if total or"
            " blind or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant(
        "blind-rule-unnamed",
        ty('        if row["nothing_examined"]:\n', "        if False:\n"),
    ),
)
def case_a_guide_run_with_no_zh_cn_page_exits_1_saying_nothing_examined(
    tools: Tools, work: Path
) -> None:
    """Each of the four rules, with no ``zh_CN`` page to read, examines nothing.

    A guide with only a ``ja`` page, a guide whose ``zh_CN`` folder holds no
    page and a guide of French and Japanese pages all exit 1, and each of the
    four rules prints its row with 0 pages and 0 edges and then
    ``nothing examined``. The same tree with one clean ``zh_CN`` page exits 0.
    """
    only_ja = build_tree(work / "only-ja")
    only_ja.page("ja", "index.md", f"{ZH_HEAD}{OFFENDING[0]}\n")
    empty = build_tree(work / "empty-folder")
    empty.page("ja", "index.md", f"{ZH_HEAD}{OFFENDING[0]}\n")
    (empty.root / GUIDE_DIR / ZH_LANGUAGE).mkdir(parents=True)
    french = build_tree(work / "fr-and-ja")
    french.page("fr", "index.md", f"# Aide\n\nOuvrir{NBSP}?\n")
    french.page("ja", "index.md", f"{ZH_HEAD}{OFFENDING[0]}\n")
    for label, tree in (("only-ja", only_ja), ("empty", empty), ("fr-ja", french)):
        run, payload = scan(tools, tree)
        assert run.returncode == 1, (label, run.stdout, run.stderr)
        blind = {r["rule"] for r in payload["rules"] if r["nothing_examined"]}
        assert set(ZH_RULE_ROWS) <= blind, (label, payload["rules"])
        text = text_of(tools, tree)
        assert text.returncode == 1, (label, text.stdout, text.stderr)
        lines = text.stdout.splitlines()
        for rule in ZH_RULE_ROWS:
            unit = row(payload, rule, "guide", ZH_LANGUAGE)
            assert unit["examined"] == 0 and unit["nothing_examined"] is True, unit
            assert set(unit["sub_counts"].values()) == {0}, unit
            head = f"{rule} [guide] "
            printed = [n for n, line in enumerate(lines) if line.startswith(head)]
            assert len(printed) == 1, (label, rule, text.stdout)
            assert "examined 0 page(s)" in lines[printed[0]], lines[printed[0]]
            assert lines[printed[0] + 1] == "  nothing examined", (label, text.stdout)
    only_ja.chinese_page()
    run, payload = scan(tools, only_ja)
    assert_clean(run, payload)


def printed_counts(stdout: str, rule: str) -> tuple[int, dict[str, int], int]:
    """Return ``(pages, sub-counts, findings)`` from the printed row of ``rule``."""
    pattern = re.compile(
        rf"^{re.escape(rule)} \[guide\] zh_CN: examined (\d+) page\(s\)"
        r"(?: \((.*)\))?, (\d+) finding\(s\)$",
        re.MULTILINE,
    )
    found = pattern.findall(stdout)
    assert len(found) == 1, (rule, stdout)
    pages, parts, findings = found[0]
    counts = {}
    for part in filter(None, parts.split(", ")):
        name, _, number = part.rpartition(" ")
        counts[name] = int(number)
    return int(pages), counts, int(findings)


def printed_list(stdout: str, marker: str) -> str:
    """Return the one printed line that holds ``marker``."""
    lines = [line for line in stdout.splitlines() if marker in line]
    assert len(lines) == 1, (marker, stdout)
    return lines[0]


#: Line 3 of a page whose edges are all spaced as the rules want, by hand:
#: Han beside Latin or a digit 4, marks beside Latin or a digit 2, one closed
#: pair, one trailing symbol before Han and one opening symbol after Han.
COUNTED_TEXT = "设为 100% 的 A ，宽 3px 约 ±5 。"


@REGISTRY.regression(
    mutant(
        "chinese-lists-not-printed",
        ty(
            '    if any(row["rule"] in ZH_RULE_NAMES for row in report["rules"]):\n'
            "        print_zh_lists(report, out)\n",
            '    if any(row["rule"] in ZH_RULE_NAMES for row in report["rules"]):\n'
            "        pass\n",
        ),
    ),
    mutant(
        "chinese-sub-counts-not-printed",
        ty(
            '        if row["rule"] in ("fr-num-unit", *ZH_RULE_NAMES) and parts:\n',
            '        if row["rule"] == "fr-num-unit" and parts:\n',
        ),
    ),
    mutant(
        "chinese-rows-count-items",
        ty(
            '        if row["rule"] in ZH_RULE_NAMES:\n            unit = "page(s)"\n',
            '        if row["rule"] in ZH_RULE_NAMES:\n            unit = "item(s)"\n',
        ),
    ),
    mutant(
        "unit-list-reported-empty",
        ty(
            '        report["zh_num_unit_units"] = list(ZH_NUM_UNITS)\n',
            '        report["zh_num_unit_units"] = []\n',
        ),
    ),
    mutant(
        "trailing-list-reported-empty",
        ty(
            '        report["zh_trailing_symbols"] = list(ZH_TRAILING_SYMBOLS)\n',
            '        report["zh_trailing_symbols"] = []\n',
        ),
    ),
    mutant(
        "opening-list-reported-empty",
        ty(
            '        report["zh_opening_symbols"] = list(ZH_OPENING_SYMBOLS)\n',
            '        report["zh_opening_symbols"] = []\n',
        ),
    ),
)
def case_the_chinese_rules_print_their_pages_sub_counts_and_lists(
    tools: Tools, work: Path
) -> None:
    """The report gives the pages examined, each rule's edges and the three lists.

    Two ``zh_CN`` pages (the clean companion and one with known edges) are
    counted by hand. The text report prints, per rule, the pages examined with
    the sub-counts beside them (and 0 where there are none), and the unit list,
    the trailing-symbol list and the opening-symbol list each with its length;
    a page with a finding prints it at ``<page>:<line>``.
    """
    tree = build_tree(work / "counted")
    tree.page(ZH_LANGUAGE, ZH_PAGE, f"{ZH_HEAD}{COUNTED_TEXT}\n")
    tree.chinese_page()
    run, payload = scan(tools, tree, "--surface", "guide")
    assert_clean(run, payload)
    text = text_of(tools, tree, "--surface", "guide")
    assert text.returncode == 0, (text.stdout, text.stderr)
    expected = {
        ZH_HAN_LATIN: {"edges": 6},
        ZH_MARK_LATIN: {"mark edges": 2, "symbol edges": 0},
        ZH_UNIT: {"pairs": 1},
        ZH_SYMBOL: {"trailing-symbol edges": 1, "opening-symbol edges": 1},
    }
    for rule, counts in expected.items():
        assert printed_counts(text.stdout, rule) == (2, counts, 0), (rule, text.stdout)
        assert row(payload, rule, "guide", ZH_LANGUAGE)["sub_counts"] == counts
    assert re.search(r"\(1\): px$", printed_list(text.stdout, f"{ZH_UNIT} units"))
    trailing = printed_list(text.stdout, "trailing symbols")
    assert re.search(r"\(2\): %, \u00b0$", trailing), trailing
    opening = printed_list(text.stdout, "opening symbols")
    assert re.search(r"\(1\): \u00b1$", opening), opening
    assert payload["zh_num_unit_units"] == ZH_UNIT_LIST
    assert payload["zh_trailing_symbols"] == ZH_TRAILING_LIST
    assert payload["zh_opening_symbols"] == ZH_OPENING_LIST

    failing = build_tree(work / "failing")
    failing.page(ZH_LANGUAGE, "bad.md", f"{ZH_HEAD}{OFFENDING[0]}\n")
    text = text_of(tools, failing, "--surface", "guide")
    assert text.returncode == 1, (text.stdout, text.stderr)
    assert printed_counts(text.stdout, ZH_HAN_LATIN) == (1, {"edges": 2}, 2)
    named = [x for x in text.stdout.splitlines() if x.startswith("  zh_CN/bad.md:3: ")]
    assert len(named) == 2, text.stdout


# --------------------------------------------------------------------------- #
# A verbatim quotation of an interface message (SC-L10N-DATA-004-16).
#
# The planted ``zh_CN`` catalogue holds the scenario's four finished messages:
# M1 with the page's quotation marks inside it, M2 with a placeholder, M3 with
# no wording at all, M4 with one space. Each example is line 3 of a ``zh_CN``
# page; the run covers the guide surface; every one of the four Chinese rules
# judges it. A quotation is listed with its page, its line and the source text
# of the message it quotes.
# --------------------------------------------------------------------------- #
ZH_LQ = "\u201c"
ZH_RQ = "\u201d"
QUOTE_M1 = Msg("Merged into the main branch", f"已合并到{ZH_LQ}main{ZH_RQ}分支")
QUOTE_M2 = Msg("Export %1 frames", "导出%1帧")
QUOTE_M3 = Msg("%1: %2", "%1: %2")
QUOTE_M4 = Msg("Export as PNG", "导出为 PNG")
QUOTE_MESSAGES = [QUOTE_M1, QUOTE_M2, QUOTE_M3, QUOTE_M4]
QUOTE_CATALOGUE = "pixelart_zh_CN.ts"
#: The finished messages the script reads, and the ones that quote some wording
#: (M3 holds none, so three of the four).
QUOTE_FINISHED = 4
QUOTE_QUOTABLE = 3
QUOTE_HEADING = re.compile(
    r"zh quotations exempted from all four rules \((\d+)\), (\S+): "
    r"(\d+) finished message\(s\) read, (\d+) quotable"
)


class QuoteRow(NamedTuple):
    """One row of the scenario: line 3, the findings it expects, what it quotes."""

    text: str
    found: tuple[Found, ...]
    quoted: tuple[Msg, ...]
    #: Whether the row also judges the messages the report says it read and could
    #: quote: the row whose reason is that one message holds no wording.
    reads: bool = False


QUOTE_ROWS = [
    # 1. The marks beside main are the message's own.
    QuoteRow(f"界面显示：已合并到{ZH_LQ}main{ZH_RQ}分支。", (), (QUOTE_M1,)),
    # 2. One character differs: not verbatim, judged whole.
    QuoteRow(
        f"界面显示：已合并至{ZH_LQ}main{ZH_RQ}分支。",
        (
            at(ZH_MARK_LATIN, "between ", ZH_LQ, " and m: ", NOTHING_BETWEEN),
            at(ZH_MARK_LATIN, "between n and ", ZH_RQ, NOTHING_BETWEEN),
        ),
        (),
    ),
    # 3. The shown text equals the message; the hidden break is inside it.
    QuoteRow(f"界面显示：已合并到{ZH_LQ}\nmain{ZH_RQ}分支。", (), (QUOTE_M1,)),
    # 4. The placeholder matches 12.
    QuoteRow("状态栏显示：导出12帧。", (), (QUOTE_M2,)),
    # 5. M3 holds no wording: it exempts nothing.
    QuoteRow(
        "比值为3: 4倍",
        (
            at(ZH_HAN_LATIN, "between ", "为", " and 3: ", NOTHING_BETWEEN),
            at(ZH_HAN_LATIN, "between 4 and ", "倍", NOTHING_BETWEEN),
        ),
        (),
        reads=True,
    ),
    # 6. The page's own mark is outside the quotation (M4).
    QuoteRow(
        f"选择{ZH_LQ}导出为 PNG{ZH_RQ}。",
        (at(ZH_MARK_LATIN, "between G and ", ZH_RQ, NOTHING_BETWEEN),),
        (QUOTE_M4,),
    ),
    # 7. The same with the one space the mark needs.
    QuoteRow(f"选择{ZH_LQ}导出为 PNG {ZH_RQ}。", (), (QUOTE_M4,)),
    # 8. Outside the quotation the rules apply as before.
    QuoteRow(
        f"共3个，已合并到{ZH_LQ}main{ZH_RQ}分支",
        (
            at(ZH_HAN_LATIN, "between ", "共", " and 3: ", NOTHING_BETWEEN),
            at(ZH_HAN_LATIN, "between 3 and ", "个", NOTHING_BETWEEN),
        ),
        (QUOTE_M1,),
    ),
]


def quote_tree(work: Path, pages: dict[str, str]) -> Tree:
    """Build a root with the planted ``zh_CN`` catalogue and one page per entry.

    ``pages`` maps a page name to what follows its two-line heading.
    """
    tree = build_tree(work)
    tree.catalogue(ZH_LANGUAGE, QUOTE_MESSAGES)
    for name, text in pages.items():
        tree.page(ZH_LANGUAGE, name, f"{ZH_HEAD}{text}\n")
    return tree


def item_key(item: dict) -> tuple[str, int]:
    """Return the sort key of a listed quotation: its page and its line."""
    return item["page"], item["line"]


def quote_items(quoted: list[tuple[str, int, Msg]]) -> list[dict]:
    """Return the report items of ``(page, line, message)`` quotations, as sorted."""
    items = [{"page": p, "line": n, "source": m.source} for p, n, m in quoted]
    return sorted(items, key=item_key)


def judge_quote_report(
    payload: dict, quoted: list[tuple[str, int, Msg]], reads: bool = False
) -> None:
    """Judge what a JSON report says of the quotations it exempted.

    The number exempted on the block and on each of the four rules' rows, the
    items (page, line, source text of the message), and, when ``reads`` is set,
    the messages read and the ones that can be quoted.
    """
    block = payload.get("zh_quotations")
    assert block is not None, "no zh_quotations block in the report"
    wanted = {
        "catalogue": QUOTE_CATALOGUE,
        "exempted": len(quoted),
        "items": quote_items(quoted),
    }
    if reads:
        wanted["finished_messages"] = QUOTE_FINISHED
        wanted["quotable_messages"] = QUOTE_QUOTABLE
    got = {key: block.get(key) for key in wanted}
    got["items"] = sorted(got["items"] or [], key=item_key)
    assert got == wanted, block
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit.get("quotations_exempted") == len(quoted), unit


def judge_quote_text(
    stdout: str, quoted: list[tuple[str, int, Msg]], reads: bool = False
) -> None:
    """Judge what the text report prints of the quotations it exempted.

    One heading with the number (0 included), and then one line per quotation
    with its page, line and the message's source text; no other message's
    source text is printed as a quotation.
    """
    lines = stdout.splitlines()
    heads = [found for found in map(QUOTE_HEADING.fullmatch, lines) if found]
    assert len(heads) == 1, stdout
    count, name, finished, quotable = heads[0].groups()
    assert (int(count), name) == (len(quoted), QUOTE_CATALOGUE), heads[0].string
    if reads:
        assert (int(finished), int(quotable)) == (
            QUOTE_FINISHED,
            QUOTE_QUOTABLE,
        ), stdout
    expected = sorted(f"  {p}:{n}: {m.source}" for p, n, m in quoted)
    printed = sorted(
        line
        for line in lines
        if any(line.endswith(f": {message.source}") for message in QUOTE_MESSAGES)
    )
    assert printed == expected, (printed, expected)


def check_quote_row(tools: Tools, work: Path, example: QuoteRow) -> None:
    """Judge one row of the scenario on both reports.

    Exit code; the findings of each of the four rules with the page and line 3
    and the words that name the edge; one page examined by every rule; and the
    quotations, in the JSON and in the text.
    """
    tree = quote_tree(work, {ZH_PAGE: example.text})
    run, payload = scan(tools, tree, "--surface", "guide")
    expected = len(example.found)
    assert run.returncode == (1 if expected else 0), (run.stdout, run.stderr)
    assert payload["findings_total"] == expected, payload["rules"]
    assert payload["rules_examining_nothing"] == 0, payload["rules"]
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit["examined"] == 1 and unit["files"] == 1, unit
        wanted = [item for item in example.found if item.rule == rule]
        assert len(unit["findings"]) == len(wanted), (rule, unit["findings"])
        for finding, want in zip(unit["findings"], wanted):
            assert finding["where"] == f"{ZH_WHERE}:3", finding
            assert in_order(finding["detail"], want.words), (want.words, finding)
    quoted = [(ZH_WHERE, 3, message) for message in example.quoted]
    judge_quote_report(payload, quoted, example.reads)
    text = text_of(tools, tree, "--surface", "guide")
    assert text.returncode == run.returncode, (text.stdout, text.stderr)
    judge_quote_text(text.stdout, quoted, example.reads)


def check_quote_rows(tools: Tools, work: Path, rows: tuple[int, ...] = ()) -> None:
    """Judge the scenario's rows (all of them, or the numbered ones), in parallel.

    Every row that fails is named, so that a broken copy shows which rows it
    breaks.
    """
    assert len(QUOTE_ROWS) == 8
    chosen = [(n, QUOTE_ROWS[n - 1]) for n in (rows or range(1, 9))]

    def one(item: tuple[int, QuoteRow]) -> str:
        number, example = item
        try:
            check_quote_row(tools, work / f"row-{number}", example)
        except Exception as error:  # every kind of failure is a failed row
            return f"row {number} {example.text!r}: {str(error)[:260]}"
        return ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [text for text in pool.map(one, chosen) if text]
    assert not failures, f"{len(failures)} row(s) failed:\n" + "\n".join(failures)


#: A copy that exempts what lies one character beyond the quotation: the page's
#: own mark beside it (row 6).
QUOTE_MARKS_EXEMPT = mutant(
    "edge-with-the-pages-own-mark-exempt",
    ty(
        "            if a <= first and last <= b:\n",
        "            if a - 1 <= first and last <= b + 1:\n",
    ),
)
#: A copy that exempts every edge of a paragraph that holds a quotation (rows 6
#: and 8).
QUOTE_PARAGRAPH_EXEMPT = mutant(
    "paragraph-holding-a-quotation-exempt",
    ty(
        "            self.quote = self.inside(keep[index], keep[index + 1])\n",
        "            self.quote = 0 if self.runs else -1\n",
    ),
)
#: A copy that reads a message without wording as a quotation of something (the
#: only trace of it in the report is the count of messages that can be quoted).
QUOTE_NO_WORDING_PASSES = mutant(
    "wording-free-message-counts-as-quotable",
    ty(
        "    return texts, any(char.isalpha() for char in outside)\n",
        "    return texts, True\n",
    ),
)
#: The same copy, whose message with no wording also takes the longest run for
#: each placeholder at its edge, so that it exempts the whole of row 5's page.
QUOTE_NO_WORDING_EXEMPTS = mutant(
    "wording-free-message-exempts-the-whole-run",
    ty(
        "    return texts, any(char.isalpha() for char in outside)\n",
        "    return texts, True\n",
    ),
    ty('ZH_ANY_RUN = r"[^\\ufffc]+?"\n', 'ZH_ANY_RUN = r"[^\\ufffc]+"\n'),
)
#: A copy that accepts a run that differs from the message by one character
#: (row 2): any one character of the message may be another one.
QUOTE_NEAR_VERBATIM = mutant(
    "run-differing-by-one-character-accepted",
    ty(
        "                pattern = re.compile("
        "ZH_ANY_RUN.join(re.escape(p) for p in pieces))\n",
        "                pattern = re.compile(ZH_ANY_RUN.join("
        '"(?:" + "|".join(re.escape(p[:i]) + "." + re.escape(p[i + 1 :]) '
        'for i in range(len(p))) + ")" for p in pieces))\n',
    ),
    ty(
        "                probe = max(pieces, key=len)\n",
        "                probe = max(pieces, key=len)[:2]\n",
    ),
)


@REGISTRY.regression(
    QUOTE_MARKS_EXEMPT,
    QUOTE_PARAGRAPH_EXEMPT,
    QUOTE_NO_WORDING_PASSES,
    QUOTE_NO_WORDING_EXEMPTS,
    QUOTE_NEAR_VERBATIM,
    mutant(
        "quotations-never-loaded",
        ty(
            "                load_zh_quotes(tally, folder, catalogues)\n",
            "                pass\n",
        ),
    ),
    mutant(
        "numbered-placeholder-is-literal-text",
        ty("(?:n|[1-9][0-9]?)", "(?:n|z)"),
    ),
    mutant(
        "hidden-break-kept-in-the-shown-text",
        ty(
            '        if cell.kind != "hidden":\n            chars.append(cell.char)\n',
            '        if True:\n            chars.append(cell.char or "\\n")\n',
        ),
    ),
)
def case_a_verbatim_quotation_of_a_message_is_not_judged_by_the_chinese_rules(
    tools: Tools, work: Path
) -> None:
    """The eight rows of SC-L10N-DATA-004-16, with M1 to M4 planted.

    Rows 1, 3, 4 and 7 exit 0 with one quotation (the marks beside main are the
    message's; the shown text equals the message with a hidden break inside it;
    the placeholder matches 12; the mark's space). Row 2 differs by one
    character, so it is not verbatim and exits 1 after the mark and before the
    other. Row 5 quotes a message with no wording and exempts nothing. Row 6
    exits 1 naming only the page's own mark, row 8 names the two edges outside
    its quotation.
    """
    check_quote_rows(tools, work)


@REGISTRY.regression(
    mutant(
        "quotation-block-not-printed",
        ty(
            "    if quoted:\n"
            '        where = quoted["catalogue"] or "no zh_CN catalogue read"\n',
            "    if False:\n"
            '        where = quoted["catalogue"] or "no zh_CN catalogue read"\n',
        ),
    ),
    mutant(
        "quotation-items-not-printed",
        ty('        for item in quoted["items"]:\n', "        for item in []:\n"),
    ),
    mutant(
        "quotation-count-printed-as-zero",
        ty("rules ({quoted['exempted']}), ", "rules (0), "),
    ),
    mutant(
        "quotation-line-not-printed",
        ty(
            "print(f\"  {item['page']}:{item['line']}: {source}\", file=out)",
            "print(f\"  {item['page']}: {source}\", file=out)",
        ),
    ),
    mutant(
        "quotation-source-not-printed",
        ty(
            "print(f\"  {item['page']}:{item['line']}: {source}\", file=out)",
            "print(f\"  {item['page']}:{item['line']}:\", file=out)",
        ),
    ),
    mutant(
        "quotation-not-reported-in-json",
        ty('        report["zh_quotations"] = {\n', '        report["quoted"] = {\n'),
    ),
    mutant(
        "quotation-count-missing-from-the-rows",
        ty(
            '                row["quotations_exempted"] = len(tally.zh_exempted)\n',
            "                pass\n",
        ),
    ),
    mutant(
        "exemption-applied-but-not-recorded",
        ty(
            "        tally.zh_exempted.append("
            '{"page": rel, "line": line, "source": source})\n',
            "        pass\n",
        ),
    ),
)
def case_the_chinese_rules_report_each_quotation_they_exempted(
    tools: Tools, work: Path
) -> None:
    """The number of quotations is printed with each one's page, line and source.

    Three quotations on two pages (M4 on line 3 of one, M1 on line 3 and M2 on
    line 5 of the other) are listed, in the JSON and in the text report, each
    with its page, its line and the message's source text. A page that quotes
    nothing prints 0, and no listing.
    """
    pages = {
        "other.md": f"选择{ZH_LQ}导出为 PNG {ZH_RQ}。",
        ZH_PAGE: f"界面显示：已合并到{ZH_LQ}main{ZH_RQ}分支。\n\n状态栏显示：导出12帧。",
    }
    tree = quote_tree(work / "listed", pages)
    quoted = [
        ("zh_CN/other.md", 3, QUOTE_M4),
        (ZH_WHERE, 3, QUOTE_M1),
        (ZH_WHERE, 5, QUOTE_M2),
    ]
    run, payload = scan(tools, tree, "--surface", "guide")
    assert_clean(run, payload)
    judge_quote_report(payload, quoted)
    text = text_of(tools, tree, "--surface", "guide")
    assert text.returncode == 0, (text.stdout, text.stderr)
    judge_quote_text(text.stdout, quoted)
    none = quote_tree(work / "none", {ZH_PAGE: "使用 F1 键。"})
    run, payload = scan(tools, none, "--surface", "guide")
    assert_clean(run, payload)
    judge_quote_report(payload, [])
    text = text_of(tools, none, "--surface", "guide")
    assert text.returncode == 0, (text.stdout, text.stderr)
    judge_quote_text(text.stdout, [])


# --------------------------------------------------------------------------- #
# The exemption's readings that the scenario's rows leave open: overlapping
# quotations, no ``zh_CN`` catalogue, and a message that
# quotes no wording. Each case plants messages and a page of its own; the
# scenario's M1 to M4 and its eight rows are not touched.
# --------------------------------------------------------------------------- #
#: A message the planted pages never quote: a catalogue that holds only this one
#: judges every page as if nothing could be exempted.
BYSTANDER = Msg("Unrelated", "无关内容")
HEADING_PREFIX = "zh quotations exempted from all four rules ("


def planted_tree(work: Path, messages: list[Msg], text: str) -> Tree:
    """Build a root whose ``zh_CN`` catalogue holds ``messages`` and one page.

    ``text`` is what follows the page's two-line heading, so it is line 3.
    """
    tree = build_tree(work)
    tree.catalogue(ZH_LANGUAGE, messages)
    tree.page(ZH_LANGUAGE, ZH_PAGE, f"{ZH_HEAD}{text}\n")
    return tree


def planted_run(
    tools: Tools, work: Path, messages: list[Msg], text: str
) -> tuple[ScriptRun, dict, ScriptRun]:
    """Run both reports over a planted page: the JSON run, its payload, the text."""
    tree = planted_tree(work, messages, text)
    run, payload = scan(tools, tree, "--surface", "guide")
    printed = text_of(tools, tree, "--surface", "guide")
    assert printed.returncode == run.returncode, (printed.stdout, printed.stderr)
    return run, payload, printed


def findings_of(payload: dict) -> list[tuple[str, str, str]]:
    """Return every finding of the report as (rule, place, detail), in report order."""
    return [
        (unit["rule"], item["where"], item["detail"])
        for unit in payload["rules"]
        for item in unit["findings"]
    ]


def judge_found(run: ScriptRun, payload: dict, wanted: tuple[Found, ...]) -> None:
    """Judge the exit code and the findings of each of the four rules, by words."""
    assert run.returncode == (1 if wanted else 0), (run.stdout, run.stderr)
    assert payload["findings_total"] == len(wanted), payload["rules"]
    assert payload["rules_examining_nothing"] == 0, payload["rules"]
    for rule in ZH_RULE_ROWS:
        got = details(row(payload, rule, "guide", ZH_LANGUAGE))
        mine = [item for item in wanted if item.rule == rule]
        assert len(got) == len(mine), (rule, got)
        for detail, want in zip(got, mine):
            assert in_order(detail, want.words), (want.words, detail)


def judge_listing(
    payload: dict, stdout: str, quoted: list[Msg], planted: list[Msg]
) -> None:
    """Judge the quotations a report lists: all on line 3 of the one page.

    ``quoted`` are the messages the report must list, in the JSON and in the
    text; ``planted`` every message of the catalogue, so that a line printing
    one that was not quoted is seen. The order is not judged.
    """
    wanted = sorted((ZH_WHERE, 3, message.source) for message in quoted)
    block = payload["zh_quotations"]
    assert block["exempted"] == len(quoted), block
    got = sorted(
        (item["page"], item["line"], item["source"]) for item in block["items"]
    )
    assert got == wanted, block
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit["quotations_exempted"] == len(quoted), unit
    lines = stdout.splitlines()
    assert any(line.startswith(f"{HEADING_PREFIX}{len(quoted)}), ") for line in lines)
    every = [f"  {ZH_WHERE}:3: {message.source}" for message in planted]
    printed = sorted(line for line in lines if line in every)
    assert printed == sorted(f"  {ZH_WHERE}:3: {item[2]}" for item in wanted), stdout


# (b) Overlapping quotations. Two messages whose runs overlap on ``abc`` and a
# page that holds both, with one edge inside each run only: the Han beside the
# Latin letters ``a`` (inside the first run) and the Han after ``c`` (inside the
# second). The requirement exempts "the inside of the quotation", and nothing lets
# one quotation displace another, so both edges are exempt and both quotations
# are listed. The script's precedence keeps the first message's run when the two
# weigh the same and the second's when it is longer, so each message is the
# overlapped one in one of the two variants; the case does not depend on which.
OVERLAP_FIRST = Msg("Test run", "测试abc")
OVERLAPS = [
    ("equal", Msg("Demo run", "abc演示"), "页面 测试abc演示 结束"),
    ("second-longer", Msg("Demo deck", "abc演示文稿"), "页面 测试abc演示文稿 结束"),
]
EDGE_BEFORE_LATIN = at(ZH_HAN_LATIN, "between ", "试", " and a: ", NOTHING_BETWEEN)
EDGE_AFTER_LATIN = at(ZH_HAN_LATIN, "between c and ", "演", NOTHING_BETWEEN)


@REGISTRY.regression(
    mutant(
        "overlapped-quotation-dropped",
        ty(
            "        for start, end, number in (*kept, *overlapped)\n",
            "        for start, end, number in (*kept,)\n",
        ),
    ),
    mutant(
        "only-the-first-listed-quotation-exempts",
        ty(
            "        for number, (a, b) in enumerate(self.runs):\n",
            "        for number, (a, b) in enumerate(self.runs[:1]):\n",
        ),
    ),
)
def case_an_edge_inside_an_overlapping_quotation_is_not_judged(
    tools: Tools, work: Path
) -> None:
    """Both edges are exempt and both quotations listed; alone, each exempts its own.

    The page judged with only an unrelated message has both edges as findings,
    so they are real. With both messages planted the run exits 0, counts both
    edges and lists both quotations. With either message alone, only the edge
    inside that message's run is exempt.
    """
    for label, second, text in OVERLAPS:
        first = OVERLAP_FIRST
        planted = [first, second, BYSTANDER]
        place = work / label
        both = [first, second]
        run, payload, printed = planted_run(tools, place / "both", both, text)
        judge_found(run, payload, ())
        assert row(payload, ZH_HAN_LATIN, "guide", ZH_LANGUAGE)["sub_counts"] == {
            "edges": 2
        }, (label, payload["rules"])
        judge_listing(payload, printed.stdout, both, planted)
        scenes = [
            ("none", [BYSTANDER], [], (EDGE_BEFORE_LATIN, EDGE_AFTER_LATIN)),
            ("first", [first], [first], (EDGE_AFTER_LATIN,)),
            ("second", [second], [second], (EDGE_BEFORE_LATIN,)),
        ]
        for name, messages, quoted, found in scenes:
            run, payload, printed = planted_run(tools, place / name, messages, text)
            judge_found(run, payload, found)
            judge_listing(payload, printed.stdout, quoted, planted)


# (c) No ``zh_CN`` catalogue. The page quotes M1 (the scenario's row 1), which a
# ``zh_CN`` catalogue would exempt. With none the report names the path it tried
# and "0 finished message(s) read", nothing is exempted, and the findings are
# those of the same page judged without the exemption. A catalogue of another
# language that holds M1 is not read for it.
NO_CATALOGUE = re.compile(
    re.escape(f"{HEADING_PREFIX}0), no zh_CN catalogue read (tried ")
    + r"(.+)"
    + re.escape("): 0 finished message(s) read")
    + r"(?:,.*)?"
)


def judge_no_catalogue(run: ScriptRun, payload: dict, printed: ScriptRun, tree: Tree):
    """Judge a run whose root holds no ``zh_CN`` catalogue: what it says it read."""
    block = payload["zh_quotations"]
    assert (block["exempted"], block["items"], block["finished_messages"]) == (0, [], 0)
    for rule in ZH_RULE_ROWS:
        unit = row(payload, rule, "guide", ZH_LANGUAGE)
        assert unit["quotations_exempted"] == 0, unit
    heads = [
        found
        for found in map(NO_CATALOGUE.fullmatch, printed.stdout.splitlines())
        if found
    ]
    assert len(heads) == 1, printed.stdout
    tried = Path(heads[0].group(1))
    assert tried.resolve() == (tree.root / CAT_DIR / QUOTE_CATALOGUE).resolve(), tried
    assert f"  {ZH_WHERE}:3: {QUOTE_M1.source}" not in printed.stdout.splitlines()


@REGISTRY.regression(
    mutant(
        "path-tried-not-printed",
        ty(
            "            where = f\"{where} (tried {quoted['tried']})\"\n",
            "            pass\n",
        ),
    ),
    mutant(
        "path-tried-not-recorded",
        ty(
            '    tried = os.path.join(folder, f"pixelart_{ZH_LANGUAGE}.ts")\n',
            '    tried = ""\n',
        ),
    ),
    mutant(
        "messages-read-not-named",
        ty(
            "{quoted['finished_messages']} finished message(s) read, ",
            "{quoted['finished_messages']} message(s) read, ",
        ),
    ),
    mutant(
        "another-languages-catalogue-read",
        ty(
            "                and catalogues.file_code(candidate) == ZH_LANGUAGE\n",
            "                and catalogues.file_code(candidate) is not None\n",
        ),
    ),
)
def case_a_run_with_no_zh_cn_catalogue_names_the_path_and_exempts_nothing(
    tools: Tools, work: Path
) -> None:
    """The report names the catalogue path tried and "0 finished message(s) read".

    The page quotes M1. A root with no catalogue folder, and a root whose folder
    holds only a German catalogue that carries M1, each exit 1 with the findings
    of the page judged by a ``zh_CN`` catalogue that holds nothing it quotes;
    with M1 in a ``zh_CN`` catalogue the same page exits 0 with one quotation.
    """
    page = QUOTE_ROWS[0].text
    alone_run, alone, _printed = planted_run(tools, work / "alone", [BYSTANDER], page)
    baseline = findings_of(alone)
    assert alone_run.returncode == 1 and len(baseline) == 2, baseline
    run, payload, printed = planted_run(tools, work / "control", [QUOTE_M1], page)
    judge_found(run, payload, ())
    judge_listing(payload, printed.stdout, [QUOTE_M1], [QUOTE_M1])

    none = build_tree(work / "none")
    none.page(ZH_LANGUAGE, ZH_PAGE, f"{ZH_HEAD}{page}\n")
    other = build_tree(work / "other")
    other.catalogue("de", [QUOTE_M1])
    other.page(ZH_LANGUAGE, ZH_PAGE, f"{ZH_HEAD}{page}\n")
    for tree in (none, other):
        run, payload = scan(tools, tree, "--surface", "guide")
        printed = text_of(tools, tree, "--surface", "guide")
        assert run.returncode == printed.returncode == 1, (run.stdout, printed.stdout)
        assert findings_of(payload) == baseline, (tree.root, payload["rules"])
        judge_no_catalogue(run, payload, printed, tree)


# (d) The wording clause, by behaviour. The wording-free message ``%1（%2`` quotes
# no wording, so it exempts nothing: its page, ``3（R``, is judged as if no
# message were planted, and both rule-(b) edges inside the shortest run (the digit
# beside the mark, the mark beside the Latin letter) are findings. A message that
# does quote wording (``%1（abc%2``) exempts the same shape of page.
WORDING_FREE = Msg("%1 (%2", "%1（%2")
WORDING_FULL = Msg("%1 (abc%2", "%1（abc%2")
WORDING_FREE_EDGES = (
    at(ZH_MARK_LATIN, "between 3 and ", "（", NOTHING_BETWEEN),
    at(ZH_MARK_LATIN, "between ", "（", " and R: ", NOTHING_BETWEEN),
)


@REGISTRY.regression(
    QUOTE_NO_WORDING_PASSES,
    mutant(
        "any-character-outside-the-placeholders-is-wording",
        ty(
            "    return texts, any(char.isalpha() for char in outside)\n",
            "    return texts, bool(outside)\n",
        ),
    ),
)
def case_a_message_with_no_wording_exempts_nothing(tools: Tools, work: Path) -> None:
    """The edges inside a wording-free message's run are findings; with wording, exempt.

    ``3（R`` against ``%1（%2`` exits 1 naming both edges, lists no quotation and
    gives the findings of the same page with no message that matches it.
    ``3（abcR`` against ``%1（abc%2`` exits 0 with the one quotation.
    """
    run, payload, printed = planted_run(tools, work / "free", [WORDING_FREE], "3（R")
    judge_found(run, payload, WORDING_FREE_EDGES)
    judge_listing(payload, printed.stdout, [], [WORDING_FREE])
    none_run, none, _printed = planted_run(tools, work / "none", [BYSTANDER], "3（R")
    assert none_run.returncode == 1, (none_run.stdout, none_run.stderr)
    assert findings_of(payload) == findings_of(none), (payload["rules"], none["rules"])

    text = "3（abcR"
    run, payload, printed = planted_run(tools, work / "full", [WORDING_FULL], text)
    judge_found(run, payload, ())
    judge_listing(payload, printed.stdout, [WORDING_FULL], [WORDING_FULL])
    bare_run, bare, _printed = planted_run(tools, work / "bare", [BYSTANDER], text)
    assert bare_run.returncode == 1 and len(findings_of(bare)) == 2, bare["rules"]


# --------------------------------------------------------------------------- #
# The generic tests: every case against the real script and its broken copies.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", REGISTRY.real())
def test_case_holds_on_the_real_script(case: Case, tmp_path: Path) -> None:
    """The clean fixture exits 0 and the broken one exits 1, as the case states."""
    work = tmp_path / "work"
    work.mkdir()
    case.run(Tools(SCRIPTS_DIR), work)


@pytest.mark.parametrize(("case", "broken"), REGISTRY.broken())
def test_case_fails_on_a_broken_copy(
    case: Case, broken: Mutant, tmp_path: Path
) -> None:
    """With the defended rule removed from a copy of the script the case fails."""
    tools = make_broken(tmp_path / "scripts", broken)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(AssertionError):
        case.run(tools, work)


def test_every_case_has_a_broken_copy() -> None:
    """A case registered without a mutant would be a control that controls nothing."""
    assert REGISTRY.cases
    assert [case.name for case in REGISTRY.cases if not case.mutants] == []


def test_an_unmodified_copy_loads_its_sibling_and_behaves_alike(
    tmp_path: Path,
) -> None:
    """The machinery is neutral: a copy with no edit passes the cases.

    The copy holds the catalogue reader beside it, which the script loads from
    its own folder.
    """
    tools = make_broken(tmp_path / "scripts", Mutant("unmodified", ()))
    for case in REGISTRY.cases[:3]:
        work = tmp_path / case.name
        work.mkdir()
        case.run(tools, work)
