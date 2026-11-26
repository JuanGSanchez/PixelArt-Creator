# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""A platform default that is an alias is captured as the family Qt draws for it.

``REQ-VI-UI-016``: "Use system font" restores exactly the platform's own font.
``REQ-L10N-UI-009``: that mode is one of the two the appearance preference
offers. On some platforms the application's default font is not a family name
but a generic alias that the font database does not list (the offscreen plugin
gives "Sans Serif" on Linux and on macOS). The product must capture the family
Qt draws for that alias, so that everything built from the captured font (the
family chain, the guide page, the per-class fonts) starts from an installed
family. Captured as the alias itself, the Han probe answers for a face that is
not the platform's and the Nifen Art CJK face is asked for, and drawn, where the
platform font is expected.

What is measured, in a child process per test
---------------------------------------------
Each test starts a fresh interpreter, which is the only way to get a font
database and a captured platform font that nothing else has touched. The child:

1. creates the application and reports that the font database is not empty and
   does not list the alias;
2. sets the application font to the alias, the value the platform gives;
3. reads, before any bundled face is registered, the family Qt draws for it;
4. runs the product's start-up call with "Use system font" on;
5. reports the captured family, what the case under test builds from it, and
   whether the Han probe answers for it.

The parent asserts both preconditions (the database is not empty, the alias is
absent) and that the family read in step 3 is a real, non-bundled one, so a host
that cannot show the shape fails and is never passed over. The assertions are
the same on every operating system. On Windows only, the child is also given the
font folder, because the offscreen plugin there finds no system font without it;
that is provisioning, not a branch of the test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from pixelart_creator.ui import app_font
from testing.suites.ui.test_app_font import platform_font_dir

#: The generic family name the platform gives as its default, which Qt's font
#: database does not list.
ALIAS = "Sans Serif"

#: How long one child may run, in seconds; below the suite's per-test timeout.
CHILD_TIMEOUT_SECONDS = 100

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The child's script. ``argv[1]`` is the case, ``argv[2]`` the repository root.
_CHILD_SCRIPT = """
import json
import os
import sys

sys.path.insert(0, sys.argv[2])
case = sys.argv[1]

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication, QLabel, QWidget

app = QApplication([])
families = QFontDatabase.families()
out = {
    "platform": app.platformName(),
    "fontdir": os.environ.get("QT_QPA_FONTDIR", ""),
    "families": len(families),
    "has_alias": "Sans Serif" in families,
}
app.setFont(QFont("Sans Serif"))
out["expected"] = QFontInfo(QFont("Sans Serif")).family()

import pixelart_creator.logic.font_chain as font_chain
from pixelart_creator.ui import app_font

bundled = {
    app_font.NIFEN_ART_FAMILY,
    font_chain.CJK_SC_FAMILY,
    font_chain.CJK_JP_FAMILY,
    font_chain.CJK_HANGUL_FAMILY,
}
app_font.prepare_interface_font(app, True)
snapshot = app_font.platform_default_font().family()
out["snapshot"] = snapshot
out["snapshot_bundled"] = snapshot in bundled
out["expected_bundled"] = out["expected"] in bundled
out["holds"] = app_font.primary_holds_cjk(snapshot)


def first_of(font):
    listed = font.families()
    return listed[0] if listed else font.family()


if case == "system_font":
    font = QLabel("x").font()
    out["first"] = first_of(font)
    out["resolved"] = QFontInfo(font).family()
else:
    from pixelart_creator.ui.user_guide import User_Guide_Dialog

    def page_font(dialog):
        return dialog._content_view.document().defaultFont()

    dialog = User_Guide_Dialog(None)
    page = page_font(dialog)
    out["page_family"] = page.family()
    out["first"] = first_of(page)
    out["resolved"] = QFontInfo(page).family()
    if case == "logo_switch":

        def fonts_of(dialog):
            found = {}
            for index, widget in enumerate([dialog, *dialog.findChildren(QWidget)]):
                key = "guide:%d:%s:%s" % (
                    index,
                    type(widget).__name__,
                    widget.objectName(),
                )
                found[key] = widget.font().toString()
            found["application"] = QApplication.font().toString()
            for name in app_font._PLATFORM_CLASS_FONTS:
                found["class:" + name] = QApplication.font(name).toString()
            return found

        def changed(before, after):
            keys = set(before) | set(after)
            return sorted(k for k in keys if before.get(k) != after.get(k))

        before = fonts_of(dialog)
        out["widgets_examined"] = len([k for k in before if k.startswith("guide:")])
        bold = QFont(dialog._toc_tree.font())
        bold.setBold(True)
        original = QFont(dialog._toc_tree.font())
        dialog._toc_tree.setFont(bold)
        seen = changed(before, fonts_of(dialog))
        dialog._toc_tree.setFont(original)
        out["control_seen"] = any("QTreeWidget" in key for key in seen)
        out["control_restored"] = changed(before, fonts_of(dialog))
        dialog._logo_switch.click()
        app.processEvents()
        out["page_on"] = page_font(dialog).family()
        out["changed_on"] = changed(before, fonts_of(dialog))
        dialog._logo_switch.click()
        app.processEvents()
        out["page_off"] = page_font(dialog).family()
        out["changed_off"] = changed(before, fonts_of(dialog))
        built_on = User_Guide_Dialog(None, guide_pixel_font=True)
        built_off = User_Guide_Dialog(None, guide_pixel_font=False)
        out["built_on_pixel"] = built_on.page_uses_pixel_font()
        out["built_on_page"] = page_font(built_on).family()
        out["built_off_pixel"] = built_off.page_uses_pixel_font()
        out["built_off_page"] = page_font(built_off).family()

print("RESULT " + json.dumps(out), flush=True)
"""


def _run_child(tmp_path: Path, case: str) -> Dict[str, Any]:
    """Run the child for ``case`` and return the JSON line it prints."""
    script = tmp_path / "platform_default_child.py"
    script.write_text(_CHILD_SCRIPT, encoding="utf-8")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    fonts = platform_font_dir()
    if fonts:
        env["QT_QPA_FONTDIR"] = fonts
    done = subprocess.run(
        [sys.executable, str(script), case, str(_REPO_ROOT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=CHILD_TIMEOUT_SECONDS,
    )
    assert (
        done.returncode == 0
    ), f"the child exited {done.returncode}\n{done.stdout}\n{done.stderr}"
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, f"the child printed no RESULT line\n{done.stdout}\n{done.stderr}"
    result: Dict[str, Any] = json.loads(lines[-1][len("RESULT ") :])
    return result


def _facts(result: Dict[str, Any]) -> str:
    """Return the values every assertion message carries."""
    return (
        f"platform {result['platform']!r}; snapshot {result['snapshot']!r}; "
        f"expected {result['expected']!r}; first family {result['first']!r}; "
        f"resolved {result['resolved']!r}; holds {result['holds']}"
    )


def _assert_host_shows_the_shape(result: Dict[str, Any]) -> None:
    """Fail unless this host can show a platform default that is an alias."""
    assert (
        result["families"] > 0
    ), f"the child's font database is empty; {_facts(result)}"
    assert not result["has_alias"], (
        f"{ALIAS!r} is a family of the child's font database, so it is not an "
        f"alias here; {_facts(result)}"
    )
    assert result["expected"] and result["expected"] != ALIAS, (
        f"Qt draws {result['expected']!r} for {ALIAS!r}: the host cannot show "
        f"the shape; {_facts(result)}"
    )
    assert not result["expected_bundled"], (
        f"Qt draws a bundled family for {ALIAS!r}: the host cannot show the "
        f"shape; {_facts(result)}"
    )


@pytest.fixture
def theme() -> str:
    """Take the place of the suite's parametrised theme: the child owns the look.

    Nothing here draws in the test process, so a light and a dark run would be
    the same run twice.
    """
    return "none"


def test_an_alias_default_is_captured_as_the_family_qt_draws(
    tmp_path: Path,
) -> None:
    """``REQ-VI-UI-016``: "Use system font" starts from an installed family.

    The captured default is the family Qt draws for the alias, it is not a
    bundled family, and a label in the application's font asks for it first and
    is drawn with it.
    """
    result = _run_child(tmp_path, "system_font")
    _assert_host_shows_the_shape(result)
    snapshot = result["snapshot"]
    assert snapshot == result["expected"], (
        f"the platform default was captured as {snapshot!r}, not as the family "
        f"Qt draws for {ALIAS!r}; {_facts(result)}"
    )
    assert snapshot != ALIAS, f"the alias was captured as it is; {_facts(result)}"
    assert not result[
        "snapshot_bundled"
    ], f"the platform default was captured as a bundled family; {_facts(result)}"
    assert result["first"] == snapshot, (
        f"a label's font asks for {result['first']!r} first, not for the "
        f"platform default; {_facts(result)}"
    )
    assert result["resolved"] == snapshot, (
        f"a label is drawn with {result['resolved']!r}, not with the platform "
        f"default; {_facts(result)}"
    )


def test_the_guide_page_font_equals_the_platform_font(tmp_path: Path) -> None:
    """``REQ-VI-UI-013``: the page text is in the platform font, not Nifen Art.

    The guide page's font, built by the guide itself, has the captured platform
    family, and that family is the one Qt draws for the alias.
    """
    result = _run_child(tmp_path, "guide_page")
    _assert_host_shows_the_shape(result)
    assert result["page_family"] == result["snapshot"], (
        f"the guide page is in {result['page_family']!r}, the platform font is "
        f"{result['snapshot']!r}; {_facts(result)}"
    )
    assert result["snapshot"] == result["expected"], (
        f"the platform default was captured as {result['snapshot']!r}, not as "
        f"the family Qt draws for {ALIAS!r}; {_facts(result)}"
    )
    assert result["page_family"] != app_font.NIFEN_ART_FAMILY, _facts(result)


def test_the_logo_switch_moves_the_page_font_between_the_two_fonts(
    tmp_path: Path,
) -> None:
    """``REQ-VI-UI-017``: the switch toggles the page text and nothing else.

    A guide built with the switch off starts in the platform font, the switch
    puts the page text in Nifen Art and back, no other font of the guide or of
    the application changes, and a guide built with the remembered switch on
    starts in Nifen Art. The control: a font change on the topic list must show
    in the comparison.
    """
    result = _run_child(tmp_path, "logo_switch")
    _assert_host_shows_the_shape(result)
    nifen = app_font.NIFEN_ART_FAMILY
    facts = _facts(result)
    assert result["page_family"] == result["snapshot"], (
        f"the guide page starts in {result['page_family']!r}, the platform font "
        f"is {result['snapshot']!r}; {facts}"
    )
    assert result["snapshot"] == result["expected"], (
        f"the platform default was captured as {result['snapshot']!r}, not as "
        f"the family Qt draws for {ALIAS!r}; {facts}"
    )
    assert (
        result["widgets_examined"] > 10
    ), f"the comparison examined almost nothing; {facts}"
    assert result["control_seen"], f"the comparison is blind to a font change; {facts}"
    assert result["control_restored"] == [], (
        f"a font did not come back after the control: {result['control_restored']}; "
        f"{facts}"
    )
    assert result["page_on"] == nifen, (
        f"with the switch on the page is in {result['page_on']!r}, not "
        f"{nifen!r}; {facts}"
    )
    assert result["changed_on"] == [], (
        f"a font outside the page changed with the switch on: "
        f"{result['changed_on']}; {facts}"
    )
    assert result["page_off"] == result["snapshot"], (
        f"with the switch off again the page is in {result['page_off']!r}, not "
        f"in the platform font {result['snapshot']!r}; {facts}"
    )
    assert result["changed_off"] == [], (
        f"a font did not come back with the switch off: {result['changed_off']}; "
        f"{facts}"
    )
    assert result["built_on_pixel"] is True and result["built_on_page"] == nifen, (
        f"a guide built with the switch on is in {result['built_on_page']!r}, "
        f"pixel font {result['built_on_pixel']}; {facts}"
    )
    assert (
        result["built_off_pixel"] is False
        and result["built_off_page"] == result["snapshot"]
        and result["built_off_page"] != nifen
    ), (
        f"a guide built with the switch off is in {result['built_off_page']!r}, "
        f"pixel font {result['built_off_pixel']}; {facts}"
    )
