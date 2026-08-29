"""Tests for pixelart_creator.data.favourites_io (JSON persistence).

Covers the REQ-P3-LOGIC-015 persistence substrate (SC-U004-3): save→load
round-trips the Favourites list, a missing file loads as empty (first-run
friendly), and malformed content raises the domain error defensively (Article
VII) — never crashes. Paths are supplied by the caller (Qt-free, portable).
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data.favourites_io import (
    FavouritesIOError,
    load_favourites,
    save_favourites,
)
from pixelart_creator.logic.favourites import Favourites

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def test_save_then_load_round_trips(tmp_path):
    # SC-U004-3: a saved favourite is present after reload.
    path = tmp_path / "favourites.json"
    fav = Favourites([RED, GREEN, BLUE])
    written = save_favourites(path, fav)
    assert written == path
    assert path.exists()
    assert load_favourites(path) == fav


def test_save_accepts_str_path(tmp_path):
    path = tmp_path / "fav.json"
    fav = Favourites([RED])
    save_favourites(str(path), fav)
    assert load_favourites(str(path)) == fav


def test_load_missing_file_is_empty(tmp_path):
    # First-run friendly: missing file -> empty Favourites, no error.
    assert load_favourites(tmp_path / "does-not-exist.json") == Favourites()


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(FavouritesIOError):
        load_favourites(path)


def test_load_malformed_content_raises(tmp_path):
    # Valid JSON but not a list of hex colours -> defensive domain error.
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"colours": ["#FF0000FF"]}), encoding="utf-8")
    with pytest.raises(FavouritesIOError):
        load_favourites(path)


def test_load_bad_colour_entry_raises(tmp_path):
    path = tmp_path / "bad2.json"
    path.write_text(json.dumps(["not-a-hex"]), encoding="utf-8")
    with pytest.raises(FavouritesIOError):
        load_favourites(path)


def test_save_to_unwritable_path_raises(tmp_path):
    # A path whose parent directory does not exist cannot be written.
    bad = tmp_path / "no-such-dir" / "fav.json"
    with pytest.raises(FavouritesIOError):
        save_favourites(bad, Favourites([RED]))


def test_empty_favourites_round_trip(tmp_path):
    path = tmp_path / "empty.json"
    save_favourites(path, Favourites())
    assert load_favourites(path) == Favourites()
