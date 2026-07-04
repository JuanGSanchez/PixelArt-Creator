"""Security invariant #1 — NO ``eval``/``exec`` on untrusted input (REQ-P8-LOGIC-003).

This is the paramount, S1-level Phase-8 invariant (Article VII, SC-L003-1): the
automation engine executes **data**, never a language. Crafted / malicious input
(an unknown op-name, a param that *looks* like code, a serialised string like
``"__import__('os').system(...)"``) must be **rejected with a typed error or kept
inert as data** — never executed as code. These tests prove it two ways:

1. **Static** — an AST scan of every automation module asserts there is no
   ``eval`` / ``exec`` / ``compile`` / ``__import__`` **call** anywhere on the
   path (the only textual hits are docstrings *describing* the invariant).
2. **Behavioural** — crafted ops / macros are fed to the dispatcher and loader
   and asserted to be rejected or held as inert data with **no side effect**.
"""

from __future__ import annotations

import ast
import inspect
import json

import pytest

from pixelart_creator.data import automation_cli, macro_io
from pixelart_creator.logic import (
    batch_ops,
    history,
    macro,
    plugins,
    procgen,
    scripting,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.palette import Palette

RED = (255, 0, 0, 255)

_FORBIDDEN = {"eval", "exec", "compile", "__import__"}
_AUTOMATION_MODULES = (
    scripting,
    macro,
    plugins,
    procgen,
    batch_ops,
    history,
    macro_io,
    automation_cli,
)


def _forbidden_calls(module) -> list:
    """Return the forbidden builtin call-names invoked in ``module``'s source."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _FORBIDDEN:
            found.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN:
            found.append(func.attr)
    return found


@pytest.mark.parametrize("module", _AUTOMATION_MODULES, ids=lambda m: m.__name__)
def test_no_eval_exec_compile_call_anywhere(module):
    # SC-L003-1: the engine is eval-free BY CONSTRUCTION — no interpreter to escape.
    assert (
        _forbidden_calls(module) == []
    ), f"{module.__name__} must not call eval/exec/compile/__import__"


def test_unknown_op_name_rejected_never_executed():
    # A crafted op-name that *looks* like code is an unknown op → ScriptError,
    # and is NEVER dispatched to any factory.
    doc = Document(4, 4, palette=Palette([RED]))
    for crafted in ("__import__('os').system('echo hi')", "eval", "exec", "danger"):
        with pytest.raises(scripting.ScriptError):
            scripting.dispatch(doc, [Op(crafted, {})])


def test_code_like_param_value_is_inert_data(tmp_path):
    # A param whose *value* is a code-looking string is accepted only as JSON-native
    # data (procgen allow_extra); it is never evaluated. Assert no side effect: a
    # sentinel file the "code" would create is absent, and the op runs as pure data.
    doc = Document(4, 4, palette=Palette([RED]))
    sentinel = tmp_path / "pwned.txt"
    payload = f"__import__('pathlib').Path({str(sentinel)!r}).write_text('x')"
    cmd = scripting.dispatch(
        doc,
        [Op("procgen", {"algorithm": "value_noise", "evil": payload}, seed=1)],
    )
    # The op executed as data (a reversible command was produced) …
    cmd.undo()
    # … and the code-looking string was NOT executed.
    assert not sentinel.exists()


def test_malicious_pixmacro_loads_as_inert_data(tmp_path):
    # A .pixmacro carrying a code-looking string loads defensively (eval-free):
    # the string survives as literal DATA in op.params — never executed.
    path = tmp_path / "evil.pixmacro"
    exploit = "__import__('os').system('rm -rf /')"
    payload = {
        "format": "pixmacro",
        "schema_version": "1",
        "min_app_version": "0.8.0",
        "ops": [
            {
                "op": "procgen",
                "params": {"algorithm": "value_noise", "note": exploit},
                "seed": 3,
                "api_version": "1",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = macro_io.load_macro(path)
    assert loaded.ops[0].params["note"] == exploit  # kept as data, not run
    assert loaded.ops[0].name == "procgen"


def test_malicious_op_name_in_pixmacro_rejected_on_replay(tmp_path):
    # Even a well-formed .pixmacro whose op-name is crafted loads (structure ok)
    # but is REJECTED by the trusted dispatcher on replay — never executed.
    path = tmp_path / "craft.pixmacro"
    payload = {
        "format": "pixmacro",
        "schema_version": "1",
        "min_app_version": "0.8.0",
        "ops": [{"op": "eval", "params": {}, "seed": None, "api_version": "1"}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = macro_io.load_macro(path)
    doc = Document(4, 4, palette=Palette([RED]))
    with pytest.raises(scripting.ScriptError):
        macro.replay(doc, loaded)


def test_loader_uses_json_not_eval(tmp_path):
    # Defensive proof the loader is data-only: a Python-literal-but-not-JSON file
    # (single quotes) fails as invalid JSON — an eval-based loader would accept it.
    path = tmp_path / "pyliteral.pixmacro"
    path.write_text("{'format': 'pixmacro'}", encoding="utf-8")
    with pytest.raises(macro_io.MacroIOError):
        macro_io.load_macro(path)
