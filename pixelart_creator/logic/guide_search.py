# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""In-app User Guide search — a pure query over indexed topic text (zero Qt, S11).

A single pure, deterministic, case-insensitive :func:`query` over the built
:class:`~pixelart_creator.logic.guide_model.GuideModel` (spec `REQ-UG-LOGIC-003`;
ADR-0029 §6). It matches over each topic's **indexed text** — its title, keywords,
and summary (full-body indexing is a HOW refinement deferred by CL-2) — returns the
matching topics in the model's deterministic section→topic order, and caps the
result count at :data:`~pixelart_creator.logic.constants.GUIDE_SEARCH_RESULT_CAP`.
An empty/whitespace term yields the full topic set (a filter that narrows as the
user types, CL-2). Zero Qt; unit-testable independently of the viewer.

Localisation (``REQ-L10N-UI-008``): given a ``LocaleMeta`` (see
:mod:`pixelart_creator.logic.guide_model`), the index holds the **active language's**
title, keywords and summary (each falling back to English per item) **and** the
English keywords, so a user can find a topic by either. Without metadata the index is
the English one.
"""

from __future__ import annotations

from pixelart_creator.logic.constants import GUIDE_SEARCH_RESULT_CAP
from pixelart_creator.logic.guide_model import (
    GuideModel,
    GuideTopic,
    LocaleMeta,
    localised_keywords,
    localised_summary,
    localised_title,
)

__all__ = ["query", "indexed_text"]


def indexed_text(topic: GuideTopic, meta: LocaleMeta | None = None) -> str:
    """Return the lower-cased searchable text for ``topic``.

    The deterministic index a :func:`query` term is matched against (CL-2): the
    topic's title, keywords and summary in the language of ``meta`` (each falling
    back to English per item), followed by the English keywords
    (``REQ-L10N-UI-008``). With ``meta`` ``None`` the text is the English title,
    keywords and summary, as before. Body text is intentionally excluded (a future
    HOW refinement behind this same function).

    Args:
        topic: The topic to index.
        meta: The active language's metadata, or ``None`` for English.
    """
    keywords = localised_keywords(topic, meta)
    parts = (localised_title(topic, meta), *keywords, localised_summary(topic, meta))
    if keywords is not topic.keywords:
        parts = (*parts, *topic.keywords)
    return " ".join(parts).lower()


def query(
    model: GuideModel,
    term: str,
    *,
    cap: int = GUIDE_SEARCH_RESULT_CAP,
    meta: LocaleMeta | None = None,
) -> tuple[GuideTopic, ...]:
    """Return the topics matching ``term``, in model order, capped at ``cap``.

    Pure, deterministic, case-insensitive. A term is a match when its stripped,
    lower-cased form is a substring of a topic's :func:`indexed_text` (the active
    language's title, keywords and summary plus the English keywords). An
    empty/whitespace ``term`` returns the full topic set (CL-2). Ordering is the
    model's section→topic order; at most ``cap`` topics are returned.

    Args:
        model: The built guide model to search.
        term: The user's search/filter term (case-insensitive; may be empty).
        cap: Maximum number of results (defaults to
            :data:`~pixelart_creator.logic.constants.GUIDE_SEARCH_RESULT_CAP`;
            a negative cap yields no results).
        meta: The active language's metadata, or ``None`` for English; with it the
            term also matches the active language's text (``REQ-L10N-UI-008``).

    Returns:
        The matching topics, ordered and capped.
    """
    topics = model.topics()
    needle = term.strip().lower()
    if not needle:
        matches: tuple[GuideTopic, ...] = topics
    else:
        matches = tuple(
            topic for topic in topics if needle in indexed_text(topic, meta)
        )
    if cap < 0:
        return ()
    return matches[:cap]
