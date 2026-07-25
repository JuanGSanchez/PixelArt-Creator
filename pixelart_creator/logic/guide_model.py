"""In-app User Guide content model — the section→topic tree (zero Qt, S11).

Pure, deterministic domain model for the offline User Guide (ADR-0029; spec
`REQ-UG-LOGIC-001/-002/-004/-005`). It has **zero Qt** and does **no I/O**: the
defensive bundle reader in :mod:`pixelart_creator.data.guide_content` reads the
committed ``userguide_content/`` package data, validates it, and hands this module a
:class:`Manifest`; this module turns that declaration into an ordered, query-ready
:class:`GuideModel` (an ordered tree of :class:`GuideSection` → :class:`GuideTopic`
plus a flattened topic index), resolves a topic's content reference for the active
locale, and reports the coverage/completeness contract.

Discovery/extensibility (Article XI): the tree is built *entirely* from the
discovered manifest, so adding a topic/section is a data change (a new ``.md`` file
+ a manifest entry) with **no change here** (REQ-UG-LOGIC-002). Ordering is the
manifest order → deterministic (same bundle ⇒ same ToC).

Numerics come from :mod:`pixelart_creator.logic.constants` (S12). Section/topic ids
and the default locale code are **string identifiers**, not numeric tuning values
(Article II governs numerics), so ``DEFAULT_GUIDE_LOCALE`` is module-local here, not
in ``constants.py`` (ADR-0001; spec §9). ``GuideModelError`` (a ``ValueError``, the
repo convention) reports every malformed/inconsistent manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pixelart_creator.logic.constants import GUIDE_MAX_TOC_DEPTH

__all__ = [
    "GuideModelError",
    "GuideTopic",
    "GuideSection",
    "Manifest",
    "GuideModel",
    "build_model",
    "resolve_content_ref",
    "missing_required_areas",
    "REQUIRED_AREAS",
    "REQUIRED_AREA_TITLES",
    "DEFAULT_GUIDE_LOCALE",
    "CONTENT_DIR_NAME",
    "CONTENT_FILE_SUFFIX",
    "content_ref_path",
]

#: Fallback locale used when no localised doc exists for the active locale
#: (REQ-UG-LOGIC-004; CL-3). A STRING identifier, not a numeric — homed here, not in
#: ``constants.py`` (Article II; ADR-0001; spec §9).
DEFAULT_GUIDE_LOCALE = "en"

#: Sub-directory (under the bundle root) holding the per-locale content trees.
CONTENT_DIR_NAME = "content"

#: File suffix of a per-topic Markdown resource.
CONTENT_FILE_SUFFIX = ".md"

#: Logical resource-path separator for a bundle content reference. Bundle refs are
#: importlib.resources *logical* paths (always forward-slash), never OS paths, so
#: this is portable across the source tree, a wheel, and a zip (path_portability).
_REF_SEP = "/"


class GuideModelError(ValueError):
    """Raised when a guide manifest is malformed, inconsistent, or unknown.

    Subclasses ``ValueError`` (the repo-wide domain-exception convention) so callers
    can catch it uniformly. Raised for a duplicate/empty id, an over-deep tree, an
    unknown ``topic_id`` lookup, or a structurally invalid manifest.
    """


@dataclass(frozen=True)
class GuideTopic:
    """One leaf topic of the guide (a single content page).

    Attributes:
        id: Stable, unique topic identifier (a string; the ToC/link key).
        title: Human-readable topic title (chrome; localised at render time).
        content_ref: The locale-agnostic content *stem* (the ``.md`` base name,
            without locale directory or suffix) used to resolve the bundled file
            via :func:`resolve_content_ref` → :func:`content_ref_path`.
        keywords: Ordered search keywords indexed by :mod:`.guide_search`.
        summary: Short one-line description, also indexed for search.
    """

    id: str
    title: str
    content_ref: str
    keywords: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class GuideSection:
    """An ordered group of topics for one window / functionality area.

    Attributes:
        id: Stable, unique section identifier (matches a :data:`REQUIRED_AREAS`
            entry for a required area).
        title: Human-readable section title (chrome; localised at render time).
        topics: The section's topics, in declared (deterministic) order.
    """

    id: str
    title: str
    topics: tuple[GuideTopic, ...]


@dataclass(frozen=True)
class Manifest:
    """The parsed, validated guide declaration mirroring ``manifest.json``.

    Produced by :func:`pixelart_creator.data.guide_content.load_manifest` (which
    does the reading + defensive type/bounds checks) and consumed by
    :func:`build_model`. The domain declaration type is homed in this pure ``logic/``
    module — not in ``data/`` — so ``logic`` never imports ``data`` (Article I /
    ADR-0029 §6): the reader (``data``) imports these types from here and constructs
    a ``Manifest``, keeping the one-way ``data → logic`` dependency.

    Attributes:
        schema_version: The manifest schema version (forward-compat marker).
        default_locale: The bundle's default/source locale code.
        sections: The declared sections, in deterministic (declared) order.
    """

    schema_version: int
    default_locale: str
    sections: tuple[GuideSection, ...]


#: The functionality areas the guide MUST cover (REQ-UG-LOGIC-005; spec §2/§4). Each
#: entry is a required **section id**; a required area is "covered" when a section
#: with that id exists AND has ≥ 1 topic. Ordered for deterministic gap reporting.
REQUIRED_AREAS: tuple[str, ...] = (
    "app-basics",
    "canvas-and-view",
    "colour-hub",
    "layers",
    "selection-and-transform",
    "animation-timeline",
    "tileset-and-tilemap",
    "export-and-pipeline",
    "automation-and-scripting",
    "visual-aids",
    "cloud-and-collaboration",
    "asset-library",
)

#: Default human-readable titles for the required areas (used only to seed the
#: committed scaffold manifest; AGT-08 owns the authored titles/prose). Kept aligned
#: with :data:`REQUIRED_AREAS` for reference; not part of the coverage check.
REQUIRED_AREA_TITLES: dict[str, str] = {
    "app-basics": "Application Basics",
    "canvas-and-view": "Canvas & View",
    "colour-hub": "Colour Hub",
    "layers": "Layers",
    "selection-and-transform": "Selection & Transform",
    "animation-timeline": "Animation Timeline",
    "tileset-and-tilemap": "Tileset & Tilemap Editor",
    "export-and-pipeline": "Export & Pipeline",
    "automation-and-scripting": "Automation & Scripting",
    "visual-aids": "Visual Aids",
    "cloud-and-collaboration": "Cloud & Collaboration",
    "asset-library": "Asset Library",
}


class GuideModel:
    """An ordered section→topic tree with a flattened topic index.

    Immutable after construction. Built by :func:`build_model` from a validated
    :class:`Manifest`; the viewer (``ui/user_guide.py``) reads :attr:`sections` for
    the ToC and calls :meth:`topic` / :func:`.guide_search.query` — it never
    hard-codes the ToC (Article I).
    """

    __slots__ = ("_sections", "_index")

    def __init__(self, sections: tuple[GuideSection, ...]) -> None:
        """Store ``sections`` and build the ``topic_id → GuideTopic`` index.

        Prefer :func:`build_model` (which validates the manifest) over calling this
        directly. Assumes ``sections`` already have unique topic ids.
        """
        self._sections = sections
        index: dict[str, GuideTopic] = {}
        for section in sections:
            for topic in section.topics:
                index[topic.id] = topic
        self._index = index

    @property
    def sections(self) -> tuple[GuideSection, ...]:
        """The ordered sections (the ToC backbone)."""
        return self._sections

    def topics(self) -> tuple[GuideTopic, ...]:
        """All topics, flattened in deterministic section→topic order."""
        return tuple(topic for section in self._sections for topic in section.topics)

    def topic(self, topic_id: str) -> GuideTopic:
        """Return the topic with ``topic_id``.

        Raises:
            GuideModelError: If no topic has that id.
        """
        try:
            return self._index[topic_id]
        except KeyError:
            raise GuideModelError(f"unknown guide topic id: {topic_id!r}") from None


def _validate_id(kind: str, value: object) -> str:
    """Return ``value`` as a non-empty id string or raise ``GuideModelError``."""
    if not isinstance(value, str) or not value.strip():
        raise GuideModelError(f"guide {kind} id must be a non-empty string: {value!r}")
    return value


def _tree_depth(sections: tuple[GuideSection, ...]) -> int:
    """Return the achieved depth of the section→topic tree (0 if empty).

    A section alone is depth 1; a section with ≥ 1 topic is depth 2. (Sub-topics —
    a future manifest extension — would raise this; the ceiling guards that.)
    """
    depth = 0
    for section in sections:
        depth = max(depth, 2 if section.topics else 1)
    return depth


def build_model(manifest: Manifest) -> GuideModel:
    """Build the ordered :class:`GuideModel` from a validated ``manifest``.

    Deterministic: the ToC order is exactly the manifest's declared section/topic
    order (REQ-UG-LOGIC-002). Enforces globally-unique, non-empty section and topic
    ids and a tree depth within
    :data:`~pixelart_creator.logic.constants.GUIDE_MAX_TOC_DEPTH`.

    Args:
        manifest: The parsed declaration (from ``data.guide_content.load_manifest``).

    Returns:
        The immutable model.

    Raises:
        GuideModelError: On a duplicate/empty id or an over-deep tree.
    """
    seen_section_ids: set[str] = set()
    seen_topic_ids: set[str] = set()
    for section in manifest.sections:
        sid = _validate_id("section", section.id)
        if sid in seen_section_ids:
            raise GuideModelError(f"duplicate guide section id: {sid!r}")
        seen_section_ids.add(sid)
        for topic in section.topics:
            tid = _validate_id("topic", topic.id)
            _validate_id("topic content_ref", topic.content_ref)
            if tid in seen_topic_ids:
                raise GuideModelError(f"duplicate guide topic id: {tid!r}")
            seen_topic_ids.add(tid)

    depth = _tree_depth(manifest.sections)
    if depth > GUIDE_MAX_TOC_DEPTH:
        raise GuideModelError(
            f"guide ToC depth {depth} exceeds ceiling {GUIDE_MAX_TOC_DEPTH}"
        )
    return GuideModel(manifest.sections)


def content_ref_path(content_ref: str, locale: str) -> str:
    """Build the bundle-relative content path for ``content_ref`` in ``locale``.

    The returned logical resource path — ``content/<locale>/<content_ref>.md`` —
    uses forward slashes (the importlib.resources convention), so it is portable and
    is what :func:`pixelart_creator.data.guide_content.read_content` resolves + guards.
    """
    return _REF_SEP.join((CONTENT_DIR_NAME, locale, content_ref + CONTENT_FILE_SUFFIX))


def resolve_content_ref(
    model: GuideModel,
    topic_id: str,
    active_locale: str,
    *,
    default_locale: str = DEFAULT_GUIDE_LOCALE,
    available_locales: Iterable[str],
) -> str:
    """Resolve a topic's bundle content path for ``active_locale`` (pure).

    Returns the localised content path when a doc for the topic exists in
    ``active_locale`` (i.e. ``active_locale`` is in ``available_locales``), otherwise
    falls back to the ``default_locale`` path (REQ-UG-LOGIC-004; CL-3). Pure and
    deterministic — no I/O; the caller passes the set of locales that have this
    topic's content (the bundle-level set from
    :func:`pixelart_creator.data.guide_content.available_locales` when every topic
    ships in every locale, the current invariant).

    Args:
        model: The built model.
        topic_id: The topic to resolve.
        active_locale: The application's active locale code.
        default_locale: The fallback locale (defaults to :data:`DEFAULT_GUIDE_LOCALE`).
        available_locales: Locale codes for which the topic has a bundled doc.

    Returns:
        The bundle-relative content path (see :func:`content_ref_path`).

    Raises:
        GuideModelError: If ``topic_id`` is unknown.
    """
    topic = model.topic(topic_id)
    available = frozenset(available_locales)
    locale = active_locale if active_locale in available else default_locale
    return content_ref_path(topic.content_ref, locale)


def missing_required_areas(model: GuideModel) -> tuple[str, ...]:
    """Return the required areas not covered by ``model`` (empty ⇒ complete).

    A required area (a :data:`REQUIRED_AREAS` id) is covered when a section with that
    id exists AND has ≥ 1 topic — so "content present for each area" is a checkable
    property of the discovered set, and a missing area (e.g. cloud & collaboration) is
    a detectable gap, not a silent pass (REQ-UG-LOGIC-005). Ordered per
    :data:`REQUIRED_AREAS` for deterministic reporting.
    """
    covered = {section.id for section in model.sections if section.topics}
    return tuple(area for area in REQUIRED_AREAS if area not in covered)
