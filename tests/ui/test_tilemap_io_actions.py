"""Phase-6 Tiled JSON import/export UI-action tests (REQ-P6-UI-011/-012, round-trip).

pytest-qt, headless, both themes (autouse ``theme`` fixture). Drives the thin Qt
front-end ``tilemap_io_actions`` over ``data/tiled_io``: export writes a valid Tiled
map to a portable path (SC-UI-011-1); export->import through the UI yields an
equivalent map (SC-UI-012-1 / REQ-P6-DATA-002); and the typed load errors — zstd
layer data, external ``.tsx`` tileset, out-of-range gid, malformed JSON — surface as
a user-facing warning and return ``None`` WITHOUT crashing the UI (SC-UI-012-1).
The ``QFileDialog`` calls are monkeypatched so the tests are deterministic/headless.
"""

from __future__ import annotations

import base64
import json

import pytest
from PySide6.QtWidgets import QWidget

from pixelart_creator.data.tiled_io import write_tiled_json
from pixelart_creator.ui import tilemap_io_actions as io_actions


@pytest.fixture
def parent_widget(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _stamped_map(make_tilemap_setup):
    """Return a tilemap with a couple of stamped (incl. flipped) instances."""
    from pixelart_creator.logic.tilemap import FLIPPED_HORIZONTALLY_FLAG

    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)
    tilemap.make_stamp_command(0, 1, 1, tileset.first_gid).execute()
    tilemap.make_stamp_command(
        0, 2, 1, tileset.first_gid | FLIPPED_HORIZONTALLY_FLAG
    ).execute()
    return tileset, tilemap


def test_sc_ui_011_1_export_writes_valid_tiled_json(
    qtbot, monkeypatch, tmp_path, parent_widget, make_tilemap_setup
):
    """SC-UI-011-1: export writes a valid Tiled map to the chosen portable path."""
    _tileset, tilemap = _stamped_map(make_tilemap_setup)
    out = tmp_path / "level.tmj"
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "Tiled JSON (*.tmj *.json)")),
    )

    written = io_actions.export_tilemap_dialog(parent_widget, tilemap)
    assert written is not None
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["type"] == "map"  # a valid Tiled map object
    assert payload["tilewidth"] == 16 and payload["tileheight"] == 16
    assert payload["tilesets"] and payload["layers"]


def test_sc_ui_012_1_export_import_round_trip_is_equivalent(
    qtbot, monkeypatch, tmp_path, parent_widget, make_tilemap_setup
):
    """SC-UI-012-1 / REQ-P6-DATA-002: export->import through the UI is lossless."""
    _tileset, tilemap = _stamped_map(make_tilemap_setup)
    out = tmp_path / "roundtrip.tmj"
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )

    assert io_actions.export_tilemap_dialog(parent_widget, tilemap) is not None
    imported = io_actions.import_tilemap_dialog(parent_widget)
    assert imported is not None
    # Equivalent map: same geometry, layer count, per-cell gid + flip flags.
    assert imported.tile_width == tilemap.tile_width
    assert len(imported.layers) == len(tilemap.layers)
    for x, y, gid in tilemap.layers[0].cells():
        assert imported.layers[0].get(x, y) == gid  # gid incl. flip nibble preserved


# --------------------------------------------------------------------------- #
# T-23 (AGT-06 audit, regression for C-02) — window-level import is ONE macro #
# --------------------------------------------------------------------------- #


def test_t23_window_import_tiled_is_one_undo_removing_everything(
    qtbot, monkeypatch, tmp_path, make_tilemap_setup
):
    """T-23 (regression for C-02): ``Main_Window._on_import_tiled`` pushes the
    imported tileset attach(es) + the tilemap add as ONE undo macro — a single
    undo removes the imported tilemap AND detaches every imported tileset
    (CF-15). Builds a genuine standalone imported ``Tilemap`` via a real
    export -> import round trip (not a hand-built stub) so the tileset list
    reflects what the loader actually returns."""
    # Regression test for C-02 — proven by reversion in the commit pass.
    from pixelart_creator.ui import main_window as main_window_module
    from pixelart_creator.ui import tilemap_io_actions as io_actions

    parent = QWidget()
    qtbot.addWidget(parent)
    _tileset, tilemap = _stamped_map(make_tilemap_setup)
    out = tmp_path / "t23_import.tmj"
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    assert io_actions.export_tilemap_dialog(parent, tilemap) is not None
    imported = io_actions.import_tilemap_dialog(parent)
    assert imported is not None
    assert len(imported.tilesets) >= 1

    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    tilesets_before = len(record.document.tilesets)
    tilemaps_before = len(record.document.tilemaps)
    stack_count_before = record.stack.count()

    monkeypatch.setattr(
        main_window_module, "import_tilemap_dialog", lambda parent: imported
    )
    win._on_import_tiled()

    # Exactly ONE macro command for the whole import (attaches + add).
    assert record.stack.count() == stack_count_before + 1
    assert len(record.document.tilesets) == tilesets_before + len(imported.tilesets)
    assert len(record.document.tilemaps) == tilemaps_before + 1

    record.stack.undo()

    # A SINGLE undo removes the imported tilemap AND detaches every imported
    # tileset — the C-02 fix (a ``beginMacro``/``endMacro`` around both pushes).
    assert len(record.document.tilesets) == tilesets_before
    assert len(record.document.tilemaps) == tilemaps_before


def _write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_map(gid_data, *, extra_map=None, extra_layer=None, tilesets=None):
    layer = {
        "type": "tilelayer",
        "name": "L",
        "id": 1,
        "width": 2,
        "height": 1,
        "x": 0,
        "y": 0,
        "visible": True,
        "opacity": 1.0,
        "data": gid_data,
    }
    if extra_layer:
        layer.update(extra_layer)
    obj = {
        "type": "map",
        "version": "1.10",
        "tiledversion": "1.12.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "infinite": False,
        "width": 2,
        "height": 1,
        "tilewidth": 16,
        "tileheight": 16,
        "tilesets": (
            tilesets
            if tilesets is not None
            else [
                {
                    "firstgid": 1,
                    "name": "ts",
                    "tilewidth": 16,
                    "tileheight": 16,
                    "tilecount": 4,
                    "columns": 4,
                    "imagewidth": 64,
                    "imageheight": 16,
                }
            ]
        ),
        "layers": [layer],
        "nextlayerid": 2,
        "nextobjectid": 1,
    }
    if extra_map:
        obj.update(extra_map)
    return obj


@pytest.mark.parametrize(
    "name,payload_factory",
    [
        # zstd-compressed layer data (unsupported dependency, S8).
        (
            "zstd.tmj",
            lambda: _base_map(
                base64.b64encode(b"\x00" * 8).decode("ascii"),
                extra_layer={"encoding": "base64", "compression": "zstd"},
            ),
        ),
        # external .tsx (XML) tileset (unsupported; only embedded / .tsj).
        (
            "tsx.tmj",
            lambda: _base_map(
                [1, 2],
                tilesets=[{"firstgid": 1, "source": "tiles.tsx"}],
            ),
        ),
        # gid out of every referenced tileset range (tilecount 4 -> gid 99 invalid).
        ("oob_gid.tmj", lambda: _base_map([1, 99])),
    ],
)
def test_sc_ui_012_1_typed_load_errors_surface_without_crash(
    qtbot,
    monkeypatch,
    tmp_path,
    parent_widget,
    name,
    payload_factory,
):
    """SC-UI-012-1: zstd / .tsx / out-of-range gid surface a warning, no crash."""
    path = _write(tmp_path, name, payload_factory())
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(path), "")),
    )
    warnings = []
    monkeypatch.setattr(
        io_actions.QMessageBox,
        "warning",
        lambda *a, **k: warnings.append(a),
    )

    result = io_actions.import_tilemap_dialog(parent_widget)
    assert result is None  # defensive load rejected the file
    assert warnings, f"{name}: a typed load error must surface a user-facing warning"


def test_sc_ui_012_1_malformed_json_surfaces_without_crash(
    qtbot, monkeypatch, tmp_path, parent_widget
):
    """SC-UI-012-1: a malformed (non-JSON) file surfaces a warning, never a crash."""
    path = tmp_path / "broken.tmj"
    path.write_text("{ this is not valid json ", encoding="utf-8")
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(path), "")),
    )
    warnings = []
    monkeypatch.setattr(
        io_actions.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )

    assert io_actions.import_tilemap_dialog(parent_widget) is None
    assert warnings


def test_cancelled_dialogs_return_none(qtbot, monkeypatch, parent_widget):
    """A cancelled file dialog (empty path) returns None and writes nothing."""
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    assert io_actions.import_tilemap_dialog(parent_widget) is None


def test_write_tiled_json_is_reimportable(tmp_path, make_tilemap_setup):
    """Sanity: a UI-exported file re-imports via the same data seam (portability)."""
    from pixelart_creator.data.tiled_io import read_tiled_json

    _tileset, tilemap = _stamped_map(make_tilemap_setup)
    out = write_tiled_json(tmp_path / "s.tmj", tilemap)
    reloaded = read_tiled_json(out)
    assert len(reloaded.layers) == len(tilemap.layers)
