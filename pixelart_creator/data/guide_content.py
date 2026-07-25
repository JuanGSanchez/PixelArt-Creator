"""Offline bundled-content reader for the in-app User Guide (zero Qt, S11).

The defensive ``data/`` reader for the committed, distributable content bundle
``pixelart_creator/userguide_content/`` (ADR-0029; spec `REQ-UG-DATA-001/-002/-003`).
It locates the bundle root via :func:`importlib.resources.files` (portable across the
source tree, a wheel, and a zip — no hardcoded separators, ``path_portability_check``),
reads and validates ``manifest.json`` into a
:class:`~pixelart_creator.logic.guide_model.Manifest`, and reads a manifest-known
per-topic Markdown resource as **text**.

Security posture (Article VII / REQ-UG-DATA-003): **no network access, ever**;
content is returned as text/markup and is **never** passed to ``eval``/``exec``; a
**bundle-root path guard** rejects any content reference that could escape the bundle
(``..`` / absolute / drive-letter / backslash segments); and a per-file **size guard**
(:data:`~pixelart_creator.logic.constants.GUIDE_MAX_CONTENT_BYTES`) bounds a
malformed/oversized resource *before* decode. Missing/malformed content raises a
domain :class:`GuideContentError` (a ``ValueError``, the repo convention), never a
crash. This module imports only from ``logic`` (the domain types) — never from ``ui``
— keeping the one-way ``data → logic`` dependency (Article I).
"""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from pixelart_creator.logic.constants import GUIDE_MAX_CONTENT_BYTES
from pixelart_creator.logic.guide_model import (
    CONTENT_DIR_NAME,
    GuideSection,
    GuideTopic,
    Manifest,
)

__all__ = [
    "GuideContentError",
    "bundle_root",
    "load_manifest",
    "read_content",
    "available_locales",
    "BUNDLE_PACKAGE",
    "BUNDLE_DIR_NAME",
    "MANIFEST_FILE_NAME",
]

#: The importable package the content bundle is shipped inside (package data).
BUNDLE_PACKAGE = "pixelart_creator"

#: The bundle directory name under :data:`BUNDLE_PACKAGE` (a package-data sibling of
#: ``logic/``/``data/``/``ui/``; carries only ``.md`` + ``.json`` — no Python).
BUNDLE_DIR_NAME = "userguide_content"

#: The discovery/ordering manifest file name at the bundle root.
MANIFEST_FILE_NAME = "manifest.json"

#: Logical resource-path separator for a bundle content reference (forward slash —
#: the importlib.resources convention; never an OS separator).
_REF_SEP = "/"

#: Path segments that would escape the bundle root or denote a non-portable path.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})


class GuideContentError(ValueError):
    """Raised when the guide bundle is missing, malformed, oversized, or unsafe.

    Subclasses ``ValueError`` (the repo-wide domain-exception convention). Raised for
    a missing/unreadable resource, a malformed ``manifest.json`` (bad JSON or failed
    type/bounds check), an over-size content file, or a content reference that fails
    the bundle-root path guard (traversal / absolute / backslash / drive letter).
    """


def bundle_root() -> Traversable:
    """Return the traversable root of the committed content bundle.

    Uses :func:`importlib.resources.files` so the path resolves portably whether the
    package is an on-disk source tree, an installed wheel, or a zip import.
    """
    return resources.files(BUNDLE_PACKAGE) / BUNDLE_DIR_NAME


def _require(condition: bool, message: str) -> None:
    """Raise :class:`GuideContentError` with ``message`` when ``condition`` is false."""
    if not condition:
        raise GuideContentError(message)


def _as_str(value: Any, field: str) -> str:
    """Return ``value`` as a non-empty ``str`` or raise ``GuideContentError``."""
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"guide manifest field {field!r} must be a non-empty string",
    )
    return value


def _as_str_tuple(value: Any, field: str) -> tuple[str, ...]:
    """Return ``value`` as a tuple of strings or raise ``GuideContentError``."""
    _require(
        isinstance(value, list) and all(isinstance(item, str) for item in value),
        f"guide manifest field {field!r} must be a list of strings",
    )
    return tuple(value)


def _parse_topic(raw: Any, where: str) -> GuideTopic:
    """Build a :class:`GuideTopic` from a raw manifest mapping (defensive)."""
    _require(
        isinstance(raw, dict), f"guide manifest topic in {where} must be an object"
    )
    return GuideTopic(
        id=_as_str(raw.get("id"), f"{where}.id"),
        title=_as_str(raw.get("title"), f"{where}.title"),
        content_ref=_as_str(raw.get("content"), f"{where}.content"),
        keywords=_as_str_tuple(raw.get("keywords", []), f"{where}.keywords"),
        summary=_as_str(raw.get("summary"), f"{where}.summary"),
    )


def _parse_section(raw: Any, index: int) -> GuideSection:
    """Build a :class:`GuideSection` from a raw manifest mapping (defensive)."""
    where = f"sections[{index}]"
    _require(isinstance(raw, dict), f"guide manifest {where} must be an object")
    topics_raw = raw.get("topics")
    _require(
        isinstance(topics_raw, list), f"guide manifest {where}.topics must be a list"
    )
    topics = tuple(
        _parse_topic(topic, f"{where}.topics[{i}]")
        for i, topic in enumerate(topics_raw)
    )
    return GuideSection(
        id=_as_str(raw.get("id"), f"{where}.id"),
        title=_as_str(raw.get("title"), f"{where}.title"),
        topics=topics,
    )


def load_manifest() -> Manifest:
    """Read and validate ``manifest.json`` from the bundle into a :class:`Manifest`.

    Defensive: a missing/unreadable file, non-JSON content, or a failed type/bounds
    check surfaces a :class:`GuideContentError` — never a crash (REQ-UG-DATA-001).

    Returns:
        The parsed, validated declaration (consumed by
        :func:`pixelart_creator.logic.guide_model.build_model`).

    Raises:
        GuideContentError: If the manifest is missing or malformed.
    """
    manifest_file = bundle_root() / MANIFEST_FILE_NAME
    try:
        raw_text = manifest_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise GuideContentError(f"guide manifest not readable: {exc}") from exc
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GuideContentError(f"guide manifest is not valid JSON: {exc}") from exc

    _require(isinstance(data, dict), "guide manifest root must be a JSON object")
    sections_raw = data.get("sections")
    _require(isinstance(sections_raw, list), "guide manifest 'sections' must be a list")
    schema_version = data.get("schema_version")
    _require(
        isinstance(schema_version, int) and not isinstance(schema_version, bool),
        "guide manifest 'schema_version' must be an integer",
    )
    default_locale = _as_str(data.get("default_locale"), "default_locale")
    sections = tuple(
        _parse_section(section, i) for i, section in enumerate(sections_raw)
    )
    return Manifest(
        schema_version=schema_version,
        default_locale=default_locale,
        sections=sections,
    )


def _guard_ref(content_ref: str) -> tuple[str, ...]:
    """Validate ``content_ref`` and return its safe path segments.

    The bundle-root path guard (REQ-UG-DATA-003 / Article VII): the reference must be
    a relative, forward-slash logical path whose every segment is a plain name — no
    empty/``.``/``..`` segment (traversal), no backslash, no drive letter/colon, and
    not absolute. A violation raises :class:`GuideContentError` (never silent access).
    """
    _require(
        isinstance(content_ref, str) and bool(content_ref),
        f"guide content ref must be a non-empty string: {content_ref!r}",
    )
    _require(
        "\\" not in content_ref,
        f"guide content ref must not contain a backslash: {content_ref!r}",
    )
    _require(
        not content_ref.startswith(_REF_SEP),
        f"guide content ref must be relative: {content_ref!r}",
    )
    segments = tuple(content_ref.split(_REF_SEP))
    for segment in segments:
        _require(
            segment not in _FORBIDDEN_SEGMENTS,
            f"guide content ref segment escapes the bundle root: {content_ref!r}",
        )
        _require(
            ":" not in segment,
            f"guide content ref segment is not portable: {content_ref!r}",
        )
    return segments


def read_content(content_ref: str) -> str:
    """Return the bundled Markdown text for a manifest-known ``content_ref``.

    Resolves ``content_ref`` (a forward-slash bundle-relative path, e.g.
    ``content/en/layers.md``) under the bundle root, enforcing the **bundle-root path
    guard** and the **size guard**
    (:data:`~pixelart_creator.logic.constants.GUIDE_MAX_CONTENT_BYTES`). The content is
    returned as **text** and never executed. **No network access.**

    Args:
        content_ref: The bundle-relative content path (from
            :func:`pixelart_creator.logic.guide_model.resolve_content_ref`).

    Returns:
        The decoded Markdown text.

    Raises:
        GuideContentError: If the ref fails the path guard, the resource is
            missing/unreadable, or its byte length exceeds the size guard.
    """
    segments = _guard_ref(content_ref)
    node: Traversable = bundle_root()
    for segment in segments:
        node = node / segment
    if not node.is_file():
        raise GuideContentError(f"guide content not found: {content_ref!r}")
    try:
        raw = node.read_bytes()
    except OSError as exc:
        raise GuideContentError(
            f"guide content not readable: {content_ref!r}: {exc}"
        ) from exc
    if len(raw) > GUIDE_MAX_CONTENT_BYTES:
        raise GuideContentError(
            f"guide content exceeds {GUIDE_MAX_CONTENT_BYTES} bytes: {content_ref!r}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuideContentError(
            f"guide content is not valid UTF-8: {content_ref!r}"
        ) from exc


def available_locales() -> frozenset[str]:
    """Return the set of locale codes present under the bundle's content directory.

    Discovers the shipped locales by listing the immediate sub-directories of
    ``content/`` (each ``content/<locale>/`` is one locale). Deterministic; a missing
    content directory yields the empty set (surfaced upstream as a coverage gap, not a
    crash).
    """
    content_root = bundle_root() / CONTENT_DIR_NAME
    if not content_root.is_dir():
        return frozenset()
    return frozenset(child.name for child in content_root.iterdir() if child.is_dir())
