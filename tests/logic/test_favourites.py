"""Tests for pixelart_creator.logic.favourites (ordered, de-duplicated model).

Covers REQ-P3-LOGIC-015 (SC-L015-1..4): add appends / no-op if present,
remove + move behave as specified, ``to_serializable``/``from_serializable``
round-trips (persistence substrate), and malformed colours raise the domain
error. Soft cap ``FAVOURITES_MAX`` is enforced defensively (Article VII).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic import constants
from pixelart_creator.logic.favourites import Favourites, FavouritesError

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def test_add_appends_and_dedup_noop():
    # SC-L015-1.
    fav = Favourites()
    fav.add(RED)
    fav.add(GREEN)
    fav.add(RED)  # duplicate -> no-op
    assert fav.colors() == [RED, GREEN]
    assert len(fav) == 2


def test_add_rejects_malformed():
    # SC-L015-4.
    fav = Favourites()
    with pytest.raises(FavouritesError):
        fav.add((1, 2, 3))  # type: ignore[arg-type]


def test_remove_and_missing():
    # SC-L015-2.
    fav = Favourites([RED, GREEN])
    fav.remove(RED)
    assert fav.colors() == [GREEN]
    with pytest.raises(FavouritesError):
        fav.remove(BLUE)
    with pytest.raises(FavouritesError):
        fav.remove((1, 2, 3))  # type: ignore[arg-type]


def test_move_reorders_and_preserves_rest():
    # SC-L015-2.
    fav = Favourites([RED, GREEN, BLUE])
    fav.move(0, 2)
    assert fav.colors() == [GREEN, BLUE, RED]


@pytest.mark.parametrize("frm,to", [(-1, 0), (0, 9), (True, 0), (0, "x")])
def test_move_bad_index_raises(frm, to):
    fav = Favourites([RED, GREEN])
    with pytest.raises(FavouritesError):
        fav.move(frm, to)  # type: ignore[arg-type]


def test_contains_len_iter_eq_repr():
    fav = Favourites([RED, GREEN])
    assert RED in fav
    assert (1, 2, 3) not in fav
    assert list(fav) == [RED, GREEN]
    assert fav == Favourites([RED, GREEN])
    assert fav != Favourites([RED])
    assert (fav == "x") is False
    assert "Favourites" in repr(fav)


def test_serialise_round_trip():
    # SC-L015-3: to_serializable / from_serializable round-trips the list.
    fav = Favourites([RED, GREEN, BLUE])
    data = fav.to_serializable()
    assert data == ["#FF0000FF", "#00FF00FF", "#0000FFFF"]
    assert Favourites.from_serializable(data) == fav


def test_from_serializable_rejects_non_list():
    with pytest.raises(FavouritesError):
        Favourites.from_serializable({"nope": 1})


def test_from_serializable_rejects_non_string_entry():
    with pytest.raises(FavouritesError):
        Favourites.from_serializable([123])


def test_from_serializable_rejects_bad_hex():
    with pytest.raises(FavouritesError):
        Favourites.from_serializable(["not-a-colour"])


def test_soft_cap_enforced():
    # Article VII defensive bound; adding past FAVOURITES_MAX raises.
    colors = [(i, 0, 0, 255) for i in range(constants.FAVOURITES_MAX)]
    fav = Favourites(colors)
    assert len(fav) == constants.FAVOURITES_MAX
    with pytest.raises(FavouritesError):
        fav.add((0, 0, 1, 255))


@pytest.mark.parametrize("bad", [0, -1, True, "x"])
def test_bad_max_size_raises(bad):
    with pytest.raises(FavouritesError):
        Favourites(max_size=bad)  # type: ignore[arg-type]


def test_custom_max_size():
    fav = Favourites(max_size=2)
    fav.add(RED)
    fav.add(GREEN)
    with pytest.raises(FavouritesError):
        fav.add(BLUE)
