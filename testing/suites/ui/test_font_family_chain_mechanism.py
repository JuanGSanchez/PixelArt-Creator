"""The per-character font family list: how Qt resolves it, and the precedence rule.

``REQ-L10N-UI-012`` needs Han and Hangul text to be drawn by the application's
own CJK faces on every machine, including one whose UI font holds those
characters. Whether a family list can deliver that depends on facts about
``QFont.setFamilies`` that no document settles, so this module measures them
instead of assuming them:

* the family that holds a character FIRST in list order draws it;
* the list's line metrics are the FIRST family's;
* a listed family's process-wide substitutes are tried only AFTER the whole list;
* the order that lets a Han-capable platform family draw Han (the *platform-first
  order*) breaks the rule, and the order that puts the CJK family first (the
  *CJK-first order*) keeps it. The platform-first case is a control: the probe
  must SEE that defect, or the probe is blind and the verdict means nothing;
* two fonts that share a first family, size and weight share one tail in a
  process (measured; see ``test_two_fonts_that_differ_only_in_their_tail...``).

How the cases are built (and why):

* **One subprocess per case, and one family list per subprocess.** A font
  database, a substitution table and Qt's font cache are process-wide. Qt's
  cache does not include the families AFTER the first in its key (measured), so a
  second list with the same first family, size and weight is drawn from the first
  list's tail. A case that measured two such lists in one process would be
  reading its own leftovers. The family that draws a character is read from the
  glyph runs of a ``QTextLayout``, ``rawFont().familyName()``, never inferred
  from a font object's own ``family()``.
* **Every family a verdict depends on is registered by the case itself.** The
  offscreen platform on Windows sees only application-registered fonts and has
  no operating-system fallback (measured), so a verdict on a system font would
  be blind there. The cases register Nifen Art exactly as the application does
  (``register_app_fonts``), and synthetic faces generated here with fontTools
  under ``tmp_path`` and never committed: a Han-and-Hangul-only face in two
  variants (the OS/2 CJK range bits set, and cleared), a stand-in for a
  Han-capable platform UI font (Latin, Han and Hangul, with a taller line box
  than Nifen Art's, so a clipped line is detectable), and a Latin-only face.
  Every glyph is a plain box: no glyph is taken from any font.
* **A positive control runs first in every subprocess**: a character the first
  family lacks must be drawn by the next registered family. If it is not, the case
  fails and names the plugin; it never passes blind.
* **The application's own substitutions are installed first**
  (``install_font_substitutions``), as the application does.
* A real system font's file, registered by path, is added as an extra case per
  operating system. It is never the only case.
* Coverage questions pass an integer code point (``QRawFont.supportsCharacter``
  and ``QFontMetrics.inFontUcs4``); the one-character ``str`` form answers wrongly
  on Linux.
* The operating-system fallback past the end of the list (``REQ-L10N-UI-011``) is
  asserted on Linux only, where the offscreen platform reaches fontconfig. On
  Windows and macOS the case prints that it is not observable offscreen and is
  proven on Linux; it does not pass the clause.

Everything measured is printed (run ``pytest -rP``), so a result on another
operating system can be read, not only counted.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

_REPO_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------------------------------- #
# Probe characters. Integer code points throughout.                            #
# --------------------------------------------------------------------------- #

LATIN_A = 0x41
LATIN_B = 0x42
N_TILDE = 0xF1  # held by Nifen Art, lacked by the Latin-only face: the control
HAN_PROBE = 0x5B57  # 字
HAN_SECOND = 0x65E5  # 日
HANGUL_PROBE = 0xD55C  # 한
HANGUL_SECOND = 0xAE00  # 글
HIRAGANA = 0x3042  # あ
KATAKANA = 0x30AB  # カ

PROBES: Tuple[int, ...] = (
    LATIN_A,
    HAN_PROBE,
    HAN_SECOND,
    HANGUL_PROBE,
    HANGUL_SECOND,
    HIRAGANA,
    KATAKANA,
)
CJK_PROBES: Tuple[int, ...] = (HAN_PROBE, HAN_SECOND, HANGUL_PROBE, HANGUL_SECOND)

# --------------------------------------------------------------------------- #
# The synthetic faces.                                                         #
# --------------------------------------------------------------------------- #

#: Nifen Art's grid: 1536 units to the em, 12 px, so 128 units to the pixel.
_UPEM = 1536
_PX = 128
_ADVANCE = 12 * _PX
_BOX = (0, -_PX, 11 * _PX, 10 * _PX)  # ink columns 0..10, rows -1..9

#: OS/2 Unicode-range bits: Basic Latin, Hangul Jamo, CJK Symbols and
#: Punctuation, Hangul Syllables, CJK Unified Ideographs.
_BITS_LATIN = (0,)
_BITS_CJK = (28, 48, 56, 59)
#: OS/2 code-page-range bits: Latin 1, then the five East-Asian code pages.
_CODEPAGE_LATIN = (0,)
_CODEPAGE_CJK = (17, 18, 19, 20, 21)


@dataclass(frozen=True)
class Face:
    """One synthetic face: what it holds and how tall its line box is."""

    family: str
    codepoints: Tuple[int, ...]
    ascent_px: int
    descent_px: int
    unicode_bits: Tuple[int, ...]
    codepage_bits: Tuple[int, ...]


FACES: Dict[str, Face] = {
    # Han and Hangul only, the line box of Nifen Art (11 / 3 px at 12 px).
    "Fset": Face(
        "Probe Han Hangul Bits",
        CJK_PROBES,
        11,
        3,
        _BITS_CJK,
        _CODEPAGE_CJK,
    ),
    "Fclear": Face("Probe Han Hangul Bare", CJK_PROBES, 11, 3, (), ()),
    # A Han-capable platform UI font: Latin, Han and Hangul, taller than Nifen Art.
    "P": Face(
        "Probe Platform Han",
        (LATIN_A, LATIN_B, N_TILDE) + CJK_PROBES,
        13,
        3,
        _BITS_LATIN + _BITS_CJK,
        _CODEPAGE_LATIN + _CODEPAGE_CJK,
    ),
    # Latin only, and without the n-tilde: the first family of the control.
    "L": Face(
        "Probe Latin Only", (LATIN_A, LATIN_B), 12, 3, _BITS_LATIN, _CODEPAGE_LATIN
    ),
}


def _glyph_name(codepoint: int) -> str:
    return f"uni{codepoint:04X}"


def _box_glyph() -> Any:
    """Return a one-contour rectangular glyph on the Nifen Art grid."""
    x0, y0, x1, y1 = _BOX
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    return pen.glyph()


def _range_words(bits: Sequence[int], words: int) -> List[int]:
    """Spread OS/2 range bit numbers over ``words`` 32-bit fields."""
    fields = [0] * words
    for bit in bits:
        fields[bit // 32] |= 1 << (bit % 32)
    return fields


def build_face(face: Face, path: Path) -> Path:
    """Write ``face`` as a TrueType file at ``path`` and return the path.

    Every glyph is a plain box on the Nifen Art grid; the file holds no outline
    taken from any font. The OS/2 range bits are exactly ``face``'s: an empty
    tuple clears them.
    """
    order = [".notdef"] + [_glyph_name(cp) for cp in face.codepoints]
    glyphs = {name: _box_glyph() for name in order}
    builder = FontBuilder(_UPEM, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({cp: _glyph_name(cp) for cp in face.codepoints})
    builder.setupGlyf(glyphs)
    table = builder.font["glyf"]
    metrics = {name: (_ADVANCE, table[name].xMin) for name in order}
    builder.setupHorizontalMetrics(metrics)
    ascent = face.ascent_px * _PX
    descent = face.descent_px * _PX
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    builder.setupNameTable({"familyName": face.family, "styleName": "Regular"})
    builder.setupOS2(
        version=4,
        sTypoAscender=ascent,
        sTypoDescender=-descent,
        sTypoLineGap=0,
        usWinAscent=ascent,
        usWinDescent=descent,
        fsSelection=0xC0,
        usWeightClass=400,
    )
    os2 = builder.font["OS/2"]
    (
        os2.ulUnicodeRange1,
        os2.ulUnicodeRange2,
        os2.ulUnicodeRange3,
        os2.ulUnicodeRange4,
    ) = _range_words(face.unicode_bits, 4)
    os2.ulCodePageRange1, os2.ulCodePageRange2 = _range_words(face.codepage_bits, 2)
    builder.setupPost()
    builder.save(str(path))
    return path


def _build_faces(tmp_path: Path, tokens: Sequence[str]) -> Dict[str, Tuple[str, str]]:
    """Generate the named faces under ``tmp_path``; return token -> (path, family)."""
    out: Dict[str, Tuple[str, str]] = {}
    for token in tokens:
        face = FACES[token]
        path = build_face(face, tmp_path / f"{token}.ttf")
        out[token] = (str(path), face.family)
    return out


# --------------------------------------------------------------------------- #
# The child process: one case per interpreter.                                 #
# --------------------------------------------------------------------------- #

#: Runs in a fresh interpreter. It reads one JSON spec from ``argv[1]``,
#: registers the families the case judges, runs the positive control, measures,
#: and prints one ``RESULT`` JSON line. It asserts nothing: the parent does.
_CHILD = r"""
import json
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion
from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QFontInfo,
    QFontMetrics,
    QGuiApplication,
    QRawFont,
    QTextLayout,
)
from PySide6.QtWidgets import QApplication

spec = json.loads(sys.argv[1])
app = QApplication([])
from pixelart_creator.ui import app_font

LINES = []


def say(text):
    LINES.append(str(text))


def cp_name(cp):
    return "U+%04X" % cp


def register(path):
    font_id = QFontDatabase.addApplicationFont(path)
    families = []
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
    return font_id, families


# The application's own start-up order: Nifen Art registered as the product
# registers it, the platform font captured, then the substitutions installed.
nifen_registered = bool(app_font.register_app_fonts())
app_font.capture_platform_font()
app_font.install_font_substitutions()

NAMES = {"N": app_font.NIFEN_ART_FAMILY}
errors = []
for token, entry in spec["faces"].items():
    path, expected = entry
    font_id, families = register(path)
    if expected not in families:
        errors.append("%s: wanted %r, Qt registered %r" % (token, expected, families))
    NAMES[token] = expected

extra_families = []
for path in spec.get("register_paths", []):
    font_id, families = register(path)
    say("registered %s: id %s, families %r" % (path, font_id, families))
    for family in families:
        if family not in extra_families:
            extra_families.append(family)

if spec.get("substitute"):
    QFont.insertSubstitutions(
        app_font.NIFEN_ART_FAMILY, [NAMES[t] for t in spec["substitute"]]
    )
    say("insertSubstitutions: %r" % ([NAMES[t] for t in spec["substitute"]],))


def resolve(token):
    if token in NAMES:
        return NAMES[token]
    if token == "@platform":
        return app_font.platform_default_font().family()
    if token.startswith("="):
        return token[1:]
    raise KeyError(token)


def make_font(chain, px=12):
    font = QFont(chain[0])
    font.setFamilies(list(chain))
    font.setPixelSize(px)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def one(chain, cp, px=12):
    layout = QTextLayout(chr(cp), make_font(chain, px))
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(100000)
    layout.endLayout()
    runs = layout.glyphRuns()
    if not runs:
        return {"family": "", "notdef": True, "holds": False}
    raw = runs[0].rawFont()
    glyphs = [int(g) for g in runs[0].glyphIndexes()]
    return {
        "family": raw.familyName(),
        "notdef": 0 in glyphs,
        "holds": bool(raw.supportsCharacter(cp)),
    }


def metrics_of(chain, px=12):
    fm = QFontMetrics(make_font(chain, px))
    return [fm.ascent(), fm.descent(), fm.height()]


def probe(label, chain, px=12):
    drawn = {str(cp): one(chain, cp, px) for cp in spec["probes"]}
    parts = []
    for cp in spec["probes"]:
        r = drawn[str(cp)]
        flag = " (missing glyph)" if r["notdef"] else ""
        parts.append("%s=%s%s" % (cp_name(cp), r["family"] or "-", flag))
    say("chain %s %r at %s px -> %s" % (label, chain, px, "; ".join(parts)))
    entry = {"chain": chain, "px": px, "drawn": drawn}
    if spec.get("metrics"):
        entry["metrics"] = metrics_of(chain, px)
        say("metrics %s: ascent/descent/height %s" % (label, entry["metrics"]))
    return entry


def resolved_note(entry):
    if entry["matches"]:
        return ""
    return " [resolved to %r]" % entry["resolved"]


def holds(name, cp):
    font = QFont(name)
    font.setPixelSize(12)
    font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
    resolved = QFontInfo(font).family()
    raw = QRawFont.fromFont(font)
    return {
        "resolved": resolved,
        "matches": resolved == name,
        "inFontUcs4": bool(QFontMetrics(font).inFontUcs4(cp)),
        "supportsCharacter": bool(raw.supportsCharacter(cp)),
    }


def describe_holds(name, table):
    return "detect %r: %s" % (
        name,
        "; ".join(
            "%s inFontUcs4=%s supportsCharacter=%s%s"
            % (
                cp_name(int(key)),
                row["inFontUcs4"],
                row["supportsCharacter"],
                resolved_note(row),
            )
            for key, row in table.items()
        ),
    )


say(
    "plugin %s; PySide6 %s; Qt %s; Python %s"
    % (
        QGuiApplication.platformName(),
        pyside_version,
        qVersion(),
        sys.version.split()[0],
    )
)

# The positive control comes before any verdict.
ctl = spec["control"]
ctl_chain = [resolve(t) for t in ctl["chain"]]
ctl_drew = one(ctl_chain, ctl["cp"])
control = {
    "ok": ctl_drew["family"] == resolve(ctl["expect"]),
    "drew": ctl_drew["family"],
    "expected": resolve(ctl["expect"]),
    "chain": ctl_chain,
    "cp": ctl["cp"],
}
say(
    "positive control: %s drawn by %r (expected %r) -> %s"
    % (
        cp_name(ctl["cp"]),
        control["drew"],
        control["expected"],
        "ok" if control["ok"] else "FAILED",
    )
)

result = {
    "plugin": QGuiApplication.platformName(),
    "nifen_registered": nifen_registered,
    "registration_errors": errors,
    "names": NAMES,
    "control": control,
    "chains": {},
    "detect": {},
}

for label, tokens in spec.get("chains", {}).items():
    px = spec.get("sizes", {}).get(label, 12)
    result["chains"][label] = probe(label, [resolve(t) for t in tokens], px)

for token in spec.get("detect", []):
    name = resolve(token)
    table = {str(cp): holds(name, cp) for cp in spec["detect_probes"]}
    result["detect"][token] = {"family": name, "table": table}
    say(describe_holds(name, table))

if spec.get("discover"):
    han_capable = []
    detect_real = {}
    for family in extra_families:
        first = holds(family, 0x5B57)
        if first["matches"] and first["supportsCharacter"]:
            han_capable.append(family)
            table = {str(cp): holds(family, cp) for cp in spec["detect_probes"]}
            detect_real[family] = table
            say(describe_holds(family, table))
    say("Han-capable families found: %r" % (han_capable,))
    result["registered"] = extra_families
    result["han_capable"] = han_capable
    result["detect_real"] = detect_real

result["info"] = LINES
print("RESULT " + json.dumps(result), flush=True)
"""

_DEFAULT_CONTROL: Dict[str, Any] = {"chain": ["L", "N"], "expect": "N", "cp": N_TILDE}

_OS_NAME = (
    "Windows"
    if sys.platform == "win32"
    else "macOS" if sys.platform == "darwin" else "Linux"
)


@pytest.fixture(autouse=True)
def theme() -> str:
    """Replace the suite's two-way theme fixture: no case here depends on a theme.

    The cases judge which font family draws a character in a child process, and
    a theme cannot change that, so running each twice would only repeat every
    subprocess.
    """
    return "none"


def _run_case(
    name: str,
    tmp_path: Path,
    faces: Sequence[str],
    *,
    control: Optional[Dict[str, Any]] = None,
    expect_control: bool = True,
    shared_process: bool = False,
    **spec: Any,
) -> Dict[str, Any]:
    """Run one case in a fresh interpreter and return its measurements.

    Prints every line the child measured. Unless ``expect_control`` is False, the
    positive control is asserted FIRST, so no verdict is read from a plugin that
    cannot tell families apart. A case measures ONE family list per process;
    ``shared_process`` is for the single case whose subject is two lists sharing
    one.
    """
    chains = spec.get("chains", {})
    assert shared_process or len(chains) <= 1, (
        f"{name}: {len(chains)} family lists in one process; Qt's font cache would "
        "let the first one answer for the others"
    )
    profile = tmp_path / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    spec = dict(spec)
    spec["faces"] = _build_faces(tmp_path, ["L", *[f for f in faces if f != "L"]])
    spec["control"] = control if control is not None else _DEFAULT_CONTROL
    spec.setdefault("probes", list(PROBES))
    spec.setdefault("detect_probes", [LATIN_A, HAN_PROBE, HANGUL_PROBE])
    env = dict(os.environ)
    env.update(
        PYTHONPATH=os.pathsep.join(
            [str(_REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        ),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
    )
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    done = subprocess.run(
        [sys.executable, "-B", "-c", _CHILD, json.dumps(spec)],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert (
        done.returncode == 0
    ), f"{name}: the child exited {done.returncode}\n{done.stdout}\n{done.stderr}"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert (
        lines
    ), f"{name}: the child printed no RESULT line\n{done.stdout}\n{done.stderr}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    for line in result["info"]:
        print(f"[{name}] [{_OS_NAME}] {line}")
    assert result["nifen_registered"], f"{name}: Nifen Art did not register"
    assert not result["registration_errors"], (
        f"{name}: a synthetic face was not registered under its own family name: "
        f"{result['registration_errors']}"
    )
    if expect_control:
        ctl = result["control"]
        assert ctl["ok"], (
            f"{name}: the positive control FAILED on the {result['plugin']!r} plugin "
            f"({_OS_NAME}): U+{ctl['cp']:04X} in {ctl['chain']} was drawn by "
            f"{ctl['drew']!r}, not by the next registered family {ctl['expected']!r}. "
            "This plugin cannot tell registered families apart, so no verdict below "
            "can be read from it."
        )
    return result


def _require(condition: bool, message: str) -> None:
    """Fail with ``message`` unless ``condition`` holds."""
    assert condition, message


def _who(result: Dict[str, Any], chain: str, codepoint: int) -> str:
    """Return the family that drew ``codepoint`` in the named chain."""
    return str(result["chains"][chain]["drawn"][str(codepoint)]["family"])


def _is_from(drawn: str, families: Sequence[str]) -> bool:
    """Return whether ``drawn`` names one of ``families`` (or a style of it)."""
    return any(
        drawn == f or drawn.startswith(f) or f.startswith(drawn)
        for f in families
        if drawn
    )


# --------------------------------------------------------------------------- #
# The instrument checks, in the parent.                                        #
# --------------------------------------------------------------------------- #


def test_the_generated_faces_hold_what_they_claim_and_no_borrowed_outline(tmp_path):
    """The synthetic faces are what the cases assume: contents, boxes, range bits."""
    built = _build_faces(tmp_path, list(FACES))
    for token, (path, family) in built.items():
        face = FACES[token]
        font = TTFont(path)
        cmap = font.getBestCmap()
        assert sorted(cmap) == sorted(face.codepoints), (token, sorted(cmap))
        names = {rec.toUnicode() for rec in font["name"].names if rec.nameID == 1}
        assert names == {family}, (token, names)
        glyf = font["glyf"]
        for glyph_name in font.getGlyphOrder():
            glyph = glyf[glyph_name]
            coords, ends, _flags = glyph.getCoordinates(glyf)
            assert (
                len(ends) == 1 and len(coords) == 4
            ), f"{token}:{glyph_name} is not a one-contour box: {len(coords)} points"
        assert (
            font["hhea"].ascent == face.ascent_px * _PX
            and -font["hhea"].descent == face.descent_px * _PX
        ), token
    set_bits = TTFont(built["Fset"][0])["OS/2"]
    clear_bits = TTFont(built["Fclear"][0])["OS/2"]
    # The control of the two variants: they differ in exactly the CJK bits.
    han_word, han_bit = divmod(59, 32)
    assert getattr(set_bits, f"ulUnicodeRange{han_word + 1}") & (1 << han_bit)
    assert not getattr(clear_bits, f"ulUnicodeRange{han_word + 1}") & (1 << han_bit)
    hangul_word, hangul_bit = divmod(56, 32)
    assert getattr(set_bits, f"ulUnicodeRange{hangul_word + 1}") & (1 << hangul_bit)
    assert not getattr(clear_bits, f"ulUnicodeRange{hangul_word + 1}") & (
        1 << hangul_bit
    )
    assert set_bits.ulCodePageRange1 & (1 << 18) and not clear_bits.ulCodePageRange1
    assert (
        clear_bits.ulUnicodeRange1,
        clear_bits.ulUnicodeRange2,
        clear_bits.ulUnicodeRange3,
        clear_bits.ulUnicodeRange4,
    ) == (0, 0, 0, 0)
    print(
        f"[faces] {len(built)} faces generated; Fset ulUnicodeRange2="
        f"{set_bits.ulUnicodeRange2:#010x}, Fclear ulUnicodeRange2="
        f"{clear_bits.ulUnicodeRange2:#010x}"
    )


def test_the_positive_control_fails_when_the_next_family_cannot_be_seen(tmp_path):
    """Control of the control: naming an unregistered next family must FAIL it.

    If this passed vacuously, the positive control of every other case would be
    unable to tell a working plugin from a blind one.
    """
    result = _run_case(
        "control-can-fail",
        tmp_path,
        [],
        control={
            "chain": ["L", "=Probe Never Registered"],
            "expect": "=Probe Never Registered",
            "cp": N_TILDE,
        },
        expect_control=False,
    )
    assert result["control"]["ok"] is False, (
        "a family that was never registered was reported as the one that drew the "
        f"character: {result['control']}"
    )


# --------------------------------------------------------------------------- #
# First holder wins.                                                           #
# --------------------------------------------------------------------------- #


def test_first_holder_wins_han_and_hangul_from_the_face_and_latin_from_nifen(
    tmp_path,
):
    """[Nifen Art, face]: Han and Hangul from the face, Latin from Nifen Art.

    Kana are printed only: which family draws them is information, not a verdict.
    """
    result = _run_case(
        "first-holder",
        tmp_path,
        ["Fset"],
        chains={"nifen-then-face": ["N", "Fset"]},
    )
    face = result["names"]["Fset"]
    assert _who(result, "nifen-then-face", LATIN_A) == result["names"]["N"]
    for cp in CJK_PROBES:
        assert _who(result, "nifen-then-face", cp) == face, (
            f"U+{cp:04X} was drawn by {_who(result, 'nifen-then-face', cp)!r}, not by "
            f"the first family that holds it ({face!r}) on {_OS_NAME}"
        )
    hira = _who(result, "nifen-then-face", HIRAGANA)
    kata = _who(result, "nifen-then-face", KATAKANA)
    print(f"[kana] {_OS_NAME}: U+3042 by {hira!r}, U+30AB by {kata!r} (information)")


def test_first_holder_wins_over_a_later_listed_family_that_also_holds_the_character(
    tmp_path,
):
    """[Nifen Art, stand-in, face]: the stand-in, listed first, draws Han and Hangul.

    Both the stand-in and the face hold them, and the face is the one Qt's own
    lookup of registered fonts would reach without the list. So the stand-in
    drawing them can only be list order.
    """
    result = _run_case(
        "first-holder-over-later",
        tmp_path,
        ["Fset", "P"],
        chains={"stand-in-before-face": ["N", "P", "Fset"]},
    )
    stand_in = result["names"]["P"]
    for cp in CJK_PROBES:
        assert _who(result, "stand-in-before-face", cp) == stand_in, (
            f"U+{cp:04X} was drawn by {_who(result, 'stand-in-before-face', cp)!r}, "
            f"not by the earlier listed {stand_in!r} on {_OS_NAME}"
        )
    assert _who(result, "stand-in-before-face", LATIN_A) == result["names"]["N"]


def test_a_listed_familys_substitutes_come_after_the_whole_list(tmp_path):
    """A substitute of Nifen Art never draws a character a later listed face holds.

    The application's own substitutions are installed first; one more substitute
    for Nifen Art, the Han-capable platform stand-in, is added. The control, in a
    process of its own: Nifen Art ALONE must then draw Han from something else,
    which proves the substitution is consulted at all, so the verdict on the list
    is not vacuous.
    """
    alone = _run_case(
        "substitution-alone",
        tmp_path / "alone",
        ["Fset", "P"],
        substitute=["P"],
        chains={"alone": ["N"]},
    )
    nifen = alone["names"]["N"]
    drawn = alone["chains"]["alone"]["drawn"][str(HAN_PROBE)]
    assert drawn["family"] != nifen and not drawn["notdef"], (
        "control: Nifen Art alone drew Han from itself or as a missing glyph, so the "
        f"substitution is not being consulted on {_OS_NAME}: {drawn}"
    )
    listed = _run_case(
        "substitution-order",
        tmp_path / "listed",
        ["Fset", "P"],
        substitute=["P"],
        chains={"list": ["N", "Fset"]},
    )
    face = listed["names"]["Fset"]
    for cp in (HAN_PROBE, HANGUL_PROBE):
        assert _who(listed, "list", cp) == face, (
            f"a substitute of Nifen Art drew U+{cp:04X} ({_who(listed, 'list', cp)!r}) "
            f"ahead of the listed face {face!r} on {_OS_NAME}"
        )
    assert _who(listed, "list", LATIN_A) == nifen


# --------------------------------------------------------------------------- #
# The precedence rule, with its failing control.                               #
# --------------------------------------------------------------------------- #


def test_platform_first_order_lets_the_platform_family_draw_han_the_control(tmp_path):
    """Control: [platform, Nifen Art, face] draws Han from the platform family.

    That IS the defect the rule forbids (REQ-L10N-UI-012). The probe must see it:
    a rule check applied to this order has to answer "violated". If it did not,
    the probe could not detect the defect and the passing CJK-first case below
    would prove nothing.
    """
    result = _run_case(
        "platform-first",
        tmp_path,
        ["Fset", "P"],
        chains={"platform-first": ["P", "N", "Fset"]},
    )
    platform = result["names"]["P"]
    face = result["names"]["Fset"]
    rule_holds = all(
        _who(result, "platform-first", cp) == face for cp in (HAN_PROBE, HANGUL_PROBE)
    )
    assert not rule_holds, (
        f"the probe did not see the defect: in the platform-first order Han/Hangul "
        f"came from {face!r} on {_OS_NAME}, so the rule check cannot fail"
    )
    assert _who(result, "platform-first", HAN_PROBE) == platform
    assert _who(result, "platform-first", HANGUL_PROBE) == platform
    assert _who(result, "platform-first", LATIN_A) == platform


def test_cjk_first_order_draws_han_from_the_face_and_latin_from_the_platform(
    tmp_path,
):
    """[face, platform, Nifen Art]: Han and Hangul from the face, Latin stays put."""
    result = _run_case(
        "cjk-first",
        tmp_path,
        ["Fset", "P"],
        chains={"cjk-first": ["Fset", "P", "N"]},
    )
    platform = result["names"]["P"]
    face = result["names"]["Fset"]
    for cp in CJK_PROBES:
        assert _who(result, "cjk-first", cp) == face, (
            f"U+{cp:04X} came from {_who(result, 'cjk-first', cp)!r}, not the face "
            f"{face!r}, in the CJK-first order on {_OS_NAME}"
        )
    assert _who(result, "cjk-first", LATIN_A) == platform, (
        f"Latin was drawn by {_who(result, 'cjk-first', LATIN_A)!r}, not by the "
        f"platform family {platform!r}, in the CJK-first order on {_OS_NAME}"
    )


@pytest.mark.parametrize(
    "chain,first,other",
    [
        pytest.param(["N", "P"], "N", "P", id="nifen-first"),
        pytest.param(["P", "N", "Fset"], "P", "N", id="platform-first"),
        pytest.param(["Fset", "P", "N"], "Fset", "P", id="cjk-first"),
    ],
)
def test_a_chains_line_metrics_are_the_first_familys(tmp_path, chain, first, other):
    """QFontMetrics of a family list are the FIRST family's, as measured on Windows.

    Three processes, because the first family alone and the list would share one
    cache entry in a single process and the comparison would be trivially true:
    the list, the first family alone, and the other family alone (the
    discriminator, whose line box differs). A different result on another
    operating system fails and names it: it changes what the CJK-first order costs
    a machine whose UI font holds Han.
    """
    faces = ["Fset", "P"]

    def metrics(label: str, tokens: List[str]) -> List[int]:
        done = _run_case(
            f"metrics-{label}",
            tmp_path / label,
            faces,
            chains={label: tokens},
            metrics=True,
            probes=[LATIN_A],
        )
        return list(done["chains"][label]["metrics"])

    in_chain = metrics("chain", chain)
    first_alone = metrics("first-alone", [first])
    other_alone = metrics("other-alone", [other])
    print(
        f"[metrics] {_OS_NAME} {chain}: chain {in_chain}, first family alone "
        f"{first_alone}, other family alone {other_alone}"
    )
    assert other_alone != first_alone, (
        f"the discriminator is blind on {_OS_NAME}: {other!r} and {first!r} alone have "
        f"the same line box {other_alone}"
    )
    assert in_chain == first_alone, (
        f"On {_OS_NAME} the chain's ascent/descent/height {in_chain} are NOT the "
        f"first family's {first_alone} (the other's: {other_alone}). On Windows "
        "they are the first family's; this changes what the CJK-first order costs "
        "and must go back to the architect."
    )


# --------------------------------------------------------------------------- #
# Two lists that share a first family.                                         #
# --------------------------------------------------------------------------- #


def test_two_fonts_that_differ_only_in_their_tail_may_share_one_tail(tmp_path):
    """Measured hazard: the second list takes the first list's Han and Hangul face.

    Two fonts in one process with the same first family, pixel size and weight and
    DIFFERENT later families: the second is drawn from the first's tail. The
    control, in the same process: the same second list at another pixel size gets
    its own tail, so the probe does tell tails apart. The sharing itself is
    asserted as measured on Windows and printed elsewhere, because a design that
    gives two roles (or two menu entries) different CJK faces behind one first
    family depends on it.
    """
    result = _run_case(
        "shared-first-family",
        tmp_path,
        ["Fset", "Fclear"],
        shared_process=True,
        chains={
            "first": ["N", "Fset"],
            "second": ["N", "Fclear"],
            "second-other-size": ["N", "Fclear"],
        },
        sizes={"second-other-size": 13},
        probes=[LATIN_A, HAN_PROBE, HANGUL_PROBE],
    )
    bits = result["names"]["Fset"]
    bare = result["names"]["Fclear"]
    assert _who(result, "first", HAN_PROBE) == bits
    assert _who(result, "second-other-size", HAN_PROBE) == bare, (
        "control: a list at another pixel size did not get its own tail on "
        f"{_OS_NAME}, so this probe cannot tell tails apart"
    )
    shared = _who(result, "second", HAN_PROBE) == bits
    print(
        f"[tail-sharing] {_OS_NAME}: a second list [Nifen Art, {bare}] after "
        f"[Nifen Art, {bits}] at the same size drew U+5B57 from "
        f"{_who(result, 'second', HAN_PROBE)!r}; shared tail: {shared}"
    )
    if sys.platform == "win32":
        assert shared, (
            "On Windows the second list used to take the first list's tail and now "
            "draws from its own: the cache no longer ignores the families after the "
            "first. Re-measure before relying on either behaviour."
        )


# --------------------------------------------------------------------------- #
# Detection: the call the platform-holds-Han check makes.                      #
# --------------------------------------------------------------------------- #


def _holding(detect: Dict[str, Any], token: str, codepoint: int) -> Dict[str, Any]:
    return dict(detect[token]["table"][str(codepoint)])


def test_detection_says_true_for_a_han_capable_family_and_false_for_a_han_free_one(
    tmp_path,
):
    """NoFontMerging with inFontUcs4 and supportsCharacter, integers, registered faces.

    The Han-capable stand-in answers True for Han and Hangul, the Latin-only face
    answers False, and ``A`` is True for both (the control that the call can
    answer True at all). Both calls must agree. Registered faces are used because
    the offscreen platform on Windows cannot see Segoe UI.
    """
    result = _run_case("detection-registered", tmp_path, ["P"], detect=["P", "L"])
    detect = result["detect"]
    for token in ("P", "L"):
        a = _holding(detect, token, LATIN_A)
        assert a["matches"], f"{token} did not resolve to its own family: {a}"
        _require(
            a["inFontUcs4"] and a["supportsCharacter"],
            f"control: 'A' is not held by {token} on {_OS_NAME}: {a}",
        )
    for cp in (HAN_PROBE, HANGUL_PROBE):
        capable = _holding(detect, "P", cp)
        free = _holding(detect, "L", cp)
        _require(
            capable["inFontUcs4"] and capable["supportsCharacter"],
            f"U+{cp:04X}: the Han-capable stand-in was not detected on "
            f"{_OS_NAME}: {capable}",
        )
        _require(
            not free["inFontUcs4"] and not free["supportsCharacter"],
            f"U+{cp:04X}: the Han-free face was reported as holding it on "
            f"{_OS_NAME}: {free}",
        )


def _system_families() -> List[Tuple[str, str]]:
    """Return (id, token) pairs of the system UI families to try on this OS."""
    if sys.platform == "win32":
        return [("segoe-ui", "=Segoe UI"), ("platform-default", "@platform")]
    if sys.platform == "darwin":
        return [("platform-default", "@platform"), ("helvetica", "=Helvetica Neue")]
    return [("dejavu-sans", "=DejaVu Sans"), ("platform-default", "@platform")]


#: Families known to hold no Han: where the plugin resolves them the answer is asserted.
_KNOWN_HAN_FREE = {"Segoe UI", "DejaVu Sans", "Helvetica Neue"}


@pytest.mark.parametrize("entry", _system_families(), ids=lambda e: e[0])
def test_detection_on_a_system_family_is_asserted_only_where_the_plugin_resolves_it(
    tmp_path, entry
):
    """Extra case: a system UI family, judged only if the plugin really resolves it.

    "Resolves" means ``QFontInfo(font).family()`` equals the requested name. Where
    it does not, the answer is printed and nothing is asserted about Han.
    """
    label, token = entry
    result = _run_case(f"detection-system-{label}", tmp_path, [], detect=[token])
    family = result["detect"][token]["family"]
    a = _holding(result["detect"], token, LATIN_A)
    han = _holding(result["detect"], token, HAN_PROBE)
    if not a["matches"]:
        print(
            f"[detection] {family!r} not resolved by the {result['plugin']!r} plugin "
            f"on {_OS_NAME} (resolved to {a['resolved']!r}); no verdict asserted"
        )
        return
    _require(
        a["inFontUcs4"] and a["supportsCharacter"],
        f"control: 'A' is not held by {family!r} on {_OS_NAME}: {a}",
    )
    print(
        f"[detection] {_OS_NAME} {family!r}: Han held inFontUcs4={han['inFontUcs4']} "
        f"supportsCharacter={han['supportsCharacter']}"
    )
    if family in _KNOWN_HAN_FREE:
        _require(
            not han["inFontUcs4"] and not han["supportsCharacter"],
            f"{family!r} was reported as holding U+{HAN_PROBE:04X} on {_OS_NAME}: "
            f"{han}",
        )


# --------------------------------------------------------------------------- #
# The OS/2 range bits.                                                         #
# --------------------------------------------------------------------------- #


def _positions(result: Dict[str, Any], label: str, tokens: Sequence[str]) -> List[int]:
    """Return, per probe, the chain position of the family that drew it (-1: none)."""
    names = [result["names"][t] for t in tokens]
    row = []
    for cp in PROBES:
        drawn = _who(result, label, cp)
        row.append(names.index(drawn) if drawn in names else -1)
    return row


@pytest.mark.parametrize(
    "label,tokens",
    [
        pytest.param("nifen-mode", ("N", "{F}", "P"), id="nifen-mode"),
        pytest.param("platform-first", ("P", "N", "{F}"), id="platform-first"),
        pytest.param("cjk-first", ("{F}", "P", "N"), id="cjk-first"),
    ],
)
def test_clearing_the_range_bits_changes_no_position_in_the_chain(
    tmp_path, label, tokens
):
    """The bits-cleared face is drawn in the same chain positions as the bits-set one.

    Each variant is measured in a process of its own, and each probe is mapped to
    the POSITION of the family that drew it. The stand-in also holds Han and
    Hangul, so a face that is skipped for Han shows up as a position, not as a
    silent success. A difference is printed and fails, naming the operating
    system: the build would then have to set the bits.
    """
    positions: Dict[str, List[int]] = {}
    for variant in ("Fset", "Fclear"):
        chain_tokens = [t.replace("{F}", variant) for t in tokens]
        result = _run_case(
            f"bits-{label}-{variant}",
            tmp_path / variant,
            [variant, "P"],
            chains={label: chain_tokens},
        )
        positions[variant] = _positions(result, label, chain_tokens)
    print(
        f"[bits] {_OS_NAME} {label}: positions with bits set {positions['Fset']}, "
        f"cleared {positions['Fclear']} (probes {[f'U+{c:04X}' for c in PROBES]})"
    )
    assert positions["Fset"] == positions["Fclear"], (
        f"On {_OS_NAME} the OS/2 CJK range bits change which chain position draws "
        f"a probe in the {label} order: set {positions['Fset']}, cleared "
        f"{positions['Fclear']}. The font build must set the bits."
    )


# --------------------------------------------------------------------------- #
# Past the end of the list: the operating system.                              #
# --------------------------------------------------------------------------- #


def test_a_family_that_does_not_exist_falls_to_the_operating_system(tmp_path):
    """[Nifen Art, "No Such Family"]: asserted on Linux only (REQ-L10N-UI-011).

    Only Nifen Art and the Latin-only face are registered here, so a Han character
    can come from nowhere but the operating system. On Windows and macOS the
    offscreen platform does not reach one, and the case says so instead of passing
    the clause.
    """
    result = _run_case(
        "operating-system-fallback",
        tmp_path,
        [],
        chains={"missing": ["N", "=No Such Family"]},
        probes=[LATIN_A, HAN_PROBE, HANGUL_PROBE, HIRAGANA],
    )
    drawn = result["chains"]["missing"]["drawn"][str(HAN_PROBE)]
    nifen = result["names"]["N"]
    if sys.platform.startswith("linux"):
        if not drawn["holds"] or drawn["notdef"] or drawn["family"] == nifen:
            if os.environ.get("PIXELART_REQUIRE_FALLBACK_FONT"):
                pytest.fail(
                    "the probe font for the operating-system fallback is not "
                    f"installed: U+{HAN_PROBE:04X} was drawn by {drawn}"
                )
            pytest.skip(
                "no system font holds U+5B57 on this Linux host "
                "(PIXELART_REQUIRE_FALLBACK_FONT is not set)"
            )
        assert drawn["family"] != nifen
        print(
            f"[fallback] Linux: U+{HAN_PROBE:04X} drawn by the operating system's "
            f"{drawn['family']!r}"
        )
        return
    print(
        f"OS fallback not observable on {_OS_NAME} offscreen; proven on Linux "
        f"(measured here on the {result['plugin']!r} plugin: U+{HAN_PROBE:04X} "
        f"drawn by {drawn['family']!r}, missing glyph {drawn['notdef']})"
    )


# --------------------------------------------------------------------------- #
# Extra cases: a real system font's file, registered by path.                  #
# --------------------------------------------------------------------------- #


def _system_han_files() -> List[Path]:
    """Return the Han-capable system font files to try on this operating system."""
    if sys.platform == "win32":
        system_root = os.environ.get("SystemRoot", "")
        if not system_root:
            return []
        fonts = Path(system_root) / "Fonts"
        return [fonts / n for n in ("malgun.ttf", "msyh.ttc", "YuGothM.ttc")]
    if sys.platform == "darwin":
        base = Path("/System/Library/Fonts")
        names = (
            "PingFang.ttc",
            "Hiragino Sans GB.ttc",
            "AppleSDGothicNeo.ttc",
            "ヒラギノ角ゴシック W3.ttc",
        )
        return [base / n for n in names]
    found: List[Path] = []
    for root in (
        Path("/usr/share/fonts"),  # portability: ok (Linux system font root probe)
        Path("/usr/local/share/fonts"),  # portability: ok (Linux font root probe)
    ):
        if root.is_dir():
            found.extend(sorted(root.rglob("NotoSansCJK*-Regular.*")))
    return found[:1]


_SYSTEM_FILES = [p for p in _system_han_files() if p.is_file()]


@pytest.mark.parametrize(
    "font_file", _SYSTEM_FILES or [None], ids=lambda p: p.name if p else "none-found"
)
def test_the_rule_holds_for_a_real_system_han_family_registered_by_path(
    tmp_path, font_file
):
    """Extra: the platform-first defect and the CJK-first rule on a real family.

    The file is registered by path (Windows: a Malgun Gothic, Microsoft YaHei or Yu
    Gothic file; macOS: a PingFang or Hiragino file; Linux: the CJK probe font the
    CI installs). The names actually found are printed. One process finds the
    Han-capable families of the file; each family then gets one process per order.
    This case is never the only one: the registered stand-ins above carry the
    verdict.
    """
    if font_file is None:
        message = f"no Han-capable system font file found on {_OS_NAME}"
        if sys.platform.startswith("linux") and os.environ.get(
            "PIXELART_REQUIRE_FALLBACK_FONT"
        ):
            pytest.fail(message + " (the CI probe font is not installed)")
        pytest.skip(message)
    paths = [str(font_file)]
    found = _run_case(
        f"real-{font_file.name}-families",
        tmp_path / "families",
        ["Fset"],
        register_paths=paths,
        discover=True,
    )
    print(
        f"[real] {_OS_NAME} {font_file.name}: families {found['registered']}, "
        f"Han-capable {found['han_capable']}"
    )
    _require(
        bool(found["han_capable"]),
        f"no family of {font_file} holds U+{HAN_PROBE:04X} through the "
        f"{found['plugin']!r} plugin",
    )
    face = found["names"]["Fset"]
    nifen = found["names"]["N"]
    for index, family in enumerate(found["han_capable"]):
        table = found["detect_real"][family]
        assert table[str(LATIN_A)]["inFontUcs4"], (family, table)
        assert table[str(HAN_PROBE)]["inFontUcs4"], (family, table)
        assert table[str(HAN_PROBE)]["supportsCharacter"], (family, table)
        orders = {
            "platform-first": [f"={family}", "N", "Fset"],
            "cjk-first": ["Fset", f"={family}", "N"],
        }
        drawn: Dict[str, Dict[str, Any]] = {}
        for order, tokens in orders.items():
            drawn[order] = _run_case(
                f"real-{font_file.name}-{index}-{order}",
                tmp_path / f"{index}-{order}",
                ["Fset"],
                register_paths=paths,
                chains={order: tokens},
            )
        same = list(found["registered"])
        platform_first = _who(drawn["platform-first"], "platform-first", HAN_PROBE)
        # The defect: the platform family ahead of the face draws Han.
        assert platform_first != face, (
            f"{family!r}: the probe did not see the defect in the platform-first "
            f"order on {_OS_NAME}"
        )
        assert _is_from(platform_first, same), (family, platform_first)
        # The rule: the face first draws Han and Hangul, and the family keeps Latin.
        cjk_first = drawn["cjk-first"]
        assert _who(cjk_first, "cjk-first", HAN_PROBE) == face
        assert _who(cjk_first, "cjk-first", HANGUL_PROBE) == face
        latin = _who(cjk_first, "cjk-first", LATIN_A)
        assert _is_from(latin, same) and latin != nifen
        print(
            f"[kana] {_OS_NAME} {family!r}: platform-first U+3042 by "
            f"{_who(drawn['platform-first'], 'platform-first', HIRAGANA)!r}, U+30AB by "
            f"{_who(drawn['platform-first'], 'platform-first', KATAKANA)!r} "
            "(information only)"
        )


# --------------------------------------------------------------------------- #
# The chain tag against Qt's font cache.                                       #
# --------------------------------------------------------------------------- #
#
# Qt's font cache ignores the families after the first (the case above), so two
# fonts that agree on first family, pixel size, weight and the other attributes
# the cache keys on are drawn with ONE tail. The application keeps its family
# lists apart by carrying a *chain tag* in the font's style strategy, and the
# four cases below measure, for each candidate flag and on every operating
# system, the two properties that mechanism needs:
#
# * SEPARATION: a list that carries the tag gets its own tail, even when an
#   earlier list with the same first family was drawn untagged (and the other
#   way round). It is judged against a CONTROL in the same process, the same
#   pair of lists without the tag, which must share a tail where the platform
#   shares at all; where it does not, the case says "not observable" and the
#   flag is judged on neutrality alone there.
# * NEUTRALITY: the tag changes nothing else. The same list and sample are
#   drawn untagged and tagged in separate processes, and the glyph runs
#   (family, glyph indexes, positions), the rendered pixels and the font
#   metrics must be identical.
#
# Both are judged twice: through a ``QTextLayout`` (the family of every glyph
# run) and through a real ``QLabel`` (pixels only), since a widget could reach
# the cache differently from a bare layout. Two registered fixture faces whose
# Han and Hangul boxes differ in shape let a pixel comparison tell which face
# drew. The cache key includes the pixel size, so a case that needs several
# independent experiments in one process gives each its own pixel size.

#: The style-strategy flags a chain tag may be made of, one candidate each.
TAG_CANDIDATES: Tuple[str, ...] = (
    "PreferOutline",
    "ForceOutline",
    "PreferMatch",
    "PreferQuality",
)
#: The two bases a family list is put on: the interface font (Nifen mode) and
#: the platform default font (the platform-text mode).
BASES: Tuple[str, ...] = ("nifen", "default")

#: Latin, Han, Hangul, kana, punctuation and a space: what neutrality draws.
SAMPLE: Tuple[int, ...] = (
    LATIN_A,
    HAN_PROBE,
    HANGUL_PROBE,
    HIRAGANA,
    KATAKANA,
    0x3001,
    0x2E,
    0x20,
)
#: The characters a pixel comparison uses to tell which face drew.
SHAPE_TEXT: Tuple[int, ...] = (HAN_PROBE, HANGUL_PROBE)
#: The pixel sizes neutrality is judged at: the interface em, a size that is not
#: a multiple of the em (a platform text size), and the guide's largest heading.
NEUTRAL_SIZES: Tuple[int, ...] = (12, 13, 24)
_NEUTRAL_WANT: Tuple[str, ...] = ("probes", "runs", "pixels", "label", "metrics")

Rect = Tuple[int, int, int, int]

#: Fixture faces whose Han and Hangul boxes differ in shape (ink columns and
#: rows in pixels of the 12 px em; every box starts at column 0 so the left
#: side bearing is zero and the outline is not shifted by the rasteriser).
TAIL_FACES: Dict[str, Tuple[str, Dict[int, Rect]]] = {
    "Fa": (
        "Probe Tail A",
        {
            HAN_PROBE: (0, 5, 11, 10),
            HAN_SECOND: (0, 5, 11, 10),
            HANGUL_PROBE: (0, -1, 5, 10),
            HANGUL_SECOND: (0, -1, 5, 10),
        },
    ),
    "Fb": (
        "Probe Tail B",
        {
            HAN_PROBE: (0, -1, 11, 4),
            HAN_SECOND: (0, -1, 11, 4),
            HANGUL_PROBE: (0, -1, 11, 1),
            HANGUL_SECOND: (0, -1, 11, 1),
        },
    ),
}


def build_tail_face(
    family: str, shapes: Dict[int, Rect], path: Path, *, range_bits: bool = True
) -> Path:
    """Write a Han-and-Hangul face whose boxes are ``shapes`` and return ``path``.

    The face is built exactly as the other fixture faces are (the line box of
    Nifen Art, the OS/2 CJK range bits set, or cleared when ``range_bits`` is
    False), and each listed glyph is then replaced by a plain rectangle, with its
    left side bearing set to its own left edge. No glyph is taken from any font.
    """
    unicode_bits = _BITS_CJK if range_bits else ()
    codepage_bits = _CODEPAGE_CJK if range_bits else ()
    build_face(
        Face(family, tuple(shapes), 11, 3, unicode_bits, codepage_bits),
        path,
    )
    font = TTFont(str(path))
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    for codepoint, (x0, y0, x1, y1) in shapes.items():
        pen = TTGlyphPen(None)
        pen.moveTo((x0 * _PX, y0 * _PX))
        pen.lineTo((x0 * _PX, y1 * _PX))
        pen.lineTo((x1 * _PX, y1 * _PX))
        pen.lineTo((x1 * _PX, y0 * _PX))
        pen.closePath()
        glyph = pen.glyph()
        glyph.recalcBounds(glyf)
        name = _glyph_name(codepoint)
        glyf[name] = glyph
        hmtx[name] = (_ADVANCE, glyph.xMin)
    font.save(str(path))
    return path


#: A face the platform's own fallback search has no reason to choose: the shapes
#: of ``Fa`` with the OS/2 CJK range bits cleared. The cases that need a tail
#: reachable through a family list and by no other route register it ALONE (not
#: ``Fa`` or ``Fb``, which hold Han with their range bits set and which a font
#: with no family list reaches through the platform's fallback; measured).
QUIET_FACES: Dict[str, Tuple[str, Dict[int, Rect]]] = {
    "Fq": ("Probe Tail Quiet", TAIL_FACES["Fa"][1])
}


def _table_token(index: int) -> str:
    """Return the token of the ``index``-th face of the combination table."""
    return f"G{index:02d}"


def _tail_face_files(
    tmp_path: Path, table_size: int, quiet: bool
) -> Dict[str, Tuple[str, str]]:
    """Generate every face a tail case registers; return token -> (path, family)."""
    out = _build_faces(tmp_path, ["L"])
    for token, (family, shapes) in () if quiet else TAIL_FACES.items():
        out[token] = (
            str(build_tail_face(family, shapes, tmp_path / f"{token}.ttf")),
            family,
        )
    for token, (family, shapes) in QUIET_FACES.items() if quiet else ():
        path = build_tail_face(
            family, shapes, tmp_path / f"{token}.ttf", range_bits=False
        )
        out[token] = (str(path), family)
    for index in range(table_size):
        token = _table_token(index)
        family = f"Probe Tail Table {index:02d}"
        shapes = {cp: (0, 5, 11, 10) for cp in CJK_PROBES}
        out[token] = (
            str(build_tail_face(family, shapes, tmp_path / f"{token}.ttf")),
            family,
        )
    return out


#: Runs in a fresh interpreter, like ``_CHILD``. It reads one JSON spec, builds
#: the families the way the application does, runs the positive control, then
#: executes the spec's steps IN ORDER in this one process (the subject of a tail
#: case is what an earlier font does to a later one) and prints one ``RESULT``
#: line. Every font is built the way the application will build a chain: a copy
#: of the base font, ``setFamilies``, then the base's style strategy with every
#: candidate flag cleared and the tag's flags set.
_TAIL_CHILD = r"""
import hashlib
import json
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QPointF, Qt, qVersion
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QPainter,
    QPalette,
    QTextLayout,
)
from PySide6.QtWidgets import QApplication, QLabel

spec = json.loads(sys.argv[1])
app = QApplication([])
from pixelart_creator.ui import app_font

STRAT = QFont.StyleStrategy
TAG_MASK = (
    STRAT.PreferOutline | STRAT.ForceOutline | STRAT.PreferMatch | STRAT.PreferQuality
)
LINES = []


def say(text):
    LINES.append(str(text))


def cp_name(cp):
    return "U+%04X" % cp


def text_of(cps):
    return "".join(chr(cp) for cp in cps)


nifen_registered = bool(app_font.register_app_fonts())
app_font.capture_platform_font()
app_font.install_font_substitutions()

NAMES = {"N": app_font.NIFEN_ART_FAMILY}
errors = []
for token, entry in spec["faces"].items():
    path, expected = entry
    font_id = QFontDatabase.addApplicationFont(path)
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    if expected not in families:
        errors.append("%s: wanted %r, Qt registered %r" % (token, expected, families))
    NAMES[token] = expected


def base_font():
    if spec["base"] == "nifen":
        return app_font.interface_font()
    return app_font.platform_default_font()


NAMES["P"] = base_font().family()


def make_font(chain, px, tag):
    font = base_font()
    if chain is not None:
        font.setFamilies(list(chain))
    font.setPixelSize(px)
    if tag:
        strategy = font.styleStrategy() & ~TAG_MASK
        for name in tag:
            strategy |= getattr(STRAT, name)
        font.setStyleStrategy(strategy)
    return font


def laid_out(font, text):
    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(100000)
    layout.endLayout()
    return layout


def one(font, cp):
    runs = laid_out(font, chr(cp)).glyphRuns()
    if not runs:
        return {"family": "", "notdef": True}
    raw = runs[0].rawFont()
    glyphs = [int(g) for g in runs[0].glyphIndexes()]
    return {"family": raw.familyName(), "notdef": 0 in glyphs}


def runs_of(layout):
    out = []
    for run in layout.glyphRuns():
        out.append(
            {
                "family": run.rawFont().familyName(),
                "glyphs": [int(g) for g in run.glyphIndexes()],
                "positions": [
                    [round(p.x(), 3), round(p.y(), 3)] for p in run.positions()
                ],
            }
        )
    # glyphRuns() does not promise an order (measured: it varies between runs), so
    # the runs are put in the order they are drawn from left to right.
    out.sort(key=lambda r: (r["positions"][:1], r["family"]))
    return out


def image_hash(image):
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def gray_count(image):
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if (image.pixel(x, y) & 0xFFFFFF) not in (0xFFFFFF, 0x000000):
                count += 1
    return count


def layout_pixels(font, text, px):
    image = QImage(px * (len(text) + 2), px * 2 + 8, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    layout = laid_out(font, text)
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    layout.draw(painter, QPointF(4, 4))
    painter.end()
    return {"sha256": image_hash(image), "gray": gray_count(image)}


def label_hash(font, text, px):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setFont(font)
    palette = label.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("white"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("black"))
    label.setPalette(palette)
    label.setAutoFillBackground(True)
    label.setFixedSize(px * (len(text) + 2), px * 2 + 8)
    image = label.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    label.deleteLater()
    return image_hash(image)


def metrics_of(font, text):
    fm = QFontMetrics(font)
    return {
        "ascent": fm.ascent(),
        "descent": fm.descent(),
        "height": fm.height(),
        "leading": fm.leading(),
        "averageCharWidth": fm.averageCharWidth(),
        "maxWidth": fm.maxWidth(),
        "xHeight": fm.xHeight(),
        "advance": fm.horizontalAdvance(text),
    }


say(
    "plugin %s; PySide6 %s; Qt %s; Python %s; base %s"
    % (
        QGuiApplication.platformName(),
        pyside_version,
        qVersion(),
        sys.version.split()[0],
        spec["base"],
    )
)

# The positive control comes before any verdict: at a pixel size no step uses,
# so it cannot give any later step a tail.
ctl = spec["control"]
ctl_chain = [NAMES[t] for t in ctl["chain"]]
ctl_drew = one(make_font(ctl_chain, ctl["px"], []), ctl["cp"])
control = {
    "ok": ctl_drew["family"] == NAMES[ctl["expect"]],
    "drew": ctl_drew["family"],
    "expected": NAMES[ctl["expect"]],
    "chain": ctl_chain,
    "cp": ctl["cp"],
}
say(
    "positive control: %s drawn by %r (expected %r) -> %s"
    % (
        cp_name(ctl["cp"]),
        control["drew"],
        control["expected"],
        "ok" if control["ok"] else "FAILED",
    )
)

steps = {}
for step in spec["steps"]:
    op = step.get("op", "draw")
    if op == "fontkey":
        fonts = []
        for side in ("a", "b"):
            names = [NAMES[t] for t in step[side]["chain"]]
            fonts.append(make_font(names, step["px"], step[side]["tag"]))
        eq = bool(fonts[0] == fonts[1])
        key_eq = bool(fonts[0].key() == fonts[1].key())
        steps[step["id"]] = {"eq": eq, "key_eq": key_eq}
        say("fontkey %s: == %s, key() equal %s" % (step["id"], eq, key_eq))
        continue
    chain = [NAMES[t] for t in step["chain"]] if step["chain"] is not None else None
    px = step["px"]
    tag = step.get("tag", [])
    font = make_font(chain, px, tag)
    want = step.get("want", ["probes"])
    text = text_of(step.get("text", spec["sample"]))
    record = {"chain": chain, "px": px, "tag": tag}
    shown = []
    if "probes" in want:
        record["probes"] = {str(cp): one(font, cp) for cp in spec["probes"]}
        for cp in spec["probes"]:
            row = record["probes"][str(cp)]
            missing = " (missing)" if row["notdef"] else ""
            shown.append("%s=%s%s" % (cp_name(cp), row["family"] or "-", missing))
    if "runs" in want:
        record["runs"] = runs_of(laid_out(font, text))
    if "pixels" in want:
        record["pixels"] = layout_pixels(font, text, px)
    if "label" in want:
        record["label"] = label_hash(font, text, px)
    if "metrics" in want:
        record["metrics"] = metrics_of(font, text)
    steps[step["id"]] = record
    say(
        "step %s: %r at %s px, tag %r -> %s"
        % (step["id"], chain, px, tag, "; ".join(shown) or ",".join(want))
    )

print(
    "RESULT "
    + json.dumps(
        {
            "plugin": QGuiApplication.platformName(),
            "nifen_registered": nifen_registered,
            "registration_errors": errors,
            "names": NAMES,
            "control": control,
            "steps": steps,
            "info": LINES,
        }
    ),
    flush=True,
)
"""


def _spawn_tail(
    name: str,
    tmp_path: Path,
    base: str,
    steps: Sequence[Dict[str, Any]],
    *,
    table_size: int = 0,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Run ``steps`` in order in ONE fresh interpreter and return what it measured.

    Prints every line the child measured. The positive control is asserted FIRST,
    so no verdict is read from a plugin that cannot tell registered families
    apart. Unlike ``_run_case``, several font lists share the process on purpose:
    what an earlier font does to a later one is the subject.
    """
    profile = tmp_path / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    spec = {
        "base": base,
        "faces": _tail_face_files(tmp_path, table_size, quiet),
        # Pixel size 10 is used by no step: the control builds no engine a step uses.
        "control": {"chain": ["L", "N"], "expect": "N", "cp": N_TILDE, "px": 10},
        "probes": list(PROBES),
        "sample": list(SAMPLE),
        "steps": list(steps),
    }
    env = dict(os.environ)
    env.update(
        PYTHONPATH=os.pathsep.join(
            [str(_REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        ),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
    )
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    done = subprocess.run(
        [sys.executable, "-B", "-c", _TAIL_CHILD, json.dumps(spec)],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert (
        done.returncode == 0
    ), f"{name}: the child exited {done.returncode}\n{done.stdout}\n{done.stderr}"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert (
        lines
    ), f"{name}: the child printed no RESULT line\n{done.stdout}\n{done.stderr}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    for line in result["info"]:
        print(f"[{name}] [{_OS_NAME}] {line}")
    assert result["nifen_registered"], f"{name}: Nifen Art did not register"
    assert not result["registration_errors"], (
        f"{name}: a synthetic face was not registered under its own family name: "
        f"{result['registration_errors']}"
    )
    ctl = result["control"]
    assert ctl["ok"], (
        f"{name}: the positive control FAILED on the {result['plugin']!r} plugin "
        f"({_OS_NAME}): U+{ctl['cp']:04X} in {ctl['chain']} was drawn by "
        f"{ctl['drew']!r}, not by the next registered family {ctl['expected']!r}. "
        "This plugin cannot tell registered families apart, so no verdict below "
        "can be read from it."
    )
    return result


def _step(
    step_id: str,
    chain: Optional[Sequence[str]],
    px: int,
    *,
    tag: Sequence[str] = (),
    want: Sequence[str] = ("probes",),
    text: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Return one draw step: a family list at a pixel size, with a tag.

    ``chain`` None draws the base font itself, with no family list put on it.
    """
    step: Dict[str, Any] = {
        "id": step_id,
        "chain": None if chain is None else list(chain),
        "px": px,
        "tag": list(tag),
        "want": list(want),
    }
    if text is not None:
        step["text"] = list(text)
    return step


def _han_by(result: Dict[str, Any], step_id: str) -> str:
    """Return the family that drew the Han probe in step ``step_id``."""
    return str(result["steps"][step_id]["probes"][str(HAN_PROBE)]["family"])


def _label_steps(
    prefix: str, px: int, first_tag: Sequence[str], second_tag: Sequence[str]
) -> List[Dict[str, Any]]:
    """Return the steps of one label experiment at pixel size ``px``.

    Two reference labels (each face alone, so they have a first family of their
    own and cannot be given anyone's tail), then the pair under test: ``[Nifen
    Art, Fa]`` and ``[Nifen Art, Fb]`` behind one first family.
    """
    want = ("label",)
    return [
        _step(f"{prefix}-ref-a", ["Fa"], px, want=want, text=SHAPE_TEXT),
        _step(f"{prefix}-ref-b", ["Fb"], px, want=want, text=SHAPE_TEXT),
        _step(
            f"{prefix}-1", ["N", "Fa"], px, tag=first_tag, want=want, text=SHAPE_TEXT
        ),
        _step(
            f"{prefix}-2", ["N", "Fb"], px, tag=second_tag, want=want, text=SHAPE_TEXT
        ),
    ]


def _label_outcome(result: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Judge a label experiment by pixels: which face drew each of the two labels.

    ``calibrated`` is the instrument check: the references differ from each
    other, and the first label (first at its cache key, so nothing can have given
    it a tail) is pixel-identical to its own face alone. Without it a pixel
    verdict means nothing.
    """
    steps = result["steps"]
    ref_a = steps[f"{prefix}-ref-a"]["label"]
    ref_b = steps[f"{prefix}-ref-b"]["label"]

    def kind(step_id: str) -> str:
        got = steps[step_id]["label"]
        return "A" if got == ref_a else "B" if got == ref_b else "other"

    return {
        "calibrated": ref_a != ref_b and kind(f"{prefix}-1") == "A",
        "first": kind(f"{prefix}-1"),
        "second": kind(f"{prefix}-2"),
    }


def _first_difference(left: Any, right: Any, path: str = "") -> Optional[str]:
    """Return a description of the first place two measurements differ, or None."""
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return f"{path}/{key}: present on one side only"
            found = _first_difference(left[key], right[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path}: {len(left)} entries against {len(right)}"
        for index, (a, b) in enumerate(zip(left, right)):
            found = _first_difference(a, b, f"{path}[{index}]")
            if found:
                return found
        return None
    if left != right:
        return f"{path}: {left!r} against {right!r}"
    return None


# --------------------------------------------------------------------------- #
# The control: the sharing, reproduced.                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("order", ["a-then-b", "b-then-a"])
def test_chain_tag_control_two_untagged_lists_share_one_tail(tmp_path, base, order):
    """Control: untagged [Nifen Art, A] then [Nifen Art, B] draw both from one tail.

    The reproduction of the hazard the tag exists for, in both build orders and in
    both bases (the interface font's strategy, and the platform default). A
    probe that cannot see the hazard could not judge the tag. The control in the
    same process: the second list at another pixel size gets its own tail, so
    the probe does tell tails apart. The sharing itself is asserted on Windows,
    where it was measured, and printed elsewhere.
    """
    first, second = (
        (["N", "Fa"], ["N", "Fb"])
        if order == "a-then-b"
        else (["N", "Fb"], ["N", "Fa"])
    )
    result = _spawn_tail(
        f"tag-control-{base}-{order}",
        tmp_path,
        base,
        [
            _step("first", first, 12),
            _step("second", second, 12),
            _step("second-other-size", second, 13),
        ],
    )
    names = result["names"]
    first_tail = names[first[1]]
    second_tail = names[second[1]]
    assert _han_by(result, "first") == first_tail
    assert _han_by(result, "second-other-size") == second_tail, (
        "control: a list at another pixel size did not get its own tail on "
        f"{_OS_NAME}, so this probe cannot tell tails apart"
    )
    shared = _han_by(result, "second") == first_tail
    print(
        f"[tail-sharing] {_OS_NAME} base={base} order={order}: [Nifen Art, "
        f"{second_tail}] after [Nifen Art, {first_tail}] at one size drew U+5B57 "
        f"from {_han_by(result, 'second')!r}; shared tail: {shared}"
    )
    if sys.platform == "win32":
        assert shared, (
            "On Windows the second list used to take the first list's tail and now "
            "draws from its own: the cache no longer ignores the families after the "
            "first. Re-measure before relying on either behaviour."
        )


@pytest.mark.parametrize("base", BASES)
def test_chain_tag_control_the_sharing_is_seen_through_a_real_label(tmp_path, base):
    """Control through ``QLabel``: the second label shows the first label's Han face.

    A label is drawn into an image and which face drew is told by its pixels,
    against two reference labels (each face alone). The first label, first at its
    cache key, must equal its own face's reference: that is the calibration of
    the pixel judge. The sharing is asserted on Windows and printed elsewhere.
    """
    result = _spawn_tail(
        f"tag-control-label-{base}",
        tmp_path,
        base,
        _label_steps("lc", 16, [], []),
    )
    outcome = _label_outcome(result, "lc")
    assert outcome["calibrated"], (
        f"the pixel judge is not calibrated on {_OS_NAME}: the two reference labels "
        f"are identical, or the first label is not its own face alone: {outcome}"
    )
    print(
        f"[tail-sharing-label] {_OS_NAME} base={base}: the second label is drawn "
        f"with face {outcome['second']!r} (A is the first list's tail, B its own)"
    )
    assert outcome["second"] in {
        "A",
        "B",
    }, f"the second label matched neither reference on {_OS_NAME}: {outcome}"
    if sys.platform == "win32":
        assert outcome["second"] == "A", (
            "On Windows a real label shared the first list's tail through "
            "QTextLayout but does not now: re-measure before relying on either."
        )


def test_chain_tag_fixture_faces_differ_in_shape_and_stay_boxes(tmp_path):
    """The two tail faces hold the same code points in different, plain boxes."""
    built = {
        token: build_tail_face(family, shapes, tmp_path / f"{token}.ttf")
        for token, (family, shapes) in TAIL_FACES.items()
    }
    boxes: Dict[str, Dict[int, Tuple[int, int, int, int]]] = {}
    for token, path in built.items():
        font = TTFont(str(path))
        cmap = font.getBestCmap()
        assert sorted(cmap) == sorted(CJK_PROBES), (token, sorted(cmap))
        glyf = font["glyf"]
        boxes[token] = {}
        for codepoint in CJK_PROBES:
            glyph = glyf[cmap[codepoint]]
            coords, ends, _flags = glyph.getCoordinates(glyf)
            assert len(ends) == 1 and len(coords) == 4, (token, codepoint)
            assert font["hmtx"][cmap[codepoint]][1] == glyph.xMin, (token, codepoint)
            boxes[token][codepoint] = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
        assert font["hhea"].ascent == 11 * _PX and -font["hhea"].descent == 3 * _PX
    for codepoint in CJK_PROBES:
        assert boxes["Fa"][codepoint] != boxes["Fb"][codepoint], codepoint
    print(f"[tail-faces] boxes (font units) {boxes}")


# --------------------------------------------------------------------------- #
# Separation: the tag gives a list its own tail.                               #
# --------------------------------------------------------------------------- #


def _measure_separation(
    tmp_path: Path, base: str, flag: str, *, tag: Optional[Sequence[str]] = None
) -> Dict[str, Any]:
    """Measure whether ``tag`` (default: ``flag`` alone) separates two tails.

    One process, four independent experiments, each at a pixel size of its own
    (the pixel size is part of the cache key, so the experiments cannot give one
    another a tail):

    * the control, 17 px: the pair without a tag, through ``QTextLayout``;
    * 12 px: ``[Nifen Art, A]`` untagged, then ``[Nifen Art, B]`` tagged;
    * 14 px: ``[Nifen Art, A]`` tagged, then ``[Nifen Art, B]`` untagged;
    * 16 px and 18 px: the tagged pair and the control pair through ``QLabel``.

    The returned ``verdict`` is ``separates``, ``not separated`` or ``not
    observable`` (the control shows no sharing here, so nothing could be
    separated).
    """
    applied = [flag] if tag is None else list(tag)
    steps = [
        _step("ctl-1", ["N", "Fa"], 17),
        _step("ctl-2", ["N", "Fb"], 17),
        _step("e1-1", ["N", "Fa"], 12),
        _step("e1-2", ["N", "Fb"], 12, tag=applied),
        _step("e2-1", ["N", "Fa"], 14, tag=applied),
        _step("e2-2", ["N", "Fb"], 14),
    ]
    steps += _label_steps("lc", 18, [], [])
    steps += _label_steps("lt", 16, [], applied)
    result = _spawn_tail(f"tag-separation-{base}-{flag}", tmp_path, base, steps)
    fa = result["names"]["Fa"]
    fb = result["names"]["Fb"]
    sane = (
        _han_by(result, "ctl-1") == fa
        and _han_by(result, "e1-1") == fa
        and _han_by(result, "e2-1") == fa
    )
    observable = _han_by(result, "ctl-2") == fa
    own_first_order = _han_by(result, "e1-2") == fb
    own_second_order = _han_by(result, "e2-2") == fb
    control_label = _label_outcome(result, "lc")
    tagged_label = _label_outcome(result, "lt")
    label_observable = control_label["second"] == "A"
    own_label = tagged_label["second"] == "B"
    if not observable:
        verdict = "not observable"
    elif own_first_order and own_second_order and (own_label or not label_observable):
        verdict = "separates"
    else:
        verdict = "not separated"
    print(
        f"[tag-separation] {_OS_NAME} base={base} tag={applied}: control shares "
        f"{observable}; own tail after an untagged list {own_first_order}, "
        f"untagged after a tagged list {own_second_order}; label control shares "
        f"{label_observable}, tagged label has its own tail {own_label} "
        f"-> {verdict}"
    )
    return {
        "verdict": verdict,
        "sane": sane,
        "observable": observable,
        "own_first_order": own_first_order,
        "own_second_order": own_second_order,
        "label_calibrated": control_label["calibrated"] and tagged_label["calibrated"],
        "label_observable": label_observable,
        "own_label": own_label,
        "names": result["names"],
    }


def _assert_separation(flag: str, base: str, measured: Dict[str, Any]) -> None:
    """Fail naming the flag unless it separates where separation is observable."""
    assert measured["sane"], (
        f"{flag}/{base} on {_OS_NAME}: a first list did not draw its own tail, so "
        "the probe is blind"
    )
    assert measured["label_calibrated"], (
        f"{flag}/{base} on {_OS_NAME}: the pixel judge of the label experiments is "
        "not calibrated (the references are identical, or a first label is not its "
        "own face alone)"
    )
    if sys.platform == "win32":
        assert measured["observable"], (
            "On Windows two untagged lists behind one first family used to share a "
            "tail and do not now: re-measure before judging any flag."
        )
    if measured["verdict"] == "not observable":
        print(
            f"[tag-separation] flag {flag} ({base}): not observable: no sharing on "
            f"{_OS_NAME}; judged on neutrality alone here"
        )
        return
    assert measured["verdict"] == "separates", (
        f"flag {flag} does not separate tails in the {base} base on {_OS_NAME}: "
        f"a list sharing the first family of an earlier list drew from its own tail "
        f"after an untagged list: {measured['own_first_order']}, before one: "
        f"{measured['own_second_order']}; through a QLabel: "
        f"{measured['own_label']}. The flag is dropped on this operating system."
    )


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("flag", TAG_CANDIDATES)
def test_chain_tag_flag_gives_a_list_its_own_tail(tmp_path, flag, base):
    """Separation: a list tagged with ``flag`` is drawn from its own tail.

    Both orders (the tagged list second, and first) and both ways of drawing
    (family of the glyph run through ``QTextLayout``, and the pixels of a real
    ``QLabel``). Judged only where the control in the same process shows the
    sharing; where it does not, the case prints "not observable" and the flag is
    judged on neutrality alone.
    """
    _assert_separation(flag, base, _measure_separation(tmp_path, base, flag))


@pytest.mark.parametrize("base", BASES)
def test_chain_tag_probe_fails_when_no_tag_is_applied(tmp_path, base):
    """Instrument proof: with NO tag, the separation probe must report no separation.

    The same measurement with an empty tag is the sabotaged copy. On a platform
    where untagged lists share a tail, both orders must then be drawn from the
    shared tail; if they were not, the separation cases above could pass without
    any tag at all. Where nothing is shared the case prints that.
    """
    measured = _measure_separation(tmp_path, base, "none", tag=[])
    if not measured["observable"]:
        print(
            f"[tag-separation] untagged control: not observable: no sharing on "
            f"{_OS_NAME}"
        )
        return
    assert measured["verdict"] == "not separated", (
        f"the separation probe passed on {_OS_NAME} with no tag applied: "
        f"{measured}; it cannot tell a tag from the lack of one"
    )
    assert not measured["own_first_order"], measured
    assert not measured["own_second_order"], measured


# --------------------------------------------------------------------------- #
# Neutrality: the tag changes nothing else.                                    #
# --------------------------------------------------------------------------- #


def _measure_neutrality(
    tmp_path: Path, base: str, tag: Sequence[str]
) -> Dict[str, Any]:
    """Draw the sample untagged and tagged, in separate processes, and compare.

    Per size in ``NEUTRAL_SIZES``: the glyph runs (family per run, glyph indexes,
    positions), the pixels of a ``QTextLayout`` drawn into an image and of a
    ``QLabel``, the family of each probe, and the font metrics. Returns, per
    size, the first difference found (None when identical).
    """

    def run(label: str, applied: Sequence[str]) -> Dict[str, Any]:
        steps = [
            _step(
                f"s{px}",
                ["N", "Fa"],
                px,
                tag=applied,
                want=_NEUTRAL_WANT,
                text=SAMPLE,
            )
            for px in NEUTRAL_SIZES
        ]
        return _spawn_tail(
            f"tag-neutrality-{base}-{'+'.join(tag) or 'none'}-{label}",
            tmp_path / label,
            base,
            steps,
        )

    plain = run("plain", [])
    tagged = run("tagged", tag)
    differences: Dict[int, Optional[str]] = {}
    for px in NEUTRAL_SIZES:
        left = dict(plain["steps"][f"s{px}"])
        right = dict(tagged["steps"][f"s{px}"])
        for key in ("tag",):
            left.pop(key, None)
            right.pop(key, None)
        differences[px] = _first_difference(left, right)
    print(
        f"[tag-neutrality] {_OS_NAME} base={base} tag={list(tag)}: first difference "
        f"per size {differences}"
    )
    return {"differences": differences, "plain": plain, "tagged": tagged}


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("flag", TAG_CANDIDATES)
def test_chain_tag_flag_changes_neither_rendering_nor_metrics(tmp_path, flag, base):
    """Neutrality: a list tagged with ``flag`` renders and measures as the untagged one.

    The same list and the same sample (Latin, Han, Hangul, kana, punctuation and a
    space) at 12 px, at a size that is not a multiple of the em, and at the guide's
    largest heading size, each untagged and tagged in a process of its own. Glyph
    runs, rendered pixels (a layout and a label) and the metrics must be
    identical, or the flag is dropped on this operating system.
    """
    measured = _measure_neutrality(tmp_path, base, [flag])
    for px, difference in measured["differences"].items():
        assert difference is None, (
            f"flag {flag} is not neutral in the {base} base at {px} px on "
            f"{_OS_NAME}: first difference {difference}. The flag is dropped on "
            "this operating system."
        )


def test_chain_tag_probe_fails_for_a_tag_that_changes_rendering(tmp_path):
    """Instrument proof: the antialiasing flag used as the tag must fail neutrality.

    The sabotaged copy applies ``NoAntialias`` as the tag on the platform default
    base. Where the untagged text has gray (antialiased) pixels at all, the tagged
    text must differ, or the neutrality cases could not see a flag that changes
    rendering. Where there is no antialiased text offscreen, the case prints that.
    """
    measured = _measure_neutrality(tmp_path, "default", ["NoAntialias"])
    gray = {
        px: measured["plain"]["steps"][f"s{px}"]["pixels"]["gray"]
        for px in NEUTRAL_SIZES
    }
    if not any(gray.values()):
        print(
            f"[tag-neutrality] no antialiased text is drawn offscreen on "
            f"{_OS_NAME}: the antialiasing control is not observable"
        )
        return
    for px, count in gray.items():
        if count:
            assert measured["differences"][px] is not None, (
                f"the neutrality probe saw no difference at {px} px on {_OS_NAME} "
                f"although the untagged text has {count} antialiased pixels and "
                "the tag turns antialiasing off: it cannot see a non-neutral flag"
            )
    print(f"[tag-neutrality] antialiasing control: gray pixels untagged {gray}")


# --------------------------------------------------------------------------- #
# The untagged competitor.                                                     #
# --------------------------------------------------------------------------- #


#: The one-family fonts drawn first, and the chain drawn after each. ``set-*`` put a
#: one-entry list on the font with ``setFamilies``; ``base-plain`` is the base font
#: exactly as the application builds it (the interface font, or the platform
#: default), whose family list is empty.
COMPETITORS: Tuple[str, ...] = ("set-latin-only", "set-nifen", "base-plain")
#: Where, measured on Windows, a one-family font drawn AFTER an untagged chain with
#: the same first family draws Han from the chain's tail. It is not so for the
#: Latin-only face, nor for the platform default (which the offscreen platform
#: cannot resolve); a font drawn BEFORE the chain never takes the chain's tail.
INHERITS_ON_WINDOWS = {
    ("set-nifen", "nifen"),
    ("set-nifen", "default"),
    ("base-plain", "nifen"),
}


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("kind", COMPETITORS)
def test_chain_tag_untagged_single_family_font_and_a_chain_in_both_orders(
    tmp_path, kind, base
):
    """A one-family font and a chain behind the same first family, in both orders.

    The font drawn first, then the chain untagged (the order in which the chain
    could be left with an empty tail), and the chain drawn first, then the
    font. Both results are printed for every operating system and base, and the
    second is asserted where it was measured. The tail is a face registered
    alone, with its OS/2 range bits cleared, so a font with no family list cannot
    reach it by the platform's fallback and only a family list can deliver it.
    The chain with each candidate flag must draw its Han from ``Fq`` after the
    one-family font; and a one-family font drawn after tagged chains must not
    inherit their tail. The one-family font is the Latin-only face, then Nifen
    Art, both set through ``setFamilies``, and then the base font as the
    application builds it, with no family list at all.
    """
    if kind == "set-latin-only":
        alone: Optional[List[str]] = ["L"]
        chain = ["L", "N", "Fq"]
    elif kind == "set-nifen":
        alone = ["N"]
        chain = ["N", "Fq"]
    else:
        alone = None
        chain = ["P", "Fq"] if base == "nifen" else ["P", "N", "Fq"]
    tagged = [_step(f"tag-{flag}", chain, 12, tag=[flag]) for flag in TAG_CANDIDATES]
    forward = _spawn_tail(
        f"tag-competitor-{kind}-{base}-font-first",
        tmp_path / "font-first",
        base,
        [_step("alone", alone, 12), _step("untagged", chain, 12), *tagged],
        quiet=True,
    )
    chain_first = _spawn_tail(
        f"tag-competitor-{kind}-{base}-chain-first",
        tmp_path / "chain-first",
        base,
        [_step("chain", chain, 12), _step("alone-after", alone, 12)],
        quiet=True,
    )
    tagged_first = _spawn_tail(
        f"tag-competitor-{kind}-{base}-tagged-chain-first",
        tmp_path / "tagged-first",
        base,
        [*tagged, _step("alone-after", alone, 12)],
        quiet=True,
    )
    fa = forward["names"]["Fq"]
    forward_han = _han_by(forward, "untagged")
    inherited = _han_by(chain_first, "alone-after")
    after_tagged = _han_by(tagged_first, "alone-after")
    print(
        f"[tag-competitor] {_OS_NAME} base={base}: {kind} {alone} drawn first, then "
        f"{chain} untagged drew U+5B57 from {forward_han!r}; the chain lost its "
        f"tail: {forward_han != fa}"
    )
    print(
        f"[tag-competitor] {_OS_NAME} base={base}: {chain} drawn first, then {kind} "
        f"{alone} drew U+5B57 from {inherited!r}; the font inherited the chain's "
        f"tail: {inherited == fa}"
    )
    print(
        f"[tag-competitor] {_OS_NAME} base={base}: the tagged chains first, then "
        f"{kind} {alone} drew U+5B57 from {after_tagged!r}"
    )
    for flag in TAG_CANDIDATES:
        drew = _han_by(forward, f"tag-{flag}")
        print(f"[tag-competitor] {_OS_NAME} base={base}: tagged {flag}: {drew!r}")
        assert drew == fa, (
            f"flag {flag}: the chain {chain} tagged drew U+5B57 from {drew!r}, not "
            f"from {fa!r}, after an untagged {kind} font on {_OS_NAME}"
        )
    assert after_tagged != fa, (
        f"a {kind} font drawn after the tagged chains inherited their tail "
        f"({after_tagged!r}) on {_OS_NAME}: the tag does not keep a chain apart "
        "from a font the application does not chain"
    )
    if sys.platform == "win32" and (kind, base) in INHERITS_ON_WINDOWS:
        assert inherited == fa, (
            f"On Windows a {kind} font drawn after an untagged chain used to draw "
            f"Han from the chain's face and now draws it from {inherited!r}: "
            "re-measure before relying on either."
        )


# --------------------------------------------------------------------------- #
# The verdict: which flags are kept, and what they buy.                        #
# --------------------------------------------------------------------------- #


def _combinations(flags: Sequence[str]) -> List[Tuple[str, ...]]:
    """Return every non-empty combination of ``flags``, smallest first."""
    return [
        combo
        for size in range(1, len(flags) + 1)
        for combo in itertools.combinations(flags, size)
    ]


def _measure_table(tmp_path: Path, base: str, kept: Sequence[str]) -> Dict[str, Any]:
    """Draw one list per non-empty combination of ``kept`` behind one first family.

    All in one process, each with a tail of its own (a different registered
    face), so each must draw its Han from its own face. Also reports whether
    ``QFont.__eq__`` and ``QFont.key()`` tell the first two variants apart.
    """
    combos = _combinations(kept)
    steps: List[Dict[str, Any]] = [
        _step(f"table-{index}", ["N", _table_token(index)], 12, tag=combo)
        for index, combo in enumerate(combos)
    ]
    if len(combos) >= 2:
        steps.append(
            {
                "id": "variants",
                "op": "fontkey",
                "px": 12,
                "a": {"chain": ["N", "Fa"], "tag": list(combos[0])},
                "b": {"chain": ["N", "Fa"], "tag": list(combos[1])},
            }
        )
    result = _spawn_tail(
        f"tag-table-{base}", tmp_path, base, steps, table_size=len(combos)
    )
    drawn = {
        combo: _han_by(result, f"table-{index}") for index, combo in enumerate(combos)
    }
    expected = {
        combo: result["names"][_table_token(index)]
        for index, combo in enumerate(combos)
    }
    wrong = {c: (drawn[c], expected[c]) for c in combos if drawn[c] != expected[c]}
    print(
        f"[tag-table] {_OS_NAME} base={base}: {len(combos)} combinations of "
        f"{list(kept)}, each behind Nifen Art with a tail of its own; "
        f"{len(combos) - len(wrong)} drew from their own tail, wrong: {wrong}"
    )
    if "variants" in result["steps"]:
        row = result["steps"]["variants"]
        print(
            f"[tag-table] {_OS_NAME} base={base}: QFont == for two tagged variants "
            f"{row['eq']}, key() equal {row['key_eq']} (information)"
        )
    return {"combos": combos, "wrong": wrong}


def test_chain_tag_at_least_two_flags_are_kept_on_every_operating_system(tmp_path):
    """The verdict: a flag is kept if it separates AND is neutral, in both bases.

    Every candidate is measured in both bases; the kept ones are printed with
    their reasons, and at least two must be kept (the intersection across the
    three operating systems is what the application may use). The non-empty
    combinations of the kept flags are then drawn as separate lists behind one
    first family, in one process, and each must draw its own tail.
    """
    kept: List[str] = []
    rows: List[str] = []
    for flag in TAG_CANDIDATES:
        reasons: List[str] = []
        for base in BASES:
            separation = _measure_separation(
                tmp_path / f"{flag}-{base}-sep", base, flag
            )
            neutrality = _measure_neutrality(
                tmp_path / f"{flag}-{base}-neu", base, [flag]
            )
            if separation["verdict"] == "not separated":
                reasons.append(f"{base}: does not separate")
            elif separation["verdict"] == "not observable":
                reasons.append(f"{base}: separation not observable")
            first = next(
                (f"{px} px {d}" for px, d in neutrality["differences"].items() if d),
                None,
            )
            if first:
                reasons.append(f"{base}: not neutral ({first})")
        ok = not any("does not separate" in r or "not neutral" in r for r in reasons)
        rows.append(
            f"{flag}: {'KEPT' if ok else 'DROPPED'}"
            + (f" ({'; '.join(reasons)})" if reasons else "")
        )
        if ok:
            kept.append(flag)
    for row in rows:
        print(f"[tag-verdict] {_OS_NAME}: {row}")
    print(
        f"[tag-verdict] {_OS_NAME}: kept flags {kept}; capacity "
        f"{len(_combinations(kept))} lists behind one first family"
    )
    assert len(kept) >= 2, (
        f"fewer than two flags are kept on {_OS_NAME}: {kept}. The chain tag cannot "
        "hold today's two Han forms and one more; this goes back to the architect, "
        "who re-plans the family chain (the order is never changed by an agent)."
    )
    for base in BASES:
        table = _measure_table(tmp_path / f"table-{base}", base, kept)
        assert not table["wrong"], (
            f"on {_OS_NAME} in the {base} base these combinations of the kept flags "
            f"did not draw from their own tail: {table['wrong']}"
        )
