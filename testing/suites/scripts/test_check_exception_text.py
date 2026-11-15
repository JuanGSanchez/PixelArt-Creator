"""Contract tests for ``scripts/check_exception_text.py`` (ADR-0047).

Contract asserted here, taken from the script's own header::

    check_exception_text.py [paths ...] [--root pixelart_creator/ui] [--json]
    EXIT CODES: 0 clean (a non-zero number of sites, none tainted); 1 any
        tainted site, or nothing examined, or no site found in the files
        examined; 2 usage error, a missing root or path, a file that cannot be
        parsed.

The check reads the interface layer as source and reports every place where the
text of a caught exception can reach a surface the user reads, by channel:
a message box, a translated template, a worker signal, text stored for later
display, and a direct surface (a status bar, label, tooltip or text view). It
exits 1 on a site whose shown text takes a value from the exception.

Method. Every case builds a small ``ui/`` tree of its own under a scratch
folder (made from ``tmp_path`` and removed after each test) and runs the script
from that folder with ``--root ui``, so the names in the report are
``ui/<module>.py``. The tracked interface code is never read. The tree is a
clean BASELINE (modules whose handlers show only the failure sentences: one or
two sites in every channel) plus, for a planted row, one module ``planted.py``
holding the site under test. Each planted row is judged on the JSON report (the
file, the line and the channel of the one tainted site; the count per channel;
the total) and on the printed report, and is paired with the same site written
from the failure sentences, which must be counted clean and exit 0.

Each REGRESSION CASE is registered with MUTANTS: copies of the script, made under
``tmp_path``, with one guarded line altered so that the rule the case defends is
gone. The module's generic tests run every case against the real script (it
must hold) and against each broken copy (it must raise an ``AssertionError``).
The registry and the edit types are imported from the sibling module for
``check_catalogues.py``.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from .conftest import SCRIPTS_DIR, ScriptRun
from .test_check_catalogues import Case, Edit, Mutant, Registry, Tools, mutant

SCRIPT = "check_exception_text.py"
REGISTRY = Registry()

BOX = "message box"
TEMPLATE = "translated template"
SIGNAL = "worker signal"
STORED = "stored for later display"
DIRECT = "direct surface"
CHANNELS = (BOX, TEMPLATE, SIGNAL, STORED, DIRECT)

PLANTED = "planted.py"
PLANTED_REL = f"ui/{PLANTED}"
OCTOBER_LINE = "October figure: 72 (a record, not compared)"


#: A backslash followed by the letter "n": how the script's own source spells a
#: newline inside a string literal. It is assembled from two literals on purpose.
#: Written as one literal next to the words around it, the pair reads as a path
#: with a backslash separator to scripts/path_portability_check.py, which is right
#: about literals that name paths and wrong about this one, which names source text.
SOURCE_NEWLINE_ESCAPE = "\\" + "n"


def ex(old: str, new: str) -> Edit:
    """Build an edit of ``check_exception_text.py``."""
    return Edit(SCRIPT, old, new)


def make_broken(folder: Path, broken: Mutant) -> Tools:
    """Copy the script into ``folder`` and apply ``broken``'s edits.

    Files are read and written as bytes. An anchor that is not found exactly
    once, or an edit that leaves a script that does not compile, raises: a
    control must fail for the reason it names and for no other.
    """
    folder.mkdir(parents=True)
    shutil.copyfile(SCRIPTS_DIR / SCRIPT, folder / SCRIPT)
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


@pytest.fixture
def work(tmp_path: Path):
    """A scratch folder under the temp root, removed when the test ends."""
    folder = tmp_path / "work"
    folder.mkdir()
    yield folder
    shutil.rmtree(tmp_path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# The baseline tree: every handler shows a sentence, never the exception.
# --------------------------------------------------------------------------- #
MAIN_VIEW = """\
from PySide6.QtWidgets import QMessageBox

from pixelart_creator.ui.failure_messages import failure_kind, failure_text


class MainView:
    def open_file(self, path):
        try:
            self.load(path)
        except OSError as exc:
            QMessageBox.warning(self, self.tr("Open"), failure_text(failure_kind(exc)))

    def export_to(self, name):
        try:
            self.write(name)
        except ValueError as exc:
            kind = failure_kind(exc)
            text = self.tr("Could not export {name}: {why}").format(
                name=name, why=failure_text(kind)
            )
            QMessageBox.critical(self, self.tr("Export"), text)

    def refresh(self):
        try:
            self.reload()
        except RuntimeError as exc:
            self.statusBar().showMessage(failure_text(failure_kind(exc)))
"""

WORKER = """\
from PySide6.QtCore import QThread, Signal

from pixelart_creator.ui.failure_messages import failure_kind


class Worker(QThread):
    failed = Signal(str)

    def run(self):
        try:
            self.work()
        except Exception as exc:
            self.failed.emit(failure_kind(exc).value)
"""

PAGE = """\
from pixelart_creator.ui.failure_messages import failure_kind, failure_text


class Page:
    def load(self):
        try:
            self.read()
        except OSError as exc:
            self.failure = failure_kind(exc)

    def show(self):
        self.label.setText(failure_text(self.failure))
"""

PANEL = """\
from PySide6.QtWidgets import QMessageBox

from pixelart_creator.ui.failure_messages import failure_kind, failure_text


class Panel:
    def delete(self):
        try:
            self.remove()
        except PermissionError as exc:
            self._warn(failure_text(failure_kind(exc)))

    def _warn(self, text):
        QMessageBox.warning(self, self.tr("Delete"), text)
"""

BASELINE = {
    "main_view.py": MAIN_VIEW,
    "worker.py": WORKER,
    "page.py": PAGE,
    "panel.py": PANEL,
}
#: The sites of the baseline by channel; each of its six handlers holds one.
BASELINE_SITES = {BOX: 2, TEMPLATE: 1, SIGNAL: 1, STORED: 1, DIRECT: 1}
BASELINE_HANDLERS = 6


def write_ui(folder: Path, files: dict[str, str]) -> Path:
    """Write ``files`` (name -> source, as UTF-8 bytes) into ``folder/ui``."""
    ui = folder / "ui"
    ui.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        (ui / name).write_bytes(source.encode("utf-8"))
    return ui


def run_text(tools: Tools, folder: Path, *args: str) -> ScriptRun:
    """Run the check over ``ui`` of ``folder`` and return the printed report."""
    return tools.run(SCRIPT, ["--root", "ui", *args], folder)


def run_json(tools: Tools, folder: Path, *args: str) -> tuple[ScriptRun, dict]:
    """Run the check with ``--json`` and parse the report."""
    run = run_text(tools, folder, *args, "--json")
    try:
        report = json.loads(run.stdout)
    except ValueError:
        raise AssertionError(
            f"stdout is not JSON: exit {run.returncode}, stdout "
            f"{run.stdout[:300]!r}, stderr {run.stderr[:300]!r}"
        ) from None
    assert isinstance(report, dict), report
    return run, report


def header_of(stdout: str) -> tuple[int, ...]:
    """Return the five denominators of the first printed line.

    Files examined, handlers examined, handlers with a name, sites found and
    the handlers that hold a site.
    """
    first = stdout.splitlines()[0]
    found = re.fullmatch(
        r"check_exception_text: files examined (\d+), handlers examined (\d+) "
        r"\((\d+) named\), sites found (\d+) in (\d+) handlers",
        first,
    )
    assert found, first
    return tuple(int(group) for group in found.groups())


def table_of(stdout: str) -> dict[str, tuple[int, int]]:
    """Return ``{channel: (sites, tainted)}`` from the printed table, total included."""
    table = {}
    names = "|".join([*CHANNELS, "total"])
    for line in stdout.splitlines():
        found = re.fullmatch(rf"({names})\s+(\d+)\s+(\d+)", line)
        if found:
            table[found.group(1)] = (int(found.group(2)), int(found.group(3)))
    return table


def site_line(source: str, needle: str) -> int:
    """Return the 1-based line of the one line of ``source`` that holds ``needle``."""
    lines = [n for n, text in enumerate(source.splitlines(), 1) if needle in text]
    assert len(lines) == 1, (needle, lines)
    return lines[0]


# --------------------------------------------------------------------------- #
# Planted sites. A plant is the body of an ``except OSError as exc`` handler, an
# optional continuation of the method, and optional methods of the class.
# --------------------------------------------------------------------------- #
PLANT_HEAD = """\
from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import QMessageBox

from pixelart_creator.ui.failure_messages import failure_kind, failure_text


class Planted:
    failed = Signal(str)

    def run(self):
        try:
            self.work()
        except OSError as exc:
"""


class Plant(NamedTuple):
    """One planted site and the one line of it that the report must name."""

    name: str
    lines: tuple[str, ...]
    needle: str
    tail: str = ""
    after: tuple[str, ...] = ()


def planted_source(plant: Plant) -> str:
    """Return the source of ``planted.py`` for ``plant``."""
    handler = "".join(f"            {line}\n" for line in plant.lines)
    after = "".join(f"        {line}\n" for line in plant.after)
    return PLANT_HEAD + handler + after + plant.tail


BOX_PLANTS = [
    Plant(
        "str",
        ('QMessageBox.warning(self, "Failed", str(exc))',),
        'QMessageBox.warning(self, "Failed", str(exc))',
    ),
    Plant(
        "f-string",
        ('QMessageBox.critical(self, "Failed", f"Could not open: {exc}")',),
        "QMessageBox.critical(",
    ),
    Plant(
        "repr",
        ('QMessageBox.information(self, "Failed", repr(exc))',),
        "QMessageBox.information(",
    ),
    Plant(
        "args",
        ('QMessageBox.warning(self, "Failed", exc.args[0])',),
        "QMessageBox.warning(",
    ),
    Plant(
        "through a local",
        ("text = str(exc)", 'QMessageBox.warning(self, "Failed", text)'),
        'QMessageBox.warning(self, "Failed", text)',
    ),
    Plant(
        "through a helper of the module",
        ("self.warn(str(exc))",),
        "self.warn(str(exc))",
        tail=(
            "\n    def warn(self, text):\n"
            '        QMessageBox.warning(self, "Failed", text)\n'
        ),
    ),
    Plant(
        "text of a box object",
        ("box = QMessageBox(self)", "box.setText(str(exc))", "box.exec()"),
        "box.setText(str(exc))",
    ),
]
BOX_CLEAN = [
    Plant(
        "sentence",
        ('QMessageBox.warning(self, "Failed", failure_text(failure_kind(exc)))',),
        "QMessageBox.warning(",
    ),
    Plant(
        "helper given a sentence",
        ("self.warn(failure_text(failure_kind(exc)))",),
        "self.warn(",
        tail=(
            "\n    def warn(self, text):\n"
            '        QMessageBox.warning(self, "Failed", text)\n'
        ),
    ),
]

SHOW_TEMPLATE = 'QMessageBox.warning(self, self.tr("Open"), text)'
TEMPLATE_PLANTS = [
    Plant(
        "format",
        (
            'text = self.tr("Could not open: {why}").format(why=str(exc))',
            SHOW_TEMPLATE,
        ),
        ".format(why=str(exc))",
    ),
    Plant(
        "arg",
        ('text = self.tr("Could not open: %1").arg(str(exc))', SHOW_TEMPLATE),
        ".arg(str(exc))",
    ),
    Plant(
        "replace of a translated text",
        (
            "text = QCoreApplication.translate(",
            '    "Open", "Could not open: %1"',
            ').replace("%1", str(exc))',
            SHOW_TEMPLATE,
        ),
        "text = QCoreApplication.translate(",
    ),
    Plant(
        "through a local",
        (
            "why = str(exc)",
            'text = self.tr("Could not open: %1").arg(why)',
            SHOW_TEMPLATE,
        ),
        ".arg(why)",
    ),
    Plant(
        "percent operator",
        ('text = self.tr("Could not open: %s") % str(exc)', SHOW_TEMPLATE),
        "% str(exc)",
    ),
]
TEMPLATE_CLEAN = [
    Plant(
        "sentence",
        (
            "kind = failure_kind(exc)",
            'text = self.tr("Failed: {why}").format(why=failure_text(kind))',
            SHOW_TEMPLATE,
        ),
        ".format(why=failure_text(kind))",
    ),
]

SIGNAL_PLANTS = [
    Plant(
        "type name and text",
        ('self.failed.emit(f"{type(exc).__name__}: {exc}")',),
        "self.failed.emit(",
    ),
    Plant(
        "type name alone",
        ("self.failed.emit(type(exc).__name__)",),
        "self.failed.emit(",
    ),
    Plant(
        "type name through a local",
        ("label = type(exc).__name__", "self.failed.emit(label)"),
        "self.failed.emit(label)",
    ),
    Plant("str", ("self.failed.emit(str(exc))",), "self.failed.emit("),
    Plant(
        "through a helper of the module",
        ("self.report(str(exc))",),
        "self.report(str(exc))",
        tail="\n    def report(self, text):\n        self.failed.emit(text)\n",
    ),
]
SIGNAL_CLEAN = [
    Plant(
        "kind",
        ("self.failed.emit(failure_kind(exc).value)",),
        "self.failed.emit(",
    ),
]

SHOW_ATTRIBUTE = "\n    def show(self):\n        self.label.setText(self.last_error)\n"
STORED_PLANTS = [
    Plant(
        "attribute read by a setter",
        ("self.last_error = str(exc)",),
        "self.last_error = str(exc)",
        tail=SHOW_ATTRIBUTE,
    ),
    Plant(
        "container read by a setter",
        ("self.errors.append(str(exc))",),
        "self.errors.append(str(exc))",
        tail=(
            "\n    def show(self):\n"
            '        self.label.setText(", ".join(self.errors))\n'
        ),
    ),
    Plant(
        "local read after the handler",
        ("message = str(exc)",),
        "message = str(exc)",
        after=("self.label.setText(message)",),
    ),
    Plant("returned to the caller", ("return str(exc)",), "return str(exc)"),
]
STORED_CLEAN = [
    Plant(
        "kind read by a sentence",
        ("self.last_error = failure_kind(exc)",),
        "self.last_error = failure_kind(exc)",
        tail=(
            "\n    def show(self):\n"
            "        self.label.setText(failure_text(self.last_error))\n"
        ),
    ),
]

DIRECT_PLANTS = [
    Plant(
        "status bar",
        ('self.statusBar().showMessage(f"failed: {exc}")',),
        "showMessage(",
    ),
    Plant("label", ("self.label.setText(str(exc))",), "self.label.setText("),
    Plant("tooltip", ("self.setToolTip(repr(exc))",), "self.setToolTip("),
    Plant(
        "through a helper of the module",
        ("self.show_text(str(exc))",),
        "self.show_text(str(exc))",
        tail="\n    def show_text(self, text):\n        self.label.setText(text)\n",
    ),
]
DIRECT_CLEAN = [
    Plant(
        "sentence",
        ("self.statusBar().showMessage(failure_text(failure_kind(exc)))",),
        "showMessage(",
    ),
]


def check_plant(
    tools: Tools, folder: Path, plant: Plant, channel: str, tainted: bool
) -> None:
    """Plant one site on the baseline and judge the reports against the plan.

    A tainted plant exits 1 with exactly one tainted site, in the named channel,
    at the line of ``plant.needle`` of ``planted.py``; a clean twin exits 0 with
    the same site counted clean. In both the baseline's sites are all still
    there, each channel counts its own and no other.
    """
    source = planted_source(plant)
    write_ui(folder, {**BASELINE, PLANTED: source})
    line = site_line(source, plant.needle)
    run, report = run_json(tools, folder)
    assert run.returncode == (1 if tainted else 0), (run.stdout, run.stderr)
    wanted = dict(BASELINE_SITES, **{channel: BASELINE_SITES[channel] + 1})
    assert {k: v["sites"] for k, v in report["by_channel"].items()} == wanted
    bad = {name: int(tainted and name == channel) for name in CHANNELS}
    assert {k: v["tainted"] for k, v in report["by_channel"].items()} == bad
    assert report["sites_total"] == sum(wanted.values()), report["sites_total"]
    assert report["tainted_total"] == int(tainted), report["tainted_total"]
    assert report["files_examined"] == len(BASELINE) + 1
    mine = [s for s in report["sites"] if s["file"] == PLANTED_REL]
    assert len(mine) == 1, report["sites"]
    site = mine[0]
    assert (site["line"], site["channel"], site["tainted"]) == (line, channel, tainted)
    assert not [s for s in report["sites"] if s["file"] != PLANTED_REL and s["tainted"]]
    assert report["tainted_by_file"] == ({PLANTED_REL: [site]} if tainted else {})
    text = run_text(tools, folder)
    assert text.returncode == run.returncode, (text.stdout, text.stderr)
    shown = "TAINTED" if tainted else "clean"
    place = rf"^  {re.escape(PLANTED_REL)}:{line} \[{channel}\] {shown} "
    assert re.search(place, text.stdout, re.MULTILINE), text.stdout
    if tainted:
        total = report["sites_total"]
        assert f"1 tainted site(s) of {total}" in text.stderr, text.stderr
    else:
        assert text.stderr == "", text.stderr
    assert table_of(text.stdout)[channel] == (wanted[channel], int(tainted))


def check_plants(
    tools: Tools, work: Path, channel: str, plants: list[Plant], tainted: bool
) -> None:
    """Run :func:`check_plant` over each plant, naming the plant that fails."""
    kind = "tainted" if tainted else "clean"
    for number, plant in enumerate(plants):
        try:
            check_plant(tools, work / f"{kind}-{number}", plant, channel, tainted)
        except AssertionError as error:
            raise AssertionError(f"{kind} plant {plant.name!r}: {error}") from error


#: Edits that make a broken copy treat a whole class of values as clean.
TAINT_EXIT_IGNORED = mutant(
    "tainted-site-does-not-fail",
    ex('    if rep["tainted_total"]:\n', "    if False:\n"),
)
FSTRINGS_NEVER_TAINTED = mutant(
    "f-strings-never-tainted",
    ex(
        "        if node is None:\n            return False\n",
        "        if node is None or isinstance(node, ast.JoinedStr):\n"
        "            return False\n",
    ),
)
SENTENCES_NOT_SANITISED = mutant(
    "failure-sentences-not-sanitised",
    ex(
        'SANITISERS = {\n    "failure_kind",\n    "failure_text",\n',
        "SANITISERS = {\n",
    ),
)


# --------------------------------------------------------------------------- #
# Nothing planted: the baseline.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    SENTENCES_NOT_SANITISED,
    mutant(
        "october-figure-not-printed",
        ex(
            '    w("October figure: %d (a record, not compared)\\n" % '
            'rep["october_figure"])\n',
            '    w("")\n',
        ),
    ),
    mutant(
        "october-figure-changed", ex("OCTOBER_FIGURE = 72\n", "OCTOBER_FIGURE = 71\n")
    ),
    mutant(
        "message-box-calls-not-sites",
        ex(
            'BOX_STATICS = {"information", ', 'BOX_STATICS = set() and {"information", '
        ),
    ),
    mutant(
        "templates-not-sites",
        ex("TEMPLATE_METHODS = {", "TEMPLATE_METHODS = set() and {"),
    ),
    mutant(
        "emit-not-a-site",
        ex('            if name == "emit" and args:\n', "            if False:\n"),
    ),
    mutant(
        "stored-text-not-a-site",
        ex(
            "                if not mention.tainted(value):\n",
            "                if True:\n",
        ),
    ),
    mutant(
        "direct-setters-not-sites",
        ex("            if name in DIRECT_SETTERS:\n", "            if False:\n"),
    ),
    mutant(
        "helper-sites-not-followed",
        ex("        helper = self._resolve(call)\n", "        helper = None\n"),
    ),
)
def case_a_tree_whose_handlers_show_no_exception_text_exits_0_with_a_non_zero_total(
    tools: Tools, work: Path
) -> None:
    """Nothing planted: exit 0, the sites counted per channel, the record printed.

    The baseline has six handlers in four modules, each with one site: two in
    message boxes (one through a helper of the module), one translated
    template, one worker signal, one stored value and one direct surface. All
    are counted and none is tainted. The first printed line carries the
    denominators (files, handlers, named handlers, sites, handlers with a
    site), the table carries each channel's sites and tainted sites and the
    total, and the October figure, 72, is printed beside it as a record.
    """
    write_ui(work, BASELINE)
    run, report = run_json(tools, work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert report["sites_total"] == 6 and report["tainted_total"] == 0
    assert {k: v["sites"] for k, v in report["by_channel"].items()} == BASELINE_SITES
    assert all(v["tainted"] == 0 for v in report["by_channel"].values())
    assert all(s["tainted"] is False for s in report["sites"]), report["sites"]
    assert report["october_figure"] == 72 and report["tainted_by_file"] == {}
    assert report["files_examined"] == 4
    assert report["handlers_examined"] == BASELINE_HANDLERS
    text = run_text(tools, work)
    assert text.returncode == 0 and text.stderr == "", (text.stdout, text.stderr)
    handlers = BASELINE_HANDLERS
    assert header_of(text.stdout) == (4, handlers, handlers, 6, handlers)
    table = table_of(text.stdout)
    assert table == {
        BOX: (2, 0),
        TEMPLATE: (1, 0),
        SIGNAL: (1, 0),
        STORED: (1, 0),
        DIRECT: (1, 0),
        "total": (6, 0),
    }, table
    assert OCTOBER_LINE in text.stdout.splitlines(), text.stdout
    assert "TAINTED" not in text.stdout, text.stdout


# --------------------------------------------------------------------------- #
# A message box whose body is the exception's text.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    TAINT_EXIT_IGNORED,
    FSTRINGS_NEVER_TAINTED,
    SENTENCES_NOT_SANITISED,
    mutant(
        "message-box-calls-not-sites",
        ex(
            'BOX_STATICS = {"information", ', 'BOX_STATICS = set() and {"information", '
        ),
    ),
    mutant(
        "box-object-text-not-a-site",
        ex("BOX_INSTANCE_TEXT = {", "BOX_INSTANCE_TEXT = set() and {"),
    ),
    mutant(
        "helper-sites-not-followed",
        ex("        helper = self._resolve(call)\n", "        helper = None\n"),
    ),
)
def case_a_message_box_planted_with_the_exception_text_fails_naming_file_line_channel(
    tools: Tools, work: Path
) -> None:
    """``QMessageBox`` text taken from ``exc`` exits 1: file, line, ``message box``.

    The body is ``str(exc)``, an f-string holding it, ``repr(exc)``, an
    attribute of it, a local assigned from it, a call of a helper of the module
    that makes the box, or the text of a ``QMessageBox`` object. The same
    boxes written from the failure sentences are counted clean and exit 0.
    """
    check_plants(tools, work, BOX, BOX_PLANTS, tainted=True)
    check_plants(tools, work, BOX, BOX_CLEAN, tainted=False)


# --------------------------------------------------------------------------- #
# The exception's text in a translated template's placeholder.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    TAINT_EXIT_IGNORED,
    SENTENCES_NOT_SANITISED,
    mutant(
        "templates-not-sites",
        ex("TEMPLATE_METHODS = {", "TEMPLATE_METHODS = set() and {"),
    ),
    mutant(
        "translation-calls-unknown",
        ex('TR_NAMES = {"tr", ', 'TR_NAMES = set() and {"tr", '),
    ),
    mutant(
        "percent-operator-not-a-template",
        ex(
            "        if isinstance(node, ast.BinOp) and "
            "isinstance(node.op, ast.Mod):\n",
            "        if False:\n",
        ),
    ),
)
def case_a_template_planted_with_the_exception_text_fails_naming_file_line_channel(
    tools: Tools, work: Path
) -> None:
    """``str(exc)`` in a template exits 1: file, line, ``translated template``.

    The placeholder is filled through ``.format``, ``.arg``, ``.replace`` of a
    ``translate()`` result, a local assigned from the exception, or the ``%``
    operator. The box that shows the filled template is not counted again. The
    same template filled from the failure sentences is counted clean.
    """
    check_plants(tools, work, TEMPLATE, TEMPLATE_PLANTS, tainted=True)
    check_plants(tools, work, TEMPLATE, TEMPLATE_CLEAN, tainted=False)


# --------------------------------------------------------------------------- #
# A worker signal that emits the exception's text or its type name.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    TAINT_EXIT_IGNORED,
    FSTRINGS_NEVER_TAINTED,
    SENTENCES_NOT_SANITISED,
    mutant(
        "emit-not-a-site",
        ex('            if name == "emit" and args:\n', "            if False:\n"),
    ),
    mutant(
        "type-name-ignored",
        ex(
            "            if self.sanitise and call_name(node.func) in SANITISERS:\n",
            "            if self.sanitise and call_name(node.func) in "
            'SANITISERS | {"type"}:\n',
        ),
    ),
    mutant(
        "helper-sites-not-followed",
        ex("        helper = self._resolve(call)\n", "        helper = None\n"),
    ),
)
def case_a_worker_signal_planted_with_the_exception_text_fails_naming_file_line_channel(
    tools: Tools, work: Path
) -> None:
    """A signal that emits ``exc`` or its type name exits 1 as ``worker signal``.

    The emitted value is ``f"{type(exc).__name__}: {exc}"``, ``type(exc).__name__``
    alone (the form that only a check that follows the type name still sees),
    that name through a local, ``str(exc)``, or a helper of the module that
    emits what it is given. A signal that emits ``failure_kind(exc).value`` is
    counted clean.
    """
    check_plants(tools, work, SIGNAL, SIGNAL_PLANTS, tainted=True)
    check_plants(tools, work, SIGNAL, SIGNAL_CLEAN, tainted=False)


# --------------------------------------------------------------------------- #
# Text stored for later display.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    TAINT_EXIT_IGNORED,
    SENTENCES_NOT_SANITISED,
    mutant(
        "stored-text-not-a-site",
        ex(
            "                if not mention.tainted(value):\n",
            "                if True:\n",
        ),
    ),
    mutant(
        "returned-text-not-a-site",
        ex(
            "                if ctx.tainted(node.value):\n",
            "                if False:\n",
        ),
    ),
)
def case_text_stored_with_the_exception_text_fails_naming_file_line_channel(
    tools: Tools, work: Path
) -> None:
    """Text from ``exc`` kept for a surface exits 1 as ``stored for later display``.

    An attribute or a container assigned in the handler and read by a setter
    elsewhere in the module, a local read after the handler, and a value the
    handler returns to its caller. An attribute that holds only the failure
    kind is counted clean.
    """
    check_plants(tools, work, STORED, STORED_PLANTS, tainted=True)
    check_plants(tools, work, STORED, STORED_CLEAN, tainted=False)


# --------------------------------------------------------------------------- #
# A direct surface: a status bar, a label, a tooltip.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    TAINT_EXIT_IGNORED,
    FSTRINGS_NEVER_TAINTED,
    SENTENCES_NOT_SANITISED,
    mutant(
        "direct-setters-not-sites",
        ex("            if name in DIRECT_SETTERS:\n", "            if False:\n"),
    ),
    mutant(
        "helper-sites-not-followed",
        ex("        helper = self._resolve(call)\n", "        helper = None\n"),
    ),
)
def case_a_direct_surface_planted_with_the_exception_text_fails_naming_file_and_line(
    tools: Tools, work: Path
) -> None:
    """A status bar, label or tooltip set from ``exc`` exits 1 as ``direct surface``.

    The channel is outside the four of the scenario and is kept, so that a
    failure shown without a message box, a template, a signal or a stored
    value is not invisible. ``showMessage`` of an f-string, ``setText`` of
    ``str(exc)``, ``setToolTip`` of ``repr(exc)`` and a helper of the module that
    sets what it is given; the same status bar message made from the failure
    sentences is counted clean.
    """
    check_plants(tools, work, DIRECT, DIRECT_PLANTS, tainted=True)
    check_plants(tools, work, DIRECT, DIRECT_CLEAN, tainted=False)


# --------------------------------------------------------------------------- #
# An empty tree, and a tree with no site.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant("no-file-passes", ex("    if not files:\n", "    if False:\n")),
    mutant(
        "empty-tree-unnamed-on-stdout",
        ex("files examined 0, nothing examined", "files examined 0"),
    ),
    mutant(
        "empty-tree-unnamed-on-stderr",
        ex("nothing examined (no .py file)", "no python file"),
    ),
    mutant(
        "october-figure-missing-on-an-empty-tree",
        ex(
            '            "October figure: %d (a record, not compared)\\n"'
            " % OCTOBER_FIGURE\n",
            '            ""\n',
        ),
    ),
    mutant(
        "no-site-passes", ex('    if rep["sites_total"] == 0:\n', "    if False:\n")
    ),
)
def case_an_empty_tree_or_a_tree_with_no_site_exits_1_saying_nothing_examined(
    tools: Tools, work: Path
) -> None:
    """The interface code replaced by an empty tree exits 1: ``nothing examined``.

    A ``ui`` folder with no Python file in it (only a text file and a cache
    folder) says so on both streams, still prints the October figure, and fails;
    so does a tree whose files hold no site at all, because a total of zero is
    a gate that could not answer.
    """
    ui = work / "empty" / "ui"
    (ui / "__pycache__").mkdir(parents=True)
    (ui / "notes.txt").write_bytes(b"not code\n")
    run = run_text(tools, work / "empty")
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert "nothing examined" in run.stdout and "nothing examined" in run.stderr
    assert OCTOBER_LINE in run.stdout.splitlines(), run.stdout

    write_ui(work / "quiet", {"plain.py": "class Plain:\n    pass\n"})
    run, report = run_json(tools, work / "quiet")
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert report["sites_total"] == 0 and report["files_examined"] == 1
    assert "no site found" in run.stderr, run.stderr
    text = run_text(tools, work / "quiet")
    assert header_of(text.stdout)[3] == 0, text.stdout
    assert OCTOBER_LINE in text.stdout.splitlines(), text.stdout


# --------------------------------------------------------------------------- #
# Explicit files, and the errors that are a usage error.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant("explicit-files-ignored", ex("    if paths:\n", "    if False:\n")),
)
def case_explicit_files_are_examined_instead_of_the_tree(
    tools: Tools, work: Path
) -> None:
    """Files named on the command line are the only ones examined.

    With a planted tainted module in the tree, naming the four clean modules
    exits 0 over four files, and naming the planted one exits 1 over one file.
    """
    source = planted_source(BOX_PLANTS[0])
    ui = write_ui(work, {**BASELINE, PLANTED: source})
    clean = [str(Path("ui") / name) for name in BASELINE]
    run = tools.run(SCRIPT, [*clean, "--json"], work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    report = json.loads(run.stdout)
    assert report["files_examined"] == 4 and report["tainted_total"] == 0, report
    run = tools.run(SCRIPT, [str(Path("ui") / PLANTED), "--json"], work)
    assert run.returncode == 1, (run.stdout, run.stderr)
    report = json.loads(run.stdout)
    assert report["files_examined"] == 1 and report["tainted_total"] == 1, report
    assert ui.is_dir()


@REGISTRY.regression(
    mutant(
        "missing-root-is-a-finding",
        ex(
            "root not found: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % args.root)\n        return 2\n',
            "root not found: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % args.root)\n        return 1\n',
        ),
    ),
    mutant(
        "missing-file-is-a-finding",
        ex(
            "path not found: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % p)\n            return 2\n',
            "path not found: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % p)\n            return 1\n',
        ),
    ),
    mutant(
        "unparsable-file-is-a-finding",
        ex(
            "cannot examine: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % (exc,))\n        return 2\n',
            "cannot examine: %r"
            + SOURCE_NEWLINE_ESCAPE
            + '" % (exc,))\n        return 1\n',
        ),
    ),
)
def case_a_missing_root_or_file_or_a_file_that_does_not_parse_exits_2(
    tools: Tools, work: Path
) -> None:
    """A usage error is exit 2, never 1: the gate could not be asked, not failed."""
    run = tools.run(SCRIPT, ["--root", "nowhere"], work)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "root not found" in run.stderr, run.stderr
    run = tools.run(SCRIPT, ["ui/missing.py"], work)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "path not found" in run.stderr, run.stderr
    write_ui(work, {"broken.py": "def broken(:\n"})
    run = run_text(tools, work)
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "cannot examine" in run.stderr, run.stderr
    write_ui(work, {"broken.py": "class Fixed:\n    pass\n"})
    run = run_text(tools, work)
    assert run.returncode == 1, (run.stdout, run.stderr)


# --------------------------------------------------------------------------- #
# The generic tests: every case against the real script and its broken copies.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", REGISTRY.real())
def test_case_holds_on_the_real_script(case: Case, work: Path) -> None:
    """The clean fixture exits 0 and each planted one exits 1, as the case states."""
    case.run(Tools(SCRIPTS_DIR), work)


@pytest.mark.parametrize(("case", "broken"), REGISTRY.broken())
def test_case_fails_on_a_broken_copy(
    case: Case, broken: Mutant, work: Path, tmp_path: Path
) -> None:
    """With the defended rule removed from a copy of the script the case fails."""
    tools = make_broken(tmp_path / "scripts", broken)
    with pytest.raises(AssertionError):
        case.run(tools, work)


def test_every_case_has_a_broken_copy() -> None:
    """A case registered without a mutant would be a control that controls nothing."""
    assert REGISTRY.cases
    assert [case.name for case in REGISTRY.cases if not case.mutants] == []


def test_an_unmodified_copy_behaves_like_the_real_script(
    work: Path, tmp_path: Path
) -> None:
    """The machinery is neutral: a copy with no edit passes every case."""
    tools = make_broken(tmp_path / "scripts", Mutant("unmodified", ()))
    for number, case in enumerate(REGISTRY.cases):
        folder = work / f"copy-{number}"
        folder.mkdir()
        case.run(tools, folder)
