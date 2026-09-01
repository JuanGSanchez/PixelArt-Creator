# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Persist the Favourites list to an app-level JSON store (zero Qt, S11).

A small, defensive JSON reader/writer for the colour-hub Favourites, mirroring
``data/project_io.py`` (ADR-0004). The caller (the UI) resolves the app-config
directory via ``QStandardPaths`` and passes a :class:`~pathlib.Path`; this module
never imports Qt and never resolves paths itself, so ``data/`` stays Qt-free
(Article I). Loading is defensive: a missing file yields an empty
:class:`~pixelart_creator.logic.favourites.Favourites`, and malformed content
raises :class:`FavouritesIOError` (never crashes, Article VII). Paths use
:mod:`pathlib` for portability (``path_portability_check``). REQ-P3-LOGIC-015
persistence substrate; SC-U004-3.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Union

from pixelart_creator.logic.favourites import Favourites, FavouritesError

__all__ = ["FavouritesIOError", "save_favourites", "load_favourites"]

_PathLike = Union[str, "os.PathLike[str]"]


class FavouritesIOError(ValueError):
    """Raised when the favourites store cannot be written or is malformed."""


def save_favourites(path: _PathLike, favourites: Favourites) -> Path:
    """Serialise ``favourites`` to ``path`` as JSON (a list of hex colours).

    Returns:
        The :class:`~pathlib.Path` written.

    Raises:
        FavouritesIOError: If the file cannot be written.
    """
    target = Path(path)
    try:
        target.write_text(json.dumps(favourites.to_serializable()), encoding="utf-8")
    except OSError as exc:
        raise FavouritesIOError(f"cannot write {target}: {exc}") from exc
    return target


def load_favourites(path: _PathLike) -> Favourites:
    """Read and validate the favourites store at ``path``.

    A missing file returns an empty :class:`Favourites` (first-run friendly);
    malformed JSON or content raises :class:`FavouritesIOError`.

    Raises:
        FavouritesIOError: If the file exists but is unreadable or malformed.
    """
    target = Path(path)
    if not target.exists():
        return Favourites()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise FavouritesIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FavouritesIOError(f"{target} is not valid JSON: {exc}") from exc
    try:
        return Favourites.from_serializable(payload)
    except FavouritesError as exc:
        raise FavouritesIOError(f"malformed favourites in {target}: {exc}") from exc
