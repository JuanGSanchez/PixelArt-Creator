"""Whole-number interface scaling at start-up (REQ-VI-UI-012; ADR-0072).

The stored "Pixel-perfect interface" preference (on by default) chooses Qt's high-DPI
scale-factor rounding policy, and Qt reads that policy only when the application
object is created. A policy is therefore fixed for the life of a process, so every
start-up behaviour is exercised in a **child process** that builds the real application
through ``create_app``; the in-process tests cover only what a running application can
show (the "applies at the next launch" message, and that a second ``create_app`` leaves
the policy alone).

What is covered, by scenario id of the whole-number-scale feature:

* **SC-VI-UI-012-1** at an OS scale of 150 % with the preference on the device-pixel
  ratio is whole (2.0) and the pixels of a framed button hold no interpolated colour;
  the positive control is the same button with the preference off (ratio 1.5), where
  the detector must find interpolated pixels. The call that sets the policy is also
  watched: it happens once, with the right value, while no application exists.
* **SC-VI-UI-012-2** the OS scale 100 / 125 / 150 / 200 % gives a ratio of 1 / 1 / 2 / 2
  with the preference on, and the OS scale itself (1 / 1.25 / 1.5 / 2) with it off; a
  175 % screen and two screens at 100 % and 150 % side by side are covered too.
* **SC-VI-UI-012-3** a first launch with no stored setting has the preference checked
  and Round in force; unchecking shows the "applies the next time the application
  starts" message once, stores the choice, leaves the running scale alone, and a second
  process then starts with the OS scale. An unreadable stored value falls back to on.
* **SC-VI-UI-012-4** the Real-Size Preview shows a document pixel at the same physical
  size with the preference on and off (and at the size the document's own PPI asks).
* **Environment override.** ``QT_SCALE_FACTOR_ROUNDING_POLICY`` beats the setter: the
  variable wins, exactly one line names it when it contradicts the preference, no line
  appears when it agrees or is not a valid policy, and the application never alters it.

How a fractional OS scale is produced headless. The offscreen platform takes a screen
configuration file (``QT_QPA_PLATFORM=offscreen:configfile=<path>``); a screen's
``logicalDpi`` over ``logicalBaseDpi`` 96 feeds Qt's high-DPI scaling exactly as the OS
setting does (144 is 150 %). Its ``dpr`` key is NOT a platform scale and is not used.
The option string is split on ``:``, so the path must hold no colon: the file is
written into the child's working directory and passed by its bare name (a drive letter
would abort the process). ``QT_SCREEN_SCALE_FACTORS`` is the second means, covered
once. ``QT_SCALE_FACTOR`` is not one: it is not rounded (one test records that).

Isolation. Each child redirects ``QSettings`` into ``tmp_path`` with the suite's own
helper, asserts the redirect before any write, and runs with a temporary profile
directory (``APPDATA``, ``HOME``, ...), so no child can read or write a real user's
settings or favourites. A stored value is written with the product's own settings
seam (or, for an unreadable value, with the four-argument ``QSettings`` form it uses).
Nothing here touches a real ``.pixproj``, theme or catalogue.

Both modes. The suite's two-way ``theme`` fixture is replaced inside this module: the
policy and the ratio do not depend on the colour mode, and running every child twice
would only double the time. Every test that LOOKS at something (the message, the
rendered pixels of a framed button) takes the mode explicitly and runs in both.

HONEST LIMITS, stated and not hidden:

* the offscreen platform emulates the OS scale; it is not a display. The real-display
  check at 150 % stays additional evidence and is not replaced by anything here;
* the "interpolated colour" detector counts opaque pixels further than six levels from
  every role colour of the style, because Qt leaves one-level colour offsets at the
  joints of a frame even when it is exact; six levels absorbs those and still sees a
  blend, which the preference-off control proves;
* the Spanish wording of the message is checked through a stand-in translator (it proves
  the text is wrapped for translation, in the right context, and looked up when shown);
  the shipped Spanish catalogue is not checked here because it does not carry the
  message until the catalogues are next regenerated.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest
from PySide6.QtCore import QCoreApplication, Qt, QTranslator
from PySide6.QtGui import QGuiApplication

from pixelart_creator.ui.app import create_app
from pixelart_creator.ui.appearance_settings import (
    ROUNDING_POLICY_ENV,
    apply_stored_rounding_policy,
    default_appearance,
    load_appearance,
    rounding_policy_mismatch,
    save_appearance,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
)
from testing.suites.ui.conftest import assert_settings_isolated

#: The product repository root (``testing/suites/ui/<this file>`` -> four levels).
_REPO_ROOT = Path(__file__).resolve().parents[3]

ROUND = Qt.HighDpiScaleFactorRoundingPolicy.Round.name
PASS_THROUGH = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough.name
FLOOR = Qt.HighDpiScaleFactorRoundingPolicy.Floor.name

#: ``logicalDpi`` over ``logicalBaseDpi`` 96 is the OS scale: 96 -> 100 % ... 192 -> 200 %.
_BASE_DPI = 96
_DPI_100, _DPI_125, _DPI_150, _DPI_175, _DPI_200 = 96, 120, 144, 168, 192

#: The message the user reads after changing the preference (source language).
_NEXT_LAUNCH_MESSAGE = (
    "Pixel-perfect interface: the change applies the next time the application starts."
)
#: The translation context of the window that owns the message.
_MESSAGE_CONTEXT = "Main_Window"

#: A pixel further than this many levels from every role colour is "interpolated".
_PALETTE_TOLERANCE = 6

#: Tolerance on the physical size of a preview pixel (the screen's own size is a
#: rounded whole number of logical pixels, which alone moves the ratio by ~3e-4).
_PHYSICAL_SIZE_REL_TOL = 5e-3
_DOCUMENT_PPI = 96.0
_MM_PER_INCH = 25.4

_CHILD_TIMEOUT_S = 60

#: Variables that would change the scale of a child behind the test's back.
_SCALE_ENV = (
    ROUNDING_POLICY_ENV,
    "QT_SCALE_FACTOR",
    "QT_SCREEN_SCALE_FACTORS",
    "QT_AUTO_SCREEN_SCALE_FACTOR",
    "QT_ENABLE_HIGHDPI_SCALING",
    "QT_FONT_DPI",
)


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture (see the module docstring)."""
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store: Path) -> Path:
    """Fail BEFORE any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)
    return settings_store


# --------------------------------------------------------------------------- #
# The child process                                                           #
# --------------------------------------------------------------------------- #

#: Runs in a fresh interpreter: seed the stored choice, build the application through
#: ``create_app`` (watching the call that sets the policy and the log), then report.
#: argv[1] is one JSON object (see ``_launch``). The last line it prints starts RESULT.
_CHILD = r'''
import json, logging, os, sys
from dataclasses import replace
from pathlib import Path

spec = json.loads(sys.argv[1])

from testing.suites.ui.conftest import assert_settings_isolated, redirect_settings_store

root = Path(spec["root"])
redirect_settings_store(root)
assert_settings_isolated(root)

from PySide6.QtGui import QGuiApplication
from pixelart_creator.ui import appearance_settings as aset
from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.app import create_app

store = spec["store"]
settings = aset.open_settings()
settings.beginGroup(aset.SETTINGS_GROUP)
key_present_before = settings.contains(aset.KEY_PIXEL_PERFECT)
settings.endGroup()
if store["kind"] == "bool" or spec["mode"] is not None:
    chosen = aset.load_appearance()
    if store["kind"] == "bool":
        chosen = replace(chosen, pixel_perfect=store["value"])
    if spec["mode"] is not None:
        chosen = replace(chosen, mode=spec["mode"])
    aset.save_appearance(chosen)
if store["kind"] == "raw":
    settings = aset.open_settings()
    settings.beginGroup(aset.SETTINGS_GROUP)
    settings.setValue(aset.KEY_PIXEL_PERFECT, store["value"])
    settings.sync()

# Watch the one call that sets the policy: its value, and whether an application
# object existed when it was made.
calls = []
original = QGuiApplication.setHighDpiScaleFactorRoundingPolicy


def spy(policy):
    calls.append([policy.name, QGuiApplication.instance() is not None])
    return original(policy)


QGuiApplication.setHighDpiScaleFactorRoundingPolicy = staticmethod(spy)

records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


logging.getLogger().addHandler(Collect())
logging.getLogger().setLevel(logging.INFO)

env_before = os.environ.get(aset.ROUNDING_POLICY_ENV)
app, window = create_app([])
env_after = os.environ.get(aset.ROUNDING_POLICY_ENV)

result = dict(
    calls=calls,
    effective=QGuiApplication.highDpiScaleFactorRoundingPolicy().name,
    dpr=window.devicePixelRatioF(),
    screens=[s.devicePixelRatio() for s in app.screens()],
    art_scale=theme_module.art_scale(),
    pixel_perfect_shown=window.pixel_perfect_interface(),
    key_present_before=key_present_before,
    env_before=env_before,
    env_after=env_after,
    naming_lines=[m for m in records if aset.ROUNDING_POLICY_ENV in m],
    mode=window.current_mode(),
    style=window.current_style(),
)

if spec["uncheck"]:
    window.statusBar().clearMessage()
    window.set_pixel_perfect_interface(False)
    result["message_after_uncheck"] = window.statusBar().currentMessage()
    result["dpr_after_uncheck"] = window.devicePixelRatioF()
    result["effective_after_uncheck"] = (
        QGuiApplication.highDpiScaleFactorRoundingPolicy().name
    )

if spec["probe"]:
    import numpy as np
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QPushButton

    tolerance = spec["tolerance"]
    roles = theme_module.role_map(result["mode"], result["style"])
    palette = np.array(
        [[int(v[i : i + 2], 16) for i in (1, 3, 5)] for v in roles.values() if len(v) == 7],
        dtype=np.int16,
    )

    def interpolated_pixels(screen):
        """Count opaque pixels of a framed, text-free button far from every role colour."""
        button = QPushButton("")
        button.setFixedSize(64, 40)
        button.setScreen(screen)
        geometry = screen.geometry()
        button.move(geometry.x() + 20, geometry.y() + 20)
        button.show()
        app.processEvents()
        app.processEvents()
        image = button.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        raw = np.frombuffer(image.constBits(), dtype=np.uint8, count=image.sizeInBytes())
        rows = raw.reshape(image.height(), image.bytesPerLine())
        data = rows[:, : image.width() * 4].reshape(image.height(), image.width(), 4)
        pixels = data[data[..., 3] > 0][:, :3].astype(np.int16)
        nearest = np.abs(pixels[:, None, :] - palette[None, :, :]).max(axis=2).min(axis=1)
        entry = dict(
            dpr=button.devicePixelRatioF(),
            width=image.width(),
            opaque=int(len(pixels)),
            interpolated=int((nearest > tolerance).sum()),
        )
        button.close()
        return entry

    result["probe"] = [interpolated_pixels(screen) for screen in app.screens()]

if spec["preview"]:
    from PySide6.QtWidgets import QGraphicsScene
    from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window

    preview = Real_Size_Preview_Window(QGraphicsScene(0, 0, 32, 32), spec["document_ppi"])
    preview.show()
    app.processEvents()
    screen = preview.screen()
    dpr = preview.devicePixelRatioF()
    device_dpi = screen.geometry().width() * dpr / (screen.physicalSize().width() / 25.4)
    result["preview"] = dict(
        dpr=dpr,
        scale=preview.current_scale(),
        device_dpi=device_dpi,
        mm_per_document_pixel=preview.current_scale() * dpr / device_dpi * 25.4,
    )
    preview.close()

window.close()
print("RESULT " + json.dumps(result))
'''


@dataclass(frozen=True)
class Child:
    """What one start-up child reported."""

    data: Dict[str, Any]
    stderr: str

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


class _Counter:
    """Gives each child of one test its own working directory."""

    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


_counters: Dict[Path, _Counter] = {}


def _launch(
    tmp_path: Path,
    *,
    stored: Any = None,
    raw: Optional[str] = None,
    mode: Optional[str] = None,
    screens: Optional[Sequence[int]] = (_DPI_100,),
    scale_factors: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    uncheck: bool = False,
    probe: bool = False,
    preview: bool = False,
) -> Child:
    """Start the real application in a fresh process and return what it reported.

    ``stored`` is a bool written through the product's settings seam; ``raw`` is a
    text written to the key as it is (an unreadable value); neither means nothing is
    stored. ``screens`` is the ``logicalDpi`` of each screen (``None``: the plain
    offscreen screen). ``scale_factors`` sets ``QT_SCREEN_SCALE_FACTORS``; ``env``
    adds variables. Settings live under ``tmp_path`` and are SHARED by the children of
    one test (that is what makes a restart a restart); the working directory is not.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    counter = _counters.setdefault(tmp_path, _Counter())
    workdir = tmp_path / f"child{counter.next()}"
    workdir.mkdir()
    profile = tmp_path / "profile"
    profile.mkdir(exist_ok=True)

    child_env = {k: v for k, v in os.environ.items() if k not in _SCALE_ENV}
    child_env.update(
        PYTHONPATH=os.pathsep.join(
            [str(_REPO_ROOT)]
            + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
        ),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HOME=str(profile),
        USERPROFILE=str(profile),
        XDG_CONFIG_HOME=str(profile),
        XDG_DATA_HOME=str(profile),
        QT_QPA_PLATFORM="offscreen",
    )
    if screens is not None:
        config = {
            "windowFrameMargins": False,
            "synchronousWindowSystemEvents": True,
            "screens": [
                {
                    "name": f"screen{i}",
                    "x": i * 800,
                    "y": 0,
                    "width": 800,
                    "height": 600,
                    "logicalDpi": dpi,
                    "logicalBaseDpi": _BASE_DPI,
                }
                for i, dpi in enumerate(screens)
            ],
        }
        (workdir / "screens.json").write_text(json.dumps(config), encoding="utf-8")
        # a bare relative name: the option string is split on ':' (no drive letter)
        child_env["QT_QPA_PLATFORM"] = "offscreen:configfile=screens.json"
    if scale_factors is not None:
        child_env["QT_SCREEN_SCALE_FACTORS"] = scale_factors
    child_env.update(env or {})

    if raw is not None:
        store: Dict[str, Any] = {"kind": "raw", "value": raw}
    elif stored is not None:
        store = {"kind": "bool", "value": bool(stored)}
    else:
        store = {"kind": "none"}
    spec = dict(
        root=str(tmp_path / "qs-root"),
        store=store,
        mode=mode,
        uncheck=uncheck,
        probe=probe,
        tolerance=_PALETTE_TOLERANCE,
        preview=preview,
        document_ppi=_DOCUMENT_PPI,
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", _CHILD, json.dumps(spec)],
        cwd=str(workdir),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
    )
    assert done.returncode == 0, (
        f"the start-up child exited {done.returncode}\n"
        f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    )
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert (
        lines
    ), f"the start-up child printed no result\nstdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    return Child(json.loads(lines[-1][len("RESULT ") :]), done.stderr)


def _settings_file_exists(tmp_path: Path) -> bool:
    return any((tmp_path / "qs-root").rglob("*.ini"))


# --------------------------------------------------------------------------- #
# The preference is read, and the policy is set before the application exists  #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_012_3_first_launch_sets_round_before_the_application_exists(tmp_path):
    """SC-VI-UI-012-3: nothing stored -> the preference reads on and Round is in force.

    The setter is called exactly once, with Round, while NO application object exists
    (the spy records whether one did), and the policy read back from Qt agrees.
    """
    child = _launch(tmp_path)
    assert (
        child["key_present_before"] is False
    ), "the child did not start from a clean store"
    assert child["pixel_perfect_shown"] is True
    assert child["calls"] == [[ROUND, False]]
    assert child["effective"] == ROUND
    assert child["naming_lines"] == []
    # the variable was not set, and the application did not set it
    assert child["env_before"] is None and child["env_after"] is None


@pytest.mark.parametrize("stored, policy", [(True, ROUND), (False, PASS_THROUGH)])
def test_sc_vi_ui_012_1_the_stored_preference_chooses_the_policy(
    tmp_path, stored, policy
):
    """SC-VI-UI-012-1: stored on -> Round, stored off -> PassThrough, set before the app."""
    child = _launch(tmp_path, stored=stored)
    assert child["pixel_perfect_shown"] is stored
    assert child["calls"] == [[policy, False]]
    assert child["effective"] == policy
    assert child["naming_lines"] == []


@pytest.mark.parametrize("unreadable", ["maybe", "", "2", "enabled"])
def test_sc_vi_ui_012_3_an_unreadable_stored_value_falls_back_to_on(
    tmp_path, unreadable
):
    """An unreadable stored value yields the default (on): Round, with the switch checked."""
    child = _launch(tmp_path, raw=unreadable)
    assert child["pixel_perfect_shown"] is True
    assert child["calls"] == [[ROUND, False]]
    assert child["effective"] == ROUND


# --------------------------------------------------------------------------- #
# SC-VI-UI-012-2: the effective ratio at each OS scale                         #
# --------------------------------------------------------------------------- #

#: (logicalDpi, OS scale, ratio with the preference on, ratio with it off)
_OS_SCALES = [
    pytest.param(_DPI_100, 1.0, 1.0, id="100pct"),
    pytest.param(_DPI_125, 1.25, 1.0, id="125pct"),
    pytest.param(_DPI_150, 1.5, 2.0, id="150pct"),
    pytest.param(_DPI_175, 1.75, 2.0, id="175pct"),
    pytest.param(_DPI_200, 2.0, 2.0, id="200pct"),
]


@pytest.mark.parametrize("dpi, os_scale, rounded", _OS_SCALES)
def test_sc_vi_ui_012_2_with_the_preference_on_the_ratio_is_whole(
    tmp_path, dpi, os_scale, rounded
):
    """SC-VI-UI-012-2: on -> 100 % stays 1, 125 % rounds to 1, 150 % and above to 2."""
    child = _launch(tmp_path, stored=True, screens=[dpi])
    assert child["effective"] == ROUND
    assert child["dpr"] == rounded
    assert child["screens"] == [rounded]
    assert child["art_scale"] == rounded


@pytest.mark.parametrize("dpi, os_scale, rounded", _OS_SCALES)
def test_sc_vi_ui_012_3_with_the_preference_off_the_interface_follows_the_os_scale(
    tmp_path, dpi, os_scale, rounded
):
    """SC-VI-UI-012-3: off -> the ratio is the OS scale itself; the art scale rounds up."""
    child = _launch(tmp_path, stored=False, screens=[dpi])
    assert child["effective"] == PASS_THROUGH
    assert child["dpr"] == pytest.approx(os_scale)
    assert child["art_scale"] == math.ceil(os_scale)


@pytest.mark.parametrize("stored, ratio", [(True, 2.0), (False, 1.5)])
def test_sc_vi_ui_012_1_screen_scale_factors_variable_is_rounded_like_the_os_scale(
    tmp_path, stored, ratio
):
    """QT_SCREEN_SCALE_FACTORS=1.5 emulates a 150 % OS scale: on -> 2.0, off -> 1.5."""
    child = _launch(tmp_path, stored=stored, screens=None, scale_factors="1.5")
    assert child["dpr"] == ratio
    assert child["screens"] == [ratio]


def test_qt_scale_factor_is_not_rounded_so_it_is_not_an_os_scale_emulation(tmp_path):
    """QT_SCALE_FACTOR=1.5 stays 1.5 even with the preference on.

    It is a user scale on top of the OS one and the rounding policy does not touch it,
    which is why the 150 % cases above use the screen configuration instead.
    """
    child = _launch(tmp_path, stored=True, screens=None, env={"QT_SCALE_FACTOR": "1.5"})
    assert child["effective"] == ROUND
    assert child["dpr"] == pytest.approx(1.5)


def test_sc_vi_ui_012_2_two_screens_at_100_and_150_get_ratios_1_and_2(tmp_path):
    """Two screens side by side: 100 % -> 1 and 150 % -> 2 (preference on), art scale 2."""
    child = _launch(tmp_path, stored=True, screens=[_DPI_100, _DPI_150], probe=True)
    assert child["screens"] == [1.0, 2.0]
    assert child["art_scale"] == 2
    assert [entry["dpr"] for entry in child["probe"]] == [1.0, 2.0]
    assert [entry["interpolated"] for entry in child["probe"]] == [0, 0], child["probe"]


# --------------------------------------------------------------------------- #
# SC-VI-UI-012-1: frames hold no interpolated colour at 150 %                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_012_1_at_150_percent_on_the_framed_button_has_no_interpolated_pixel(
    tmp_path, mode
):
    """At an OS scale of 150 % with the preference on: ratio 2.0 and 0 interpolated pixels."""
    child = _launch(tmp_path, stored=True, mode=mode, screens=[_DPI_150], probe=True)
    assert child["mode"] == mode
    assert child["dpr"] == 2.0
    (entry,) = child["probe"]
    assert entry["opaque"] > 0, "the grab held no opaque pixel -- nothing was examined"
    assert entry["interpolated"] == 0, entry


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_012_1_control_at_150_percent_off_the_detector_finds_interpolation(
    tmp_path, mode
):
    """Positive control: the same button at ratio 1.5 (preference off) IS blurred.

    The detector of the test above must see this, or "0 interpolated pixels" there
    would mean nothing.
    """
    child = _launch(tmp_path, stored=False, mode=mode, screens=[_DPI_150], probe=True)
    assert child["dpr"] == pytest.approx(1.5)
    (entry,) = child["probe"]
    assert entry["opaque"] > 0
    assert entry["interpolated"] > 0, entry


# --------------------------------------------------------------------------- #
# The environment variable wins                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "variable, stored, effective, ratio",
    [
        (PASS_THROUGH, True, PASS_THROUGH, 1.5),
        (FLOOR, True, FLOOR, 1.0),
        (ROUND, False, ROUND, 2.0),
    ],
    ids=["passthrough-beats-on", "floor-beats-on", "round-beats-off"],
)
def test_the_environment_variable_overrides_the_preference_and_one_line_names_it(
    tmp_path, variable, stored, effective, ratio
):
    """The variable decides the policy; the contradiction is logged once, naming it.

    The variable is left exactly as it was: not cleared, not rewritten.
    """
    child = _launch(
        tmp_path,
        stored=stored,
        screens=[_DPI_150],
        env={ROUNDING_POLICY_ENV: variable},
    )
    assert child["effective"] == effective
    assert child["dpr"] == pytest.approx(ratio)
    assert len(child["naming_lines"]) == 1, child["naming_lines"]
    assert ROUNDING_POLICY_ENV in child["naming_lines"][0]
    assert child["env_before"] == variable and child["env_after"] == variable


def test_an_environment_variable_that_agrees_with_the_preference_logs_nothing(tmp_path):
    """Variable PassThrough + preference off: nothing to explain, no line."""
    child = _launch(
        tmp_path,
        stored=False,
        screens=[_DPI_150],
        env={ROUNDING_POLICY_ENV: PASS_THROUGH},
    )
    assert child["effective"] == PASS_THROUGH
    assert child["dpr"] == pytest.approx(1.5)
    assert child["naming_lines"] == []
    assert child["env_after"] == PASS_THROUGH


def test_an_environment_variable_that_is_not_a_policy_leaves_the_preference_in_charge(
    tmp_path,
):
    """A value Qt does not recognise is ignored by Qt: the stored preference decides, no line."""
    child = _launch(
        tmp_path,
        stored=True,
        screens=[_DPI_150],
        env={ROUNDING_POLICY_ENV: "not-a-policy"},
    )
    assert child["effective"] == ROUND
    assert child["dpr"] == 2.0
    assert child["naming_lines"] == []
    assert child["env_after"] == "not-a-policy"


# --------------------------------------------------------------------------- #
# SC-VI-UI-012-3: the message, and a real restart                              #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_012_3_unchecking_applies_at_the_next_launch_across_a_real_restart(
    tmp_path,
):
    """Process A unchecks the switch; process B starts with the OS scale.

    In A: the message appears, the running scale and policy are unchanged. The choice
    is on disk. In B (a new interpreter, same settings) the preference reads off, the
    policy is PassThrough and the ratio is the OS's 1.5.
    """
    first = _launch(tmp_path, screens=[_DPI_150], uncheck=True)
    assert first["effective"] == ROUND and first["dpr"] == 2.0
    assert first["message_after_uncheck"] == _NEXT_LAUNCH_MESSAGE
    assert first["effective_after_uncheck"] == ROUND
    assert first["dpr_after_uncheck"] == 2.0
    assert _settings_file_exists(tmp_path), "process A wrote no settings file"

    second = _launch(tmp_path, screens=[_DPI_150])
    assert second["pixel_perfect_shown"] is False
    assert second["calls"] == [[PASS_THROUGH, False]]
    assert second["effective"] == PASS_THROUGH
    assert second["dpr"] == pytest.approx(1.5)


# --------------------------------------------------------------------------- #
# SC-VI-UI-012-4: the Real-Size Preview keeps its physical size                #
# --------------------------------------------------------------------------- #


def test_sc_vi_ui_012_4_the_real_size_preview_has_the_same_physical_size_on_and_off(
    tmp_path,
):
    """At 150 %, a document pixel is the same physical size with the preference on and off.

    It is also the size the document's own PPI asks for (1/96 inch), so "equal" cannot
    mean "equally wrong". A manual multiplication by the ratio would show as 1.5/2.
    """
    on = _launch(tmp_path / "on", stored=True, screens=[_DPI_150], preview=True)
    off = _launch(tmp_path / "off", stored=False, screens=[_DPI_150], preview=True)
    assert on["preview"]["dpr"] == 2.0 and off["preview"]["dpr"] == pytest.approx(1.5)
    expected = _MM_PER_INCH / _DOCUMENT_PPI
    assert on["preview"]["mm_per_document_pixel"] == pytest.approx(
        expected, rel=_PHYSICAL_SIZE_REL_TOL
    )
    assert off["preview"]["mm_per_document_pixel"] == pytest.approx(
        expected, rel=_PHYSICAL_SIZE_REL_TOL
    )
    assert on["preview"]["mm_per_document_pixel"] == pytest.approx(
        off["preview"]["mm_per_document_pixel"], rel=_PHYSICAL_SIZE_REL_TOL
    )


# --------------------------------------------------------------------------- #
# In this process: a running application is left alone                        #
# --------------------------------------------------------------------------- #


class _PolicySpy:
    """Stands in for the policy setter: records the calls, changes nothing."""

    def __init__(self) -> None:
        self.calls: List[Any] = []

    def __call__(self, policy: Any) -> None:
        self.calls.append(policy)


def test_the_policy_setter_does_nothing_when_an_application_exists(monkeypatch):
    """With a running application the setter is not called and reports that it did nothing.

    The preference is stored OFF, so a call that slipped through would be a visible
    PassThrough in the spy.
    """
    assert QGuiApplication.instance() is not None
    save_appearance(replace(default_appearance(), pixel_perfect=False))
    spy = _PolicySpy()
    monkeypatch.setattr(
        QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", staticmethod(spy)
    )
    assert apply_stored_rounding_policy() is False
    assert spy.calls == []


def test_create_app_with_a_running_application_leaves_the_policy_and_the_log_alone(
    qtbot, monkeypatch, caplog
):
    """A second create_app (the test harness case) neither sets the policy nor logs.

    The preference is on (the default) and the override variable is set, while this
    process runs under Qt's default policy: that is a contradiction the start-up
    would log, so the control below proves the scenario would speak if the code
    reached the check. A call to the setter would show in the spy.
    """
    assert QGuiApplication.instance() is not None
    spy = _PolicySpy()
    monkeypatch.setattr(
        QGuiApplication, "setHighDpiScaleFactorRoundingPolicy", staticmethod(spy)
    )
    monkeypatch.setenv(ROUNDING_POLICY_ENV, FLOOR)
    before = QGuiApplication.highDpiScaleFactorRoundingPolicy()
    assert (
        before.name != ROUND
    ), "the scenario needs a policy that contradicts the preference"
    assert rounding_policy_mismatch(True) is not None, "control: this would be logged"
    with caplog.at_level("INFO"):
        app, window = create_app([])
    qtbot.addWidget(window)
    assert app is QGuiApplication.instance()
    assert spy.calls == []
    assert QGuiApplication.highDpiScaleFactorRoundingPolicy() == before
    assert [r for r in caplog.records if ROUNDING_POLICY_ENV in r.getMessage()] == []
    assert os.environ[ROUNDING_POLICY_ENV] == FLOOR


# --------------------------------------------------------------------------- #
# In this process: the "applies at the next launch" message                    #
# --------------------------------------------------------------------------- #


def _open(qtbot, qapp, mode: str) -> Main_Window:
    apply_theme(qapp, mode, DEFAULT_STYLE)
    window = Main_Window()
    qtbot.addWidget(window)
    return window


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_012_3_first_launch_is_checked_and_shows_no_message(qtbot, qapp, mode):
    """A first launch: "Pixel-perfect interface" is checked, and nothing is announced."""
    window = _open(qtbot, qapp, mode)
    assert window.pixel_perfect_interface() is True
    assert window._interface_pixel_perfect_action.isChecked() is True
    assert window.statusBar().currentMessage() == ""
    assert load_appearance().pixel_perfect is True


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_012_3_unchecking_states_that_the_change_applies_at_the_next_launch(
    qtbot, qapp, mode
):
    """Unchecking shows the message, stores the choice, emits once; the policy is untouched."""
    window = _open(qtbot, qapp, mode)
    policy = QGuiApplication.highDpiScaleFactorRoundingPolicy()
    ratio = window.devicePixelRatioF()
    heard: List[bool] = []
    window.pixelPerfectInterfaceChanged.connect(heard.append)
    with qtbot.waitSignal(window.pixelPerfectInterfaceChanged, timeout=1000):
        window._interface_pixel_perfect_action.trigger()
    assert heard == [False]
    assert window.statusBar().currentMessage() == _NEXT_LAUNCH_MESSAGE
    assert load_appearance().pixel_perfect is False
    # the new choice cannot apply to this run
    assert QGuiApplication.highDpiScaleFactorRoundingPolicy() == policy
    assert window.devicePixelRatioF() == ratio


@pytest.mark.parametrize("mode", [THEME_LIGHT, THEME_DARK])
def test_sc_vi_ui_012_3_setting_the_same_value_again_announces_nothing(
    qtbot, qapp, mode
):
    """Re-setting the value it already has shows no message and emits no signal."""
    window = _open(qtbot, qapp, mode)
    window.set_pixel_perfect_interface(False)
    window.statusBar().clearMessage()
    heard: List[bool] = []
    window.pixelPerfectInterfaceChanged.connect(heard.append)
    window.set_pixel_perfect_interface(False)
    assert heard == []
    assert window.statusBar().currentMessage() == ""
    # checking it again is a change, so it is announced again
    window.set_pixel_perfect_interface(True)
    assert heard == [True]
    assert window.statusBar().currentMessage() == _NEXT_LAUNCH_MESSAGE


class _StandInTranslator(QTranslator):
    """Translates exactly one message of one context, to a recognisable text."""

    def __init__(self, context: str, source: str, target: str) -> None:
        super().__init__()
        self._key = (context, source)
        self._target = target

    def isEmpty(self) -> bool:  # noqa: N802 (Qt override)
        return False

    def translate(  # noqa: N802 (Qt override)
        self,
        context: str,
        source: str,
        disambiguation: Optional[str] = None,
        n: int = -1,
    ) -> Optional[str]:
        return self._target if (context, source) == self._key else None


def test_sc_vi_ui_012_3_the_message_is_translated_when_it_is_shown(qtbot, qapp):
    """The message is wrapped for translation (context Main_Window) and looked up when shown.

    A stand-in translator carries one entry. While installed the message reads in the
    other language; once removed the next announcement reads in English again.
    """
    target = "TRANSLATED: applies at the next launch"
    translator = _StandInTranslator(_MESSAGE_CONTEXT, _NEXT_LAUNCH_MESSAGE, target)
    window = _open(qtbot, qapp, THEME_LIGHT)
    assert QCoreApplication.installTranslator(translator)
    try:
        window.set_pixel_perfect_interface(False)
        assert window.statusBar().currentMessage() == target
    finally:
        QCoreApplication.removeTranslator(translator)
    window.set_pixel_perfect_interface(True)
    assert window.statusBar().currentMessage() == _NEXT_LAUNCH_MESSAGE


def test_the_translator_stand_in_is_consulted_only_for_its_own_message():
    """Control: the stand-in changes the one message and nothing else."""
    translator = _StandInTranslator(_MESSAGE_CONTEXT, _NEXT_LAUNCH_MESSAGE, "X")
    assert QCoreApplication.installTranslator(translator)
    try:
        assert QCoreApplication.translate(_MESSAGE_CONTEXT, _NEXT_LAUNCH_MESSAGE) == "X"
        assert (
            QCoreApplication.translate(_MESSAGE_CONTEXT, "Something else")
            == "Something else"
        )
        assert (
            QCoreApplication.translate("Other", _NEXT_LAUNCH_MESSAGE)
            == _NEXT_LAUNCH_MESSAGE
        )
    finally:
        QCoreApplication.removeTranslator(translator)
