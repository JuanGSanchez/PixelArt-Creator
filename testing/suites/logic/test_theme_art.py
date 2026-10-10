"""Tests for ``pixelart_creator.logic.theme_art`` (REQ-VI-UI-003, REQ-VI-BUILD-001).

Qt-free. Uses small self-contained grids; the committed theme data is covered by
the catalogue integration test in ``testing/suites/data/test_style_catalog.py``.
Expected focus-touch counts are worked out by hand in the comments (4-neighbour
pairs, each unordered pair counted once) so they do not restate the algorithm.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import theme_art
from pixelart_creator.logic.constants import MAX_CANVAS_WIDTH
from pixelart_creator.logic.theme_art import (
    DEFAULT_FOCUS_GROUNDS,
    FOCUS_ROLE,
    KIND_NINE_SLICE,
    KIND_ORNAMENT,
    KIND_OVERLAY,
    KIND_PATTERN,
    KIND_SPRITE,
    TEMPLATE_KINDS,
    TRANSPARENT_SYMBOL,
    RoleGrid,
    Slices,
    Template,
    TemplateSet,
    ThemeArtError,
    compose,
    focus_touch_roles,
    parse_grid,
    render,
)

LEGEND = {
    "a": "accent",
    "s": "surface",
    "h": "frame_hi",
    "m": "frame_mid",
    "f": FOCUS_ROLE,
    "_": None,
}
ROLE_MAP = {
    "accent": "#c0392b",
    "surface": "#fdf6e3",
    "frame_hi": "#ffffff",
    "frame_mid": "#808080",
    "focus": "#0000ff",
    "background": "#102030",
}


def grid(*rows: str, legend=None) -> RoleGrid:
    return parse_grid("\n".join(rows), LEGEND if legend is None else legend)


def tpl(name, rows, slices=(0, 0, 0, 0), kind=KIND_NINE_SLICE) -> Template:
    return Template(name, grid(*rows), Slices.from_css(slices), kind)


# --- Slices ----------------------------------------------------------------


class TestSlices:
    def test_stores_the_four_insets(self):
        s = Slices(left=1, top=2, right=3, bottom=4)
        assert (s.left, s.top, s.right, s.bottom) == (1, 2, 3, 4)

    def test_from_css_uses_top_right_bottom_left_order(self):
        s = Slices.from_css([1, 2, 3, 4])
        assert (s.top, s.right, s.bottom, s.left) == (1, 2, 3, 4)

    @pytest.mark.parametrize("values", [[], [1], [1, 2, 3], [1, 2, 3, 4, 5]])
    def test_from_css_rejects_a_wrong_count(self, values):
        with pytest.raises(ThemeArtError, match="4 values"):
            Slices.from_css(values)

    @pytest.mark.parametrize("name", ["left", "top", "right", "bottom"])
    def test_negative_inset_is_rejected(self, name):
        kwargs = dict(left=0, top=0, right=0, bottom=0, **{})
        kwargs[name] = -1
        with pytest.raises(ThemeArtError, match=name):
            Slices(**kwargs)

    @pytest.mark.parametrize("bad", [1.0, "1", None, True])
    def test_non_int_inset_is_rejected(self, bad):
        with pytest.raises(ThemeArtError):
            Slices(left=bad, top=0, right=0, bottom=0)

    def test_zero_is_allowed_and_is_zero(self):
        assert Slices(0, 0, 0, 0).is_zero is True

    @pytest.mark.parametrize("name", ["left", "top", "right", "bottom"])
    def test_any_single_nonzero_inset_is_not_zero(self, name):
        kwargs = dict(left=0, top=0, right=0, bottom=0)
        kwargs[name] = 1
        assert Slices(**kwargs).is_zero is False

    def test_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            Slices(0, 0, 0, 0).left = 1


# --- parse_grid ------------------------------------------------------------


class TestParseGrid:
    def test_parses_rows_without_a_legend(self):
        g = parse_grid("ab\ncd")
        assert g.rows == ("ab", "cd")
        assert g.legend == ()
        assert (g.width, g.height) == (2, 2)

    def test_trailing_blank_lines_are_ignored(self):
        assert parse_grid("ab\ncd\n\n  \n").rows == ("ab", "cd")

    def test_carriage_returns_are_stripped(self):
        assert parse_grid("ab\r\ncd\r\n").rows == ("ab", "cd")

    def test_legend_is_stored_sorted_by_symbol(self):
        g = parse_grid("ba", {"b": "x", "a": "y"})
        assert g.legend == (("a", "y"), ("b", "x"))

    def test_transparent_symbol_needs_no_legend_entry(self):
        assert parse_grid("a_", {"a": "accent"}).rows == ("a_",)

    def test_legend_may_map_a_symbol_to_none(self):
        assert parse_grid("a", {"a": None}).legend == (("a", None),)

    @pytest.mark.parametrize("text", ["", "\n", "   \n\n"])
    def test_empty_grid_is_rejected(self, text):
        with pytest.raises(ThemeArtError, match="empty"):
            parse_grid(text)

    def test_ragged_grid_names_the_row(self):
        with pytest.raises(ThemeArtError, match="ragged row 1"):
            parse_grid("abc\nab")

    def test_whitespace_inside_a_row_is_rejected(self):
        with pytest.raises(ThemeArtError, match="whitespace"):
            parse_grid("a b")

    def test_leading_blank_first_row_is_rejected(self):
        with pytest.raises(ThemeArtError, match="empty or contains whitespace"):
            parse_grid("\nab")

    def test_tab_is_whitespace(self):
        with pytest.raises(ThemeArtError, match="whitespace"):
            parse_grid("a\tb")

    def test_symbol_missing_from_the_legend_is_rejected(self):
        with pytest.raises(ThemeArtError, match="not in the legend"):
            parse_grid("ab", {"a": "accent"})

    def test_missing_symbols_are_reported_sorted(self):
        with pytest.raises(ThemeArtError) as info:
            parse_grid("zy", {})
        assert "['y', 'z']" in str(info.value)

    def test_theme_art_error_is_a_value_error(self):
        assert issubclass(ThemeArtError, ValueError)


# --- RoleGrid --------------------------------------------------------------


class TestRoleGrid:
    def test_role_of_returns_the_mapped_role(self):
        assert grid("a").role_of("a") == "accent"

    def test_role_of_underscore_is_transparent(self):
        assert grid("a").role_of(TRANSPARENT_SYMBOL) is None

    def test_underscore_is_transparent_even_if_the_legend_names_a_role(self):
        g = parse_grid("_", {"_": "accent"})
        assert g.role_of("_") is None

    def test_role_of_legend_none_is_transparent(self):
        assert parse_grid("t", {"t": None}).role_of("t") is None

    def test_role_of_unknown_symbol_raises(self):
        with pytest.raises(ThemeArtError, match="'q'"):
            grid("a").role_of("q")

    def test_roles_are_sorted_and_deduplicated(self):
        g = parse_grid("ab", {"b": "zeta", "a": "alpha", "c": "alpha", "t": None})
        assert g.roles() == ("alpha", "zeta")

    def test_roles_of_a_legendless_grid_is_empty(self):
        assert parse_grid("ab").roles() == ()


# --- Template / TemplateSet ------------------------------------------------


class TestTemplate:
    def test_kinds_are_the_five_documented(self):
        assert set(TEMPLATE_KINDS) == {
            KIND_NINE_SLICE,
            KIND_SPRITE,
            KIND_OVERLAY,
            KIND_ORNAMENT,
            KIND_PATTERN,
        }

    @pytest.mark.parametrize("kind", TEMPLATE_KINDS)
    def test_every_known_kind_is_accepted(self, kind):
        assert tpl("t", ["aa", "aa"], kind=kind).kind == kind

    def test_default_kind_is_nine_slice(self):
        assert Template("t", grid("a"), Slices(0, 0, 0, 0)).kind == KIND_NINE_SLICE

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ThemeArtError, match="unknown template kind"):
            tpl("t", ["a"], kind="wobbly")

    def test_horizontal_insets_larger_than_the_grid_are_rejected(self):
        with pytest.raises(ThemeArtError, match="exceed"):
            tpl("t", ["aaa", "aaa", "aaa"], slices=(0, 2, 0, 2))

    def test_vertical_insets_larger_than_the_grid_are_rejected(self):
        with pytest.raises(ThemeArtError, match="exceed"):
            tpl("t", ["aaa", "aaa", "aaa"], slices=(2, 0, 2, 0))

    def test_insets_exactly_filling_the_grid_are_allowed(self):
        tpl("t", ["aaa", "aaa", "aaa"], slices=(1, 1, 2, 2))

    def test_qss_hint_defaults_to_empty(self):
        assert tpl("t", ["a"]).qss_hint == ""


class TestTemplateSet:
    def _set(self):
        t = tpl("one", ["a"])
        return TemplateSet(
            style="washi", templates={"one": t}, focus_rings={}, pattern=t
        )

    def test_get_returns_the_template(self):
        ts = self._set()
        assert ts.get("one") is ts.templates["one"]

    def test_get_unknown_names_style_and_template(self):
        with pytest.raises(ThemeArtError, match="washi.*'two'"):
            self._set().get("two")


# --- compose ---------------------------------------------------------------

NINE = ["ABCD", "EFGH", "IJKL", "MNOP"]  # 4x4, insets 1, middle 2x2


def nine(rows=NINE, slices=(1, 1, 1, 1)):
    return Template(
        "nine",
        parse_grid("\n".join(rows), {c: "accent" for c in "".join(rows)}),
        Slices.from_css(slices),
    )


class TestCompose:
    def test_native_size_is_the_identity(self):
        assert compose(nine(), 4, 4).rows == tuple(NINE)

    def test_grows_by_tiling_edges_and_centre(self):
        # Middle columns are B,C / F,G / J,K / N,O repeated B C B C ...
        assert compose(nine(), 6, 6).rows == (
            "ABCBCD",
            "EFGFGH",
            "IJKJKL",
            "EFGFGH",
            "IJKJKL",
            "MNONOP",
        )

    def test_odd_growth_cuts_the_tile_mid_period(self):
        assert compose(nine(), 5, 4).rows == (
            "ABCBD",
            "EFGFH",
            "IJKJL",
            "MNONP",
        )

    def test_corners_are_never_stretched(self):
        out = compose(nine(), 9, 7).rows
        assert (out[0][0], out[0][-1]) == ("A", "D")
        assert (out[-1][0], out[-1][-1]) == ("M", "P")

    def test_uneven_insets_use_the_right_and_bottom_sizes(self):
        # left 1, right 2, top 2, bottom 1 on a 4x4: middle is 1 wide, 1 high.
        t = nine(slices=(2, 2, 1, 1))
        assert compose(t, 5, 5).rows == (
            "ABBCD",
            "EFFGH",
            "IJJKL",
            "IJJKL",
            "MNNOP",
        )

    def test_legend_is_carried_over(self):
        assert compose(nine(), 6, 6).legend == nine().grid.legend

    def test_zero_slices_tile_the_whole_grid(self):
        t = Template(
            "tile", parse_grid("ab\ncd", {c: "x" for c in "abcd"}), Slices(0, 0, 0, 0)
        )
        assert compose(t, 4, 3).rows == ("abab", "cdcd", "abab")

    def test_target_smaller_than_the_insets_is_rejected(self):
        with pytest.raises(ThemeArtError, match="width 1 < slices 1\\+1"):
            compose(nine(), 1, 4)

    def test_height_smaller_than_the_insets_is_rejected(self):
        with pytest.raises(ThemeArtError, match="height"):
            compose(nine(), 4, 1)

    def test_axis_without_a_middle_cannot_grow(self):
        # 3 wide with insets 1+2: no middle to repeat.
        t = Template(
            "t",
            parse_grid("abc\nabc", {c: "x" for c in "abc"}),
            Slices(left=1, top=0, right=2, bottom=0),
        )
        with pytest.raises(ThemeArtError, match="no middle"):
            compose(t, 5, 2)

    def test_axis_without_a_middle_is_fine_at_native_size(self):
        t = Template(
            "t",
            parse_grid("abc\nabc", {c: "x" for c in "abc"}),
            Slices(left=1, top=0, right=2, bottom=0),
        )
        assert compose(t, 3, 2).rows == ("abc", "abc")

    def test_axis_without_a_middle_may_still_grow_on_the_other_axis(self):
        t = Template(
            "t",
            parse_grid("abc\nabc", {c: "x" for c in "abc"}),
            Slices(left=1, top=0, right=2, bottom=0),
        )
        assert compose(t, 3, 4).rows == ("abc",) * 4

    @pytest.mark.parametrize(
        "w,h", [(4.0, 4), (4, 4.0), (True, 4), (4, True), ("4", 4)]
    )
    def test_non_int_size_is_rejected(self, w, h):
        with pytest.raises(ThemeArtError, match="must be an int"):
            compose(nine(), w, h)

    @given(
        st.integers(1, 6).flatmap(
            lambda cols: st.lists(
                st.text(st.sampled_from("abcdefgh"), min_size=cols, max_size=cols),
                min_size=1,
                max_size=6,
            )
        ),
        st.data(),
    )
    def test_composed_size_is_the_requested_size_and_cells_come_from_the_grid(
        self, rows, data
    ):
        h0, w0 = len(rows), len(rows[0])
        left = data.draw(st.integers(0, w0))
        right = data.draw(st.integers(0, w0 - left))
        top = data.draw(st.integers(0, h0))
        bottom = data.draw(st.integers(0, h0 - top))
        t = Template(
            "p",
            parse_grid("\n".join(rows), {c: "x" for c in "abcdefgh"}),
            Slices(left, top, right, bottom),
        )
        w = (
            w0
            if w0 - left - right == 0
            else data.draw(st.integers(max(1, left + right), 14))
        )
        h = (
            h0
            if h0 - top - bottom == 0
            else data.draw(st.integers(max(1, top + bottom), 14))
        )
        out = compose(t, w, h)
        assert (out.width, out.height) == (w, h)
        assert set("".join(out.rows)) <= set("".join(rows))
        # Corners and the four insets are copied unchanged.
        for y in range(top):
            assert out.rows[y][:left] == rows[y][:left]
        for k in range(1, bottom + 1):
            assert out.rows[-k][w - right :] == rows[-k][w0 - right :]

    @given(st.integers(0, 4), st.integers(0, 4))
    def test_growing_by_a_whole_period_repeats_the_rows(self, extra_cols, extra_rows):
        period_w, period_h = 2, 2  # NINE's middle
        base = compose(nine(), 4, 4)
        grown = compose(nine(), 4 + extra_cols * period_w, 4 + extra_rows * period_h)
        assert grown.rows[0][:2] == base.rows[0][:2]
        assert grown.rows[-1][-2:] == base.rows[-1][-2:]


# --- render ----------------------------------------------------------------


class TestRender:
    def test_size_is_grid_size_times_scale(self):
        buf = render(grid("as", "sa", "ss"), ROLE_MAP, 3)
        assert (buf.width, buf.height) == (6, 9)

    def test_each_cell_becomes_a_uniform_block_of_its_role_colour(self):
        buf = render(grid("as"), ROLE_MAP, 2)
        accent = (0xC0, 0x39, 0x2B, 255)
        surface = (0xFD, 0xF6, 0xE3, 255)
        assert (buf.data[:, :2] == accent).all()
        assert (buf.data[:, 2:] == surface).all()

    def test_transparent_cells_are_fully_transparent(self):
        buf = render(grid("a_"), ROLE_MAP, 2)
        assert (buf.data[:, 2:] == (0, 0, 0, 0)).all()

    def test_alpha_is_binary(self):
        buf = render(grid("a_sm"), ROLE_MAP, 3)
        assert set(np.unique(buf.data[..., 3])) <= {0, 255}

    def test_scale_one_is_cell_for_cell(self):
        buf = render(grid("am", "sh"), ROLE_MAP, 1)
        assert tuple(buf.data[1, 1]) == (255, 255, 255, 255)
        assert tuple(buf.data[0, 1]) == (0x80, 0x80, 0x80, 255)

    def test_role_unused_by_the_grid_need_not_be_in_the_map(self):
        render(grid("a"), {"accent": "#c0392b"}, 1)

    def test_upper_case_hex_is_accepted(self):
        buf = render(grid("a"), {"accent": "#C0392B"}, 1)
        assert tuple(buf.data[0, 0]) == (0xC0, 0x39, 0x2B, 255)

    @pytest.mark.parametrize("scale", [0, -1, 1.5, "2", True, None])
    def test_bad_scale_is_rejected(self, scale):
        with pytest.raises(ThemeArtError, match="scale"):
            render(grid("a"), ROLE_MAP, scale)

    def test_role_missing_from_the_map_is_rejected(self):
        with pytest.raises(ThemeArtError, match="'accent'.*role map"):
            render(grid("a"), {}, 1)

    def test_translucent_role_colour_is_rejected(self):
        with pytest.raises(ThemeArtError, match="translucent"):
            render(grid("a"), {"accent": "#80c0392b"}, 1)

    def test_fully_opaque_eight_digit_role_colour_is_accepted(self):
        buf = render(grid("a"), {"accent": "#ffc0392b"}, 1)
        assert tuple(buf.data[0, 0]) == (0xC0, 0x39, 0x2B, 255)

    def test_malformed_role_colour_is_rejected_as_a_theme_art_error(self):
        with pytest.raises(ThemeArtError, match="accent"):
            render(grid("a"), {"accent": "red"}, 1)

    def test_symbol_not_in_the_grids_legend_is_rejected(self):
        bare = RoleGrid(rows=("q",), legend=())
        with pytest.raises(ThemeArtError, match="legend"):
            render(bare, ROLE_MAP, 1)

    def test_result_too_large_for_a_pixel_buffer_is_rejected(self):
        wide = RoleGrid(rows=("a" * 2,), legend=(("a", "accent"),))
        with pytest.raises(ThemeArtError, match="not allowed"):
            render(wide, ROLE_MAP, MAX_CANVAS_WIDTH)

    def test_all_transparent_grid_renders_clear(self):
        buf = render(grid("__", "__"), {}, 2)
        assert not buf.data.any()

    @given(
        st.lists(
            st.text(st.sampled_from("ashmf_"), min_size=3, max_size=3),
            min_size=1,
            max_size=5,
        ),
        st.integers(1, 4),
    )
    def test_every_cell_maps_to_a_declared_role_at_the_scaled_size(self, rows, scale):
        g = grid(*rows)
        buf = render(g, ROLE_MAP, scale)
        assert (buf.width, buf.height) == (g.width * scale, g.height * scale)
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                role = g.role_of(symbol)
                expected = (
                    (0, 0, 0, 0)
                    if role is None
                    else (
                        *(int(ROLE_MAP[role][i : i + 2], 16) for i in (1, 3, 5)),
                        255,
                    )
                )
                block = buf.data[
                    y * scale : (y + 1) * scale, x * scale : (x + 1) * scale
                ]
                assert (block == expected).all()

    @given(
        st.lists(
            st.text(st.sampled_from("ashmf_"), min_size=2, max_size=2),
            min_size=1,
            max_size=4,
        )
    )
    def test_every_rendered_colour_is_a_declared_role_colour_or_clear(self, rows):
        buf = render(grid(*rows), ROLE_MAP, 2)
        allowed = {(0, 0, 0, 0)} | {
            (*(int(v[i : i + 2], 16) for i in (1, 3, 5)), 255)
            for v in ROLE_MAP.values()
        }
        seen = {tuple(int(c) for c in px) for px in buf.data.reshape(-1, 4)}
        assert seen <= allowed


# --- focus_touch_roles -----------------------------------------------------


def _set(control, ring, rings=None, style="s"):
    return TemplateSet(
        style=style,
        templates={"control": control, "ring": ring},
        focus_rings={"control": "ring"} if rings is None else rings,
        pattern=control,
    )


class TestFocusTouchRoles:
    def test_ring_on_the_border_touches_the_control_and_the_ground(self):
        # 3x3 accent block, ring on its 8 border cells, ground all round.
        # Ring vs ground: the 3x3 perimeter has 12 unit edges -> 12.
        # Ring vs the single centre accent cell: its 4 edges -> 4.
        control = tpl("control", ["aaa", "aaa", "aaa"])
        ring = tpl("ring", ["fff", "f_f", "fff"], kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring), grounds=("background",))
        assert got == {"accent": 4, "background": 12}

    def test_each_ground_is_probed_and_counts_add_up(self):
        control = tpl("control", ["aaa", "aaa", "aaa"])
        ring = tpl("ring", ["fff", "f_f", "fff"], kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring))
        assert DEFAULT_FOCUS_GROUNDS == ("background", "surface")
        assert got == {"accent": 8, "background": 12, "surface": 12}

    def test_result_keys_are_sorted(self):
        control = tpl("control", ["aaa", "aaa", "aaa"])
        ring = tpl("ring", ["fff", "f_f", "fff"], kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring))
        assert list(got) == sorted(got)

    def test_planted_one_pixel_ring_inside_a_frame_touches_the_frame_role(self):
        # 5x5: frame_hi border, surface inside; the ring sits on the second
        # ring of cells. Its outer edge (12 unit edges) touches frame_hi, its
        # inner edge (4 edges around the one centre cell) touches surface.
        control = tpl(
            "control",
            ["hhhhh", "hsssh", "hsssh", "hsssh", "hhhhh"],
        )
        ring = tpl(
            "ring",
            ["_____", "_fff_", "_f_f_", "_fff_", "_____"],
            kind=KIND_OVERLAY,
        )
        got = focus_touch_roles(_set(control, ring), grounds=("background",))
        assert got == {"frame_hi": 12, "surface": 4}

    def test_nine_slice_control_is_probed_at_twice_its_native_size(self):
        # 3x3 nine-slice (insets 1) probed at 6x6: frame_mid border, 4x4
        # surface inside. The ring (same slices) replaces the border: its
        # outer perimeter is 24 edges (ground), its inner is 16 (surface).
        control = tpl("control", ["mmm", "msm", "mmm"], slices=(1, 1, 1, 1))
        ring = tpl(
            "ring", ["fff", "f_f", "fff"], slices=(1, 1, 1, 1), kind=KIND_OVERLAY
        )
        got = focus_touch_roles(_set(control, ring), grounds=("background",))
        assert got == {"background": 24, "surface": 16}

    def test_ring_never_counts_itself(self):
        control = tpl("control", ["aaa", "aaa", "aaa"])
        ring = tpl("ring", ["fff", "fff", "fff"], kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring), grounds=("background",))
        assert FOCUS_ROLE not in got
        assert got == {"background": 12}

    def test_ground_equal_to_focus_is_not_counted_as_a_touch(self):
        control = tpl("control", ["aaa", "aaa", "aaa"])
        ring = tpl("ring", ["fff", "f_f", "fff"], kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring), grounds=(FOCUS_ROLE,))
        assert got == {"accent": 4}

    def test_several_controls_accumulate(self):
        control = tpl("control", ["aaa", "aaa", "aaa"])
        other = tpl("other", ["sss", "sss", "sss"])
        ring = tpl("ring", ["fff", "f_f", "fff"], kind=KIND_OVERLAY)
        ts = TemplateSet(
            style="s",
            templates={"control": control, "other": other, "ring": ring},
            focus_rings={"control": "ring", "other": "ring"},
            pattern=control,
        )
        assert focus_touch_roles(ts, grounds=("background",)) == {
            "accent": 4,
            "surface": 4,
            "background": 24,
        }

    def test_no_ring_assignments_is_an_error_not_an_empty_result(self):
        control = tpl("control", ["a"])
        ring = tpl("ring", ["f"], kind=KIND_OVERLAY)
        with pytest.raises(ThemeArtError, match="no focus ring"):
            focus_touch_roles(_set(control, ring, rings={}))

    def test_no_grounds_is_an_error(self):
        control = tpl("control", ["a"])
        ring = tpl("ring", ["f"], kind=KIND_OVERLAY)
        with pytest.raises(ThemeArtError, match="no grounds"):
            focus_touch_roles(_set(control, ring), grounds=())

    def test_unknown_control_template_is_an_error(self):
        control = tpl("control", ["a"])
        ring = tpl("ring", ["f"], kind=KIND_OVERLAY)
        with pytest.raises(ThemeArtError, match="ghost"):
            focus_touch_roles(_set(control, ring, rings={"ghost": "ring"}))

    def test_unknown_ring_template_is_an_error(self):
        control = tpl("control", ["a"])
        ring = tpl("ring", ["f"], kind=KIND_OVERLAY)
        with pytest.raises(ThemeArtError, match="ghost"):
            focus_touch_roles(_set(control, ring, rings={"control": "ghost"}))

    @given(st.integers(1, 6), st.integers(1, 6))
    def test_ring_around_a_plain_block_touches_ground_by_the_block_perimeter(
        self, w, h
    ):
        # A w x h block entirely covered by the ring is an h*2 + w*2 perimeter.
        control = tpl("control", ["a" * w] * h)
        ring = tpl("ring", ["f" * w] * h, kind=KIND_OVERLAY)
        got = focus_touch_roles(_set(control, ring), grounds=("background",))
        assert got == {"background": 2 * (w + h)}


def test_focus_role_is_named_focus():
    assert FOCUS_ROLE == "focus"


def test_public_surface_is_exported():
    assert set(theme_art.__all__) >= {
        "ThemeArtError",
        "Slices",
        "RoleGrid",
        "Template",
        "TemplateSet",
        "parse_grid",
        "compose",
        "render",
        "focus_touch_roles",
    }
