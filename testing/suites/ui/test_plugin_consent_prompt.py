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

SC-L10N-UI-016-3: the prompt is shown in every interface language. With each of
the eight languages active in turn and a plugin with a loaded manifest, Enable
shows the text of that catalogue's finished translation of the prompt, with the
plugin's name and its permission list (each permission named by that catalogue's
finished translation of its name) in the two placeholders; the number of languages
examined, 8, is printed. Neither earlier English source text of the prompt is a live
message of any of the eight catalogues, and the English source message is the text
whose SHA-256 the truth check recorded (a stale reading hashes differently). The
expected text is read from each language's own ``.ts``, never from the code under
test.

Both themes (the suite's ``theme`` fixture applies to every case), offscreen.
Nothing outside ``tmp_path`` is written, and no catalogue or product file is
changed: the catalogue is only read.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import xml.etree.ElementTree as ET
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

import pixelart_creator
from pixelart_creator.logic import plugins
from pixelart_creator.logic.plugins import ENTRY_POINT_GROUP
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
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


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-3: the prompt in every interface language                    #
# --------------------------------------------------------------------------- #

#: The languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8
LANGUAGES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ko", "ja")

#: The digest the truth check recorded for the English source message of the
#: prompt (report ``agt08-consent-truth-r30.md`` section 5): the UTF-8 bytes of the
#: unescaped text, both placeholders left in, four line feeds, no trailing newline.
RECORDED_SHA256 = "19f52cf91aedea74481271c425af5d294004568d738b70c6b185d36f9a33974b"
#: The digest the same report records for the round-17 text, which a stale reading
#: would hash to.
ROUND_17_SHA256 = "610042f122b1ff24248e2573e78529467c1ce3bd1e4bbb42086f4ee988a26978"

#: The plugin the rows enable, and the permissions its manifest declares, in order,
#: each with the English source message that names it in the catalogue.
PLUGIN_NAME = "lang-probe"
DECLARED = (
    ("read_document", "Read the open document"),
    ("write_via_command", "Change the document through the app's commands"),
)
BULLET = "• "

#: The two earlier English source texts of the prompt (the "runs sandboxed" text and
#: the one written to round 17's clause 3).
EARLIER_TEXTS = (RUNS_SANDBOXED_TEXT, OWN_COMMANDS_TEXT)

Message = Tuple[str, str, Optional[str], Optional[str]]


def digest(text: str) -> str:
    """Return the SHA-256 of ``text`` as the truth check hashed it (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _folded(text: str) -> str:
    """Return ``text`` with one kind of apostrophe and single spaces only."""
    return " ".join(text.replace("’", "'").split())


def _messages(code: str, directory: Optional[Path] = None) -> List[Message]:
    """Return every message of a catalogue as (context, source, kind, text)."""
    folder = directory if directory is not None else _default_translations_dir()
    root = ET.parse(folder / f"pixelart_{code}.ts").getroot()
    found: List[Message] = []
    for context in root.iter("context"):
        name = context.findtext("name") or ""
        for message in context.iter("message"):
            translation = message.find("translation")
            kind = None if translation is None else translation.get("type")
            text = None if translation is None else translation.text
            found.append((name, message.findtext("source") or "", kind, text))
    return found


def _is_live(kind: Optional[str]) -> bool:
    """Return whether a message of this translation kind is live in its catalogue."""
    return kind not in ("obsolete", "vanished")


def prompt_template(code: str, directory: Optional[Path] = None) -> str:
    """Return the prompt's text in ``code``: the catalogue's, with both placeholders.

    There must be exactly one live message of the panel's context that starts with
    the prompt's opening. English shows its source; any other language shows the
    entry's translation, which must be finished, with a text, hold each placeholder
    once and differ from the English source.
    """
    hits = [
        (source, kind, text)
        for context, source, kind, text in _messages(code, directory)
        if context == CONTEXT and source.startswith(OPENING) and _is_live(kind)
    ]
    assert len(hits) == 1, f"{code}: {len(hits)} live prompt messages: {hits!r}"
    source, kind, text = hits[0]
    if code == FALLBACK_LANGUAGE:
        return source
    assert text, f"{code}: the prompt has no translation text"
    assert kind != "unfinished", f"{code}: the prompt is unfinished"
    for placeholder in PLACEHOLDERS:
        assert text.count(placeholder) == 1, f"{code}: {placeholder} not once: {text!r}"
    assert text != source, f"{code}: the prompt is its English source"
    return text


def permission_name(code: str, source: str, directory: Optional[Path] = None) -> str:
    """Return the catalogue's finished name of one permission in ``code``."""
    hits = [
        (kind, text)
        for context, found, kind, text in _messages(code, directory)
        if context == CONTEXT and found == source
    ]
    assert len(hits) == 1, f"{code}: {len(hits)} entries for {source!r}"
    kind, text = hits[0]
    if code == FALLBACK_LANGUAGE:
        return source
    assert text and kind != "unfinished", f"{code}: {source!r} is not finished"
    return text


def expected_prompt(code: str) -> str:
    """Return the prompt the user must be shown in ``code`` for the probe plugin."""
    listing = "\n".join(
        BULLET + permission_name(code, source) for _value, source in DECLARED
    )
    template = prompt_template(code)
    return template.replace("%1", PLUGIN_NAME).replace("%2", listing)


def earlier_texts_live(
    directory: Optional[Path] = None, codes: Sequence[str] = LANGUAGES
) -> List[str]:
    """Return a finding for each live message, in any catalogue, that is an old prompt.

    A message is one of the earlier prompts when its source, with one kind of
    apostrophe and single spaces, equals either earlier text so folded. A message
    marked obsolete or vanished is not live, and an absent one is not found.
    """
    old = {_folded(text): text for text in EARLIER_TEXTS}
    findings: List[str] = []
    for code in codes:
        for context, source, kind, _text in _messages(code, directory):
            if _folded(source) in old and _is_live(kind):
                findings.append(
                    f"pixelart_{code}.ts: context {context}: the earlier prompt "
                    f"{source[:40]!r}... is live (translation type {kind!r})"
                )
    return findings


@pytest.fixture
def language(qapp) -> Iterator[LanguageManager]:
    """Hand out the app's own language manager; restore English afterwards."""
    manager = LanguageManager(qapp)
    try:
        yield manager
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def shown_prompt(
    qtbot, monkeypatch, tmp_path: Path, manager: LanguageManager, code: str
) -> str:
    """Enable the probe plugin with ``code`` active; return the prompt it showed.

    The plugin's manifest is a file under ``tmp_path`` loaded through the panel's
    own install action, Enable is pressed on the real button, and the one question
    box it raises is answered No, so nothing is enabled.
    """
    assert manager.set_language(code) is True, f"{code!r} did not load"
    panel = Plugin_Manager_Panel()
    qtbot.addWidget(panel)
    manifest = write_manifest(
        tmp_path / f"lang-probe-{code}.json",
        name=PLUGIN_NAME,
        capabilities=[value for value, _source in DECLARED],
    )
    _install(panel, monkeypatch, manifest)
    shown = _answer(monkeypatch, QMessageBox.StandardButton.No)
    assert panel._enable_button.isEnabled(), "Enable is not available for the probe"
    panel._enable_button.click()
    assert len(shown) == 1, f"{len(shown)} prompts were shown, not one: {shown!r}"
    return shown[0]


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_016_3_the_prompt_is_the_catalogue_text_with_both_filled(
    qtbot, monkeypatch, tmp_path, language, code
):
    """SC-L10N-UI-016-3: Enable shows that catalogue's finished prompt, filled in.

    With ``code`` active and the probe plugin's manifest loaded, the one prompt shown
    equals the catalogue's text for the prompt with the plugin's name in ``%1`` and
    the permission list (a bullet and that catalogue's finished name for each
    declared permission, one per line) in ``%2``; no placeholder is left in it.
    """
    shown = shown_prompt(qtbot, monkeypatch, tmp_path, language, code)
    expected = expected_prompt(code)
    assert shown == expected, f"[{code}] shown {shown!r}, catalogue gives {expected!r}"
    assert "%1" not in shown and "%2" not in shown, shown
    assert shown.count(PLUGIN_NAME) == 1, shown


def test_sc_l10n_ui_016_3_the_languages_examined_are_printed(
    qtbot, monkeypatch, tmp_path, language, capsys
):
    """SC-L10N-UI-016-3: the run says how many of the eight languages it examined."""
    examined: List[str] = []
    for code in LANGUAGES:
        shown = shown_prompt(qtbot, monkeypatch, tmp_path, language, code)
        assert shown == expected_prompt(code), f"[{code}] {shown!r}"
        examined.append(code)
    line = (
        f"languages examined: {len(examined)} of {EXPECTED_LANGUAGE_COUNT} {examined}; "
        f"permissions per prompt: {len(DECLARED)}"
    )
    print(line)
    with capsys.disabled():
        print(f"[consent prompt] {line}")
    assert len(examined) == EXPECTED_LANGUAGE_COUNT == 8
    assert examined == list(LANGUAGES)


def test_sc_l10n_ui_016_3_the_english_prompt_shown_is_the_source_message(
    qtbot, monkeypatch, tmp_path, language
):
    """SC-L10N-UI-016-3: in English the prompt is the source message, filled in."""
    shown = shown_prompt(qtbot, monkeypatch, tmp_path, language, "en")
    assert shown.startswith(f"Enable {PLUGIN_NAME} and ")
    listing = "\n".join(BULLET + name for _value, name in DECLARED)
    assert shown == prompt_template("en").replace("%1", PLUGIN_NAME).replace(
        "%2", listing
    )


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_016_3_each_catalogue_holds_one_live_prompt(code):
    """SC-L10N-UI-016-3: one live prompt per catalogue, finished, both placeholders.

    ``prompt_template`` is the oracle of the rows above; this case holds it to
    account on its own, so a catalogue that lost, duplicated or left the message
    unfinished is named without any window.
    """
    template = prompt_template(code)
    assert template.count("%1") == 1 and template.count("%2") == 1, template


def test_sc_l10n_ui_016_3_neither_earlier_english_text_is_live_in_any_catalogue(
    capsys,
):
    """SC-L10N-UI-016-3: neither earlier English source text is a live message.

    Each of the eight ``.ts`` files is read in full; a message whose source is the
    "runs sandboxed" text or the round-17 text, live, is a finding. The number of
    catalogues and of messages examined is printed and must be non-zero.
    """
    examined = {code: len(_messages(code)) for code in LANGUAGES}
    line = (
        f"catalogues examined: {len(examined)} of {EXPECTED_LANGUAGE_COUNT}; "
        f"messages examined: {sum(examined.values())}; earlier texts: "
        f"{len(EARLIER_TEXTS)}"
    )
    print(line)
    with capsys.disabled():
        print(f"[consent prompt] {line}")
    assert len(examined) == EXPECTED_LANGUAGE_COUNT
    assert all(count > 0 for count in examined.values()), examined
    assert earlier_texts_live() == []


def _scratch_catalogue(
    folder: Path, code: str, source: str, kind: Optional[str], text: str = "x"
) -> None:
    """Write a one-message catalogue for ``code`` under ``folder`` (a scratch copy)."""
    folder.mkdir(parents=True, exist_ok=True)
    attr = "" if kind is None else f' type="{kind}"'

    def escape(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace("'", "&apos;")

    (folder / f"pixelart_{code}.ts").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
        f'<TS version="2.1" language="{code}"><context><name>{CONTEXT}</name>'
        f"<message><source>{escape(source)}</source>"
        f"<translation{attr}>{escape(text)}</translation>"
        "</message></context></TS>\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "which", range(len(EARLIER_TEXTS)), ids=["sandboxed", "round-17"]
)
def test_sc_l10n_ui_016_3_a_live_earlier_text_is_found_and_named(tmp_path, which):
    """SC-L10N-UI-016-3 control: each earlier text, planted live, fails naming its file.

    A scratch catalogue under ``tmp_path`` holds the earlier text as a live message
    (unmarked, then marked ``unfinished``); the scan names the file and the context.
    The same text marked ``obsolete`` or ``vanished`` is not live and is not found.
    """
    text = EARLIER_TEXTS[which]
    for kind in (None, "unfinished"):
        folder = tmp_path / f"live-{kind}"
        _scratch_catalogue(folder, "de", text, kind)
        findings = earlier_texts_live(folder, codes=("de",))
        assert len(findings) == 1, findings
        assert "pixelart_de.ts" in findings[0] and CONTEXT in findings[0], findings
    for kind in ("obsolete", "vanished"):
        folder = tmp_path / f"dead-{kind}"
        _scratch_catalogue(folder, "de", text, kind)
        assert earlier_texts_live(folder, codes=("de",)) == []


def test_sc_l10n_ui_016_3_an_earlier_text_is_found_in_another_spelling(tmp_path):
    """SC-L10N-UI-016-3 control: a curly apostrophe or a line break does not hide it."""
    curly = OWN_COMMANDS_TEXT.replace("'", "’")
    wrapped = RUNS_SANDBOXED_TEXT.replace(" ", "\n", 3)
    for name, text in (("curly", curly), ("wrapped", wrapped)):
        folder = tmp_path / name
        _scratch_catalogue(folder, "ja", text, None)
        assert len(earlier_texts_live(folder, codes=("ja",))) == 1, name


def test_sc_l10n_ui_016_3_the_current_prompt_is_not_an_earlier_text(tmp_path):
    """SC-L10N-UI-016-3 control: the current English source is not found as old."""
    folder = tmp_path / "current"
    _scratch_catalogue(folder, "fr", prompt_template("en"), None)
    assert earlier_texts_live(folder, codes=("fr",)) == []


def test_sc_l10n_ui_016_3_the_oracle_refuses_an_unfinished_or_missing_prompt(
    tmp_path,
):
    """SC-L10N-UI-016-3 control: ``prompt_template`` fails on each broken catalogue.

    Scratch catalogues under ``tmp_path``: the prompt unfinished, translated without
    ``%2``, equal to its English source, and absent.
    """
    source = prompt_template("en")
    cases = {
        "unfinished": ("unfinished", source.replace("Enable", "Activer")),
        "no-second-placeholder": (None, "Activer %1 et rien d'autre"),
        "english-source": (None, source),
    }
    for name, (kind, text) in cases.items():
        folder = tmp_path / name
        _scratch_catalogue(folder, "fr", source, kind, text)
        with pytest.raises(AssertionError):
            prompt_template("fr", folder)
    folder = tmp_path / "unfinished-empty"
    _scratch_catalogue(folder, "fr", source, "unfinished", "")
    with pytest.raises(AssertionError, match="no translation text"):
        prompt_template("fr", folder)
    folder = tmp_path / "absent"
    _scratch_catalogue(folder, "fr", "Some other message", None)
    with pytest.raises(AssertionError, match="0 live prompt messages"):
        prompt_template("fr", folder)
    folder = tmp_path / "good"
    _scratch_catalogue(folder, "fr", source, None, "Activer %1 ? %2")
    assert prompt_template("fr", folder) == "Activer %1 ? %2"


def test_sc_l10n_ui_016_3_the_english_source_is_the_text_whose_digest_was_recorded(
    qtbot, monkeypatch, tmp_path
):
    """SC-L10N-UI-016-3: the English source message hashes to the recorded digest.

    Both readings of the one message are hashed: the source message of the English
    catalogue and the source text the panel passes to ``tr()`` when Enable is chosen.
    A stale reading hashes differently (the next case).
    """
    from_catalogue = prompt_template("en")
    from_panel = panel_prompt_source(qtbot, monkeypatch, tmp_path)
    assert digest(from_panel) == RECORDED_SHA256, f"the panel's text: {from_panel!r}"
    assert digest(from_catalogue) == RECORDED_SHA256, f"catalogue: {from_catalogue!r}"
    assert from_catalogue == from_panel


def test_sc_l10n_ui_016_3_a_stale_reading_hashes_differently():
    """SC-L10N-UI-016-3 control: an earlier text, a trailing line feed, a changed word.

    The round-17 text reproduces its recorded digest (so the hashing is the truth
    check's own), and it, the "runs sandboxed" text, the current text with a
    trailing line feed and the current text with one letter changed all differ from
    the recorded digest.
    """
    current = prompt_template("en")
    assert digest(OWN_COMMANDS_TEXT) == ROUND_17_SHA256
    assert digest(OWN_COMMANDS_TEXT) != RECORDED_SHA256
    assert digest(RUNS_SANDBOXED_TEXT) != RECORDED_SHA256
    assert digest(current + "\n") != RECORDED_SHA256
    assert digest(current.replace("trust", "Trust")) != RECORDED_SHA256
