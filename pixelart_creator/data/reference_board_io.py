"""Read/write the ``.pixboard`` reference-board layout (zero Qt, S11; DEP-4).

Defensive, ``eval``-free (de)serialisation of a PureRef-style reference board
(REQ-P9-DATA-002; ADR-0024 §3 / ADR-0025 §3), reusing the ``data.project_io`` IO-3
posture: plain JSON — ``schema_version`` + board view state (pan/zoom) + an ordered
list of reference-image records ``{image (path reference **or** embedded base64),
transform (2x3 affine as 6 floats), crop (x, y, w, h), z_order}``. **Every field is
type/bounds/version-checked on load**, a malformed / unknown-version document raises
:class:`ReferenceBoardIOError` (surfaced to the user, never a crash/execution), and
content is **never** passed to ``eval``/``exec``. Paths are :mod:`pathlib`-portable.

The pure :class:`ReferenceBoardLayout` / :class:`ReferenceImageEntry` dataclasses
live here in ``data/`` (no Qt): the serialiser round-trips a plain model and the
``ui/`` reference board maps it to ``QGraphicsPixmapItem`` s (ADR-0024 §3). The board
is **non-destructive** — nothing here touches the document or its undo history
(REQ-P9-UI-010). Round-trip identity is the acceptance gate (SC-UI-006-1).

Layering: ``data -> logic`` (imports ``logic.constants``) and ``data -> data``
(``ReferenceBoardIOError`` extends ``project_io.ProjectIOError``); never
``logic -> data``. Zero Qt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple, Union, cast

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.constants import MAX_REFERENCE_IMAGES

__all__ = [
    "ReferenceBoardIOError",
    "FORMAT_NAME",
    "FILE_SUFFIX",
    "REFERENCE_BOARD_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "ReferenceImageEntry",
    "ReferenceBoardLayout",
    "serialize",
    "deserialize",
    "save_board",
    "load_board",
]

FORMAT_NAME = "pixboard"
FILE_SUFFIX = ".pixboard"

#: Reference-board wire schema version — a module-local format-intrinsic string
#: (ADR-0001 / BF-2, the macro/timelapse precedent).
REFERENCE_BOARD_SCHEMA_VERSION: str = "1"

#: Schema versions this build can load (ADR-0025 §3).
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (REFERENCE_BOARD_SCHEMA_VERSION,)


class ReferenceBoardIOError(ProjectIOError):
    """Raised when a reference board cannot be serialised or is malformed on load."""


@dataclass(frozen=True)
class ReferenceImageEntry:
    """One reference image on the board (a pure model — no Qt).

    Attributes:
        image: A path reference **or** an embedded base64 payload for the image.
        transform: A 2x3 affine as six floats ``(a, b, c, d, e, f)``.
        crop: The visible crop rectangle ``(x, y, w, h)`` (``w >= 0``, ``h >= 0``).
        z_order: The stacking order (higher draws in front).
    """

    image: str
    transform: Tuple[float, float, float, float, float, float]
    crop: Tuple[float, float, float, float]
    z_order: int

    def __post_init__(self) -> None:
        """Validate the image ref, affine, crop and z-order."""
        if not isinstance(self.image, str) or not self.image:
            raise ReferenceBoardIOError(
                f"image must be a non-empty str, got {self.image!r}"
            )
        transform = _require_floats(self.transform, 6, "transform")
        object.__setattr__(self, "transform", transform)
        crop = _require_floats(self.crop, 4, "crop")
        if crop[2] < 0.0 or crop[3] < 0.0:
            raise ReferenceBoardIOError("crop width/height must be >= 0")
        object.__setattr__(self, "crop", crop)
        if isinstance(self.z_order, bool) or not isinstance(self.z_order, int):
            raise ReferenceBoardIOError(f"z_order must be an int, got {self.z_order!r}")


@dataclass(frozen=True)
class ReferenceBoardLayout:
    """A reference-board layout: view state + ordered images (a pure model).

    Attributes:
        schema_version: The format-intrinsic version string.
        pan: The board pan ``(x, y)``.
        zoom: The board zoom factor (``> 0``).
        images: The ordered reference images; ``<= MAX_REFERENCE_IMAGES``.
    """

    schema_version: str = REFERENCE_BOARD_SCHEMA_VERSION
    pan: Tuple[float, float] = (0.0, 0.0)
    zoom: float = 1.0
    images: Tuple[ReferenceImageEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate the schema version, pan, zoom and image count."""
        if not isinstance(self.schema_version, str):
            raise ReferenceBoardIOError(
                f"schema_version must be a str, got {self.schema_version!r}"
            )
        pan = _require_floats(self.pan, 2, "pan")
        object.__setattr__(self, "pan", pan)
        if isinstance(self.zoom, bool) or not isinstance(self.zoom, (int, float)):
            raise ReferenceBoardIOError(f"zoom must be a number, got {self.zoom!r}")
        if not (self.zoom > 0.0):
            raise ReferenceBoardIOError(f"zoom must be > 0, got {self.zoom}")
        object.__setattr__(self, "zoom", float(self.zoom))
        images = tuple(self.images)
        object.__setattr__(self, "images", images)
        if len(images) > MAX_REFERENCE_IMAGES:
            raise ReferenceBoardIOError(
                f"{len(images)} images exceeds MAX_REFERENCE_IMAGES "
                f"({MAX_REFERENCE_IMAGES})"
            )
        for entry in images:
            if not isinstance(entry, ReferenceImageEntry):
                raise ReferenceBoardIOError(
                    f"expected a ReferenceImageEntry, got {entry!r}"
                )


# --------------------------------------------------------------------------- #
# Serialisation                                                               #
# --------------------------------------------------------------------------- #


def serialize(layout: ReferenceBoardLayout) -> Dict[str, Any]:
    """Serialise a :class:`ReferenceBoardLayout` to a plain JSON-ready dict."""
    if not isinstance(layout, ReferenceBoardLayout):
        raise ReferenceBoardIOError(f"expected a ReferenceBoardLayout, got {layout!r}")
    return {
        "format": FORMAT_NAME,
        "schema_version": layout.schema_version,
        "pan": list(layout.pan),
        "zoom": layout.zoom,
        "images": [
            {
                "image": entry.image,
                "transform": list(entry.transform),
                "crop": list(entry.crop),
                "z_order": entry.z_order,
            }
            for entry in layout.images
        ],
    }


def save_board(layout: ReferenceBoardLayout, path: Union[str, Path]) -> Path:
    """Serialise ``layout`` and write it to ``path`` (adds ``.pixboard``)."""
    target = Path(path)
    if target.suffix != FILE_SUFFIX:
        target = target.with_suffix(FILE_SUFFIX)
    payload = serialize(layout)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Deserialisation (defensive)                                                 #
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReferenceBoardIOError(message)


def _require_floats(value: Any, count: int, name: str) -> Tuple[float, ...]:
    """Return ``value`` as a ``count``-tuple of finite floats, else raise."""
    if not isinstance(value, (tuple, list)) or len(value) != count:
        raise ReferenceBoardIOError(f"{name} must be {count} numbers, got {value!r}")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ReferenceBoardIOError(f"{name} entries must be numbers")
        out.append(float(item))
    return tuple(out)


def deserialize(payload: Dict[str, Any]) -> ReferenceBoardLayout:
    """Reconstruct a :class:`ReferenceBoardLayout` from a parsed dict.

    Raises:
        ReferenceBoardIOError: If the root, ``schema_version``, view state, or any
            image record is missing, mistyped, out of bounds, or the version is
            unsupported.
    """
    _require(isinstance(payload, dict), "reference board root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixboard file")
    schema_version: Any = payload.get("schema_version")
    _require(isinstance(schema_version, str), "schema_version must be a string")
    _require(
        schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported reference-board schema_version {schema_version!r}; "
        f"supported: {SUPPORTED_SCHEMA_VERSIONS}",
    )
    pan = _require_floats(payload.get("pan"), 2, "pan")
    zoom: Any = payload.get("zoom")
    _require(
        isinstance(zoom, (int, float)) and not isinstance(zoom, bool),
        "zoom must be a number",
    )
    images_raw: Any = payload.get("images")
    _require(isinstance(images_raw, list), "images must be a list")
    _require(
        len(images_raw) <= MAX_REFERENCE_IMAGES,
        f"images exceeds MAX_REFERENCE_IMAGES ({MAX_REFERENCE_IMAGES})",
    )
    entries = []
    for raw in images_raw:
        _require(isinstance(raw, dict), "each image must be a JSON object")
        image: Any = raw.get("image")
        _require(
            isinstance(image, str) and bool(image), "image must be a non-empty str"
        )
        transform = _require_floats(raw.get("transform"), 6, "transform")
        crop = _require_floats(raw.get("crop"), 4, "crop")
        z_order: Any = raw.get("z_order")
        _require(
            isinstance(z_order, int) and not isinstance(z_order, bool),
            "z_order must be an int",
        )
        entries.append(
            ReferenceImageEntry(
                image=image,
                transform=cast(
                    "Tuple[float, float, float, float, float, float]", transform
                ),
                crop=cast("Tuple[float, float, float, float]", crop),
                z_order=z_order,
            )
        )
    return ReferenceBoardLayout(
        schema_version=schema_version,
        pan=cast("Tuple[float, float]", pan),
        zoom=float(zoom),
        images=tuple(entries),
    )


def load_board(path: Union[str, Path]) -> ReferenceBoardLayout:
    """Read and validate a ``.pixboard`` file into a :class:`ReferenceBoardLayout`."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReferenceBoardIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReferenceBoardIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize(payload)
