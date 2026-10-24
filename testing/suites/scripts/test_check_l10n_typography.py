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
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from .conftest import SCRIPTS_DIR, ScriptRun
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
        """Write one guide page of ``language`` as UTF-8 bytes."""
        path = self.root / GUIDE_DIR / language / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path


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
    """Scan a root holding one guide page and nothing else."""
    tree = build_tree(work / label)
    tree.page(language, "index.md", text)
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
    run, payload = scan(tools, guide)
    assert run.returncode == 1, (run.stdout, run.stderr)
    unit = row(payload, "no-u202f", "guide", "de")
    assert details(unit) == ["U+202F"]
    assert unit["findings"][0]["where"] == f"de/index.md:{line_of(page, NNBSP)}"


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
            '        if row["rule"] == "fr-num-unit" and parts:\n',
            "        if False:\n",
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
