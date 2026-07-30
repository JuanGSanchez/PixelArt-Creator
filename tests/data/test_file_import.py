"""Tests for pixelart_creator.data.file_import (classify + error family).

Covers REQ-DDI-DATA-003 (file-type classification) and REQ-DDI-DATA-005 (the
shared, defensive import-error family) for the drag-drop import feature. Maps to
Gherkin SC-D003-1/-2 (extension routing, case-insensitivity), SC-D004-1 (.pixproj
routes to PROJECT) and SC-D005-2/-3 (one catchable base, no eval/exec).

``classify`` is a *pure* predicate over the path string: these tests assert it
never touches disk (paths that do not exist still classify) and is deterministic
for str and pathlib.Path inputs.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data import file_import
from pixelart_creator.data.file_import import (
    IMAGE_EXTENSIONS,
    PALETTE_EXTENSIONS,
    PALETTE_FORMAT_BY_EXTENSION,
    PROJECT_EXTENSION,
    FileImportError,
    FileType,
    ImageImportError,
    PaletteImportError,
    classify,
)

# --------------------------------------------------------------------------- #
# classify — extension routing (SC-D003-1)                                    #
# --------------------------------------------------------------------------- #

_IMAGE_CASES = [
    ("foo.png", FileType.IMAGE),
    ("a.jpg", FileType.IMAGE),
    ("b.jpeg", FileType.IMAGE),
    ("s.bmp", FileType.IMAGE),
    ("g.gif", FileType.IMAGE),
]
_PROJECT_CASES = [("p.pixproj", FileType.PROJECT)]
_PALETTE_CASES = [
    ("q.gpl", FileType.PALETTE),
    ("r.hex", FileType.PALETTE),
    ("t.pal", FileType.PALETTE),
]
_UNKNOWN_CASES = [
    ("z.txt", FileType.UNKNOWN),
    ("readme.md", FileType.UNKNOWN),
    ("archive.zip", FileType.UNKNOWN),
    ("noextension", FileType.UNKNOWN),
    ("weird.aco", FileType.UNKNOWN),  # deferred binary palette (CL-A6)
    ("weird.ase", FileType.UNKNOWN),
]


@pytest.mark.parametrize(
    "name, expected",
    _IMAGE_CASES + _PROJECT_CASES + _PALETTE_CASES + _UNKNOWN_CASES,
)
def test_classify_by_extension(name, expected):
    # SC-D003-1: each extension routes to exactly one FileType.
    assert classify(name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("PHOTO.PNG", FileType.IMAGE),
        ("Sprite.JpG", FileType.IMAGE),
        ("Proj.PIXPROJ", FileType.PROJECT),
        ("pal.GpL", FileType.PALETTE),
        ("list.HEX", FileType.PALETTE),
        ("jasc.PAL", FileType.PALETTE),
    ],
)
def test_classify_is_case_insensitive(name, expected):
    # SC-D003-2: upper/mixed case classifies like lower case.
    assert classify(name) == expected


def test_classify_accepts_str_and_path_equivalently():
    assert classify("dir/sub/image.png") == FileType.IMAGE
    assert classify(Path("dir/sub/image.png")) == FileType.IMAGE
    assert classify("x.gpl") == classify(Path("x.gpl")) == FileType.PALETTE


def test_classify_is_pure_no_disk_io(tmp_path):
    # The path need not exist — classify never reads the filesystem.
    missing = tmp_path / "does-not-exist.png"
    assert not missing.exists()
    assert classify(missing) == FileType.IMAGE


def test_classify_is_deterministic():
    for name in ("a.png", "b.gpl", "c.pixproj", "d.txt"):
        assert classify(name) == classify(name)


def test_classify_full_path_with_dotted_directories():
    # Only the final suffix matters, not dots earlier in the path.
    assert classify(Path("user.png.backup") / "sprite.gif") == FileType.IMAGE
    assert classify(Path("v1.2.3") / "palette.gpl") == FileType.PALETTE


def test_classify_dotfile_without_extension_is_unknown():
    # A leading-dot filename with no further suffix has no extension.
    assert classify(".gitignore") == FileType.UNKNOWN


@pytest.mark.parametrize("ext", sorted(IMAGE_EXTENSIONS))
def test_every_declared_image_extension_classifies_as_image(ext):
    assert classify(f"file{ext}") == FileType.IMAGE


@pytest.mark.parametrize("ext", sorted(PALETTE_EXTENSIONS))
def test_every_declared_palette_extension_classifies_as_palette(ext):
    assert classify(f"file{ext}") == FileType.PALETTE


def test_project_extension_constant_classifies_as_project():
    assert classify(f"file{PROJECT_EXTENSION}") == FileType.PROJECT


# --------------------------------------------------------------------------- #
# classify — property: case & directory invariance (SC-D003-2, NFR-2)         #
# --------------------------------------------------------------------------- #

_ALL_KNOWN = sorted(IMAGE_EXTENSIONS | PALETTE_EXTENSIONS | {PROJECT_EXTENSION})


@given(
    stem=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=12,
    ),
    ext=st.sampled_from(_ALL_KNOWN),
    upper=st.booleans(),
)
def test_classify_case_invariant_property(stem, ext, upper):
    # Randomising the extension case never changes the classification.
    name = f"{stem}{ext.upper() if upper else ext}"
    assert classify(name) == classify(f"{stem}{ext}")


@given(
    stem=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=8,
    ),
)
def test_classify_unknown_extension_property(stem):
    # A stem with an obviously-unknown extension is always UNKNOWN.
    assert classify(f"{stem}.zzz") == FileType.UNKNOWN


# --------------------------------------------------------------------------- #
# error family (SC-D005-3, ADR-0010)                                          #
# --------------------------------------------------------------------------- #


def test_import_errors_share_one_catchable_base():
    # SC-D005-3: the UI catches a single family.
    assert issubclass(PaletteImportError, FileImportError)
    assert issubclass(ImageImportError, FileImportError)
    assert issubclass(FileImportError, ValueError)


@pytest.mark.parametrize("exc_type", [PaletteImportError, ImageImportError])
def test_family_members_are_caught_as_file_import_error(exc_type):
    with pytest.raises(FileImportError):
        raise exc_type("boom")


def test_format_map_agrees_with_palette_extension_set():
    # The extension->fmt map keys are exactly the palette extension set.
    assert set(PALETTE_FORMAT_BY_EXTENSION) == set(PALETTE_EXTENSIONS)
    assert set(PALETTE_FORMAT_BY_EXTENSION.values()) == {"gpl", "hex", "pal"}


def test_no_eval_or_exec_in_import_source():
    # SC-D005-2 (static assertion): the import path never evals content.
    src = inspect.getsource(file_import)
    assert "eval(" not in src
    assert "exec(" not in src
