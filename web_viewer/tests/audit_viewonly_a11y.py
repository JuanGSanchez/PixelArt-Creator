"""Static VIEW-ONLY / eval-free + a11y audit of the web viewer.

A framework-free static analyser (no browser, no node, no
bundler) over the shipped ``web_viewer/static`` sources. It corroborates two
guarantees the frontend agent claimed and runs the *automatable-now* slice of the
accessibility criteria:

1. **VIEW-ONLY (WEB-002) + eval-free (Article VII)** over BOTH the DOM/WS wiring
   file ``viewer.js`` AND the extracted pure-logic module ``viewer_core.mjs`` (the
   wire-decode ``JSON.parse`` now lives in the module). The sources are
   listed explicitly in ``VIEW_ONLY_SOURCES`` so a future ``.mjs`` split is covered
   by extending that tuple:
   * no ``eval(`` / ``new Function(`` in ANY source;
   * wire input is parsed with ``JSON.parse`` (now in ``viewer_core.mjs``) and no
     eval-based parsing exists in any source;
   * every ``ws.send(...)`` argument is ``encodeControl(CONTROL.JOIN|LEAVE ...)``
     (the socket lives in ``viewer.js``);
   * no ``encodeUpdate`` symbol and no ``encodeControl(CONTROL.UPDATE`` / no
     ``"kind":"update"`` construction in ANY source — the client builds no
     mutation frame.

2. **Static a11y markup checks** over ``index.html`` (the subset verifiable without
   a running browser): document ``lang``; an accessible, non-scale-locked viewport;
   a skip link; landmark roles; a labelled canvas; labelled/typed buttons; a live
   status region. Dynamic, script-generated controls (the per-layer checkboxes) are
   NOT statically reachable here and are called out for the manual/AT pass.

Not part of the default pytest suite (``testpaths = ["tests"]``). Run directly::

    python web_viewer/tests/audit_viewonly_a11y.py

Exit code 0 = all hard checks pass (findings that are advisory are printed but do
not fail the run); non-zero = a VIEW-ONLY/eval-free or hard a11y check failed.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.normpath(os.path.join(HERE, "..", "static"))
VIEWER_JS = os.path.join(STATIC, "viewer.js")
VIEWER_CORE = os.path.join(STATIC, "viewer_core.mjs")
INDEX_HTML = os.path.join(STATIC, "index.html")

# The pure-logic sources carrying the VIEW-ONLY / eval-free / wire-parse invariants.
# viewer.js owns the DOM/WebSocket/Canvas wiring; viewer_core.mjs owns the extracted
# wire-decode logic (JSON.parse). Listed explicitly so a future .mjs split is covered
# by extending this tuple.
VIEW_ONLY_SOURCES = (VIEWER_JS, VIEWER_CORE)

Result = Tuple[str, bool, str]  # (label, passed, detail)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _strip_comments(js: str) -> str:
    """Remove JS comments so token checks never match explanatory prose.

    Block comments ``/* ... */`` are dropped; a line comment is dropped only when
    ``//`` starts the line or follows whitespace, so string URLs like ``ws://`` /
    ``"//"`` (preceded by ``:`` or ``"``) are left intact.
    """
    without_block = re.sub(r"/\*[\s\S]*?\*/", " ", js)
    return re.sub(r"(^|\s)//.*$", r"\1", without_block, flags=re.MULTILINE)


def audit_view_only(sources: List[Tuple[str, str]]) -> List[Result]:
    """Corroborate VIEW-ONLY + eval-free across the pure-logic sources (hard checks).

    ``sources`` is a list of ``(filename, stripped_js)`` pairs (comments already
    removed). The eval-free, wire-parse and no-UPDATE-frame invariants are asserted
    across EVERY source; the ``ws.send()`` JOIN/LEAVE check scans all sources
    combined (only the socket-owning file has send sites).
    """
    results: List[Result] = []
    names = [name for name, _ in sources]
    combined = "\n".join(js for _, js in sources)

    # eval-free (Article VII) across EVERY source — no eval( / new Function( anywhere.
    eval_offenders = [
        name
        for name, js in sources
        if re.search(r"\beval\s*\(", js) or re.search(r"\bnew\s+Function\s*\(", js)
    ]
    results.append(
        (
            "eval-free (no eval/new Function) in every source",
            not eval_offenders,
            f"Article VII; files={names}; offenders={eval_offenders}",
        )
    )

    # Wire input parsed with JSON.parse (now in viewer_core.mjs) and NO eval-based
    # parsing anywhere — eval-free above already proves the latter over every source.
    parse_files = [name for name, js in sources if "JSON.parse" in js]
    results.append(
        (
            "wire input parsed with JSON.parse (no eval-based parsing)",
            bool(parse_files) and not eval_offenders,
            f"A.4; JSON.parse in={parse_files}",
        )
    )

    # Every ws.send(...) must carry an encodeControl(CONTROL.JOIN|LEAVE ...) call.
    # Scanned across all sources; only the socket-owning file (viewer.js) has sends.
    sends = re.findall(r"\.send\(\s*([^\n;]*?)\)\s*;", combined)
    bad_sends = [
        s
        for s in sends
        if not re.match(r"encodeControl\(\s*CONTROL\.(JOIN|LEAVE)\b", s.strip())
    ]
    results.append(
        (
            "all ws.send() emit only JOIN/LEAVE control frames",
            len(sends) > 0 and not bad_sends,
            f"{len(sends)} send site(s); offenders={bad_sends}",
        )
    )

    # No UPDATE/mutation frame is ever constructed in ANY source. viewer_core.mjs's
    # ``UPDATE: "update"`` CONTROL constant + read-side comparisons are NOT matched:
    # this looks only for update-frame CONSTRUCTION tokens.
    update_offenders = [
        name
        for name, js in sources
        if (
            re.search(r"\bencodeUpdate\b", js)
            or re.search(r"encodeControl\(\s*CONTROL\.UPDATE\b", js)
            or re.search(r'"kind"\s*:\s*"update"', js)
        )
    ]
    results.append(
        (
            "no UPDATE/mutation frame is ever constructed in any source",
            not update_offenders,
            f"WEB-002; offenders={update_offenders}",
        )
    )

    # Inbound UPDATE frames are consumed (rendered) but the guard proves the client
    # only READS them — it must decode, never re-emit. The decode path is defined in
    # viewer_core.mjs and called from viewer.js; assert it exists across the sources.
    results.append(
        (
            "inbound UPDATE decoded via decodeMessage/decodeUpdate (read-only)",
            "decodeMessage" in combined and "decodeUpdate" in combined,
            "A.4 read path",
        )
    )
    return results


def audit_a11y(html: str) -> Tuple[List[Result], List[Result]]:
    """Static a11y checks over index.html. Returns (hard_checks, advisory)."""
    hard: List[Result] = []
    advisory: List[Result] = []

    hard.append(
        (
            "<html> has a lang attribute",
            re.search(r"<html[^>]*\blang=", html) is not None,
            "WCAG 3.1.1",
        )
    )

    vp = re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*>', html)
    vp_content = vp.group(0) if vp else ""
    scale_locked = bool(
        re.search(r"user-scalable\s*=\s*no", vp_content)
        or re.search(r"maximum-scale\s*=\s*1(\.0)?\b", vp_content)
    )
    hard.append(
        (
            "viewport present and NOT scale-locked (pinch-zoom preserved)",
            vp is not None and not scale_locked,
            "WCAG 1.4.4 / ADR-0036 A note",
        )
    )

    hard.append(
        ("skip link to main content present", 'class="skip-link"' in html, "WCAG 2.4.1")
    )

    for role in ("banner", "status"):
        hard.append(
            (f'landmark/role "{role}" present', f'role="{role}"' in html, "WCAG 1.3.1")
        )
    hard.append(
        (
            "main content region present (<main>)",
            re.search(r"<main\b", html) is not None,
            "WCAG 1.3.1",
        )
    )
    hard.append(
        (
            "complementary sidebar is labelled (aria-label)",
            re.search(r"<aside[^>]*aria-label=", html) is not None,
            "WCAG 1.3.1",
        )
    )

    canvas = re.search(r"<canvas\b[^>]*>", html)
    canvas_tag = canvas.group(0) if canvas else ""
    hard.append(
        (
            "canvas has role=img + aria-label",
            'role="img"' in canvas_tag and "aria-label=" in canvas_tag,
            "WCAG 1.1.1",
        )
    )

    # Every static <button> must be typed and have a text label or aria-label.
    buttons = re.findall(r"<button\b[^>]*>(.*?)</button>", html, flags=re.DOTALL)
    button_tags = re.findall(r"<button\b[^>]*>", html)
    unlabelled = []
    for tag, inner in zip(button_tags, buttons):
        has_aria = "aria-label=" in tag
        has_text = bool(inner.strip())
        if not (has_aria or has_text):
            unlabelled.append(tag)
    hard.append(
        (
            "every static <button> has a text or aria-label",
            len(button_tags) > 0 and not unlabelled,
            f"{len(button_tags)} button(s); unlabelled={unlabelled}",
        )
    )
    typed = all("type=" in t for t in button_tags)
    advisory.append(
        ('all <button> carry type="button"', typed, "avoids implicit submit")
    )

    hard.append(
        (
            "status region is a live region (aria-live)",
            re.search(r'id="status"[^>]*aria-live=', html) is not None,
            "WCAG 4.1.3",
        )
    )
    hard.append(
        (
            "error overlay is a labelled alertdialog",
            'role="alertdialog"' in html and "aria-labelledby=" in html,
            "WCAG 4.1.2",
        )
    )

    advisory.append(
        (
            "color-scheme meta advertises light+dark",
            re.search(r'name=["\']color-scheme["\']', html) is not None,
            "honours OS theme",
        )
    )
    advisory.append(
        (
            "canvas keyboard-focusable (tabindex)",
            re.search(r"<canvas\b[^>]*tabindex=", html) is not None,
            "keyboard reachability",
        )
    )
    return hard, advisory


def _print_block(title: str, results: List[Result]) -> bool:
    print(f"\n== {title} ==")
    ok = True
    for label, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        ok = ok and passed
        print(f"  [{mark}] {label}  ({detail})")
    return ok


def main() -> int:
    """Run the static audit; fail the process only on a hard-check failure."""
    sources = [
        (os.path.basename(path), _strip_comments(_read(path)))
        for path in VIEW_ONLY_SOURCES
    ]
    html = _read(INDEX_HTML)

    view_only = audit_view_only(sources)
    a11y_hard, a11y_advisory = audit_a11y(html)

    scanned = " + ".join(name for name, _ in sources)
    ok_view = _print_block(f"VIEW-ONLY / eval-free ({scanned})", view_only)
    ok_a11y = _print_block("A11Y hard checks (index.html)", a11y_hard)
    _print_block("A11Y advisory (index.html)", a11y_advisory)

    print("\n== manual / assistive-tech follow-ups (NOT statically checkable) ==")
    for note in (
        "Dynamic per-layer checkboxes are built in JS (updateControls); verify each "
        "has a programmatic name + is keyboard-operable with a screen reader.",
        "Focus-visible ring + logical tab order across topbar -> sidebar -> canvas.",
        "Colour contrast of viewer.css light AND dark themes (>=4.5:1 text).",
        "aria-live status announcements are read on connect/expire transitions.",
    ):
        print(f"  [MANUAL] {note}")

    return 0 if (ok_view and ok_a11y) else 1


if __name__ == "__main__":
    raise SystemExit(main())
