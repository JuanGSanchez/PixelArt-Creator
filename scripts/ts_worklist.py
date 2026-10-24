#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Export translation worklists from a Qt catalogue and import them back.

Standalone script, stdlib only, maintained by the localisation owner. It moves
text between a ``.ts`` catalogue and a JSON worklist; it never writes a
translation itself. The catalogue reader and the per-entry rules are the ones
of the sibling ``check_catalogues.py``, loaded from this script's folder, so
there is one parser and one rule set.

``ts_worklist.py export --catalogue TS --batch NAME --out-dir DIR``
    Write ``NAME-i<k>.json`` holding the catalogue's unfinished messages
    (mode ``new``, instance 1 unless ``--instance`` says otherwise).

``ts_worklist.py export --catalogue TS --batch NAME --out-dir DIR --keys FILE``
    Write a ``rework`` worklist holding exactly the finished messages named in
    FILE, with their current translations filled in. FILE is a JSON list of
    ``{"context", "source"[, "disambiguation"]}`` objects, an object with an
    ``entries`` list, or a ``check_catalogues.py --json`` report (its findings
    that name a message). A key that is not a finished live message is
    refused, naming it. The instance defaults to the next free number (2 or
    more) for the batch.

``ts_worklist.py import WORKLIST --catalogue TS [--partial]``
    Put the worklist's translations into the catalogue. Staleness is judged
    per entry: an entry whose key is not a live message of the catalogue, or
    that fails the catalogue lint, is refused and named. By default any refusal
    exits 1 and writes nothing. With ``--partial`` every other entry is
    imported and the refused ones are written to ``<worklist>.stale.json``.
    A mismatch of the recorded source digest is printed, never a refusal.

The catalogue is patched in place at text level, so every message the import
does not change keeps its bytes. An entry whose translation already equals the
catalogue's leaves its message untouched. All file I/O is binary.

Exit codes: 0 done; 1 refusal, or nothing examined; 2 usage or read error.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_ERROR = 2

SCHEMA = 1
MODE_NEW = "new"
MODE_REWORK = "rework"

ACCESS_KEY_RULE = (
    "Write no single `&` and no access-key marker of your own. Keep every `&&` "
    "exactly as the source has it: it is one literal ampersand. The application "
    "places the access key itself, at run time, on the first occurrence of the "
    "English source's marked letter in your text, or appends ` (&X)` when that "
    "letter is absent."
)

BATCH_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
INSTANCE_FILE = re.compile(r"-i([0-9]+)\.json\Z")
ENTRY_LABEL = re.compile(r"entry ([0-9]+)")
MESSAGE_BLOCK = re.compile(r"<message\b[^>]*>.*?</message>", re.DOTALL)
TRANSLATION_SPAN = re.compile(
    r"<translation(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</translation>)", re.DOTALL
)
TYPE_ATTRIBUTE = re.compile(r'\s+type="[^"]*"')

# Findings that mean "the entry no longer describes a live message".
STALE_CHECKS = ("unknown-key", "comment-mismatch", "numerus-flag")


class WorklistError(Exception):
    """Raised when an input cannot be read or an operation cannot be done."""


def _load_sibling(name: str):
    """Load a Python file of this script's folder by path."""
    if name in sys.modules:
        return sys.modules[name]
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None or not os.path.isfile(path):
        raise WorklistError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def _lint():
    """Return the sibling catalogue lint module."""
    return _load_sibling("check_catalogues")


def _read_bytes(path: str) -> bytes:
    """Read a file in binary."""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise WorklistError(f"{path}: {exc}") from exc


def _read_json(path: str):
    """Read a UTF-8 JSON file in binary."""
    try:
        return json.loads(_read_bytes(path).decode("utf-8"))
    except ValueError as exc:
        raise WorklistError(f"{path}: {exc}") from exc


def _write_bytes(path: str, data: bytes) -> None:
    """Write a file in binary, replacing it atomically."""
    temporary = path + ".tmp"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    except OSError as exc:
        raise WorklistError(f"{path}: {exc}") from exc


def _json_bytes(document) -> bytes:
    """Serialise a JSON document as UTF-8 with LF line ends."""
    text = json.dumps(document, ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    """Return the hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def _sibling_source(catalogue_path: str) -> str:
    """Return the path of the source-language catalogue beside a catalogue."""
    folder = os.path.dirname(os.path.abspath(catalogue_path))
    return os.path.join(folder, "pixelart_en.ts")


def _display(text, width: int = 60) -> str:
    """Shorten a string for one-line display."""
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 3] + "..."


def _required_forms(message, plural_forms) -> int:
    """Return how many translation forms a message needs."""
    if not message.numerus:
        return 1
    if plural_forms is None:
        raise WorklistError(
            f"[{message.context}] {_display(message.source)}: the plural form "
            f"count of the catalogue language is unknown"
        )
    return plural_forms


def _make_entry(message, plural_forms, forms) -> dict:
    """Build one worklist entry for a catalogue message."""
    return {
        "context": message.context,
        "source": message.source,
        "disambiguation": message.disambiguation or None,
        "comment": message.extra_comment or None,
        "numerus": message.numerus,
        "forms_required": _required_forms(message, plural_forms),
        "translation": list(forms),
        "note": "",
    }


def _read_keys(path: str) -> list:
    """Return the ``(context, source, disambiguation-or-None)`` keys of a file."""
    data = _read_json(path)
    items = data
    if isinstance(data, dict):
        if isinstance(data.get("entries"), list):
            items = data["entries"]
        elif isinstance(data.get("catalogues"), list) or isinstance(
            data.get("record"), dict
        ):
            records = data.get("catalogues") or [data["record"]]
            items = [
                finding
                for record in records
                for finding in record.get("findings", [])
                if finding.get("context") is not None
            ]
        else:
            raise WorklistError(f"{path}: no key list found")
    if not isinstance(items, list):
        raise WorklistError(f"{path}: no key list found")
    keys: dict = {}
    for number, item in enumerate(items, start=1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("context"), str)
            or not isinstance(item.get("source"), str)
        ):
            raise WorklistError(
                f"{path}: item {number} has no string 'context' and 'source'"
            )
        disambiguation = item.get("disambiguation", None)
        if "disambiguation" in item and disambiguation is None:
            disambiguation = ""
        keys[(item["context"], item["source"], disambiguation)] = None
    return list(keys)


def _next_instance(out_dir: str, batch: str) -> int:
    """Return the next free instance number (2 or more) for a batch."""
    highest = 1
    if os.path.isdir(out_dir):
        for name in os.listdir(out_dir):
            if not name.startswith(batch + "-i"):
                continue
            found = INSTANCE_FILE.search(name[len(batch) :])
            if found:
                highest = max(highest, int(found.group(1)))
    return highest + 1


def build_export(args, lint) -> tuple:
    """Return ``(path, document, refused_keys)`` for an export."""
    if not BATCH_NAME.match(args.batch):
        raise WorklistError(f"invalid batch name {args.batch!r}")
    catalogue = lint.load_catalogue(args.catalogue)
    if catalogue.identity:
        raise WorklistError(
            f"{args.catalogue}: translates into its own source language "
            f"{catalogue.language!r}; there is nothing to export"
        )
    source_path = args.source or _sibling_source(args.catalogue)
    if not os.path.isfile(source_path):
        raise WorklistError(f"source catalogue {source_path} not found; pass --source")
    digest = _sha256(_read_bytes(source_path))
    plural_forms = lint.expected_forms(catalogue.language)
    live = catalogue.live_messages()
    refused: list = []
    entries: list = []
    if args.keys:
        mode = MODE_REWORK
        finished = [m for m in live if m.kind != "unfinished"]
        chosen: dict = {}
        for context, source, disambiguation in _read_keys(args.keys):
            matches = [
                m
                for m in finished
                if m.context == context
                and m.source == source
                and (disambiguation is None or m.disambiguation == disambiguation)
            ]
            if not matches:
                refused.append((context, source, disambiguation))
            for message in matches:
                chosen[message.key] = message
        entries = [_make_entry(m, plural_forms, m.forms) for m in chosen.values()]
    else:
        mode = MODE_NEW
        for message in live:
            if message.kind == "unfinished":
                forms = [""] * _required_forms(message, plural_forms)
                entries.append(_make_entry(message, plural_forms, forms))
    instance = args.instance
    if instance is None:
        instance = _next_instance(args.out_dir, args.batch) if args.keys else 1
    document = {
        "schema": SCHEMA,
        "language": catalogue.language,
        "batch": args.batch,
        "instance": instance,
        "mode": mode,
        "source_catalogue": os.path.basename(args.catalogue),
        "source_sha256": digest,
        "rules": [ACCESS_KEY_RULE],
        "entries": entries,
    }
    path = os.path.join(args.out_dir, f"{args.batch}-i{instance}.json")
    return path, document, refused


def _run_export(args) -> int:
    """Export a worklist."""
    lint = _lint()
    path, document, refused = build_export(args, lint)
    result = {"mode": "export", "path": path, "examined": len(document["entries"])}
    if refused:
        for context, source, _disambiguation in refused:
            print(
                f"refused key: [{context}] {_display(source)}: "
                f"not a finished live message",
                file=sys.stderr,
            )
        print(f"{len(refused)} key(s) refused; nothing written")
        return EXIT_REFUSED
    if not document["entries"]:
        print("nothing examined: no entries to export; nothing written")
        return EXIT_REFUSED
    if os.path.exists(path):
        raise WorklistError(f"{path} exists already; choose --instance or --out-dir")
    os.makedirs(args.out_dir, exist_ok=True)
    _write_bytes(path, _json_bytes(document))
    result.update(
        language=document["language"],
        worklist_mode=document["mode"],
        instance=document["instance"],
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"wrote {path}: {document['mode']} instance {document['instance']}, "
            f"{result['examined']} entr(ies) examined"
        )
    return EXIT_OK


def classify_entries(worklist: dict, catalogue, lint) -> dict:
    """Split a worklist's entries into carried and refused ones.

    Returns a dict with ``fatal`` (file-level findings), ``refused`` (a list of
    ``(number, entry, findings)``) and ``carried`` (a list of
    ``(number, entry, message)``).
    """
    entries = worklist.get("entries")
    if isinstance(entries, list) and not all(isinstance(e, dict) for e in entries):
        raise WorklistError("the worklist has an entry that is not an object")
    record = lint.lint_worklist(worklist, catalogue)
    fatal: list = []
    by_entry: dict = {}
    for finding in record["findings"]:
        found = ENTRY_LABEL.match(finding["detail"])
        if found:
            by_entry.setdefault(int(found.group(1)), []).append(finding)
        elif finding["check"] != "nothing-examined":
            fatal.append(finding)
    index = {m.key: m for m in catalogue.live_messages()}
    carried: list = []
    refused: list = []
    for number, entry in enumerate(entries or [], start=1):
        if number in by_entry:
            refused.append((number, entry, by_entry[number]))
            continue
        key = (
            str(entry.get("context") or ""),
            str(entry.get("source") or ""),
            entry.get("disambiguation") or "",
        )
        carried.append((number, entry, index[key]))
    return {
        "examined": record["examined"],
        "fatal": fatal,
        "refused": refused,
        "carried": carried,
    }


def _escape(text: str) -> str:
    """Escape text the way the Qt tools write it."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_translation(
    forms, numerus: bool, attributes: str, indent: str, newline: str
) -> str:
    """Return the ``<translation>`` element for finished forms."""
    attributes = TYPE_ATTRIBUTE.sub("", attributes)
    if not numerus:
        return f"<translation{attributes}>{_escape(forms[0])}</translation>"
    inner = newline.join(
        f"{indent}    <numerusform>{_escape(form)}</numerusform>" for form in forms
    )
    return f"<translation{attributes}>{newline}{inner}{newline}{indent}</translation>"


def _patch_block(block: str, forms, numerus: bool) -> str:
    """Return a message block with its translation replaced by finished forms."""
    found = TRANSLATION_SPAN.search(block)
    if found is None:
        raise WorklistError("a message has no <translation> element")
    line_start = block.rfind("\n", 0, found.start()) + 1
    indent = block[line_start : found.start()]
    if indent.strip():
        indent = ""
    newline = "\r\n" if "\r\n" in block else "\n"
    rendered = render_translation(
        forms, numerus, found.group("attrs") or "", indent, newline
    )
    return block[: found.start()] + rendered + block[found.end() :]


def patch_catalogue(data: bytes, catalogue, updates: dict) -> bytes:
    """Return the catalogue bytes with the updated messages patched in.

    ``updates`` maps a message's position in ``catalogue.messages`` to its new
    finished forms. Every byte outside the patched translations is preserved.
    """
    text = data.decode("utf-8")
    blocks = list(MESSAGE_BLOCK.finditer(text))
    if len(blocks) != len(catalogue.messages):
        raise WorklistError(
            f"found {len(blocks)} message blocks, the parser read "
            f"{len(catalogue.messages)}"
        )
    pieces: list = []
    last = 0
    for position, (block, message) in enumerate(zip(blocks, catalogue.messages)):
        source = ET.fromstring(block.group(0)).findtext("source") or ""
        if source != message.source:
            raise WorklistError(
                f"message block {position + 1} does not match the parsed catalogue"
            )
        if position not in updates:
            continue
        pieces.append(text[last : block.start()])
        pieces.append(_patch_block(block.group(0), updates[position], message.numerus))
        last = block.end()
    pieces.append(text[last:])
    return "".join(pieces).encode("utf-8")


def _verify_patched(path: str, before, updates: dict, lint) -> None:
    """Check that only the intended messages changed in the patched file."""
    after = lint.load_catalogue(path)
    if len(after.messages) != len(before.messages):
        raise WorklistError("the patched catalogue has a different message count")
    for position, (old, new) in enumerate(zip(before.messages, after.messages)):
        if position in updates:
            if new.forms != tuple(updates[position]) or new.kind != "":
                raise WorklistError(
                    f"[{old.context}] {_display(old.source)}: patched text differs "
                    f"from the worklist"
                )
        elif new != old:
            raise WorklistError(
                f"[{old.context}] {_display(old.source)}: an untouched message "
                f"changed"
            )


def _entry_label(entry: dict) -> str:
    """Return the display label of a worklist entry."""
    return f"[{entry.get('context')}] {_display(entry.get('source'))}"


def _refusal_record(number: int, entry: dict, findings: list) -> dict:
    """Return the sidecar form of a refused entry."""
    stale = any(f["check"] in STALE_CHECKS for f in findings)
    return dict(
        entry,
        refused={
            "entry": number,
            "kind": "stale" if stale else "lint",
            "findings": [
                {"check": f["check"], "detail": f["detail"]} for f in findings
            ],
        },
    )


def _run_import(args) -> int:
    """Import a worklist into its catalogue."""
    lint = _lint()
    worklist = _read_json(args.worklist)
    if not isinstance(worklist, dict):
        raise WorklistError(f"{args.worklist}: not a JSON object")
    catalogue = lint.load_catalogue(args.catalogue)
    plan = classify_entries(worklist, catalogue, lint)
    examined = plan["examined"]
    refused = plan["refused"]
    carried = plan["carried"]
    lines: list = []
    exit_code = EXIT_OK
    if examined == 0:
        print("nothing examined: the worklist holds no entries")
        return EXIT_REFUSED
    if plan["fatal"]:
        for finding in plan["fatal"]:
            print(f"refused worklist: {finding['check']}: {finding['detail']}")
        print(f"examined {examined} entr(ies); nothing imported")
        return EXIT_REFUSED
    source_path = args.source or _sibling_source(args.catalogue)
    recorded = worklist.get("source_sha256")
    if os.path.isfile(source_path) and recorded:
        current = _sha256(_read_bytes(source_path))
        if current != recorded:
            lines.append(
                f"note: source_sha256 differs (worklist {recorded[:12]}, "
                f"{os.path.basename(source_path)} {current[:12]}); "
                f"{len(carried)} of {examined} entr(ies) are still live. "
                f"This is not a ground for refusal."
            )
    elif recorded:
        lines.append(f"note: {source_path} not found; source_sha256 not compared")
    for number, entry, findings in refused:
        names = ", ".join(sorted({f["check"] for f in findings}))
        lines.append(f"refused entry {number} {_entry_label(entry)}: {names}")
        lines.extend(f"    {f['detail']}" for f in findings)
    updates = {}
    positions = {id(m): i for i, m in enumerate(catalogue.messages)}
    unchanged = 0
    for _number, entry, message in carried:
        forms = tuple(entry["translation"])
        if forms == message.forms and message.kind == "":
            unchanged += 1
        else:
            updates[positions[id(message)]] = forms
    sidecar = None
    applied = not (refused and not args.partial)
    if not applied:
        exit_code = EXIT_REFUSED
        lines.append(
            f"{len(refused)} entr(ies) refused; nothing imported "
            f"(use --partial to import the rest)"
        )
    else:
        if updates:
            data = _read_bytes(args.catalogue)
            patched = patch_catalogue(data, catalogue, updates)
            temporary = args.catalogue + ".verify"
            _write_bytes(temporary, patched)
            try:
                _verify_patched(temporary, catalogue, updates, lint)
            except Exception:
                os.remove(temporary)
                raise
            os.replace(temporary, args.catalogue)
        if refused:
            sidecar = args.worklist + ".stale.json"
            document = {
                key: worklist.get(key)
                for key in (
                    "schema",
                    "language",
                    "batch",
                    "instance",
                    "mode",
                    "source_catalogue",
                    "source_sha256",
                    "rules",
                )
            }
            document["entries"] = [_refusal_record(n, e, f) for n, e, f in refused]
            _write_bytes(sidecar, _json_bytes(document))
        if not carried:
            exit_code = EXIT_REFUSED
    summary = {
        "mode": "import",
        "examined": examined,
        "imported": len(updates) if applied else 0,
        "unchanged": unchanged if applied else 0,
        "refused": len(refused),
        "stale_sidecar": sidecar,
        "exit": exit_code,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return exit_code
    for line in lines:
        print(line)
    print(
        f"examined {examined} entr(ies): imported "
        f"{summary['imported']}, unchanged {summary['unchanged']}, "
        f"refused {len(refused)}"
    )
    if sidecar:
        print(f"refused entries written to {sidecar}")
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    export = modes.add_parser("export", help="write a worklist from a catalogue")
    export.add_argument("--catalogue", required=True, help="the target .ts file")
    export.add_argument("--batch", required=True, help="the batch name")
    export.add_argument("--out-dir", required=True, help="folder for the worklist")
    export.add_argument("--source", help="the English .ts (default: beside TS)")
    export.add_argument("--keys", help="rework: JSON file naming finished messages")
    export.add_argument("--instance", type=int, help="instance number")
    export.add_argument("--json", action="store_true", help="print JSON")
    export.set_defaults(run=_run_export)
    imported = modes.add_parser("import", help="import a worklist into a catalogue")
    imported.add_argument("worklist", metavar="WORKLIST")
    imported.add_argument("--catalogue", required=True, help="the target .ts file")
    imported.add_argument("--source", help="the English .ts (default: beside TS)")
    imported.add_argument(
        "--partial", action="store_true", help="import the entries that are not refused"
    )
    imported.add_argument("--json", action="store_true", help="print JSON")
    imported.set_defaults(run=_run_import)
    return parser


def main(argv=None) -> int:
    """Run the requested mode and return the process exit code."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        catalogue_error = _lint().CatalogueError
        return args.run(args)
    except (WorklistError, catalogue_error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
