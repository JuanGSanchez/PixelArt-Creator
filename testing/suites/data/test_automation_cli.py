"""Tests for pixelart_creator.data.automation_cli — headless automation driver.

Covers REQ-P8-LOGIC-014 (exit codes 0/1/2 with defensive .pixproj + .pixmacro
loading) and REQ-P8-UI-010 support (CLI==GUI parity: running a macro via
``automation_cli.main`` equals running it via the dispatcher/``replay``
in-process — the SAME trusted engine). Tests ``main`` directly (the
``pixelart-run`` console script is wired by AGT-09, not here).
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.data import automation_cli
from pixelart_creator.data.automation_cli import build_parser, main
from pixelart_creator.data.macro_io import load_macro, save_macro
from pixelart_creator.data.project_io import load_project, save_project
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.macro import Macro, Op, record, replay
from pixelart_creator.logic.palette import Palette

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _doc() -> Document:
    return Document(6, 6, palette=Palette([RED, BLUE, (0, 255, 0, 255)]))


def _leaf(doc):
    return iter_layers(doc.frames[0].layers)[0].buffer


def _fixture(tmp_path, ops):
    """Write an input .pixproj + a .pixmacro of ``ops``; return their paths."""
    input_path = save_project(_doc(), tmp_path / "in.pixproj")
    macro_path = save_macro(record(ops), tmp_path / "job.pixmacro")
    output_path = tmp_path / "out.pixproj"
    return input_path, macro_path, output_path


_OPS = [
    Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=9),
    Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
]


# --------------------------------------------------------------------------- #
# parser + helpers                                                             #
# --------------------------------------------------------------------------- #


def test_build_parser_requires_core_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])  # missing required --input/--macro/--output


def test_parse_params_int_and_string():
    out = automation_cli._parse_params(["n=5", "name=hello"])
    assert out == {"n": 5, "name": "hello"}


def test_parse_params_rejects_missing_equals():
    with pytest.raises(ValueError):
        automation_cli._parse_params(["noequals"])


def test_parse_params_rejects_empty_key():
    with pytest.raises(ValueError):
        automation_cli._parse_params(["=value"])


def test_apply_overrides_fills_seed_only_when_absent():
    macro = Macro(
        "1",
        "0.8.0",
        (Op("procgen", {"algorithm": "value_noise"}, seed=None), Op("x", {}, seed=7)),
    )
    out = automation_cli._apply_overrides(macro, seed=99, overrides={"k": 1})
    assert out.ops[0].seed == 99  # filled (had none)
    assert out.ops[1].seed == 7  # recorded seed wins
    assert out.ops[0].params["k"] == 1  # override merged
    assert out.ops[1].params["k"] == 1


def test_apply_overrides_noop_when_nothing_to_do():
    macro = record([Op("x")])
    assert automation_cli._apply_overrides(macro, seed=None, overrides={}) is macro


# --------------------------------------------------------------------------- #
# main — exit code 0 (success)                                                 #
# --------------------------------------------------------------------------- #


def test_main_success_returns_zero(tmp_path):
    input_path, macro_path, output_path = _fixture(tmp_path, _OPS)
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
        ]
    )
    assert rc == 0
    assert output_path.exists()


def test_main_seed_override_applies(tmp_path):
    # A seedless procgen op gets --seed; output is written.
    ops = [Op("procgen", {"algorithm": "value_noise"})]
    input_path, macro_path, output_path = _fixture(tmp_path, ops)
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
            "--seed",
            "5",
        ]
    )
    assert rc == 0


# --------------------------------------------------------------------------- #
# main — exit code 2 (bad args / defensive load error)                         #
# --------------------------------------------------------------------------- #


def test_main_missing_required_arg_exits_two():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_main_bad_param_returns_two(tmp_path):
    input_path, macro_path, output_path = _fixture(tmp_path, _OPS)
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
            "--param",
            "noequals",
        ]
    )
    assert rc == 2


def test_main_missing_input_returns_two(tmp_path):
    _in, macro_path, output_path = _fixture(tmp_path, _OPS)
    rc = main(
        [
            "--input",
            str(tmp_path / "does_not_exist.pixproj"),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
        ]
    )
    assert rc == 2


def test_main_malformed_macro_returns_two(tmp_path):
    input_path, _m, output_path = _fixture(tmp_path, _OPS)
    bad_macro = tmp_path / "bad.pixmacro"
    bad_macro.write_text("{not valid json", encoding="utf-8")
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(bad_macro),
            "--output",
            str(output_path),
        ]
    )
    assert rc == 2


# --------------------------------------------------------------------------- #
# main — exit code 1 (runtime / write error)                                   #
# --------------------------------------------------------------------------- #


def test_main_unknown_op_returns_one(tmp_path):
    # A well-formed macro whose op is unknown → ScriptError at replay → exit 1.
    input_path, macro_path, output_path = _fixture(
        tmp_path, [Op("this_op_does_not_exist", {})]
    )
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
        ]
    )
    assert rc == 1


def test_main_write_error_returns_one(tmp_path):
    input_path, macro_path, _out = _fixture(tmp_path, _OPS)
    unwritable = tmp_path / "no_such_dir" / "out.pixproj"  # parent missing
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(unwritable),
        ]
    )
    assert rc == 1


# --------------------------------------------------------------------------- #
# CLI == GUI parity (REQ-P8-UI-010) — same trusted engine                       #
# --------------------------------------------------------------------------- #


def test_cli_result_identical_to_in_process_replay(tmp_path):
    # REQ-P8-LOGIC-014 / SC-L014-1 (R-29, data half): CLI==GUI result-identity.
    # Running the macro via automation_cli.main == running it via replay in-process.
    input_path, macro_path, output_path = _fixture(tmp_path, _OPS)
    rc = main(
        [
            "--input",
            str(input_path),
            "--macro",
            str(macro_path),
            "--output",
            str(output_path),
        ]
    )
    assert rc == 0
    cli_doc = load_project(output_path)

    # Reference: load the SAME input fresh and replay the SAME macro in-process.
    ref_doc = load_project(input_path)
    replay(ref_doc, load_macro(macro_path))

    assert np.array_equal(_leaf(cli_doc).data, _leaf(ref_doc).data)
