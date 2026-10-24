"""Contract tests for ``scripts/i18n_extract.py`` (ADR-0047).

Contract asserted here, taken from the script's own header::

    i18n_extract.py [--check] [--json] [--root DIR] [--source DIR]
                    [--catalogues DIR] [--locales a,b] [--removals FILE]
                    [--backup-dir DIR] [--keep-backup] [--lupdate EXE]
    EXIT CODES: 0 nothing lost / keys identical ; 1 an unrecorded drop (the
        catalogues are restored) or changed keys in --check, or nothing was
        examined ; 2 the tool or an input is unavailable, or lupdate failed.

Scenario bound here: SC-L10N-BUILD-007-1 (a regeneration that loses
translations is rejected: the step exits non-zero and the catalogue is restored
from its backup).

Method. The real ``pyside6-lupdate`` is NEVER run by this module, and no
tracked catalogue is ever handed to the script. Every case builds a scratch
product root under ``tmp_path`` (a source folder, two catalogues written with
CRLF line ends and non-ASCII text so that a restore that normalises anything
is visible) and passes ``--root`` and ``--lupdate`` to a small stand-in
executable written beside it. The stand-in understands ``-extensions py`` the
way the real tool does, reads the ``tr()`` calls of the scratch source, keeps
the translations of the messages that survive, marks the vanished ones, and
records every call it receives (argv and working directory) so the tests assert
what the script actually ran. A ``plan.json`` beside it makes it misbehave on
demand: fail, empty the catalogues, empty or alter the surviving
translations. The subprocesses get their temporary folder under ``tmp_path``
too, so the backups and scratch copies the script makes are visible and are
deleted with the test.

Each REGRESSION CASE drives the script through a clean fixture and a broken one
and is registered with MUTANTS: copies of the script, made under ``tmp_path``,
with one guarded line altered so that the rule the case defends is gone. The
module's generic tests run every case against the real script (it must hold)
and against each broken copy (it must raise an ``AssertionError``). The
registry, the scratch-catalogue writer and the edit types are imported from the
sibling module for ``check_catalogues.py``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR, ScriptRun
from .test_check_catalogues import (
    Case,
    Edit,
    Msg,
    Mutant,
    Registry,
    Tools,
    mutant,
    put,
)

EXTRACT = "i18n_extract.py"
REGISTRY = Registry()


def ex(old: str, new: str) -> Edit:
    """Build an edit of ``i18n_extract.py``."""
    return Edit(EXTRACT, old, new)


def make_broken(folder: Path, broken: Mutant) -> Tools:
    """Copy the script into ``folder`` and apply ``broken``'s edits.

    Files are read and written as bytes. An anchor that is not found exactly
    once, or an edit that leaves a script that does not compile, raises: a
    control must fail for the reason it names and for no other.
    """
    folder.mkdir(parents=True)
    shutil.copyfile(SCRIPTS_DIR / EXTRACT, folder / EXTRACT)
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
# The repository's own catalogues must come out of this module untouched.
# --------------------------------------------------------------------------- #
def _digests() -> dict[str, str]:
    """Return the sha256 of every tracked catalogue of the working tree."""
    folder = REPO_ROOT / "pixelart_creator" / "i18n"
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.glob("pixelart_*.ts"))
    }


@pytest.fixture(scope="module", autouse=True)
def tracked_catalogues_stay_untouched():
    """Fail the module if any tracked catalogue changed while it ran."""
    before = _digests()
    assert before, "no tracked catalogue found: the guard would be blind"
    yield
    assert _digests() == before


# --------------------------------------------------------------------------- #
# The stand-in for pyside6-lupdate.
# --------------------------------------------------------------------------- #
STUB = r'''
import json
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HERE = pathlib.Path(__file__).resolve().parent
PLAN_FILE = HERE / "plan.json"
PLAN = json.loads(PLAN_FILE.read_text(encoding="utf-8")) if PLAN_FILE.exists() else {}
ARGV = sys.argv[1:]
with (HERE / "calls.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": ARGV, "cwd": os.getcwd()}) + "\n")

CALL = re.compile(r'\b(ntr|tr)\("([^"]*)"\)')
CLASS = re.compile(r"^class (\w+)")
DEAD = ("vanished", "obsolete")


def split(argv):
    """Return (inputs, extensions_active, targets) the way lupdate reads argv."""
    stop = argv.index("-ts") if "-ts" in argv else len(argv)
    head, targets = argv[:stop], argv[stop + 1:]
    inputs, active, i = [], False, 0
    while i < len(head):
        if head[i] == "-extensions" and i + 1 < len(head):
            if not inputs:
                active = head[i + 1] == "py"
            i += 2
            continue
        inputs.append(head[i])
        i += 1
    return inputs, active, targets


def scan(inputs):
    """Return the (context, source, numerus) keys of the tr() calls found."""
    found = []
    for entry in inputs:
        for path in sorted(pathlib.Path(entry).rglob("*.py")):
            context = "Unknown"
            for line in path.read_text(encoding="utf-8").splitlines():
                named = CLASS.match(line)
                if named:
                    context = named.group(1)
                for call in CALL.finditer(line):
                    key = (context, call.group(2), call.group(1) == "ntr")
                    if key not in found:
                        found.append(key)
    return found


def load(path):
    root = ET.parse(path).getroot()
    messages = []
    for context in root.iter("context"):
        name = context.findtext("name")
        for element in context.findall("message"):
            numerus = element.get("numerus") == "yes"
            translation = element.find("translation")
            kind = (translation.get("type") or "") if translation is not None else ""
            if numerus:
                forms = [f.text or "" for f in translation.findall("numerusform")]
            else:
                forms = [translation.text or ""]
            messages.append(
                {
                    "context": name,
                    "source": element.findtext("source") or "",
                    "numerus": numerus,
                    "kind": kind,
                    "forms": forms,
                }
            )
    return root.get("language"), root.get("sourcelanguage"), messages


def rebuild(existing, found):
    live = {
        (m["context"], m["source"], m["numerus"]): m
        for m in existing
        if m["kind"] not in DEAD
    }
    out = []
    for key in found:
        old = live.get(key)
        if old is None:
            forms = ["", ""] if key[2] else [""]
            out.append(
                {"context": key[0], "source": key[1], "numerus": key[2],
                 "kind": "unfinished", "forms": forms}
            )
            continue
        forms, kind = list(old["forms"]), old["kind"]
        if PLAN.get("mode") == "empty_translations":
            forms, kind = [""] * len(forms), "unfinished"
        elif PLAN.get("mode") == "alter_translations":
            forms = [f + "!" if f else f for f in forms]
        out.append({**old, "forms": forms, "kind": kind})
    for key, old in live.items():
        if key not in found and any(old["forms"]):
            out.append({**old, "kind": "vanished"})
    out += [m for m in existing if m["kind"] in DEAD]
    return out


def write(path, language, source_language, messages):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!DOCTYPE TS>",
        f'<TS version="2.1" language="{language}" sourcelanguage="{source_language}">',
    ]
    contexts = {}
    for message in messages:
        contexts.setdefault(message["context"], []).append(message)
    for name, group in contexts.items():
        lines += ["<context>", f"    <name>{escape(name)}</name>"]
        for m in group:
            opening = '    <message numerus="yes">' if m["numerus"] else "    <message>"
            lines.append(opening)
            lines.append(f"        <source>{escape(m['source'])}</source>")
            kind = f' type="{m["kind"]}"' if m["kind"] else ""
            if m["numerus"]:
                lines.append(f"        <translation{kind}>")
                for form in m["forms"]:
                    body = escape(form)
                    lines.append(f"            <numerusform>{body}</numerusform>")
                lines.append("        </translation>")
            else:
                body = escape(m["forms"][0])
                lines.append(f"        <translation{kind}>{body}</translation>")
            lines.append("    </message>")
        lines.append("</context>")
    lines.append("</TS>")
    pathlib.Path(path).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


inputs, active, targets = split(ARGV)
found = scan(inputs) if active else []
if PLAN.get("mode") == "fail":
    for target in targets:
        pathlib.Path(target).write_bytes(b"<TS><truncated")
    print("lupdate-stub: fatal: simulated failure", file=sys.stderr)
    sys.exit(3)
for target in targets:
    path = pathlib.Path(os.getcwd()) / target
    language, source_language, existing = load(path)
    if PLAN.get("mode") == "empty_all":
        write(path, language, source_language, [])
    else:
        write(path, language, source_language, rebuild(existing, found))
print("lupdate-stub: done")
'''


class World(NamedTuple):
    """A scratch product root, the stand-in tool and the temporary folder."""

    work: Path
    root: Path
    launcher: Path
    stub_dir: Path
    temp: Path
    source: str
    catalogues: str

    def catalogue_paths(self) -> list[Path]:
        """Return the scratch catalogues, sorted by name."""
        return sorted((self.root / self.catalogues).glob("pixelart_*.ts"))

    def catalogue_bytes(self) -> dict[str, bytes]:
        """Return the bytes of every scratch catalogue by file name."""
        return {path.name: path.read_bytes() for path in self.catalogue_paths()}

    def plan(self, **plan: object) -> None:
        """Tell the stand-in how to behave from now on."""
        (self.stub_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

    def calls(self) -> list[dict]:
        """Return every call the stand-in received, in order."""
        path = self.stub_dir / "calls.jsonl"
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def write_source(self, text: str, name: str = "panel.py") -> None:
        """Write a module of the scratch source folder."""
        folder = self.root / self.source
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(text.encode("utf-8"))

    def leftovers(self, prefix: str) -> list[str]:
        """Return the names in the temporary folder that start with ``prefix``."""
        return sorted(p.name for p in self.temp.iterdir() if p.name.startswith(prefix))


SOURCE = '''\
class Panel:
    """A scratch widget."""

    def build(self):
        self.tr("Open")
        self.tr("Close")
        self.tr("Save")
        self.ntr("%n frame(s)")
'''

ENGLISH = [
    Msg("Open", "Open"),
    Msg("Close", "Close"),
    Msg("Save", "Save"),
    Msg("%n frame(s)", ["%n frame", "%n frames"], numerus=True),
]

SPANISH = [
    Msg("Open", "Abrir"),
    Msg("Close", "Cerrar sesi\u00f3n"),
    Msg("Save", "", kind="unfinished"),
    Msg("%n frame(s)", ["%n fotograma", "%n fotogramas"], numerus=True),
    Msg("Gone", "Antiguo", kind="vanished"),
    Msg("Older", "Viejo", kind="obsolete"),
]

# Live messages and non-empty translations of the two fixtures above.
EN_LIVE, EN_TRANSLATED = 4, 4
ES_LIVE, ES_TRANSLATED = 4, 3


def install_stub(folder: Path) -> Path:
    """Write the stand-in tool and a launcher for this platform; return it."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "lupdate_stub.py"
    script.write_bytes(STUB.encode("utf-8"))
    if sys.platform == "win32":
        launcher = folder / "lupdate-stub.cmd"
        text = f'@"{sys.executable}" "{script}" %*\r\n'
    else:
        launcher = folder / "lupdate-stub"
        text = f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n'
    launcher.write_bytes(text.encode("utf-8"))
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return launcher


def build_world(
    work: Path,
    *,
    english: list[Msg] | None = None,
    spanish: list[Msg] | None = None,
    source: str = SOURCE,
    source_dir: str = "pixelart_creator",
    catalogue_dir: str = "pixelart_creator/i18n",
) -> World:
    """Build a scratch root with an English and a Spanish catalogue.

    The catalogues use CRLF line ends and a non-ASCII translation, which the
    stand-in rewrites with LF, so any restore that is not a byte copy shows.
    """
    work.mkdir(parents=True, exist_ok=True)
    root = work / "root"
    stub_dir = work / "stub"
    temp = work / "temp"
    temp.mkdir(exist_ok=True)
    launcher = install_stub(stub_dir)
    world = World(work, root, launcher, stub_dir, temp, source_dir, catalogue_dir)
    world.write_source(source)
    put(
        root,
        catalogue_dir,
        "en",
        ENGLISH if english is None else english,
        newline="\r\n",
    )
    put(
        root,
        catalogue_dir,
        "es",
        SPANISH if spanish is None else spanish,
        newline="\r\n",
    )
    return world


def invoke(
    tools: Tools, world: World, *args: str, lupdate: str | None = None
) -> ScriptRun:
    """Run the script under test against ``world`` with the stand-in tool.

    ``--root`` and ``--lupdate`` are always passed, so the real tool and the
    real catalogues can never be reached from here.
    """
    command = [
        sys.executable,
        str(tools.folder / EXTRACT),
        "--root",
        str(world.root),
        "--lupdate",
        lupdate if lupdate is not None else str(world.launcher),
        *args,
    ]
    env = dict(os.environ)
    env.update(TMPDIR=str(world.temp), TEMP=str(world.temp), TMP=str(world.temp))
    completed = subprocess.run(
        command,
        cwd=str(world.work),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env=env,
    )
    return ScriptRun(completed.returncode, completed.stdout, completed.stderr)


def report(run: ScriptRun) -> dict:
    """Parse the JSON document the script printed on stdout."""
    try:
        payload = json.loads(run.stdout)
    except ValueError:
        raise AssertionError(
            f"stdout is not JSON: exit {run.returncode}, stdout "
            f"{run.stdout[:300]!r}, stderr {run.stderr[:300]!r}"
        ) from None
    assert isinstance(payload, dict), payload
    return payload


def by_name(payload: dict) -> dict[str, dict]:
    """Return the per-catalogue records of a report by catalogue file name."""
    return {record["catalogue"]: record for record in payload["catalogues"]}


def key(source: str, context: str = "Panel", plural: bool = False) -> list:
    """Return a message key the way the JSON report spells it."""
    return [context, source, "", plural]


def renamed(old: str, new: str) -> str:
    """Return the scratch source with one translatable string renamed."""
    return SOURCE.replace(f'"{old}"', f'"{new}"')


def sha(data: dict[str, bytes]) -> dict[str, str]:
    """Return the sha256 of each value of ``data``."""
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}


# --------------------------------------------------------------------------- #
# Extraction mode: nothing lost.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "empty-translation-counts",
        ex(
            "        return {key for key, text in self.live.items() if text}\n",
            "        return set(self.live)\n",
        ),
    ),
    mutant(
        "obsolete-is-live",
        ex(
            'DEAD_TYPES = frozenset({"vanished", "obsolete"})\n',
            'DEAD_TYPES = frozenset({"vanished"})\n',
        ),
    ),
    mutant(
        "no-live-key-total",
        ex(
            "{report['keys_examined']} live key(s)\"\n",
            "{report['keys_examined']} keys\"\n",
        ),
    ),
    mutant(
        "unchanged-run-fails",
        ex(
            "    ok = examined > 0 and all(r.ok for r in results)\n",
            "    ok = False\n",
        ),
    ),
)
def case_an_unchanged_source_extracts_and_exits_0(tools: Tools, work: Path) -> None:
    """On the unchanged source the counts are printed per catalogue; exit 0.

    SC-L10N-BUILD-007-1, the clean leg: nothing is lost, so nothing is
    restored. Vanished and obsolete messages are not live, and a translation
    only counts when it is not empty.
    """
    world = build_world(work)
    assert b"\r\n" in world.catalogue_bytes()["pixelart_es.ts"]
    run = invoke(tools, world, "--json")
    assert run.returncode == 0, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["mode"] == "extract"
    assert payload["ok"] is True
    assert payload["restored_from_backup"] is False
    assert payload["keys_examined"] == EN_LIVE + ES_LIVE
    records = by_name(payload)
    assert sorted(records) == ["pixelart_en.ts", "pixelart_es.ts"]
    en, es = records["pixelart_en.ts"], records["pixelart_es.ts"]
    assert [en[k] for k in ("messages_before", "messages_after")] == [EN_LIVE] * 2
    assert [en[k] for k in ("translations_before", "translations_after")] == [
        EN_TRANSLATED
    ] * 2
    assert [es[k] for k in ("messages_before", "messages_after")] == [ES_LIVE] * 2
    assert [es[k] for k in ("translations_before", "translations_after")] == [
        ES_TRANSLATED
    ] * 2
    assert [es[k] for k in ("vanished_before", "vanished_after")] == [2, 2]
    assert es["removed"] == es["added"] == es["unrecorded_removed"] == []
    # JSON mode keeps stdout for the document and prints the table on stderr.
    assert f"{ES_LIVE} -> {ES_LIVE}" in run.stderr
    assert f"{ES_TRANSLATED} -> {ES_TRANSLATED}" in run.stderr
    assert "verdict: OK" in run.stderr
    text = invoke(tools, world)
    assert text.returncode == 0, (text.stdout, text.stderr)
    assert "live messages" in text.stdout
    assert "non-empty translations" in text.stdout
    assert f"examined: 2 catalogue(s), {EN_LIVE + ES_LIVE} live key(s)" in text.stdout
    assert "verdict: OK" in text.stdout


@REGISTRY.regression(
    mutant(
        "no-restore",
        ex(
            "    if not ok:\n        _restore(paths, raws)\n        restored = True\n",
            "    if not ok:\n        restored = True\n",
        ),
    ),
    mutant(
        "restore-normalises-line-ends",
        ex(
            "        path.write_bytes(raws[path.name])\n",
            "        path.write_bytes("  # portability: ok (CR-LF escape text)
            'raws[path.name].replace(b"\\r\\n", b"\\n"))\n',
        ),
        ex("        if path.read_bytes() != raws[path.name]:\n", "        if False:\n"),
    ),
    mutant(
        "unrecorded-drop-passes",
        ex(
            "        return not (self.unrecorded_removed or self.lost_translations "
            "or self.altered)\n",
            "        return not (self.lost_translations or self.altered)\n",
        ),
    ),
    mutant(
        "backup-is-truncated",
        ex(
            "        (backup / name).write_bytes(raw)\n",
            "        (backup / name).write_bytes(raw[:-1])\n",
        ),
    ),
)
def case_a_drop_with_no_record_exits_1_and_restores_byte_identical(
    tools: Tools, work: Path
) -> None:
    """A string leaves the source without a record: exit 1, bytes restored.

    SC-L10N-BUILD-007-1. The catalogues were rewritten by the stand-in (with
    LF line ends) before the script restored them, so equality with the
    original CRLF bytes proves a byte copy, not a re-serialisation. The
    backup the script made is byte-identical too.
    """
    world = build_world(work)
    originals = world.catalogue_bytes()
    world.write_source(renamed("Open", "Open file"))
    backup = work / "backup"
    run = invoke(tools, world, "--json", "--backup-dir", str(backup))
    assert run.returncode == 1, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["ok"] is False
    assert payload["restored_from_backup"] is True
    records = by_name(payload)
    for name in ("pixelart_en.ts", "pixelart_es.ts"):
        assert records[name]["unrecorded_removed"] == [key("Open")]
        assert records[name]["added"] == [key("Open file")]
    assert len(world.calls()) == 1
    assert world.catalogue_bytes() == originals
    assert backup.is_dir()
    assert {p.name: p.read_bytes() for p in backup.iterdir()} == originals
    assert "REMOVED WITHOUT A RECORD" in run.stderr
    assert "RESTORED every catalogue byte-identical" in run.stderr
    assert "verdict: FAILED" in run.stderr


@REGISTRY.regression(
    mutant(
        "record-never-excuses",
        ex(
            '    return any((c, key3) in removals for c in ("*", catalogue, stem))\n',
            "    return False\n",
        ),
    ),
    mutant(
        "record-excuses-every-catalogue",
        ex(
            '    return any((c, key3) in removals for c in ("*", catalogue, stem))\n',
            "    return any(k3 == key3 for (_c, k3) in removals)\n",
        ),
    ),
    mutant(
        "reason-not-required", ex("        if not reason:\n", "        if False:\n")
    ),
    mutant(
        "context-alone-excuses",
        ex(
            '    return any((c, key3) in removals for c in ("*", catalogue, stem))\n',
            "    return any(k3[0] == key3[0] for (_c, k3) in removals)\n",
        ),
    ),
)
def case_a_recorded_removal_may_leave_a_catalogue(tools: Tools, work: Path) -> None:
    """Only a removal listed with a reason, for that catalogue, may leave it.

    SC-L10N-BUILD-007-1, the recorded leg: the same renamed string exits 0
    once the removals file lists it with a reason; a record for the other
    catalogue, for another string, or without a reason does not excuse it.
    """
    removal = {"context": "Panel", "source": "Open", "comment": ""}
    removals = work / "removals.json"

    def write(*entries: dict) -> None:
        removals.write_text(json.dumps({"removals": list(entries)}), encoding="utf-8")

    world = build_world(work / "all")
    world.write_source(renamed("Open", "Open file"))
    write({**removal, "reason": "renamed for clarity"})
    run = invoke(tools, world, "--json", "--removals", str(removals))
    assert run.returncode == 0, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["ok"] is True and payload["restored_from_backup"] is False
    records = by_name(payload)
    assert records["pixelart_es.ts"]["removed"] == [key("Open")]
    assert records["pixelart_es.ts"]["unrecorded_removed"] == []
    assert records["pixelart_es.ts"]["added"] == [key("Open file")]
    assert records["pixelart_es.ts"]["translations_before"] == ES_TRANSLATED
    assert records["pixelart_es.ts"]["translations_after"] == ES_TRANSLATED - 1
    assert "removed (recorded) (1):" in run.stderr

    # A record for one catalogue does not excuse the removal from the other.
    one = build_world(work / "one")
    one.write_source(renamed("Open", "Open file"))
    originals = one.catalogue_bytes()
    write({**removal, "reason": "renamed", "catalogue": "pixelart_es.ts"})
    run = invoke(tools, one, "--json", "--removals", str(removals))
    assert run.returncode == 1, (run.stdout, run.stderr)
    records = by_name(report(run))
    assert records["pixelart_es.ts"]["unrecorded_removed"] == []
    assert records["pixelart_en.ts"]["unrecorded_removed"] == [key("Open")]
    assert one.catalogue_bytes() == originals

    # A record for another string excuses nothing.
    other = build_world(work / "other")
    other.write_source(renamed("Open", "Open file"))
    write({**removal, "source": "Close", "reason": "unrelated"})
    run = invoke(tools, other, "--removals", str(removals))
    assert run.returncode == 1, (run.stdout, run.stderr)

    # A removal with no reason is refused before lupdate runs at all.
    bare = build_world(work / "bare")
    originals = bare.catalogue_bytes()
    write({**removal, "reason": "  "})
    run = invoke(tools, bare, "--removals", str(removals))
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "removal without a reason" in run.stderr
    assert bare.calls() == []
    assert bare.catalogue_bytes() == originals


@REGISTRY.regression(
    mutant(
        "emptied-translation-passes",
        ex("        if old and not new:\n", "        if False:\n"),
    ),
    mutant(
        "altered-translation-passes",
        ex("        elif old and new and old != new:\n", "        elif False:\n"),
    ),
)
def case_a_surviving_translation_that_is_emptied_or_altered_is_refused(
    tools: Tools, work: Path
) -> None:
    """A message that survives with a different translation is a loss.

    SC-L10N-BUILD-007-1. The tool keeps every message here, so the count of
    messages does not move; the non-empty translations do, or their text.
    """
    emptied = build_world(work / "emptied")
    originals = emptied.catalogue_bytes()
    emptied.plan(mode="empty_translations")
    run = invoke(tools, emptied, "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    records = by_name(report(run))
    assert len(records["pixelart_es.ts"]["lost_translations"]) == ES_TRANSLATED
    assert records["pixelart_es.ts"]["translations_after"] == 0
    assert "TRANSLATION EMPTIED" in run.stderr
    assert emptied.catalogue_bytes() == originals

    altered = build_world(work / "altered")
    originals = altered.catalogue_bytes()
    altered.plan(mode="alter_translations")
    run = invoke(tools, altered, "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    records = by_name(report(run))
    assert len(records["pixelart_es.ts"]["altered_translations"]) == ES_TRANSLATED
    assert "TRANSLATION ALTERED" in run.stderr
    assert altered.catalogue_bytes() == originals


@REGISTRY.regression(
    mutant(
        "emptying-tool-passes",
        ex(
            "    ok = examined > 0 and all(r.ok for r in results)\n",
            "    ok = True\n",
        ),
    ),
    mutant(
        "no-restore",
        ex(
            "    if not ok:\n        _restore(paths, raws)\n        restored = True\n",
            "    if not ok:\n        restored = True\n",
        ),
    ),
)
def case_a_tool_that_empties_every_catalogue_is_caught(
    tools: Tools, work: Path
) -> None:
    """A run that exits 0 but leaves no message behind is rejected and undone.

    SC-L10N-BUILD-007-1. This is the failure that a wrong ``-extensions``
    placement causes in the real tool: it scans no Python file and writes
    empty catalogues while exiting 0.
    """
    world = build_world(work)
    originals = world.catalogue_bytes()
    world.plan(mode="empty_all")
    run = invoke(tools, world, "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["restored_from_backup"] is True
    records = by_name(payload)
    assert len(records["pixelart_es.ts"]["unrecorded_removed"]) == ES_LIVE
    assert len(records["pixelart_en.ts"]["unrecorded_removed"]) == EN_LIVE
    assert world.catalogue_bytes() == originals


@REGISTRY.regression(
    mutant(
        "no-restore-after-failure",
        ex(
            "    except ExtractError:\n        _restore(paths, raws)\n        raise\n",
            "    except ExtractError:\n        raise\n",
        ),
    ),
    mutant(
        "failing-tool-is-ignored",
        ex("    if done.returncode != 0:\n", "    if False:\n"),
    ),
)
def case_a_failing_lupdate_restores_the_catalogues_and_exits_2(
    tools: Tools, work: Path
) -> None:
    """When lupdate fails half way the catalogues are put back; exit 2."""
    world = build_world(work)
    originals = world.catalogue_bytes()
    world.plan(mode="fail")
    run = invoke(tools, world)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "ERROR:" in run.stderr
    assert "exited 3" in run.stderr
    assert "simulated failure" in run.stderr
    assert world.catalogue_bytes() == originals


# --------------------------------------------------------------------------- #
# The lupdate argv.
# --------------------------------------------------------------------------- #
def posix(args: list[str]) -> list[str]:
    """Return ``args`` with path separators spelled the same on every OS."""
    return [a.replace("\\", "/") for a in args]


@REGISTRY.regression(
    mutant(
        "extensions-after-the-source",
        ex(
            '    argv = [lupdate, "-extensions", "py", source, "-ts", *catalogues]\n',
            '    argv = [lupdate, source, "-extensions", "py", "-ts", *catalogues]\n',
        ),
        ex("    verify_argv(argv, source)\n    return argv\n", "    return argv\n"),
    ),
    mutant(
        "extensions-left-out",
        ex(
            '    argv = [lupdate, "-extensions", "py", source, "-ts", *catalogues]\n',
            '    argv = [lupdate, source, "-ts", *catalogues]\n',
        ),
        ex("    verify_argv(argv, source)\n    return argv\n", "    return argv\n"),
    ),
    mutant(
        "source-option-ignored",
        ex(
            "        lupdate, args.source, [os.path.relpath(p, root) for p in paths]\n",
            "        lupdate, DEFAULT_SOURCE, "
            "[os.path.relpath(p, root) for p in paths]\n",
        ),
    ),
)
def case_the_lupdate_argv_carries_extensions_py_before_the_source(
    tools: Tools, work: Path
) -> None:
    """The argv the script really ran has ``-extensions py`` before the source.

    Asserted on what the stand-in received, not assumed from the code: a
    flag placed after the source (or left out) makes the real tool scan no
    Python file and empty every catalogue at exit 0.
    """
    world = build_world(work / "default")
    run = invoke(tools, world)
    assert run.returncode == 0, (run.stdout, run.stderr)
    calls = world.calls()
    assert len(calls) == 1, calls
    (call,) = calls
    assert Path(call["cwd"]).resolve() == world.root.resolve()
    argv = posix(call["argv"])
    assert argv == [
        "-extensions",
        "py",
        "pixelart_creator",
        "-ts",
        "pixelart_creator/i18n/pixelart_en.ts",
        "pixelart_creator/i18n/pixelart_es.ts",
    ]
    assert argv.index("-extensions") < argv.index("pixelart_creator")
    assert argv.index("pixelart_creator") < argv.index("-ts")

    custom = build_world(work / "custom", source_dir="app", catalogue_dir="app/langs")
    run = invoke(tools, custom, "--source", "app", "--catalogues", "app/langs")
    assert run.returncode == 0, (run.stdout, run.stderr)
    calls = custom.calls()
    assert len(calls) == 1, calls
    (call,) = calls
    assert posix(call["argv"]) == [
        "-extensions",
        "py",
        "app",
        "-ts",
        "app/langs/pixelart_en.ts",
        "app/langs/pixelart_es.ts",
    ]


def load_module(folder: Path) -> ModuleType:
    """Load the script of ``folder`` as a module, for its pure functions."""
    path = folder / EXTRACT
    name = f"i18n_extract_{hashlib.sha256(str(path).encode()).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[name]
    return module


def assert_refused(module: ModuleType, argv: list[str], source: str) -> None:
    """Assert that ``verify_argv`` raises its error for ``argv``."""
    try:
        module.verify_argv(argv, source)
    except module.ExtractError:
        return
    raise AssertionError(f"verify_argv accepted {argv}")


@REGISTRY.regression(
    mutant(
        "order-not-checked",
        ex(
            '    if argv[flag + 1 : flag + 2] != ["py"] or flag >= where:\n',
            '    if argv[flag + 1 : flag + 2] != ["py"]:\n',
        ),
    ),
    mutant(
        "language-not-checked",
        ex(
            '    if argv[flag + 1 : flag + 2] != ["py"] or flag >= where:\n',
            "    if flag >= where:\n",
        ),
    ),
    mutant(
        "ts-position-not-checked",
        ex(
            '    if "-ts" not in argv or argv.index("-ts") < where:\n',
            "    if False:\n",
        ),
    ),
    mutant(
        "missing-flag-accepted",
        ex(
            "        raise ExtractError("
            'f"lupdate argv lacks -extensions or the source: {exc}")\n',
            "        return\n",
        ),
    ),
)
def case_the_argv_guard_refuses_every_wrong_order(tools: Tools, work: Path) -> None:
    """``verify_argv`` accepts the one right shape and refuses the wrong ones."""
    module = load_module(tools.folder)
    good = ["lupdate", "-extensions", "py", "src", "-ts", "a.ts", "b.ts"]
    assert module.build_lupdate_argv("lupdate", "src", ["a.ts", "b.ts"]) == good
    module.verify_argv(good, "src")
    assert_refused(
        module, ["lupdate", "src", "-extensions", "py", "-ts", "a.ts"], "src"
    )
    assert_refused(module, ["lupdate", "src", "-ts", "a.ts"], "src")
    assert_refused(
        module, ["lupdate", "-extensions", "cpp", "src", "-ts", "a.ts"], "src"
    )
    assert_refused(
        module, ["lupdate", "-extensions", "py", "-ts", "a.ts", "src"], "src"
    )
    assert_refused(module, ["lupdate", "-extensions", "py", "src", "a.ts"], "src")


# --------------------------------------------------------------------------- #
# --check: the English-source freeze proof.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "check-writes-the-tracked-catalogue",
        ex("            copy = scratch / path.name\n", "            copy = path\n"),
        ex(
            "    unchanged = all(p.read_bytes() == raws[p.name] for p in paths)\n",
            "    unchanged = True\n",
        ),
    ),
    mutant(
        "scratch-left-behind",
        ex("        shutil.rmtree(scratch, ignore_errors=True)\n", "        pass\n"),
    ),
    mutant(
        "no-keys-examined-line",
        ex(
            '                f"    live keys examined: {r.before.messages} tracked, "\n'
            '                f"{r.after.messages} extracted"\n',
            '                f"    live keys: {r.before.messages} tracked, "\n'
            '                f"{r.after.messages} extracted"\n',
        ),
    ),
    mutant(
        "check-fails-on-identical-keys",
        ex(
            "    ok = examined > 0 and not live_empty and identical\n",
            "    ok = False\n",
        ),
    ),
)
def case_check_on_the_unchanged_source_exits_0_and_writes_nothing(
    tools: Tools, work: Path
) -> None:
    """``--check`` on the unchanged source: exit 0, keys printed, no write.

    SC-L10N-BUILD-007-1 (the freeze proof). The stand-in is handed scratch
    copies only: every ``-ts`` it received lies in the temporary folder, none
    in the root, and the tracked catalogues are byte-identical afterwards.
    """
    world = build_world(work)
    originals = world.catalogue_bytes()
    run = invoke(tools, world, "--check", "--json")
    assert run.returncode == 0, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["mode"] == "check"
    assert payload["ok"] is True
    assert payload["tracked_catalogues_unchanged"] is True
    assert payload["keys_examined"] == EN_LIVE + ES_LIVE
    assert payload["zero_examined"] == []
    for record in payload["catalogues"]:
        assert record["added"] == [] and record["removed"] == []
    assert f"live keys examined: {ES_LIVE} tracked, {ES_LIVE} extracted" in run.stderr
    assert f"live keys examined: {EN_LIVE} tracked, {EN_LIVE} extracted" in run.stderr
    assert "tracked catalogues byte-identical after the run: True" in run.stderr
    assert "verdict: OK" in run.stderr
    assert world.catalogue_bytes() == originals
    calls = world.calls()
    assert len(calls) == 1, calls
    (call,) = calls
    argv = call["argv"]
    assert argv[:3] == ["-extensions", "py", "pixelart_creator"]
    scratch = [Path(arg) for arg in argv[argv.index("-ts") + 1 :]]
    assert len(scratch) == 2
    for path in scratch:
        assert path.is_absolute()
        assert world.temp.resolve() in path.resolve().parents
        assert world.root.resolve() not in path.resolve().parents
    assert world.leftovers("i18n_extract_check_") == []


@REGISTRY.regression(
    mutant(
        "added-key-ignored",
        ex(
            "    identical = all(not r.removed and not r.added for r in results)\n",
            "    identical = all(not r.removed for r in results)\n",
        ),
    ),
    mutant(
        "removed-key-ignored",
        ex(
            "    identical = all(not r.removed and not r.added for r in results)\n",
            "    identical = all(not r.added for r in results)\n",
        ),
    ),
    mutant(
        "changed-keys-pass",
        ex(
            "    ok = examined > 0 and not live_empty and identical\n",
            "    ok = True\n",
        ),
    ),
    mutant(
        "removed-keys-not-listed",
        ex(
            '            lines += _lines("removed keys", r.removed)\n',
            "            pass\n",
        ),
    ),
    mutant(
        "added-keys-not-listed",
        ex(
            "        lines += _lines("
            '"added keys" if check_mode else "added", r.added)\n',
            "        pass\n",
        ),
    ),
    mutant(
        "check-writes-the-tracked-catalogue",
        ex("            copy = scratch / path.name\n", "            copy = path\n"),
        ex(
            "    unchanged = all(p.read_bytes() == raws[p.name] for p in paths)\n",
            "    unchanged = True\n",
        ),
    ),
)
def case_check_after_a_changed_tr_string_exits_1_naming_both_keys(
    tools: Tools, work: Path
) -> None:
    """A renamed ``tr()`` string: exit 1, the added and the removed key named.

    SC-L10N-BUILD-007-1 (the freeze proof). Adding a string and removing one
    are each enough on their own to exit 1, and in no case does ``--check``
    write a tracked catalogue.
    """
    world = build_world(work / "renamed")
    originals = world.catalogue_bytes()
    world.write_source(renamed("Open", "Open file"))
    run = invoke(tools, world, "--check", "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    payload = report(run)
    assert payload["ok"] is False
    assert payload["tracked_catalogues_unchanged"] is True
    for record in payload["catalogues"]:
        assert record["added"] == [key("Open file")]
        assert record["removed"] == [key("Open")]
    assert world.catalogue_bytes() == originals
    text = invoke(tools, world, "--check")
    assert text.returncode == 1, (text.stdout, text.stderr)
    assert "added keys (1):" in text.stdout and "'Open file'" in text.stdout
    assert "removed keys (1):" in text.stdout and "'Open'" in text.stdout
    assert "verdict: FAILED" in text.stdout
    assert world.catalogue_bytes() == originals

    added = build_world(work / "added")
    originals = added.catalogue_bytes()
    added.write_source(SOURCE + '        self.tr("Print")\n')
    run = invoke(tools, added, "--check", "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    for record in report(run)["catalogues"]:
        assert record["added"] == [key("Print")] and record["removed"] == []
    assert added.catalogue_bytes() == originals

    removed = build_world(work / "removed")
    originals = removed.catalogue_bytes()
    removed.write_source(SOURCE.replace('        self.tr("Save")\n', ""))
    run = invoke(tools, removed, "--check", "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    for record in report(run)["catalogues"]:
        assert record["removed"] == [key("Save")] and record["added"] == []
    assert removed.catalogue_bytes() == originals


# --------------------------------------------------------------------------- #
# Nothing examined, usage and tool errors, the backup.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "zero-examined-passes",
        ex(
            "    ok = examined > 0 and all(r.ok for r in results)\n",
            "    ok = all(r.ok for r in results)\n",
        ),
    ),
    mutant(
        "zero-live-keys-pass-check",
        ex(
            "    ok = examined > 0 and not live_empty and identical\n",
            "    ok = identical\n",
        ),
    ),
    mutant(
        "no-catalogue-passes",
        ex(
            "        if not paths:\n"
            '            print("FAILED: no catalogue examined (zero found)", '
            "file=sys.stderr)\n"
            "            return EXIT_FINDINGS\n",
            "        if not paths:\n            return EXIT_OK\n",
        ),
    ),
)
def case_a_run_that_examined_nothing_exits_1(tools: Tools, work: Path) -> None:
    """No catalogue, or catalogues with no live message, is a failure."""
    nothing = build_world(work / "none")
    for path in nothing.catalogue_paths():
        path.unlink()
    run = invoke(tools, nothing)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert "no catalogue examined" in run.stderr

    for mode in ([], ["--check"]):
        empty = build_world(work / f"empty{len(mode)}", english=[], spanish=[])
        empty.write_source('class Panel:\n    """Nothing to translate."""\n')
        originals = empty.catalogue_bytes()
        run = invoke(tools, empty, *mode, "--json")
        assert run.returncode == 1, (mode, run.stdout, run.stderr)
        payload = report(run)
        assert payload["ok"] is False
        assert payload["keys_examined"] == 0
        assert "verdict: FAILED" in run.stderr
        assert empty.catalogue_bytes() == originals
        if mode:
            assert sorted(payload["zero_examined"]) == [
                "pixelart_en.ts",
                "pixelart_es.ts",
            ]
            assert "had zero live keys to compare" in run.stderr


@REGISTRY.regression(
    mutant("locales-ignored", ex("    if locales:\n", "    if False:\n")),
    mutant(
        "unknown-locale-passes",
        ex("        if missing:\n", "        if False:\n"),
    ),
    mutant(
        "missing-source-passes",
        ex("        if not (root / args.source).is_dir():\n", "        if False:\n"),
    ),
    mutant(
        "missing-tool-passes",
        ex("    if found is None:\n", "    if False:\n"),
    ),
    mutant(
        "malformed-catalogue-passes",
        ex(
            '        raise ExtractError(f"{name}: not well-formed XML '
            '({exc})") from exc\n',
            "        return Snapshot(name, '', {}, 0)\n",
        ),
    ),
)
def case_an_unusable_input_or_tool_exits_2(tools: Tools, work: Path) -> None:
    """A missing locale, source, tool or a malformed catalogue exits 2."""
    only = build_world(work / "only")
    run = invoke(tools, only, "--locales", "es", "--json")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert [c["catalogue"] for c in report(run)["catalogues"]] == ["pixelart_es.ts"]
    calls = only.calls()
    assert len(calls) == 1, calls
    (call,) = calls
    assert posix(call["argv"])[-1] == "pixelart_creator/i18n/pixelart_es.ts"
    assert not [a for a in call["argv"] if a.endswith("pixelart_en.ts")]

    unknown = build_world(work / "unknown")
    run = invoke(tools, unknown, "--locales", "fr")
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "catalogue not found" in run.stderr
    assert unknown.calls() == []

    nosource = build_world(work / "nosource")
    run = invoke(tools, nosource, "--source", "elsewhere")
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "source folder not found" in run.stderr

    notool = build_world(work / "notool")
    run = invoke(tools, notool, lupdate=str(work / "no-such-lupdate"))
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "could not run" in run.stderr

    malformed = build_world(work / "malformed")
    path = malformed.catalogue_paths()[0]
    path.write_bytes(b"<TS><context>")
    run = invoke(tools, malformed)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "not well-formed XML" in run.stderr
    assert malformed.calls() == []


@REGISTRY.regression(
    mutant(
        "backup-always-kept",
        ex(
            "    elif not args.keep_backup and not args.backup_dir:\n",
            "    elif False:\n",
        ),
    ),
    mutant(
        "backup-always-removed",
        ex(
            "    elif not args.keep_backup and not args.backup_dir:\n",
            "    elif True:\n",
        ),
    ),
    mutant(
        "backup-dir-ignored",
        ex(
            "        args.backup_dir or "
            'tempfile.mkdtemp(prefix="i18n_extract_backup_")\n',
            '        tempfile.mkdtemp(prefix="i18n_extract_backup_")\n',
        ),
    ),
)
def case_the_backup_is_kept_when_asked_for_or_when_the_run_fails(
    tools: Tools, work: Path
) -> None:
    """A good run removes its backup unless told to keep it; a failed run keeps it."""
    plain = build_world(work / "plain")
    run = invoke(tools, plain)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert plain.leftovers("i18n_extract_backup_") == []

    kept = build_world(work / "kept")
    originals = kept.catalogue_bytes()
    run = invoke(tools, kept, "--keep-backup", "--json")
    assert run.returncode == 0, (run.stdout, run.stderr)
    folder = Path(report(run)["backup"])
    assert folder.parent.resolve() == kept.temp.resolve()
    assert folder.is_dir()
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == originals

    chosen = build_world(work / "chosen")
    originals = chosen.catalogue_bytes()
    target = work / "chosen-backup"
    run = invoke(tools, chosen, "--backup-dir", str(target))
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert target.is_dir()
    assert {p.name: p.read_bytes() for p in target.iterdir()} == originals
    assert chosen.leftovers("i18n_extract_backup_") == []

    failed = build_world(work / "failed")
    originals = failed.catalogue_bytes()
    failed.write_source(renamed("Open", "Open file"))
    run = invoke(tools, failed, "--json")
    assert run.returncode == 1, (run.stdout, run.stderr)
    folder = Path(report(run)["backup"])
    assert folder.parent.resolve() == failed.temp.resolve()
    assert folder.is_dir()
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == originals


# --------------------------------------------------------------------------- #
# The generic tests: every case against the real script and its broken copies.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", REGISTRY.real())
def test_case_holds_on_the_real_script(case: Case, tmp_path: Path) -> None:
    """The clean fixture exits as the contract says and the broken one fails."""
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


def test_an_unmodified_copy_behaves_like_the_real_script(tmp_path: Path) -> None:
    """The broken-copy machinery is neutral: a copy with no edit passes the cases."""
    tools = make_broken(tmp_path / "scripts", Mutant("unmodified", ()))
    for case in REGISTRY.cases[:3]:
        work = tmp_path / case.name
        work.mkdir()
        case.run(tools, work)


def test_the_stand_in_tool_follows_the_extensions_trap(tmp_path: Path) -> None:
    """Control: the stand-in empties the catalogues when the flag is misplaced.

    Without this the mutants that misplace the flag could pass for the wrong
    reason; here the stand-in is run directly with the wrong order and with
    the right one on the same scratch root.
    """
    world = build_world(tmp_path / "world")
    target = "pixelart_creator/i18n/pixelart_es.ts"
    wrong = [
        str(world.launcher),
        "pixelart_creator",
        "-extensions",
        "py",
        "-ts",
        target,
    ]
    done = subprocess.run(wrong, cwd=str(world.root), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    emptied = (world.root / target).read_text(encoding="utf-8")
    assert '<translation type="vanished">Abrir</translation>' in emptied
    assert "<translation>Abrir</translation>" not in emptied
    fresh = build_world(tmp_path / "fresh")
    right = [
        str(fresh.launcher),
        "-extensions",
        "py",
        "pixelart_creator",
        "-ts",
        target,
    ]
    done = subprocess.run(right, cwd=str(fresh.root), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    restored = (fresh.root / target).read_text(encoding="utf-8")
    assert "<translation>Abrir</translation>" in restored
