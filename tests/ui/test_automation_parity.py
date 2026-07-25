"""GUI == CLI state-identity — SC-UI-010-1 (REQ-P8-UI-010, REQ-P8-LOGIC-014).

The GUI automation controls drive the SAME trusted ``logic.scripting`` dispatcher
(via ``logic.macro.replay``) as the headless ``data.automation_cli`` — so a fixed
macro on a fixed document yields a STATE-IDENTICAL result whether run via the GUI
worker or the CLI. The CLI is called in-process (the ``pixelart-run`` console
script is intentionally not relied upon — it is not wired yet). Headless; both
themes.
"""

from __future__ import annotations

from pixelart_creator.data import automation_cli
from pixelart_creator.data.macro_io import save_macro
from pixelart_creator.data.project_io import load_project, save_project
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._automation_helpers import (
    GREEN,
    RED,
    arrays_equal,
    batch_recolour_op,
    buffer_of,
    macro_of,
    paint,
    procgen_op,
    replay,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _assert_gui_equals_cli(qtbot, tmp_path, macro):
    win = _window(qtbot)
    tab = win.active_tab()
    paint(tab.document, RED)  # deterministic starting content

    # Persist the EXACT initial document so the CLI loads an equivalent Document.
    pixproj = tmp_path / "doc.pixproj"
    save_project(tab.document, pixproj)
    macro_path = save_macro(macro, tmp_path / "m.pixmacro")

    # GUI path: replay via the real off-thread worker (mutates the live document).
    replay(qtbot, win, macro)
    gui_buffer = buffer_of(win.active_document()).copy()

    # CLI path: in-process automation_cli.main on the same saved doc + macro.
    out = tmp_path / "out.pixproj"
    argv = [
        "--input",
        str(pixproj),
        "--macro",
        str(macro_path),
        "--output",
        str(out),
    ]
    assert automation_cli.main(argv) == 0
    cli_doc = load_project(out)

    # State-identical: both drove the same pure engine; the GUI adds no engine logic.
    assert arrays_equal(gui_buffer, buffer_of(cli_doc))


def test_sc_ui_010_gui_procgen_replay_equals_cli(qtbot, tmp_path):
    """SC-UI-010-1: a seeded procgen macro → identical GUI and CLI documents."""
    _assert_gui_equals_cli(qtbot, tmp_path, macro_of(procgen_op(seed=11)))


def test_sc_ui_010_gui_batch_recolour_replay_equals_cli(qtbot, tmp_path):
    """SC-UI-010-1: a batch-recolour macro → identical GUI and CLI documents."""
    _assert_gui_equals_cli(
        qtbot, tmp_path, macro_of(batch_recolour_op(src=RED, dst=GREEN))
    )
