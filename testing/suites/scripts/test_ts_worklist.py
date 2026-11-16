"""Contract tests for ``scripts/ts_worklist.py`` (ADR-0047).

Contract asserted here, taken from the script's own header::

    ts_worklist.py export --catalogue TS --batch NAME --out-dir DIR
                          [--keys FILE] [--instance K] [--source EN.ts] [--json]
    ts_worklist.py import WORKLIST --catalogue TS [--partial] [--source EN.ts]
                          [--json]
    EXIT CODES: 0 done ; 1 refusal, or nothing examined ; 2 usage or read error.

The method is the one of the sibling module for ``check_catalogues.py`` and its
registry, scratch-catalogue writer and broken-copy builder are imported from
there. Every fixture is a scratch catalogue pair (the English source and the
Spanish target, side by side) built under ``tmp_path``; the tracked catalogues
are never read. A regression case drives the script on a clean fixture (exit
0) and a broken one (exit 1, the entry or key named, JSON parsed by field) and
is then required to FAIL against a broken copy of the script with the defended
rule removed. The worklist script loads the catalogue lint beside itself, so a
broken copy always holds both scripts.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from .conftest import SCRIPTS_DIR
from .test_check_catalogues import (
    CHECK,
    WORKLIST,
    Case,
    Edit,
    Msg,
    Mutant,
    Registry,
    Tools,
    edit,
    make_broken,
    mutant,
    put,
    ts_text,
    write_ts,
)

REGISTRY = Registry()

#: The access-key sentence, verbatim; deliberately not read from the script.
ACCESS_KEY_SENTENCE = (
    "Write no single `&` and no access-key marker of your own. Keep every `&&` "
    "exactly as the source has it: it is one literal ampersand. The application "
    "places the access key itself, at run time, on the first occurrence of the "
    "English source's marked letter in your text, or appends ` (&X)` when that "
    "letter is absent."
)


def tsw(old: str, new: str) -> Edit:
    """Build an edit of ``ts_worklist.py``."""
    return edit(old, new, WORKLIST)


# --------------------------------------------------------------------------- #
# The scratch workspace: an English catalogue and its Spanish target.
# --------------------------------------------------------------------------- #
ENGLISH = [
    Msg("Open", "", kind="unfinished"),
    Msg("Close", "", kind="unfinished"),
    Msg("Layer %1 of %2", "", kind="unfinished"),
    Msg("%n frame(s)", ["", ""], kind="unfinished", numerus=True),
    Msg("Save", "", kind="unfinished"),
]

SPANISH = [
    Msg("Open", "Abrir"),
    Msg("Close", "", kind="unfinished"),
    Msg("Layer %1 of %2", "", kind="unfinished", comment="Layer position"),
    Msg("%n frame(s)", ["", ""], kind="unfinished", numerus=True),
    Msg("Save", "Guardar"),
    Msg("Old", "Viejo", kind="vanished"),
]

TRANSLATIONS = {
    "Close": ["Cerrar"],
    "Layer %1 of %2": ["Capa %1 de %2"],
    "%n frame(s)": ["%n fotograma", "%n fotogramas"],
}


def finished(messages: list[Msg], translations: dict) -> list[Msg]:
    """Return ``messages`` with the unfinished ones named in ``translations`` done."""
    done = []
    for message in messages:
        if message.kind == "unfinished" and message.source in translations:
            forms = translations[message.source]
            text = forms if message.numerus else forms[0]
            message = dataclasses.replace(message, kind="", translation=text)
        done.append(message)
    return done


def workspace(
    work: Path, name: str, spanish: list[Msg] | None = None, english=None
) -> Path:
    """Write ``pixelart_en.ts`` and ``pixelart_es.ts`` side by side.

    Returns the path of the Spanish one.
    """
    folder = work / name
    write_ts(folder / "pixelart_en.ts", "en", english or ENGLISH)
    return write_ts(folder / "pixelart_es.ts", "es", spanish or SPANISH)


def clone(catalogue: Path, work: Path, name: str) -> Path:
    """Copy a workspace and return the copy's Spanish catalogue."""
    target = work / name
    shutil.copytree(catalogue.parent, target)
    return target / catalogue.name


def read_json(path: Path):
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_bytes().decode("utf-8"))


def save_json(path: Path, document) -> Path:
    """Write a JSON document the way the script writes its own."""
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def export_new(
    tools: Tools, work: Path, catalogue: Path, batch: str = "screen"
) -> tuple[Path, dict]:
    """Export the unfinished messages; return the worklist's path and content."""
    out = work / "lists"
    args = ["export", "--catalogue", str(catalogue), "--batch", batch]
    args += ["--out-dir", str(out), "--json"]
    run, payload = tools.json(WORKLIST, args, work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    path = Path(payload["path"])
    return path, read_json(path)


def export_keys(
    tools: Tools, work: Path, catalogue: Path, keys: Path, batch: str, *extra: str
):
    """Run ``export --keys`` and return the finished process."""
    args = ["export", "--catalogue", str(catalogue), "--batch", batch]
    args += ["--out-dir", str(work / "lists"), "--keys", str(keys), *extra]
    return tools.run(WORKLIST, args, work)


def rules_of(document: dict) -> list:
    """Return a worklist's top-level ``rules`` list, requiring that it exists."""
    assert "rules" in document, "the worklist has no top-level 'rules' list"
    assert isinstance(document["rules"], list)
    return document["rules"]


def with_translations(document: dict, translations: dict | None = None) -> dict:
    """Return a copy of an exported worklist with its translations filled in."""
    filled = copy.deepcopy(document)
    for item in filled["entries"]:
        item["translation"] = list((translations or TRANSLATIONS)[item["source"]])
    return filled


def import_text(tools: Tools, work: Path, worklist: Path, catalogue: Path, *flags):
    """Run ``import`` in its human-readable form."""
    args = ["import", str(worklist), "--catalogue", str(catalogue), *flags]
    return tools.run(WORKLIST, args, work)


def import_json(tools: Tools, work: Path, worklist: Path, catalogue: Path, *flags):
    """Run ``import --json`` and return ``(run, summary)``."""
    args = ["import", str(worklist), "--catalogue", str(catalogue), *flags, "--json"]
    run, summary = tools.json(WORKLIST, args, work)
    assert summary["mode"] == "import"
    assert summary["exit"] == run.returncode
    return run, summary


def key_file(work: Path, items, name: str = "keys.json") -> Path:
    """Write a keys file."""
    return save_json(work / name, items)


def key(source: str, **extra) -> dict:
    """Return a key object for the ``Panel`` context."""
    return {"context": "Panel", "source": source, **extra}


# --------------------------------------------------------------------------- #
# export: the new-mode worklist.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "finished-messages-are-exported",
        tsw(
            '            if message.kind == "unfinished":\n',
            '            if message.kind != "unfinished":\n',
        ),
    ),
)
def case_export_writes_the_unfinished_messages(tools: Tools, work: Path) -> None:
    """A new worklist holds exactly the unfinished live messages, empty forms."""
    catalogue = workspace(work, "ws")
    out = work / "lists"
    args = ["export", "--catalogue", str(catalogue), "--batch", "screen"]
    args += ["--out-dir", str(out)]
    run, payload = tools.json(WORKLIST, [*args, "--json"], work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    path = out / "screen-i1.json"
    assert payload == {
        "mode": "export",
        "path": str(path),
        "examined": 3,
        "language": "es",
        "worklist_mode": "new",
        "instance": 1,
    }
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    document = json.loads(raw.decode("utf-8"))
    english = catalogue.parent / "pixelart_en.ts"
    assert document["schema"] == 1
    assert (document["language"], document["batch"]) == ("es", "screen")
    assert (document["instance"], document["mode"]) == (1, "new")
    assert document["source_catalogue"] == "pixelart_es.ts"
    assert document["source_sha256"] == hashlib.sha256(english.read_bytes()).hexdigest()
    assert document["entries"] == [
        {
            "context": "Panel",
            "source": "Close",
            "disambiguation": None,
            "comment": None,
            "numerus": False,
            "forms_required": 1,
            "translation": [""],
            "note": "",
        },
        {
            "context": "Panel",
            "source": "Layer %1 of %2",
            "disambiguation": None,
            "comment": "Layer position",
            "numerus": False,
            "forms_required": 1,
            "translation": [""],
            "note": "",
        },
        {
            "context": "Panel",
            "source": "%n frame(s)",
            "disambiguation": None,
            "comment": None,
            "numerus": True,
            "forms_required": 2,
            "translation": ["", ""],
            "note": "",
        },
    ]
    text = tools.run(WORKLIST, [*args[:-2], "--out-dir", str(work / "again")], work)
    assert text.returncode == 0
    assert "new instance 1, 3 entr(ies) examined" in text.stdout


# --------------------------------------------------------------------------- #
# export --keys: the rework worklist.
# --------------------------------------------------------------------------- #
KEYED = [
    Msg("Open", "Abrir", disambiguation="menu"),
    Msg("Open", "Abrir archivo", disambiguation="button"),
    Msg("Save", "Guardar"),
    Msg("Close", "", kind="unfinished"),
    Msg("%n item(s)", ["%n elemento", "%n elementos"], numerus=True),
    Msg("Old", "Viejo", kind="vanished"),
]


@REGISTRY.regression(
    mutant(
        "mode-stays-new",
        tsw("        mode = MODE_REWORK\n", "        mode = MODE_NEW\n"),
    ),
    mutant(
        "disambiguation-is-ignored",
        tsw(
            "                and (disambiguation is None "
            "or m.disambiguation == disambiguation)\n",
            "                and True\n",
        ),
    ),
    mutant(
        "entries-object-is-not-read",
        tsw(
            '        if isinstance(data.get("entries"), list):\n', "        if False:\n"
        ),
    ),
)
def case_export_keys_writes_a_rework_worklist(tools: Tools, work: Path) -> None:
    """``--keys`` writes exactly the named finished messages, forms pre-filled."""
    catalogue = workspace(work, "ws", KEYED)
    keys = key_file(
        work,
        [key("Save"), key("%n item(s)"), key("Open", disambiguation="menu")],
    )
    run = export_keys(tools, work, catalogue, keys, "rework")
    assert run.returncode == 0, (run.stdout, run.stderr)
    path = work / "lists" / "rework-i2.json"
    assert f"wrote {path}: rework instance 2, 3 entr(ies) examined" in run.stdout
    document = read_json(path)
    assert (document["mode"], document["instance"]) == ("rework", 2)
    got = [
        (e["source"], e["disambiguation"], e["numerus"], e["forms_required"])
        for e in document["entries"]
    ]
    assert got == [
        ("Save", None, False, 1),
        ("%n item(s)", None, True, 2),
        ("Open", "menu", False, 1),
    ]
    assert [e["translation"] for e in document["entries"]] == [
        ["Guardar"],
        ["%n elemento", "%n elementos"],
        ["Abrir"],
    ]

    # The same keys as an object with an "entries" list.
    wrapped = key_file(work, {"entries": [key("Save")]}, "wrapped.json")
    run = export_keys(tools, work, catalogue, wrapped, "wrapped")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert [
        e["source"] for e in read_json(work / "lists" / "wrapped-i2.json")["entries"]
    ] == ["Save"]

    # No disambiguation in the key names every message of that text.
    both = key_file(work, [key("Open")], "both.json")
    assert export_keys(tools, work, catalogue, both, "both").returncode == 0
    names = [
        e["disambiguation"]
        for e in read_json(work / "lists" / "both-i2.json")["entries"]
    ]
    assert names == ["menu", "button"]

    # An explicit null names the messages that have none: there is no such one.
    none = key_file(work, [key("Open", disambiguation=None)], "none.json")
    run = export_keys(tools, work, catalogue, none, "none")
    assert run.returncode == 1 and "1 key(s) refused" in run.stdout


@REGISTRY.regression(
    mutant(
        "unfinished-key-is-accepted",
        tsw(
            '        finished = [m for m in live if m.kind != "unfinished"]\n',
            "        finished = live\n",
        ),
    ),
    mutant(
        "vanished-key-is-accepted",
        tsw(
            "    live = catalogue.live_messages()\n    refused: list = []\n",
            "    live = catalogue.messages\n    refused: list = []\n",
        ),
    ),
)
def case_export_keys_refuses_a_key_that_is_not_a_finished_message(
    tools: Tools, work: Path
) -> None:
    """An unfinished, vanished or absent key exits 1 naming it; nothing is written."""
    catalogue = workspace(work, "ws", KEYED)
    keys = key_file(
        work, [key("Save"), key("Close"), key("Old"), key("Nowhere"), key("Open")]
    )
    run = export_keys(tools, work, catalogue, keys, "rework")
    assert run.returncode == 1, (run.stdout, run.stderr)
    for name in ("Close", "Old", "Nowhere"):
        assert f"refused key: [Panel] {name}: not a finished live message" in run.stderr
    assert "refused key: [Panel] Save" not in run.stderr
    assert "3 key(s) refused; nothing written" in run.stdout
    assert not (work / "lists").exists(), "a refused export writes nothing at all"

    only = key_file(work, [key("Save"), key("Open", disambiguation="menu")], "ok.json")
    run = export_keys(tools, work, catalogue, only, "rework")
    assert run.returncode == 0, (run.stdout, run.stderr)


@REGISTRY.regression(
    mutant(
        "findings-without-a-message-are-keys",
        tsw(
            '                if finding.get("context") is not None\n',
            "                if True\n",
        ),
    ),
)
def case_export_keys_reads_a_lint_report(tools: Tools, work: Path) -> None:
    """The ``--json`` report of the catalogue lint is accepted as a keys file."""
    catalogue = workspace(
        work,
        "ws",
        [Msg("Open %1", "Abrir %1"), Msg("Save", "Guardar"), Msg("Close", "Cerrar")],
    )
    # A lint run that has a file-level finding (no message) and two findings on
    # one message, so the report holds an item the reader must skip and a pair
    # it must merge.
    flawed = put(
        work,
        "flawed",
        "es",
        [Msg("Open %1", "&Abrir"), Msg("Save", "Guardar &")],
        language="fr",
    )
    report = tools.run(CHECK, ["lint", str(flawed), "--json"], work)
    assert report.returncode == 1, (report.stdout, report.stderr)
    found = json.loads(report.stdout)["catalogues"][0]["findings"]
    assert {f["check"] for f in found} == {
        "language-attribute",
        "placeholders",
        "lone-ampersand",
    }
    keys = work / "report.json"
    keys.write_text(report.stdout, encoding="utf-8")
    run = export_keys(tools, work, catalogue, keys, "fix")
    assert run.returncode == 0, (run.stdout, run.stderr)
    document = read_json(work / "lists" / "fix-i2.json")
    assert document["mode"] == "rework"
    assert [e["source"] for e in document["entries"]] == ["Open %1", "Save"]


# --------------------------------------------------------------------------- #
# The access-key rule travels in every exported worklist.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant("rules-list-omitted", tsw('        "rules": [ACCESS_KEY_RULE],\n', "")),
    mutant("rules-list-empty", tsw('"rules": [ACCESS_KEY_RULE],', '"rules": [],')),
    mutant(
        "rules-sentence-altered",
        tsw(
            "Write no single `&` and no access-key marker of your own. ",
            "Write what you like. ",
        ),
    ),
)
def case_every_exported_worklist_carries_the_access_key_rule(
    tools: Tools, work: Path
) -> None:
    """Both modes write a top-level ``rules`` list holding the sentence verbatim."""
    catalogue = workspace(work, "ws", KEYED)
    _, new = export_new(tools, work, catalogue)
    assert new["mode"] == "new"
    assert ACCESS_KEY_SENTENCE in rules_of(new)

    keys = key_file(work, [key("Save")])
    run = export_keys(tools, work, catalogue, keys, "rework")
    assert run.returncode == 0, (run.stdout, run.stderr)
    rework = read_json(work / "lists" / "rework-i2.json")
    assert rework["mode"] == "rework"
    assert ACCESS_KEY_SENTENCE in rules_of(rework)

    # The batch named "markers" writes markers-i1.json when instance 1 is asked for.
    run = export_keys(tools, work, catalogue, keys, "markers", "--instance", "1")
    assert run.returncode == 0, (run.stdout, run.stderr)
    markers = read_json(work / "lists" / "markers-i1.json")
    assert (markers["batch"], markers["instance"]) == ("markers", 1)
    assert markers["mode"] == "rework"
    assert ACCESS_KEY_SENTENCE in rules_of(markers)


# --------------------------------------------------------------------------- #
# Instances and the guards of export.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "next-instance-repeats-the-last",
        tsw("    return highest + 1\n", "    return highest\n"),
    ),
)
def case_a_rework_export_takes_the_next_free_instance(tools: Tools, work: Path) -> None:
    """A new worklist is instance 1, a rework starts at 2 and counts per batch."""
    catalogue = workspace(work, "ws", KEYED)
    path, document = export_new(tools, work, catalogue)
    assert path.name == "screen-i1.json" and document["instance"] == 1
    keys = key_file(work, [key("Save")])
    lists = work / "lists"
    for expected in (2, 3):
        run = export_keys(tools, work, catalogue, keys, "screen")
        assert run.returncode == 0, (run.stdout, run.stderr)
        assert (lists / f"screen-i{expected}.json").is_file()
    # Another batch counts on its own; a batch that merely starts with the same
    # letters is not confused with it.
    run = export_keys(tools, work, catalogue, keys, "scr")
    assert run.returncode == 0 and (lists / "scr-i2.json").is_file()
    # An explicit instance is taken as given.
    run = export_keys(tools, work, catalogue, keys, "screen", "--instance", "9")
    assert run.returncode == 0 and (lists / "screen-i9.json").is_file()
    assert read_json(lists / "screen-i9.json")["instance"] == 9
    # With no instance asked for, the batch named "markers" gets 2 as any rework
    # does; it is the explicit --instance 1 above that names markers-i1.json.
    run = export_keys(tools, work, catalogue, keys, "markers")
    assert run.returncode == 0 and (lists / "markers-i2.json").is_file()
    assert not (lists / "markers-i1.json").exists()


@REGISTRY.regression(
    mutant(
        "batch-name-unchecked",
        tsw("    if not BATCH_NAME.match(args.batch):\n", "    if False:\n"),
    ),
    mutant(
        "source-language-exports",
        tsw("    if catalogue.identity:\n", "    if False:\n"),
    ),
    mutant(
        "missing-source-unnamed",
        tsw("    if not os.path.isfile(source_path):\n", "    if False:\n"),
    ),
    mutant(
        "existing-worklist-overwritten",
        tsw("    if os.path.exists(path):\n", "    if False:\n"),
    ),
)
def case_export_refuses_what_it_cannot_do_safely(tools: Tools, work: Path) -> None:
    """A bad batch name, the English file, a missing source, a clash: exit 2."""
    catalogue = workspace(work, "ws")
    out = str(work / "lists")

    def run_export(target: Path, batch: str, *extra: str):
        args = ["export", "--catalogue", str(target), f"--batch={batch}"]
        return tools.run(WORKLIST, [*args, "--out-dir", out, *extra], work)

    for bad in ("../x", "a b", "-x", ""):
        result = run_export(catalogue, bad)
        assert result.returncode == 2, (bad, result.stdout, result.stderr)
        assert "invalid batch name" in result.stderr
    assert not (work / "lists").exists()

    english = catalogue.parent / "pixelart_en.ts"
    result = run_export(english, "screen")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "nothing to export" in result.stderr

    lonely = clone(catalogue, work, "lonely")
    (lonely.parent / "pixelart_en.ts").unlink()
    result = run_export(lonely, "screen")
    assert result.returncode == 2 and "pass --source" in result.stderr
    result = run_export(lonely, "screen", "--source", str(english))
    assert result.returncode == 0, (result.stdout, result.stderr)

    path = work / "lists" / "plain-i1.json"
    assert run_export(catalogue, "plain").returncode == 0
    before = path.read_bytes()
    result = run_export(catalogue, "plain")
    assert result.returncode == 2 and "exists already" in result.stderr
    assert path.read_bytes() == before
    assert run_export(catalogue, "a.b_c-1").returncode == 0


@REGISTRY.regression(
    mutant(
        "empty-export-succeeds",
        tsw('    if not document["entries"]:\n', "    if False:\n"),
    ),
    mutant("empty-import-is-silent", tsw("    if examined == 0:\n", "    if False:\n")),
)
def case_nothing_to_export_or_import_is_not_a_success(tools: Tools, work: Path) -> None:
    """No unfinished message, or a worklist without entries, exits 1."""
    done = workspace(work, "done", [Msg("Open", "Abrir"), Msg("Save", "Guardar")])
    out = work / "lists"
    args = ["export", "--catalogue", str(done), "--batch", "screen"]
    result = tools.run(WORKLIST, [*args, "--out-dir", str(out)], work)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "nothing examined" in result.stdout
    assert not out.exists()

    catalogue = workspace(work, "ws")
    before = catalogue.read_bytes()
    empty = save_json(
        work / "empty.json", {"schema": 1, "language": "es", "entries": []}
    )
    result = import_text(tools, work, empty, catalogue)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "nothing examined" in result.stdout
    assert catalogue.read_bytes() == before


# --------------------------------------------------------------------------- #
# import: finishing a new worklist, the byte-for-byte promise.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "entries-stay-unfinished",
        tsw(
            '    attributes = TYPE_ATTRIBUTE.sub("", attributes)\n',
            "    attributes = attributes\n",
        ),
    ),
)
def case_a_filled_new_worklist_finishes_its_messages(tools: Tools, work: Path) -> None:
    """The import writes the forms, drops ``unfinished`` and leaves the rest alone."""
    catalogue = workspace(work, "ws")
    _, exported = export_new(tools, work, catalogue)
    filled = save_json(work / "filled.json", with_translations(exported))
    expected = ts_text("es", finished(SPANISH, TRANSLATIONS)).encode("utf-8")

    target = clone(catalogue, work, "json")
    run, summary = import_json(tools, work, filled, target)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert summary == {
        "mode": "import",
        "examined": 3,
        "imported": 3,
        "unchanged": 0,
        "refused": 0,
        "stale_sidecar": None,
        "exit": 0,
    }
    assert target.read_bytes() == expected

    again = clone(catalogue, work, "text")
    run = import_text(tools, work, filled, again)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "examined 3 entr(ies): imported 3, unchanged 0, refused 0" in run.stdout
    assert again.read_bytes() == expected

    # The result passes the catalogue lint, and the import ignores "rules".
    lint = tools.run(CHECK, ["lint", str(target)], work)
    assert lint.returncode == 0, (lint.stdout, lint.stderr)
    bare = with_translations(exported)
    del bare["rules"]
    bare_path = save_json(work / "bare.json", bare)
    third = clone(catalogue, work, "bare")
    assert import_text(tools, work, bare_path, third).returncode == 0
    assert third.read_bytes() == expected


ROUND_TRIP = [
    Msg("Open", "Abrí", raw="Abr&#237;"),
    Msg("%n item(s)", ["%n elemento", "%n elementos"], numerus=True),
    Msg("Save", "Guardar"),
    Msg("Close", "", kind="unfinished"),
]


@REGISTRY.regression(
    mutant(
        "unchanged-entries-are-rewritten",
        tsw(
            '        if forms == message.forms and message.kind == "":\n',
            "        if False:\n",
        ),
    ),
)
def case_a_rework_round_trip_leaves_untouched_messages_byte_identical(
    tools: Tools, work: Path
) -> None:
    """Export then import changes nothing; an edit changes only its own bytes."""
    catalogue = workspace(work, "ws", ROUND_TRIP)
    original = catalogue.read_bytes()
    keys = key_file(
        work, [key("Open"), key("%n item(s)"), key("Save")], "all-finished.json"
    )
    assert export_keys(tools, work, catalogue, keys, "rework").returncode == 0
    worklist = work / "lists" / "rework-i2.json"

    run, summary = import_json(tools, work, worklist, catalogue)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert (summary["imported"], summary["unchanged"], summary["refused"]) == (0, 3, 0)
    assert catalogue.read_bytes() == original, "a round trip must be byte-identical"

    document = read_json(worklist)
    document["entries"][2]["translation"] = ["Guardar como"]
    edited = save_json(work / "edited.json", document)
    run, summary = import_json(tools, work, edited, catalogue)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert (summary["imported"], summary["unchanged"]) == (1, 2)
    expected = original.replace(
        b"<translation>Guardar</translation>",
        b"<translation>Guardar como</translation>",
    )
    assert expected != original
    assert catalogue.read_bytes() == expected, "only the edited message may change"
    assert b"Abr&#237;" in catalogue.read_bytes()


CRLF_SPANISH = [
    Msg("%n frame(s)", ["", ""], kind="unfinished", numerus=True),
    Msg("Open", "Abrir"),
]


@REGISTRY.regression(
    mutant(
        "line-ends-become-lf",
        tsw(
            '    newline = "\\r\\n" if "\\r\\n" in block else "\\n"\n',  # portability: ok (source text of the tool under mutation, not a path)
            '    newline = "\\n"\n',
        ),
    ),
)
def case_a_crlf_catalogue_keeps_its_line_ends(tools: Tools, work: Path) -> None:
    """Patching a numerus message in a CRLF catalogue adds no bare line feed."""
    folder = work / "ws"
    write_ts(folder / "pixelart_en.ts", "en", ENGLISH)
    catalogue = write_ts(folder / "pixelart_es.ts", "es", CRLF_SPANISH, newline="\r\n")
    assert re.search(rb"(?<!\r)\n", catalogue.read_bytes()) is None
    _, exported = export_new(tools, work, catalogue)
    translations = {"%n frame(s)": ["%n fotograma", "%n fotogramas"]}
    filled = save_json(work / "filled.json", with_translations(exported, translations))
    run = import_text(tools, work, filled, catalogue)
    assert run.returncode == 0, (run.stdout, run.stderr)
    data = catalogue.read_bytes()
    assert re.search(rb"(?<!\r)\n", data) is None, "a bare line feed was written"
    expected = ts_text("es", finished(CRLF_SPANISH, translations), newline="\r\n")
    assert data == expected.encode("utf-8")


# --------------------------------------------------------------------------- #
# import: staleness is judged per entry.
# --------------------------------------------------------------------------- #
CHANGED_SPANISH = [
    Msg("Open", "Abrir"),
    Msg("Close dialog", "", kind="unfinished"),
    Msg("Close", "", kind="vanished"),
    Msg("Layer %1 of %2", "", kind="unfinished", comment="Layer position"),
    Msg("%n frame(s)", ["", ""], kind="unfinished", numerus=True),
    Msg("Save", "Guardar"),
    Msg("Old", "Viejo", kind="vanished"),
]
CHANGED_ENGLISH = [
    dataclasses.replace(m, source="Close dialog") if m.source == "Close" else m
    for m in ENGLISH
]


def stale_setup(tools: Tools, work: Path):
    """Export and fill a worklist, then re-extract with one message changed.

    Returns the filled worklist and the catalogue pair AFTER the change.
    """
    before = workspace(work, "before")
    _, exported = export_new(tools, work, before)
    filled = save_json(work / "filled.json", with_translations(exported))
    after = workspace(work, "after", CHANGED_SPANISH, CHANGED_ENGLISH)
    return filled, after


@REGISTRY.regression(
    mutant(
        "stale-entry-imported-anyway",
        tsw(
            "    applied = not (refused and not args.partial)\n", "    applied = True\n"
        ),
    ),
)
def case_an_entry_whose_message_changed_is_refused_by_name(
    tools: Tools, work: Path
) -> None:
    """Without ``--partial`` the changed entry is named and nothing is written."""
    filled, after = stale_setup(tools, work)
    original = after.read_bytes()
    run = import_text(tools, work, filled, after)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert "refused entry 1 [Panel] Close: unknown-key" in run.stdout
    assert "refused entry 2" not in run.stdout and "refused entry 3" not in run.stdout
    assert "1 entr(ies) refused; nothing imported" in run.stdout
    assert after.read_bytes() == original
    assert not Path(str(filled) + ".stale.json").exists()
    run, summary = import_json(tools, work, filled, after)
    assert run.returncode == 1
    assert (summary["imported"], summary["refused"]) == (0, 1)
    assert summary["stale_sidecar"] is None
    assert after.read_bytes() == original


@REGISTRY.regression(
    mutant(
        "no-sidecar",
        tsw(
            '    if refused:\n            sidecar = args.worklist + ".stale.json"\n',
            '    if False:\n            sidecar = args.worklist + ".stale.json"\n',
        ),
    ),
    mutant(
        "stale-checks-are-empty",
        tsw(
            'STALE_CHECKS = ("unknown-key", "comment-mismatch", "numerus-flag")',
            "STALE_CHECKS = ()",
        ),
    ),
)
def case_partial_import_keeps_the_rest_and_writes_the_stale_sidecar(
    tools: Tools, work: Path
) -> None:
    """``--partial`` imports every other entry and writes the refused one aside."""
    filled, after = stale_setup(tools, work)
    sidecar = Path(str(filled) + ".stale.json")
    expected = ts_text(
        "es",
        finished(
            CHANGED_SPANISH,
            {k: v for k, v in TRANSLATIONS.items() if k != "Close"},
        ),
    ).encode("utf-8")

    target = clone(after, work, "json")
    run, summary = import_json(tools, work, filled, target, "--partial")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert summary == {
        "mode": "import",
        "examined": 3,
        "imported": 2,
        "unchanged": 0,
        "refused": 1,
        "stale_sidecar": str(sidecar),
        "exit": 0,
    }
    assert target.read_bytes() == expected
    document = read_json(sidecar)
    assert [
        document[k] for k in ("schema", "language", "batch", "instance", "mode")
    ] == [
        1,
        "es",
        "screen",
        1,
        "new",
    ]
    assert document["source_catalogue"] == "pixelart_es.ts"
    assert ACCESS_KEY_SENTENCE in rules_of(document)
    [refused] = document["entries"]
    assert refused["source"] == "Close" and refused["translation"] == ["Cerrar"]
    assert refused["refused"] == {
        "entry": 1,
        "kind": "stale",
        "findings": [{"check": "unknown-key", "detail": "entry 1: not a live message"}],
    }

    sidecar.unlink()
    again = clone(after, work, "text")
    run = import_text(tools, work, filled, again, "--partial")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "refused entry 1 [Panel] Close: unknown-key" in run.stdout
    assert "examined 3 entr(ies): imported 2, unchanged 0, refused 1" in run.stdout
    assert f"refused entries written to {sidecar}" in run.stdout
    assert again.read_bytes() == expected

    # A changed extracomment makes just that entry stale, too.
    commented = [
        (
            dataclasses.replace(m, comment="Position of the layer")
            if m.source.startswith("Layer")
            else m
        )
        for m in SPANISH
    ]
    other = workspace(work, "commented", commented)
    sidecar.unlink()
    run, summary = import_json(tools, work, filled, other, "--partial")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert (summary["imported"], summary["refused"]) == (2, 1)
    [refused] = read_json(sidecar)["entries"]
    assert refused["source"] == "Layer %1 of %2"
    assert refused["refused"]["entry"] == 2 and refused["refused"]["kind"] == "stale"
    assert [f["check"] for f in refused["refused"]["findings"]] == ["comment-mismatch"]


@REGISTRY.regression(
    mutant(
        "digest-mismatch-refuses",
        tsw(
            '                f"This is not a ground for refusal."\n            )\n',
            '                f"This is not a ground for refusal."\n'
            "            )\n"
            "            return EXIT_REFUSED\n",
        ),
    ),
)
def case_a_source_digest_mismatch_alone_is_only_printed(
    tools: Tools, work: Path
) -> None:
    """A changed English file with every entry still live imports all of them."""
    before = workspace(work, "before")
    _, exported = export_new(tools, work, before)
    filled = save_json(work / "filled.json", with_translations(exported))
    english = [*ENGLISH, Msg("Quit", "", kind="unfinished")]
    after = workspace(work, "after", english=english)
    expected = ts_text("es", finished(SPANISH, TRANSLATIONS)).encode("utf-8")

    run = import_text(tools, work, filled, after)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "note: source_sha256 differs" in run.stdout
    assert "3 of 3 entr(ies) are still live" in run.stdout
    assert "This is not a ground for refusal." in run.stdout
    assert after.read_bytes() == expected

    # With the English file back as exported there is no note at all.
    same = clone(before, work, "same")
    run = import_text(tools, work, filled, same)
    assert run.returncode == 0 and "source_sha256" not in run.stdout


# --------------------------------------------------------------------------- #
# import: entries that fail the catalogue lint, and worklists that do not fit.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "entry-findings-are-file-level",
        tsw(
            '        found = ENTRY_LABEL.match(finding["detail"])\n        if found:\n',
            '        found = ENTRY_LABEL.match(finding["detail"])\n        if False:\n',
        ),
    ),
)
def case_an_entry_that_fails_the_catalogue_lint_is_refused(
    tools: Tools, work: Path
) -> None:
    """A typed ``&`` and a lost placeholder are refused by entry; the third imports."""
    catalogue = workspace(work, "ws")
    original = catalogue.read_bytes()
    _, exported = export_new(tools, work, catalogue)
    flawed = {
        "Close": ["&Cerrar"],
        "Layer %1 of %2": ["Capa %1"],
        "%n frame(s)": ["%n fotograma", "%n fotogramas"],
    }
    worklist = save_json(work / "flawed.json", with_translations(exported, flawed))

    run = import_text(tools, work, worklist, catalogue)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert "refused entry 1 [Panel] Close: lone-ampersand" in run.stdout
    assert "refused entry 2 [Panel] Layer %1 of %2: placeholders" in run.stdout
    assert "refused entry 3" not in run.stdout
    assert "2 entr(ies) refused; nothing imported" in run.stdout
    assert catalogue.read_bytes() == original

    target = clone(catalogue, work, "partial")
    run, summary = import_json(tools, work, worklist, target, "--partial")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert (summary["imported"], summary["refused"]) == (1, 2)
    sidecar = read_json(Path(summary["stale_sidecar"]))
    assert [e["refused"]["kind"] for e in sidecar["entries"]] == ["lint", "lint"]
    assert [e["refused"]["entry"] for e in sidecar["entries"]] == [1, 2]
    done = ts_text("es", finished(SPANISH, {"%n frame(s)": flawed["%n frame(s)"]}))
    assert target.read_bytes() == done.encode("utf-8")


@REGISTRY.regression(
    mutant(
        "file-level-findings-are-dropped",
        tsw(
            '        elif finding["check"] != "nothing-examined":\n',
            "        elif False:\n",
        ),
    ),
)
def case_a_worklist_that_does_not_fit_the_catalogue_is_refused_whole(
    tools: Tools, work: Path
) -> None:
    """A worklist for another language exits 1 and imports nothing, even partially."""
    catalogue = workspace(work, "ws")
    original = catalogue.read_bytes()
    _, exported = export_new(tools, work, catalogue)
    french = with_translations(exported)
    french["language"] = "fr"
    worklist = save_json(work / "french.json", french)
    for flags in ((), ("--partial",)):
        run = import_text(tools, work, worklist, catalogue, *flags)
        assert run.returncode == 1, (flags, run.stdout, run.stderr)
        assert "refused worklist: language-attribute" in run.stdout
        assert "examined 3 entr(ies); nothing imported" in run.stdout
        assert catalogue.read_bytes() == original
    assert not Path(str(worklist) + ".stale.json").exists()


# --------------------------------------------------------------------------- #
# Read and usage errors.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "read-error-exits-1",
        tsw("        return EXIT_ERROR\n", "        return EXIT_REFUSED\n"),
    ),
)
def case_an_unreadable_input_exits_2(tools: Tools, work: Path) -> None:
    """A missing or malformed worklist, catalogue or keys file exits 2."""
    catalogue = workspace(work, "ws", KEYED)

    def code(*args: str) -> int:
        result = tools.run(WORKLIST, list(args), work)
        assert result.stdout == "" or result.returncode != 2, result.stdout
        return result.returncode

    cat = str(catalogue)
    assert code("import", str(work / "no.json"), "--catalogue", cat) == 2
    garbage = work / "garbage.json"
    garbage.write_text("{not json", encoding="utf-8")
    assert code("import", str(garbage), "--catalogue", cat) == 2
    listing = save_json(work / "list.json", [])
    assert code("import", str(listing), "--catalogue", cat) == 2
    odd = save_json(work / "odd.json", {"schema": 1, "entries": ["text"]})
    assert code("import", str(odd), "--catalogue", cat) == 2
    ok = save_json(work / "ok.json", {"schema": 1, "entries": []})
    assert code("import", str(ok), "--catalogue", str(work / "no.ts")) == 2

    out = ["--batch", "b", "--out-dir", str(work / "lists")]
    assert code("export", "--catalogue", str(work / "no.ts"), *out) == 2
    for text in ('{"x": 1}', "[1]", '[{"context": "Panel"}]', "{not json"):
        keys = work / "bad-keys.json"
        keys.write_text(text, encoding="utf-8")
        assert code("export", "--catalogue", cat, *out, "--keys", str(keys)) == 2, text
    assert code() == 2, "no mode word is a usage error"
    assert code("export", "--catalogue", cat) == 2, "missing --batch is a usage error"


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
    """A copy of the pair, unedited, still finds the lint beside it and passes."""
    tools = make_broken(tmp_path / "scripts", Mutant("unmodified", ()))
    for case in REGISTRY.cases[:3]:
        work = tmp_path / case.name
        work.mkdir()
        case.run(tools, work)
