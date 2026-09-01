# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""UI acceptance tests for the brand-logo app icon.

One test per acceptance criterion covering the runtime wiring: the loader
module (``pixelart_creator/ui/app_icon.py``), ``create_app()``,
``Main_Window.__init__`` and the in-app User Guide's document resource put in
place. Headless (``QT_QPA_PLATFORM=offscreen``, set by
``testing/suites/ui/conftest.py`` before any ``QApplication`` exists). Every test in
this module also runs once per theme via that conftest's autouse ``theme``
fixture (light + dark QSS applied to the shared ``qapp``) -- independent of the
*icon* itself, which carries no theme axis, but satisfies the "both themes"
UI-suite convention structurally with no per-test parametrisation needed here.

Deliberately NOT extending ``test_tool_icons.py``: that module covers the
eleven SVG toolbar glyphs and their tinting loader -- a different subject, a
different owner. This module owns the raster app/window/taskbar icon and the
guide's document-resource mark only.

The "every declared size" check is asserted against ``QIcon.availableSizes()``,
not merely against ``pixmap(n).isNull()``: a ``QIcon`` assembled from ONE large
raster (scaled per query with Qt's own smooth transform) would satisfy a
weaker non-null-pixmap-of-size-n check while silently returning a blurred
pixmap for every size but the one it was actually built from --
``availableSizes()`` reports the DISCRETE pixmaps a ``QIcon`` actually
carries, so it is the assertion that tells the two apart.

The missing-asset test never asserts on log wording (a diagnostic's message
is not this suite's contract) -- only that a WARNING-or-above record was
emitted on the loader's own logger while the asset resolves to nothing, and
that ``create_app()`` still completes with a null (never a crashing) icon.
The "unreadable asset" is simulated by redirecting the loader's own
resolution root to an empty scratch directory under ``tmp_path`` (D: drive,
per this job's scratch policy) -- never by touching a real committed asset,
which the "never mutate a real user artifact" rule forbids even temporarily.

The guide-logo-resource test asserts BOTH the positive (``pac-logo.png``
resolves to a real, non-null ``QImage`` once the real ``app-basics`` topic --
the one topic the shipped User Guide content actually carries the mark in --
has been rendered) and the negative (an absent resource url resolves to
``None``) against the REAL committed User Guide bundle. Without the negative,
"resolves" cannot be told apart from "resolves anything you ask it", which is
exactly the failure mode a typo'd resource url would produce silently.

``app_icon()``/``guide_logo_image()`` are process-global ``lru_cache``d (by
design -- built at most once per process). Because this module deliberately
exercises their FAILURE branch by redirecting the loader's resolution root,
an autouse fixture clears both caches before AND after every test in this
module, so no cached null/degraded icon leaks into a sibling test in this
file or into another UI module sharing the same pytest-xdist worker process.
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QTextDocument

import pixelart_creator.ui.app_icon as app_icon_module
import pixelart_creator.ui.main_window as main_window_module
from pixelart_creator.ui.app import DESKTOP_FILE_NAME, create_app
from pixelart_creator.ui.app_icon import RUNTIME_ICON_SIZES_PX, app_icon
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.user_guide import User_Guide_Dialog

#: The resource url the real committed guide content references
#: (``pixelart_creator/ui/user_guide.py``'s own ``_LOGO_RESOURCE_URL``,
#: matching the Markdown ``![PixelArt Creator](pac-logo.png)`` reference the
#: brand-logo delivery added to ``app-basics.md`` in both locale content trees).
_LOGO_RESOURCE_URL = "pac-logo.png"

#: The one real topic that carries the mark
#: (``userguide_content/manifest.json`` names its ``content`` ref ``"app-basics"``).
_LOGO_TOPIC_ID = "app-basics"


@pytest.fixture(autouse=True)
def _reset_icon_caches():
    """Clear the loader's process-global caches before AND after every test.

    ``app_icon()`` / ``guide_logo_image()`` are ``functools.lru_cache``d --
    built at most once per process by design. The missing-asset test
    deliberately drives their failure branch by redirecting resolution to an
    empty scratch directory; without this reset that redirected (null-icon)
    result would be cached and silently served to every later test in this
    file -- and to any other UI module sharing the same pytest-xdist worker
    process -- instead of the real asset family.
    """
    app_icon_module.app_icon.cache_clear()
    app_icon_module.guide_logo_image.cache_clear()
    yield
    app_icon_module.app_icon.cache_clear()
    app_icon_module.guide_logo_image.cache_clear()


def _available_sizes(icon) -> set:
    return {size.width() for size in icon.availableSizes()}


# --------------------------------------------------------------------------- #
# app_icon() carries every declared size, discretely.                         #
# --------------------------------------------------------------------------- #


def test_app_icon_carries_every_declared_size_as_a_distinct_pixmap(qapp):
    icon = app_icon()
    assert not icon.isNull(), "app_icon() returned a null QIcon"

    declared = set(RUNTIME_ICON_SIZES_PX)
    available = _available_sizes(icon)
    assert available == declared, (
        f"QIcon.availableSizes() widths {sorted(available)} != declared "
        f"RUNTIME_ICON_SIZES_PX {sorted(declared)} -- a QIcon assembled from "
        "one large raster (smooth-scaled per query) would carry only that "
        "one discrete size while still answering every pixmap() call, so "
        "this is the assertion that actually distinguishes 'every declared "
        "size present' from 'one size present, scaled on demand'"
    )
    for size in RUNTIME_ICON_SIZES_PX:
        pixmap = icon.pixmap(size, size)
        assert not pixmap.isNull(), f"icon.pixmap({size}, {size}) is null"
        assert (pixmap.width(), pixmap.height()) == (size, size), (
            f"icon.pixmap({size}, {size}) returned "
            f"{pixmap.width()}x{pixmap.height()}, not an exact {size}x{size}"
        )


# --------------------------------------------------------------------------- #
# create_app() sets the QApplication icon + desktop name.                     #
# --------------------------------------------------------------------------- #


def test_create_app_sets_application_icon_and_desktop_file_name(qtbot):
    app, window = create_app([])
    qtbot.addWidget(window)  # tracked -> drained/disposed by the conftest registry

    icon = app.windowIcon()
    assert not icon.isNull(), "QApplication.windowIcon() is null after create_app()"
    assert _available_sizes(icon) == set(
        RUNTIME_ICON_SIZES_PX
    ), "QApplication.windowIcon() does not carry the declared runtime size set"
    assert app.desktopFileName() == DESKTOP_FILE_NAME == "PixelArtCreator", (
        f"QApplication.desktopFileName() == {app.desktopFileName()!r}, expected "
        f"{DESKTOP_FILE_NAME!r} (the basename build_appimage.sh's .desktop entry "
        "expects, per app.py's DESKTOP_FILE_NAME docstring)"
    )


# --------------------------------------------------------------------------- #
# Main_Window sets its own icon once; retranslate does not re-set it.         #
# --------------------------------------------------------------------------- #


def test_window_icon_set_once_at_construction_not_by_retranslate(qtbot, monkeypatch):
    calls = []
    real_app_icon = main_window_module.app_icon

    def _counting_app_icon():
        calls.append(1)
        return real_app_icon()

    monkeypatch.setattr(main_window_module, "app_icon", _counting_app_icon)

    win = Main_Window()
    qtbot.addWidget(win)

    assert len(calls) == 1, (
        f"app_icon() was called {len(calls)} times during Main_Window.__init__, "
        "expected exactly 1"
    )
    icon = win.windowIcon()
    assert not icon.isNull(), "Main_Window.windowIcon() is null after construction"
    assert _available_sizes(icon) == set(
        RUNTIME_ICON_SIZES_PX
    ), "Main_Window.windowIcon() does not carry the declared runtime size set"

    # A language change is exactly the event class that already re-runs every
    # OTHER retranslatable string on this window (Main_Window.changeEvent ->
    # _retranslate) -- driven the same way test_phase6_retranslate.py drives it,
    # a real QEvent.LanguageChange through the real Qt override, not a private
    # method call.
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert len(calls) == 1, (
        "app_icon() was called again after a LanguageChange event -- the window "
        "icon must be set ONCE at construction; it is not a translatable string "
        "and must not be re-set by _retranslate()"
    )


# --------------------------------------------------------------------------- #
# A missing/unreadable asset degrades safely + logs a diagnostic.             #
# --------------------------------------------------------------------------- #


def test_unresolvable_asset_yields_null_icon_and_emits_a_diagnostic(
    qtbot, monkeypatch, caplog, tmp_path
):
    # A scratch directory under tmp_path (D: drive) that carries NONE of the
    # runtime assets -- simulates "missing/unreadable" without touching a real
    # committed asset (the "never mutate a real user artifact" rule).
    empty_root = tmp_path / "scratch-icons-app"
    empty_root.mkdir()
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: empty_root)

    with caplog.at_level(logging.WARNING, logger="pixelart_creator.ui.app_icon"):
        app, window = create_app([])
    qtbot.addWidget(window)

    assert app.windowIcon().isNull(), (
        "a missing/unreadable app-icon asset must degrade to a null QIcon; "
        "create_app() must still complete rather than raise"
    )
    diagnostics = [
        record
        for record in caplog.records
        if record.name == "pixelart_creator.ui.app_icon"
        and record.levelno >= logging.WARNING
    ]
    assert diagnostics, (
        "no diagnostic record was emitted on the app_icon logger while the asset "
        "family was unresolvable -- a failure like this must be surfaced through "
        "the existing logging path, never swallowed silently (this assertion "
        "checks a record was emitted, not its wording)"
    )


# --------------------------------------------------------------------------- #
# The guide logo resolves as an in-memory document resource.                  #
# --------------------------------------------------------------------------- #


def test_guide_logo_resource_resolves_positive_and_negative(qtbot):
    dialog = User_Guide_Dialog(None)  # the REAL committed bundle (model=None)
    qtbot.addWidget(dialog)

    dialog.show_topic(_LOGO_TOPIC_ID)
    document = dialog._content_view.document()

    # Positive control: the real, committed markdown reference resolves to a
    # real, non-empty in-memory image (registered AFTER setMarkdown, so it is
    # already available when Qt resolves the reference it just parsed).
    resolved = document.resource(
        QTextDocument.ResourceType.ImageResource, QUrl(_LOGO_RESOURCE_URL)
    )
    assert resolved is not None, (
        f"{_LOGO_RESOURCE_URL!r} did not resolve as a QTextDocument image resource "
        f"after rendering the {_LOGO_TOPIC_ID!r} topic"
    )
    assert not resolved.isNull(), f"{_LOGO_RESOURCE_URL!r} resolved to a null QImage"
    assert resolved.width() > 0 and resolved.height() > 0, (
        f"{_LOGO_RESOURCE_URL!r} resolved to an empty "
        f"({resolved.width()}x{resolved.height()}) image"
    )

    # Negative control: an absent url must resolve to None -- without this,
    # "resolves" cannot be told apart from "resolves anything you ask it".
    absent = document.resource(
        QTextDocument.ResourceType.ImageResource, QUrl("does-not-exist.png")
    )
    assert absent is None, (
        f"an absent resource url resolved to {absent!r} instead of None -- the "
        "positive result above is not evidence of a real, url-scoped resolution "
        "without this negative control"
    )


# --------------------------------------------------------------------------- #
# Coverage: the app_icon() loader's decode-failure and unreadable-file paths. #
# --------------------------------------------------------------------------- #


class _UnreadableAsset:
    """A traversable-like node that EXISTS but raises ``OSError`` on read.

    Distinct from the missing-asset case above (``is_file()`` returning
    ``False``): this simulates a file that is present but cannot actually be
    read (a permission fault, a race with deletion, a locked handle) -- the
    ``except OSError`` branch in ``app_icon.py``'s ``_asset_bytes``, which the
    missing-asset scenario never reaches because it never gets past
    ``is_file()``.
    """

    def __truediv__(self, _other):
        return self

    def is_file(self):
        return True

    def read_bytes(self):
        raise OSError(13, "simulated permission fault")


def test_unreadable_existing_asset_yields_null_icon_and_logs_unreadable(
    qapp, monkeypatch, caplog
):
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: _UnreadableAsset())

    with caplog.at_level(logging.WARNING, logger="pixelart_creator.ui.app_icon"):
        icon = app_icon_module.app_icon()

    assert icon.isNull(), (
        "an asset that exists but raises OSError on read must still degrade to "
        "a null QIcon, exactly like a missing asset"
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "pixelart_creator.ui.app_icon"
        and record.levelno >= logging.WARNING
    ]
    assert any("unreadable" in message for message in messages), (
        f"expected an 'unreadable' diagnostic distinguishing this OSError case "
        f"from a plain missing file; got {messages!r}"
    )


def test_undecodable_asset_bytes_yield_null_icon_and_log_decode_failure(
    qapp, monkeypatch, caplog, tmp_path
):
    # A real scratch directory (D: drive, tmp_path) carrying a file at the
    # FIRST size app_icon() requests (RUNTIME_ICON_SIZES_PX is largest-first)
    # whose bytes are not a decodable image at all -- QPixmap.loadFromData
    # returns False without raising, which is the branch under test.
    scratch = tmp_path / "scratch-icons-undecodable"
    scratch.mkdir()
    first_size = RUNTIME_ICON_SIZES_PX[0]
    (scratch / f"app-icon-{first_size}.png").write_bytes(b"not a real png payload")
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: scratch)

    with caplog.at_level(logging.WARNING, logger="pixelart_creator.ui.app_icon"):
        icon = app_icon_module.app_icon()

    assert icon.isNull(), (
        "an asset whose bytes fail to decode as an image must degrade to a "
        "null QIcon, never raise and never return a partially-built icon"
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "pixelart_creator.ui.app_icon"
        and record.levelno >= logging.WARNING
    ]
    assert any("decode" in message for message in messages), (
        f"expected a 'failed to decode' diagnostic distinguishing this bad-bytes "
        f"case from a missing/unreadable file; got {messages!r}"
    )


def test_guide_logo_image_returns_none_when_asset_is_missing(monkeypatch, tmp_path):
    empty_root = tmp_path / "scratch-guide-logo-missing"
    empty_root.mkdir()
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: empty_root)

    assert app_icon_module.guide_logo_image() is None, (
        "guide_logo_image() must degrade to None when its asset is missing -- "
        "the User Guide is documented to open without the mark rather than "
        "fail to open"
    )


def test_guide_logo_image_returns_none_when_asset_bytes_do_not_decode(
    qapp, monkeypatch, caplog, tmp_path
):
    scratch = tmp_path / "scratch-guide-logo-undecodable"
    scratch.mkdir()
    (scratch / "app-icon-128.png").write_bytes(b"not a real png payload")
    monkeypatch.setattr(app_icon_module, "_icons_root", lambda: scratch)

    with caplog.at_level(logging.WARNING, logger="pixelart_creator.ui.app_icon"):
        result = app_icon_module.guide_logo_image()

    assert result is None, (
        "guide_logo_image() must return None, not a null/partial QImage, when "
        "its asset bytes fail to decode"
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "pixelart_creator.ui.app_icon"
        and record.levelno >= logging.WARNING
    ]
    assert any("decode" in message for message in messages), (
        f"expected a 'failed to decode' diagnostic on the guide-logo decode "
        f"failure path; got {messages!r}"
    )
