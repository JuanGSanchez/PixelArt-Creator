# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Qt-free loader and validator of the shipped styles and modes (zero Qt, S11).

The styles are package data (ADR-0070): ``pixelart_creator/themes/`` holds

* ``index.json`` -- style ids in menu order, the defaults and the mode ids,
* ``contrast-pairs.json`` -- the declared text / component / info pairs,
* ``<style>/roles.json`` -- one role map per mode,
* ``<style>/templates.json`` plus the grid files it names -- the role-indexed
  frame art (ADR-0069).

Everything is validated when a catalogue is built, so an invalid shipped file
fails loudly at load time (a domain error a test catches) instead of at paint
time. The rules enforced are the ones the design depends on: identical role keys
in every (style, mode), colour syntax ``#RRGGBB`` / ``#AARRGGBB`` (alpha first),
``focus`` distinct from ``accent``, identical template names in every style,
and legends closed over the role keys.

Resolution of a template's ``grid`` entry: a list of strings is the grid itself;
a string names a file, looked for relative to the style folder first and then
relative to its ``templates/`` folder.

Display names of styles and modes are not data (they are translated strings in
``ui/``).
"""

from __future__ import annotations

import functools
import json
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any, Dict, List, Optional, Set, Tuple

from pixelart_creator.logic.contrast import (
    ContrastPair,
    PairKind,
    is_valid_color,
)
from pixelart_creator.logic.theme_art import (
    KIND_NINE_SLICE,
    KIND_PATTERN,
    Slices,
    Template,
    TemplateSet,
    ThemeArtError,
    parse_grid,
)

__all__ = [
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
]

# Format-intrinsic (ADR-0001): the schema version every theme file carries.
_SUPPORTED_FORMAT = 1
_THEMES_DIR = "themes"
_PACKAGE = "pixelart_creator"
_INDEX_FILE = "index.json"
_PAIRS_FILE = "contrast-pairs.json"
_ROLES_FILE = "roles.json"
_TEMPLATES_FILE = "templates.json"
_TEMPLATES_SUBDIR = "templates"
_PAIR_KINDS_DECLARABLE = (PairKind.TEXT, PairKind.COMPONENT, PairKind.INFO)
_FOCUS_ROLE = "focus"
_ACCENT_ROLE = "accent"
_ENCODING = "utf-8"


class StyleCatalogError(ValueError):
    """Raised when the shipped theme data is missing, malformed or inconsistent."""


def _read_json(node: Traversable, where: str) -> Any:
    try:
        if not node.is_file():
            raise StyleCatalogError(f"{where}: file not found")
        return json.loads(node.read_text(encoding=_ENCODING))
    except (OSError, ValueError) as exc:
        if isinstance(exc, StyleCatalogError):
            raise
        raise StyleCatalogError(f"{where}: cannot be read as JSON: {exc}") from exc


def _dict(value: Any, where: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise StyleCatalogError(f"{where}: expected an object")
    return value


def _str_list(value: Any, where: str) -> Tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v for v in value)
    ):
        raise StyleCatalogError(f"{where}: expected a non-empty list of strings")
    if len(set(value)) != len(value):
        raise StyleCatalogError(f"{where}: duplicate entries")
    return tuple(value)


def _check_format(doc: Dict[str, Any], where: str) -> None:
    if doc.get("format") != _SUPPORTED_FORMAT:
        raise StyleCatalogError(
            f"{where}: format {doc.get('format')!r} is not {_SUPPORTED_FORMAT}"
        )


def _load_roles(
    style: str, doc: Dict[str, Any], modes: Tuple[str, ...], where: str
) -> Dict[str, Dict[str, str]]:
    _check_format(doc, where)
    if doc.get("style") != style:
        raise StyleCatalogError(f"{where}: 'style' is {doc.get('style')!r}")
    block = _dict(doc.get("modes"), f"{where} modes")
    if set(block) != set(modes):
        raise StyleCatalogError(
            f"{where}: modes {sorted(block)} differ from the index {sorted(modes)}"
        )
    out: Dict[str, Dict[str, str]] = {}
    for mode in modes:
        roles = _dict(block[mode], f"{where} modes.{mode}")
        if not roles:
            raise StyleCatalogError(f"{where} modes.{mode}: no roles")
        for key, value in roles.items():
            if not isinstance(value, str) or not is_valid_color(value):
                raise StyleCatalogError(
                    f"{where} modes.{mode}.{key}: {value!r} is not "
                    f"#RRGGBB or #AARRGGBB"
                )
        if (
            str(roles.get(_FOCUS_ROLE, "")).lower()
            == str(roles.get(_ACCENT_ROLE, "")).lower()
        ):
            raise StyleCatalogError(
                f"{where} modes.{mode}: '{_FOCUS_ROLE}' must differ from "
                f"'{_ACCENT_ROLE}'"
            )
        out[mode] = dict(roles)
    return out


def _legend(raw: Any, role_keys: Set[str], where: str) -> Dict[str, Optional[str]]:
    legend = _dict(raw, f"{where} legend")
    out: Dict[str, Optional[str]] = {}
    for symbol, role in legend.items():
        if len(symbol) != 1:
            raise StyleCatalogError(f"{where} legend: {symbol!r} is not one character")
        if role is not None and (not isinstance(role, str) or role not in role_keys):
            raise StyleCatalogError(
                f"{where} legend: symbol {symbol!r} names unknown role {role!r}"
            )
        out[symbol] = role
    return out


def _grid_text(spec: Any, style_dir: Traversable, where: str) -> str:
    if isinstance(spec, list) and all(isinstance(r, str) for r in spec):
        return "\n".join(spec)
    if not isinstance(spec, str) or not spec:
        raise StyleCatalogError(f"{where}: 'grid' must be a file name or row list")
    for base in (style_dir, style_dir.joinpath(_TEMPLATES_SUBDIR)):
        node = base.joinpath(spec)
        if node.is_file():
            return node.read_text(encoding=_ENCODING)
    raise StyleCatalogError(f"{where}: grid file {spec!r} not found")


def _slices(raw: Any, where: str) -> Slices:
    try:
        if isinstance(raw, dict):
            return Slices(
                left=raw["left"],
                top=raw["top"],
                right=raw["right"],
                bottom=raw["bottom"],
            )
        if isinstance(raw, list):
            return Slices.from_css(raw)
    except (KeyError, ThemeArtError) as exc:
        raise StyleCatalogError(f"{where}: bad slices: {exc}") from exc
    raise StyleCatalogError(f"{where}: slices must be an object or [t, r, b, l]")


def _template(
    name: str,
    spec: Dict[str, Any],
    default_legend: Optional[Any],
    style_dir: Traversable,
    role_keys: Set[str],
    where: str,
    forced_kind: Optional[str] = None,
) -> Template:
    legend_raw = spec.get("legend", default_legend)
    if legend_raw is None:
        raise StyleCatalogError(f"{where}: no legend")
    legend = _legend(legend_raw, role_keys, where)
    kind = forced_kind or spec.get("kind", KIND_NINE_SLICE)
    slices = (
        Slices(0, 0, 0, 0) if "slices" not in spec else _slices(spec["slices"], where)
    )
    try:
        grid = parse_grid(_grid_text(spec.get("grid"), style_dir, where), legend)
        return Template(
            name=name,
            grid=grid,
            slices=slices,
            kind=kind,
            qss_hint=str(spec.get("qss_hint", "")),
        )
    except ThemeArtError as exc:
        raise StyleCatalogError(f"{where}: {exc}") from exc


def _load_template_set(
    style: str, style_dir: Traversable, role_keys: Set[str]
) -> TemplateSet:
    where = f"{style}/{_TEMPLATES_FILE}"
    doc = _dict(_read_json(style_dir.joinpath(_TEMPLATES_FILE), where), where)
    _check_format(doc, where)
    default_legend = doc.get("legend")
    block = _dict(doc.get("templates"), f"{where} templates")
    if not block:
        raise StyleCatalogError(f"{where}: no templates")
    templates: Dict[str, Template] = {}
    for name, spec in block.items():
        templates[name] = _template(
            name,
            _dict(spec, f"{where} {name}"),
            default_legend,
            style_dir,
            role_keys,
            f"{where} {name}",
        )
    rings = _dict(doc.get("focus_rings"), f"{where} focus_rings")
    if not rings:
        raise StyleCatalogError(f"{where}: focus_rings is empty")
    for control, ring in rings.items():
        if control not in templates or ring not in templates:
            raise StyleCatalogError(
                f"{where} focus_rings: {control!r} -> {ring!r} names no template"
            )
    pattern = _template(
        "pattern",
        _dict(doc.get("pattern"), f"{where} pattern"),
        default_legend,
        style_dir,
        role_keys,
        f"{where} pattern",
        forced_kind=KIND_PATTERN,
    )
    return TemplateSet(
        style=style,
        templates=templates,
        focus_rings={str(k): str(v) for k, v in rings.items()},
        pattern=pattern,
    )


def _load_pairs(doc: Any, role_keys: Set[str]) -> Tuple[ContrastPair, ...]:
    where = _PAIRS_FILE
    if not isinstance(doc, list) or not doc:
        raise StyleCatalogError(f"{where}: expected a non-empty list")
    pairs: List[ContrastPair] = []
    for i, raw in enumerate(doc):
        row = _dict(raw, f"{where}[{i}]")
        try:
            kind = PairKind(row.get("kind"))
        except ValueError:
            raise StyleCatalogError(
                f"{where}[{i}]: unknown kind {row.get('kind')!r}"
            ) from None
        if kind not in _PAIR_KINDS_DECLARABLE:
            raise StyleCatalogError(
                f"{where}[{i}]: kind {kind.value!r} is derived, not declared"
            )
        over = row.get("over")
        for role in (row.get("fg"), row.get("bg"), over):
            if role is not None and role not in role_keys:
                raise StyleCatalogError(f"{where}[{i}]: unknown role {role!r}")
        if not row.get("fg") or not row.get("bg"):
            raise StyleCatalogError(f"{where}[{i}]: 'fg' and 'bg' are required")
        pairs.append(
            ContrastPair(
                fg=row["fg"],
                bg=row["bg"],
                kind=kind,
                over=over,
                note=str(row.get("note", "")),
            )
        )
    return tuple(pairs)


class StyleCatalog:
    """The validated styles, modes, role maps, templates and declared pairs."""

    def __init__(self, root: Traversable) -> None:
        """Load and validate everything under ``root``.

        Args:
            root: The themes folder (``importlib.resources`` traversable or path).

        Raises:
            StyleCatalogError: On any missing, malformed or inconsistent file.
        """
        index = _dict(_read_json(root.joinpath(_INDEX_FILE), _INDEX_FILE), _INDEX_FILE)
        _check_format(index, _INDEX_FILE)
        self._styles = _str_list(index.get("styles"), f"{_INDEX_FILE} styles")
        self._modes = _str_list(index.get("modes"), f"{_INDEX_FILE} modes")
        self._default_style = str(index.get("default_style"))
        self._default_mode = str(index.get("default_mode"))
        if self._default_style not in self._styles:
            raise StyleCatalogError(f"{_INDEX_FILE}: default_style is not a style")
        if self._default_mode not in self._modes:
            raise StyleCatalogError(f"{_INDEX_FILE}: default_mode is not a mode")
        self._roles: Dict[str, Dict[str, Dict[str, str]]] = {}
        reference: Optional[Tuple[str, Set[str]]] = None
        for style in self._styles:
            where = f"{style}/{_ROLES_FILE}"
            doc = _dict(_read_json(root.joinpath(style, _ROLES_FILE), where), where)
            self._roles[style] = _load_roles(style, doc, self._modes, where)
            for mode, roles in self._roles[style].items():
                keys = set(roles)
                if reference is None:
                    reference = (f"{style}/{mode}", keys)
                elif keys != reference[1]:
                    diff = sorted(keys ^ reference[1])
                    raise StyleCatalogError(
                        f"{style}/{mode}: role keys differ from {reference[0]}: {diff}"
                    )
        if reference is None:  # unreachable: _str_list rejects an empty list
            raise StyleCatalogError(f"{_INDEX_FILE}: no styles")
        self._role_keys = tuple(sorted(reference[1]))
        keyset = set(self._role_keys)
        self._templates: Dict[str, TemplateSet] = {}
        for style in self._styles:
            self._templates[style] = _load_template_set(
                style, root.joinpath(style), keyset
            )
        first = self._styles[0]
        names = set(self._templates[first].templates)
        for style in self._styles[1:]:
            other = set(self._templates[style].templates)
            if other != names:
                raise StyleCatalogError(
                    f"{style}/{_TEMPLATES_FILE}: template names differ from "
                    f"{first}: {sorted(other ^ names)}"
                )
        self._pairs = _load_pairs(
            _read_json(root.joinpath(_PAIRS_FILE), _PAIRS_FILE), keyset
        )

    def style_ids(self) -> Tuple[str, ...]:
        """Return the style ids in menu order."""
        return self._styles

    def default_style(self) -> str:
        """Return the default style id."""
        return self._default_style

    def default_mode(self) -> str:
        """Return the default mode id."""
        return self._default_mode

    def mode_ids(self) -> Tuple[str, ...]:
        """Return the mode ids in index order."""
        return self._modes

    def role_keys(self) -> Tuple[str, ...]:
        """Return the sorted role keys common to every (style, mode)."""
        return self._role_keys

    def role_map(self, style: str, mode: str) -> Dict[str, str]:
        """Return a copy of the role map of ``style`` in ``mode``.

        Raises:
            StyleCatalogError: If the style or the mode is unknown.
        """
        try:
            return dict(self._roles[style][mode])
        except KeyError:
            raise StyleCatalogError(f"unknown style/mode {style!r}/{mode!r}") from None

    def template_set(self, style: str) -> TemplateSet:
        """Return the templates of ``style``.

        Raises:
            StyleCatalogError: If the style is unknown.
        """
        try:
            return self._templates[style]
        except KeyError:
            raise StyleCatalogError(f"unknown style {style!r}") from None

    def contrast_pairs(self) -> Tuple[ContrastPair, ...]:
        """Return the declared pairs (focus pairs are derived, not listed)."""
        return self._pairs


def load_catalog(root: Optional[Traversable] = None) -> StyleCatalog:
    """Build a validated catalogue from ``root`` (default: the shipped data).

    Args:
        root: A themes folder; ``None`` reads ``pixelart_creator/themes`` through
            ``importlib.resources``.

    Raises:
        StyleCatalogError: If the data is invalid.
    """
    if root is None:
        root = resources.files(_PACKAGE).joinpath(_THEMES_DIR)
    return StyleCatalog(root)


@functools.lru_cache(maxsize=None)
def _default_catalog() -> StyleCatalog:
    return load_catalog()


def reset_default_catalog() -> None:
    """Forget the cached shipped catalogue (for tests that swap the data)."""
    _default_catalog.cache_clear()


def style_ids() -> Tuple[str, ...]:
    """Return the shipped style ids in menu order."""
    return _default_catalog().style_ids()


def default_style() -> str:
    """Return the shipped default style id."""
    return _default_catalog().default_style()


def default_mode() -> str:
    """Return the shipped default mode id."""
    return _default_catalog().default_mode()


def mode_ids() -> Tuple[str, ...]:
    """Return the shipped mode ids."""
    return _default_catalog().mode_ids()


def role_keys() -> Tuple[str, ...]:
    """Return the sorted role keys shared by every shipped (style, mode)."""
    return _default_catalog().role_keys()


def role_map(style: str, mode: str) -> Dict[str, str]:
    """Return a copy of the shipped role map of ``style`` in ``mode``."""
    return _default_catalog().role_map(style, mode)


def template_set(style: str) -> TemplateSet:
    """Return the shipped templates of ``style``."""
    return _default_catalog().template_set(style)


def contrast_pairs() -> Tuple[ContrastPair, ...]:
    """Return the shipped declared contrast pairs."""
    return _default_catalog().contrast_pairs()
