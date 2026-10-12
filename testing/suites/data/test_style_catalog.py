"""Tests for ``pixelart_creator.data.style_catalog`` (REQ-VI-UI-003, REQ-VI-UI-004,
REQ-VI-BUILD-001; ADR-0070).

Qt-free. Every unit test builds a small themes tree under ``tmp_path`` from the
dictionary returned by :func:`valid_tree`, mutates one thing and asserts the
domain error -- so each rejection is paired with the control that the unmutated
tree loads. The shipped-data integration test at the bottom loads every
committed style and fails (never skips) while the data is absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from pixelart_creator.data import style_catalog
from pixelart_creator.data.style_catalog import (
    StyleCatalog,
    StyleCatalogError,
    load_catalog,
)
from pixelart_creator.logic.contrast import (
    FOCUS_MIN_RATIO,
    ContrastPair,
    PairKind,
    contrast_ratio,
    meets_floor,
)
from pixelart_creator.logic.theme_art import (
    KIND_NINE_SLICE,
    KIND_PATTERN,
    TemplateSet,
    focus_touch_roles,
)

ROLES = {
    "background": "#fdf6e3",
    "surface": "#eee8d5",
    "hover": "#e0d8c0",
    "pressed": "#c8bfa5",
    "accent": "#c0392b",
    "accent_text": "#ffffff",
    "focus": "#1f5fbf",
    "text": "#1a1a1a",
    "border": "#586e75",
    "frame_hi": "#ffffff",
    "frame_mid": "#93a1a1",
    "frame_lo": "#586e75",
    "info": "#78787890",
}
LEGEND = {
    "a": "accent",
    "s": "surface",
    "h": "frame_hi",
    "m": "frame_mid",
    "f": "focus",
    "_": None,
}
STYLES = ("alpha", "beta")
MODES = ("light", "dark")


def _roles_doc(style: str) -> Dict[str, Any]:
    dark = dict(ROLES, background="#002b36", surface="#073642", text="#eeeeee")
    return {
        "format": 1,
        "style": style,
        "modes": {"light": dict(ROLES), "dark": dark},
    }


def _templates_doc() -> Dict[str, Any]:
    return {
        "format": 1,
        "legend": dict(LEGEND),
        "templates": {
            "button": {
                "kind": "nine-slice",
                "grid": ["mmm", "msm", "mmm"],
                "slices": [1, 1, 1, 1],
                "qss_hint": "QPushButton",
            },
            "focus_ring": {
                "kind": "overlay",
                "grid": ["fff", "f_f", "fff"],
                "slices": {"left": 1, "top": 1, "right": 1, "bottom": 1},
            },
        },
        "focus_rings": {"button": "focus_ring"},
        "pattern": {"grid": ["ms", "sm"]},
    }


def valid_tree() -> Dict[str, Any]:
    """Return ``{relative path: json-able object | str | bytes}`` of a good tree."""
    tree: Dict[str, Any] = {
        "index.json": {
            "format": 1,
            "styles": list(STYLES),
            "default_style": "alpha",
            "modes": list(MODES),
            "default_mode": "light",
        },
        "contrast-pairs.json": [
            {"fg": "text", "bg": "background", "kind": "text", "note": "body"},
            {"fg": "border", "bg": "surface", "kind": "component"},
            {"fg": "info", "bg": "info", "kind": "info", "over": "background"},
        ],
    }
    for style in STYLES:
        tree[f"{style}/roles.json"] = _roles_doc(style)
        tree[f"{style}/templates.json"] = _templates_doc()
    return tree


def materialise(root: Path, tree: Dict[str, Any]) -> Path:
    for rel, content in tree.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        elif isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            target.write_text(json.dumps(content), encoding="utf-8")
    return root


@pytest.fixture
def tree():
    return valid_tree()


@pytest.fixture
def build(tmp_path):
    def _build(tr: Dict[str, Any]) -> StyleCatalog:
        return load_catalog(materialise(tmp_path / "themes", tr))

    return _build


@pytest.fixture
def catalog(build, tree):
    return build(tree)


def expect_error(build, tree, match):
    with pytest.raises(StyleCatalogError, match=match):
        build(tree)


# --- control: the unmutated tree loads -------------------------------------


class TestValidTree:
    def test_style_ids_keep_menu_order(self, catalog):
        assert catalog.style_ids() == STYLES

    def test_mode_ids_keep_index_order(self, catalog):
        assert catalog.mode_ids() == MODES

    def test_defaults_come_from_the_index(self, catalog):
        assert (catalog.default_style(), catalog.default_mode()) == ("alpha", "light")

    def test_role_keys_are_sorted_and_common(self, catalog):
        assert catalog.role_keys() == tuple(sorted(ROLES))

    def test_role_map_is_per_style_and_mode(self, catalog):
        assert catalog.role_map("beta", "dark")["background"] == "#002b36"
        assert catalog.role_map("beta", "light")["background"] == "#fdf6e3"

    def test_role_map_is_a_copy(self, catalog):
        catalog.role_map("alpha", "light")["background"] = "#000000"
        assert catalog.role_map("alpha", "light")["background"] == "#fdf6e3"

    def test_template_set_has_templates_rings_and_pattern(self, catalog):
        ts = catalog.template_set("alpha")
        assert isinstance(ts, TemplateSet)
        assert ts.style == "alpha"
        assert set(ts.templates) == {"button", "focus_ring"}
        assert dict(ts.focus_rings) == {"button": "focus_ring"}
        assert ts.pattern.kind == KIND_PATTERN
        assert ts.pattern.grid.rows == ("ms", "sm")

    def test_template_fields_are_read(self, catalog):
        button = catalog.template_set("alpha").get("button")
        assert button.kind == KIND_NINE_SLICE
        assert button.qss_hint == "QPushButton"
        assert (button.slices.top, button.slices.left) == (1, 1)
        assert button.grid.role_of("m") == "frame_mid"

    def test_dict_slices_and_list_slices_both_load(self, catalog):
        ring = catalog.template_set("alpha").get("focus_ring")
        assert (ring.slices.left, ring.slices.right) == (1, 1)

    def test_contrast_pairs_are_typed(self, catalog):
        pairs = catalog.contrast_pairs()
        assert all(isinstance(p, ContrastPair) for p in pairs)
        assert [p.kind for p in pairs] == [
            PairKind.TEXT,
            PairKind.COMPONENT,
            PairKind.INFO,
        ]
        assert pairs[0].note == "body"
        assert pairs[1].note == "" and pairs[1].over is None
        assert pairs[2].over == "background"

    def test_derived_focus_touch_runs_on_the_loaded_set(self, catalog):
        touched = focus_touch_roles(catalog.template_set("alpha"))
        assert set(touched) == {"background", "surface"}

    def test_path_traversable_root_and_str_free_loading(self, tmp_path, tree):
        root = materialise(tmp_path / "t", tree)
        assert StyleCatalog(root).style_ids() == STYLES


# --- lookups ---------------------------------------------------------------


class TestLookups:
    def test_unknown_style_in_role_map_is_rejected(self, catalog):
        with pytest.raises(
            StyleCatalogError, match="unknown style/mode 'nope'/'light'"
        ):
            catalog.role_map("nope", "light")

    def test_unknown_mode_in_role_map_is_rejected(self, catalog):
        with pytest.raises(StyleCatalogError, match="'alpha'/'sepia'"):
            catalog.role_map("alpha", "sepia")

    def test_unknown_style_in_template_set_is_rejected(self, catalog):
        with pytest.raises(StyleCatalogError, match="unknown style 'nope'"):
            catalog.template_set("nope")

    def test_style_catalog_error_is_a_value_error(self):
        assert issubclass(StyleCatalogError, ValueError)


# --- index.json ------------------------------------------------------------


class TestIndex:
    def test_missing_index(self, build, tree):
        del tree["index.json"]
        expect_error(build, tree, "index.json: file not found")

    def test_malformed_json_is_a_domain_error(self, build, tree):
        tree["index.json"] = "{not json"
        expect_error(build, tree, "index.json: cannot be read as JSON")

    def test_non_utf8_bytes_are_a_domain_error(self, build, tree):
        tree["index.json"] = b"\xff\xfe\x00{"
        expect_error(build, tree, "cannot be read as JSON")

    def test_empty_file_is_a_domain_error(self, build, tree):
        tree["index.json"] = ""
        expect_error(build, tree, "cannot be read as JSON")

    def test_index_must_be_an_object(self, build, tree):
        tree["index.json"] = ["alpha"]
        expect_error(build, tree, "index.json: expected an object")

    def test_unsupported_format(self, build, tree):
        tree["index.json"]["format"] = 2
        expect_error(build, tree, "format 2 is not 1")

    def test_missing_format(self, build, tree):
        del tree["index.json"]["format"]
        expect_error(build, tree, "format None")

    @pytest.mark.parametrize("bad", [[], "alpha", [""], [1], ["a", "a"], None])
    def test_styles_must_be_a_unique_non_empty_list_of_strings(self, build, tree, bad):
        tree["index.json"]["styles"] = bad
        expect_error(build, tree, "styles")

    def test_duplicate_styles_are_named_as_such(self, build, tree):
        tree["index.json"]["styles"] = ["alpha", "alpha"]
        expect_error(build, tree, "duplicate entries")

    @pytest.mark.parametrize("bad", [[], ["light", "light"], "light"])
    def test_modes_must_be_a_unique_non_empty_list(self, build, tree, bad):
        tree["index.json"]["modes"] = bad
        expect_error(build, tree, "modes")

    def test_default_style_must_be_a_style(self, build, tree):
        tree["index.json"]["default_style"] = "gamma"
        expect_error(build, tree, "default_style is not a style")

    def test_default_style_missing_is_rejected(self, build, tree):
        del tree["index.json"]["default_style"]
        expect_error(build, tree, "default_style")

    def test_default_mode_must_be_a_mode(self, build, tree):
        tree["index.json"]["default_mode"] = "sepia"
        expect_error(build, tree, "default_mode is not a mode")


# --- roles.json ------------------------------------------------------------


class TestRoles:
    def test_missing_roles_file(self, build, tree):
        del tree["beta/roles.json"]
        expect_error(build, tree, "beta/roles.json: file not found")

    def test_roles_doc_must_be_an_object(self, build, tree):
        tree["alpha/roles.json"] = []
        expect_error(build, tree, "alpha/roles.json: expected an object")

    def test_roles_format_is_checked(self, build, tree):
        tree["alpha/roles.json"]["format"] = 9
        expect_error(build, tree, "alpha/roles.json: format 9")

    def test_roles_style_must_name_its_folder(self, build, tree):
        tree["beta/roles.json"]["style"] = "alpha"
        expect_error(build, tree, "beta/roles.json: 'style' is 'alpha'")

    def test_modes_block_must_be_an_object(self, build, tree):
        tree["alpha/roles.json"]["modes"] = ["light", "dark"]
        expect_error(build, tree, "modes: expected an object")

    def test_extra_mode_is_rejected(self, build, tree):
        tree["alpha/roles.json"]["modes"]["sepia"] = dict(ROLES)
        expect_error(build, tree, "differ from the index")

    def test_missing_mode_is_rejected(self, build, tree):
        del tree["alpha/roles.json"]["modes"]["dark"]
        expect_error(build, tree, "differ from the index")

    def test_empty_mode_is_rejected(self, build, tree):
        tree["alpha/roles.json"]["modes"]["dark"] = {}
        expect_error(build, tree, "no roles")

    def test_mode_must_be_an_object(self, build, tree):
        tree["alpha/roles.json"]["modes"]["dark"] = "#000000"
        expect_error(build, tree, "modes.dark: expected an object")

    @pytest.mark.parametrize(
        "bad",
        ["red", "#fff", "123456", "#12345g", "#1234567", "", 0, None, ["#000000"]],
    )
    def test_malformed_colour_is_rejected_with_its_address(self, build, tree, bad):
        tree["alpha/roles.json"]["modes"]["light"]["text"] = bad
        expect_error(build, tree, "alpha/roles.json modes.light.text")

    @pytest.mark.parametrize("good", ["#000000", "#ABCDEF", "#80123456"])
    def test_six_and_eight_digit_colours_are_accepted(self, build, tree, good):
        tree["alpha/roles.json"]["modes"]["light"]["text"] = good
        assert build(tree).role_map("alpha", "light")["text"] == good

    def test_focus_must_differ_from_accent(self, build, tree):
        tree["alpha/roles.json"]["modes"]["dark"]["focus"] = ROLES["accent"]
        expect_error(build, tree, "'focus' must differ from 'accent'")

    def test_focus_equal_to_accent_is_caught_case_insensitively(self, build, tree):
        tree["alpha/roles.json"]["modes"]["light"]["focus"] = ROLES["accent"].upper()
        expect_error(build, tree, "'focus' must differ")

    def test_both_focus_and_accent_missing_is_rejected_not_skipped(self, build, tree):
        # Two absent roles compare equal ("" == ""): they must not slip through.
        for mode in MODES:
            for style in STYLES:
                del tree[f"{style}/roles.json"]["modes"][mode]["focus"]
                del tree[f"{style}/roles.json"]["modes"][mode]["accent"]
        expect_error(build, tree, "must differ")


class TestRoleKeyParity:
    def test_a_role_missing_from_one_mode_is_rejected(self, build, tree):
        del tree["alpha/roles.json"]["modes"]["dark"]["hover"]
        expect_error(
            build, tree, r"alpha/dark: role keys differ from alpha/light: \['hover'\]"
        )

    def test_an_extra_role_in_one_mode_is_rejected(self, build, tree):
        tree["alpha/roles.json"]["modes"]["dark"]["glow"] = "#ffffff"
        expect_error(build, tree, r"differ from alpha/light: \['glow'\]")

    def test_a_role_missing_from_another_style_is_rejected(self, build, tree):
        for mode in MODES:
            del tree["beta/roles.json"]["modes"][mode]["pressed"]
        expect_error(
            build, tree, r"beta/light: role keys differ from alpha/light: \['pressed'\]"
        )

    def test_differences_are_reported_from_both_sides(self, build, tree):
        modes = tree["beta/roles.json"]["modes"]
        modes["light"]["extra"] = "#ffffff"
        del modes["light"]["info"]
        expect_error(build, tree, r"\['extra', 'info'\]")


# --- templates.json --------------------------------------------------------


def templates(tree, style="alpha"):
    return tree[f"{style}/templates.json"]


class TestTemplates:
    def test_missing_templates_file(self, build, tree):
        del tree["alpha/templates.json"]
        expect_error(build, tree, "alpha/templates.json: file not found")

    def test_templates_format_is_checked(self, build, tree):
        templates(tree)["format"] = 3
        expect_error(build, tree, "templates.json: format 3")

    def test_templates_block_must_be_an_object(self, build, tree):
        templates(tree)["templates"] = []
        expect_error(build, tree, "templates: expected an object")

    def test_templates_block_must_not_be_empty(self, build, tree):
        templates(tree)["templates"] = {}
        expect_error(build, tree, "no templates")

    def test_a_template_must_be_an_object(self, build, tree):
        templates(tree)["templates"]["button"] = "mmm"
        expect_error(build, tree, "button: expected an object")

    def test_no_legend_anywhere_is_rejected(self, build, tree):
        del templates(tree)["legend"]
        expect_error(build, tree, "no legend")

    def test_per_template_legend_replaces_the_default(self, build, tree):
        del templates(tree)["legend"]
        for spec in templates(tree)["templates"].values():
            spec["legend"] = dict(LEGEND)
        templates(tree)["pattern"]["legend"] = dict(LEGEND)
        assert (
            build(tree).template_set("alpha").get("button").grid.role_of("s")
            == "surface"
        )

    def test_legend_must_be_an_object(self, build, tree):
        templates(tree)["legend"] = ["a"]
        expect_error(build, tree, "legend: expected an object")

    def test_legend_symbol_must_be_one_character(self, build, tree):
        templates(tree)["legend"]["ab"] = "accent"
        expect_error(build, tree, "'ab' is not one character")

    def test_legend_role_must_exist_in_every_role_map(self, build, tree):
        templates(tree)["legend"]["a"] = "no_such_role"
        expect_error(build, tree, "names unknown role 'no_such_role'")

    def test_legend_role_must_be_a_string(self, build, tree):
        templates(tree)["legend"]["a"] = 7
        expect_error(build, tree, "unknown role 7")

    def test_legend_null_is_transparent_and_accepted(self, build, tree):
        templates(tree)["legend"]["t"] = None
        templates(tree)["templates"]["button"]["grid"] = ["mmm", "mtm", "mmm"]
        assert build(tree).template_set("alpha").get("button").grid.role_of("t") is None

    def test_grid_symbol_outside_the_legend_is_rejected_as_a_catalog_error(
        self, build, tree
    ):
        templates(tree)["templates"]["button"]["grid"] = ["mmm", "mzm", "mmm"]
        expect_error(build, tree, "not in the legend")

    def test_ragged_grid_is_rejected_as_a_catalog_error(self, build, tree):
        templates(tree)["templates"]["button"]["grid"] = ["mmm", "mm", "mmm"]
        expect_error(build, tree, "ragged row 1")

    def test_unknown_kind_is_rejected_as_a_catalog_error(self, build, tree):
        templates(tree)["templates"]["button"]["kind"] = "wobbly"
        expect_error(build, tree, "unknown template kind")

    def test_kind_defaults_to_nine_slice(self, build, tree):
        del templates(tree)["templates"]["button"]["kind"]
        assert build(tree).template_set("alpha").get("button").kind == KIND_NINE_SLICE

    def test_slices_default_to_zero(self, build, tree):
        del templates(tree)["templates"]["button"]["slices"]
        assert build(tree).template_set("alpha").get("button").slices.is_zero

    def test_slices_dict_missing_a_key_is_rejected(self, build, tree):
        templates(tree)["templates"]["focus_ring"]["slices"] = {"left": 1}
        expect_error(build, tree, "bad slices")

    def test_slices_list_of_wrong_length_is_rejected(self, build, tree):
        templates(tree)["templates"]["button"]["slices"] = [1, 1, 1]
        expect_error(build, tree, "bad slices")

    def test_negative_slices_are_rejected(self, build, tree):
        templates(tree)["templates"]["button"]["slices"] = [-1, 1, 1, 1]
        expect_error(build, tree, "bad slices")

    @pytest.mark.parametrize("bad", ["1,1,1,1", 4, None])
    def test_slices_of_another_type_are_rejected(self, build, tree, bad):
        templates(tree)["templates"]["button"]["slices"] = bad
        expect_error(build, tree, "slices must be an object or")

    def test_slices_larger_than_the_grid_are_rejected(self, build, tree):
        templates(tree)["templates"]["button"]["slices"] = [2, 2, 2, 2]
        expect_error(build, tree, "exceed")

    def test_grid_may_name_a_file_in_the_style_folder(self, build, tree):
        templates(tree)["templates"]["button"]["grid"] = "button.grid.txt"
        tree["alpha/button.grid.txt"] = "mmm\nmsm\nmmm\n"
        assert build(tree).template_set("alpha").get("button").grid.rows == (
            "mmm",
            "msm",
            "mmm",
        )

    def test_grid_may_name_a_file_in_the_templates_subfolder(self, build, tree):
        templates(tree)["templates"]["button"]["grid"] = "button.grid.txt"
        tree["alpha/templates/button.grid.txt"] = "mmm\nmsm\nmmm\n"
        assert build(tree).template_set("alpha").get("button").grid.width == 3

    def test_style_folder_wins_over_the_templates_subfolder(self, build, tree):
        templates(tree)["templates"]["button"]["grid"] = "button.grid.txt"
        tree["alpha/button.grid.txt"] = "mmm\nmsm\nmmm\n"
        tree["alpha/templates/button.grid.txt"] = "sss\nsss\nsss\n"
        assert build(tree).template_set("alpha").get("button").grid.rows[0] == "mmm"

    def test_missing_grid_file_is_rejected(self, build, tree):
        templates(tree)["templates"]["button"]["grid"] = "gone.grid.txt"
        expect_error(build, tree, "grid file 'gone.grid.txt' not found")

    @pytest.mark.parametrize("bad", [None, "", 5, {"rows": []}, ["mmm", 3]])
    def test_grid_of_another_shape_is_rejected(self, build, tree, bad):
        templates(tree)["templates"]["button"]["grid"] = bad
        expect_error(build, tree, "'grid' must be a file name or row list")

    def test_grid_key_missing_is_rejected(self, build, tree):
        del templates(tree)["templates"]["button"]["grid"]
        expect_error(build, tree, "'grid' must be")


class TestFocusRingsAndPattern:
    def test_focus_rings_must_be_an_object(self, build, tree):
        templates(tree)["focus_rings"] = ["button"]
        expect_error(build, tree, "focus_rings: expected an object")

    def test_focus_rings_must_not_be_empty(self, build, tree):
        templates(tree)["focus_rings"] = {}
        expect_error(build, tree, "focus_rings is empty")

    def test_ring_must_name_an_existing_template(self, build, tree):
        templates(tree)["focus_rings"] = {"button": "ghost"}
        expect_error(build, tree, "'button' -> 'ghost' names no template")

    def test_control_must_name_an_existing_template(self, build, tree):
        templates(tree)["focus_rings"] = {"ghost": "focus_ring"}
        expect_error(build, tree, "'ghost' -> 'focus_ring'")

    def test_pattern_is_required(self, build, tree):
        del templates(tree)["pattern"]
        expect_error(build, tree, "pattern: expected an object")

    def test_pattern_kind_is_forced_to_pattern(self, build, tree):
        templates(tree)["pattern"]["kind"] = "sprite"
        assert build(tree).template_set("alpha").pattern.kind == KIND_PATTERN

    def test_pattern_may_name_a_grid_file(self, build, tree):
        templates(tree)["pattern"]["grid"] = "pattern.grid.txt"
        tree["alpha/pattern.grid.txt"] = "ms\nsm\n"
        assert build(tree).template_set("alpha").pattern.grid.rows == ("ms", "sm")


class TestTemplateNameParity:
    def test_template_present_in_one_style_only_is_rejected(self, build, tree):
        templates(tree, "beta")["templates"]["extra"] = dict(
            templates(tree, "beta")["templates"]["button"]
        )
        expect_error(
            build,
            tree,
            r"beta/templates.json: template names differ from alpha: \['extra'\]",
        )

    def test_template_missing_from_a_later_style_is_rejected(self, build, tree):
        templates(tree, "beta")["templates"].pop("focus_ring")
        templates(tree, "beta")["focus_rings"] = {"button": "button"}
        expect_error(build, tree, r"differ from alpha: \['focus_ring'\]")

    def test_different_art_with_the_same_names_is_allowed(self, build, tree):
        templates(tree, "beta")["templates"]["button"]["grid"] = ["sss", "sas", "sss"]
        assert build(tree).template_set("beta").get("button").grid.rows[1] == "sas"


# --- contrast-pairs.json ---------------------------------------------------


class TestPairs:
    def test_missing_pairs_file(self, build, tree):
        del tree["contrast-pairs.json"]
        expect_error(build, tree, "contrast-pairs.json: file not found")

    @pytest.mark.parametrize("bad", [{}, '"x"', None, []])
    def test_pairs_must_be_a_non_empty_list(self, build, tree, bad):
        tree["contrast-pairs.json"] = bad
        expect_error(build, tree, "expected a non-empty list")

    def test_a_pair_must_be_an_object(self, build, tree):
        tree["contrast-pairs.json"] = ["text/background"]
        expect_error(build, tree, r"contrast-pairs.json\[0\]: expected an object")

    def test_unknown_kind(self, build, tree):
        tree["contrast-pairs.json"][0]["kind"] = "shiny"
        expect_error(build, tree, r"\[0\]: unknown kind 'shiny'")

    def test_missing_kind(self, build, tree):
        del tree["contrast-pairs.json"][0]["kind"]
        expect_error(build, tree, "unknown kind None")

    def test_focus_pairs_are_derived_not_declared(self, build, tree):
        tree["contrast-pairs.json"][0]["kind"] = "focus"
        expect_error(build, tree, "'focus' is derived, not declared")

    @pytest.mark.parametrize("field", ["fg", "bg", "over"])
    def test_unknown_role_in_a_pair_is_rejected(self, build, tree, field):
        tree["contrast-pairs.json"][0][field] = "no_such_role"
        expect_error(build, tree, "unknown role 'no_such_role'")

    @pytest.mark.parametrize("field", ["fg", "bg"])
    def test_missing_operand_is_rejected(self, build, tree, field):
        del tree["contrast-pairs.json"][0][field]
        expect_error(build, tree, "unknown role None|'fg' and 'bg' are required")

    def test_empty_operand_is_rejected(self, build, tree):
        tree["contrast-pairs.json"][0]["fg"] = ""
        expect_error(build, tree, "unknown role ''")

    def test_error_names_the_offending_index(self, build, tree):
        tree["contrast-pairs.json"][2]["kind"] = "bogus"
        expect_error(build, tree, r"\[2\]")


# --- module-level accessors over the default catalogue ---------------------


class TestDefaultCatalogAccessors:
    @pytest.fixture(autouse=True)
    def _patched_shipped_data(self, tmp_path, tree, monkeypatch):
        root = materialise(tmp_path / "shipped", tree)
        calls = []

        def fake_load(arg=None):
            calls.append(arg)
            return StyleCatalog(root)

        style_catalog.reset_default_catalog()
        monkeypatch.setattr(style_catalog, "load_catalog", fake_load)
        self.calls = calls
        yield
        style_catalog.reset_default_catalog()

    def test_accessors_delegate_to_the_catalogue(self):
        assert style_catalog.style_ids() == STYLES
        assert style_catalog.mode_ids() == MODES
        assert style_catalog.default_style() == "alpha"
        assert style_catalog.default_mode() == "light"
        assert style_catalog.role_keys() == tuple(sorted(ROLES))
        assert style_catalog.role_map("beta", "dark")["background"] == "#002b36"
        assert style_catalog.template_set("beta").style == "beta"
        assert len(style_catalog.contrast_pairs()) == 3

    def test_catalogue_is_loaded_once_and_cached(self):
        style_catalog.style_ids()
        style_catalog.role_keys()
        style_catalog.contrast_pairs()
        assert len(self.calls) == 1

    def test_reset_forgets_the_cache(self):
        style_catalog.style_ids()
        style_catalog.reset_default_catalog()
        style_catalog.style_ids()
        assert len(self.calls) == 2

    def test_unknown_style_through_the_function_is_a_domain_error(self):
        with pytest.raises(StyleCatalogError):
            style_catalog.template_set("nope")
        with pytest.raises(StyleCatalogError):
            style_catalog.role_map("nope", "light")


def test_load_catalog_reads_the_package_resource_by_default(monkeypatch):
    seen = {}

    class Stop(Exception):
        pass

    def fake_init(self, root):
        seen["root"] = root
        raise Stop

    monkeypatch.setattr(StyleCatalog, "__init__", fake_init)
    with pytest.raises(Stop):
        load_catalog()
    assert str(seen["root"]).replace("\\", "/").endswith("pixelart_creator/themes")


def test_public_surface_is_exported():
    assert set(style_catalog.__all__) >= {
        "StyleCatalogError",
        "StyleCatalog",
        "load_catalog",
        "reset_default_catalog",
        "style_ids",
        "default_style",
        "default_mode",
        "mode_ids",
        "role_map",
        "role_keys",
        "template_set",
        "contrast_pairs",
    }


# --- integration: the committed styles -------------------------------------

# The two styles committed so far; ``arcade-kikko`` is added later and joins
# this list when it lands.
_EXPECTED_STYLES = ("washi-kintsugi", "edo-night")
_EXPECTED_MODES = ("light", "dark")
_FOCUS_TOUCHED_BY_EVERY_STYLE = {"background", "surface", "hover", "pressed", "accent"}


class TestCommittedStyles:
    """REQ-VI-UI-003/004: every committed style loads and validates.

    Fails (never skips) while the committed theme data is absent.
    """

    @pytest.fixture
    def shipped(self):
        root = Path(style_catalog.__file__).resolve().parents[1] / "themes"
        if not (root / "index.json").is_file():
            pytest.fail(
                "pixelart_creator/themes/index.json does not exist: the committed "
                "style data is absent, so the shipped styles cannot be "
                "verified. This is a failure, not a skip."
            )
        return load_catalog()

    def test_expected_style_ids_are_present(self, shipped):
        assert set(_EXPECTED_STYLES) <= set(shipped.style_ids())

    def test_both_modes_are_present(self, shipped):
        assert tuple(shipped.mode_ids()) == _EXPECTED_MODES

    def test_defaults_are_a_committed_style_and_mode(self, shipped):
        assert shipped.default_style() in shipped.style_ids()
        assert shipped.default_mode() in shipped.mode_ids()

    def test_every_style_and_mode_has_the_same_role_keys(self, shipped):
        keys = set(shipped.role_keys())
        assert keys
        for style in shipped.style_ids():
            for mode in shipped.mode_ids():
                assert set(shipped.role_map(style, mode)) == keys

    def test_focus_touch_derivation_returns_the_expected_roles_for_each_style(
        self, shipped
    ):
        for style in shipped.style_ids():
            touched = set(focus_touch_roles(shipped.template_set(style)))
            assert _FOCUS_TOUCHED_BY_EVERY_STYLE <= touched, style

    def test_declared_pairs_are_present(self, shipped):
        assert shipped.contrast_pairs()

    def test_every_declared_text_and_component_pair_meets_its_floor(self, shipped):
        measured = 0
        for style in shipped.style_ids():
            for mode in shipped.mode_ids():
                roles = shipped.role_map(style, mode)
                for pair in shipped.contrast_pairs():
                    if pair.kind is PairKind.INFO:
                        continue
                    over = roles[pair.over] if pair.over else None
                    ratio = contrast_ratio(roles[pair.fg], roles[pair.bg], over)
                    measured += 1
                    assert meets_floor(
                        pair.kind, ratio
                    ), f"{style}/{mode} {pair.fg} on {pair.bg}: {ratio:.2f}"
        assert measured > 0

    def test_derived_focus_pairs_meet_the_focus_floor(self, shipped):
        measured = 0
        for style in shipped.style_ids():
            touched = focus_touch_roles(shipped.template_set(style))
            for mode in shipped.mode_ids():
                roles = shipped.role_map(style, mode)
                for role in touched:
                    ratio = contrast_ratio(roles["focus"], roles[role])
                    measured += 1
                    assert (
                        ratio >= FOCUS_MIN_RATIO
                    ), f"{style}/{mode} focus on {role}: {ratio:.2f}"
        assert measured > 0
