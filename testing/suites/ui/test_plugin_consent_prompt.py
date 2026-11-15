"""The plugin consent prompt is truthful (REQ-L10N-UI-016).

SC-L10N-UI-016-1: the English source message of the prompt holds neither
"sandbox" (in any letter case), nor "cannot reach", nor the phrase "through the
app's own commands", and holds each of its two placeholders, ``%1`` and ``%2``,
exactly once. The scan is applied to two readings of that one message: the
source message of ``pixelart_en.ts`` and the source text the panel passes to
``tr()`` when Enable is chosen. Planted copies of the two earlier prompt texts
prove the scan fails, and names what it found, so a green run cannot be a scan
that finds nothing; wordings that meet the requirement prove it can be met.

SC-L10N-UI-016-2, clause 5's fact: enabling a plugin from the panel runs none of
the plugin's code. A real distribution in the plugin entry-point group, on a
scratch ``sys.path`` only, writes a marker file when its module is imported;
no marker after Enable proves the code did not run, and a control that loads
the same entry point writes it.

Both themes (the suite's ``theme`` fixture applies to every case), offscreen.
Nothing outside ``tmp_path`` is written, and no catalogue or product file is
changed: the catalogue is only read.
"""

from __future__ import annotations

import importlib
import sys
import xml.etree.ElementTree as ET
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterator, List

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

import pixelart_creator
from pixelart_creator.logic import plugins
from pixelart_creator.logic.plugins import ENTRY_POINT_GROUP
from pixelart_creator.ui.plugin_manager_panel import Plugin_Manager_Panel
from testing.suites.ui._automation_helpers import write_manifest

CATALOGUE = Path(pixelart_creator.__file__).parent / "i18n" / "pixelart_en.ts"
CONTEXT = "Plugin_Manager_Panel"
# The prompt's first part, which every wording of it keeps: it is how the one
# live message of the prompt is found in the catalogue and among the panel's
# source texts.
OPENING = "Enable %1 and "

# What the English prompt must not hold, in any letter case. A scan that is
# blind to case, to a typographic apostrophe or to a line break inside a phrase
# would let the same claim through in another spelling.
BANNED = ("sandbox", "cannot reach", "through the app's own commands")
PLACEHOLDERS = ("%1", "%2")

# The two earlier English texts of the prompt, planted as controls.
RUNS_SANDBOXED_TEXT = (
    "Enable %1 and grant it these permissions?\n\n%2\n\n"
    "The plugin runs sandboxed and can only edit through reversible commands. "
    "It cannot reach the UI, filesystem, or network."
)
OWN_COMMANDS_TEXT = (
    "Enable %1 and approve these permissions?\n\n%2\n\n"
    "Plugins are not isolated from your computer. Only enable plugins you trust. "
    "These permissions limit what a plugin can do through the app's own commands, "
    "not what the plugin's own code can do."
)

# The prompt's first three parts, as they are, followed by wordings of the last
# sentence that state what the permissions do and do not limit.
FIRST_PARTS = (
    "Enable %1 and approve these permissions?\n\n%2\n\n"
    "Plugins are not isolated from your computer. Only enable plugins you trust. "
)
MEETING_SENTENCES = {
    # The example wording the requirement offers (offered, not required).
    "requirement-example": (
        "These permissions are checked only on requests made through the app's "
        "permission object, not on what the plugin's own code can do."
    ),
    # A differently worded sentence that states the same facts.
    "reworded": (
        "A permission is enforced only when a call goes through the plugin "
        "host's permission object; it places no limit on what the plugin's own "
        "code can do."
    ),
}


def prompt_findings(text: str) -> List[str]:
    """Return what is wrong with a prompt text; an empty list means nothing is."""
    folded = " ".join(text.replace("’", "'").split()).lower()
    found = [f'contains "{banned}"' for banned in BANNED if banned in folded]
    for placeholder in PLACEHOLDERS:
        count = text.count(placeholder)
        if count != 1:
            found.append(f"holds {placeholder} {count} times, not once")
    return found


def assert_prompt_acceptable(text: str) -> None:
    """Fail naming each banned word or phrase, and each wrong placeholder count."""
    findings = prompt_findings(text)
    assert not findings, (
        "the consent prompt is not acceptable: "
        + "; ".join(findings)
        + f"\nprompt text: {text!r}"
    )


def catalogue_prompt_source() -> str:
    """Return the one live English source message of the prompt from the catalogue."""
    hits: List[str] = []
    for context in ET.parse(CATALOGUE).getroot().iter("context"):
        if context.findtext("name") != CONTEXT:
            continue
        for message in context.iter("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            kind = None if translation is None else translation.get("type")
            if source.startswith(OPENING) and kind not in ("obsolete", "vanished"):
                hits.append(source)
    assert len(hits) == 1, (
        f"expected exactly one live message in context {CONTEXT} that starts with "
        f"{OPENING!r}, found {len(hits)}: {hits!r}"
    )
    return hits[0]


def _install(panel, monkeypatch, path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    panel._on_install()


def _answer(monkeypatch, answer: QMessageBox.StandardButton) -> List[str]:
    """Stub the consent question to give ``answer``; return the texts it was shown."""
    shown: List[str] = []

    def question(parent, title, text, *args, **kwargs):
        shown.append(text)
        return answer

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return shown


def panel_prompt_source(qtbot, monkeypatch, tmp_path) -> str:
    """Return the source text the panel passes to ``tr()`` for the consent prompt."""
    panel = Plugin_Manager_Panel()
    qtbot.addWidget(panel)
    manifest = write_manifest(
        tmp_path / "source-probe.json",
        name="source-probe",
        capabilities=["read_document"],
    )
    _install(panel, monkeypatch, manifest)
    sources: List[str] = []

    def record(source: str, *args, **kwargs) -> str:
        sources.append(source)
        return source

    monkeypatch.setattr(panel, "tr", record)
    _answer(monkeypatch, QMessageBox.StandardButton.No)
    panel._on_enable()
    hits = [source for source in sources if source.startswith(OPENING)]
    assert len(hits) == 1, (
        f"expected exactly one source text starting with {OPENING!r} among what "
        f"Enable passed to tr(), found {len(hits)}; all of them: {sources!r}"
    )
    return hits[0]


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-1: the prompt the user is shown                              #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_016_1_catalogue_source_message_is_acceptable():
    """SC-L10N-UI-016-1: the source message of pixelart_en.ts passes the scan."""
    assert_prompt_acceptable(catalogue_prompt_source())


def test_sc_l10n_ui_016_1_panel_source_text_is_acceptable(qtbot, monkeypatch, tmp_path):
    """SC-L10N-UI-016-1: the text the panel passes to tr() passes the scan."""
    assert_prompt_acceptable(panel_prompt_source(qtbot, monkeypatch, tmp_path))


def test_sc_l10n_ui_016_1_the_two_readings_find_one_message(
    qtbot, monkeypatch, tmp_path
):
    """SC-L10N-UI-016-1: each reading finds exactly one live message to scan."""
    assert catalogue_prompt_source().startswith(OPENING)
    assert panel_prompt_source(qtbot, monkeypatch, tmp_path).startswith(OPENING)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-1: the scan itself, with planted controls                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("planted", "named"),
    [
        pytest.param(
            RUNS_SANDBOXED_TEXT,
            ['contains "sandbox"', 'contains "cannot reach"'],
            id="runs-sandboxed-text",
        ),
        pytest.param(
            OWN_COMMANDS_TEXT,
            ['contains "through the app\'s own commands"'],
            id="own-commands-text",
        ),
    ],
)
def test_sc_l10n_ui_016_1_planted_earlier_text_fails_naming_what_it_holds(
    planted, named
):
    """SC-L10N-UI-016-1: each earlier text, planted, fails and names its words."""
    assert prompt_findings(planted) == named
    with pytest.raises(AssertionError) as failure:
        assert_prompt_acceptable(planted)
    for finding in named:
        assert finding in str(failure.value)


@pytest.mark.parametrize(
    ("planted", "named"),
    [
        pytest.param("Runs in a SANDBOX.", 'contains "sandbox"', id="upper-case"),
        pytest.param("A Sandboxed plugin.", 'contains "sandbox"', id="capitalised"),
        pytest.param(
            "It Cannot Reach the network.", 'contains "cannot reach"', id="cannot-reach"
        ),
        pytest.param(
            "limit it through the app’s own commands.",
            'contains "through the app\'s own commands"',
            id="curly-apostrophe",
        ),
        pytest.param(
            "limit it through the app's\nown commands.",
            'contains "through the app\'s own commands"',
            id="line-break-inside-the-phrase",
        ),
        pytest.param(
            "Through the app's own commands only.",
            'contains "through the app\'s own commands"',
            id="capital-letter",
        ),
    ],
)
def test_sc_l10n_ui_016_1_spelling_variants_are_found(planted, named):
    """SC-L10N-UI-016-1: a banned word or phrase is found in another spelling."""
    assert named in prompt_findings("%1 %2 " + planted)


@pytest.mark.parametrize(
    ("planted", "named"),
    [
        pytest.param(
            "Enable %1 and approve?\n\n%2 %2", "holds %2 2 times", id="2-twice"
        ),
        pytest.param("Enable %1 %1 and %2", "holds %1 2 times", id="1-twice"),
        pytest.param("Enable %1 and approve?", "holds %2 0 times", id="2-missing"),
        pytest.param("Enable and approve %2?", "holds %1 0 times", id="1-missing"),
    ],
)
def test_sc_l10n_ui_016_1_placeholders_are_counted_once_each(planted, named):
    """SC-L10N-UI-016-1: a placeholder held twice, or not at all, fails naming it."""
    with pytest.raises(AssertionError) as failure:
        assert_prompt_acceptable(planted)
    assert named in str(failure.value)


@pytest.mark.parametrize(
    "sentence", MEETING_SENTENCES.values(), ids=list(MEETING_SENTENCES)
)
def test_sc_l10n_ui_016_1_a_wording_that_meets_the_requirement_passes(sentence):
    """SC-L10N-UI-016-1 control: the scan can be satisfied by a truthful sentence."""
    text = FIRST_PARTS + sentence
    assert prompt_findings(text) == []
    assert_prompt_acceptable(text)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-2, clause 5: enabling runs no plugin code                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def probe_plugin(tmp_path, monkeypatch) -> Iterator[Dict[str, object]]:
    """Install, on a scratch sys.path only, a real distribution in the plugin group.

    Its module writes a marker file when imported, so a marker proves the plugin's
    code ran and its absence proves it did not. Nothing is installed anywhere else.
    """
    site = tmp_path / "site"
    site.mkdir()
    marker = tmp_path / "consent_probe_ran.txt"
    module = "consent_probe_plugin_module"
    (site / f"{module}.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    dist_info = site / "consent_probe_plugin-1.2.3.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: consent-probe-plugin\nVersion: 1.2.3\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        f"[{ENTRY_POINT_GROUP}]\nconsent-probe = {module}\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()
    try:
        yield {"marker": marker, "module": module}
    finally:
        sys.modules.pop(module, None)


def test_sc_l10n_ui_016_2_clause_5_enabling_from_the_panel_runs_no_plugin_code(
    qtbot, monkeypatch, tmp_path, plugin_isolation, probe_plugin
):
    """SC-L10N-UI-016-2 clause 5: Enable, confirmed, runs none of the plugin's code."""
    assert "consent-probe" in [m.name for m in plugins.discover()]  # installed
    panel = Plugin_Manager_Panel()
    qtbot.addWidget(panel)
    manifest = write_manifest(
        tmp_path / "consent-probe.json",
        name="consent-probe",
        capabilities=["read_document"],
    )
    _install(panel, monkeypatch, manifest)
    shown = _answer(monkeypatch, QMessageBox.StandardButton.Yes)

    panel._on_enable()

    assert len(shown) == 1  # the prompt was shown and confirmed
    assert "consent-probe" in panel._handles  # and the plugin really was enabled
    assert plugins.loaded_count() == 1
    assert not probe_plugin["marker"].exists()
    assert probe_plugin["module"] not in sys.modules


def test_sc_l10n_ui_016_2_clause_5_control_loading_the_plugin_writes_the_marker(
    probe_plugin,
):
    """SC-L10N-UI-016-2 clause 5 control: loading the same plugin writes the marker."""
    points = [
        point
        for point in metadata.entry_points(group=ENTRY_POINT_GROUP)
        if point.name == "consent-probe"
    ]
    assert len(points) == 1
    assert not probe_plugin["marker"].exists()
    points[0].load()
    assert probe_plugin["marker"].read_text() == "ran"
