"""No failure sentence continues on a lead-in's line (REQ-L10N-UI-020).

A lead-in is a source message that shows a failure sentence in a placeholder after
text of its own, such as ``Could not import the asset: %1``. Under REQ-L10N-UI-020
the failure sentence never continues on the lead-in's line: it starts a line of its
own, or it follows a lead-in that ends with a sentence-ending mark of its
catalogue's language (a colon, full-width or not, ends no sentence). The sentence
keeps its catalogue form wherever it is shown.

**The inventory is derived, not listed.** An AST pass over ``pixelart_creator/ui/``
finds every site that puts a failure sentence into a template: a ``failure_text``
result, or the message parameter of a receiver of ``failed``, ``targetFailed``,
``operationFailed`` or ``errorOccurred``, passed to ``.replace``, ``.format`` or the
joining function ``failure_on_own_line`` on a ``tr()`` or ``translate()`` template.
The module carries **no exemption list**. Every derived site must be claimed by a
surface of the driver table, and every surface must claim a site: a surface removed
from the table fails the check, saying it was not examined (SC-L10N-UI-020-4).

**What is driven.** Each surface is driven through the interface's own code for each
of the six sentences, and what the user reads is taken from where the user reads it
(the message box text, the label, the transcript, the list row, the status bar). A
failure of each kind is planted as an exception of the class the site catches,
raised ``from`` a cause of the class that selects the kind. The expected text is
never read from the code under test: a sentence is the English source message of
the requirement, or, for another language, the finished entry of that language's
own ``.ts`` file.

**Languages.** A language whose six sentences or whose lead-ins are still
``unfinished`` is reported "not yet comparable": the case is skipped with that
reason, counted, and never passed. English is examined by its source messages.

**Printed, not asserted.** For each surface, every composition that passes because
the text before the sentence on its line ends with a sentence-ending mark is
printed. Only the status bar's failure-only frame is expected there; any other
surface in that print is a question for the requirements owner, and no check can
tell a label from a sentence, so nothing here asserts it.

Both themes (the suite's ``theme`` fixture applies to every case), offscreen.
Nothing outside ``tmp_path`` is written and no catalogue or product file is changed:
the catalogues are only read.
"""

from __future__ import annotations

import ast
import json
import types
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TypeGuard,
)

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QWidget

import pixelart_creator
import pixelart_creator.ui.dependency_graph_view as dependency_graph_view
import pixelart_creator.ui.export_worker as export_worker
import pixelart_creator.ui.provider_config_dialog as provider_config_dialog
import pixelart_creator.ui.realtime_actions as realtime_actions
import pixelart_creator.ui.script_runner_panel as script_runner_panel
import pixelart_creator.ui.tilemap_io_actions as tilemap_io_actions
import pixelart_creator.ui.user_guide as user_guide
from pixelart_creator.data.guide_content import GuideContentError
from pixelart_creator.data.llm.fake_adapter import FakeLLMAdapter
from pixelart_creator.data.llm.token_store import TokenStoreError
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.assistant import AssistantError
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.convergence import MetadataOp
from pixelart_creator.logic.dependency_graph import DependencyGraphError
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.realtime_apply import RealtimeError, encode_update
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.assistant_dock import Assistant_Dock
from pixelart_creator.ui.assistant_worker import Assistant_Controller
from pixelart_creator.ui.batch_export_panel import Batch_Export_Panel
from pixelart_creator.ui.dependency_graph_view import Dependency_Graph_View
from pixelart_creator.ui.export_worker import ExportTarget
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, LanguageManager
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.provider_config_dialog import Provider_Config_Dialog
from pixelart_creator.ui.realtime_actions import Realtime_Session
from pixelart_creator.ui.script_runner_panel import Script_Runner_Panel
from pixelart_creator.ui.user_guide import User_Guide_Dialog

# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

UI_ROOT = Path(pixelart_creator.__file__).parent / "ui"
CATALOGUES = Path(pixelart_creator.__file__).parent / "i18n"

#: The eight shipped languages, English first.
LANGUAGES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

#: The six failure sentences, as the English source messages of the requirement
#: states them, keyed by the kind of failure each is shown for.
SENTENCES: Dict[str, str] = {
    "TIMEOUT": "The operation timed out.",
    "CONNECTION": "The connection failed.",
    "NOT_FOUND": "The file or folder could not be found.",
    "PERMISSION": "Access to the file or folder was denied.",
    "INVALID_VALUE": "A value was not valid for this operation.",
    "GENERIC": "The operation could not be completed.",
}
SENTENCE_CONTEXT = "Failure_Messages"

#: What the Spanish target-reader review counted, printed beside the derived
#: figures as a record and never compared with them.
REVIEW_INLINE_LEAD_INS = 13
REVIEW_SENTENCES = 6

#: The reason of the real-time requirement, which is not a failure sentence.
REASON_SOURCE = "no real-time transport configured"
REASON_CONTEXT = "Realtime_Client"
REASON_FRAME = ("Main_Window", "Real-time: {msg}")
FAILURE_ONLY_FRAME = ("Main_Window", "Real-time. {msg}")

_ENDING_ASCII = ".!?"
_ENDING_FULL_WIDTH = "。！？．｡"
#: The sentence-ending marks of each language. A colon, full-width or not, is in none.
SENTENCE_ENDINGS: Dict[str, str] = {
    "en": _ENDING_ASCII,
    "es": _ENDING_ASCII,
    "fr": _ENDING_ASCII,
    "de": _ENDING_ASCII,
    "ru": _ENDING_ASCII,
    "zh_CN": _ENDING_ASCII + _ENDING_FULL_WIDTH,
    "ja": _ENDING_ASCII + _ENDING_FULL_WIDTH,
    "ko": _ENDING_ASCII + _ENDING_FULL_WIDTH,
}

#: The marker every planted failure carries.
PLANTED_NAME = "PlantedFailure"


def _read_catalogue(code: str) -> Dict[Tuple[str, str], Optional[str]]:
    """Return ``{(context, source): finished text or None}`` for one catalogue."""
    entries: Dict[Tuple[str, str], Optional[str]] = {}
    root = ET.parse(CATALOGUES / f"pixelart_{code}.ts").getroot()
    for scope in root.iter("context"):
        context = scope.findtext("name") or ""
        for message in scope.iter("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            kind = None if translation is None else translation.get("type")
            text = None if translation is None else translation.text
            finished = bool(text) and kind not in ("unfinished", "obsolete", "vanished")
            entries[(context, source)] = text if finished else None
    return entries


_CATALOGUE_CACHE: Dict[str, Dict[Tuple[str, str], Optional[str]]] = {}


def finished_text(code: str, context: str, source: str) -> Optional[str]:
    """Return the finished translation of a message, or ``None`` if it is not.

    English has no translation file text to compare with: its shown text is the
    source message itself, so the source is its finished text.
    """
    if code == FALLBACK_LANGUAGE:
        return source
    if code not in _CATALOGUE_CACHE:
        _CATALOGUE_CACHE[code] = _read_catalogue(code)
    return _CATALOGUE_CACHE[code].get((context, source))


def sentence_in(code: str, kind: str) -> Optional[str]:
    """Return the finished sentence of ``kind`` in ``code``, or ``None``."""
    return finished_text(code, SENTENCE_CONTEXT, SENTENCES[kind])


# --------------------------------------------------------------------------- #
# The inventory: derived from the code, never listed                          #
# --------------------------------------------------------------------------- #

FAILURE_SIGNALS = ("failed", "targetFailed", "operationFailed", "errorOccurred")
_TEXT_METHODS = (
    "lower upper capitalize title casefold strip lstrip rstrip format replace "
    "removeprefix removesuffix swapcase"
).split()


class Site(NamedTuple):
    """One place that puts a failure sentence into a template."""

    module: str
    function: str
    line: int
    context: str
    source: str


def _is_failure_text(node: ast.AST) -> TypeGuard[ast.Call]:
    """Return whether ``node`` is a call of ``failure_text``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "failure_text"
    return isinstance(func, ast.Name) and func.id == "failure_text"


def _literal(node: ast.AST) -> Optional[str]:
    """Return the string a constant node holds, or ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _template_of(
    node: ast.AST, class_name: str, templates: Dict[str, Tuple[str, str]]
) -> Optional[Tuple[str, str]]:
    """Return ``(context, source)`` if ``node`` is a translated template.

    A template is a ``tr("...")`` or ``translate("context", "...")`` call, a name
    that was assigned one, or either of those with ``.replace`` / ``.format`` chained.
    """
    while (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("replace", "format")
    ):
        node = node.func.value
    if isinstance(node, ast.Name):
        return templates.get(node.id)
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name == "tr" and node.args:
        source = _literal(node.args[0])
        return (class_name, source) if source is not None else None
    if name == "translate" and len(node.args) >= 2:
        context, source = _literal(node.args[0]), _literal(node.args[1])
        if context is not None and source is not None:
            return (context, source)
    return None


def _receivers(tree: ast.AST) -> set:
    """Return the names of the methods connected to a failure signal."""
    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        target = node.func.value
        if node.func.attr != "connect" or not isinstance(target, ast.Attribute):
            continue
        if target.attr in FAILURE_SIGNALS and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Attribute):
                found.add(argument.attr)
    return found


def _str_params(function: ast.FunctionDef) -> set:
    """Return the names of a function's parameters annotated ``str``."""
    return {
        argument.arg
        for argument in function.args.args
        if isinstance(argument.annotation, ast.Name) and argument.annotation.id == "str"
    }


def _functions(tree: ast.Module) -> Iterator[Tuple[str, ast.FunctionDef]]:
    """Yield ``(enclosing class name or "", function)`` for every function."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef):
                    yield node.name, child
    inside = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for child in ast.walk(node)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and id(node) not in inside:
            yield "", node


def derive_inventory(ui_root: Path = UI_ROOT) -> List[Site]:
    """Return every site that puts a failure sentence into a template.

    The sentence is a ``failure_text`` call, a name assigned from one, the message
    parameter of a receiver of a failure signal, or an attribute a receiver
    appends it to. The template is joined by ``.replace``, ``.format`` or
    ``failure_on_own_line``.
    """
    sites: List[Site] = []
    for path in sorted(ui_root.glob("*.py")):
        tree = ast.parse(path.read_bytes())
        receivers = _receivers(tree)
        collected = set()
        for _class, function in _functions(tree):
            if function.name not in receivers:
                continue
            names = _str_params(function)
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append"
                    and isinstance(node.func.value, ast.Attribute)
                    and any(
                        isinstance(part, ast.Name) and part.id in names
                        for arg in node.args
                        for part in ast.walk(arg)
                    )
                ):
                    collected.add(node.func.value.attr)
        for class_name, function in _functions(tree):
            tainted = _str_params(function) if function.name in receivers else set()
            templates: Dict[str, Tuple[str, str]] = {}

            def carries(expression: ast.AST) -> bool:
                for part in ast.walk(expression):
                    if _is_failure_text(part):
                        return True
                    if isinstance(part, ast.Name) and part.id in tainted:
                        return True
                    if (
                        isinstance(part, ast.Attribute)
                        and part.attr in collected
                        and isinstance(part.value, ast.Name)
                        and part.value.id == "self"
                    ):
                        return True
                return False

            for node in ast.walk(function):
                if isinstance(node, ast.Assign):
                    found = _template_of(node.value, class_name, templates)
                    for target in node.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if found is not None and isinstance(node.value, ast.Call):
                            if not isinstance(node.value.func, ast.Attribute) or (
                                node.value.func.attr not in ("replace", "format")
                            ):
                                templates[target.id] = found
                        if carries(node.value):
                            tainted.add(target.id)
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                joined: Optional[Tuple[str, str]] = None
                arguments = list(node.args) + [kw.value for kw in node.keywords]
                if isinstance(func, ast.Attribute) and func.attr in (
                    "replace",
                    "format",
                ):
                    joined = _template_of(node, class_name, templates)
                elif (
                    isinstance(func, ast.Attribute)
                    and func.attr == "failure_on_own_line"
                ) or (isinstance(func, ast.Name) and func.id == "failure_on_own_line"):
                    if node.args:
                        joined = _template_of(node.args[0], class_name, templates)
                        arguments = list(node.args[1:]) + [
                            kw.value for kw in node.keywords
                        ]
                if joined is not None and any(carries(arg) for arg in arguments):
                    sites.append(
                        Site(
                            path.name, function.name, node.lineno, joined[0], joined[1]
                        )
                    )
    return _outermost(sites)


def _outermost(sites: List[Site]) -> List[Site]:
    """Return one site per (module, function, source): a chained call is one site."""
    seen: Dict[Tuple[str, str, str], Site] = {}
    for site in sites:
        key = (site.module, site.function, site.source)
        if key not in seen or site.line < seen[key].line:
            seen[key] = site
    return sorted(seen.values(), key=lambda s: (s.module, s.line))


def untransformed_sentence_findings(ui_root: Path = UI_ROOT) -> List[str]:
    """Return every ``failure_text`` call whose sentence is changed or concatenated.

    A sentence shown alone must be shown as it is: a method called on it
    (``.lower()``), a ``+`` join or an f-string is a composition the template
    inventory does not see. Each is named by file and line.
    """
    found: List[str] = []
    for path in sorted(ui_root.glob("*.py")):
        tree = ast.parse(path.read_bytes())
        parents: Dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        for node in ast.walk(tree):
            if not _is_failure_text(node):
                continue
            parent = parents.get(id(node))
            if isinstance(parent, ast.Attribute) and parent.value is node:
                found.append(
                    f"{path.name}:{node.lineno}: a method ({parent.attr}) "
                    "is called on it"
                )
            elif isinstance(parent, (ast.BinOp, ast.JoinedStr, ast.FormattedValue)):
                found.append(
                    f"{path.name}:{node.lineno}: it is concatenated or in an f-string"
                )
    return found


def count_alone_sites(ui_root: Path = UI_ROOT) -> int:
    """Return how many ``failure_text`` calls are not inside a template join."""
    count = 0
    inventory = {(s.module, s.line) for s in derive_inventory(ui_root)}
    for path in sorted(ui_root.glob("*.py")):
        tree = ast.parse(path.read_bytes())
        for node in ast.walk(tree):
            if _is_failure_text(node):
                count += 1
    return max(count - len(inventory), 0)


# --------------------------------------------------------------------------- #
# The verdicts                                                                #
# --------------------------------------------------------------------------- #


def junction_findings(shown: str, sentence: str, code: str) -> List[str]:
    """Return what is wrong with where ``sentence`` stands in ``shown``.

    The sentence passes when it starts a line, or when the text before it on its
    line ends with a sentence-ending mark of the language. Anything else is a
    sentence that continues on its lead-in's line.
    """
    index = shown.find(sentence)
    if index < 0:
        return ["the sentence is not in the text shown"]
    before = shown[:index].rsplit("\n", 1)[-1].rstrip()
    if not before or before[-1] in SENTENCE_ENDINGS[code]:
        return []
    return [f"the sentence continues on its lead-in's line, after {before!r}"]


def passes_by_ending_mark(shown: str, sentence: str, code: str) -> bool:
    """Return whether the sentence passes only because a mark ends its line's text."""
    index = shown.find(sentence)
    if index < 0:
        return False
    before = shown[:index].rsplit("\n", 1)[-1].rstrip()
    return bool(before) and before[-1] in SENTENCE_ENDINGS[code]


def assert_junction(
    code: str, surface: str, lead_in: str, sentence: str, shown: str
) -> None:
    """Fail naming the language, the surface, the lead-in and the sentence."""
    findings = junction_findings(shown, sentence, code)
    assert not findings, (
        f"[{code}] {surface}: lead-in {lead_in!r}, sentence {sentence!r}: "
        + "; ".join(findings)
        + f"; shown {shown!r}"
    )


def failure_only_frame_findings(shown: str, reason: str, code: str) -> List[str]:
    """Return a finding when the reason is shown in a failure-only frame.

    The failure-only frame is the lead-in that ends with a sentence-ending mark; it
    may carry a failure sentence only.
    """
    index = shown.find(reason)
    if index < 0:
        return []
    before = shown[:index].rsplit("\n", 1)[-1].rstrip()
    if before and before[-1] in SENTENCE_ENDINGS[code]:
        return [
            f"the status bar shows the reason {reason!r} in the failure-only "
            f"frame {before!r}, which may carry a failure sentence only"
        ]
    return []


# --------------------------------------------------------------------------- #
# Planted failures                                                            #
# --------------------------------------------------------------------------- #

_CAUSES: Dict[str, type] = {
    "TIMEOUT": TimeoutError,
    "CONNECTION": ConnectionError,
    "NOT_FOUND": FileNotFoundError,
    "PERMISSION": PermissionError,
    "INVALID_VALUE": ValueError,
    "GENERIC": OSError,
}


def plant(base: type, kind: str, *args: Any) -> Exception:
    """Return an error of a planted subclass of ``base``, raised from the kind's cause.

    The chain is read as the interface reads it, so the sentence a site shows is
    the one of ``kind`` whatever class the site catches.
    """
    failure = type(PLANTED_NAME, (base,), {})(*(args or ("planted",)))
    failure.__cause__ = _CAUSES[kind]("cause")
    return failure


# --------------------------------------------------------------------------- #
# The driver table: one surface per lead-in, driven through the interface     #
# --------------------------------------------------------------------------- #


class Env(NamedTuple):
    """What a driver may use."""

    qtbot: Any
    monkeypatch: Any
    boxes: List[Tuple[str, str, str]]
    tmp_path: Path
    code: str


def _warning_text(env: Env) -> str:
    """Return the one warning box text shown, and fail unless there was exactly one."""
    shown = [text for (kind, _title, text) in env.boxes if kind == "warning"]
    assert len(shown) == 1, f"{len(shown)} warning boxes were shown, not one: {shown!r}"
    env.boxes.clear()
    return shown[0]


def _asset_driver(method: str) -> Callable[[Env, str], str]:
    """Return a driver of one of the asset library's failure reporters."""

    def drive(env: Env, kind: str) -> str:
        session = Asset_Library_Session()
        parent = QWidget()
        env.qtbot.addWidget(parent)
        env.boxes.clear()
        getattr(session, method)(plant(Exception, kind), parent)
        return _warning_text(env)

    return drive


def _drive_cycle_label(env: Env, kind: str) -> str:
    """Show a dependency cycle report in the view's notice and read the notice."""
    failure = plant(DependencyGraphError, kind)

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise failure

    env.monkeypatch.setattr(dependency_graph_view, "DependencyGraph", raising)
    view = Dependency_Graph_View()
    env.qtbot.addWidget(view)
    view.show()
    view.show_edges(())
    assert not view._cycle_label.isHidden(), "the notice is not shown"
    return view._cycle_label.text()


def _drive_key_hint(env: Env, kind: str) -> str:
    """Make storing the API key fail and read the provider dialog's hint."""
    failure = plant(TokenStoreError, kind)

    def raising(*args: Any, **kwargs: Any) -> None:
        raise failure

    env.monkeypatch.setattr(
        provider_config_dialog, "is_keyring_available", lambda: True
    )
    env.monkeypatch.setattr(provider_config_dialog, "store_token", raising)
    dialog = Provider_Config_Dialog()
    env.qtbot.addWidget(dialog)
    dialog._base_url_edit.setText("https://example.test/v1")
    dialog._model_edit.setText("test-model")
    dialog._key_edit.setText("sk-planted")
    dialog._on_accept()
    return dialog._hint_label.text()


def _drive_invalid_json(env: Env, kind: str) -> str:
    """Make the script's JSON fail to parse and read the box the panel opens."""
    failure = plant(json.JSONDecodeError, kind, "planted", "", 0)

    def raising(text: str) -> Any:
        raise failure

    env.monkeypatch.setattr(
        script_runner_panel,
        "json",
        types.SimpleNamespace(loads=raising, JSONDecodeError=json.JSONDecodeError),
    )
    panel = Script_Runner_Panel()
    env.qtbot.addWidget(panel)
    panel._editor.setPlainText("[")
    env.boxes.clear()
    panel._on_run()
    return _warning_text(env)


def _tilemap_driver(export: bool) -> Callable[[Env, str], str]:
    """Return a driver of the Tiled map export or import failure box."""

    def drive(env: Env, kind: str) -> str:
        failure = plant(ProjectIOError, kind)

        def raising(*args: Any, **kwargs: Any) -> Any:
            raise failure

        env.monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **k: (str(env.tmp_path / "map.tmj"), "")),
        )
        env.monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(env.tmp_path / "map.tmj"), "")),
        )
        parent = QWidget()
        env.qtbot.addWidget(parent)
        env.boxes.clear()
        if export:
            env.monkeypatch.setattr(tilemap_io_actions, "write_tiled_json", raising)
            no_map: Any = None
            tilemap_io_actions.export_tilemap_dialog(parent, no_map)
        else:
            env.monkeypatch.setattr(tilemap_io_actions, "read_tiled_json", raising)
            tilemap_io_actions.import_tilemap_dialog(parent)
        return _warning_text(env)

    return drive


def _drive_assistant_transcript(env: Env, kind: str) -> str:
    """Make an assistant turn fail on the worker and read the dock's transcript."""
    failure = plant(AssistantError, kind)

    class _Raising(FakeLLMAdapter):
        def respond(self, conversation: Any, tools: Any) -> Any:
            raise failure

    controller = Assistant_Controller()
    document = Document(16, 16, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)]))
    dock = Assistant_Dock(controller, lambda: document, lambda: _Raising([]))
    env.qtbot.addWidget(dock)
    try:
        dock._input.setText("planted request")
        with env.qtbot.waitSignal(controller.runFinished, timeout=5000):
            dock._on_send()
        return dock._transcript.toPlainText()
    finally:
        controller.shutdown()


def _drive_batch_row(env: Env, kind: str) -> str:
    """Make one batch export target fail on the worker and read its list row."""
    failure = plant(RuntimeError, kind)

    def raising(*args: Any, **kwargs: Any) -> None:
        raise failure

    env.monkeypatch.setattr(export_worker, "write_export", raising)
    from pixelart_creator.ui.export_worker import Export_Controller

    controller = Export_Controller()
    document = Document(8, 8, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)]))
    panel = Batch_Export_Panel()
    env.qtbot.addWidget(panel)
    panel.set_context(controller, lambda: document)
    target = ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG),
        out_path=str(env.tmp_path / "planted.png"),
        label="planted.png",
    )
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    panel._targets.append(target)
    item = QListWidgetItem(target.label)
    item.setData(Qt.ItemDataRole.UserRole, target.label)
    panel._list.addItem(item)
    try:
        with env.qtbot.waitSignal(controller.batchFinished, timeout=5000):
            panel._on_export_all()
        return panel._list.item(0).text()
    finally:
        controller.shutdown()


def _drive_import_box(env: Env, kind: str) -> str:
    """Report a failed drag-and-drop import through the window's own handler."""
    window = _window(env)
    env.boxes.clear()
    window._notify_import_error(
        str(env.tmp_path / "picture.png"), plant(Exception, kind)
    )
    return _warning_text(env)


def _drive_export_summary(env: Env, kind: str) -> str:
    """Fail one export target on the window's controller; read the summary box."""
    window = _window(env)
    from pixelart_creator.ui.failure_messages import FailureKind, failure_text

    env.boxes.clear()
    controller = window._export_controller
    controller.busyChanged.emit(True)  # a run starts: the accumulators reset
    controller.targetFailed.emit(0, failure_text(FailureKind(_KIND_VALUE[kind])))
    controller.batchFinished.emit()
    return _warning_text(env)


def _drive_guide_topic(env: Env, kind: str) -> str:
    """Fail to load a guide topic and read the pane."""
    failure = plant(GuideContentError, kind)

    def raising(ref: str) -> str:
        raise failure

    dialog = User_Guide_Dialog(None, reader=raising, content_locales=frozenset({"en"}))
    env.qtbot.addWidget(dialog)
    return dialog._content_view.toPlainText()


def _drive_guide_bundle(env: Env, kind: str) -> str:
    """Fail to load the guide bundle and read the pane."""
    failure = plant(GuideContentError, kind)

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise failure

    env.monkeypatch.setattr(user_guide, "load_manifest", raising)
    dialog = User_Guide_Dialog()
    env.qtbot.addWidget(dialog)
    return dialog._content_view.toPlainText()


_KIND_VALUE = {
    "TIMEOUT": "timeout",
    "CONNECTION": "connection",
    "NOT_FOUND": "not_found",
    "PERMISSION": "permission",
    "INVALID_VALUE": "invalid_value",
    "GENERIC": "generic",
}

_WINDOWS: Dict[int, Main_Window] = {}


def _window(env: Env) -> Main_Window:
    """Return the main window of this run, built once per test."""
    key = id(env.qtbot)
    if key not in _WINDOWS:
        window = Main_Window()
        env.qtbot.addWidget(window)
        _WINDOWS[key] = window
    return _WINDOWS[key]


def _drive_status_bar(env: Env, kind: str) -> str:
    """Drive the five real-time sites with a failure of ``kind``; read the status bar.

    Each site is driven through the real window's own session: a local update
    that cannot be encoded, a cursor that cannot be serialised, a frame that
    cannot be decoded, an update that cannot be applied, and a transport that
    fails on the worker thread. The one message the bar shows after each is
    joined, and the text of each must be read from one single line.
    """
    window = _window(env)
    bar = window.statusBar()
    session = window.findChildren(Realtime_Session)[0]
    client = session.client()
    shown: List[str] = []

    def read() -> None:
        shown.append(bar.currentMessage())
        bar.clearMessage()

    def raising_for(base: type) -> Callable[..., Any]:
        def raising(*args: Any, **kwargs: Any) -> Any:
            raise plant(base, kind)

        return raising

    session.connect_realtime("doc", "alice")  # no transport: the reason is shown
    assert not client.is_active(), "the no-transport connect started a worker"
    bar.clearMessage()
    frame = sync_protocol.encode_update(
        "doc", encode_update((MetadataOp("k", "v", 1, 1),))
    )
    document = Document(8, 8, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)]))
    session.set_document(document)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "is_active", lambda: True)
        mp.setattr(client, "send_update", lambda blob: None)
        mp.setattr(client, "send_presence", lambda data: None)
        mp.setattr(realtime_actions, "encode_update", raising_for(RealtimeError))
        session.push_local_update([object()])  # type: ignore[list-item]
        read()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "is_active", lambda: True)
        mp.setattr(client, "send_presence", lambda data: None)
        mp.setattr(
            realtime_actions,
            "json",
            types.SimpleNamespace(dumps=raising_for(ValueError)),
        )
        session.push_local_cursor(1, 2)
        read()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            realtime_actions.sync_protocol,
            "decode_message",
            raising_for(CloudValidationError),
        )
        client.frameReceived.emit("doc", frame)
        read()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(realtime_actions, "apply_remote", raising_for(RealtimeError))
        client.frameReceived.emit("doc", frame)
        read()

    class _Boom:
        def __call__(self) -> Any:
            raise plant(RuntimeError, kind)

    # The factory is this drive's own and is put back when the drive ends. Left set, it
    # made the NEXT drive's first connect (the no-transport one above) start a worker
    # that raised THIS kind: its queued failure reached the bar in the next drive,
    # ahead of (or instead of, when that worker was still running and the connect
    # below was a no-op) the next kind's own.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_factory", _Boom())
        assert (
            not client.is_active()
        ), "a worker is running: the connect below would do nothing"
        with env.qtbot.waitSignal(
            session.errorOccurred, timeout=5000, raising=True
        ) as delivered:
            session.connect_realtime("doc", "alice")
        read()
        session.disconnect_realtime()
    assert (
        delivered.args is not None and delivered.args[1] is True
    ), f"the worker's failure was not delivered as a failure: {delivered.args!r}"
    QCoreApplication.processEvents()  # a late delivery would show on the bar now
    assert (
        bar.currentMessage() == ""
    ), f"a delivery reached the status bar after the drive's: {bar.currentMessage()!r}"
    assert len(shown) == 5 and all(shown), f"the five real-time sites showed {shown!r}"
    return "\n@@\n".join(shown)


@dataclass(frozen=True)
class Surface:
    """One surface on which the interface shows a lead-in with a failure sentence."""

    name: str
    module: str
    sources: Tuple[str, ...]
    drive: Callable[[Env, str], str]
    #: The text a driver returns holds several messages, separated by this line.
    separator: Optional[str] = None


SURFACES: Tuple[Surface, ...] = (
    Surface(
        "asset import box",
        "asset_library_actions.py",
        ("Could not import the asset: %1",),
        _asset_driver("_report_import_failure"),
    ),
    Surface(
        "asset export box",
        "asset_library_actions.py",
        ("Could not export the asset: %1",),
        _asset_driver("_report_export_failure"),
    ),
    Surface(
        "project bundle export box",
        "asset_library_actions.py",
        ("Could not export the project bundle: %1",),
        _asset_driver("_report_bundle_export_failure"),
    ),
    Surface(
        "project bundle import box",
        "asset_library_actions.py",
        ("Could not import the project bundle: %1",),
        _asset_driver("_report_bundle_import_failure"),
    ),
    Surface(
        "asset registration box",
        "asset_library_actions.py",
        ("Could not register the asset: %1",),
        _asset_driver("_report_failure"),
    ),
    Surface(
        "dependency cycle notice",
        "dependency_graph_view.py",
        ("Dependency cycle detected (graph unchanged): %1",),
        _drive_cycle_label,
    ),
    Surface(
        "provider key hint",
        "provider_config_dialog.py",
        ("Could not store the API key: {0}",),
        _drive_key_hint,
    ),
    Surface(
        "script error box",
        "script_runner_panel.py",
        ("Invalid JSON: %1",),
        _drive_invalid_json,
    ),
    Surface(
        "tilemap export box",
        "tilemap_io_actions.py",
        ("Could not export the map: %1",),
        _tilemap_driver(True),
    ),
    Surface(
        "tilemap import box",
        "tilemap_io_actions.py",
        ("Could not import the map: %1",),
        _tilemap_driver(False),
    ),
    Surface(
        "assistant transcript",
        "assistant_dock.py",
        ("Assistant error: {0}",),
        _drive_assistant_transcript,
    ),
    Surface(
        "batch export row",
        "batch_export_panel.py",
        ("%1 — failed: %2",),
        _drive_batch_row,
    ),
    Surface(
        "status bar",
        "main_window.py",
        (REASON_FRAME[1], FAILURE_ONLY_FRAME[1]),
        _drive_status_bar,
        separator="@@",
    ),
    Surface(
        "import failed box",
        "main_window.py",
        ("Could not import %1:\n%2",),
        _drive_import_box,
    ),
    Surface(
        "export summary box",
        "main_window.py",
        ("%n export target(s) failed:\n%2",),
        _drive_export_summary,
    ),
    Surface(
        "guide topic pane",
        "user_guide.py",
        ("Could not load this topic:\n\n%1",),
        _drive_guide_topic,
    ),
    Surface(
        "guide bundle pane",
        "user_guide.py",
        ("The User Guide content could not be loaded:\n\n%1",),
        _drive_guide_bundle,
    ),
)


def unexamined(sites: List[Site], surfaces: Tuple[Surface, ...]) -> List[str]:
    """Return what the table does not examine, and what it examines that is not there.

    A derived site that no surface claims was not examined. A surface that claims
    no derived site is stale: it would pass without driving anything real.
    """
    problems: List[str] = []
    claimed: set[str] = set()
    for site in sites:
        owners = [
            s for s in surfaces if s.module == site.module and site.source in s.sources
        ]
        if not owners:
            problems.append(
                f"{site.module}:{site.line} {site.function}: lead-in {site.source!r} "
                "was not examined (no surface in the driver table claims it)"
            )
        claimed.update(s.name for s in owners)
    for surface in surfaces:
        if surface.name not in claimed:
            problems.append(f"surface {surface.name!r} claims no derived site")
    return problems


def comparable(code: str, surface: Surface, sites: List[Site]) -> Optional[str]:
    """Return why a language cannot be compared on a surface, or ``None`` if it can."""
    missing = [k for k in SENTENCES if sentence_in(code, k) is None]
    if missing:
        return f"the sentences of {missing} are unfinished in {code}"
    for site in sites:
        if site.module == surface.module and site.source in surface.sources:
            if site.source == FAILURE_ONLY_FRAME[1]:
                continue
            if finished_text(code, site.context, site.source) is None:
                return f"the lead-in {site.source!r} is unfinished in {code}"
    return None


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def language(qapp) -> Iterator[Callable[[str], None]]:
    """Install a language through the app's own manager; restore English after."""
    manager = LanguageManager(qapp)

    def install(code: str) -> None:
        assert manager.set_language(code) is True, f"{code!r} did not load"

    try:
        yield install
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
        _WINDOWS.clear()


@pytest.fixture(scope="module")
def sites() -> List[Site]:
    """The derived inventory, read once."""
    return derive_inventory()


def _examine(
    code: str,
    sites: List[Site],
    env: Env,
    surfaces: Tuple[Surface, ...] = SURFACES,
) -> Tuple[List[str], Dict[str, int], List[str]]:
    """Drive every surface with every sentence in ``code``.

    Returns the failures (each naming language, surface, lead-in and sentence), the
    counts, and the compositions that pass only because a mark ends the text before
    the sentence.
    """
    failures: List[str] = []
    ending_marks: List[str] = []
    compositions = 0
    for surface in surfaces:
        lead_in = " | ".join(surface.sources)
        for kind in SENTENCES:
            sentence = sentence_in(code, kind)
            assert sentence is not None
            text = surface.drive(env, kind)
            parts = (
                text.split(f"\n{surface.separator}\n") if surface.separator else [text]
            )
            for shown in parts:
                compositions += 1
                findings = junction_findings(shown, sentence, code)
                if findings:
                    failures.append(
                        f"[{code}] {surface.name}: lead-in {lead_in!r}, sentence "
                        f"{sentence!r}: {'; '.join(findings)}"
                    )
                elif passes_by_ending_mark(shown, sentence, code):
                    ending_marks.append(f"{surface.name}: {shown!r}")
    counts = {
        "lead_ins": len(sites),
        "sentences": len(SENTENCES),
        "compositions": compositions,
    }
    return failures, counts, ending_marks


def _report(code: str, counts: Dict[str, int], ending_marks: List[str], capsys) -> None:
    """Print the figures of one language: derived, with the review's beside them."""
    surfaces_with_marks = sorted({line.split(":", 1)[0] for line in ending_marks})
    line = (
        f"[lead-in junction] {code}: lead-ins {counts['lead_ins']}, sentences "
        f"{counts['sentences']}, compositions {counts['compositions']}; "
        f"record, never compared: the review counted {REVIEW_INLINE_LEAD_INS} inline "
        f"lead-ins and {REVIEW_SENTENCES} sentences; compositions that pass because "
        f"a sentence-ending mark ends the text before the sentence, by surface: "
        f"{surfaces_with_marks} (only the status bar's failure-only frame is expected)"
    )
    print(line)
    with capsys.disabled():
        print(line)
    assert counts["lead_ins"] > 0 and counts["sentences"] > 0
    assert counts["compositions"] > 0


def _env(qtbot, monkeypatch, mute_message_boxes, tmp_path, code: str) -> Env:
    return Env(qtbot, monkeypatch, mute_message_boxes, tmp_path, code)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-020-4: every surface is examined, none is exempt                 #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_020_4_the_inventory_is_derived_and_every_surface_is_driven(
    sites, capsys
):
    """SC-L10N-UI-020-4: each derived site belongs to a surface, and each surface to a
    site.

    The surfaces are printed with the compositions each takes in a language, and
    the check carries no list of exempt surfaces, lead-ins or languages.
    """
    per_module: Dict[str, int] = {}
    for site in sites:
        per_module[site.module] = per_module.get(site.module, 0) + 1
    line = (
        f"[lead-in inventory] derived {len(sites)} sites in {len(per_module)} ui "
        f"modules; surfaces driven {len(SURFACES)}; alone sites (a failure sentence "
        f"not in a template, record) {count_alone_sites()}: "
        + "; ".join(f"{s.module}:{s.line} {s.source!r}" for s in sites)
    )
    print(line)
    with capsys.disabled():
        print(line)
    assert len(sites) > 0
    assert unexamined(sites, SURFACES) == []


def test_sc_l10n_ui_020_4_a_surface_planted_as_skipped_fails_saying_it_was_not_examined(
    sites,
):
    """SC-L10N-UI-020-4: remove one surface from the table and the check names it."""
    for removed in SURFACES:
        reduced = tuple(s for s in SURFACES if s is not removed)
        problems = unexamined(sites, reduced)
        assert problems, f"removing {removed.name!r} was not noticed"
        assert any(
            "was not examined" in problem and repr(removed.sources[0]) in problem
            for problem in problems
        ), f"removing {removed.name!r}: {problems!r}"


def test_sc_l10n_ui_020_4_the_derivation_finds_a_planted_inline_site(tmp_path):
    """SC-L10N-UI-020-4 control: an inline composition in a scratch module is derived.

    The scratch module holds one site of each shape the derivation reads: a
    ``failure_text`` result replaced into a ``tr()`` template, a receiver's message
    parameter formatted into one, and a joining function. A table that claims none
    of them reports each as not examined.
    """
    (tmp_path / "scratch_surface.py").write_text(
        "from pixelart_creator.ui import failure_messages\n"
        "from pixelart_creator.ui.failure_messages import failure_on_own_line\n"
        "class Scratch:\n"
        "    def wire(self, controller):\n"
        "        controller.failed.connect(self.on_failed)\n"
        "    def on_failed(self, message: str):\n"
        "        return self.tr('Scratch error: {0}').format(message)\n"
        "    def inline(self, exc):\n"
        "        return self.tr('Scratch inline: %1').replace('%1',\n"
        "            failure_messages.failure_text(\n"
        "                failure_messages.failure_kind(exc)))\n"
        "    def own(self, exc):\n"
        "        return failure_on_own_line(self.tr('Scratch own: %1'), '%1',\n"
        "            failure_messages.failure_text(\n"
        "                failure_messages.failure_kind(exc)))\n",
        encoding="utf-8",
    )
    found = derive_inventory(tmp_path)
    assert sorted(site.source for site in found) == [
        "Scratch error: {0}",
        "Scratch inline: %1",
        "Scratch own: %1",
    ]
    problems = unexamined(found, SURFACES)
    assert sum("was not examined" in problem for problem in problems) == 3


def test_sc_l10n_ui_020_4_no_sentence_is_changed_or_concatenated_outside_a_template():
    """SC-L10N-UI-020-4: a sentence is never lower-cased, joined by ``+`` or in an
    f-string."""
    assert untransformed_sentence_findings() == []


# --------------------------------------------------------------------------- #
# SC-L10N-UI-020-1 and -2: no sentence continues on a lead-in's line          #
# --------------------------------------------------------------------------- #


def _run_language(
    code: str,
    sites,
    language,
    qtbot,
    monkeypatch,
    mute_message_boxes,
    tmp_path,
    capsys,
) -> None:
    """Drive every surface in ``code`` and fail naming each sentence that continues."""
    reasons = {surface.name: comparable(code, surface, sites) for surface in SURFACES}
    blocked = {name: why for name, why in reasons.items() if why}
    if blocked:
        counted = len(blocked) * len(SENTENCES)
        why = sorted(set(blocked.values()))[0]
        line = (
            f"[lead-in junction] {code}: not yet comparable on {len(blocked)} of "
            f"{len(SURFACES)} surfaces, {counted} rows counted and not passed ({why})"
        )
        print(line)
        with capsys.disabled():
            print(line)
        pytest.skip(f"not yet comparable: {why}")
    language(code)
    env = _env(qtbot, monkeypatch, mute_message_boxes, tmp_path, code)
    failures, counts, ending_marks = _examine(code, sites, env)
    _report(code, counts, ending_marks, capsys)
    assert (
        not failures
    ), f"{len(failures)} compositions continue on a lead-in's line:\n" + "\n".join(
        failures
    )


def test_sc_l10n_ui_020_1_in_spanish_no_failure_sentence_continues_on_a_lead_ins_line(
    sites, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
):
    """SC-L10N-UI-020-1: in Spanish, each lead-in composed with each sentence is
    clear."""
    _run_language(
        "es", sites, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
    )


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "es"])
def test_sc_l10n_ui_020_2_no_sentence_continues_on_a_lead_ins_line(
    code, sites, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
):
    """SC-L10N-UI-020-2: in each other language, each lead-in composed with each
    sentence is clear."""
    _run_language(
        code, sites, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
    )


def test_sc_l10n_ui_020_1_and_2_the_languages_not_yet_comparable_are_counted(
    sites, capsys
):
    """SC-L10N-UI-020-1 and -2: each language is comparable or counted, never passed."""
    rows = len(SURFACES) * len(SENTENCES)
    ready = [
        c for c in LANGUAGES if all(comparable(c, s, sites) is None for s in SURFACES)
    ]
    waiting = [c for c in LANGUAGES if c not in ready]
    line = (
        f"[lead-in junction] languages compared: {len(ready)} of {len(LANGUAGES)} "
        f"{ready}; not yet comparable: {waiting} ({len(waiting) * rows} rows counted, "
        f"never passed)"
    )
    print(line)
    with capsys.disabled():
        print(line)
    assert FALLBACK_LANGUAGE in ready, "English must always be comparable"
    assert len(ready) + len(waiting) == len(LANGUAGES)


# -- the planted compositions ------------------------------------------------ #

REVIEW_LEAD_IN = "No se pudo exportar el mapa: %1"
REVIEW_SENTENCE = "Se agotó el tiempo de espera de la operación."
REVIEW_LOWER = "se agotó el tiempo de espera de la operación."


def _compose_inline(template: str, sentence: str) -> str:
    return template.replace("%1", sentence)


def test_sc_l10n_ui_020_1_the_composition_the_reviewer_read_fails_naming_both():
    """SC-L10N-UI-020-1: the reviewer's Spanish composition, planted, fails and names
    both."""
    shown = _compose_inline(REVIEW_LEAD_IN, REVIEW_SENTENCE)
    assert shown == "No se pudo exportar el mapa: " + REVIEW_SENTENCE
    with pytest.raises(AssertionError) as failure:
        assert_junction("es", "planted", REVIEW_LEAD_IN, REVIEW_SENTENCE, shown)
    text = str(failure.value)
    assert REVIEW_LEAD_IN in text and REVIEW_SENTENCE in text and "es" in text


def test_sc_l10n_ui_020_1_the_same_composition_with_a_lower_case_sentence_fails_too():
    """SC-L10N-UI-020-1: the lower-case variant of the reviewer's composition fails
    too."""
    shown = _compose_inline(REVIEW_LEAD_IN, REVIEW_LOWER)
    assert shown == "No se pudo exportar el mapa: " + REVIEW_LOWER
    with pytest.raises(AssertionError) as failure:
        assert_junction("es", "planted", REVIEW_LEAD_IN, REVIEW_LOWER, shown)
    text = str(failure.value)
    assert REVIEW_LEAD_IN in text and REVIEW_LOWER in text


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != "es"])
def test_sc_l10n_ui_020_2_one_inline_composition_per_language_fails_naming_it(code):
    """SC-L10N-UI-020-2: a sentence planted after the lead-in's colon fails in each
    language.

    The lead-in is the language's own finished translation of the map export
    message; the sentence is the language's finished one, or the English source
    where the language has none yet, which exercises the verdict and not the
    catalogue.
    """
    source = "Could not export the map: %1"
    lead_in = finished_text(code, "tilemap_io", source)
    assert lead_in is not None and "%1" in lead_in, f"{code}: no finished lead-in"
    sentence = sentence_in(code, "TIMEOUT") or SENTENCES["TIMEOUT"]
    shown = _compose_inline(lead_in, sentence)
    with pytest.raises(AssertionError) as failure:
        assert_junction(code, "planted", lead_in, sentence, shown)
    text = str(failure.value)
    assert code in text and repr(lead_in) in text and repr(sentence) in text


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_020_1_and_2_the_verdict_can_be_satisfied(
    code,
):
    """SC-L10N-UI-020-1 and -2 control: the verdict can be met in every language."""
    lead_in = finished_text(code, "tilemap_io", "Could not export the map: %1") or (
        "Could not export the map: %1"
    )
    sentence = sentence_in(code, "TIMEOUT") or SENTENCES["TIMEOUT"]
    head = lead_in.replace("%1", "").rstrip()
    assert junction_findings(f"{head}\n{sentence}", sentence, code) == []
    assert junction_findings(sentence, sentence, code) == []
    closed = head.rstrip(":：") + SENTENCE_ENDINGS[code][0]
    assert junction_findings(f"{closed} {sentence}", sentence, code) == []
    for colon in (":", "：", " :"):
        assert junction_findings(
            f"{head.rstrip(':：')}{colon} {sentence}", sentence, code
        )


# --------------------------------------------------------------------------- #
# SC-L10N-UI-020-3: a sentence not joined inline keeps its catalogue form     #
# --------------------------------------------------------------------------- #


def _alone_findings(shown: str, sentence: str) -> List[str]:
    """Return what is wrong with a sentence shown alone as a message's whole body."""
    if shown != sentence:
        return [f"shown {shown!r}, the catalogue holds {sentence!r}"]
    return []


def _drive_alone_message_box(env: Env, kind: str) -> str:
    """Make the tagging panel reject a tag; read the box (the sentence is the body)."""
    import pixelart_creator.ui.asset_tagging_panel as asset_tagging_panel
    from pixelart_creator.logic.asset_catalog import (
        AssetCatalog,
        AssetDescriptor,
        AssetKind,
    )
    from pixelart_creator.logic.asset_tags import AssetTagError
    from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel

    failure = plant(AssetTagError, kind)

    def raising(descriptor: Any, tag: Any) -> Any:
        raise failure

    env.monkeypatch.setattr(asset_tagging_panel, "make_add_tag", raising)
    session = Asset_Library_Session(
        catalog=AssetCatalog(
            descriptors=(
                AssetDescriptor(
                    asset_id="a1",
                    kind=AssetKind.SPRITE,
                    name="Hero",
                    content_hash="hash-a1",
                    tags=frozenset({"hero"}),
                ),
            )
        )
    )
    panel = Asset_Tagging_Panel()
    env.qtbot.addWidget(panel)
    panel.set_session(session)
    panel.set_asset("a1")
    panel._tag_edit.setText("player")
    env.boxes.clear()
    panel._on_add_tag()
    return _warning_text(env)


def _drive_alone_worker_message(env: Env, kind: str) -> str:
    """Fail a cloud operation on the worker; read the message the controller relays."""
    from pixelart_creator.data.cloud import CloudError, FakeCloudAdapter
    from pixelart_creator.ui.cloud_actions import Cloud_Session, make_save_job
    from pixelart_creator.ui.cloud_worker import Cloud_Controller

    failure = plant(CloudError, kind)

    class _Raising(FakeCloudAdapter):
        def put(self, *args: Any, **kwargs: Any) -> Any:
            raise failure

    session = Cloud_Session(factory=lambda: _Raising(connected=True))
    session.connect_provider()
    controller = Cloud_Controller()
    messages: List[str] = []
    controller.operationFailed.connect(lambda _kind, message: messages.append(message))
    try:
        document = Document(
            8, 8, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)])
        )
        port = session.port()
        assert port is not None
        with env.qtbot.waitSignal(controller.operationFinished, timeout=5000):
            controller.submit("save", make_save_job(port, "proj", document))
    finally:
        controller.shutdown()
    assert len(messages) == 1, messages
    return messages[0]


ALONE_SITES: Dict[str, Callable[[Env, str], str]] = {
    "message box (ui/asset_tagging_panel.py)": _drive_alone_message_box,
    "worker signal (ui/cloud_worker.py)": _drive_alone_worker_message,
}


def _own_line_findings(shown: str, sentence: str) -> List[str]:
    """Return what is wrong with a sentence that stands on a line of its own."""
    for line in shown.split("\n"):
        if line == sentence:
            return []
    return [f"no line of {shown!r} equals the catalogue's {sentence!r}"]


def test_sc_l10n_ui_020_3_a_sentence_not_joined_inline_keeps_its_catalogue_form(
    sites, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
):
    """SC-L10N-UI-020-3: alone, or on a line of its own, the sentence is the
    catalogue's.

    English is examined (the other languages follow as their sentences are
    finished). Sites are printed per kind and the total is non-zero. A sentence
    shown after a lead-in that ends as a sentence is checked on the status bar's
    failure-only frame, where the surface shows it.
    """
    language("en")
    env = _env(qtbot, monkeypatch, mute_message_boxes, tmp_path, "en")
    failures: List[str] = []
    alone = own_line = after_ending = 0
    for site_name, drive in ALONE_SITES.items():
        for kind, sentence in SENTENCES.items():
            alone += 1
            findings = _alone_findings(drive(env, kind), sentence)
            failures += [f"{site_name}, {kind}: {f}" for f in findings]
    for surface in SURFACES:
        for kind, sentence in SENTENCES.items():
            text = surface.drive(env, kind)
            parts = (
                text.split(f"\n{surface.separator}\n") if surface.separator else [text]
            )
            for shown in parts:
                index = shown.find(sentence)
                before = (
                    shown[:index].rsplit("\n", 1)[-1].rstrip() if index >= 0 else ""
                )
                if index < 0:
                    failures.append(
                        f"{surface.name}, {kind}: the catalogue's {sentence!r} is "
                        f"not in what is shown, {shown!r}"
                    )
                elif not before:
                    own_line += 1
                    findings = _own_line_findings(shown, sentence)
                    failures += [f"{surface.name}, {kind}: {f}" for f in findings]
                elif before[-1] in SENTENCE_ENDINGS["en"]:
                    after_ending += 1
                    if not shown.endswith(sentence):
                        failures.append(
                            f"{surface.name}, {kind}: the sentence is not "
                            f"the end of {shown!r}"
                        )
    line = (
        f"[lead-in sentences] en: sites examined alone {alone}, on a line of its own "
        f"{own_line}, after a lead-in that ends as a sentence {after_ending}; total "
        f"{alone + own_line + after_ending}"
    )
    print(line)
    with capsys.disabled():
        print(line)
    assert alone + own_line + after_ending > 0
    assert not failures, "\n".join(failures)


def test_sc_l10n_ui_020_3_a_lower_case_spanish_sentence_alone_fails_naming_the_site():
    """SC-L10N-UI-020-3: the planted lower-case Spanish sentence, alone, fails and
    names the site."""
    site = "message box (ui/asset_tagging_panel.py)"
    expected = REVIEW_SENTENCE
    findings = _alone_findings(REVIEW_LOWER, expected)
    assert findings, "a sentence in lower case where it stands alone passed"
    with pytest.raises(AssertionError) as failure:
        assert not findings, f"{site}: {findings}"
    assert site in str(failure.value)
    assert _alone_findings(expected, expected) == []


# --------------------------------------------------------------------------- #
# SC-L10N-UI-020-4: the status bar                                            #
# --------------------------------------------------------------------------- #


def _status_bar_surface() -> Surface:
    return next(s for s in SURFACES if s.name == "status bar")


def _status_line_for(code: str, kind: str, env: Env) -> List[str]:
    """Return the five lines the real window's bar shows for a failure of ``kind``."""
    text = _status_bar_surface().drive(env, kind)
    return text.split("\n@@\n")


def _frame_text(code: str) -> Optional[str]:
    """Return the failure-only frame of ``code`` (``None`` while it is unfinished)."""
    return finished_text(code, *FAILURE_ONLY_FRAME)


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_020_4_each_failure_sentence_is_shown_in_the_failure_only_frame(
    code, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
):
    """SC-L10N-UI-020-4: on the status bar each sentence is the frame with the sentence
    in {msg}.

    On the real window, each failure sentence of the five real-time sites is shown
    in the failure-only frame (English source ``Real-time. {msg}``): that
    catalogue's finished translation of the frame with the sentence in place of
    ``{msg}``. A language whose frame or sentences are still unfinished is "not yet
    comparable": skipped, counted, never passed.
    """
    frame = _frame_text(code)
    unfinished = [k for k in SENTENCES if sentence_in(code, k) is None]
    if frame is None or unfinished:
        line = (
            f"[status bar] {code}: not yet comparable, "
            f"{len(SENTENCES) * 5} rows counted and not passed "
            f"(frame {'unfinished' if frame is None else 'finished'}, "
            f"sentences unfinished: {len(unfinished)})"
        )
        print(line)
        with capsys.disabled():
            print(line)
        pytest.skip(
            f"not yet comparable: the frame or the sentences are unfinished in {code}"
        )
    language(code)
    env = _env(qtbot, monkeypatch, mute_message_boxes, tmp_path, code)
    failures: List[str] = []
    compared = 0
    for kind in SENTENCES:
        sentence = sentence_in(code, kind)
        assert sentence is not None
        expected = frame.replace("{msg}", sentence)
        for shown in _status_line_for(code, kind, env):
            compared += 1
            if shown != expected:
                failures.append(
                    f"[{code}] status bar, lead-in {frame!r}, sentence {sentence!r}: "
                    f"shown {shown!r}, expected {expected!r}"
                )
    line = (
        f"[status bar] {code}: compositions compared {compared}, "
        f"failures {len(failures)}"
    )
    print(line)
    with capsys.disabled():
        print(line)
    assert compared == len(SENTENCES) * 5
    assert not failures, "\n".join(failures)


def test_sc_l10n_ui_020_4_the_inline_frame_planted_with_a_sentence_fails():
    """SC-L10N-UI-020-4: ``Real-time: {msg}`` planted with a sentence in {msg} fails
    and names it."""
    lead_in = REASON_FRAME[1]
    sentence = SENTENCES["TIMEOUT"]
    shown = lead_in.replace("{msg}", sentence)
    assert shown == "Real-time: The operation timed out."
    with pytest.raises(AssertionError) as failure:
        assert_junction("en", "status bar", lead_in, sentence, shown)
    text = str(failure.value)
    assert "status bar" in text and lead_in in text and sentence in text


def test_sc_l10n_ui_020_4_the_failure_only_frame_planted_with_a_sentence_passes():
    """SC-L10N-UI-020-4 control: the frame that closes the label passes the verdict."""
    shown = FAILURE_ONLY_FRAME[1].replace("{msg}", SENTENCES["TIMEOUT"])
    assert shown == "Real-time. The operation timed out."
    assert_junction(
        "en", "status bar", FAILURE_ONLY_FRAME[1], SENTENCES["TIMEOUT"], shown
    )


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_020_4_with_no_transport_the_reason_keeps_its_frame(
    code, language, qtbot, monkeypatch, mute_message_boxes, tmp_path, capsys
):
    """SC-L10N-UI-020-4: with no transport configured the bar keeps ``Real-time:
    {msg}``.

    The status bar shows that catalogue's translation of ``Real-time: {msg}`` with
    its translation of the reason in place of ``{msg}``, and not the failure-only
    frame. This passes before and after the failure-only frame exists.
    """
    frame = finished_text(code, *REASON_FRAME)
    reason = finished_text(code, REASON_CONTEXT, REASON_SOURCE)
    if frame is None or reason is None:
        line = (
            f"[status bar] {code}: the reason is not yet comparable, 1 row counted "
            f"and not passed (frame finished {frame is not None}, reason finished "
            f"{reason is not None})"
        )
        print(line)
        with capsys.disabled():
            print(line)
        pytest.skip(
            f"not yet comparable: the frame or the reason is unfinished in {code}"
        )
    language(code)
    env = _env(qtbot, monkeypatch, mute_message_boxes, tmp_path, code)
    window = _window(env)
    bar = window.statusBar()
    session = window.findChildren(Realtime_Session)[0]
    bar.clearMessage()
    session.connect_realtime("doc", "alice")  # no transport factory is configured
    shown = bar.currentMessage()
    assert shown == frame.replace("{msg}", reason), (
        f"[{code}] status bar: shown {shown!r}, expected "
        f"{frame.replace('{msg}', reason)!r}"
    )
    assert failure_only_frame_findings(shown, reason, code) == []


def test_sc_l10n_ui_020_4_the_reason_in_the_failure_only_frame_fails():
    """SC-L10N-UI-020-4: the reason in the failure-only frame fails, naming the status
    bar and it."""
    shown = FAILURE_ONLY_FRAME[1].replace("{msg}", REASON_SOURCE)
    assert shown == "Real-time. no real-time transport configured"
    findings = failure_only_frame_findings(shown, REASON_SOURCE, "en")
    assert findings, "the reason in the failure-only frame passed"
    text = " ".join(findings)
    assert "status bar" in text and REASON_SOURCE in text
    existing = REASON_FRAME[1].replace("{msg}", REASON_SOURCE)
    assert failure_only_frame_findings(existing, REASON_SOURCE, "en") == []
