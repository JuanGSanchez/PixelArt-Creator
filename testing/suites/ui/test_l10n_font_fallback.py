"""Fallback outside Nifen Art, and the Han forms, measured on real fonts and widgets.

``REQ-L10N-UI-011`` (a character Nifen Art lacks is drawn from another font, never
as a box) and ``REQ-L10N-UI-012`` (a Han character takes the form of the active
language, and each endonym label keeps its own language's form). The scenarios
proven here are SC-L10N-UI-011-1 to -4 and SC-L10N-UI-012-1 and -2, with the cache
cases that make them hold when several fonts share one process.

How the cases are built (and why):

* **One subprocess per case.** Qt's font cache does not tell two fonts apart by the
  families after the first, so a case that needs a clean cache runs in a fresh
  interpreter. The cases that put several fonts in one process on purpose (both
  endonym labels, a live language switch, a one-family font drawn after the chains)
  say so, and each has a control built from the product's own ``chain_font`` with
  the tag disabled.
* **The child imports this module** and calls :func:`child_main`, so the code that
  runs in the child is ordinary, linted module code and not a string.
* **Every family a verdict depends on is registered by the case.** The bundled
  faces are registered as the application registers them. "A Han-free platform
  family" and "a Han-capable platform family" are generated stand-ins (fontTools,
  plain boxes, nothing copied from any font), set as the platform's default font
  before the application captures it. The named system fonts' files, registered by
  path, are extra cases only. Every case first runs a positive control: a character
  the first family lacks must be drawn by the next registered family, or the case
  fails and names the plugin.
* **Every check that names the family that drew a character keys it by the
  character** (a one-character layout). The run order of a multi-run layout differs
  between processes on identical input and is never read.
* **Every face is registered before the first drawing** and nothing is registered
  or removed between two drawings, because a registration clears Qt's font cache.
* **The operating-system fallback clauses** (SC-L10N-UI-011-1 to -4, past the end of
  the list) are asserted on Linux, where offscreen reaches fontconfig and the probe
  font is installed. On Windows and macOS offscreen they are printed as not
  observable and are not claimed as passed; what holds on every OS (Nifen Art draws
  the Latin letters, the inactive form family is never used) is asserted on every OS.
* Coverage questions pass an integer code point. Every print is ASCII.

Run ``pytest -rP`` to read every measurement.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

import pytest
from fontTools.ttLib import TTFont
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QImage,
    QPainter,
    QRawFont,
    QTextLayout,
)
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic import constants as logic_constants
from pixelart_creator.logic import font_chain, language_names
from pixelart_creator.ui import app_font
from pixelart_creator.ui.i18n import LanguageManager
from testing.suites.ui.test_font_family_chain_mechanism import (
    FACES,
    N_TILDE,
    Face,
    build_face,
)

_MODULE = "testing.suites.ui.test_l10n_font_fallback"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FONT_DIR = _REPO_ROOT / "pixelart_creator" / "fonts"
_MEASURED = _REPO_ROOT / "fonts-src" / "nifen-art-cjk" / "coverage" / "measured-set.txt"
_I18N_DIR = _REPO_ROOT / "pixelart_creator" / "i18n"

#: When set, the children import the product from this root instead of the
#: repository's, so a copy that carries a deliberate defect can be measured.
SUBJECT_ENV = "PIXELART_L10N_SUBJECT_ROOT"

NIFEN = font_chain.NIFEN_ART_FAMILY
CJK_SC = font_chain.CJK_SC_FAMILY
CJK_JP = font_chain.CJK_JP_FAMILY
CJK_KR = font_chain.CJK_HANGUL_FAMILY

IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform == "win32"
OS_NAME = "Windows" if IS_WINDOWS else "macOS" if sys.platform == "darwin" else "Linux"

#: Font cases: (use the platform font, which stand-in is the platform family).
CONDITIONS: Dict[str, Tuple[bool, str]] = {
    "nifen": (False, "free"),
    "system-free": (True, "free"),
    "system-capable": (True, "capable"),
}

_ASCII: Tuple[int, ...] = tuple(range(0x20, 0x7F))
_BITS_LATIN: Tuple[int, ...] = (0,)
_BITS_CJK: Tuple[int, ...] = (28, 48, 56, 59)
_PAGES_LATIN: Tuple[int, ...] = (0,)
_PAGES_CJK: Tuple[int, ...] = (17, 18, 19, 20, 21)

#: Candidate probe characters outside every bundled face: traditional forms and
#: rare Hangul syllables. Those that a bundled face holds are dropped at run time.
_PROBE_CANDIDATES: Tuple[int, ...] = (
    0x5B78,
    0x9AD4,
    0x570B,
    0x8AAA,
    0x7063,
    0x9B31,
    0x7C60,
    0x9EA4,
    0xBDC1,
    0xB620,
)

_PRELUDE = (
    "import importlib, json, sys\n"
    "spec = json.load(open(sys.argv[1], encoding='utf-8'))\n"
    "sys.path[:0] = spec['paths']\n"
    "importlib.import_module(spec['module']).child_main(spec)\n"
)


def ascii_safe(text: object) -> str:
    """Return ``text`` with every non-ASCII character escaped (prints stay ASCII)."""
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def cp_name(code_point: int) -> str:
    """Return ``U+XXXX`` for a code point."""
    return "U+%04X" % code_point


def family_ok(drawn: str, family: str) -> bool:
    """Return whether ``drawn`` names ``family`` (either weight)."""
    return drawn == family or drawn == family + " Bold"


def subject_root() -> Path:
    """Return the root the children import the product from."""
    override = os.environ.get(SUBJECT_ENV, "")
    return Path(override) if override else _REPO_ROOT


@pytest.fixture(autouse=True)
def theme() -> str:
    """Replace the suite's two-way theme fixture: no case here depends on a theme.

    Which family draws a character cannot change with the style sheet, so running
    each case twice would only repeat every subprocess.
    """
    return "none"


# --------------------------------------------------------------------------- #
# Parent side: the measured set, the languages, the instrument faces           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CjkSets:
    """The Han and Hangul characters the shipped text uses, per form set."""

    jp: FrozenSet[int]
    sc: FrozenSet[int]
    kr: FrozenSet[int]
    header_shared: int

    @property
    def shared(self) -> FrozenSet[int]:
        """The Han characters held in both form sets."""
        return self.jp & self.sc

    @property
    def jp_only(self) -> FrozenSet[int]:
        """The Han characters only the Japanese-form set holds."""
        return self.jp - self.sc

    @property
    def sc_only(self) -> FrozenSet[int]:
        """The Han characters only the Simplified-form set holds."""
        return self.sc - self.jp


def read_measured(path: Path = _MEASURED) -> CjkSets:
    """Read the measured set the way the font lint reads it (``<set>: <chars>``)."""
    text = path.read_bytes().decode("utf-8")
    sets: Dict[str, FrozenSet[int]] = {}
    header_shared = -1
    for line in text.splitlines():
        if line.startswith("#"):
            found = re.search(r"in both jp and sc (\d+)", line)
            if found:
                header_shared = int(found.group(1))
            continue
        label, separator, rest = line.partition(":")
        if separator and label in ("jp", "sc", "kr"):
            sets[label] = frozenset(ord(char) for char in rest.strip())
    return CjkSets(sets["jp"], sets["sc"], sets["kr"], header_shared)


def discover_languages() -> Tuple[str, ...]:
    """Return the language codes of the compiled catalogue sources."""
    codes = sorted(path.stem[len("pixelart_") :] for path in _I18N_DIR.glob("*.ts"))
    return tuple(codes)


LANGUAGES = discover_languages()


def _cmap(file_name: str) -> Dict[int, str]:
    """Return the code point -> glyph name map of a bundled face."""
    font = TTFont(str(_FONT_DIR / file_name), lazy=True)
    try:
        table = font.getBestCmap()
        assert table, f"{file_name} has no Unicode character map"
        return dict(table)
    finally:
        font.close()


def build_instrument_faces(folder: Path) -> Dict[str, Tuple[str, str]]:
    """Generate the stand-in faces under ``folder``; return token -> (path, family).

    ``L`` is Latin only (the control's first family). ``PL`` is a Han-free platform
    family. ``PH`` is a Han-capable platform family holding every Han and Hangul
    character the shipped text uses, with a taller line box than Nifen Art's.
    """
    sets = read_measured()
    cjk = tuple(sorted(sets.jp | sets.sc | sets.kr))
    faces = {
        "L": FACES["L"],
        "PL": Face("Probe Platform Latin", _ASCII, 13, 3, _BITS_LATIN, _PAGES_LATIN),
        "PH": Face(
            "Probe Platform Han",
            _ASCII + cjk,
            13,
            3,
            _BITS_LATIN + _BITS_CJK,
            _PAGES_LATIN + _PAGES_CJK,
        ),
    }
    built: Dict[str, Tuple[str, str]] = {}
    for token, face in faces.items():
        path = build_face(face, folder / f"{token}.ttf")
        built[token] = (str(path), face.family)
    return built


@pytest.fixture(scope="session")
def instrument_faces(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    """The generated stand-in faces, built once per process."""
    return dict(build_instrument_faces(tmp_path_factory.mktemp("l10n-faces")))


def probe_characters() -> List[int]:
    """Return the probe characters: candidates no bundled face holds."""
    sets = read_measured()
    held = sets.jp | sets.sc | sets.kr
    nifen = set(_cmap("NifenArt-Regular.ttf"))
    return [cp for cp in _PROBE_CANDIDATES if cp not in held and cp not in nifen]


def run_case(
    name: str,
    tmp_path: Path,
    faces: Dict[str, Any],
    kind: str,
    *,
    module: str = _MODULE,
    environment: str = "native",
    **spec: Any,
) -> Dict[str, Any]:
    """Run one case in a fresh interpreter; return what it measured.

    Prints every line the child measured. The positive control is asserted first,
    so no verdict is read from a plugin that cannot tell registered families apart.
    """
    profile = tmp_path / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    root = subject_root()
    paths = [str(root)] + ([str(_REPO_ROOT)] if root != _REPO_ROOT else [])
    full = dict(spec)
    full.update(
        kind=kind,
        module=module,
        faces=faces,
        profile=str(profile),
        paths=paths,
        environment=environment,
    )
    spec_file = tmp_path / "spec.json"
    spec_file.write_bytes(json.dumps(full).encode("utf-8"))
    env = dict(os.environ)
    env.update(
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
    )
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    if environment == "hidden":
        env["FONTCONFIG_FILE"] = str(_write_hidden_fontconfig(tmp_path))
    done = subprocess.run(
        [sys.executable, "-B", "-c", _PRELUDE, str(spec_file)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    assert done.returncode == 0, (
        f"{name}: the child exited {done.returncode}\n"
        f"{ascii_safe(done.stdout)}\n{ascii_safe(done.stderr)}"
    )
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, f"{name}: the child printed no RESULT line\n{ascii_safe(done.stderr)}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    for line in result.get("info", []):
        print(f"[{name}] [{OS_NAME}] {ascii_safe(line)}")
    assert not result["errors"], f"{name}: setup errors {ascii_safe(result['errors'])}"
    assert result["nifen_registered"], f"{name}: Nifen Art did not register"
    control = result["control"]
    assert control["ok"], (
        f"{name}: the positive control FAILED on the {result['plugin']!r} plugin "
        f"({OS_NAME}): U+{control['cp']:04X} in {control['chain']} was drawn by "
        f"{control['drew']!r}, not by the next registered family "
        f"{control['expected']!r}. This plugin cannot tell registered families "
        "apart, so no verdict below can be read from it."
    )
    return result


def _write_hidden_fontconfig(folder: Path) -> Path:
    """Write a fontconfig file that sees no system font at all (Linux cases).

    The only directory it lists is empty, so no system CJK font (nor any other
    system font) is visible; the case checks that it really is hidden.
    """
    empty = folder / "no-system-fonts"
    empty.mkdir(parents=True, exist_ok=True)
    cache = folder / "fontconfig-cache"
    cache.mkdir(parents=True, exist_ok=True)
    text = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        f"<fontconfig>\n<dir>{empty}</dir>\n<cachedir>{cache}</cachedir>\n"
        "</fontconfig>\n"
    )
    path = folder / "fonts.conf"
    path.write_bytes(text.encode("utf-8"))
    return path


# --------------------------------------------------------------------------- #
# Child side: the boot, the probes, the runners                                #
# --------------------------------------------------------------------------- #


@dataclass
class Booted:
    """What a child set up before its runner starts."""

    app: QApplication
    names: Dict[str, str]
    lines: List[str]
    errors: List[str]
    control: Dict[str, Any]
    nifen_registered: bool
    keep: List[Any]

    def say(self, text: str) -> None:
        """Record one line for the parent to print."""
        self.lines.append(ascii_safe(text))

    def base(self) -> Dict[str, Any]:
        """Return the fields every result carries."""
        return {
            "plugin": QGuiApplication.platformName(),
            "control": self.control,
            "errors": self.errors,
            "nifen_registered": self.nifen_registered,
            "names": self.names,
            "info": self.lines,
        }


def draw_one(font: QFont, code_point: int) -> Tuple[str, bool]:
    """Return (family, missing-glyph) for one character laid out alone in ``font``."""
    layout = QTextLayout(chr(code_point), font)
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(100000)
    layout.endLayout()
    runs = layout.glyphRuns()
    if not runs:
        return "", True
    glyphs = [int(glyph) for glyph in runs[0].glyphIndexes()]
    return str(runs[0].rawFont().familyName()), 0 in glyphs


def make_font(families: Sequence[str]) -> QFont:
    """Build a plain font of the interface's size and strategy (a control font)."""
    font = QFont(families[0])
    font.setFamilies(list(families))
    font.setPixelSize(app_font.NIFEN_ART_EM_PX)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def pixel_hash(font: QFont, code_point: int) -> str:
    """Return a short digest of the pixels ``font`` draws for one character."""
    image = QImage(24, 24, QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(QColor(0, 0, 0))
    painter.drawText(2, 18, chr(code_point))
    painter.end()
    return hashlib.sha256(bytes(image.constBits())).hexdigest()[:16]


def is_han(code_point: int) -> bool:
    """Return whether ``code_point`` lies in the product's Han ranges."""
    ranges = logic_constants.HAN_RANGES
    return any(first <= code_point <= last for first, last in ranges)


class _NoTags:
    """A registry that gives every list the untagged class (the control)."""

    def tag_for(self, families: Sequence[str]) -> Optional[int]:
        """Return no tag, whatever the list."""
        return None


def disable_chain_tags() -> None:
    """Make ``chain_font`` tag nothing: the control the cache cases are read against."""
    setattr(app_font, "_CHAIN_TAG_REGISTRY", _NoTags())


def register_font_file(path: str) -> List[str]:
    """Register a font file with Qt; return its families ([] when Qt refuses it)."""
    font_id = QFontDatabase.addApplicationFont(path)
    return QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []


def boot(spec: Dict[str, Any]) -> Booted:
    """Isolate the settings, register every face, set the platform, run the control."""
    from testing.suites.ui import conftest as ui_conftest

    profile = Path(spec["profile"])
    ui_conftest.redirect_settings_store(profile / "qsettings")
    config = profile / "appconfig"
    config.mkdir(parents=True, exist_ok=True)
    setattr(
        QStandardPaths,
        "writableLocation",
        staticmethod(lambda *_args, **_kwargs: str(config)),
    )
    app = QApplication([])
    booted = Booted(app, {}, [], [], {}, False, [])
    booted.say(
        "plugin %s; Qt %s; Python %s"
        % (QGuiApplication.platformName(), _qt_version(), sys.version.split()[0])
    )
    # Only what the case needs is registered: the Han-capable stand-in would otherwise
    # be a font the database could offer as a fallback in a case that has no business
    # with it.
    needed = {"L", "PL"} | ({"PH"} if spec.get("platform") == "capable" else set())
    for token, entry in spec["faces"].items():
        if token not in needed:
            continue
        path, expected = entry
        families = register_font_file(path)
        if expected not in families:
            booted.errors.append(f"{token}: wanted {expected!r}, Qt gave {families!r}")
        booted.names[token] = expected
    for path in spec.get("system_files", []):
        families = register_font_file(path)
        booted.say("registered %s: families %r" % (path, families))
        booted.names["file:" + path] = ",".join(families)
    booted.nifen_registered = bool(app_font.register_app_fonts())
    platform = spec.get("platform", "none")
    platform_family = ""
    if platform in ("free", "capable"):
        platform_family = booted.names["PL" if platform == "free" else "PH"]
    elif platform.startswith("file:"):
        platform_family = spec["platform_family"]
    if platform_family:
        app.setFont(QFont(platform_family, 9))
    app_font.capture_platform_font()
    from pixelart_creator.ui.theme import apply_font_fallbacks

    apply_font_fallbacks()
    app_font.install_font_substitutions()
    booted.say("platform family: %r (%s)" % (platform_family, platform))
    chain = [booted.names["L"], NIFEN]
    drew, _missing = draw_one(make_font(chain), N_TILDE)
    booted.control = {
        "ok": drew == NIFEN,
        "drew": drew,
        "expected": NIFEN,
        "chain": chain,
        "cp": N_TILDE,
    }
    booted.say(
        "positive control: %s drawn by %r (expected %r) -> %s"
        % (cp_name(N_TILDE), drew, NIFEN, "ok" if drew == NIFEN else "FAILED")
    )
    return booted


def _qt_version() -> str:
    """Return the Qt runtime version."""
    from PySide6.QtCore import qVersion

    return str(qVersion())


def system_families(booted: Booted) -> List[str]:
    """Return the font families the database holds besides the registered ones."""
    own = set(booted.names.values()) | {NIFEN, CJK_SC, CJK_JP, CJK_KR}
    return sorted(f for f in QFontDatabase.families() if f not in own)


def probe_holders(booted: Booted, probes: Sequence[int]) -> List[str]:
    """Return the system families that hold every probe character."""
    holders: List[str] = []
    for family in system_families(booted):
        face = QFont(family)
        face.setPixelSize(app_font.NIFEN_ART_EM_PX)
        raw = QRawFont.fromFont(face)
        if raw.isValid() and raw.familyName() == family:
            if all(raw.supportsCharacter(cp) for cp in probes):
                holders.append(family)
    return holders


def plant_use_system_font(value: bool) -> None:
    """Store the "Use system font" choice in the (isolated) settings."""
    from pixelart_creator.ui import appearance_settings

    current = appearance_settings.load_appearance()
    appearance_settings.save_appearance(replace(current, use_system_font=value))


def open_window(system: bool, no_tag: bool = False) -> Any:
    """Build the main window with the font mode stored first, as a start-up does."""
    if no_tag:
        disable_chain_tags()
    plant_use_system_font(system)
    from pixelart_creator.ui.main_window import Main_Window

    window = Main_Window()
    window.resize(1200, 800)
    QApplication.processEvents()
    return window


def close_window(window: Any) -> None:
    """Drain the window's off-thread work so nothing survives into process exit."""
    window.shutdown_prewarm()


def switch_language(window: Any, code: str) -> None:
    """Make ``code`` the active language through the window's own manager."""
    if code == "en" and window._language_manager.current_language() == "en":
        return
    if not window._language_manager.set_language(code):
        raise RuntimeError(f"no catalogue for {code!r}")
    QApplication.processEvents()


def start_language(booted: Booted, code: str) -> LanguageManager:
    """Register a language manager and activate ``code`` (no main window)."""
    manager = LanguageManager(booted.app)
    booted.keep.append(manager)
    if not manager.set_language(code):
        raise RuntimeError(f"no catalogue for {code!r}")
    return manager


def draw_all(font: QFont, code_points: Sequence[int]) -> Dict[int, Tuple[str, bool]]:
    """Draw each character alone in ``font``; return code point -> (family, box)."""
    return {cp: draw_one(font, cp) for cp in code_points}


def summarise(
    drawn: Dict[int, Tuple[str, bool]], expected: str, other: str
) -> Dict[str, Any]:
    """Count what drew the characters: right family, wrong ones, the other form."""
    wrong = [
        [cp, fam, missing]
        for cp, (fam, missing) in drawn.items()
        if missing or not family_ok(fam, expected)
    ]
    used_other = [cp for cp, (fam, _m) in drawn.items() if family_ok(fam, other)]
    families = Counter(fam for fam, _m in drawn.values())
    return {
        "examined": len(drawn),
        "wrong_count": len(wrong),
        "wrong": wrong[:8],
        "other_count": len(used_other),
        "other": used_other[:8],
        "families": dict(families),
    }


def run_control_blind(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw with an unregistered next family: the control must report it unseen."""
    chain = [booted.names["L"], "Probe Never Registered"]
    drew, _missing = draw_one(make_font(chain), N_TILDE)
    booted.say("blind control: %r drew %s" % (drew, cp_name(N_TILDE)))
    return {"drew": drew, "reported_seen": drew == "Probe Never Registered"}


def run_labels(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw the selector's two Han labels through the real entries' fonts."""
    window: Any = open_window(bool(spec["system"]), bool(spec.get("no_tag")))
    try:
        switch_language(window, spec["language"])
        entries = dict(window._language_entry_actions)
        order = ["zh_CN", "ja"] if spec["order"] == "sc-first" else ["ja", "zh_CN"]
        labels: Dict[str, Any] = {}
        for code in order:
            action = entries[code]
            font = QFont(action.font())
            han = [ord(ch) for ch in action.text() if is_han(ord(ch))]
            drawn = draw_all(font, han)
            labels[code] = {
                "han": [[cp, fam, box] for cp, (fam, box) in drawn.items()],
                "chain": list(font.families()),
            }
            booted.say(
                "label %s: chain %r, Han drawn by %r"
                % (code, list(font.families()), sorted({f for f, _b in drawn.values()}))
            )
        return {"labels": labels, "order": order}
    finally:
        close_window(window)


def run_labels_platform_first(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Control: the platform-first order with a Han-capable platform family.

    The two labels' Han are drawn with a font built here, the platform family first
    and the bundled faces behind it. If the platform family draws them, the probe
    can see the defect that the product's order avoids.
    """
    platform = booted.names["PH"]
    labels: Dict[str, Any] = {}
    for code, form in (("zh_CN", CJK_SC), ("ja", CJK_JP)):
        font = make_font([platform, NIFEN, form, CJK_KR])
        han = [ord(ch) for ch in language_names.ENDONYMS[code] if is_han(ord(ch))]
        drawn = draw_all(font, han)
        labels[code] = {"han": [[cp, fam, box] for cp, (fam, box) in drawn.items()]}
        booted.say(
            "platform-first %s: Han drawn by %r"
            % (code, sorted({f for f, _b in drawn.values()}))
        )
    return {"labels": labels, "platform": platform}


def run_shared(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw the shared Han characters in every role under one active language."""
    from pixelart_creator.ui.user_guide import User_Guide_Dialog

    language = spec["language"]
    system = bool(spec["system"])
    start_language(booted, language)
    if spec.get("no_tag"):
        disable_chain_tags()
    app_font.prepare_interface_font(booted.app, system)
    expected = CJK_JP if language == "ja" else CJK_SC
    other = CJK_SC if expected == CJK_JP else CJK_JP
    roles: Dict[str, QFont] = {"ui": QFont(booted.app.font())}
    bold = QFont(booted.app.font())
    bold.setBold(True)
    roles["ui_bold"] = bold
    dialogs: List[Any] = []
    for label, pixel in (("guide_default", False), ("guide_pixel", True)):
        if pixel and system:
            continue
        dialog: Any = User_Guide_Dialog(
            locale_provider=lambda: language,
            guide_pixel_font=pixel,
            use_system_font=system,
        )
        dialogs.append(dialog)
        roles[label] = QFont(dialog._content_view.document().defaultFont())
    shared = list(spec["shared"])
    inactive = list(spec["inactive"])
    out: Dict[str, Any] = {}
    for role, font in roles.items():
        mine = summarise(draw_all(font, shared), expected, other)
        theirs = summarise(draw_all(font, inactive), expected, other)
        out[role] = {
            "shared": mine,
            "inactive": {
                "examined": theirs["examined"],
                "used_inactive": theirs["other_count"],
                "used_inactive_cps": theirs["other"],
                "families": theirs["families"],
            },
            "chain": list(font.families()),
        }
        booted.say(
            "%s: chain %r; shared %d, wrong %d, by %r; inactive-only %d, drawn by "
            "the inactive form %d"
            % (
                role,
                list(font.families()),
                mine["examined"],
                mine["wrong_count"],
                mine["families"],
                theirs["examined"],
                theirs["other_count"],
            )
        )
    return {"roles": out, "expected": expected}


def run_switch(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw the shared characters, switch language on the same window, draw again."""
    window: Any = open_window(bool(spec["system"]), bool(spec.get("no_tag")))
    try:
        shared = list(spec["shared"])
        out: Dict[str, Any] = {}
        for stage, code in (("before", spec["first"]), ("after", spec["second"])):
            switch_language(window, code)
            font = QFont(QApplication.font())
            expected = CJK_JP if code == "ja" else CJK_SC
            other = CJK_SC if expected == CJK_JP else CJK_JP
            summary = summarise(draw_all(font, shared), expected, other)
            summary["chain"] = list(font.families())
            summary["expected"] = expected
            out[stage] = summary
            booted.say(
                "%s (%s): chain %r; %d shared, %d wrong, by %r"
                % (
                    stage,
                    code,
                    list(font.families()),
                    summary["examined"],
                    summary["wrong_count"],
                    summary["families"],
                )
            )
        return out
    finally:
        close_window(window)


#: The kinds of one-family font drawn after the chains. ``plain`` is a font that
#: carries no family list (the captured platform default, or the interface font's
#: base); ``listed`` carries a one-entry list; ``nifen-listed`` is ``[Nifen Art]``
#: built in the test, drawn even when the platform font is the base.
ONE_FAMILY_KINDS: Dict[bool, Tuple[str, ...]] = {
    False: ("plain", "listed"),
    True: ("plain", "listed", "nifen-listed"),
}


def build_one_family(system: bool, kind: str) -> QFont:
    """Build a one-family font of ``kind`` for the font mode (see the kinds above)."""
    if system and kind != "nifen-listed":
        font = app_font.platform_default_font()
    else:
        font = QFont(NIFEN)
        font.setPixelSize(app_font.NIFEN_ART_EM_PX)
        font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if kind != "plain":
        font.setFamilies([font.family()])
    return font


def draw_kinds(booted: Booted, system: bool, shared: Sequence[int], when: str) -> Any:
    """Draw every kind of one-family font with the shared characters."""
    drawn: Dict[str, Dict[str, List[str]]] = {}
    for kind in ONE_FAMILY_KINDS[system]:
        one = build_one_family(system, kind)
        drawn[kind] = draw_with_pixels(one, shared)
        booted.say(
            "one-family font %s %r %s: %d characters, drawn by %r"
            % (
                kind,
                list(one.families()) or [one.family()],
                when,
                len(drawn[kind]),
                sorted({row[0] for row in drawn[kind].values()}),
            )
        )
    return drawn


def draw_with_pixels(font: QFont, code_points: Sequence[int]) -> Dict[str, List[str]]:
    """Return code point (text) -> [family, box flag, pixel digest]."""
    out: Dict[str, List[str]] = {}
    for cp in code_points:
        family, box = draw_one(font, cp)
        out[str(cp)] = [family, str(box), pixel_hash(font, cp)]
    return out


def run_mirror(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw the product's chains for both forms, then a one-family font."""
    system = bool(spec["system"])
    window: Any = open_window(system, bool(spec.get("no_tag")))
    try:
        active = "zh_CN" if spec["order"] == "sc-first" else "ja"
        switch_language(window, active)
        shared = list(spec["shared"])
        entries = dict(window._language_entry_actions)
        fonts = [QFont(QApplication.font())]
        for code in [active] + [c for c in ("zh_CN", "ja") if c != active]:
            fonts.append(QFont(entries[code].font()))
        for font in fonts:
            draw_all(font, shared)
        return {"drawn": draw_kinds(booted, system, shared, "after the chains")}
    finally:
        close_window(window)


def run_mirror_fresh(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Draw the one-family fonts alone, in a fresh process with the same faces."""
    system = bool(spec["system"])
    return {"drawn": draw_kinds(booted, system, list(spec["shared"]), "fresh")}


def run_layer_names(booted: Booted, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Type layer names, show them in the Layers panel, read what draws each char."""
    window: Any = open_window(False)
    try:
        switch_language(window, spec["language"])
        document = window.active_document()
        probes = list(spec.get("probes", []))
        out: List[Dict[str, Any]] = []
        for name in spec["names"]:
            document.frames[0].layers[0].name = name
            window._layer_panel.rebuild()
            QApplication.processEvents()
            label = window._layer_panel._rows[0]._name
            font = QFont(label.font())
            text = str(label.text())
            chars = [[ord(ch), *draw_one(font, ord(ch))] for ch in text]
            out.append(
                {
                    "chars": chars,
                    "text_ok": text == name,
                    "chain": list(font.families()),
                }
            )
            booted.say(
                "layer name with %d characters; row font chain %r"
                % (len(text), list(font.families()))
            )
        return {
            "entries": out,
            "probe_holders": probe_holders(booted, probes) if probes else [],
            "system_families": system_families(booted),
        }
    finally:
        close_window(window)


RUNNERS: Dict[str, Callable[[Booted, Dict[str, Any]], Dict[str, Any]]] = {
    "control_blind": run_control_blind,
    "labels": run_labels,
    "labels_platform_first": run_labels_platform_first,
    "shared": run_shared,
    "switch": run_switch,
    "mirror": run_mirror,
    "mirror_fresh": run_mirror_fresh,
    "layer_names": run_layer_names,
}


def child_main(spec: Dict[str, Any]) -> None:
    """Entry of a child interpreter: run the case and print one RESULT line."""
    booted = boot(spec)
    result = RUNNERS[spec["kind"]](booted, spec)
    payload = dict(booted.base())
    payload.update(result)
    print("RESULT " + json.dumps(payload), flush=True)


# --------------------------------------------------------------------------- #
# The instrument checks, in the parent                                         #
# --------------------------------------------------------------------------- #


def test_the_eight_languages_are_discovered():
    """The cases below run once per compiled catalogue source, and there are eight."""
    print(f"[languages] {len(LANGUAGES)} catalogue sources: {list(LANGUAGES)}")
    assert len(LANGUAGES) == 8, LANGUAGES
    assert set(LANGUAGES) == set(language_names.ENDONYMS), LANGUAGES


def test_the_measured_set_is_what_the_shipped_faces_hold():
    """The faces hold the characters the measured set lists, each form its own.

    The shared count is the font lint's own: the characters in both the Japanese-form
    and the Simplified-form list. It is printed, it is non-zero, and it equals the
    count the measured file records. A Han character only one form set lists is not
    held by the other form's face (each set holds only its own language's characters).
    """
    sets = read_measured()
    jp = set(_cmap("NifenArtCJKJP-Regular.ttf"))
    sc = set(_cmap("NifenArtCJKSC-Regular.ttf"))
    kr = set(_cmap("NifenArtCJKKR-Regular.ttf"))
    print(
        f"[measured] jp {len(sets.jp)}, sc {len(sets.sc)}, kr {len(sets.kr)}; "
        f"shared {len(sets.shared)}, jp only {len(sets.jp_only)}, "
        f"sc only {len(sets.sc_only)}; the file records shared "
        f"{sets.header_shared}"
    )
    assert len(sets.shared) > 0
    assert len(sets.shared) == sets.header_shared
    assert sets.jp <= jp, sorted(sets.jp - jp)[:5]
    assert sets.sc <= sc, sorted(sets.sc - sc)[:5]
    assert sets.kr <= kr, sorted(sets.kr - kr)[:5]
    assert not (sets.jp_only & sc), sorted(sets.jp_only & sc)[:5]
    assert not (sets.sc_only & jp), sorted(sets.sc_only & jp)[:5]
    assert len(sets.jp_only) > 0 and len(sets.sc_only) > 0


def test_the_pixel_identical_shared_pairs_are_listed_as_information():
    """List the shared characters whose two drawings are pixel-identical (info only).

    The count and the code points are printed and fail nothing: the rule is that each
    drawing is its form set's own, by identity, not that the two differ.
    """
    sets = read_measured()
    faces: Dict[str, Tuple[Any, Any, Any]] = {}
    for form in ("JP", "SC"):
        font = TTFont(str(_FONT_DIR / f"NifenArtCJK{form}-Regular.ttf"), lazy=True)
        faces[form] = (font, font.getBestCmap(), font["glyf"])
    identical: List[int] = []
    try:
        for cp in sorted(sets.shared):
            shapes = []
            for form in ("JP", "SC"):
                _font, cmap, glyf = faces[form]
                coords, ends, _flags = glyf[cmap[cp]].getCoordinates(glyf)
                shapes.append((list(coords), list(ends)))
            if shapes[0] == shapes[1]:
                identical.append(cp)
    finally:
        for font, _cmap_, _glyf in faces.values():
            font.close()
    print(
        f"[identical] {len(sets.shared)} shared characters, {len(identical)} with "
        f"two identical drawings (information): "
        f"{', '.join(cp_name(cp) for cp in identical[:40])}"
    )
    assert len(sets.shared) > 0


def test_the_instrument_faces_hold_what_they_claim(instrument_faces):
    """The stand-in faces are what the cases assume: contents and the Han ranges."""
    sets = read_measured()
    han = sets.jp | sets.sc | sets.kr
    held: Dict[str, set] = {}
    for token, (path, family) in instrument_faces.items():
        font = TTFont(path, lazy=True)
        try:
            held[token] = set(font.getBestCmap())
            names = {rec.toUnicode() for rec in font["name"].names if rec.nameID == 1}
        finally:
            font.close()
        assert names == {family}, (token, names)
    print(
        f"[faces] PL holds {len(held['PL'])} code points (no Han: "
        f"{not (held['PL'] & han)}); PH holds {len(held['PH'])}, every shipped Han "
        f"and Hangul character: {han <= held['PH']}"
    )
    assert not (held["PL"] & han)
    assert han <= held["PH"]
    assert N_TILDE not in held["L"]


def test_the_probe_characters_are_outside_every_bundled_face():
    """No bundled face holds a probe character, so only a fallback font draws it."""
    probes = probe_characters()
    print(f"[probe] {len(probes)} probe characters: {[cp_name(cp) for cp in probes]}")
    assert len(probes) >= 6, probes


def test_the_positive_control_fails_when_the_next_family_cannot_be_seen(
    tmp_path, instrument_faces
):
    """Control of the control: an unregistered next family must not be reported seen.

    If this passed vacuously, the positive control of every case could not tell a
    working plugin from a blind one.
    """
    result = run_case("control-can-fail", tmp_path, instrument_faces, "control_blind")
    assert result["reported_seen"] is False, result


# --------------------------------------------------------------------------- #
# SC-L10N-UI-012-2: each endonym label in its own form                          #
# --------------------------------------------------------------------------- #


def check_labels(name: str, result: Dict[str, Any]) -> None:
    """Assert every Han of each label came from its own form family, 7 in all."""
    sc = result["labels"]["zh_CN"]["han"]
    jp = result["labels"]["ja"]["han"]
    print(
        f"[{name}] Han characters examined: {len(sc) + len(jp)} "
        f"(Simplified label {len(sc)}, Japanese label {len(jp)}); "
        f"drawn by {sorted({row[1] for row in sc + jp})}"
    )
    assert len(sc) + len(jp) == 7, (len(sc), len(jp))
    for cp, family, box in sc:
        assert family_ok(family, CJK_SC) and not box, (
            f"{name}: {cp_name(cp)} of the Simplified label was drawn by "
            f"{ascii_safe(family)!r} (box {box}), not by {CJK_SC!r}"
        )
    for cp, family, box in jp:
        assert family_ok(family, CJK_JP) and not box, (
            f"{name}: {cp_name(cp)} of the Japanese label was drawn by "
            f"{ascii_safe(family)!r} (box {box}), not by {CJK_JP!r}"
        )


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_sc_l10n_ui_012_2_each_endonym_label_is_drawn_in_its_own_forms(
    tmp_path, instrument_faces, language, condition
):
    """SC-L10N-UI-012-2: both labels, in one process, from their own form family.

    The Simplified label is drawn first and the Japanese label second, through the
    real selector entries' fonts, under each of the eight active languages, in the
    Nifen Art mode and with "Use system font" on for a Han-free and for a Han-capable
    platform family. No Han character comes from a fallback or platform font.
    """
    system, platform = CONDITIONS[condition]
    result = run_case(
        f"012-2 {condition} {language}",
        tmp_path,
        instrument_faces,
        "labels",
        language=language,
        system=system,
        platform=platform,
        order="sc-first",
    )
    check_labels(f"012-2 {condition} {language}", result)


@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_sc_l10n_ui_012_2_the_reverse_order_draws_the_same_forms(
    tmp_path, instrument_faces, condition
):
    """SC-L10N-UI-012-2: the Japanese label first, then the Simplified one.

    A second process with the two labels drawn in the reverse order, in each font case.
    """
    system, platform = CONDITIONS[condition]
    result = run_case(
        f"012-2 reverse {condition}",
        tmp_path,
        instrument_faces,
        "labels",
        language="en",
        system=system,
        platform=platform,
        order="jp-first",
    )
    assert result["order"] == ["ja", "zh_CN"]
    check_labels(f"012-2 reverse {condition}", result)


@pytest.mark.parametrize("order", ["sc-first", "jp-first"])
@pytest.mark.parametrize("condition", ["nifen", "system-free"])
def test_sc_l10n_ui_012_2_control_untagged_lists_hand_the_first_tail_to_the_second(
    tmp_path, instrument_faces, condition, order
):
    """Control: with the tag disabled the second label draws from the first's family.

    The same lists, rebuilt with the product's ``chain_font`` and its tag disabled,
    in the same order. Where Qt's cache is known to share a tail (Windows), the
    second label's Han comes from the FIRST form's family, which is what shows the
    case above would see the defect. Elsewhere this is printed, not passed.
    """
    system, platform = CONDITIONS[condition]
    result = run_case(
        f"012-2 control {condition} {order}",
        tmp_path,
        instrument_faces,
        "labels",
        language="en",
        system=system,
        platform=platform,
        order=order,
        no_tag=True,
    )
    first, second = result["order"]
    forms = {"zh_CN": CJK_SC, "ja": CJK_JP}
    rows = result["labels"][second]["han"]
    from_first = [row[0] for row in rows if family_ok(row[1], forms[first])]
    from_own = [row[0] for row in rows if family_ok(row[1], forms[second])]
    print(
        f"[012-2 control {condition} {order}] second label ({second}): "
        f"{len(from_first)} Han drawn by the first form's family, {len(from_own)} by "
        f"its own, of {len(rows)}"
    )
    if IS_WINDOWS:
        assert from_first, (
            "the untagged lists did not share a tail on Windows, where sharing was "
            "measured: the cache case has no control that could fail"
        )
    else:
        print(
            f"[012-2 control] sharing is not asserted on {OS_NAME}: observed "
            f"{len(from_first)} from the first family (information)"
        )


def test_sc_l10n_ui_012_2_control_the_platform_first_order_draws_han_from_the_platform(
    tmp_path, instrument_faces
):
    """Control: a platform-first font with a Han-capable family draws the Han itself.

    A font built in the test with the platform family first must draw the labels' Han
    from the platform family. That proves the probe would see the defect that the
    product's CJK-first order for such a family avoids.
    """
    result = run_case(
        "012-2 platform-first control",
        tmp_path,
        instrument_faces,
        "labels_platform_first",
        platform="capable",
    )
    rows = result["labels"]["zh_CN"]["han"] + result["labels"]["ja"]["han"]
    print(
        f"[012-2 platform-first control] {len(rows)} Han examined, drawn by "
        f"{sorted({row[1] for row in rows})}"
    )
    assert len(rows) == 7
    for cp, family, _box in rows:
        assert family == result["platform"], (
            f"the platform-first font drew {cp_name(cp)} with {ascii_safe(family)!r}, "
            f"not with the Han-capable platform family {result['platform']!r}: the "
            "probe cannot see the defect"
        )


# --------------------------------------------------------------------------- #
# SC-L10N-UI-012-1: the shared characters follow the active language           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("condition", list(CONDITIONS))
def test_sc_l10n_ui_012_1_shared_han_take_the_form_of_the_active_language(
    tmp_path, instrument_faces, language, condition
):
    """SC-L10N-UI-012-1: every shared character, from the active form's family.

    Japanese active draws each shared character from Nifen Art CJK JP, Simplified
    Chinese from Nifen Art CJK SC, and any other language from the Simplified form
    (the system language is pinned to English), keyed by the character and never by
    pixels. Held in every role (UI text, Bold, the guide page) and in every font case,
    with "Use system font" on for a Han-free and for a Han-capable platform family. A
    Han character only the inactive form set holds is never drawn by that set's family.
    """
    system, platform = CONDITIONS[condition]
    sets = read_measured()
    shared = sorted(sets.shared)
    inactive = sorted(sets.sc_only if language == "ja" else sets.jp_only)
    name = f"012-1 {condition} {language}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "shared",
        language=language,
        system=system,
        platform=platform,
        shared=shared,
        inactive=inactive,
    )
    print(
        f"[{name}] shared characters {len(shared)} (the lint's count "
        f"{sets.header_shared}); inactive-only characters {len(inactive)}; "
        f"expected family {result['expected']!r}"
    )
    assert len(shared) > 0 and len(shared) == sets.header_shared
    assert set(result["roles"]) >= {"ui", "ui_bold", "guide_default"}
    for role, data in result["roles"].items():
        mine = data["shared"]
        assert mine["examined"] == len(shared), (role, mine)
        assert mine["wrong_count"] == 0, (
            f"{name}, role {role}: {mine['wrong_count']} of {mine['examined']} shared "
            f"characters were not drawn by {result['expected']!r}: "
            f"{ascii_safe(mine['wrong'])}; families {ascii_safe(mine['families'])}"
        )
        theirs = data["inactive"]
        assert theirs["used_inactive"] == 0, (
            f"{name}, role {role}: the inactive form family drew "
            f"{theirs['used_inactive']} characters only it's set holds: "
            f"{ascii_safe(theirs['used_inactive_cps'])}"
        )


@pytest.mark.parametrize("condition", ["nifen", "system-free"])
@pytest.mark.parametrize("pair", [("ja", "zh_CN"), ("zh_CN", "ja")])
def test_sc_l10n_ui_012_1_a_live_switch_draws_the_new_form(
    tmp_path, instrument_faces, pair, condition
):
    """SC-L10N-UI-012-1: the same window, switched from one form to the other.

    With the first language active the shared characters are drawn; the language is
    switched on the same window and they are drawn again. The second drawing comes
    from the new form's family for every shared character, by the family that drew
    it, keyed by the character. The reverse switch runs in a second process.
    """
    first, second = pair
    system, platform = CONDITIONS[condition]
    shared = sorted(read_measured().shared)
    name = f"012-1 switch {first}->{second} {condition}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "switch",
        first=first,
        second=second,
        system=system,
        platform=platform,
        shared=shared,
    )
    for stage in ("before", "after"):
        data = result[stage]
        assert data["examined"] == len(shared) > 0
        assert data["wrong_count"] == 0, (
            f"{name}, {stage}: {data['wrong_count']} of {data['examined']} shared "
            f"characters were not drawn by {data['expected']!r}: "
            f"{ascii_safe(data['wrong'])}; families {ascii_safe(data['families'])}"
        )


@pytest.mark.parametrize("condition", ["nifen", "system-free"])
@pytest.mark.parametrize("pair", [("ja", "zh_CN"), ("zh_CN", "ja")])
def test_sc_l10n_ui_012_1_control_untagged_lists_keep_the_first_form_after_a_switch(
    tmp_path, instrument_faces, pair, condition
):
    """Control: with the tag disabled the post-switch drawing keeps the first form.

    The same lists rebuilt with the product's ``chain_font`` and its tag disabled, on
    the same window, in the same order. Where Qt's cache is known to share a tail
    (Windows), the drawing after the switch comes from the FIRST form's family, which
    shows the live-switch case would see the defect. Elsewhere this is printed.
    """
    first, second = pair
    system, platform = CONDITIONS[condition]
    shared = sorted(read_measured().shared)
    name = f"012-1 switch control {first}->{second} {condition}"
    result = run_case(
        name,
        tmp_path,
        instrument_faces,
        "switch",
        first=first,
        second=second,
        system=system,
        platform=platform,
        shared=shared,
        no_tag=True,
    )
    after = result["after"]
    forms = {"zh_CN": CJK_SC, "ja": CJK_JP}
    from_first = sum(
        count
        for family, count in after["families"].items()
        if family_ok(family, forms[first])
    )
    print(
        f"[{name}] after the switch: {from_first} of {after['examined']} shared "
        f"characters still drawn by the first form's family {forms[first]!r}; "
        f"families {ascii_safe(after['families'])}"
    )
    if IS_WINDOWS:
        assert from_first == after["examined"], (
            "the untagged lists did not keep the first form after the switch on "
            "Windows, where sharing was measured: the live-switch case has no "
            "control that could fail"
        )
    else:
        print(f"[012-1 control] sharing is not asserted on {OS_NAME} (information)")


# --------------------------------------------------------------------------- #
# The one-family font drawn after the chains                                   #
# --------------------------------------------------------------------------- #

_FRESH: Dict[str, Dict[str, Any]] = {}

#: The kind of chain each font case draws first, for the mirror cases: the product's
#: chains start with Nifen Art in the Nifen Art mode and with the platform's default
#: family under "Use system font".
CHAIN_KINDS: Dict[str, str] = {
    "nifen": "Nifen Art",
    "system-free": "the platform default family",
}

#: The cells (operating system, kind of chain) where an earlier measurement found Qt's
#: cache handing the tail of one chain to a later one-family font. It was measured on
#: Windows, behind chains that start with Nifen Art, with a one-family ``[Nifen Art]``
#: font that carries a family list and with the interface font as built. Behind chains
#: that start with the platform default family it was found in no cell on any system
#: measured. A later measurement that finds it in another cell adds that cell here,
#: and the control of that cell then fails until it is observable.
MEASURED_INHERITANCE: FrozenSet[Tuple[str, str]] = frozenset({("Windows", "Nifen Art")})


Drawings = Dict[str, Dict[str, List[str]]]


def fresh_drawing(tmp_path: Path, faces: Dict[str, Any], condition: str) -> Drawings:
    """Return each one-family font's drawing in a fresh process (cached per mode)."""
    if condition not in _FRESH:
        system, platform = CONDITIONS[condition]
        shared = sorted(read_measured().shared)
        _FRESH[condition] = run_case(
            f"mirror fresh {condition}",
            tmp_path,
            faces,
            "mirror_fresh",
            system=system,
            platform=platform,
            shared=shared,
        )
    drawn: Drawings = _FRESH[condition]["drawn"]
    return drawn


def mirror_drawing(
    tmp_path: Path,
    faces: Dict[str, Any],
    condition: str,
    order: str,
    no_tag: bool,
) -> Drawings:
    """Return each one-family font's drawing after the chains of both forms."""
    system, platform = CONDITIONS[condition]
    shared = sorted(read_measured().shared)
    result = run_case(
        f"mirror {'control ' if no_tag else ''}{condition} {order}",
        tmp_path,
        faces,
        "mirror",
        system=system,
        platform=platform,
        shared=shared,
        order=order,
        no_tag=no_tag,
    )
    drawn: Drawings = result["drawn"]
    return drawn


def differing(after: Dict[str, List[str]], fresh: Dict[str, List[str]]) -> List[str]:
    """Return the characters whose family or pixels differ between two drawings."""
    return sorted(key for key in fresh if after.get(key) != fresh[key])


@pytest.mark.parametrize("order", ["sc-first", "jp-first"])
@pytest.mark.parametrize("condition", ["nifen", "system-free"])
def test_sc_l10n_ui_012_1_a_one_family_font_after_the_chains_equals_a_fresh_one(
    tmp_path, instrument_faces, condition, order
):
    """A one-family font drawn after the product's chains draws as it does alone.

    The product's chains for both forms are drawn through the real fonts (the UI font
    and the two selector entries), then a one-family font is drawn with the shared Han
    characters: ``[Nifen Art]`` in the Nifen Art mode, the captured platform default
    with "Use system font" on, each as a font with no family list and as a font with a
    one-entry list. Its drawing must equal the same font's drawing in a fresh process
    with the same faces registered: the family that drew each character, then the
    pixels. The criterion is not "not from a CJK face", because with the real faces
    registered a one-family font may reach one through the platform's fallback.
    """
    fresh = fresh_drawing(tmp_path / "fresh", instrument_faces, condition)
    after = mirror_drawing(
        tmp_path / "after", instrument_faces, condition, order, False
    )
    cell = (OS_NAME, CHAIN_KINDS[condition])
    if cell not in MEASURED_INHERITANCE:
        print(
            f"[mirror {condition} {order}] printed, not claimed: on {cell[0]} the "
            f"control for a chain that starts with {cell[1]} prints 'control not "
            "observable', so this comparison cannot be shown to see the hazard here"
        )
    assert set(after) == set(fresh) and len(fresh) >= 2, (sorted(after), sorted(fresh))
    for kind, reference in fresh.items():
        differs = differing(after[kind], reference)
        print(
            f"[mirror {condition} {order} {kind}] {len(reference)} characters "
            f"compared with the fresh drawing; {len(differs)} differ; fresh drawn by "
            f"{sorted({row[0] for row in reference.values()})}"
        )
        assert len(reference) > 0
        assert not differs, (
            f"the {kind} one-family font drew differently after the chains for "
            f"{len(differs)} characters, first {ascii_safe(differs[:5])}: after "
            f"{ascii_safe([after[kind].get(k) for k in differs[:2]])}, fresh "
            f"{ascii_safe([reference[k] for k in differs[:2]])}"
        )


@pytest.mark.parametrize("condition", ["nifen", "system-free"])
def test_sc_l10n_ui_012_1_control_untagged_chains_change_a_later_one_family_font(
    tmp_path, instrument_faces, condition
):
    """Control: the same chains with the tag disabled change the later one-family font.

    In every cell where Qt's cache was measured to hand an earlier chain's tail to a
    later one-family font (see ``MEASURED_INHERITANCE``: the operating system and the
    kind of chain), a one-family font's drawing must differ from the fresh drawing in
    at least one of the two build orders. If every order and kind draws the same, the
    case reports "control not observable" and fails there. In every other cell it
    prints that, and does not fail.
    """
    fresh = fresh_drawing(tmp_path / "fresh", instrument_faces, condition)
    differs: Dict[str, int] = {}
    for order in ("sc-first", "jp-first"):
        after = mirror_drawing(
            tmp_path / order, instrument_faces, condition, order, True
        )
        for kind, reference in fresh.items():
            differs[f"{order} {kind}"] = len(differing(after[kind], reference))
    print(
        f"[mirror control {condition}] characters differing from the fresh drawing, "
        f"of {len(next(iter(fresh.values())))}: {differs}"
    )
    observable = any(differs.values())
    cell = (OS_NAME, CHAIN_KINDS[condition])
    if cell in MEASURED_INHERITANCE:
        assert observable, (
            "control not observable: both build orders drew the one-family font as a "
            f"fresh process does, though the chains were untagged ({cell[0]}, a chain "
            f"that starts with {cell[1]})"
        )
    elif observable:
        print(
            f"[mirror control {condition}] observable on {cell[0]} although no "
            f"inheritance was measured for a chain that starts with {cell[1]}: add "
            "that cell to MEASURED_INHERITANCE"
        )
    else:
        print(
            f"[mirror control {condition}] control not observable on {cell[0]} for a "
            f"chain that starts with {cell[1]}: no inheritance was measured there, so "
            "the case prints and does not fail"
        )


# --------------------------------------------------------------------------- #
# SC-L10N-UI-011-1 to -4: the layer name in the Layers panel                    #
# --------------------------------------------------------------------------- #

_PREFIX = "Capa "


def name_with(code_points: Sequence[int]) -> str:
    """Return a layer name: Latin letters, then the characters."""
    return _PREFIX + "".join(chr(cp) for cp in code_points)


def fallback_rows(entry: Dict[str, Any]) -> Tuple[List[Any], List[Any]]:
    """Split a name's per-character rows into the Latin prefix and the rest."""
    chars = entry["chars"]
    return chars[: len(_PREFIX)], chars[len(_PREFIX) :]


def drawn_names(rows: Sequence[Any]) -> List[str]:
    """Return the sorted families that drew ``rows`` (each [cp, family, box])."""
    return sorted({ascii_safe(row[1]) for row in rows})


def test_sc_l10n_ui_011_3_the_linux_fallback_check_refuses_to_run_blind(
    tmp_path, instrument_faces
):
    """SC-L10N-UI-011-3: the probe font is asserted present first, never skipped.

    On Linux a system font covering every probe character must be installed, and the
    test fails (it does not skip) when it is absent. The number of probe characters
    examined is printed and is non-zero. On Windows and macOS offscreen the operating
    system's fallback is not observable, which is printed and not claimed as passed.
    """
    probes = probe_characters()
    result = run_case(
        "011-3",
        tmp_path,
        instrument_faces,
        "layer_names",
        language="en",
        names=[name_with(probes)],
        probes=probes,
    )
    holders = result["probe_holders"]
    print(
        f"[011-3] {len(probes)} probe characters examined; system families holding "
        f"every one: {ascii_safe(holders)}"
    )
    assert len(probes) > 0
    if IS_LINUX:
        assert holders, (
            "no installed font covers every probe character "
            f"({[cp_name(cp) for cp in probes]}): the fallback path cannot be "
            "exercised on this runner, which is a failure and never a skip"
        )
    else:
        print(
            f"[011-3] not observable on {OS_NAME} offscreen: the operating system's "
            "fallback is asserted on Linux, with the probe font"
        )


def test_sc_l10n_ui_011_1_a_layer_name_outside_the_cjk_set_shows_no_box(
    tmp_path, instrument_faces
):
    """SC-L10N-UI-011-1: characters outside Nifen Art's CJK set, in the Layers panel.

    On Linux every probe character is drawn from a fallback font and none is a
    missing-glyph box. On Windows and macOS offscreen the fallback is not observable;
    the boxes seen there are printed and not claimed as passed.
    """
    probes = probe_characters()
    result = run_case(
        "011-1",
        tmp_path,
        instrument_faces,
        "layer_names",
        language="en",
        names=[name_with(probes)],
    )
    entry = result["entries"][0]
    assert entry["text_ok"], "the layer row did not show the typed name"
    _prefix, rest = fallback_rows(entry)
    boxes = [row for row in rest if row[2]]
    print(
        f"[011-1] {len(rest)} characters outside the CJK set examined; "
        f"{len(boxes)} drawn as a box; drawn by {drawn_names(rest)}"
    )
    assert len(rest) == len(probes) > 0
    if IS_LINUX:
        assert not boxes, (
            f"missing-glyph boxes for {[cp_name(row[0]) for row in boxes]}: no "
            "fallback font drew them"
        )
    else:
        print(f"[011-1] the fallback is not observable on {OS_NAME} offscreen")


def test_sc_l10n_ui_011_2_the_fallback_is_per_character(tmp_path, instrument_faces):
    """SC-L10N-UI-011-2: Latin letters in Nifen Art, only the missing character apart.

    A layer name that mixes Latin letters with one character Nifen Art lacks, drawn
    with Nifen Art active. The letters are drawn by Nifen Art on every operating
    system. The one character is not drawn by Nifen Art; on Linux it is drawn by a
    fallback font with no box (not observable on Windows and macOS offscreen).
    """
    probes = probe_characters()
    result = run_case(
        "011-2",
        tmp_path,
        instrument_faces,
        "layer_names",
        language="en",
        names=[name_with(probes[:1])],
    )
    entry = result["entries"][0]
    prefix, rest = fallback_rows(entry)
    letters = [row for row in prefix if chr(row[0]).isalpha()]
    print(
        f"[011-2] letters drawn by {drawn_names(letters)}; the foreign character "
        f"{cp_name(rest[0][0])} drawn by {drawn_names(rest)} (box {rest[0][2]})"
    )
    assert len(letters) == 4
    for cp, family, box in letters:
        assert family == NIFEN and not box, (cp_name(cp), ascii_safe(family), box)
    assert len(rest) == 1
    cp, family, box = rest[0]
    assert family != NIFEN or box, "Nifen Art drew a character it does not hold"
    if IS_LINUX:
        assert (
            family != NIFEN and not box
        ), f"{cp_name(cp)} was not drawn by a fallback font: {ascii_safe(family)!r}"
    else:
        print(f"[011-2] the fallback is not observable on {OS_NAME} offscreen")


def test_sc_l10n_ui_011_4_a_japanese_only_character_falls_back_under_chinese(
    tmp_path, instrument_faces
):
    """SC-L10N-UI-011-4: a Han character only the Japanese set holds, under zh_CN.

    Simplified Chinese is active. A layer name carries one Han character that the
    Japanese-form set holds and the Simplified-form set does not. It is never drawn
    with the Japanese-form glyph (not by Nifen Art CJK JP), on every operating system,
    and the other characters stay in Nifen Art. On Linux it is drawn from a fallback
    font with no box; that clause is not observable on Windows and macOS offscreen.
    """
    only = sorted(read_measured().jp_only)
    sample = [only[0], only[len(only) // 3], only[2 * len(only) // 3], only[-1]]
    result = run_case(
        "011-4",
        tmp_path,
        instrument_faces,
        "layer_names",
        language="zh_CN",
        names=[name_with([cp]) for cp in sample],
    )
    for cp, entry in zip(sample, result["entries"]):
        prefix, rest = fallback_rows(entry)
        letters = [row for row in prefix if chr(row[0]).isalpha()]
        _cp, family, box = rest[0]
        print(
            f"[011-4] {cp_name(cp)} under zh_CN drawn by {ascii_safe(family)!r} "
            f"(box {box}); letters by {drawn_names(letters)}"
        )
        assert not family_ok(family, CJK_JP), (
            f"{cp_name(cp)} was drawn with the Japanese-form glyph under Simplified "
            "Chinese"
        )
        for lcp, lfamily, lbox in letters:
            assert lfamily == NIFEN and not lbox, (cp_name(lcp), lfamily)
        if IS_LINUX:
            assert not box and not family_ok(family, NIFEN), (
                f"{cp_name(cp)} was not drawn by a fallback font: "
                f"{ascii_safe(family)!r}"
            )
    if not IS_LINUX:
        print(f"[011-4] the fallback clause is not observable on {OS_NAME} offscreen")


def test_sc_l10n_ui_011_4_the_simplified_only_character_never_takes_the_japanese_form(
    tmp_path, instrument_faces
):
    """The mirror of -4: a Simplified-only Han character, with Japanese active.

    It is never drawn by Nifen Art CJK SC, on every operating system.
    """
    only = sorted(read_measured().sc_only)
    sample = [only[0], only[len(only) // 2], only[-1]]
    result = run_case(
        "011-4 mirror",
        tmp_path,
        instrument_faces,
        "layer_names",
        language="ja",
        names=[name_with([cp]) for cp in sample],
    )
    for cp, entry in zip(sample, result["entries"]):
        _prefix, rest = fallback_rows(entry)
        family = rest[0][1]
        print(f"[011-4 mirror] {cp_name(cp)} under ja drawn by {ascii_safe(family)!r}")
        assert not family_ok(
            family, CJK_SC
        ), f"{cp_name(cp)} was drawn with the Simplified-form glyph under Japanese"


# --------------------------------------------------------------------------- #
# Extra cases: the operating system's own Han-capable fonts, registered by path  #
# --------------------------------------------------------------------------- #


def find_system_font(file_name: str) -> str:
    """Return the path of a font file in the platform's font folders, or ``""``.

    The folders are the ones Qt reports for the platform; nothing machine-specific is
    named here.
    """
    location = QStandardPaths.StandardLocation.FontsLocation
    for folder_name in QStandardPaths.standardLocations(location):
        folder = Path(folder_name)
        if not folder.is_dir():
            continue
        if (folder / file_name).is_file():
            return str(folder / file_name)
        found = next(folder.rglob(file_name), None)
        if found is not None:
            return str(found)
    return ""


def named_system_fonts() -> List[Tuple[str, str]]:
    """Return (file, expected family) for each named system font found here."""
    wanted: List[Tuple[str, str]] = []
    if IS_WINDOWS:
        wanted = [
            ("malgun.ttf", "Malgun Gothic"),
            ("msyh.ttc", "Microsoft YaHei UI"),
            ("YuGothR.ttc", "Yu Gothic UI"),
        ]
    elif sys.platform == "darwin":
        hiragino = "ヒラギノ角ゴシック W3.ttc"
        wanted = [("PingFang.ttc", "PingFang SC"), (hiragino, "Hiragino Sans")]
    else:
        wanted = [("NotoSansCJK-Regular.ttc", "Noto Sans CJK JP")]
    found = [(find_system_font(name), family) for name, family in wanted]
    return [(path, family) for path, family in found if path]


@pytest.mark.parametrize("found", named_system_fonts() or [("", "")])
def test_extra_a_named_system_han_font_as_the_platform_family(
    tmp_path, instrument_faces, found
):
    """Extra: the labels' forms with a real system font as the platform family.

    The font's file is registered by path and made the platform family, with "Use
    system font" on. The names found are printed. This is an extra case beside the
    stand-ins, never the only evidence; when no named font is present here it prints
    that and runs nothing.
    """
    path, family = found
    if not path:
        print(f"[extra] no named system Han font file found on {OS_NAME}; not run")
        return
    result = run_case(
        f"extra {family}",
        tmp_path,
        instrument_faces,
        "labels",
        language="en",
        system=True,
        platform="file:" + path,
        platform_family=family,
        system_files=[path],
        order="sc-first",
    )
    print(f"[extra] {family}: registered families {ascii_safe(result['names'])}")
    check_labels(f"extra {family}", result)
