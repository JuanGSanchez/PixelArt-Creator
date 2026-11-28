"""The plugin host's facts behind the consent prompt and the user guide's plugin text.

Covers REQ-L10N-UI-016 (clauses 2 and 3: the consent text must not call a plugin
isolated, and must say the permissions are checked only on calls made through the
plugin host's permission object and do not limit what a plugin's own code does,
including calling the app's command registry directly) and REQ-L10N-DATA-006
(clause 2: the guide's plugin passage states only what the host does). Every case
runs the REAL ``pixelart_creator.logic.plugins``
host; nothing here stubs the behaviour being claimed. Each case names the
statement it stands for, and each fact that a sentence could get wrong carries a
control: a case that proves the probe can tell the two answers apart (a process
that is not this one has another pid; an entry point that is loaded does run its
module; a source that does contain the planted construct is flagged).

Statements covered:

* clause 2, "not isolated": code a plugin's activation step runs executes in the
  test's own process and thread and reaches the filesystem and sockets whatever
  permissions were granted (``TestNotIsolated``);
* clause 3, "the permissions are checked only on calls made through the permission
  object", in its two routes (``TestPermissionObject``):

  - route 1, through the object: it refuses an operation whose permission was not
    granted and allows one that was; names registered through it are prefixed and
    cannot match a built-in; a read permission returns the document it is passed;
  - route 2, directly to the command registry (``logic.scripting``): code granted
    nothing registers, removes and dispatches an operation and nothing refuses it,
    because the registry's own functions check no permission;
* "in this release the app has no step that loads or runs a plugin's code":
  discovering, adding a manifest, enabling and disabling never import a plugin
  module, and no caller in the product passes an activation step
  (``TestNoStepRunsPluginCode``);
* enabling records the grant in memory only, and nothing is saved
  (``TestHostState``);
* the headless runner never touches the plugin host (``TestAutomationRunner``).

A future change that isolates plugin code, adds a step that loads or runs it, or
makes the permissions limit the plugin's own code MUST make cases here fail. Such
a change must revisit the consent prompt and the plugin passage of the user guide
in the same change, never edit these cases to pass.

Zero Qt; deterministic. The scratch directory is ``tmp_path`` (under the suite's
declared temporary root, deleted per test) and no product file is written.
"""

from __future__ import annotations

import ast
import importlib
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Tuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pixelart_creator
from pixelart_creator.data import automation_cli, macro_io
from pixelart_creator.data.macro_io import load_manifest, save_macro
from pixelart_creator.data.project_io import save_project
from pixelart_creator.logic import plugins, scripting
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Op, record
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.plugins import (
    ENTRY_POINT_GROUP,
    Capability,
    PluginCapability,
    PluginError,
    PluginManifest,
    discover,
    enable,
    loaded_count,
    validate_manifest,
)

RED = (255, 0, 0, 255)
TRANSPARENT = (0, 0, 0, 0)
ALL_CAPABILITIES = tuple(Capability)
PACKAGE_ROOT = Path(pixelart_creator.__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _manifest(
    caps: Tuple[Capability, ...] = (), name: str = "facts.plugin"
) -> PluginManifest:
    return validate_manifest(
        {
            "name": name,
            "version": "1.0.0",
            "api_version": plugins.PLUGIN_API_VERSION,
            "capabilities": [cap.value for cap in caps],
        }
    )


def _document() -> Document:
    return Document(4, 4, palette=Palette([RED]))


class _CountingCommand(Command):
    """A minimal reversible command whose execution count is observable."""

    label = "count"

    def __init__(self) -> None:
        self.executed = 0

    def execute(self) -> None:
        self.executed += 1

    def undo(self) -> None:
        self.executed -= 1


def _counting_factory(
    document: Document, params: Mapping[str, object], seed: Optional[int]
) -> Command:
    return _CountingCommand()


def _python(code: str, cwd: Path) -> str:
    """Run ``code`` in a fresh interpreter that imports the package; return stdout."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


# --------------------------------------------------------------------------- #
# Source scans (the "no caller anywhere" facts are claims about the whole      #
# product, so they are read from its source, never from a sample of it)        #
# --------------------------------------------------------------------------- #

_ISOLATION_MODULES = frozenset({"subprocess", "multiprocessing"})
_PERSISTENCE_MODULES = frozenset(
    {"os", "pathlib", "json", "pickle", "shelve", "sqlite3", "shutil", "tempfile"}
)
_DYNAMIC_LOAD_NAMES = frozenset(
    {"import_module", "exec_module", "spec_from_file_location", "addsitedir"}
)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _isolation_hits(source: str) -> List[Tuple[int, str]]:
    """Return (line, what) for every construct that would isolate code."""
    hits: List[Tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _ISOLATION_MODULES:
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _ISOLATION_MODULES:
                hits.append((node.lineno, f"from {node.module} import"))
        elif isinstance(node, ast.Call) and _call_name(node) == "addaudithook":
            hits.append((node.lineno, "addaudithook"))
    return hits


def _plugin_code_running_hits(source: str) -> List[Tuple[int, str]]:
    """Return (line, what) for every construct that loads or runs plugin code."""
    hits: List[Tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "runpy":
                    hits.append((node.lineno, "import runpy"))
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "runpy":
                hits.append((node.lineno, "from runpy import"))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name == "load" and not node.args and not node.keywords:
                hits.append((node.lineno, "entry-point .load()"))
            elif name in _DYNAMIC_LOAD_NAMES or name == "__import__":
                hits.append((node.lineno, name))
            elif name in ("insert", "append") and _is_sys_path(node.func):
                hits.append((node.lineno, f"sys.path.{name}"))
            if any(keyword.arg == "activate" for keyword in node.keywords):
                hits.append((node.lineno, "activate= keyword"))
    return hits


def _is_sys_path(func: ast.expr) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "path"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "sys"
    )


def _persistence_hits(source: str) -> List[Tuple[int, str]]:
    """Return (line, what) for every file or persistence use in ``source``."""
    hits: List[Tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _PERSISTENCE_MODULES:
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _PERSISTENCE_MODULES:
                hits.append((node.lineno, f"from {node.module} import"))
        elif isinstance(node, ast.Call) and _call_name(node) == "open":
            hits.append((node.lineno, "open()"))
    return hits


def _product_sources() -> Iterator[Tuple[Path, str]]:
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        yield path, path.read_bytes().decode("utf-8")


# --------------------------------------------------------------------------- #
# Clause 2: a plugin is not isolated                                           #
# --------------------------------------------------------------------------- #


class TestNotIsolated:
    """Clause 2: code a plugin runs is not isolated from the computer."""

    def test_read_only_plugin_runs_in_this_process_and_writes_a_file(
        self, plugins_guard, tmp_path
    ):
        """A plugin granted only the document-read permission runs in this process.

        Same pid, same thread, and it writes a file under a scratch directory.
        """
        seen: Dict[str, object] = {}
        target = tmp_path / "written_by_plugin.txt"

        def activate(capability: PluginCapability) -> None:
            seen["pid"] = os.getpid()
            seen["thread"] = threading.get_ident()
            seen["granted"] = capability.granted
            target.write_text("plugin code ran here", encoding="utf-8")

        manifest = _manifest((Capability.READ_DOCUMENT,))
        enable(manifest, {Capability.READ_DOCUMENT}, activate=activate)

        assert seen["granted"] == (Capability.READ_DOCUMENT,)
        assert seen["pid"] == os.getpid()
        assert seen["thread"] == threading.get_ident()
        assert target.read_text(encoding="utf-8") == "plugin code ran here"
        assert target.parent == tmp_path

    def test_another_process_has_another_pid(self, tmp_path):
        """Control: the pid comparison above can tell this process from another."""
        child = _python("import os; print(os.getpid())", tmp_path)
        assert int(child) != os.getpid()

    @pytest.mark.parametrize(
        "granted",
        [(), (Capability.READ_DOCUMENT,), ALL_CAPABILITIES],
        ids=["nothing-granted", "read-only", "everything-granted"],
    )
    def test_file_access_does_not_depend_on_the_permissions_granted(
        self, plugins_guard, tmp_path, granted
    ):
        """Whatever was granted, the plugin's own code reads and writes files."""
        source = tmp_path / "source.txt"
        source.write_text("readable", encoding="utf-8")
        seen: Dict[str, str] = {}

        def activate(capability: PluginCapability) -> None:
            seen["read"] = source.read_text(encoding="utf-8")
            (tmp_path / "out.txt").write_text("written", encoding="utf-8")

        enable(_manifest(granted), set(granted), activate=activate)
        assert seen["read"] == "readable"
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "written"

    def test_plugin_code_can_open_a_network_socket(self, plugins_guard):
        """A plugin's own code can create a socket; no permission stands in the way.

        A socket is only created and closed: nothing connects and no traffic is sent.
        """
        outcome: Dict[str, bool] = {}

        def activate(capability: PluginCapability) -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                outcome["created"] = sock.fileno() >= 0

        enable(_manifest(), set(), activate=activate)
        assert outcome == {"created": True}

    def test_activation_step_runs_inline_before_enable_returns(self, plugins_guard):
        """The activation step is an ordinary call: done when enable returns."""
        order: List[str] = []

        def activate(capability: PluginCapability) -> None:
            order.append("plugin code")

        enable(_manifest(), set(), activate=activate)
        order.append("enable returned")
        assert order == ["plugin code", "enable returned"]

    def test_product_has_no_process_isolation_machinery(self):
        """No module of the product starts a subprocess, a worker process or a hook."""
        offenders = [
            (path.relative_to(PACKAGE_ROOT).as_posix(), line, what)
            for path, source in _product_sources()
            for line, what in _isolation_hits(source)
        ]
        assert offenders == []

    @pytest.mark.parametrize(
        "planted",
        [
            "import subprocess\n",
            "import multiprocessing.pool\n",
            "from subprocess import run\n",
            "import sys\nsys.addaudithook(lambda *a: None)\n",
        ],
    )
    def test_isolation_scan_flags_planted_machinery(self, planted):
        """Control: the scan above does report each isolation construct."""
        assert _isolation_hits(planted) != []

    def test_isolation_scan_ignores_plain_code(self):
        """Control: the scan does not flag code that isolates nothing."""
        assert _isolation_hits("import os\nvalue = os.getpid()\n") == []


# --------------------------------------------------------------------------- #
# Clause 3: the permissions are checked only on calls made through the         #
# permission object, not on what a plugin's own code does                      #
# --------------------------------------------------------------------------- #


def _use(capability: PluginCapability, operation: str, document: Document) -> None:
    """Make the one call that ``operation`` names through the permission object."""
    if operation == "register_command":
        capability.register_command("probe", _counting_factory, scripting.ParamSchema())
    elif operation == "register_procgen":
        capability.register_procgen("probe", _counting_factory, scripting.ParamSchema())
    elif operation == "read_document":
        capability.read_document(document)
    else:
        capability.run(document, [])


_OPERATION_PERMISSION = {
    "register_command": Capability.REGISTER_COMMAND,
    "register_procgen": Capability.REGISTER_PROCGEN,
    "read_document": Capability.READ_DOCUMENT,
    "run": Capability.WRITE_VIA_COMMAND,
}


class TestPermissionObject:
    """Clause 3, both routes.

    Route 1: a call made through the permission object is checked against the grant.
    Route 2: a call made directly to the command registry is checked by nothing.
    """

    @pytest.mark.parametrize("granted", ALL_CAPABILITIES, ids=lambda c: c.value)
    @pytest.mark.parametrize("operation", sorted(_OPERATION_PERMISSION))
    def test_operation_allowed_only_with_its_own_permission(
        self, registry_guard, operation, granted
    ):
        """Route 1: a call through the object is refused unless granted."""
        capability = PluginCapability("acme", {granted})
        needed = _OPERATION_PERMISSION[operation]
        if granted is needed:
            _use(capability, operation, _document())
        else:
            with pytest.raises(PluginError, match="denied by default"):
                _use(capability, operation, _document())

    def test_object_with_nothing_granted_refuses_every_operation(self, registry_guard):
        """Route 1: deny by default, with no grant all four operations are refused."""
        capability = PluginCapability("acme", set())
        for operation in _OPERATION_PERMISSION:
            with pytest.raises(PluginError):
                _use(capability, operation, _document())

    def test_refusal_names_the_plugin_and_the_missing_permission(self):
        """The refusal says which plugin lacked which permission."""
        capability = PluginCapability("acme", {Capability.READ_DOCUMENT})
        with pytest.raises(PluginError) as caught:
            capability.run(_document(), [])
        assert "acme" in str(caught.value)
        assert Capability.WRITE_VIA_COMMAND.value in str(caught.value)

    def test_refused_registration_leaves_the_registry_unchanged(self, registry_guard):
        """A refused call changes nothing: executable operations are the same."""
        before = scripting.registered_ops()
        capability = PluginCapability("acme", {Capability.READ_DOCUMENT})
        with pytest.raises(PluginError):
            capability.register_command(
                "probe", _counting_factory, scripting.ParamSchema()
            )
        assert scripting.registered_ops() == before

    @given(st.sets(st.sampled_from(ALL_CAPABILITIES)))
    def test_permission_set_decides_read_and_run(self, granted):
        """For any granted set, read and run succeed iff their permission is in it."""
        capability = PluginCapability("acme", set(granted))
        document = _document()
        reads = Capability.READ_DOCUMENT in granted
        runs = Capability.WRITE_VIA_COMMAND in granted
        try:
            capability.read_document(document)
            read_ok = True
        except PluginError:
            read_ok = False
        try:
            capability.run(document, [])
            run_ok = True
        except PluginError:
            run_ok = False
        assert (read_ok, run_ok) == (reads, runs)

    def test_granted_write_goes_through_a_reversible_command(self, registry_guard):
        """With the write permission a run returns one command that can be undone."""
        document = _document()
        buffer = iter_layers(document.frames[0].layers)[0].buffer
        before = buffer.data.copy()
        capability = PluginCapability("acme", {Capability.WRITE_VIA_COMMAND})
        command = capability.run(
            document,
            [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})],
        )
        assert isinstance(command, Command)
        assert tuple(buffer.data[0, 0]) == RED
        command.undo()
        assert (buffer.data == before).all()

    def test_activation_step_is_handed_the_permission_object(self, plugins_guard):
        """An activation step receives a permission object holding exactly the grant."""
        received: List[PluginCapability] = []
        grant = {Capability.READ_DOCUMENT, Capability.REGISTER_COMMAND}
        enable(
            _manifest(tuple(grant)),
            set(grant),
            activate=lambda capability: received.append(capability),
        )
        assert len(received) == 1
        assert isinstance(received[0], PluginCapability)
        assert set(received[0].granted) == grant

    def test_ungranted_call_inside_the_activation_step_fails_the_enable(
        self, plugins_guard
    ):
        """A refused call made through the object during activation is not swallowed."""

        def activate(capability: PluginCapability) -> None:
            capability.run(_document(), [])

        before = loaded_count()
        with pytest.raises(PluginError, match="denied by default"):
            enable(
                _manifest((Capability.READ_DOCUMENT,)),
                {Capability.READ_DOCUMENT},
                activate=activate,
            )
        assert loaded_count() == before

    def test_registered_operation_is_prefixed_with_the_plugins_name(
        self, registry_guard
    ):
        """A name registered through the object is "<plugin>.<name>" and then runs."""
        capability = PluginCapability(
            "acme", {Capability.REGISTER_COMMAND, Capability.WRITE_VIA_COMMAND}
        )
        qualified = capability.register_command(
            "stamp", _counting_factory, scripting.ParamSchema()
        )
        assert qualified == "acme.stamp"
        assert scripting.is_registered("acme.stamp")
        group = capability.run(_document(), [Op("acme.stamp", {})])
        assert isinstance(group, Command)

    def test_built_in_operation_names_contain_no_dot(self):
        """So a prefixed name can never equal a built-in's name."""
        built_ins = (scripting.OP_BATCH_RECOLOUR, scripting.OP_PROCGEN)
        assert set(built_ins) <= set(scripting.registered_ops())
        assert all("." not in name for name in built_ins)

    def test_registering_a_built_in_name_through_the_object_leaves_the_built_in(
        self, registry_guard
    ):
        """The object cannot replace a built-in: the name becomes a prefixed one."""
        capability = PluginCapability("acme", {Capability.REGISTER_COMMAND})
        qualified = capability.register_command(
            scripting.OP_PROCGEN, _counting_factory, scripting.ParamSchema()
        )
        assert qualified == f"acme.{scripting.OP_PROCGEN}"
        assert scripting.is_registered(scripting.OP_PROCGEN)
        assert scripting.is_registered(qualified)

    def test_object_has_no_way_to_remove_an_operation(self):
        """Control: the object offers no unregister call; removal needs a direct one."""
        capability = PluginCapability("acme", set(ALL_CAPABILITIES))
        assert not hasattr(capability, "unregister_command")

    def test_read_permission_returns_the_document_it_is_passed_not_a_copy(self):
        """A read permission returns the very object it was given."""
        document = _document()
        capability = PluginCapability("acme", {Capability.READ_DOCUMENT})
        assert capability.read_document(document) is document

    def test_read_permission_holds_no_document_of_its_own(self):
        """The object keeps no document: called with nothing else it can return none."""
        assert "document" not in "".join(PluginCapability.__slots__)
        capability = PluginCapability("acme", {Capability.READ_DOCUMENT})
        first, second = _document(), _document()
        assert capability.read_document(first) is first
        assert capability.read_document(second) is second

    def test_code_that_skips_the_object_registers_with_nothing_granted(
        self, plugins_guard, registry_guard
    ):
        """Route 2, registering: a direct registry call by code granted nothing."""
        direct = "acme.direct"

        def activate(capability: PluginCapability) -> None:
            scripting.register_command(
                direct, _counting_factory, scripting.ParamSchema()
            )

        handle = enable(_manifest(), set(), activate=activate)
        assert handle.capability.granted == ()
        assert scripting.is_registered(direct)

    def test_code_that_skips_the_object_can_remove_a_built_in(self, registry_guard):
        """Route 2, removing: a direct registry call can remove a built-in operation."""
        try:
            scripting.unregister_command(scripting.OP_BATCH_RECOLOUR)
            assert not scripting.is_registered(scripting.OP_BATCH_RECOLOUR)
        finally:
            # Put the built-in back by the module's own idempotent installer.
            scripting._register_builtins()
        assert scripting.is_registered(scripting.OP_BATCH_RECOLOUR)

    def test_direct_registration_of_an_existing_name_is_refused(self, registry_guard):
        """Control (route 2): the registry's own rule refuses a duplicate name.

        The registry is not unguarded in every respect: it checks names, not grants.
        """
        with pytest.raises(scripting.ScriptError, match="already registered"):
            scripting.register_command(
                scripting.OP_PROCGEN, _counting_factory, scripting.ParamSchema()
            )

    def test_code_that_skips_the_object_dispatches_with_nothing_granted(
        self, plugins_guard, registry_guard
    ):
        """Route 2, dispatching: a direct registry call by code granted nothing works.

        The activation step of a plugin granted nothing runs a built-in operation on a
        document with the registry's own dispatch and the document changes.
        """
        document = _document()
        buffer = iter_layers(document.frames[0].layers)[0].buffer
        before = buffer.data.copy()
        ops = [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]
        dispatched: List[Command] = []

        def activate(capability: PluginCapability) -> None:
            dispatched.append(scripting.dispatch(document, ops))

        handle = enable(_manifest(), set(), activate=activate)
        assert handle.capability.granted == ()
        assert len(dispatched) == 1
        assert isinstance(dispatched[0], Command)
        assert tuple(buffer.data[0, 0]) == RED
        dispatched[0].undo()
        assert (buffer.data == before).all()

    def test_same_dispatch_through_the_object_with_nothing_granted_is_refused(
        self, plugins_guard
    ):
        """Control (route 1): the dispatch above is refused when asked of the object.

        Same document, same operations, same empty grant: only the route differs, and
        the document is left as it was.
        """
        document = _document()
        buffer = iter_layers(document.frames[0].layers)[0].buffer
        before = buffer.data.copy()
        ops = [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]

        def activate(capability: PluginCapability) -> None:
            capability.run(document, ops)

        with pytest.raises(PluginError, match="denied by default"):
            enable(_manifest(), set(), activate=activate)
        assert (buffer.data == before).all()

    def test_direct_dispatch_of_an_unregistered_name_is_refused(self):
        """Control (route 2): the registry's own rule refuses a name it does not hold.

        So a successful direct dispatch is the registry running a registered
        operation, not a call that nothing looks at.
        """
        document = _document()
        buffer = iter_layers(document.frames[0].layers)[0].buffer
        before = buffer.data.copy()
        with pytest.raises(scripting.ScriptError):
            scripting.dispatch(document, [Op("no_such_operation", {})])
        assert (buffer.data == before).all()

    def test_disable_removes_only_operations_registered_through_the_object(
        self, plugins_guard, registry_guard
    ):
        """Disable removes what went through the object, not direct registrations."""

        def activate(capability: PluginCapability) -> None:
            capability.register_command(
                "via_object", _counting_factory, scripting.ParamSchema()
            )
            scripting.register_command(
                "acme.direct", _counting_factory, scripting.ParamSchema()
            )

        handle = enable(
            _manifest((Capability.REGISTER_COMMAND,)),
            {Capability.REGISTER_COMMAND},
            activate=activate,
        )
        assert scripting.is_registered("facts.plugin.via_object")
        handle.disable()
        assert not scripting.is_registered("facts.plugin.via_object")
        assert scripting.is_registered("acme.direct")  # direct code is not undone

    def test_disable_does_not_undo_what_plugin_code_already_did(
        self, plugins_guard, tmp_path
    ):
        """Disable leaves a file the plugin's own code already wrote."""
        written = tmp_path / "kept.txt"

        def activate(capability: PluginCapability) -> None:
            written.write_text("done", encoding="utf-8")

        handle = enable(_manifest(), set(), activate=activate)
        handle.disable()
        assert not handle.active
        assert written.read_text(encoding="utf-8") == "done"

    def test_disable_with_nothing_registered_removes_nothing(
        self, plugins_guard, registry_guard
    ):
        """With no activation step nothing is registered, so disable removes none."""
        before = scripting.registered_ops()
        handle = enable(_manifest((Capability.REGISTER_COMMAND,)), set())
        assert handle.capability.registered_ops == ()
        handle.disable()
        assert scripting.registered_ops() == before

    def test_vocabulary_names_registering_operations_and_nothing_raw(self):
        """The vocabulary is the four named permissions: no file, network or UI one."""
        assert {cap.value for cap in Capability} == {
            "read_document",
            "write_via_command",
            "register_command",
            "register_procgen",
        }


# --------------------------------------------------------------------------- #
# "In this release the app has no step that loads or runs a plugin's code"     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def probe_plugin(tmp_path, monkeypatch) -> Iterator[Dict[str, object]]:
    """Install, on a scratch sys.path only, a real distribution in the plugin group.

    Its module writes a marker file when imported, so a marker proves the plugin's
    code ran and its absence proves it did not. Nothing is installed anywhere else.
    """
    site = tmp_path / "site"
    site.mkdir()
    marker = tmp_path / "plugin_module_ran.txt"
    module = "facts_probe_plugin_module"
    (site / f"{module}.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    dist_info = site / "facts_probe_plugin-3.4.5.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: facts-probe-plugin\nVersion: 3.4.5\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        f"[{ENTRY_POINT_GROUP}]\nfacts-probe = {module}\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()
    try:
        yield {"marker": marker, "module": module}
    finally:
        sys.modules.pop(module, None)


def _probe_manifest(found: Tuple[PluginManifest, ...]) -> PluginManifest:
    return next(m for m in found if m.name == "facts-probe")


class TestNoStepRunsPluginCode:
    """No step of the host or the app loads or runs a plugin's code."""

    def test_discovery_lists_name_and_version_without_running_the_plugin(
        self, probe_plugin
    ):
        """Discovery reads an installed plugin's name and version and runs nothing."""
        found = discover()
        manifest = _probe_manifest(found)
        assert manifest.version == "3.4.5"
        assert manifest.capabilities == ()
        assert not probe_plugin["marker"].exists()
        assert probe_plugin["module"] not in sys.modules

    def test_loading_the_entry_point_does_run_the_module(self, probe_plugin):
        """Control: loading the same entry point runs the plugin's module code."""
        from importlib import metadata

        points = [
            ep
            for ep in metadata.entry_points(group=ENTRY_POINT_GROUP)
            if ep.name == "facts-probe"
        ]
        assert len(points) == 1
        points[0].load()
        assert probe_plugin["marker"].read_text() == "ran"

    def test_discovered_plugin_can_be_granted_no_permission(
        self, plugins_guard, probe_plugin
    ):
        """A discovered plugin shows no permissions, so granting any is refused."""
        manifest = _probe_manifest(discover())
        with pytest.raises(PluginError, match="undeclared"):
            enable(manifest, {Capability.READ_DOCUMENT})
        assert loaded_count() == 0

    def test_enable_and_disable_without_an_activation_step_run_nothing(
        self, plugins_guard, probe_plugin
    ):
        """Enabling records the grant and marks it enabled; no plugin code runs."""
        manifest = _probe_manifest(discover())
        handle = enable(manifest, set())
        assert handle.active
        assert not probe_plugin["marker"].exists()
        assert probe_plugin["module"] not in sys.modules
        handle.disable()
        assert not probe_plugin["marker"].exists()
        assert probe_plugin["module"] not in sys.modules

    def test_a_supplied_activation_step_is_the_only_way_plugin_code_runs(
        self, plugins_guard, probe_plugin
    ):
        """Control: the same enable with a step that imports the module runs it."""
        manifest = _probe_manifest(discover())
        enable(
            manifest,
            set(),
            activate=lambda capability: importlib.import_module(
                str(probe_plugin["module"])
            ),
        )
        assert probe_plugin["marker"].read_text() == "ran"

    def test_loading_a_manifest_from_disk_runs_no_plugin_and_checks_no_install(
        self, plugins_guard, tmp_path, monkeypatch, probe_plugin
    ):
        """A manifest file is read as data, not matched against what is installed."""
        manifest_file = tmp_path / "unrelated.json"
        manifest_file.write_text(
            '{"name": "not-installed-anywhere", "version": "9", '
            f'"api_version": "{plugins.PLUGIN_API_VERSION}", '
            '"capabilities": ["read_document"]}',
            encoding="utf-8",
        )

        def trap(*args, **kwargs):
            raise AssertionError("manifest loading must not consult discovery")

        monkeypatch.setattr(plugins, "discover", trap)
        manifest = load_manifest(manifest_file)
        assert manifest.name == "not-installed-anywhere"
        assert not probe_plugin["marker"].exists()
        handle = enable(manifest, {Capability.READ_DOCUMENT})
        assert handle.active

    def test_manifest_is_not_checked_against_the_plugin_code(self, plugins_guard):
        """Consent covers the manifest only: the host never inspects what code does."""
        executed: List[str] = []

        def activate(capability: PluginCapability) -> None:
            executed.append("did something the manifest never declared")

        enable(_manifest(), set(), activate=activate)
        assert executed == ["did something the manifest never declared"]

    def test_product_source_has_no_step_that_loads_or_runs_plugin_code(self):
        """No module of the product loads an entry point, imports dynamically or passes
        an activation step: the host's only run statement has no caller."""
        offenders = [
            (path.relative_to(PACKAGE_ROOT).as_posix(), line, what)
            for path, source in _product_sources()
            for line, what in _plugin_code_running_hits(source)
        ]
        assert offenders == []

    @pytest.mark.parametrize(
        "planted, expected",
        [
            ("ep.load()\n", "entry-point .load()"),
            ("importlib.import_module('x')\n", "import_module"),
            ("spec.loader.exec_module(m)\n", "exec_module"),
            ("import runpy\n", "import runpy"),
            ("site.addsitedir(p)\n", "addsitedir"),
            ("sys.path.insert(0, p)\n", "sys.path.insert"),
            ("enable(manifest, granted, activate=run_it)\n", "activate= keyword"),
        ],
    )
    def test_plugin_code_scan_flags_each_planted_construct(self, planted, expected):
        """Control: the scan reports each way of loading or running plugin code."""
        assert expected in [what for _, what in _plugin_code_running_hits(planted)]

    def test_plugin_code_scan_ignores_ordinary_calls(self):
        """Control: file and JSON loads with arguments are not plugin loading."""
        source = "json.load(handle)\nlist.append(1)\nvalues.insert(0, 2)\n"
        assert _plugin_code_running_hits(source) == []

    def test_only_the_manager_panel_calls_enable_and_passes_no_activation_step(self):
        """The one caller of enable passes the manifest and the grant only."""
        callers: List[Tuple[str, List[str]]] = []
        for path, source in _product_sources():
            for node in ast.walk(ast.parse(source)):
                if (
                    isinstance(node, ast.Call)
                    and _call_name(node) == "enable"
                    and len(node.args) == 2
                ):
                    callers.append(
                        (
                            path.relative_to(PACKAGE_ROOT).as_posix(),
                            [k.arg or "**" for k in node.keywords],
                        )
                    )
        assert callers == [("ui/plugin_manager_panel.py", [])]


# --------------------------------------------------------------------------- #
# Enabling is recorded in memory only                                          #
# --------------------------------------------------------------------------- #


class TestHostState:
    """Enabling records the approved permissions in memory and saves nothing."""

    def test_enable_records_the_grant_and_marks_the_plugin_enabled(self, plugins_guard):
        """The handle is active and holds exactly the permissions that were granted."""
        grant = {Capability.READ_DOCUMENT, Capability.WRITE_VIA_COMMAND}
        before = loaded_count()
        handle = enable(_manifest(tuple(grant)), set(grant))
        assert handle.active
        assert set(handle.capability.granted) == grant
        assert loaded_count() == before + 1

    def test_enable_and_disable_write_no_file(
        self, plugins_guard, tmp_path, monkeypatch
    ):
        """Enabling then disabling leaves the working directory exactly as it was."""
        monkeypatch.chdir(tmp_path)
        before = sorted(p.name for p in tmp_path.iterdir())
        handle = enable(
            _manifest((Capability.READ_DOCUMENT,)), {Capability.READ_DOCUMENT}
        )
        handle.disable()
        assert sorted(p.name for p in tmp_path.iterdir()) == before

    def test_host_module_has_no_file_or_persistence_use(self):
        """The host imports nothing that could save a consent and opens no file."""
        source = Path(plugins.__file__).read_bytes().decode("utf-8")
        assert _persistence_hits(source) == []

    @pytest.mark.parametrize(
        "planted", ["import json\n", "from pathlib import Path\n", "open('x')\n"]
    )
    def test_persistence_scan_flags_planted_constructs(self, planted):
        """Control: the scan above reports file and persistence use."""
        assert _persistence_hits(planted) != []

    def test_consent_does_not_outlive_the_process(self, tmp_path):
        """A plugin enabled in one process is not enabled in the next one."""
        enabled = _python(
            "from pixelart_creator.logic import plugins as p\n"
            "m = p.validate_manifest({'name': 'once', 'version': '1', "
            "'api_version': p.PLUGIN_API_VERSION, 'capabilities': ['read_document']})\n"
            "p.enable(m, {p.Capability.READ_DOCUMENT})\n"
            "print(p.loaded_count())\n",
            tmp_path,
        )
        fresh = _python(
            "from pixelart_creator.logic import plugins as p\n"
            "print(p.loaded_count())\n",
            tmp_path,
        )
        assert (enabled, fresh) == ("1", "0")


# --------------------------------------------------------------------------- #
# The headless runner and the plugin host                                      #
# --------------------------------------------------------------------------- #


class TestAutomationRunner:
    """The ``pixelart-run`` path never touches the plugin host."""

    def test_replay_succeeds_with_the_plugin_host_made_unusable(
        self, tmp_path, monkeypatch
    ):
        """Discovery, enabling and manifest validation are trapped; the run exits 0."""

        def trap(*args, **kwargs):
            raise AssertionError("the runner must not touch the plugin host")

        for owner in (plugins, macro_io):
            for name in ("discover", "enable", "validate_manifest"):
                if hasattr(owner, name):
                    monkeypatch.setattr(owner, name, trap)
        project = _document()
        input_path = save_project(project, tmp_path / "in.pixproj")
        macro_path = save_macro(
            record(
                [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]
            ),
            tmp_path / "job.pixmacro",
        )
        output_path = tmp_path / "out.pixproj"
        exit_code = automation_cli.main(
            [
                "--input",
                str(input_path),
                "--macro",
                str(macro_path),
                "--output",
                str(output_path),
            ]
        )
        assert exit_code == 0
        assert output_path.exists()

    def test_runner_module_names_no_discovery_or_enable(self):
        """The runner imports the host's error class only, never discover or enable."""
        assert not hasattr(automation_cli, "discover")
        assert not hasattr(automation_cli, "enable")

    def test_a_fresh_runner_process_holds_only_the_built_in_operations(self, tmp_path):
        """A new process importing the runner has no plugin enabled and no plugin op."""
        printed = _python(
            "from pixelart_creator.data import automation_cli\n"
            "from pixelart_creator.logic import plugins, scripting\n"
            "print(sorted(scripting.registered_ops()), plugins.loaded_count())\n",
            tmp_path,
        )
        expected = sorted([scripting.OP_BATCH_RECOLOUR, scripting.OP_PROCGEN])
        assert printed == f"{expected} 0"

    def test_an_enabled_plugin_operation_does_not_exist_in_another_process(
        self, tmp_path
    ):
        """Control: an operation registered here is absent from the runner's process."""
        name: Optional[str] = None
        capability = PluginCapability("acme", {Capability.REGISTER_COMMAND})
        try:
            name = capability.register_command(
                "here_only", _counting_factory, scripting.ParamSchema()
            )
            assert scripting.is_registered(name)
            printed = _python(
                "from pixelart_creator.logic import scripting\n"
                "print(scripting.is_registered('acme.here_only'))\n",
                tmp_path,
            )
            assert printed == "False"
        finally:
            if name is not None and scripting.is_registered(name):
                scripting.unregister_command(name)
