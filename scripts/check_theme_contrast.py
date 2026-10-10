#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_theme_contrast  (standalone product tooling script)
# =============================================================================
# PURPOSE: Measure the WCAG contrast of every declared role pair of every
#   shipped style in every mode, and FAIL on anything that does not meet its
#   floor. Nothing is re-implemented here: the colours come from the committed
#   theme data through ``pixelart_creator.data.style_catalog``, the ratio and
#   the floors come from ``pixelart_creator.logic.contrast``, and the focus
#   pairs come from ``pixelart_creator.logic.theme_art.focus_touch_roles`` --
#   the roles the keyboard-focus ring actually touches when the framed controls
#   are composed with it, so they are MEASURED from the art, never hand-listed.
#
#   Pairs examined, per (style, mode) combination:
#     * every pair declared in ``pixelart_creator/themes/contrast-pairs.json``
#       (kind text 4.5:1, component 3:1, or info = reported, never gating);
#     * one derived ``focus`` pair (3:1) for each role the focus ring touches.
#
# THE CHECK CANNOT PASS BLIND. It exits 1 when any of these holds:
#   * a gated pair is below its floor;
#   * a pair names a role the role map lacks, or a colour cannot be measured
#     (for example a translucent background with no ``over`` role);
#   * the role-key sets of the role maps are not identical in every
#     (style, mode) combination (key parity);
#   * a combination examined zero gated pairs, or no combination was examined
#     at all, or the focus ring touched nothing (an empty derivation is a
#     blind derivation, not a clean one);
#   * a built-in control misbehaves: before any real data is trusted the
#     instrument is shown a known failing pair (2.61:1 text) and must FAIL it,
#     shown a known passing pair (21:1) and must PASS it, shown a combination
#     with no pairs, a role map with a missing key and a pair with an unknown
#     role and must refuse all three, and shown a deliberately thin focus ring
#     and must see it touching frame colours.
#
# USAGE:
#   python scripts/check_theme_contrast.py                # the shipped themes
#   python scripts/check_theme_contrast.py --control      # the controls only
#   python scripts/check_theme_contrast.py --json         # machine-readable
#   python scripts/check_theme_contrast.py --themes-dir DIR   # another copy
#
# EXIT CODES: 0 every gated pair passes, parity holds, nothing errored, every
#   count is non-zero and the controls behave as designed; 1 otherwise; 2 usage
#   problem (the themes folder does not exist).
#
# RUNTIME: Python 3.8+ with the product's own dependencies (numpy is reached
#   through ``logic.theme_art``). No Qt. Deterministic: no clock, no random,
#   no network. Rendered contrast (anti-aliasing, font hinting) is NOT measured
#   here -- every ratio is a pure function of the role colours.
# =============================================================================

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pixelart_creator.data import style_catalog  # noqa: E402
from pixelart_creator.logic.contrast import (  # noqa: E402
    ContrastError,
    ContrastPair,
    PairKind,
    contrast_ratio,
    floor_for,
)
from pixelart_creator.logic.theme_art import (  # noqa: E402
    FOCUS_ROLE,
    Slices,
    Template,
    TemplateSet,
    ThemeArtError,
    focus_touch_roles,
    parse_grid,
)

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"
ERROR = "ERROR"

ORIGIN_DECLARED = "declared"
ORIGIN_DERIVED = "derived"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

_RATIO_DIGITS = 3


# --- the measurement ---------------------------------------------------------


@dataclass(frozen=True)
class Row:
    """One measured pair."""

    fg: str
    bg: str
    kind: PairKind
    origin: str
    fg_hex: str
    bg_hex: str
    ratio: Optional[float]
    floor: Optional[float]
    status: str
    note: str = ""

    @property
    def margin(self) -> Optional[float]:
        """Ratio minus floor, for a gated pair that was measured."""
        if self.ratio is None or self.floor is None:
            return None
        return self.ratio - self.floor


@dataclass
class Combination:
    """Every pair of one (style, mode) combination."""

    style: str
    mode: str
    rows: List[Row] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.style}/{self.mode}"

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r.status == status)

    def count_origin(self, origin: str) -> int:
        return sum(1 for r in self.rows if r.origin == origin)

    @property
    def gated_examined(self) -> int:
        """Gated pairs that were actually measured (pass or fail)."""
        return self.count(PASS) + self.count(FAIL)

    def worst(self) -> Optional[Row]:
        """The measured gated row with the smallest margin."""
        measured = [r for r in self.rows if r.status in (PASS, FAIL)]
        return min(measured, key=lambda r: r.margin or 0.0) if measured else None


@dataclass
class Report:
    """The whole run."""

    combinations: List[Combination] = field(default_factory=list)
    parity_examined: int = 0
    parity_keys: int = 0
    parity_problems: List[str] = field(default_factory=list)
    derived_focus: Dict[str, Dict[str, int]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def gated_examined(self) -> int:
        return sum(c.gated_examined for c in self.combinations)

    def failures(self) -> List[str]:
        """Every reason this report must exit 1 (empty list = clean)."""
        reasons: List[str] = []
        if not self.combinations:
            reasons.append("no (style, mode) combination was examined")
        for combo in self.combinations:
            failed = combo.count(FAIL)
            if failed:
                reasons.append(f"{combo.label}: {failed} gated pair(s) below the floor")
            problems = combo.count(ERROR) + len(combo.errors)
            if problems:
                reasons.append(f"{combo.label}: {problems} error(s)")
            if combo.gated_examined == 0:
                reasons.append(f"{combo.label}: zero gated pairs examined")
        if self.parity_examined == 0:
            reasons.append("role-key parity examined zero role maps")
        if self.parity_problems:
            reasons.append(f"role-key parity: {len(self.parity_problems)} mismatch(es)")
        reasons.extend(self.errors)
        return reasons


def _measure(
    pair: ContrastPair, roles: Mapping[str, str], origin: str
) -> Tuple[Row, Optional[str]]:
    """Measure one pair against one role map; return the row and an error text."""
    needed = [pair.fg, pair.bg] + ([pair.over] if pair.over else [])
    missing = [r for r in needed if r not in roles]
    fg_hex = roles.get(pair.fg, "?")
    bg_hex = roles.get(pair.bg, "?")
    if missing:
        text = f"{pair.fg}/{pair.bg}: unknown role(s) {missing}"
        return (
            Row(pair.fg, pair.bg, pair.kind, origin, fg_hex, bg_hex, None, None, ERROR),
            text,
        )
    over_hex = roles[pair.over] if pair.over else None
    try:
        ratio = contrast_ratio(fg_hex, bg_hex, over=over_hex)
    except ContrastError as exc:
        text = f"{pair.fg}/{pair.bg}: {exc}"
        return (
            Row(pair.fg, pair.bg, pair.kind, origin, fg_hex, bg_hex, None, None, ERROR),
            text,
        )
    floor = floor_for(pair.kind)
    if floor is None:
        status = INFO
    else:
        status = PASS if ratio >= floor else FAIL
    return (
        Row(pair.fg, pair.bg, pair.kind, origin, fg_hex, bg_hex, ratio, floor, status),
        None,
    )


def derive_focus_pairs(
    template_set: TemplateSet,
) -> Tuple[Tuple[ContrastPair, ...], Dict[str, int]]:
    """Return the gated focus pairs for one style and the touch counts behind them.

    Each role the focus ring touches (4-neighbour) becomes a ``focus`` pair of
    the ring colour against that role. An empty result is an error, never a
    clean pass.

    Raises:
        ThemeArtError: If the derivation itself is impossible, or touched nothing.
    """
    touched = focus_touch_roles(template_set)
    if not touched:
        raise ThemeArtError(
            f"{template_set.style}: the focus ring touched no role at all"
        )
    pairs = tuple(
        ContrastPair(
            fg=FOCUS_ROLE,
            bg=role,
            kind=PairKind.FOCUS,
            note=f"derived: ring touches {role} in {count} adjacent pixel pair(s)",
        )
        for role, count in touched.items()
    )
    return pairs, touched


def evaluate(catalog: Any) -> Report:
    """Measure every pair of every (style, mode) of ``catalog``.

    ``catalog`` needs the read surface of ``style_catalog.StyleCatalog``:
    ``style_ids()``, ``mode_ids()``, ``role_map(style, mode)``,
    ``contrast_pairs()`` and ``template_set(style)``.
    """
    report = Report()
    declared = tuple(catalog.contrast_pairs())
    key_sets: Dict[str, frozenset] = {}
    for style in catalog.style_ids():
        derived: Tuple[ContrastPair, ...] = ()
        derive_error: Optional[str] = None
        try:
            derived, touched = derive_focus_pairs(catalog.template_set(style))
            report.derived_focus[style] = touched
        except (ThemeArtError, style_catalog.StyleCatalogError) as exc:
            derive_error = f"{style}: focus pairs could not be derived: {exc}"
            report.derived_focus[style] = {}
        for mode in catalog.mode_ids():
            roles = catalog.role_map(style, mode)
            key_sets[f"{style}/{mode}"] = frozenset(roles)
            combo = Combination(style, mode)
            if derive_error:
                combo.errors.append(derive_error)
            for pair, origin in [(p, ORIGIN_DECLARED) for p in declared] + [
                (p, ORIGIN_DERIVED) for p in derived
            ]:
                row, error = _measure(pair, roles, origin)
                combo.rows.append(row)
                if error:
                    combo.errors.append(error)
            report.combinations.append(combo)
    report.parity_examined = len(key_sets)
    if key_sets:
        reference_label, reference = next(iter(key_sets.items()))
        report.parity_keys = len(reference)
        for label, keys in key_sets.items():
            if keys != reference:
                diff = sorted(keys ^ reference)
                report.parity_problems.append(
                    f"{label} differs from {reference_label}: {diff}"
                )
    return report


# --- the controls --------------------------------------------------------------


class _ControlCatalog:
    """A tiny in-memory catalogue with the read surface ``evaluate`` needs."""

    def __init__(
        self,
        roles: Mapping[str, Mapping[str, str]],
        pairs: Sequence[ContrastPair],
        template_set: TemplateSet,
    ) -> None:
        self._roles = roles
        self._pairs = tuple(pairs)
        self._templates = template_set

    def style_ids(self) -> Tuple[str, ...]:
        return ("control",)

    def mode_ids(self) -> Tuple[str, ...]:
        return tuple(self._roles)

    def role_map(self, style: str, mode: str) -> Dict[str, str]:
        return dict(self._roles[mode])

    def contrast_pairs(self) -> Tuple[ContrastPair, ...]:
        return self._pairs

    def template_set(self, style: str) -> TemplateSet:
        return self._templates


CONTROL_LEGEND: Dict[str, Optional[str]] = {
    "_": None,
    "E": "frame_edge",
    "M": "frame_mid",
    "S": "surface",
    "F": FOCUS_ROLE,
}
CONTROL_ROLES: Dict[str, str] = {
    "background": "#ffffff",
    "surface": "#f4f4f4",
    "text": "#000000",
    "frame_edge": "#202020",
    "frame_mid": "#707070",
    FOCUS_ROLE: "#1f3a93",
}


def _template(name: str, rows: Sequence[str], inset: int, kind: str) -> Template:
    return Template(
        name=name,
        grid=parse_grid("\n".join(rows), CONTROL_LEGEND),
        slices=Slices(inset, inset, inset, inset),
        kind=kind,
    )


def control_template_set(thin_ring: bool, rings: bool = True) -> TemplateSet:
    """A one-control template set with either a 1 px or a 2 px focus ring.

    The control is a two-ring frame (``frame_edge`` outside, ``frame_mid``
    inside) round a ``surface`` fill. A 2 px ring covers both frame rings, so it
    touches only the grounds and the fill; a 1 px ring covers the outer ring
    alone, so it sits next to the inner frame ring - and it must be seen
    touching ``frame_mid``.
    """
    control = _template(
        "button",
        ["EEEEE", "EMMME", "EMSME", "EMMME", "EEEEE"],
        2,
        "nine-slice",
    )
    if thin_ring:
        ring = _template("ring", ["FFF", "F_F", "FFF"], 1, "overlay")
    else:
        ring = _template(
            "ring",
            ["FFFFFF", "FFFFFF", "FF__FF", "FF__FF", "FFFFFF", "FFFFFF"],
            2,
            "overlay",
        )
    return TemplateSet(
        style="control",
        templates={"button": control, "ring": ring},
        focus_rings={"button": "ring"} if rings else {},
        pattern=_template("pattern", ["EE", "EE"], 0, "pattern"),
    )


def control_catalog(
    pairs: Sequence[ContrastPair],
    roles: Optional[Mapping[str, Mapping[str, str]]] = None,
    thin_ring: bool = False,
    rings: bool = True,
) -> _ControlCatalog:
    return _ControlCatalog(
        roles if roles is not None else {"light": CONTROL_ROLES},
        pairs,
        control_template_set(thin_ring, rings),
    )


@dataclass(frozen=True)
class ControlResult:
    """The outcome of one control: what was expected, what was seen."""

    name: str
    expected: str
    observed: str
    ok: bool


def run_controls() -> List[ControlResult]:
    """Run every built-in control; ``ok`` means the instrument behaved as designed."""
    results: List[ControlResult] = []
    text = PairKind.TEXT

    def add(name: str, expected: str, observed: str, ok: bool) -> None:
        results.append(ControlResult(name, expected, observed, ok))

    good = [ContrastPair("text", "background", text)]

    # A passing pair passes, at the exactly-known WCAG maximum.
    report = evaluate(control_catalog(good))
    row = report.combinations[0].rows[0]
    add(
        "known passing pair (#000000 on #ffffff, text)",
        "PASS at 21.000 and the run is clean",
        (
            f"{row.status} at {row.ratio:.3f}, failures {len(report.failures())}"
            if row.ratio is not None
            else f"{row.status}, no ratio"
        ),
        row.status == PASS
        and row.ratio is not None
        and abs(row.ratio - 21.0) < 1e-9
        and not report.failures(),
    )

    # A failing pair fails: #a0a0a0 on #ffffff is 2.61:1, under the 4.5 text floor.
    weak_roles = dict(CONTROL_ROLES, text="#a0a0a0")
    report = evaluate(control_catalog(good, {"light": weak_roles}))
    row = report.combinations[0].rows[0]
    add(
        "known failing pair (#a0a0a0 on #ffffff, text)",
        "FAIL at 2.61 and the run exits non-zero",
        (
            f"{row.status} at {row.ratio:.2f}, failures {len(report.failures())}"
            if row.ratio is not None
            else f"{row.status}, no ratio"
        ),
        row.status == FAIL
        and row.ratio is not None
        and round(row.ratio, 2) == 2.61
        and bool(report.failures()),
    )

    # A combination with no pairs cannot pass: no declared pair and a template
    # set that assigns no focus ring leaves nothing to gate, and the derivation
    # itself refuses an empty ring assignment (an empty result is not a pass).
    report = evaluate(control_catalog([], rings=False))
    add(
        "role map with no pairs and no focus pairs",
        "refused: zero gated pairs examined",
        f"gated examined {report.gated_examined}, failures {len(report.failures())}",
        report.gated_examined == 0 and bool(report.failures()),
    )

    # Key parity: two modes whose role maps differ in one key.
    short = {k: v for k, v in CONTROL_ROLES.items() if k != "surface"}
    report = evaluate(
        control_catalog(
            [ContrastPair("text", "background", text)],
            {"light": CONTROL_ROLES, "dark": short},
        )
    )
    add(
        "role maps with different key sets",
        "refused: role-key parity mismatch",
        f"parity problems {len(report.parity_problems)}, "
        f"failures {len(report.failures())}",
        bool(report.parity_problems) and bool(report.failures()),
    )

    # An unknown role is an error, never skipped.
    report = evaluate(
        control_catalog([ContrastPair("no_such_role", "background", text)])
    )
    add(
        "pair naming a role the map lacks",
        "ERROR row and the run exits non-zero",
        f"errors {report.combinations[0].count(ERROR)}, "
        f"failures {len(report.failures())}",
        report.combinations[0].count(ERROR) == 1 and bool(report.failures()),
    )

    # Focus derivation: a 2 px ring touches no frame colour, a 1 px ring does.
    thick = focus_touch_roles(control_template_set(thin_ring=False))
    thin = focus_touch_roles(control_template_set(thin_ring=True))
    add(
        "focus ring of 2 px versus a deliberately thinner 1 px ring",
        "2 px ring touches no frame role; 1 px ring touches frame_mid",
        f"2 px touches {sorted(thick)}; 1 px touches {sorted(thin)}",
        "frame_mid" not in thick and "frame_mid" in thin,
    )
    return results


# --- the output ------------------------------------------------------------------


def _fmt_ratio(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.{_RATIO_DIGITS}f}"


def _fmt_row(row: Row) -> str:
    floor = "-" if row.floor is None else f"{row.floor:g}"
    margin = "" if row.margin is None else f" ({row.margin:+.3f})"
    return (
        f"  {row.status:<5} {row.kind.value:<9} {row.origin:<8} "
        f"{row.fg:>16} on {row.bg:<22} {row.fg_hex} / {row.bg_hex}  "
        f"{_fmt_ratio(row.ratio):>7} >= {floor}{margin}"
    )


def render_text(report: Report, controls: Sequence[ControlResult]) -> str:
    """Render the whole run as the matrix the command prints."""
    out: List[str] = []
    passed_controls = sum(1 for c in controls if c.ok)
    out.append(
        f"check_theme_contrast: controls {passed_controls}/{len(controls)} "
        "behave as designed"
    )
    for combo in report.combinations:
        out.append("")
        out.append(f"== {combo.label} ==")
        for row in combo.rows:
            out.append(_fmt_row(row))
        for error in combo.errors:
            out.append(f"  ERROR {error}")
        worst = combo.worst()
        worst_text = (
            "none measured"
            if worst is None
            else f"{worst.fg} on {worst.bg} {_fmt_ratio(worst.ratio)} "
            f"(margin {worst.margin:+.3f})"
        )
        problems = combo.count(ERROR) + len(combo.errors)
        out.append(
            f"  examined {len(combo.rows)}: "
            f"declared {combo.count_origin(ORIGIN_DECLARED)} + "
            f"derived focus {combo.count_origin(ORIGIN_DERIVED)}; "
            f"gated {combo.gated_examined} "
            f"(pass {combo.count(PASS)}, fail {combo.count(FAIL)}); "
            f"info {combo.count(INFO)}; errors {problems}"
        )
        out.append(f"  worst gated margin: {worst_text}")
    out.append("")
    for style, touched in report.derived_focus.items():
        listing = ", ".join(f"{role} x{n}" for role, n in touched.items()) or "NONE"
        out.append(f"focus pairs derived for {style}: {listing}")
    if report.parity_problems:
        out.append(f"role-key parity: FAILED over {report.parity_examined} role map(s)")
        out.extend(f"  {p}" for p in report.parity_problems)
    else:
        out.append(
            f"role-key parity: {report.parity_examined} role map(s) examined, "
            f"{report.parity_keys} key(s) each, identical"
        )
    out.append(
        f"TOTAL: {len(report.combinations)} combination(s); gated pairs examined "
        f"{report.gated_examined}; "
        f"pass {sum(c.count(PASS) for c in report.combinations)}, "
        f"fail {sum(c.count(FAIL) for c in report.combinations)}; "
        f"info {sum(c.count(INFO) for c in report.combinations)}; "
        f"errors {sum(c.count(ERROR) + len(c.errors) for c in report.combinations)}"
    )
    reasons = report.failures()
    if reasons:
        out.append("RESULT: FAIL")
        out.extend(f"  - {r}" for r in reasons)
    else:
        out.append("RESULT: PASS")
    return "\n".join(out)


def render_controls(controls: Sequence[ControlResult]) -> str:
    """Render the control table the ``--control`` flag prints."""
    out = ["check_theme_contrast --control: the instrument is shown known inputs"]
    for c in controls:
        out.append(f"  {'ok  ' if c.ok else 'BAD '} {c.name}")
        out.append(f"       expected: {c.expected}")
        out.append(f"       observed: {c.observed}")
    good = sum(1 for c in controls if c.ok)
    out.append(f"controls: {good}/{len(controls)} behave as designed")
    return "\n".join(out)


def report_as_dict(report: Report, controls: Sequence[ControlResult]) -> Dict[str, Any]:
    """The run as a JSON-ready dictionary (the ``--json`` output)."""
    return {
        "controls": {
            "total": len(controls),
            "ok": sum(1 for c in controls if c.ok),
        },
        "combinations": [
            {
                "label": c.label,
                "examined": len(c.rows),
                "declared": c.count_origin(ORIGIN_DECLARED),
                "derived_focus": c.count_origin(ORIGIN_DERIVED),
                "gated_examined": c.gated_examined,
                "pass": c.count(PASS),
                "fail": c.count(FAIL),
                "info": c.count(INFO),
                "errors": c.count(ERROR) + len(c.errors),
                "rows": [
                    {
                        "fg": r.fg,
                        "bg": r.bg,
                        "kind": r.kind.value,
                        "origin": r.origin,
                        "fg_hex": r.fg_hex,
                        "bg_hex": r.bg_hex,
                        "ratio": r.ratio,
                        "floor": r.floor,
                        "status": r.status,
                    }
                    for r in c.rows
                ],
            }
            for c in report.combinations
        ],
        "parity": {
            "examined": report.parity_examined,
            "keys": report.parity_keys,
            "problems": report.parity_problems,
        },
        "derived_focus": report.derived_focus,
        "gated_examined": report.gated_examined,
        "failures": report.failures(),
    }


# --- the driver ------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Measure the WCAG contrast of every role pair of every style "
        "and mode; fail on any miss, any error and any blind run."
    )
    ap.add_argument(
        "--themes-dir",
        default=None,
        help="a themes folder to read instead of the shipped pixelart_creator/themes",
    )
    ap.add_argument(
        "--control",
        action="store_true",
        help="run only the built-in controls (a known failing pair must fail, "
        "a known passing pair must pass, blind inputs must be refused)",
    )
    ap.add_argument("--json", action="store_true", help="print the run as JSON")
    args = ap.parse_args(argv)

    controls = run_controls()
    controls_ok = bool(controls) and all(c.ok for c in controls)

    if args.control:
        print(render_controls(controls))
        return EXIT_OK if controls_ok else EXIT_FAILED

    root: Optional[Path] = None
    if args.themes_dir is not None:
        root = Path(args.themes_dir)
        if not root.is_dir():
            print(f"check_theme_contrast: not a directory: {root}", file=sys.stderr)
            return EXIT_USAGE

    if not controls_ok:
        print(render_controls(controls))
        print("check_theme_contrast: a control misbehaved; no result is trusted")
        return EXIT_FAILED

    try:
        catalog = style_catalog.load_catalog(root)
    except style_catalog.StyleCatalogError as exc:
        print(f"check_theme_contrast: the theme data does not load: {exc}")
        print("RESULT: FAIL")
        return EXIT_FAILED

    report = evaluate(catalog)
    if args.json:
        print(json.dumps(report_as_dict(report, controls), indent=1))
    else:
        print(render_text(report, controls))
    return EXIT_FAILED if report.failures() else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
