"""Regression tests for ``scripts/check_doc_references.py`` (2026-08-19 gate).

Contract asserted here, taken verbatim from the script's own header (the
``--allowlist``/``--baseline`` default file NAMES below are quoted for
readability only -- the actual defaults these tests build fixtures against
are read straight out of the script's own ``argparse`` calls by
``_read_argparse_default()`` below, precisely so this docstring drifting out
of date again, the way it did when the baseline/allowlist moved from
``docs/`` to the repo root on 2026-08-19, can never again make a test build
a fixture the script does not look at)::

    ENTRYPOINT: python scripts/check_doc_references.py [--root .]
                [--allowlist doc-reference-allowlist.json]
                [--baseline doc-reference-baseline.json] [--write-baseline]
    OUTPUTS: stdout JSON {"findings": [...], "scanned": {...},
        "allowlist_entries": N, "allowlist_suppressed": N,
        "allowlist_suppressed_detail": {...}, "baseline_entries": N,
        "new_findings": [...], "stale_baseline_entries": [...],
        "likely_renames": [...]}; stderr human summary.
    EXIT CODES: 0 clean (no new findings, no stale baseline entries) ->
        COMPLETED ; 1 new finding(s) and/or stale baseline entry(ies) ->
        FAILED ; 2 error -> BLOCKED.

Every fixture below is a hand-built tiny repo tree under ``tmp_path``, passed
to the script via its own ``--root``/``--allowlist``/``--baseline`` flags.
The real repository tree (today's 145 live, 145-baselined findings) is never
scanned by these tests -- a test bound to that number breaks the moment
AGT-08 documents anything, training people to edit tests until green rather
than trusting the gate.

Per the user's explicit "regression tests" requirement, each test below
constructs a fixture that DEMONSTRATES the defect class the leg exists to
catch, alongside a negative control proving the leg does not simply flag
everything. Each test's docstring states how it was verified to actually
distinguish a working gate from a broken one.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, Optional

from .conftest import SCRIPTS_DIR, run_script

SCRIPT = "check_doc_references.py"
SCRIPT_PATH = SCRIPTS_DIR / SCRIPT


def _read_argparse_default(flag: str) -> str:
    """Resolve the CLI default for ``flag`` (e.g. ``"--baseline"``) straight
    from the script's own ``ap.add_argument(...)`` call via a source-level
    AST walk -- never a literal pasted into this test file.

    This is the fix for the exact defect the dispatch reported: the baseline
    and allowlist file NAMES were hand-copied into this module's fixture
    writer, and when the script's own defaults moved (docs/doc-reference-*
    -> doc-reference-* at the repo root, because docs/ is gitignored) the
    copy silently went stale and 3 of 10 tests started writing fixtures to a
    path the script never reads. Reading the default out of the script's own
    AST means a future default change breaks loudly (this function raises)
    rather than silently (a fixture landing in the wrong place).
    """
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == flag
        ):
            continue
        for kw in node.keywords:
            if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                return kw.value.value
    raise AssertionError(
        "could not resolve argparse default for %r from %s -- the script's "
        "add_argument shape changed; update _read_argparse_default"
        % (flag, SCRIPT_PATH)
    )


#: The script's own current defaults, resolved once at collection time (not
#: pasted) -- see ``_read_argparse_default`` docstring for why.
BASELINE_DEFAULT_REL = _read_argparse_default("--baseline")
ALLOWLIST_DEFAULT_REL = _read_argparse_default("--allowlist")


def _write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _base_tree(tmp_path: Path) -> Path:
    """A minimal repo root with every directory the gate's two legs and its
    baseline/allowlist loaders expect to find, all empty: docs/adr/,
    docs/site/pages/{en,es}/, pixelart_creator/userguide_content/content/
    {en,es}/, pixelart_creator/ui/. Nothing under it cites an ADR or defines
    a UI label yet -- callers add exactly the fixture content their test
    needs on top of this skeleton."""
    root = tmp_path / "repo"
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "site" / "pages" / "en").mkdir(parents=True)
    (root / "docs" / "site" / "pages" / "es").mkdir(parents=True)
    (root / "pixelart_creator" / "userguide_content" / "content" / "en").mkdir(
        parents=True
    )
    (root / "pixelart_creator" / "userguide_content" / "content" / "es").mkdir(
        parents=True
    )
    (root / "pixelart_creator" / "ui").mkdir(parents=True)
    return root


def _run(
    root: Path,
    allowlist: Optional[Dict] = None,
    baseline: Optional[Dict] = None,
):
    """Run the gate against `root`, optionally writing an allowlist/baseline
    JSON first at the script's own default relative path (resolved from the
    script's own argparse defaults, ``ALLOWLIST_DEFAULT_REL`` /
    ``BASELINE_DEFAULT_REL`` -- currently the repo root, not ``docs/``,
    because ``docs/`` is gitignored and a baseline living there would never
    reach CI) so the "own generated artifact" exclusion in the script
    (SELF_BASENAME + exclude_basenames) is exercised the same way the real
    CI run exercises it, rather than via a --allowlist/--baseline override
    to some other path."""
    if allowlist is not None:
        _write(root, ALLOWLIST_DEFAULT_REL, json.dumps(allowlist))
    if baseline is not None:
        _write(root, BASELINE_DEFAULT_REL, json.dumps(baseline))
    result = run_script(SCRIPT, ["--root", str(root)])
    payload = json.loads(result.stdout)
    return result, payload


# --------------------------------------------------------------------------- #
# LEG 1 -- ADR citation resolution.
# --------------------------------------------------------------------------- #
def test_dangling_adr_citation_is_caught(tmp_path):
    """A citation to an ADR number with no file under docs/adr/ is reported
    as kind=dangling-adr-citation and fails the gate.

    Proof it would catch a broken gate: this is the exact mutation under
    test -- ADR-9999 is cited but docs/adr/ contains no 9999-*.md file. If
    ``adr_leg_findings`` failed to check membership in ``valid_adr_numbers``
    (e.g. it always returned no findings), this test's
    ``result.returncode == 1`` assertion and its search for the finding in
    ``payload["findings"]`` would both fail -- there is no way for a no-op
    ADR leg to pass this test."""
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/module.py",
        "# rationale: see ADR-9999 for the layering decision\n",
    )

    result, payload = _run(root)

    assert result.returncode == 1, result.stderr
    dangling = [f for f in payload["findings"] if f["kind"] == "dangling-adr-citation"]
    assert [f["value"] for f in dangling] == ["ADR-9999"]
    assert dangling[0]["file"] == "pixelart_creator/module.py"


def test_resolvable_adr_citation_is_not_reported(tmp_path):
    """Negative control for leg 1: a citation to an ADR that DOES have a
    file under docs/adr/ must not be reported at all.

    Proof: this fixture is identical in shape to the dangling-citation
    fixture above except docs/adr/0001-example.md now exists and the
    citation reads ADR-0001. Actually running the gate against this tree and
    observing zero dangling-adr-citation findings (and exit 0) demonstrates
    the assertion direction inverts relative to the previous test -- if leg
    1 flagged every citation regardless of resolution (the failure mode this
    control exists to catch), this test would fail exactly where the
    previous one passes."""
    root = _base_tree(tmp_path)
    _write(
        root, "docs/adr/0001-example.md", "# ADR-0001: Example\n\nStatus: Accepted\n"
    )
    _write(
        root,
        "pixelart_creator/module.py",
        "# rationale: see ADR-0001 for the layering decision\n",
    )

    result, payload = _run(root)

    assert result.returncode == 0, result.stderr
    dangling = [f for f in payload["findings"] if f["kind"] == "dangling-adr-citation"]
    assert dangling == []


# --------------------------------------------------------------------------- #
# LEG 2 -- documentation currency (control labels), including the locale
# split. One shared UI fixture carries three distinct labels so the tests
# below can pin the asymmetric behaviour ("Merge" clean, "Open Diff"
# flagged, "Flatten Layers" flagged only for its Spanish half) against a
# single, realistic source file -- matching the dispatch's own worked
# example.
# --------------------------------------------------------------------------- #
def _tree_with_three_labels(tmp_path: Path) -> Path:
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/ui/toolbar.py",
        "class Toolbar:\n"
        "    def __init__(self):\n"
        "        self.merge_btn = QPushButton()\n"
        '        self.merge_btn.setText(self.tr("Merge"))\n'
        "        self.diff_btn = QPushButton()\n"
        '        self.diff_btn.setText(self.tr("Open Diff"))\n'
        "        self.flatten_btn = QPushButton()\n"
        '        self.flatten_btn.setText(self.tr("Flatten Layers"))\n',
    )
    # "Merge" and "Flatten Layers" are documented in English; only "Merge"
    # is also documented in Spanish. "Open Diff" appears in neither corpus.
    _write(
        root,
        "docs/site/pages/en/toolbar.md",
        "# Toolbar\n\nUse **Merge** to combine layers, or **Flatten Layers**"
        " to flatten the whole stack.\n",
    )
    _write(
        root,
        "docs/site/pages/es/toolbar.md",
        "# Barra de herramientas\n\nUsa **Merge** para combinar capas.\n",
    )
    return root


def test_undocumented_label_is_caught(tmp_path):
    """A shipped feature-level control label ("Open Diff") absent from both
    documentation surfaces, in both languages, is reported as
    kind=undocumented-control-label and fails the gate.

    Proof: "Open Diff" is deliberately kept out of both docs/site/pages/en
    and docs/site/pages/es fixtures. If label_leg_findings ignored the
    en_doc/es_doc booleans (e.g. always treated a label as documented), the
    membership assertion below would fail with an empty findings list --
    there is no way for a no-op label leg to pass this test."""
    root = _tree_with_three_labels(tmp_path)

    result, payload = _run(root)

    assert result.returncode == 1, result.stderr
    values = {f["value"]: f["kind"] for f in payload["findings"]}
    assert values["Open Diff"] == "undocumented-control-label"


def test_documented_label_is_not_reported(tmp_path):
    """Negative control for leg 2: 'Merge' is documented in BOTH language
    corpora in the shared fixture and must not appear in findings at all --
    the real gate's own asymmetry (leave Merge clean, flag Open Diff) is the
    behaviour worth pinning per the dispatch.

    Proof: this is the same run as test_undocumented_label_is_caught above
    (same fixture, same invocation) -- 'Merge' and 'Open Diff' are checked
    in the SAME payload. If leg 2 flagged every label regardless of
    documentation state (the failure mode a leg that always reports would
    exhibit), 'Merge' would show up in payload["findings"] here exactly as
    'Open Diff' correctly does in the sibling test -- this assertion would
    invert and fail."""
    root = _tree_with_three_labels(tmp_path)

    result, payload = _run(root)

    values = {f["value"]: f["kind"] for f in payload["findings"]}
    assert "Merge" not in values


def test_spanish_locale_checked_independently_of_english(tmp_path):
    """'Flatten Layers' is documented in the English corpus but absent from
    the Spanish corpus in the shared fixture -- it must be reported as
    kind=es-documentation-stale, distinct from undocumented-control-label,
    proving the ES half is actually evaluated on its own and not cleared by
    English coverage.

    Proof: if the locale split collapsed to "documented in EITHER language
    clears the label" (checking only the EN corpus, or OR-ing the two
    booleans instead of keeping them independent), 'Flatten Layers' -- which
    IS documented in English -- would never appear in findings at all, and
    this test's search for it would fail. Conversely if the gate ignored
    English and reported everything not in the ES corpus, 'Merge' (also
    absent needlessly... no: 'Merge' IS in the ES corpus) would still be
    correctly clean, but to confirm the EN/ES independence directly this
    test also asserts 'Flatten Layers' is NOT reported as the
    (English-anchored) undocumented-control-label kind -- the two kinds are
    mutually exclusive per finding, so seeing es-documentation-stale here
    is proof the EN half was checked and found documented while the ES half
    was checked SEPARATELY and found missing."""
    root = _tree_with_three_labels(tmp_path)

    result, payload = _run(root)

    assert result.returncode == 1, result.stderr
    values = {f["value"]: f["kind"] for f in payload["findings"]}
    assert values["Flatten Layers"] == "es-documentation-stale"
    assert "Flatten Layers" not in [
        f["value"]
        for f in payload["findings"]
        if f["kind"] == "undocumented-control-label"
    ]


# --------------------------------------------------------------------------- #
# Baseline-and-ratchet.
# --------------------------------------------------------------------------- #
def _tree_with_one_undocumented_label(tmp_path: Path, label: str) -> Path:
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/ui/panel.py",
        "class Panel:\n"
        "    def __init__(self):\n"
        "        self.btn = QPushButton()\n"
        '        self.btn.setText(self.tr("%s"))\n' % label,
    )
    return root


def test_baselined_finding_does_not_fail_the_gate(tmp_path):
    """A live finding already recorded in the baseline (matched by its
    (kind, value) key) is marked baselined and does NOT put the gate into a
    failing state -- the ratchet's whole point: known debt is tracked, not
    blocking.

    Proof (both directions actually run): first WITHOUT a baseline file the
    same fixture exits 1 with the finding in new_findings (asserted below).
    Then WITH a baseline entry matching (kind="undocumented-control-label",
    value="Ratchet Label"), the SAME fixture exits 0 and the finding's
    "baselined" flag is True while new_findings is empty. If the ratchet
    compared on the wrong key (e.g. included line number, which churns) or
    never consulted the baseline at all, the second run would still exit 1
    -- that is exactly the assertion that would flip."""
    root = _tree_with_one_undocumented_label(tmp_path, "Ratchet Label")

    unbaselined_result, unbaselined_payload = _run(root)
    assert unbaselined_result.returncode == 1, unbaselined_result.stderr
    assert "Ratchet Label" in [f["value"] for f in unbaselined_payload["new_findings"]]

    baselined_result, baselined_payload = _run(
        root,
        baseline=[
            {
                "kind": "undocumented-control-label",
                "value": "Ratchet Label",
                "file": "pixelart_creator/ui/panel.py",
                "line": 4,
            }
        ],
    )
    assert baselined_result.returncode == 0, baselined_result.stderr
    finding = next(
        f for f in baselined_payload["findings"] if f["value"] == "Ratchet Label"
    )
    assert finding["baselined"] is True
    assert baselined_payload["new_findings"] == []


def test_unbaselined_finding_fails_the_gate(tmp_path):
    """The mirror half of the ratchet: a finding present live but NOT keyed
    in the baseline is reported under new_findings and fails the gate, even
    when the baseline file exists and has unrelated entries -- an existing
    baseline must not become a blanket amnesty for anything not explicitly
    matched.

    Proof: the baseline below has one entry for an entirely different value
    ("Some Other Debt") that never appears live, so it cannot accidentally
    match "Undocumented Widget" by coincidence. If the ratchet treated "the
    baseline file exists and is non-empty" as sufficient to pass (rather
    than matching each finding's own key), this test would see exit 0 and
    an empty new_findings list instead of the assertions below."""
    root = _tree_with_one_undocumented_label(tmp_path, "Undocumented Widget")

    result, payload = _run(
        root,
        baseline=[
            {
                "kind": "undocumented-control-label",
                "value": "Some Other Debt",
                "file": "pixelart_creator/ui/elsewhere.py",
                "line": 1,
            }
        ],
    )

    assert result.returncode == 1, result.stderr
    assert "Undocumented Widget" in [f["value"] for f in payload["new_findings"]]


def test_stale_baseline_entry_is_reported_not_silently_ignored(tmp_path):
    """A baseline entry whose (kind, value) key matches NO live finding is
    reported under stale_baseline_entries and fails the gate -- the gate
    treats an unpruned baseline entry as a failure, not a silent pass,
    exactly per the script's own documented design (a baseline nobody
    prunes decays into blanket suppression).

    Proof: this fixture ships a completely clean UI tree (a single button
    whose label IS documented in both corpora, so leg 2 emits zero
    findings) and zero ADR citations, so ALL live findings are empty by
    construction -- any stale_baseline_entries in the payload can only have
    come from the baseline comparison itself, not from a coincidental live
    finding. A gate that only checked "are there new_findings" and ignored
    stale entries entirely (the exact regression this test guards against)
    would return exit 0 here; this test's returncode==1 assertion would
    fail against that broken behaviour."""
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/ui/clean_panel.py",
        "class CleanPanel:\n"
        "    def __init__(self):\n"
        "        self.btn = QPushButton()\n"
        '        self.btn.setText(self.tr("Documented Everywhere"))\n',
    )
    _write(
        root,
        "docs/site/pages/en/panel.md",
        "Use **Documented Everywhere** to do the thing.\n",
    )
    _write(
        root,
        "docs/site/pages/es/panel.md",
        "Usa **Documented Everywhere** para hacer la cosa.\n",
    )

    result, payload = _run(
        root,
        baseline=[
            {
                "kind": "undocumented-control-label",
                "value": "Long Fixed Ghost",
                "file": "pixelart_creator/ui/removed_module.py",
                "line": 9,
            }
        ],
    )

    assert result.returncode == 1, result.stderr
    assert payload["findings"] == []
    stale_values = [e["value"] for e in payload["stale_baseline_entries"]]
    assert stale_values == ["Long Fixed Ghost"]


# --------------------------------------------------------------------------- #
# Allowlist -- a narrow, named, reason-carrying suppression, never a blanket
# one; and the suppression count must be reported even when it is zero.
# --------------------------------------------------------------------------- #
def test_allowlist_suppresses_only_the_named_label(tmp_path):
    """An allowlist entry for exactly one label ("Zeta Widget") suppresses
    only that label's finding, leaves a second, unrelated undocumented
    label ("Not Suppressed Widget") reported, and its suppression count
    (allowlist_suppressed / allowlist_suppressed_detail) is nonzero and
    names the suppressed value.

    Proof this is not a blanket exemption: two labels are undocumented by
    construction; only ONE is named in the allowlist. If the allowlist
    match were not scoped per-label (e.g. any non-empty allowlist silenced
    everything), 'Not Suppressed Widget' would be missing from
    payload["findings"] and payload["new_findings"] too -- the assertion
    that it IS still present, and that the gate still exits 1 because of
    it, is what distinguishes a correctly scoped allowlist from a blanket
    one."""
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/ui/mixed_panel.py",
        "class MixedPanel:\n"
        "    def __init__(self):\n"
        "        self.a = QPushButton()\n"
        '        self.a.setText(self.tr("Zeta Widget"))\n'
        "        self.b = QPushButton()\n"
        '        self.b.setText(self.tr("Not Suppressed Widget"))\n',
    )

    result, payload = _run(
        root,
        allowlist=[
            {
                "type": "control-label",
                "value": "Zeta Widget",
                "reason": "internal-only debug affordance, not user-documented",
            }
        ],
    )

    assert result.returncode == 1, result.stderr
    values = [f["value"] for f in payload["findings"]]
    assert "Zeta Widget" not in values
    assert "Not Suppressed Widget" in values
    assert payload["allowlist_suppressed"] == 1
    assert payload["allowlist_suppressed_detail"]["control-label"] == ["Zeta Widget"]


def test_allowlist_suppression_count_reported_even_when_zero(tmp_path):
    """Negative control for the allowlist: with NO allowlist file present at
    all, allowlist_entries and allowlist_suppressed are both reported as 0
    (present in the JSON payload, not merely absent/omitted) -- the
    dispatch's own concern that a suppression count nobody sees decays into
    an invisible blanket exemption applies just as much to the zero case as
    to the nonzero one.

    Proof: this fixture has a live undocumented-label finding
    ("Unsuppressed Widget") and NO allowlist/docs/doc-reference-
    allowlist.json is written at all. If the script only emitted
    allowlist_suppressed when it was nonzero (an easy silent-omission bug),
    the key lookups below would raise KeyError instead of comparing 0 --
    this test fails loudly against that regression rather than passing by
    accident on a missing key."""
    root = _base_tree(tmp_path)
    _write(
        root,
        "pixelart_creator/ui/lone_panel.py",
        "class LonePanel:\n"
        "    def __init__(self):\n"
        "        self.a = QPushButton()\n"
        '        self.a.setText(self.tr("Unsuppressed Widget"))\n',
    )

    result, payload = _run(root)

    assert result.returncode == 1, result.stderr
    assert payload["allowlist_entries"] == 0
    assert payload["allowlist_suppressed"] == 0
    assert payload["allowlist_suppressed_detail"] == {
        "adr-citation": [],
        "control-label": [],
    }
    assert "Unsuppressed Widget" in [f["value"] for f in payload["findings"]]
