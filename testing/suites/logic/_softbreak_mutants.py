"""The broken-copy proof for the soft-line-break rule.

Not a test module (its name does not start with ``test_``): a runner. For each named
mutant it writes a copy of ``pixelart_creator/logic/guide_softbreak.py`` with ONE thing
broken, points the suite at the copy through ``SOFTBREAK_MUTANT_FILE`` and runs
``test_guide_softbreak.py`` and ``test_guide_softbreak_tables.py``. A mutant is KILLED
when the run fails at least one test (pytest exit code 1). A control run on an
unmodified copy must pass first, or the table is not printed: it proves that the
mechanism (the copy is what the tests loaded) works.

The 22 named mutants are M1 to M8 with M4b in M4's place (the eight clause and scanner
mutants), S1 to S6 (the six structural ones), E1 (the entity rule dropped), the four
joiner and guard mutants: M-J (the joiner pairs beside backticks and brackets dropped),
M-P (the paragraph-wide preservation check dropped), M-A (the permissive-link guard
dropped) and M-T (the delimiter-row header guard dropped), and the three table mutants:
M-D (the guard after a delimiter-shaped line dropped), M-S (the table start reverted to
the cell-count rule) and M-E (the rule for what ends a table dropped).
M1 is "each clause disabled in turn" and is run as its four variants M1a to M1d; M6 has
the variant M6b. M4, the two clauses tried in the other order, is EQUIVALENT (no code
point is both East Asian Width A and F/W/H), so it is run and reported but not counted.
The ``X*`` mutants are extra. ``MUST_BE_KILLED_BY`` names, for a mutant, the tests that
must be among its killers (M-D: both ``TestRegressionDelimiterShapedLine`` and P2-T): the run reports each.

A run that is not complete because the Emoji table is missing has failures
that are not mutants' doing. The control run records them as the BASELINE, and a
mutant counts as killed only by a test that the control passes. ``--pending`` names
what the baseline may contain; anything else in the control stops the run.

Usage (from the product repository root, under the ``.python-version`` interpreter)::

    py -3.13 testing/suites/logic/_softbreak_mutants.py [--plugin NAME] [--json PATH]

The source file is only READ. Copies go under ``ORCH_TEST_TMP`` (or the system
temporary folder) and are deleted at the end.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from _softbreak_support import (  # type: ignore[import-not-found]
    make_scratch,
    remove_scratch,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = REPO_ROOT / "pixelart_creator" / "logic" / "guide_softbreak.py"
TEST_FILES = (
    "testing/suites/logic/test_guide_softbreak.py",
    "testing/suites/logic/test_guide_softbreak_join.py",
    "testing/suites/logic/test_guide_softbreak_tablemodel.py",
    "testing/suites/logic/test_guide_softbreak_tables.py",
)

Patch = Tuple[str, str]

#: A backslash, built here so that no string literal of this file holds a path-like
#: ``word<backslash>word`` (scripts/path_portability_check.py).
BACKSLASH = chr(92)

SWAP_OLD = (
    "    if _is_wide(before) and _is_wide(after):\n"
    "        return SoftBreakClause.WIDE_PAIR\n"
    "    if language in CLAUSE3_LANGUAGES and (\n"
    "        (_is_ambiguous_mark(before) and _is_wide(after))\n"
    "        or (_is_ambiguous_mark(after) and _is_wide(before))\n"
    "    ):\n"
    "        return SoftBreakClause.AMBIGUOUS_PUNCTUATION\n"
)
SWAP_NEW = (
    "    if language in CLAUSE3_LANGUAGES and (\n"
    "        (_is_ambiguous_mark(before) and _is_wide(after))\n"
    "        or (_is_ambiguous_mark(after) and _is_wide(before))\n"
    "    ):\n"
    "        return SoftBreakClause.AMBIGUOUS_PUNCTUATION\n"
    "    if _is_wide(before) and _is_wide(after):\n"
    "        return SoftBreakClause.WIDE_PAIR\n"
)
RELABEL_OLD = (
    "        return SoftBreakClause.WIDE_PAIR\n"
    "    if language in CLAUSE3_LANGUAGES and ("
)
RELABEL_NEW = (
    "        return SoftBreakClause.AMBIGUOUS_PUNCTUATION\n"
    "    if language in CLAUSE3_LANGUAGES and ("
)

#: id -> (description, patches). Every patch must match exactly once.
MUTANTS: Dict[str, Tuple[str, Sequence[Patch]]] = {
    "M1a": ("clause 1 disabled", [("    if zero_width in pair:", "    if False:")]),
    "M1b": (
        "clause 2 disabled",
        [("    if _is_wide(before) and _is_wide(after):", "    if False:")],
    ),
    "M1c": (
        "clause 3 disabled",
        [("    if language in CLAUSE3_LANGUAGES and (", "    if False and (")],
    ),
    "M1d": (
        "clause 4 disabled",
        [("    if language in CLAUSE4_LANGUAGES and (", "    if False and (")],
    ),
    "M2": (
        "the Hangul exclusion dropped",
        [
            (
                "    return _width(ch) in _WIDE and not _is_hangul(ch)",
                "    return _width(ch) in _WIDE",
            )
        ],
    ),
    "M3": (
        "HANGUL_RANGES (the Syllables block) used in place of the script table",
        [
            (
                "import bisect\n",
                "import bisect\nimport pixelart_creator.logic.constants as _C\n",
            ),
            (
                "    return _in_ranges(GUIDE_HANGUL_SCRIPT_RANGES, _HANGUL_STARTS, ch)",
                "    return _in_ranges(_C.HANGUL_RANGES, _starts(_C.HANGUL_RANGES), ch)",
            ),
        ],
    ),
    "M4": (
        "clauses 2 and 3 swapped (the order of the two tests)",
        [(SWAP_OLD, SWAP_NEW)],
    ),
    "M4b": ("clauses 2 and 3 swapped (their labels)", [(RELABEL_OLD, RELABEL_NEW)]),
    "M5": (
        "the language test ignored (clauses 3 and 4 in every page)",
        [
            ("    if language in CLAUSE3_LANGUAGES and (", "    if True and ("),
            ("    if language in CLAUSE4_LANGUAGES and (", "    if True and ("),
        ],
    ),
    "M6": (
        "str.rstrip() in place of the space-and-tab strip (trailing)",
        [
            (
                "text = _NEWLINE.join(raw.rstrip(_SPACE_TAB) for raw in raws)",
                "text = _NEWLINE.join(raw.rstrip() for raw in raws)",
            ),
            (
                "position += len(raws[k].rstrip(_SPACE_TAB))",
                "position += len(raws[k].rstrip())",
            ),
            (
                "    start = this.offset + len(this.text.rstrip(_SPACE_TAB))\n"
                "    end = following.offset + paragraph[k + 1].start\n"
                "    left, right",
                "    start = this.offset + len(this.text.rstrip())\n"
                "    end = following.offset + paragraph[k + 1].start\n"
                "    left, right",
            ),
            (
                "    start = this.offset + len(this.text.rstrip(_SPACE_TAB))\n"
                "    end = following.offset + paragraph[k + 1].start\n"
                "    return _Edit(",
                "    start = this.offset + len(this.text.rstrip())\n"
                "    end = following.offset + paragraph[k + 1].start\n"
                "    return _Edit(",
            ),
        ],
    ),
    "M6b": (
        "str.isspace() in place of the space-and-tab test (leading)",
        [
            (
                "while pos < len(self.text) and self.text[pos] in _SPACE_TAB:\n            col +=",
                "while pos < len(self.text) and self.text[pos].isspace():\n            col +=",
            )
        ],
    ),
    "M7": (
        "the joiner dropped",
        [
            (
                "    if left in _EMPHASIS_CHARS or right in _EMPHASIS_CHARS:\n"
                "        return SOFT_BREAK_JOINER\n"
                '    return SOFT_BREAK_JOINER if (left, right) in _JOINER_PAIRS else ""',
                '    return ""',
            )
        ],
    ),
    "M8": (
        "the code-span (excluded line ending) test dropped",
        [
            (
                "if _is_hard_break(raws[k]) or kinds[newline_at] is _Kind.EXCLUDED:",
                "if _is_hard_break(raws[k]):",
            )
        ],
    ),
    "S1": (
        "setext detection dropped",
        [
            (
                "        if self._para_in_matched() and _SETEXT.match(rest):\n",
                "        if False and self._para_in_matched() and _SETEXT.match(rest):\n",
            )
        ],
    ),
    "S2": (
        "the HTML-block start conditions dropped",
        [
            (
                '        if not rest.startswith("<"):\n            return False',
                "        if True:\n            return False",
            )
        ],
    ),
    "S3": (
        "quote nesting not tracked (a second > opens nothing)",
        [
            (
                "            self._open_block()\n"
                "            self._mark_content(whole_stack=True)\n"
                "            self.stack.append(_Container(is_quote=True, has_content=True))\n",
                "            if not any(c.is_quote for c in self.stack):\n"
                "                self._open_block()\n"
                "                self._mark_content(whole_stack=True)\n"
                "                self.stack.append(_Container(is_quote=True, has_content=True))\n",
            )
        ],
    ),
    "S4": (
        "the list content column off by one",
        [
            (
                "                indent=(ncol - cur.col) + marker_width + gap,",
                "                indent=(ncol - cur.col) + marker_width + gap + 1,",
            )
        ],
    ),
    "S5": (
        "table detection dropped (re-anchored to the current _table_start)",
        [
            (
                "        leaf = self.leaf\n        if (\n            leaf is None\n            or _delimiter_cells(rest) is None\n",
                "        return False\n        leaf = self.leaf\n        if (\n            leaf is None\n            or _delimiter_cells(rest) is None\n",
            )
        ],
    ),
    "S6": (
        "link reference definitions read as text",
        [
            (
                '    end = _parse_label(text, pos)\n    if end is None or end >= len(text) or text[end] != ":":',
                '    return None\n    end = _parse_label(text, pos)\n    if end is None or end >= len(text) or text[end] != ":":',
            )
        ],
    ),
    "E1": (
        "the entity rule dropped (references are plain visible text)",
        [
            (
                "        match = _ENTITY.match(self.text, i)\n        if match is None:\n            return i + 1\n",
                "        return i + 1\n        match = _ENTITY.match(self.text, i)\n        if match is None:\n            return i + 1\n",
            )
        ],
    ),
    "M-J": (
        "the joiner pairs beside backticks and brackets dropped (the joiner only beside * _ ~)",
        [
            (
                '_JOINER_PAIRS = frozenset({("`", "`"), ("]", "("), ("]", "["), ("]", ":"), ("!", "[")})',
                "_JOINER_PAIRS = frozenset()",
            )
        ],
    ),
    "M-P": (
        "paragraph-wide preservation check dropped (no preservation check over the joined paragraph)",
        [
            (
                "        if not _keeps_parse(text, kinds, definitions, cuts):",
                "        if False:",
            )
        ],
    ),
    "M-A": (
        "permissive-link guard dropped (no guard for the shape of a permissive link)",
        [
            (
                "            or _forms_link_shape(raws[k], raws[k + 1])\n",
                "            or False\n",
            )
        ],
    ),
    "M-T": (
        "delimiter-row header guard dropped (the header candidate of a delimiter row is not kept)",
        [
            (
                "            or (k + 2 < len(paragraph) and paragraph[k + 2].delimiter_like)\n",
                "            or False\n",
            )
        ],
    ),
    "M-D": (
        "post-delimiter guard dropped (the break after a delimiter-shaped line is not kept)",
        [
            (
                "        elif (\n            paragraph[k].delimiter_like\n",
                "        elif (\n            False\n",
            )
        ],
    ),
    "M-S": (
        "table start reverted to the cell-count rule (a table under any paragraph line)",
        [
            (
                "        if len(leaf.lines) != 1:\n"
                "            self._delimiter_like = True\n"
                "            return False\n"
                "        self.leaf = _OpenLeaf(_Leaf.TABLE)\n"
                "        return True\n",
                "        header = leaf.lines[-1]\n"
                "        header_text = self.lines[header.index].text[header.start :]\n"
                "        if len(_split_cells(header_text)) != _delimiter_cells(rest):\n"
                "            self._delimiter_like = True\n"
                "            return False\n"
                "        leaf.lines.pop()\n"
                "        if leaf.lines:\n"
                "            self._finish_paragraph(leaf.lines)\n"
                "        self.leaf = _OpenLeaf(_Leaf.TABLE)\n"
                "        return True\n",
            )
        ],
    ),
    "M-E": (
        "table-end rule dropped (a heading, fence or HTML start, and an indented line, end a table)",
        [
            (
                "        in_table = self._kind_is(_Leaf.TABLE) and self._all_matched\n",
                "        in_table = False\n",
            ),
            (
                "            if indent >= GUIDE_MD_CODE_INDENT:\n                if in_paragraph:\n",
                "            if indent >= GUIDE_MD_CODE_INDENT:\n"
                "                if in_paragraph or (self._kind_is(_Leaf.TABLE) and self._all_matched):\n",
            ),
        ],
    ),
    "X8": (
        "(extra) table-end rule, its first half only: a heading, fence or HTML start ends a table",
        [
            (
                "        in_table = self._kind_is(_Leaf.TABLE) and self._all_matched\n",
                "        in_table = False\n",
            )
        ],
    ),
    "X9": (
        "(extra) table-end rule, its second half only: an indented line continues a table",
        [
            (
                "            if indent >= GUIDE_MD_CODE_INDENT:\n                if in_paragraph:\n",
                "            if indent >= GUIDE_MD_CODE_INDENT:\n"
                "                if in_paragraph or (self._kind_is(_Leaf.TABLE) and self._all_matched):\n",
            )
        ],
    ),
    "X1": (
        "(extra) the emoji rule dropped",
        [("    if width in _EMOJI_AS_AMBIGUOUS and _is_emoji(ch):", "    if False:")],
    ),
    "X2": (
        "(extra) decimal digits dropped from clause 4",
        [
            (
                '    return _is_latin_letter(ch) or unicodedata.category(ch) == "Nd"',
                "    return _is_latin_letter(ch)",
            )
        ],
    ),
    "X3": (
        "(extra) CR and CRLF are not line endings",
        [
            (
                '_LINE_ENDING = re.compile(r"@r@n|@r|@n")'.replace("@", BACKSLASH),
                '_LINE_ENDING = re.compile(r"@n")'.replace("@", BACKSLASH),
            )
        ],
    ),
    "X4": (
        "(extra) hard breaks are not recognised",
        [
            (
                '    spaces = len(raw) - len(raw.rstrip(" "))\n    if spaces >= GUIDE_MD_HARD_BREAK_SPACES:\n        return True\n',
                '    return False\n    spaces = len(raw) - len(raw.rstrip(" "))\n    if spaces >= GUIDE_MD_HARD_BREAK_SPACES:\n        return True\n',
            )
        ],
    ),
    "X5": (
        "(extra) the joiner is looked for on the after side only",
        [
            (
                "    if left in _EMPHASIS_CHARS or right in _EMPHASIS_CHARS:",
                "    if right in _EMPHASIS_CHARS:",
            )
        ],
    ),
    "X6": (
        "(extra) a backslash run is always a hard break",
        [
            (
                "    return backslashes % GUIDE_MD_ESCAPE_LENGTH == 1",
                "    return backslashes >= 1",
            )
        ],
    ),
    "X7": (
        "(extra) a break kept as UNDECIDED beside a tab is decided instead",
        [
            (
                "            or following.tabby\n            or following.delimiter_like\n",
                "            or following.delimiter_like\n",
            )
        ],
    ),
}

#: What the control run may fail: the Emoji cases while the table is missing, by name.
#: Every other control failure stops the run (the delimiter-shaped-line regression case
#: must pass).
MISSING_EMOJI_CASES = r"Emoji|emoji"

#: The 22 named mutants, as the variants that are run.
NAMED = {
    "M1": ["M1a", "M1b", "M1c", "M1d"],
    "M2": ["M2"],
    "M3": ["M3"],
    "M4b": ["M4b"],
    "M5": ["M5"],
    "M6": ["M6", "M6b"],
    "M7": ["M7"],
    "M8": ["M8"],
    "S1": ["S1"],
    "S2": ["S2"],
    "S3": ["S3"],
    "S4": ["S4"],
    "S5": ["S5"],
    "S6": ["S6"],
    "E1": ["E1"],
    "M-J": ["M-J"],
    "M-P": ["M-P"],
    "M-A": ["M-A"],
    "M-T": ["M-T"],
    "M-D": ["M-D"],
    "M-S": ["M-S"],
    "M-E": ["M-E"],
}  # fmt: skip

#: For a mutant, substrings of test ids that MUST be among its killers (all of its failed
#: tests are searched, not the first three). M-D is the positive control of the table idempotence property.
MUST_BE_KILLED_BY = {
    "M-D": (
        "TestRegressionDelimiterShapedLine",
        "test_p2t_the_transform_is_idempotent",
    ),
    "M-S": (
        "header-of-three-cells-then-two-rows",
        "one-line-header-then-two-rows",
        "header-candidate-is-a-second-line",
        "header-candidate-is-a-third-line",
    ),
    "M-E": (
        "an-atx-heading-is-a-body-row",
        "a-fence-is-a-body-row",
        "an-indented-line-ends-the-table",
    ),
}

#: Run and reported, never counted: no test can kill them.
EQUIVALENT = {
    "M4": "clauses 2 and 3 tried in the other order: no code point is both A and F/W/H",
}

REQUIRED = [variant for variants in NAMED.values() for variant in variants]


def apply_patches(source: str, patches: Sequence[Patch]) -> str:
    """Apply each patch, which must match exactly once."""
    for old, new in patches:
        count = source.count(old)
        if count != 1:
            raise SystemExit(f"patch matched {count} times, expected 1: {old[:70]!r}")
        source = source.replace(old, new)
    return source


def run_suite(
    mutant_file: Optional[Path], plugin: Optional[str], extra: Sequence[str]
) -> Tuple[int, List[str], str]:
    """Run the two test files; return the exit code, the failed node ids and the tail."""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if mutant_file is not None:
        env["SOFTBREAK_MUTANT_FILE"] = str(mutant_file)
    else:
        env.pop("SOFTBREAK_MUTANT_FILE", None)
    command = [
        sys.executable, "-m", "pytest", *TEST_FILES,
        "-q", "-n", "auto", "-p", "no:cacheprovider", "--no-header", "--tb=no", "-rf",
        *extra,
    ]  # fmt: skip
    if plugin:
        command += ["-p", plugin]
    done = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    out = done.stdout + done.stderr
    failed = re.findall(r"^FAILED (\S+)", out, flags=re.MULTILINE)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return done.returncode, failed, tail


def short(node: str) -> str:
    """Trim a node id to ``Class::test`` or ``test``."""
    return node.split("::", 1)[1] if "::" in node else node


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--plugin", help="a pytest plugin module to load with -p (optional)"
    )
    parser.add_argument("--json", help="write the table as JSON to this path")
    parser.add_argument("--only", nargs="*", help="run only these mutant ids")
    args = parser.parse_args(argv)

    original = SOURCE.read_bytes().decode("utf-8")
    scratch = make_scratch()
    rows = []
    try:
        control = scratch / "control" / "guide_softbreak.py"
        control.parent.mkdir()
        control.write_bytes(original.encode("utf-8"))
        code, failed, tail = run_suite(control, args.plugin, [])
        print(f"CONTROL (unmodified copy): exit {code}, failed {len(failed)}: {tail}")
        baseline = {node for node in failed}
        unexpected = [n for n in baseline if not re.search(MISSING_EMOJI_CASES, n)]
        if code not in (0, 1) or unexpected:
            print(
                "The control run failed outside the pending Emoji cases: the table would prove nothing."
            )
            for node in unexpected:
                print(f"  unexpected: {node}")
            return 2
        if baseline:
            print(
                f"  the control fails only {len(baseline)} cases (Emoji cases that need the table) "
                f"(the baseline; a mutant must fail a test outside it)"
            )
        ids = args.only or list(MUTANTS)
        for key in ids:
            description, patches = MUTANTS[key]
            mutated = apply_patches(original, patches)
            assert mutated != original
            target = scratch / key / "guide_softbreak.py"
            target.parent.mkdir()
            target.write_bytes(mutated.encode("utf-8"))
            code, failed, tail = run_suite(target, args.plugin, [])
            new_failures = [node for node in failed if node not in baseline]
            failed = new_failures
            killed = code == 1 and bool(failed)
            status = (
                "KILLED" if killed else ("ERROR" if code not in (0, 1) else "SURVIVED")
            )
            if status == "SURVIVED" and key in EQUIVALENT:
                status = "EQUIVALENT"
            killers = sorted({short(node) for node in failed})
            rows.append(
                {
                    "id": key,
                    "description": description,
                    "status": status,
                    "exit": code,
                    "failed": len(failed),
                    "killers": killers[:3],
                    "killers_all": killers,
                    "summary": tail,
                }
            )
            print(f"{key:4} {status:8} failed {len(failed):4}  {description}")
            for node in killers[:3]:
                print(f"       killed by: {node}")
            for token in MUST_BE_KILLED_BY.get(key, ()):
                hit = [k for k in killers if token in k]
                print(
                    f"       required killer {token!r}: "
                    + (f"present ({len(hit)}, e.g. {hit[0]})" if hit else "MISSING")
                )
    finally:
        remove_scratch(scratch)
    by_id = {r["id"]: r for r in rows}
    print()
    named_killed = 0
    for name, variants in NAMED.items():
        ran = [by_id[v] for v in variants if v in by_id]
        ok = (
            bool(ran)
            and len(ran) == len(variants)
            and all(r["status"] == "KILLED" for r in ran)
            and all(
                any(token in k for k in r["killers_all"])
                for r in ran
                for token in MUST_BE_KILLED_BY.get(r["id"], ())
            )
        )
        named_killed += ok
        killers = sorted({k for r in ran for k in r["killers"]})[:2]
        print(f"NAMED {name:4} {'KILLED' if ok else 'NOT KILLED':10} by {killers}")
    print(f"named mutants killed: {named_killed}/{len(NAMED)}")
    for key, why in EQUIVALENT.items():
        if key in by_id:
            print(f"EQUIVALENT {key}: {by_id[key]['status']} ({why})")
    survivors = [r["id"] for r in rows if r["status"] not in ("KILLED", "EQUIVALENT")]
    print(f"not killed (extras included): {survivors}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
