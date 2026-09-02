"""Tests for pixelart_creator.logic.favourites (ordered, de-duplicated model).

Covers REQ-P3-LOGIC-015 (SC-L015-1..4): add appends / no-op if present,
remove + move behave as specified, ``to_serializable``/``from_serializable``
round-trips (persistence substrate), and malformed colours raise the domain
error. Soft cap ``FAVOURITES_MAX`` is enforced defensively (Article VII).

(input-scheme, REQ-IS-UI-028 / SC-R-27 + R-27a, plan.md §7 RK-2): this
module is run on UNMODIFIED code, before a later wave adds a cursor
(current-index) field to ``Favourites`` for wheel-gesture navigation. Two
tests below exist specifically to survive that change unmodified and to fail
loudly if the change is done wrong:

  * ``test_eq_stays_blind_to_future_cursor_field__R27a`` pins that
    ``__eq__`` compares colours only. R-27a is the regression where a
    ``__slots__`` addition (``"_cursor"``) accidentally teaches ``__eq__``
    about it too, so two colour-identical Favourites lists would start
    comparing unequal merely because their cursors sit at different
    positions after different histories of add/remove/move calls.
  * ``test_serialise_is_byte_identical_hex_list__R27a`` pins the on-disk
    byte form so a cursor field cannot leak one byte into the persisted
    JSON.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data.favourites_io import load_favourites, save_favourites
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


def test_eq_stays_blind_to_future_cursor_field__R27a():
    """R-27a (plan.md §7 RK-2): pin that equality compares COLOURS ONLY.

    No cursor field exists yet on ``Favourites`` — a later wave adds
    one (``__slots__`` gains ``"_cursor"``) so a mouse-wheel gesture can
    travel the list. The point of this test is not that equality "works"
    today; every field that exists today is already covered by
    ``test_contains_len_iter_eq_repr``. The point is that ``__eq__`` must
    stay blind to a field that does not exist yet: two instances holding the
    same colours, reached via DIFFERENT sequences of mutating calls (which
    would very plausibly leave a future cursor at different positions), must
    still compare EQUAL. If ``__eq__`` is ever changed to also compare a
    cursor, this assertion is the one that catches it — do not delete this
    test as "redundant" with the plain equality test above; it is the
    regression guard, not a duplicate.
    """
    a = Favourites([RED, GREEN, BLUE])

    b = Favourites([RED, GREEN, BLUE])
    b.move(0, 2)  # [GREEN, BLUE, RED]
    b.move(2, 0)  # back to [RED, GREEN, BLUE] via a different mutation history

    assert a.colors() == b.colors() == [RED, GREEN, BLUE]
    assert a == b
    assert not (a != b)


def test_serialise_is_byte_identical_hex_list__R27a(tmp_path):
    """R-27a: the persisted form is a JSON list of hex strings and nothing
    else — adding a cursor to the model must not change one byte on disk.

    Locks both levels: the in-memory ``to_serializable()`` shape (a list of
    plain ``str``, nothing else appended) and the actual bytes
    ``save_favourites``/``load_favourites`` (data/favourites_io.py) write and
    read, using a scratch file under pytest's ``tmp_path`` — never a real
    project artifact.
    """
    fav = Favourites([RED, GREEN, BLUE])

    data = fav.to_serializable()
    assert data == ["#FF0000FF", "#00FF00FF", "#0000FFFF"]
    assert all(type(entry) is str for entry in data)
    assert len(data) == 3  # exactly the colours, no extra (e.g. cursor) entry

    path = tmp_path / "favourites.json"
    written = save_favourites(path, fav)
    raw = written.read_bytes()
    expected = json.dumps(data).encode("utf-8")
    assert raw == expected == b'["#FF0000FF", "#00FF00FF", "#0000FFFF"]'

    reloaded = load_favourites(path)
    assert reloaded == fav
    assert reloaded.to_serializable() == data


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


# --- (input-scheme, REQ-IS-LOGIC-001/-002): cursor + first-entry -----------------
# One test per Gherkin scenario, spec.md §9.2 ("Favourites cursor" /
# "First-entry accessor"). YELLOW is a fourth colour so the four-entry
# fixtures used throughout §9.2 ("a Favourites list of four colours") can be
# built without reusing RED/GREEN/BLUE in a different role.

YELLOW = (255, 255, 0, 255)


class TestFavouritesCursor:
    """REQ-IS-LOGIC-001 (SC-L001-1..7)."""

    def test_advancing_steps_to_the_next_entry(self):
        # SC-L001-1: cursor on entry 0, advance -> entry 1, second colour.
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        assert fav.cursor_index() == 0
        result = fav.advance()
        assert fav.cursor_index() == 1
        assert result == GREEN
        assert fav.current() == GREEN

    def test_advancing_past_the_last_entry_wraps_to_the_first(self):
        # SC-L001-2: cursor on entry 3, advance -> wraps to entry 0.
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        fav.advance()
        fav.advance()
        fav.advance()
        assert fav.cursor_index() == 3
        result = fav.advance()
        assert fav.cursor_index() == 0
        assert result == RED

    def test_retreating_before_the_first_entry_wraps_to_the_last(self):
        # SC-L001-3: cursor on entry 0, retreat -> wraps to entry 3 (last).
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        assert fav.cursor_index() == 0
        result = fav.retreat()
        assert fav.cursor_index() == 3
        assert result == YELLOW

    def test_empty_list_has_no_current_colour_and_does_not_raise(self):
        # SC-L001-4: length-0 — advance/retreat are silent no-ops.
        fav = Favourites()
        assert fav.cursor_index() == -1
        assert fav.advance() is None
        assert fav.retreat() is None
        assert fav.cursor_index() == -1
        assert fav.current() is None

    def test_single_entry_list_stays_on_that_entry(self):
        # SC-L001-5: length-1 — both directions behave sanely, no looping.
        fav = Favourites([RED])
        assert fav.cursor_index() == 0
        assert fav.advance() == RED
        assert fav.advance() == RED
        assert fav.cursor_index() == 0
        assert fav.retreat() == RED
        assert fav.cursor_index() == 0

    def test_cursor_stays_valid_across_add_remove_and_move(self):
        # SC-L001-6: cursor validity through a mixed add/remove/move sequence.
        # Removing the entry AHEAD of the cursor (index 3, cursor 2) leaves
        # the cursor unchanged; a subsequent add doesn't move it; a move that
        # relocates the cursor's own colour re-derives the cursor to follow
        # it (Favourites.move docstring) -- traced by hand below rather than
        # only asserting "does not raise".
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        fav.advance()
        fav.advance()
        assert fav.cursor_index() == 2
        assert fav.current() == BLUE

        fav.remove(YELLOW)  # index 3, ahead of cursor 2 -> cursor unchanged
        assert fav.cursor_index() == 2
        assert fav.current() == BLUE
        assert fav.colors() == [RED, GREEN, BLUE]

        purple = (128, 0, 128, 255)
        fav.add(purple)  # non-empty add never moves the cursor
        assert fav.cursor_index() == 2
        assert fav.current() == BLUE
        assert fav.colors() == [RED, GREEN, BLUE, purple]

        fav.move(0, 2)  # [GREEN, BLUE, RED, purple] -- BLUE now at index 1
        assert fav.colors() == [GREEN, BLUE, RED, purple]
        assert fav.cursor_index() == 1
        assert fav.current() == BLUE

    def test_removing_the_entry_below_the_cursor_decrements_it(self):
        # SC-L001-6 companion case named explicitly by the dispatch: removing
        # ONE BEFORE the cursor is a distinct case from removing the cursor's
        # own entry, and both must leave a valid cursor.
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        fav.advance()
        fav.advance()
        assert fav.cursor_index() == 2
        assert fav.current() == BLUE

        fav.remove(RED)  # index 0, below cursor 2 -> cursor decrements to 1
        assert fav.colors() == [GREEN, BLUE, YELLOW]
        assert fav.cursor_index() == 1
        assert fav.current() == BLUE

    def test_removing_the_cursors_own_entry_clamps_it(self):
        # SC-L001-6 companion case: removing the entry the cursor POINTS AT
        # is the other distinct case named by the dispatch. Removing the
        # last entry while the cursor addresses it clamps to the new last
        # index rather than leaving a stale, now out-of-range cursor.
        fav = Favourites([RED, GREEN, BLUE, YELLOW])
        fav.advance()
        fav.advance()
        fav.advance()
        assert fav.cursor_index() == 3
        assert fav.current() == YELLOW

        fav.remove(YELLOW)  # removing the cursor's own (last) entry
        assert fav.colors() == [RED, GREEN, BLUE]
        assert fav.cursor_index() == 2  # clamped to len - 1
        assert fav.current() == BLUE

    def test_removing_the_last_remaining_colour_leaves_no_current_entry(self):
        # SC-L001-7.
        fav = Favourites([RED])
        assert fav.cursor_index() == 0
        fav.remove(RED)
        assert len(fav) == 0
        assert fav.cursor_index() == -1
        assert fav.current() is None


class TestFavouritesFirstEntry:
    """REQ-IS-LOGIC-002 (SC-L002-1..3)."""

    def test_first_entry_is_the_colour_at_position_zero(self):
        # SC-L002-1.
        fav = Favourites([RED, GREEN, BLUE])
        assert fav.first() == fav.colors()[0] == RED

    def test_first_entry_of_an_empty_list_is_no_colour_not_an_error(self):
        # SC-L002-2: "no colour" -> None, and no exception is raised.
        fav = Favourites()
        assert fav.first() is None

    def test_reading_the_first_entry_places_the_cursor_on_it(self):
        # SC-L002-3: cursor starts on entry 2, first() moves it to entry 0,
        # and a subsequent advance lands on entry 1 (continuing FROM entry 0,
        # not from wherever the cursor used to be).
        fav = Favourites([RED, GREEN, BLUE])
        fav.advance()
        fav.advance()
        assert fav.cursor_index() == 2

        result = fav.first()
        assert result == RED
        assert fav.cursor_index() == 0

        assert fav.advance() == GREEN
        assert fav.cursor_index() == 1
