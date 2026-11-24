"""Real glyphs for every translation and every guide page, in every font case.

``REQ-L10N-UI-009`` (every interface message renders with no missing-glyph box) and
``REQ-L10N-UI-010`` (every guide page renders with no missing-glyph box in the three
font cases). The scenarios proven here are SC-L10N-UI-009-1, SC-L10N-UI-009-2 and
SC-L10N-UI-010-1, for the six new languages and for English and Spanish with them.

What is measured, in a fresh interpreter per case:

* Every message of the language's catalogue source (each translation, each plural
  form, the source text where a language has no translation) is laid out with the
  font the interface really uses (``QApplication.font()`` after the product has
  applied it, in the Nifen Art mode and with "Use system font" on) and in its Bold
  copy. A missing glyph is glyph 0 in a glyph run. The characters examined are
  printed and must be non-zero.
* Every page of the guide is rendered by the real guide dialog in the language, in
  the three font cases of the requirement (the platform font by default, Nifen Art
  with the hidden switch on, and "Use system font"), and the text of every fragment
  of the document is laid out in the font the document resolves for it and read the
  same way. (The glyph runs of a document block's own layout report no missing glyph
  even for a font that cannot draw the character, so they are not read.)
* **Control.** The same text is laid out with a Latin-only platform stand-in, font
  merging off. That font cannot draw any non-ASCII character, so it must report
  missing glyphs wherever the text has one; if it does not, the probe is blind and
  the verdict means nothing. The guide cases run it twice: on the plain text, and on
  the guide's own fragments with that font as their base font. They also check,
  keyed by the character, that every Hangul syllable a page holds is drawn by a
  shipped family and not by a system font, and that every Han character a page
  holds is drawn by the face of the active language's form (Japanese: Nifen Art
  CJK JP; Simplified Chinese: Nifen Art CJK SC), or, in the other languages, by a
  shipped family.
* **The platform family is a registered stand-in**, Han-free or Han-capable, set as
  the platform's default font before the application captures it, so the verdict
  holds whatever the machine's own fonts are. On Linux each case also runs with a
  generated fontconfig that shows no system font at all (so no system CJK font can
  hide a gap in the bundled faces), and with the system fonts visible and the probe
  font asserted present first (the case fails, it never skips, when it is absent).

Run ``pytest -rP`` to read every count. Every print is ASCII.
"""

from __future__ import annotations

import json
import unicodedata
import xml.etree.ElementTree as ElementTree
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence, Tuple

import pytest
from PySide6.QtGui import QFont, QRawFont, QTextLayout

import pixelart_creator
from pixelart_creator.ui import app_font
from testing.suites.ui.test_l10n_font_fallback import (
    CJK_JP,
    CJK_KR,
    CJK_SC,
    IS_LINUX,
    LANGUAGES,
    NIFEN,
    OS_NAME,
    Booted,
    ascii_safe,
    boot,
    build_instrument_faces,
    draw_one,
    family_ok,
    is_han,
    make_font,
    probe_characters,
    probe_holders,
    run_case,
    start_language,
    system_families,
)

_MODULE = "testing.suites.ui.test_l10n_glyph_coverage"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_I18N_DIR = _REPO_ROOT / "pixelart_creator" / "i18n"
_GUIDE_DIR = _REPO_ROOT / "pixelart_creator" / "userguide_content" / "content"

#: Linux runs each case twice: with no system font visible, and with them visible.
ENVIRONMENTS = ("hidden", "system") if IS_LINUX else ("native",)

#: The three font cases of REQ-L10N-UI-010, each with a Han-free platform family, and
#: the two platform-font cases again with a Han-capable one.
GUIDE_CASES: Dict[str, Dict[str, Any]] = {
    "platform-free": {"system": False, "pixel": False, "platform": "free"},
    "platform-capable": {"system": False, "pixel": False, "platform": "capable"},
    "nifen-switch": {"system": False, "pixel": True, "platform": "free"},
    "system-free": {"system": True, "pixel": False, "platform": "free"},
    "system-capable": {"system": True, "pixel": False, "platform": "capable"},
}

_TEXT_WIDTH = 640

#: The character a text fragment holds for an inline image.
_OBJECT_REPLACEMENT = chr(0xFFFC)

#: The families the product ships: Nifen Art and its three CJK faces.
BUNDLED_FAMILIES = (NIFEN, CJK_SC, CJK_JP, CJK_KR)

#: The face that draws every Han character of a language's guide pages: the face of
#: the form that language shows. The other languages have no form face.
HAN_FORM_FAMILY: Dict[str, str] = {"ja": CJK_JP, "zh_CN": CJK_SC}

#: Hangul jamo, compatibility jamo and syllables.
_HANGUL_RANGES = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7A3))


@pytest.fixture(autouse=True)
def theme() -> str:
    """Replace the suite's two-way theme fixture: no case here depends on a theme.

    Which glyph a font draws cannot change with the style sheet, so running each
    case twice would only repeat every subprocess.
    """
    return "none"


@pytest.fixture(scope="session")
def instrument_faces(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    """The generated stand-in faces, built once per process."""
    folder = tmp_path_factory.mktemp("l10n-faces-coverage")
    return dict(build_instrument_faces(folder))


# --------------------------------------------------------------------------- #
# Child side                                                                   #
# --------------------------------------------------------------------------- #


def read_messages(path: Path) -> List[str]:
    """Return every text a catalogue source can show: translations, then sources.

    Each translation is a message; each plural form of a plural message is one; a
    message with no translation (the source language has none) shows its source text.
    Vanished and obsolete entries are not shown and are skipped.
    """
    root = ElementTree.fromstring(path.read_bytes())
    texts: List[str] = []
    for message in root.iter("message"):
        translation = message.find("translation")
        forms: List[str] = []
        if translation is not None:
            if translation.get("type") in ("vanished", "obsolete"):
                continue
            plural = translation.findall("numerusform")
            if plural:
                forms = [form.text or "" for form in plural]
            else:
                forms = [translation.text or ""]
        forms = [form for form in forms if form.strip()]
        if not forms:
            source = message.find("source")
            if source is not None and (source.text or "").strip():
                forms = [source.text or ""]
        texts.extend(forms)
    return texts


def tidy(text: str) -> str:
    """Replace line and control characters by spaces (a layout is one run of text)."""
    return "".join(
        " " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else ch for ch in text
    )


def zero_glyphs(layout: QTextLayout) -> int:
    """Count the missing-glyph boxes (glyph 0) in a laid-out text layout."""
    total = 0
    for run in layout.glyphRuns():
        total += [int(glyph) for glyph in run.glyphIndexes()].count(0)
    return total


def lay_out(font: QFont, text: str) -> QTextLayout:
    """Lay ``text`` out on lines as wide as it needs."""
    layout = QTextLayout(text, font)
    layout.beginLayout()
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(1000000)
    layout.endLayout()
    return layout


def measure(font: QFont, texts: Sequence[str]) -> Dict[str, Any]:
    """Lay every text out in ``font``; count what was examined and what is a box."""
    examined = 0
    boxes = 0
    seen: set[int] = set()
    offenders: set[int] = set()
    for text in texts:
        clean = tidy(text)
        examined += sum(1 for ch in clean if not ch.isspace())
        seen.update(ord(ch) for ch in clean if not ch.isspace())
        zeros = zero_glyphs(lay_out(font, clean))
        boxes += zeros
        if zeros:
            for cp in sorted({ord(ch) for ch in clean if not ch.isspace()}):
                if cp not in offenders and draw_one(font, cp)[1]:
                    offenders.add(cp)
    return {
        "texts": len(texts),
        "examined": examined,
        "distinct": len(seen),
        "notdef": boxes,
        "offenders": sorted(offenders)[:40],
        "offender_count": len(offenders),
        "non_ascii": sum(1 for cp in seen if cp > 127),
    }


def control_font(booted: Booted) -> QFont:
    """Return the Latin-only platform stand-in with font merging off (the control)."""
    font = make_font([booted.names["PL"]])
    font.setStyleStrategy(font.styleStrategy() | QFont.StyleStrategy.NoFontMerging)
    return font


def han_holders(booted: Booted) -> List[str]:
    """Return the system families that hold a Han character (none when hidden)."""
    holders: List[str] = []
    for family in system_families(booted):
        face = QFont(family)
        face.setPixelSize(app_font.NIFEN_ART_EM_PX)
        raw = QRawFont.fromFont(face)
        if raw.isValid() and raw.supportsCharacter(0x5B57):
            holders.append(family)
    return holders


def environment_facts(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Report what the operating system's fonts were, for the Linux checks."""
    probes = list(spec.get("probes", []))
    return {
        "system_han_holders": han_holders(booted),
        "system_family_count": len(system_families(booted)),
        "probe_holders": probe_holders(booted, probes) if probes else [],
    }


def run_coverage(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Lay every catalogue message out in the interface font, regular and Bold."""
    language = spec["language"]
    system = bool(spec["system"])
    start_language(booted, language)
    app_font.prepare_interface_font(booted.app, system)
    regular = QFont(booted.app.font())
    bold = QFont(booted.app.font())
    bold.setBold(True)
    path = Path(pixelart_creator.__file__).parent / "i18n" / f"pixelart_{language}.ts"
    texts = read_messages(path)
    out: Dict[str, Any] = {
        "ui": measure(regular, texts),
        "ui_bold": measure(bold, texts),
        "control_stats": measure(control_font(booted), texts),
        "chain": list(regular.families()),
    }
    booted.say(
        "%s: %d messages, %d characters examined (%d distinct), boxes %d (Bold %d); "
        "control boxes %d; chain %r"
        % (
            language,
            out["ui"]["texts"],
            out["ui"]["examined"],
            out["ui"]["distinct"],
            out["ui"]["notdef"],
            out["ui_bold"]["notdef"],
            out["control_stats"]["notdef"],
            out["chain"],
        )
    )
    out.update(environment_facts(booted, spec))
    return out


def unlaid_blocks(document: Any) -> int:
    """Count the text blocks of a document that holds text but has no laid-out line."""
    count = 0
    block = document.begin()
    while block.isValid():
        if block.text().strip() and block.layout().lineCount() == 0:
            count += 1
        block = block.next()
    return count


def resolved_fragments(document: Any, base: QFont) -> Iterator[Tuple[str, QFont]]:
    """Yield (text, font) for every text fragment of a document.

    The font is the fragment's own character format resolved against ``base``, as Qt
    resolves a fragment's font against the document's default font. A text layout of
    that text in that font is then read the way every other probe here reads one,
    because the glyph runs of a document block's own layout report no missing glyph
    even where the font cannot draw the character.
    """
    block = document.begin()
    while block.isValid():
        walker = block.begin()
        while not walker.atEnd():
            fragment = walker.fragment()
            text = fragment.text().replace(_OBJECT_REPLACEMENT, " ")
            if text.strip():
                yield text, fragment.charFormat().font().resolve(base)
            walker += 1
        block = block.next()


def is_hangul(code_point: int) -> bool:
    """Return whether ``code_point`` is a Hangul syllable or jamo."""
    return any(first <= code_point <= last for first, last in _HANGUL_RANGES)


def bundled(drawn: str) -> bool:
    """Return whether ``drawn`` names a family the product ships (either weight)."""
    return any(family_ok(drawn, family) for family in BUNDLED_FAMILIES)


def run_guide(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Render every guide page in the real dialog and read each fragment's font.

    Every text fragment of every page is laid out alone in the font the document
    resolves for it and its glyph runs are read. The same fragments are read again
    with the Latin-only font as the base font: that must report boxes. Every Hangul
    syllable and every Han character is also drawn alone in its fragment's font, and
    the family that drew it is recorded, keyed by the character.
    """
    from pixelart_creator.ui.user_guide import User_Guide_Dialog

    language = spec["language"]
    system = bool(spec["system"])
    start_language(booted, language)
    app_font.prepare_interface_font(booted.app, system)
    dialog: Any = User_Guide_Dialog(
        locale_provider=lambda: language,
        guide_pixel_font=bool(spec["pixel"]),
        use_system_font=system,
    )
    document = dialog._content_view.document()
    page_font = QFont(document.defaultFont())
    blind_font = control_font(booted)
    pages = 0
    examined = 0
    boxes = 0
    unlaid = 0
    blind_examined = 0
    blind_boxes = 0
    skipped_hangul = 0
    offenders: set[int] = set()
    plain: List[str] = []
    han_drawn: Dict[Tuple[Tuple[str, ...], int], str] = {}
    hangul_drawn: Dict[Tuple[Tuple[str, ...], int], str] = {}
    topics = list(dialog._model.topics())
    for topic in topics:
        dialog.show_topic(topic.id)
        document.setTextWidth(_TEXT_WIDTH)
        document.size()
        pages += 1
        plain.extend(document.toPlainText().splitlines())
        unlaid += unlaid_blocks(document)
        for text, font in resolved_fragments(document, page_font):
            clean = tidy(text)
            characters = {ord(ch) for ch in clean if not ch.isspace()}
            examined += sum(1 for ch in clean if not ch.isspace())
            zeros = zero_glyphs(lay_out(font, clean))
            boxes += zeros
            if zeros:
                for cp in sorted(characters):
                    if draw_one(font, cp)[1]:
                        offenders.add(cp)
            chain = tuple(font.families())
            for cp in sorted(characters):
                if is_han(cp):
                    han_drawn.setdefault((chain, cp), draw_one(font, cp)[0])
                elif is_hangul(cp):
                    if font.family() == page_font.family():
                        hangul_drawn.setdefault((chain, cp), draw_one(font, cp)[0])
                    else:
                        skipped_hangul += 1
        for text, font in resolved_fragments(document, blind_font):
            clean = tidy(text)
            blind_examined += sum(1 for ch in clean if not ch.isspace())
            blind_boxes += zero_glyphs(lay_out(font, clean))
    control = measure(blind_font, plain)
    hangul_families = sorted(Counter(hangul_drawn.values()).items())
    han_families = sorted(Counter(han_drawn.values()).items())
    hangul_foreign = [
        [cp, family]
        for (_chain, cp), family in hangul_drawn.items()
        if not bundled(family)
    ]
    form_family = HAN_FORM_FAMILY.get(language)
    han_off_form = [
        [cp, family]
        for (_chain, cp), family in han_drawn.items()
        if form_family is not None and not family_ok(family, form_family)
    ]
    han_foreign = [
        [cp, family]
        for (_chain, cp), family in han_drawn.items()
        if not bundled(family)
    ]
    booted.say(
        "%s: %d pages, %d characters examined, boxes %d, blocks not laid out %d; "
        "control boxes %d; fragment control boxes %d of %d characters; page font "
        "chain %r; Hangul syllables %d drawn by %r, not by a shipped family %d, in a "
        "fragment font of another family %d; Han characters %d drawn by %r; Han form "
        "face %r, not drawn by it %d, not by a shipped family %d"
        % (
            language,
            pages,
            examined,
            boxes,
            unlaid,
            control["notdef"],
            blind_boxes,
            blind_examined,
            list(page_font.families()),
            len(hangul_drawn),
            hangul_families,
            len(hangul_foreign),
            skipped_hangul,
            len(han_drawn),
            han_families,
            form_family,
            len(han_off_form),
            len(han_foreign),
        )
    )
    out: Dict[str, Any] = {
        "pages": pages,
        "examined": examined,
        "notdef": boxes,
        "unlaid": unlaid,
        "offenders": sorted(offenders)[:40],
        "control_stats": control,
        "document_control": {"examined": blind_examined, "notdef": blind_boxes},
        "hangul": len(hangul_drawn),
        "hangul_families": hangul_families,
        "hangul_foreign": hangul_foreign[:40],
        "hangul_foreign_count": len(hangul_foreign),
        "han": len(han_drawn),
        "han_families": han_families,
        "han_form_family": form_family,
        "han_off_form": han_off_form[:40],
        "han_off_form_count": len(han_off_form),
        "han_foreign": han_foreign[:40],
        "han_foreign_count": len(han_foreign),
        "chain": list(page_font.families()),
    }
    out.update(environment_facts(booted, spec))
    dialog.close()
    return out


RUNNERS = {"coverage": run_coverage, "guide": run_guide}


def child_main(spec: Dict[str, Any]) -> None:
    """Entry of a child interpreter: run the case and print one RESULT line."""
    booted = boot(spec)
    result = RUNNERS[spec["kind"]](booted, spec)
    payload = dict(booted.base())
    payload.update(result)
    print("RESULT " + json.dumps(payload), flush=True)


# --------------------------------------------------------------------------- #
# Parent side                                                                  #
# --------------------------------------------------------------------------- #


def check_environment(name: str, environment: str, result: Dict[str, Any]) -> None:
    """Assert the Linux preconditions of an environment (nothing on other systems)."""
    if environment == "hidden":
        assert not result["system_han_holders"], (
            f"{name}: the generated fontconfig did not hide every system CJK font: "
            f"{ascii_safe(result['system_han_holders'])}"
        )
        print(f"[{name}] system fonts visible: {result['system_family_count']}")
    if environment == "system":
        assert result["probe_holders"], (
            f"{name}: no installed font covers every probe character, so the "
            "fallback path cannot be exercised on this runner: a failure, never a skip"
        )
        print(f"[{name}] probe font present: {ascii_safe(result['probe_holders'])}")


def case_args(environment: str) -> Dict[str, Any]:
    """Return the extra spec an environment needs (the probe characters on Linux)."""
    return {"probes": probe_characters()} if environment == "system" else {}


def check_coverage(name: str, result: Dict[str, Any]) -> None:
    """Assert 0 missing glyphs, characters examined, and a control that sees boxes."""
    regular, bold, control = result["ui"], result["ui_bold"], result["control_stats"]
    print(
        f"[{name}] {regular['texts']} messages; {regular['examined']} characters "
        f"examined ({regular['distinct']} distinct); missing glyphs "
        f"{regular['notdef']} (Bold {bold['notdef']}); control with a Latin-only "
        f"font {control['notdef']}; chain {ascii_safe(result['chain'])}"
    )
    assert regular["texts"] > 0 and regular["examined"] > 0
    assert regular["notdef"] == 0, (
        f"{name}: {regular['notdef']} missing glyphs; code points "
        f"{ascii_safe([hex(cp) for cp in regular['offenders']])}"
    )
    assert bold["notdef"] == 0, (
        f"{name}: {bold['notdef']} missing glyphs in Bold; code points "
        f"{ascii_safe([hex(cp) for cp in bold['offenders']])}"
    )
    if control["non_ascii"] > 0:
        assert control["notdef"] > 0, (
            f"{name}: the probe is blind: a Latin-only font with merging off drew "
            f"{control['non_ascii']} distinct non-ASCII characters with no box"
        )


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("language", LANGUAGES)
def test_sc_l10n_ui_009_1_catalogue_text_has_no_missing_glyph(
    tmp_path, instrument_faces, language, environment
):
    """SC-L10N-UI-009-1: every catalogue message, 0 missing glyphs, characters printed.

    The default font mode (Nifen Art), on the operating system the suite runs on.
    """
    name = f"009-1 {language} {environment}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "coverage",
        module=_MODULE,
        environment=environment,
        language=language,
        system=False,
        platform="free",
        **case_args(environment),
    )
    check_environment(name, environment, result)
    check_coverage(name, result)


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("platform", ["free", "capable"])
def test_sc_l10n_ui_009_2_use_system_font_does_not_bring_back_missing_glyphs(
    tmp_path, instrument_faces, platform, language, environment
):
    """SC-L10N-UI-009-2: "Use system font" on, every message, 0 missing glyphs.

    The platform family is a registered stand-in that holds no Han or Hangul
    character (as on a Linux machine without CJK fonts), and again one that holds all
    of them (as on a CJK machine). The characters must render either way.
    """
    name = f"009-2 {platform} {language} {environment}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "coverage",
        module=_MODULE,
        environment=environment,
        language=language,
        system=True,
        platform=platform,
        **case_args(environment),
    )
    check_environment(name, environment, result)
    check_coverage(name, result)


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("case", list(GUIDE_CASES))
def test_sc_l10n_ui_010_1_guide_pages_have_no_missing_glyph_in_any_font_case(
    tmp_path, instrument_faces, case, language, environment
):
    """SC-L10N-UI-010-1: every guide page, in each font case, 0 missing glyphs.

    The page text in the platform font (the default), in Nifen Art (the hidden switch
    on), and in the platform font with "Use system font" on; the platform font cases
    with a Han-free and with a Han-capable platform family. Every page is rendered by
    the real guide dialog in the language; the text of each fragment of its document
    is read in the font the document resolves for it.

    Two controls and two identity checks keep the probe honest. The same text with a
    Latin-only font as the plain text's font must report boxes, and so must the
    guide's own fragments with that font as their base font. Every Hangul syllable
    a page holds must be drawn by a family the product ships, keyed by the
    character: a missing face can be hidden behind a system font that draws the
    syllable, which no box count would see. And with Japanese active every Han
    character a page holds is drawn by Nifen Art CJK JP, with Simplified Chinese
    active by Nifen Art CJK SC (the count is printed and above 0), so the other
    form's face, or a platform font, cannot supply a page's drawing. In every other
    language each Han character must come from a shipped family.
    """
    name = f"010-1 {case} {language} {environment}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "guide",
        module=_MODULE,
        environment=environment,
        language=language,
        **GUIDE_CASES[case],
        **case_args(environment),
    )
    check_environment(name, environment, result)
    control = result["control_stats"]
    document_control = result["document_control"]
    print(
        f"[{name}] {result['pages']} pages; {result['examined']} characters examined; "
        f"missing glyphs {result['notdef']}; blocks not laid out {result['unlaid']}; "
        f"control with a Latin-only font {control['notdef']}; the same control on the "
        f"guide fragments {document_control['notdef']} boxes in "
        f"{document_control['examined']} characters; page font chain "
        f"{ascii_safe(result['chain'])}; Hangul syllables {result['hangul']} drawn by "
        f"{ascii_safe(result['hangul_families'])}; Han characters {result['han']} "
        f"drawn by {ascii_safe(result['han_families'])}; Han form face "
        f"{ascii_safe(result['han_form_family'])}, not drawn by it "
        f"{result['han_off_form_count']}, not by a shipped family "
        f"{result['han_foreign_count']}"
    )
    assert result["pages"] > 0 and result["examined"] > 0
    assert result["unlaid"] == 0, "a text block was never laid out, so never examined"
    assert result["notdef"] == 0, (
        f"{name}: {result['notdef']} missing glyphs; code points "
        f"{ascii_safe([hex(cp) for cp in result['offenders']])}"
    )
    if control["non_ascii"] > 0:
        assert control["notdef"] > 0, (
            f"{name}: the probe is blind: a Latin-only font with merging off drew "
            f"{control['non_ascii']} distinct non-ASCII characters with no box"
        )
        assert document_control["notdef"] > 0, (
            f"{name}: the fragment reading is blind: the same pages with a Latin-only "
            f"base font, merging off, drew "
            f"{document_control['examined']} characters ({control['non_ascii']} "
            "distinct non-ASCII ones in the plain text) with no box"
        )
    if language == "ko":
        assert result["hangul"] > 0, f"{name}: the Korean pages hold no Hangul"
    assert result["hangul_foreign_count"] == 0, (
        f"{name}: {result['hangul_foreign_count']} Hangul syllables on the pages are "
        "drawn by a family the product does not ship, so a missing glyph is hidden by "
        "a fallback font; first "
        f"{ascii_safe([[hex(cp), fam] for cp, fam in result['hangul_foreign'][:5]])}; "
        f"page font chain {ascii_safe(result['chain'])}"
    )
    form_family = result["han_form_family"]
    if form_family is not None:
        assert result["han"] > 0, (
            f"{name}: the pages hold no Han character, so the form check examined "
            "nothing"
        )
        assert result["han_off_form_count"] == 0, (
            f"{name}: {result['han_off_form_count']} of {result['han']} Han "
            f"characters on the pages are not drawn by {form_family!r}, the face of "
            "the form this language shows; first "
            f"{ascii_safe([[hex(cp), fam] for cp, fam in result['han_off_form'][:5]])}"
            f"; page font chain {ascii_safe(result['chain'])}"
        )
    assert result["han_foreign_count"] == 0, (
        f"{name}: {result['han_foreign_count']} Han characters on the pages are drawn "
        "by a family the product does not ship, so a fallback font draws them; first "
        f"{ascii_safe([[hex(cp), fam] for cp, fam in result['han_foreign'][:5]])}; "
        f"page font chain {ascii_safe(result['chain'])}"
    )


def test_the_catalogue_sources_and_the_guide_trees_exist_for_every_language():
    """The population: eight catalogue sources and eight guide trees, none empty."""
    sources = {p.stem[len("pixelart_") :]: p for p in _I18N_DIR.glob("*.ts")}
    trees = {p.name: p for p in _GUIDE_DIR.iterdir() if p.is_dir()}
    rows = []
    for language in LANGUAGES:
        messages = len(read_messages(sources[language]))
        pages = len(list(trees[language].glob("*.md")))
        rows.append(f"{language} {messages} messages/{pages} pages")
        assert messages > 0 and pages > 0, (language, messages, pages)
    print(f"[population] {OS_NAME}: " + "; ".join(rows))
    assert set(trees) >= set(LANGUAGES), sorted(set(LANGUAGES) - set(trees))
