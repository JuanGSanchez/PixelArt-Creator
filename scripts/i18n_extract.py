#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: i18n_extract  (standalone script — PixelArt Creator)
# =============================================================================
# PURPOSE: Run ``pyside6-lupdate`` over the application source without ever
#   losing a message or a translation (REQ-L10N-BUILD-007), and prove that the
#   English source has not moved. Two modes:
#     * extraction (default): back up every catalogue, run lupdate, compare the
#       live message count and the non-empty translation count of each
#       catalogue with the backup, and on any drop that no recorded removal
#       explains, restore the backup byte for byte and exit 1;
#     * ``--check``: extract into scratch copies only, compare the live message
#       keys of each scratch catalogue with the tracked one, exit 0 when they
#       are identical and 1 listing every added or removed key. A tracked
#       catalogue is never written in this mode.
# FLAVOUR: standalone
# LOCATION: scripts/i18n_extract.py
# INVOKED BY: the localisation role, after every change to translatable
#   strings; and, in ``--check`` mode, by every change to a ``ui/`` or
#   ``logic/`` module made once the English source is frozen.
# RUNTIME: Python 3.12+ (CPython; stdlib only) and ``pyside6-lupdate`` on PATH.
# ENTRYPOINT: python scripts/i18n_extract.py [--check] [--json] [--root DIR]
#   [--source DIR] [--catalogues DIR] [--locales a,b] [--removals FILE]
#   [--backup-dir DIR] [--keep-backup] [--lupdate EXE]
# INPUTS:
#   --root        product root (default: the parent of this script's folder).
#   --source      source folder scanned by lupdate, relative to the root
#                 (default pixelart_creator).
#   --catalogues  folder holding pixelart_<locale>.ts, relative to the root
#                 (default pixelart_creator/i18n).
#   --locales     comma-separated locales; default: every pixelart_*.ts found.
#   --removals    JSON file {"removals": [{"context", "source", "comment",
#                 "reason", "catalogue"}]}; a message may leave a catalogue
#                 only when it is listed here with a non-empty reason.
# OUTPUTS: a per-catalogue table on stdout (stderr with --json, which prints
#   one JSON document on stdout instead). Exit code per EXIT CODES.
# EXIT CODES: 0 nothing lost / keys identical; 1 an unrecorded drop (the
#   catalogues are restored) or changed keys in --check, or nothing was
#   examined; 2 the tool or an input is unavailable, or lupdate failed.
# DETERMINISM NOTE: deterministic given the same source and lupdate version.
#   Keys are (context, source, disambiguation, plural flag); the location
#   lines of a message are not part of its key.
# =============================================================================
"""Count-guarded ``pyside6-lupdate`` runner and English-source freeze check."""

import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

LUPDATE = "pyside6-lupdate"
DEFAULT_SOURCE = "pixelart_creator"
DEFAULT_CATALOGUES = "pixelart_creator/i18n"
CATALOGUE_GLOB = "pixelart_*.ts"
DEAD_TYPES = frozenset({"vanished", "obsolete"})
SHOWN_KEYS = 12

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

Key = tuple[str, str, str, bool]
Key3 = tuple[str, str, str]


class ExtractError(Exception):
    """A tool, an input or a restore failed; the run cannot be trusted."""


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """The parsed state of one catalogue."""

    name: str
    digest: str
    live: dict[Key, str]
    vanished: int

    @property
    def messages(self) -> int:
        """Live message count."""
        return len(self.live)

    @property
    def translated(self) -> set[Key]:
        """Live keys whose translation is non-empty."""
        return {key for key, text in self.live.items() if text}

    @property
    def translations(self) -> int:
        """Non-empty translation count among the live messages."""
        return len(self.translated)


def parse_catalogue(name: str, raw: bytes) -> Snapshot:
    """Parse ``raw`` (a .ts file's bytes) into a :class:`Snapshot`.

    A message is live unless its translation is typed vanished or obsolete. A
    translation is non-empty when every form (one, or each plural form) holds
    text. Raises :class:`ExtractError` on malformed XML.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ExtractError(f"{name}: not well-formed XML ({exc})") from exc
    live: dict[Key, str] = {}
    vanished = 0
    for context in root.iter("context"):
        context_name = (context.findtext("name") or "").strip()
        for message in context.iter("message"):
            translation = message.find("translation")
            if translation is not None and translation.get("type") in DEAD_TYPES:
                vanished += 1
                continue
            plural = message.get("numerus") == "yes"
            key = (
                context_name,
                message.findtext("source") or "",
                message.findtext("comment") or "",
                plural,
            )
            live[key] = _translation_text(translation, plural)
    return Snapshot(name, hashlib.sha256(raw).hexdigest(), live, vanished)


def _translation_text(translation: "ET.Element | None", plural: bool) -> str:
    """Return the translation text, or ``""`` when any form is empty."""
    if translation is None:
        return ""
    if not plural:
        return "".join(translation.itertext()).strip()
    forms = ["".join(f.itertext()).strip() for f in translation.iter("numerusform")]
    if not forms or not all(forms):
        return ""
    return "\u0001".join(forms)


def build_lupdate_argv(lupdate: str, source: str, catalogues: list[str]) -> list[str]:
    """Return the lupdate argument vector, flag first, and verify it."""
    argv = [lupdate, "-extensions", "py", source, "-ts", *catalogues]
    verify_argv(argv, source)
    return argv


def verify_argv(argv: list[str], source: str) -> None:
    """Raise :class:`ExtractError` unless ``-extensions py`` precedes the source.

    Placed after the source path, or left out, lupdate ignores the flag, scans
    no Python file and empties every catalogue while exiting 0.
    """
    try:
        flag = argv.index("-extensions")
        where = argv.index(source)
    except ValueError as exc:
        raise ExtractError(f"lupdate argv lacks -extensions or the source: {exc}")
    if argv[flag + 1 : flag + 2] != ["py"] or flag >= where:
        raise ExtractError(
            "lupdate argv must carry '-extensions py' BEFORE the source path: "
            + " ".join(argv)
        )
    if "-ts" not in argv or argv.index("-ts") < where:
        raise ExtractError("lupdate argv must list '-ts' after the source path")


def run_lupdate(argv: list[str], root: pathlib.Path) -> str:
    """Run lupdate in ``root`` and return its combined output.

    Raises :class:`ExtractError` on a non-zero exit, quoting the output.
    """
    try:
        done = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ExtractError(f"could not run {argv[0]}: {exc}") from exc
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        raise ExtractError(f"{argv[0]} exited {done.returncode}:\n{output}")
    return output


def find_lupdate(explicit: str | None) -> str:
    """Resolve the lupdate executable or raise :class:`ExtractError`."""
    found = shutil.which(explicit or LUPDATE)
    if found is None:
        raise ExtractError(f"could not run - {explicit or LUPDATE} not on PATH")
    return found


def discover(root: pathlib.Path, folder: str, locales: list[str] | None):
    """Return the catalogue paths to examine, sorted by name."""
    base = root / folder
    if locales:
        paths = [base / f"pixelart_{loc}.ts" for loc in locales]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise ExtractError("catalogue not found: " + ", ".join(missing))
        return sorted(paths)
    return sorted(base.glob(CATALOGUE_GLOB))


def load_removals(path: str | None) -> dict[tuple[str, Key3], str]:
    """Read the recorded removals as {(catalogue or '*', key3): reason}."""
    if not path:
        return {}
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        entries = data["removals"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ExtractError(f"cannot read removals file {path}: {exc}") from exc
    recorded = {}
    for entry in entries:
        reason = str(entry.get("reason", "")).strip()
        if not reason:
            raise ExtractError(f"removal without a reason: {entry}")
        key3 = (entry["context"], entry["source"], entry.get("comment", ""))
        recorded[(entry.get("catalogue", "*"), key3)] = reason
    return recorded


def _is_recorded(removals, catalogue: str, key: Key) -> bool:
    """Return whether ``key`` may leave ``catalogue`` per the recorded removals."""
    stem = catalogue.removesuffix(".ts")
    key3 = key[:3]
    return any((c, key3) in removals for c in ("*", catalogue, stem))


@dataclasses.dataclass
class Comparison:
    """The before/after difference of one catalogue."""

    name: str
    before: Snapshot
    after: Snapshot
    removed: list[Key]
    added: list[Key]
    unrecorded_removed: list[Key]
    lost_translations: list[Key]
    altered: list[Key]

    @property
    def ok(self) -> bool:
        """Whether nothing was lost without a record."""
        return not (self.unrecorded_removed or self.lost_translations or self.altered)


def compare(before: Snapshot, after: Snapshot, removals) -> Comparison:
    """Compare two snapshots of one catalogue under the recorded removals."""
    removed = sorted(set(before.live) - set(after.live))
    added = sorted(set(after.live) - set(before.live))
    unrecorded = [k for k in removed if not _is_recorded(removals, before.name, k)]
    survivors = set(before.live) & set(after.live)
    lost, altered = [], []
    for key in sorted(survivors):
        old, new = before.live[key], after.live[key]
        if old and not new:
            lost.append(key)
        elif old and new and old != new:
            altered.append(key)
    return Comparison(
        before.name, before, after, removed, added, unrecorded, lost, altered
    )


def _show(key: Key) -> str:
    """Return one printable line for a key."""
    context, source, comment, plural = key
    text = source if len(source) <= 90 else source[:87] + "..."
    extra = f" [{comment}]" if comment else ""
    return f"{context} :: {text!r}{extra}{' (plural)' if plural else ''}"


def _lines(title: str, keys: list[Key]) -> list[str]:
    """Return the report lines for a key list, capped at SHOWN_KEYS."""
    if not keys:
        return []
    out = [f"    {title} ({len(keys)}):"]
    out += [f"      - {_show(k)}" for k in keys[:SHOWN_KEYS]]
    if len(keys) > SHOWN_KEYS:
        out.append(f"      ... and {len(keys) - SHOWN_KEYS} more")
    return out


def snapshot_all(paths: list[pathlib.Path]) -> tuple[dict[str, bytes], list[Snapshot]]:
    """Read and parse every catalogue; return the raw bytes and the snapshots."""
    raws = {p.name: p.read_bytes() for p in paths}
    return raws, [parse_catalogue(n, r) for n, r in raws.items()]


def _restore(paths: list[pathlib.Path], raws: dict[str, bytes]) -> None:
    """Write the backed-up bytes back and verify them; raise on a mismatch."""
    for path in paths:
        path.write_bytes(raws[path.name])
        if path.read_bytes() != raws[path.name]:
            raise ExtractError(f"RESTORE FAILED for {path}: bytes differ")


def extract(args, root, lupdate, paths, removals) -> tuple[int, dict, list[Comparison]]:
    """Run the count-guarded extraction; return (exit code, report dict)."""
    raws, before = snapshot_all(paths)
    backup = pathlib.Path(
        args.backup_dir or tempfile.mkdtemp(prefix="i18n_extract_backup_")
    )
    backup.mkdir(parents=True, exist_ok=True)
    for name, raw in raws.items():
        (backup / name).write_bytes(raw)
    argv = build_lupdate_argv(
        lupdate, args.source, [os.path.relpath(p, root) for p in paths]
    )
    print("backup  :", backup, file=sys.stderr if args.json else sys.stdout)
    print("command :", " ".join(argv), file=sys.stderr if args.json else sys.stdout)
    try:
        output = run_lupdate(argv, root)
        _, after = snapshot_all(paths)
    except ExtractError:
        _restore(paths, raws)
        raise
    results = [compare(b, a, removals) for b, a in zip(before, after)]
    examined = sum(r.before.messages for r in results)
    ok = examined > 0 and all(r.ok for r in results)
    restored = False
    if not ok:
        _restore(paths, raws)
        restored = True
    elif not args.keep_backup and not args.backup_dir:
        shutil.rmtree(backup, ignore_errors=True)
    report = {
        "mode": "extract",
        "ok": ok,
        "restored_from_backup": restored,
        "backup": str(backup),
        "lupdate_output": output,
        "keys_examined": examined,
        "catalogues": [_as_dict(r) for r in results],
    }
    return (EXIT_OK if ok else EXIT_FINDINGS), report, results


def check(args, root, lupdate, paths) -> tuple[int, dict, list[Comparison]]:
    """Extract into scratch copies and compare live keys; never write tracked."""
    raws, tracked = snapshot_all(paths)
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="i18n_extract_check_"))
    try:
        copies = []
        for path in paths:
            copy = scratch / path.name
            copy.write_bytes(raws[path.name])
            copies.append(copy)
        argv = build_lupdate_argv(lupdate, args.source, [str(c) for c in copies])
        print("command :", " ".join(argv), file=sys.stderr if args.json else sys.stdout)
        output = run_lupdate(argv, root)
        _, extracted = snapshot_all(copies)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    unchanged = all(p.read_bytes() == raws[p.name] for p in paths)
    if not unchanged:
        raise ExtractError("a tracked catalogue changed during --check")
    results = [compare(t, e, {}) for t, e in zip(tracked, extracted)]
    examined = sum(r.before.messages for r in results)
    live_empty = [
        r.name for r in results if not r.before.messages or not r.after.messages
    ]
    identical = all(not r.removed and not r.added for r in results)
    ok = examined > 0 and not live_empty and identical
    report = {
        "mode": "check",
        "ok": ok,
        "tracked_catalogues_unchanged": unchanged,
        "lupdate_output": output,
        "keys_examined": examined,
        "zero_examined": live_empty,
        "catalogues": [_as_dict(r) for r in results],
    }
    return (EXIT_OK if ok else EXIT_FINDINGS), report, results


def _as_dict(r: Comparison) -> dict:
    """Return the JSON-serialisable form of a comparison."""
    keys = lambda items: [list(k) for k in items]  # noqa: E731
    return {
        "catalogue": r.name,
        "messages_before": r.before.messages,
        "messages_after": r.after.messages,
        "translations_before": r.before.translations,
        "translations_after": r.after.translations,
        "vanished_before": r.before.vanished,
        "vanished_after": r.after.vanished,
        "added": keys(r.added),
        "removed": keys(r.removed),
        "unrecorded_removed": keys(r.unrecorded_removed),
        "lost_translations": keys(r.lost_translations),
        "altered_translations": keys(r.altered),
    }


def render(report: dict, results: list[Comparison]) -> list[str]:
    """Return the human-readable report."""
    check_mode = report["mode"] == "check"
    lines = [f"{'catalogue':<20}{'live messages':>20}{'non-empty translations':>28}"]
    for r in results:
        lines.append(
            f"{r.name:<20}{f'{r.before.messages} -> {r.after.messages}':>20}"
            f"{f'{r.before.translations} -> {r.after.translations}':>28}"
        )
        if check_mode:
            lines.append(
                f"    live keys examined: {r.before.messages} tracked, "
                f"{r.after.messages} extracted"
            )
        lines += _lines("added keys" if check_mode else "added", r.added)
        if check_mode:
            lines += _lines("removed keys", r.removed)
        else:
            recorded = [k for k in r.removed if k not in r.unrecorded_removed]
            lines += _lines("removed (recorded)", recorded)
            lines += _lines("REMOVED WITHOUT A RECORD", r.unrecorded_removed)
        lines += _lines("TRANSLATION EMPTIED", r.lost_translations)
        lines += _lines("TRANSLATION ALTERED", r.altered)
    lines.append(
        f"examined: {len(results)} catalogue(s), {report['keys_examined']} live key(s)"
    )
    if check_mode:
        lines.append(
            "tracked catalogues byte-identical after the run: "
            f"{report['tracked_catalogues_unchanged']}"
        )
        for name in report["zero_examined"]:
            lines.append(f"FAILED: {name} had zero live keys to compare")
    elif report["restored_from_backup"]:
        lines.append("RESTORED every catalogue byte-identical from the backup")
    lines.append(f"verdict: {'OK' if report['ok'] else 'FAILED'}")
    return lines


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="i18n_extract.py",
        description="Count-guarded pyside6-lupdate and English-source freeze check.",
    )
    parser.add_argument("--check", action="store_true", help="scratch run, read-only")
    parser.add_argument("--json", action="store_true", help="JSON report on stdout")
    parser.add_argument(
        "--root", default=str(pathlib.Path(__file__).resolve().parents[1])
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--catalogues", default=DEFAULT_CATALOGUES)
    parser.add_argument("--locales", default="")
    parser.add_argument("--removals", default="")
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--keep-backup", action="store_true")
    parser.add_argument("--lupdate", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the requested mode and return the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    try:
        lupdate = find_lupdate(args.lupdate or None)
        locales = [x for x in args.locales.split(",") if x] or None
        paths = discover(root, args.catalogues, locales)
        if not paths:
            print("FAILED: no catalogue examined (zero found)", file=sys.stderr)
            return EXIT_FINDINGS
        if not (root / args.source).is_dir():
            raise ExtractError(f"source folder not found: {root / args.source}")
        if args.check:
            code, report, results = check(args, root, lupdate, paths)
        else:
            code, report, results = extract(
                args, root, lupdate, paths, load_removals(args.removals)
            )
    except ExtractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR
    text = "\n".join(render(report, results))
    if args.json:
        print(text, file=sys.stderr)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
