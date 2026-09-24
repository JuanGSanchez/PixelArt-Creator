"""Docs-content tests for the app-version feature (Qt-free).

Covers REQ-AV-DATA-001 (SC-AV-DATA-001-1, en + es: the in-app User Guide's
"App basics" page names the About entry and says the version also shows in the
window title) and the content half of REQ-AV-BUILD-002 (SC-AV-BUILD-002-1: the
documentation site describes the same, in both languages, on whichever page
the docs owner chooses per CL-AV-10 — this file does not name that page, it discovers
it). Also proves CL-AV-11 (NFR-2): no page quotes the current concrete
version.

The Spanish menu-entry wording is never typed into this file. It is read from
``pixelart_creator/i18n/pixelart_es.ts`` (stdlib ``xml.etree.ElementTree``),
under the context named for the main-window class itself (``pyside6-lupdate``
scopes a context to the innermost enclosing class name; that name is read via
``ast`` from ``pixelart_creator/ui/main_window.py`` rather than typed here, so
a rename of the class can't silently desync this suite from the catalogue —
see ``_main_window_context_name()``), the exact source string plan.md section
3.2 fixes for the action (``"&About PixelArt Creator"``), with the mnemonic
``&`` stripped — per this suite's own instruction.

RED-FIRST (NFR-5): at ``a77b5c0`` neither the guide pages, the
site pages, nor the ``.ts`` catalogue mention the About entry at all, so every
test below is expected to fail today — the assertion that finds the entry (or
its catalogue translation) fails first, before any of the later assertions in
the same test (including the "no version quoted" one, which would otherwise
hold true vacuously both before and after the feature ships, and so would not
by itself prove anything about the feature's presence).
"""

from __future__ import annotations

import ast
from pathlib import Path
from xml.etree import ElementTree

import pixelart_creator

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAIN_WINDOW_SOURCE = _REPO_ROOT / "pixelart_creator" / "ui" / "main_window.py"
_GUIDE_EN = (
    _REPO_ROOT
    / "pixelart_creator"
    / "userguide_content"
    / "content"
    / "en"
    / "app-basics.md"
)
_GUIDE_ES = (
    _REPO_ROOT
    / "pixelart_creator"
    / "userguide_content"
    / "content"
    / "es"
    / "app-basics.md"
)
_SITE_EN_DIR = _REPO_ROOT / "docs" / "site" / "pages" / "en"
_SITE_ES_DIR = _REPO_ROOT / "docs" / "site" / "pages" / "es"
_TS_ES = _REPO_ROOT / "pixelart_creator" / "i18n" / "pixelart_es.ts"

_ABOUT_ENTRY_EN = "Help ▸ About PixelArt Creator"
_ABOUT_SOURCE = "&About PixelArt Creator"  # plan.md section 3.2, verbatim tr() call


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_emphasis(text: str) -> str:
    """Drop markdown bold/italic markers so a substring search is not defeated
    by ``**Help ▸ About PixelArt Creator**`` vs the plain phrase."""
    return text.replace("**", "").replace("*", "")


def _main_window_context_name() -> str:
    """The ``.ts`` context name ``pyside6-lupdate`` derives for the main
    window: the name of the class in ``ui/main_window.py`` that subclasses
    ``QMainWindow``. Read via ``ast`` (Qt-free — no PySide6 import) instead
    of being typed here, so a class rename cannot silently desync this test
    from the product or the catalogue."""
    tree = ast.parse(_MAIN_WINDOW_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = base.attr if isinstance(base, ast.Attribute) else (
                base.id if isinstance(base, ast.Name) else None
            )
            if base_name == "QMainWindow":
                return node.name
    raise AssertionError(
        f"no QMainWindow subclass found in {_MAIN_WINDOW_SOURCE}"
    )


_MAIN_WINDOW_CONTEXT = _main_window_context_name()


def _spanish_about_entry_text() -> "str | None":
    """The finished Spanish translation of the main window's About action,
    with its mnemonic ``&`` stripped — or ``None`` if no such finished
    message exists yet in ``pixelart_es.ts``."""
    tree = ElementTree.parse(_TS_ES)
    root = tree.getroot()
    for context in root.findall("context"):
        name_el = context.find("name")
        if name_el is None or (name_el.text or "").strip() != _MAIN_WINDOW_CONTEXT:
            continue
        for message in context.findall("message"):
            source_el = message.find("source")
            if source_el is None:
                continue
            if (source_el.text or "").strip() != _ABOUT_SOURCE:
                continue
            translation_el = message.find("translation")
            if translation_el is None:
                return None
            if translation_el.get("type") == "unfinished":
                return None
            return (translation_el.text or "").strip().replace("&", "", 1)
    return None


# --------------------------------------------------------------------------- #
# in-app User Guide "App basics" page (REQ-AV-DATA-001)                       #
# --------------------------------------------------------------------------- #


def test_app_basics_en_names_the_about_entry_and_the_window_title():
    text = _strip_emphasis(_read(_GUIDE_EN))

    assert _ABOUT_ENTRY_EN in text, (
        f"expected {_ABOUT_ENTRY_EN!r} in {_GUIDE_EN}; absent at a77b5c0"
    )
    assert "window title" in text.lower(), (
        "expected the EN app-basics page to say the version also shows in "
        "the window title"
    )
    assert pixelart_creator.__version__ not in _read(_GUIDE_EN), (
        "CL-AV-11: no page may quote the current concrete version"
    )


def test_app_basics_es_names_the_about_entry_from_the_catalogue_and_the_window_title():
    spanish_entry = _spanish_about_entry_text()
    assert spanish_entry is not None, (
        f"expected a finished {_MAIN_WINDOW_CONTEXT} '&About PixelArt Creator' translation "
        f"in {_TS_ES} before the ES app-basics page can name it"
    )

    text = _strip_emphasis(_read(_GUIDE_ES))
    expected = f"Ayuda ▸ {spanish_entry}"
    assert expected in text, (
        f"expected {expected!r} in {_GUIDE_ES}, matching the catalogue's own "
        "rendering exactly (this suite reads the wording from pixelart_es.ts, "
        "never types it)"
    )
    lowered = text.lower()
    assert "título" in lowered and "ventana" in lowered, (
        "expected the ES app-basics page to say the version also shows in "
        "the window title ('título' de la ventana')"
    )
    assert pixelart_creator.__version__ not in _read(_GUIDE_ES), (
        "CL-AV-11: no page may quote the current concrete version"
    )


# --------------------------------------------------------------------------- #
# documentation site (REQ-AV-BUILD-002, content half; page chosen by the docs owner) #
# --------------------------------------------------------------------------- #


def _pages_mentioning(directory: Path, needle: str) -> "set[Path]":
    hits: "set[Path]" = set()
    if not directory.is_dir():
        return hits
    for md_path in sorted(directory.rglob("*.md")):
        if needle in _strip_emphasis(_read(md_path)):
            hits.add(md_path.relative_to(directory))
    return hits


def test_site_describes_the_about_entry_in_both_languages_on_the_same_page():
    en_hits = _pages_mentioning(_SITE_EN_DIR, "About PixelArt Creator")
    assert en_hits, (
        "expected at least one page under docs/site/pages/en to describe "
        "Help ▸ About PixelArt Creator; none does at a77b5c0"
    )

    spanish_entry = _spanish_about_entry_text()
    assert spanish_entry is not None, (
        f"expected a finished {_MAIN_WINDOW_CONTEXT} '&About PixelArt Creator' translation "
        f"in {_TS_ES} before the ES site page can be checked"
    )
    es_hits = _pages_mentioning(_SITE_ES_DIR, spanish_entry)
    assert es_hits, (
        "expected at least one page under docs/site/pages/es to describe the "
        "About entry using the catalogue's own Spanish rendering"
    )

    assert en_hits == es_hits, (
        "the same relative page(s) should describe the About entry in both "
        f"locales; en={sorted(str(p) for p in en_hits)} "
        f"es={sorted(str(p) for p in es_hits)}"
    )

    current_version = pixelart_creator.__version__
    for rel in en_hits:
        page_text = _strip_emphasis(_read(_SITE_EN_DIR / rel)).lower()
        # Token presence, not an exact phrase: the shipped wording reads
        # "window's title", not "window title", and both are equally valid
        # English for the same fact. The ES check below already applies
        # this same looser, order-agnostic style for the identical concept.
        assert "window" in page_text and "title" in page_text, (
            f"expected {_SITE_EN_DIR / rel} to mention the version in the "
            "window title too"
        )
        assert current_version not in _read(_SITE_EN_DIR / rel), (
            "CL-AV-11: no page may quote the current concrete version"
        )
    for rel in es_hits:
        page_text = _strip_emphasis(_read(_SITE_ES_DIR / rel)).lower()
        assert "título" in page_text and "ventana" in page_text, (
            f"expected {_SITE_ES_DIR / rel} to mention the version in the "
            "window title too"
        )
        assert current_version not in _read(_SITE_ES_DIR / rel), (
            "CL-AV-11: no page may quote the current concrete version"
        )
