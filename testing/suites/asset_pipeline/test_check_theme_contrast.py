# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Contract tests of ``scripts/check_theme_contrast.py`` (the theme contrast matrix).

One group of tests per scenario of the visual-identity specification:

* SC-VI-BUILD-001-1 - the check passes over every style and mode with a
  non-zero examined count printed for each combination.
* SC-VI-BUILD-001-2 - the check cannot pass blind: a 2.61:1 text pair fails,
  a combination with no pairs fails, a role-key mismatch fails, an unknown role
  fails.
* SC-VI-BUILD-001-3 - the focus pairs are derived from what the ring touches,
  and a deliberately thinner ring is seen touching frame colours (control).
* SC-VI-UI-004-1 - every text pair is at least 4.5:1, every component and focus
  pair at least 3:1, and the number of pairs examined is printed and not zero.
* SC-VI-UI-004-2 - the worst measured margins stay above their floors.

The committed theme data is only ever READ. A test that needs a broken theme
works on a copy of ``pixelart_creator/themes`` under ``tmp_path``.

Independence of the numbers: the script measures through
``pixelart_creator.logic.contrast``; the test below that recomputes every opaque
ratio with its own WCAG formula (written from the WCAG definition, not imported)
is what shows the script's figures are not merely self-consistent.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

import scripts.check_theme_contrast as ctc
from pixelart_creator.data import style_catalog
from pixelart_creator.logic.contrast import ContrastPair, PairKind
from pixelart_creator.logic.theme_art import (
    Slices,
    Template,
    TemplateSet,
    ThemeArtError,
    focus_touch_roles,
    parse_grid,
)

from .conftest import REPO_ROOT, run_script

SCRIPT = "check_theme_contrast.py"
_BLANK_GRID = "___\n___\n___"
_THEMES = REPO_ROOT / "pixelart_creator" / "themes"

TEXT_FLOOR = 4.5
GATED_FLOOR = 3.0


def _catalog() -> style_catalog.StyleCatalog:
    return style_catalog.load_catalog(_THEMES)


def _run_json(*extra: str) -> Tuple[int, Dict[str, Any]]:
    result = run_script(SCRIPT, ["--json", *extra])
    try:
        return result.returncode, json.loads(result.stdout)
    except ValueError:
        return result.returncode, {"stdout": result.stdout, "stderr": result.stderr}


def _combo(doc: Dict[str, Any], style: str, mode: str) -> Dict[str, Any]:
    for combo in doc["combinations"]:
        if combo["label"] == f"{style}/{mode}":
            return combo
    raise AssertionError(
        f"no combination {style}/{mode} in {[c['label'] for c in doc['combinations']]}"
    )


def _row(combo: Dict[str, Any], fg: str, bg: str) -> Dict[str, Any]:
    matches = [r for r in combo["rows"] if r["fg"] == fg and r["bg"] == bg]
    assert matches, f"{combo['label']}: no row {fg} on {bg}"
    return matches[0]


def _scratch_themes(tmp_path: Path) -> Path:
    """A COPY of the committed themes folder; the real one is never edited."""
    scratch = tmp_path / "themes"
    shutil.copytree(_THEMES, scratch)
    return scratch


def _edit_roles(themes: Path, style: str, mode: str, **changes: str) -> None:
    path = themes / style / "roles.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["modes"][mode].update(changes)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-001-1 / SC-VI-UI-004-1: the shipped themes pass, with counts.   #
# --------------------------------------------------------------------------- #


def test_sc_vi_build_001_1_shipped_themes_pass_with_a_nonzero_count_each():
    """SC-VI-BUILD-001-1: exit 0 and a non-zero examined count per combination."""
    cat = _catalog()
    expected = len(cat.style_ids()) * len(cat.mode_ids())
    code, doc = _run_json()
    assert code == 0, f"check_theme_contrast exited {code}: {doc.get('failures', doc)}"
    assert len(doc["combinations"]) == expected, (
        f"{len(doc['combinations'])} combinations examined, the catalogue has "
        f"{expected} (styles x modes)"
    )
    assert expected > 0
    for combo in doc["combinations"]:
        assert combo["gated_examined"] > 0, f"{combo['label']}: no gated pair examined"
        assert combo["fail"] == 0 and combo["errors"] == 0, combo["label"]
    assert doc["failures"] == []


def test_sc_vi_build_001_1_the_text_output_prints_the_examined_count_per_combination():
    """SC-VI-BUILD-001-1: the matrix prints one non-zero count per combination."""
    cat = _catalog()
    expected = len(cat.style_ids()) * len(cat.mode_ids())
    result = run_script(SCRIPT, [])
    assert result.returncode == 0, result.stdout
    lines = re.findall(
        r"^\s+examined (\d+): .*gated (\d+) \(pass (\d+), fail (\d+)\)",
        result.stdout,
        re.M,
    )
    assert (
        len(lines) == expected
    ), f"{len(lines)} summary lines for {expected} combinations"
    for examined, gated, passed, failed in lines:
        assert int(examined) > 0 and int(gated) > 0
        assert int(passed) == int(gated) and int(failed) == 0
    assert "RESULT: PASS" in result.stdout
    assert re.search(r"role-key parity: \d+ role map\(s\) examined", result.stdout)


def test_sc_vi_ui_004_1_the_examined_counts_equal_an_independent_denominator():
    """SC-VI-UI-004-1: gated count == declared non-info pairs + roles the ring touches.

    The denominator is rebuilt here from the catalogue and the focus derivation,
    not read back from the script, so a script that silently dropped pairs would
    disagree with it.
    """
    cat = _catalog()
    declared_gated = sum(1 for p in cat.contrast_pairs() if p.kind is not PairKind.INFO)
    code, doc = _run_json()
    assert code == 0
    for style in cat.style_ids():
        touched = focus_touch_roles(cat.template_set(style))
        assert touched, f"{style}: the focus derivation is empty"
        for mode in cat.mode_ids():
            combo = _combo(doc, style, mode)
            assert combo["gated_examined"] == declared_gated + len(touched), combo[
                "label"
            ]
            assert combo["declared"] == len(cat.contrast_pairs())
            assert combo["derived_focus"] == len(touched)


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _wcag_ratio(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio of two opaque ``#RRGGBB`` colours (definition)."""

    def lum(hexval: str) -> float:
        r, g, b = (int(hexval[i : i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)

    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_sc_vi_ui_004_1_every_opaque_ratio_matches_an_independent_wcag_formula():
    """SC-VI-UI-004-1: the printed ratios are WCAG ratios, not self-consistent."""
    code, doc = _run_json()
    assert code == 0
    compared = 0
    for combo in doc["combinations"]:
        for row in combo["rows"]:
            if len(row["fg_hex"]) == 7 and len(row["bg_hex"]) == 7:
                assert row["ratio"] == pytest.approx(
                    _wcag_ratio(row["fg_hex"], row["bg_hex"]), abs=1e-9
                ), f"{combo['label']}: {row['fg']} on {row['bg']}"
                compared += 1
    assert compared > 0, "no opaque row was compared"


def test_sc_vi_ui_004_1_every_gated_pair_meets_its_floor():
    """SC-VI-UI-004-1: text >= 4.5, component and focus >= 3, read from the matrix."""
    code, doc = _run_json()
    assert code == 0
    gated = 0
    for combo in doc["combinations"]:
        for row in combo["rows"]:
            if row["kind"] == "info":
                continue
            floor = TEXT_FLOOR if row["kind"] == "text" else GATED_FLOOR
            assert (
                row["floor"] == floor
            ), f"{combo['label']}: {row['fg']} on {row['bg']}"
            assert (
                row["ratio"] >= floor
            ), f"{combo['label']}: {row['fg']} on {row['bg']}"
            gated += 1
    assert gated > 0


# --------------------------------------------------------------------------- #
# SC-VI-UI-004-2: the worst measured margins.                                 #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_004_2_washi_kintsugi_dark_accent_text_on_accent_is_at_least_4_5():
    """SC-VI-UI-004-2: accent_text on accent >= 4.5 in Washi & Kintsugi Dark."""
    _code, doc = _run_json()
    ratio = _row(_combo(doc, "washi-kintsugi", "dark"), "accent_text", "accent")[
        "ratio"
    ]
    assert ratio >= TEXT_FLOOR, f"accent_text on accent measures {ratio:.3f}"


def test_sc_vi_ui_004_2_edo_night_dark_focus_on_accent_is_at_least_3():
    """SC-VI-UI-004-2: focus on accent >= 3 in Edo Night Dark."""
    _code, doc = _run_json()
    row = _row(_combo(doc, "edo-night", "dark"), "focus", "accent")
    assert row["kind"] == "focus" and row["origin"] == "derived"
    assert row["ratio"] >= GATED_FLOOR, f"focus on accent measures {row['ratio']:.3f}"


def test_sc_vi_ui_004_2_arcade_kikko_dark_accent_text_on_accent_is_at_least_4_5():
    """SC-VI-UI-004-2: accent_text on accent >= 4.5 in Arcade Kikko Dark.

    The third style is not committed yet; until it is, this criterion is
    reported as NOT verified (a skip with its reason), not as a pass.
    """
    if "arcade-kikko" not in _catalog().style_ids():
        pytest.skip("could not verify: the arcade-kikko style is not committed yet")
    _code, doc = _run_json()
    ratio = _row(_combo(doc, "arcade-kikko", "dark"), "accent_text", "accent")["ratio"]
    assert ratio >= TEXT_FLOOR, f"accent_text on accent measures {ratio:.3f}"


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-001-2: the check cannot pass blind.                             #
# --------------------------------------------------------------------------- #


def test_sc_vi_build_001_2_control_mode_shows_a_known_failing_pair_failing():
    """SC-VI-BUILD-001-2: ``--control`` shows 2.61:1 text failing (exit 0)."""
    result = run_script(SCRIPT, ["--control"])
    assert result.returncode == 0, result.stdout
    assert "FAIL at 2.61" in result.stdout, result.stdout
    assert "PASS at 21.000" in result.stdout, result.stdout
    assert "controls: 6/6 behave as designed" in result.stdout, result.stdout


def test_sc_vi_build_001_2_a_failing_text_pair_in_the_data_fails_the_run(tmp_path):
    """SC-VI-BUILD-001-2: a #a0a0a0 text role on a light ground exits 1 and is named."""
    themes = _scratch_themes(tmp_path)
    _edit_roles(themes, "washi-kintsugi", "light", text="#a0a0a0")
    result = run_script(SCRIPT, ["--themes-dir", str(themes), "--json"])
    assert result.returncode == 1, result.stdout
    doc = json.loads(result.stdout)
    combo = _combo(doc, "washi-kintsugi", "light")
    row = _row(combo, "text", "background")
    assert row["status"] == "FAIL" and row["ratio"] < TEXT_FLOOR
    # the failure is local: the unedited combinations still pass
    assert _combo(doc, "washi-kintsugi", "dark")["fail"] == 0
    assert _combo(doc, "edo-night", "light")["fail"] == 0
    assert any("washi-kintsugi/light" in f for f in doc["failures"]), doc["failures"]


def test_sc_vi_build_001_2_a_failing_derived_focus_pair_fails_the_run(tmp_path):
    """SC-VI-BUILD-001-2: a focus colour equal to a touched ground fails."""
    themes = _scratch_themes(tmp_path)
    cat = _catalog()
    surface = cat.role_map("edo-night", "dark")["surface"]
    # focus must still differ from accent (the loader enforces it): use surface
    _edit_roles(themes, "edo-night", "dark", focus=surface)
    code, doc = _run_json("--themes-dir", str(themes))
    assert code == 1
    row = _row(_combo(doc, "edo-night", "dark"), "focus", "surface")
    assert row["origin"] == "derived" and row["status"] == "FAIL"
    assert row["ratio"] == pytest.approx(1.0)


def test_sc_vi_build_001_2_an_empty_pair_list_is_refused(tmp_path):
    """SC-VI-BUILD-001-2: a pair list with no pairs exits 1 (the data does not load)."""
    themes = _scratch_themes(tmp_path)
    (themes / "contrast-pairs.json").write_text("[]", encoding="utf-8")
    result = run_script(SCRIPT, ["--themes-dir", str(themes)])
    assert result.returncode == 1, result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_sc_vi_build_001_2_a_role_key_mismatch_is_refused(tmp_path):
    """SC-VI-BUILD-001-2: a role missing from one mode exits 1 with the key named."""
    themes = _scratch_themes(tmp_path)
    path = themes / "edo-night" / "roles.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["modes"]["dark"]["pattern"]
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    result = run_script(SCRIPT, ["--themes-dir", str(themes)])
    assert result.returncode == 1, result.stdout
    assert "pattern" in result.stdout, result.stdout


def test_sc_vi_build_001_2_a_missing_themes_folder_is_a_usage_error(tmp_path):
    """SC-VI-BUILD-001-2: a folder that does not exist exits 2, never 0."""
    result = run_script(SCRIPT, ["--themes-dir", str(tmp_path / "nowhere")])
    assert result.returncode == 2, (result.stdout, result.stderr)


def _fake_catalog(
    roles: Dict[str, Dict[str, str]],
    pairs: List[ContrastPair],
    thin_ring: bool = False,
    rings: bool = True,
) -> Any:
    return ctc.control_catalog(pairs, roles, thin_ring=thin_ring, rings=rings)


def test_sc_vi_build_001_2_zero_gated_pairs_in_a_combination_fails_the_run():
    """SC-VI-BUILD-001-2: info-only pairs and no focus ring leave nothing to gate."""
    pairs = [ContrastPair("text", "background", PairKind.INFO)]
    report = ctc.evaluate(
        _fake_catalog({"light": ctc.CONTROL_ROLES}, pairs, rings=False)
    )
    assert report.gated_examined == 0
    reasons = report.failures()
    assert any("zero gated pairs" in r for r in reasons), reasons


def test_sc_vi_build_001_2_a_report_over_no_combination_fails():
    """SC-VI-BUILD-001-2: zero combinations examined is a failure."""
    assert any("no (style, mode)" in r for r in ctc.Report().failures())


def test_sc_vi_build_001_2_role_key_parity_mismatch_is_reported():
    """SC-VI-BUILD-001-2: two role maps with different keys fail the parity check."""
    short = {k: v for k, v in ctc.CONTROL_ROLES.items() if k != "surface"}
    pairs = [ContrastPair("text", "background", PairKind.TEXT)]
    report = ctc.evaluate(
        _fake_catalog({"light": ctc.CONTROL_ROLES, "dark": short}, pairs)
    )
    assert report.parity_examined == 2
    assert len(report.parity_problems) == 1 and "surface" in report.parity_problems[0]
    assert any("parity" in r for r in report.failures())


def test_sc_vi_build_001_2_an_unknown_role_is_an_error_not_a_skip():
    """SC-VI-BUILD-001-2: a pair naming an absent role is an ERROR row."""
    pairs = [ContrastPair("no_such_role", "background", PairKind.TEXT)]
    report = ctc.evaluate(_fake_catalog({"light": ctc.CONTROL_ROLES}, pairs))
    combo = report.combinations[0]
    assert combo.count(ctc.ERROR) == 1
    assert any("unknown role" in e and "no_such_role" in e for e in combo.errors)
    assert report.failures()


def test_sc_vi_build_001_2_a_translucent_background_without_over_is_an_error():
    """SC-VI-BUILD-001-2: an unmeasurable pair is reported, never dropped."""
    roles = dict(ctc.CONTROL_ROLES, surface="#80ffffff")
    pairs = [
        ContrastPair("text", "background", PairKind.TEXT),
        ContrastPair("text", "surface", PairKind.TEXT),
    ]
    report = ctc.evaluate(_fake_catalog({"light": roles}, pairs))
    assert report.combinations[0].count(ctc.ERROR) >= 1
    assert report.failures()


def test_sc_vi_build_001_2_the_translucent_background_with_over_is_measured():
    """SC-VI-BUILD-001-2 (control of the test above): ``over`` makes it measurable."""
    roles = dict(ctc.CONTROL_ROLES, surface="#80ffffff")
    pairs = [
        ContrastPair("text", "background", PairKind.TEXT),
        ContrastPair("text", "surface", PairKind.TEXT, over="background"),
    ]
    report = ctc.evaluate(_fake_catalog({"light": roles}, pairs))
    rows = {(r.fg, r.bg): r for r in report.combinations[0].rows}
    assert rows[("text", "surface")].status == ctc.PASS
    declared = [r for r in report.combinations[0].rows if r.origin == "declared"]
    assert [r.status for r in declared] == [ctc.PASS, ctc.PASS]


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-001-3: focus pairs derived from what the ring touches.          #
# --------------------------------------------------------------------------- #


def test_sc_vi_build_001_3_every_touched_role_is_a_gated_focus_pair():
    """SC-VI-BUILD-001-3: each role the ring touches is a derived, gated pair."""
    cat = _catalog()
    code, doc = _run_json()
    assert code == 0
    for style in cat.style_ids():
        touched = focus_touch_roles(cat.template_set(style))
        for mode in cat.mode_ids():
            combo = _combo(doc, style, mode)
            derived = {r["bg"]: r for r in combo["rows"] if r["origin"] == "derived"}
            assert set(derived) == set(touched), combo["label"]
            for row in derived.values():
                assert row["fg"] == "focus" and row["kind"] == "focus"
                assert row["floor"] == GATED_FLOOR and row["status"] in ("PASS", "FAIL")


def test_sc_vi_build_001_3_a_thinner_indicator_is_seen_touching_frame_colours():
    """SC-VI-BUILD-001-3 (control): a 1 px ring touches frame_mid, 2 px does not."""
    thick = focus_touch_roles(ctc.control_template_set(thin_ring=False))
    thin = focus_touch_roles(ctc.control_template_set(thin_ring=True))
    assert "frame_mid" not in thick
    assert "frame_mid" in thin


def test_sc_vi_build_001_3_the_thin_ring_makes_the_run_fail_on_its_frame_pair():
    """SC-VI-BUILD-001-3: the thin ring's frame_mid pair is gated and fails the run."""
    pairs = [ContrastPair("text", "background", PairKind.TEXT)]
    report = ctc.evaluate(
        _fake_catalog({"light": ctc.CONTROL_ROLES}, pairs, thin_ring=True)
    )
    rows = {(r.fg, r.bg): r for r in report.combinations[0].rows}
    frame_pair = rows[("focus", "frame_mid")]
    assert frame_pair.origin == ctc.ORIGIN_DERIVED and frame_pair.status == ctc.FAIL
    assert report.failures()
    clean = ctc.evaluate(
        _fake_catalog({"light": ctc.CONTROL_ROLES}, pairs, thin_ring=False)
    )
    assert clean.failures() == [], clean.failures()


def test_sc_vi_build_001_3_an_empty_focus_derivation_is_an_error():
    """SC-VI-BUILD-001-3: a style whose ring assignment is empty is refused."""
    pairs = [ContrastPair("text", "background", PairKind.TEXT)]
    report = ctc.evaluate(
        _fake_catalog({"light": ctc.CONTROL_ROLES}, pairs, rings=False)
    )
    assert report.combinations[0].errors, "no error recorded for the empty derivation"
    assert report.failures()


def test_sc_vi_build_001_3_a_ring_that_touches_nothing_is_an_error_not_a_pass():
    """SC-VI-BUILD-001-3: an all-transparent ring derives nothing and is refused."""
    base = ctc.control_template_set(thin_ring=False)
    blank = Template(
        name="ring",
        grid=parse_grid(_BLANK_GRID, ctc.CONTROL_LEGEND),
        slices=Slices(1, 1, 1, 1),
        kind="overlay",
    )
    blind = TemplateSet(
        style="control",
        templates={**base.templates, "ring": blank},
        focus_rings=base.focus_rings,
        pattern=base.pattern,
    )
    with pytest.raises(ThemeArtError):
        ctc.derive_focus_pairs(blind)
    pairs = [ContrastPair("text", "background", PairKind.TEXT)]
    catalog = ctc._ControlCatalog({"light": ctc.CONTROL_ROLES}, pairs, blind)
    report = ctc.evaluate(catalog)
    assert report.combinations[0].errors
    assert report.failures()


# --------------------------------------------------------------------------- #
# The instrument's own controls.                                              #
# --------------------------------------------------------------------------- #


def test_every_built_in_control_behaves_as_designed():
    """The controls run before any real result is trusted; all must hold."""
    results = ctc.run_controls()
    assert len(results) == 6
    assert [c.name for c in results if not c.ok] == []


def test_a_misbehaving_control_stops_the_run_before_any_result_is_trusted(
    monkeypatch, capsys
):
    """SC-VI-BUILD-001-2: if the instrument fails its own control, exit 1, no matrix."""
    bad = [ctc.ControlResult("planted", "refused", "accepted", False)]
    monkeypatch.setattr(ctc, "run_controls", lambda: bad)
    assert ctc.main([]) == 1
    out = capsys.readouterr().out
    assert "no result is trusted" in out
    assert "RESULT: PASS" not in out


def test_an_instrument_with_no_controls_at_all_is_not_trusted(monkeypatch, capsys):
    """SC-VI-BUILD-001-2: zero controls run is a failure, never a vacuous pass."""
    monkeypatch.setattr(ctc, "run_controls", lambda: [])
    assert ctc.main([]) == 1
    assert "RESULT: PASS" not in capsys.readouterr().out
