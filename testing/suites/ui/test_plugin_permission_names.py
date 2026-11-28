"""Each declared permission is named in words, on the prompt and the panel
(REQ-L10N-UI-016).

Clause 1 of the requirement: the consent prompt and the plugin manager panel's
"Declared permissions" label name each permission in words, in the active language,
one line for each declared permission, and never by its identifier. The names are
the finished entries of the catalogue; the panel's label uses the same source
messages as the prompt.

**The member set is the plugin host's own.** Every case takes the permissions from
``list(Capability)`` of ``logic/plugins.py``; no list of names or identifiers is
copied here, so a permission added to the host without a name fails the cases that
declare every permission.

**Message identity, not text.** A recording translator wraps the panel's own
``tr()``: it logs ``(context, source, disambiguation)`` and the text of every lookup
the panel makes, and returns what the real translator returns. The message that
names a permission is the lookup whose text is the permission's line; the prompt
and the label must name each permission through the *same* message, so an entry
built from a second message whose English happens to be equal is caught.

**Languages.** A language whose names are still ``unfinished`` (or not yet in its
catalogue) is "not yet comparable": the case is skipped with that reason, counted,
and never passed. English is examined by its source messages.

Both themes (the suite's ``theme`` fixture applies to every case), offscreen.
The manifests are written to ``tmp_path``; nothing else is written and no catalogue
or product file is changed.
"""

from __future__ import annotations

import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TextIO,
    Tuple,
)

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QMessageBox

import pixelart_creator
from pixelart_creator.logic.plugins import Capability
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, LanguageManager
from pixelart_creator.ui.plugin_manager_panel import Plugin_Manager_Panel
from testing.suites.ui._automation_helpers import write_manifest

CATALOGUES = Path(pixelart_creator.__file__).parent / "i18n"
CONTEXT = "Plugin_Manager_Panel"
LANGUAGES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")
BULLET = "• "
BANNED_IN_ENGLISH = ("sandbox", "cannot reach")

#: A message as the translator sees it.
MessageId = Tuple[str, str, str]

#: The messages whose text made one line: one message when the line is named
#: through one, more when a second message with the same text took part, none when
#: no message made it.
Identity = FrozenSet[MessageId]


class Lookup(NamedTuple):
    """One lookup the panel made through its translator."""

    message: MessageId
    text: str


# --------------------------------------------------------------------------- #
# The oracle: the plugin host's permissions and the catalogue's finished text  #
# --------------------------------------------------------------------------- #


def host_permissions() -> List[Capability]:
    """Return the plugin host's own permissions, never a copied list."""
    return list(Capability)


_CATALOGUE_CACHE: Dict[str, Dict[Tuple[str, str], Optional[str]]] = {}


def finished_text(code: str, context: str, source: str) -> Optional[str]:
    """Return the finished translation of a message, or ``None`` if it is not.

    English shows the source message itself, which is its finished text.
    """
    if code == FALLBACK_LANGUAGE:
        return source
    if code not in _CATALOGUE_CACHE:
        entries: Dict[Tuple[str, str], Optional[str]] = {}
        root = ET.parse(CATALOGUES / f"pixelart_{code}.ts").getroot()
        for scope in root.iter("context"):
            name = scope.findtext("name") or ""
            for message in scope.iter("message"):
                translation = message.find("translation")
                kind = None if translation is None else translation.get("type")
                text = None if translation is None else translation.text
                done = bool(text) and kind not in ("unfinished", "obsolete", "vanished")
                entries[(name, message.findtext("source") or "")] = (
                    text if done else None
                )
        _CATALOGUE_CACHE[code] = entries
    return _CATALOGUE_CACHE[code].get((context, source))


# --------------------------------------------------------------------------- #
# The checks, written as functions so each can be planted                     #
# --------------------------------------------------------------------------- #


def bullet_lines(text: str) -> List[str]:
    """Return the permission lines of a prompt or a label: the bulleted lines."""
    return [line for line in text.split("\n") if line.startswith(BULLET)]


def line_findings(lines: Sequence[str], members: Sequence[object]) -> List[str]:
    """Return what is wrong with the permission lines shown for ``members``.

    Exactly one line for each declared permission, and no line that consists of a
    permission identifier alone. The first such line is named.
    """
    found: List[str] = []
    if len(lines) != len(members):
        found.append(f"{len(lines)} lines for {len(members)} declared permissions")
    identifiers = {str(getattr(m, "value", m)) for m in members}
    identifiers |= {value for value in (_all_identifiers())}
    for line in lines:
        if line[len(BULLET) :].strip() in identifiers:
            found.append(f"the line {line!r} consists of a permission identifier alone")
            break
    return found


def _all_identifiers() -> List[str]:
    return [member.value for member in host_permissions()]


def member_findings(members: Sequence[object], names: Dict[object, str]) -> List[str]:
    """Return a finding naming each member that has no name message."""
    return [
        f"the permission {getattr(member, 'value', member)!r} has no name message"
        for member in members
        if not names.get(member)
    ]


def duplicate_findings(code: str, names: Dict[str, str]) -> List[str]:
    """Return a finding naming the language and both permissions sharing a name."""
    found: List[str] = []
    seen: Dict[str, str] = {}
    for permission, name in names.items():
        if name in seen:
            found.append(
                f"[{code}] the permissions {seen[name]!r} and {permission!r} share "
                f"the name {name!r}"
            )
        else:
            seen[name] = permission
    return found


def identity_findings(
    prompt: Dict[str, Identity], label: Dict[str, Identity]
) -> List[str]:
    """Return a finding for each permission the two surfaces name through different
    messages.

    A line is made by the messages whose text it shows; the two surfaces must be made
    by the same set of messages, so an entry built from a second message with the
    same English is found and both messages are named.
    """
    found: List[str] = []
    for permission, prompt_messages in prompt.items():
        label_messages = label.get(permission, frozenset())
        if not prompt_messages or not label_messages:
            found.append(
                f"the permission {permission!r} is named by no message "
                f"(prompt {sorted(prompt_messages)}, label {sorted(label_messages)})"
            )
        elif prompt_messages != label_messages:
            found.append(
                f"the permission {permission!r} is named by {sorted(prompt_messages)} "
                f"on the prompt and by {sorted(label_messages)} on the label"
            )
    return found


def english_name_findings(names: Dict[str, str]) -> List[str]:
    """Return a finding for each English name holding a banned word, in any case."""
    return [
        f"the name {name!r} of {permission!r} contains {banned!r}"
        for permission, name in names.items()
        for banned in BANNED_IN_ENGLISH
        if banned in name.lower()
    ]


# --------------------------------------------------------------------------- #
# Reporting: the diagnostic line, whatever the output's encoding              #
# --------------------------------------------------------------------------- #


def write_line(line: str, stream: Optional[TextIO] = None) -> None:
    """Print ``line`` to ``stream`` (the current ``sys.stdout`` if none is given).

    A character the stream's encoding cannot hold is written as its backslash escape
    instead of raising, so the diagnostic line never decides a case. The text is
    encoded with the stream's own encoding and ``backslashreplace``, then printed;
    under a UTF-8 stream that is exactly what ``print`` writes.
    """
    target = sys.stdout if stream is None else stream
    encoding = getattr(target, "encoding", None) or "utf-8"
    print(line.encode(encoding, "backslashreplace").decode(encoding), file=target)


# --------------------------------------------------------------------------- #
# Driving the panel                                                           #
# --------------------------------------------------------------------------- #


@pytest.fixture
def language(qapp) -> Iterator[Callable[[str], None]]:
    """Install a language through the app's own manager; restore English after."""
    manager = LanguageManager(qapp)

    def install(code: str) -> None:
        assert manager.set_language(code) is True, f"{code!r} did not load"

    try:
        yield install
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


class Reading(NamedTuple):
    """What one run shows: the two surfaces and the lookups behind each."""

    prompt: str
    label: str
    prompt_lookups: List[Lookup]
    label_lookups: List[Lookup]


def read_surfaces(qtbot, monkeypatch, tmp_path, capabilities: Sequence[str]) -> Reading:
    """Declare ``capabilities`` in a manifest and read the prompt and the label.

    The manifest is written to ``tmp_path``. The panel's translator is wrapped by a
    recorder before the plugin is selected (the label) and before Enable is chosen
    (the prompt); Enable is answered with No, so no plugin is enabled.
    """
    panel = Plugin_Manager_Panel()
    qtbot.addWidget(panel)
    log: List[Lookup] = []

    def recording_tr(
        source: str, disambiguation: Optional[str] = None, n: int = -1
    ) -> str:
        text = QCoreApplication.translate(CONTEXT, source, disambiguation, n)
        log.append(Lookup((CONTEXT, source, disambiguation or ""), text))
        return text

    monkeypatch.setattr(panel, "tr", recording_tr)
    manifest = write_manifest(
        tmp_path / "all-permissions.json",
        name="all-permissions",
        capabilities=list(capabilities),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(manifest), "")),
    )
    panel._on_install()
    panel._list.setCurrentRow(-1)
    log.clear()
    panel._list.setCurrentRow(0)  # selecting the plugin sets the label
    label_lookups = list(log)
    label = panel._permissions.text()

    shown: List[str] = []

    def question(parent, title, text, *args, **kwargs):
        shown.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    log.clear()
    panel._on_enable()
    assert len(shown) == 1, f"{len(shown)} prompts were shown, not one"
    return Reading(shown[0], label, list(log), label_lookups)


def identities(
    lines: Sequence[str], lookups: Sequence[Lookup], members: Sequence[Capability]
) -> Dict[str, Identity]:
    """Return, per permission, the messages whose text is its line (empty if none).

    The permission lines come in the manifest's order; each line's name is matched
    to every lookup of the surface whose text is that name.
    """
    found: Dict[str, Identity] = {}
    for member, line in zip(members, lines):
        name = line[len(BULLET) :].strip()
        found[member.value] = frozenset(
            lookup.message for lookup in lookups if lookup.text == name
        )
    return found


def names_of(lines: Sequence[str], members: Sequence[Capability]) -> Dict[str, str]:
    """Return ``{identifier: name}`` read from the permission lines."""
    return {m.value: line[len(BULLET) :].strip() for m, line in zip(members, lines)}


def english_identities(qtbot, monkeypatch, tmp_path) -> Dict[str, Identity]:
    """Return the message that names each permission on the English prompt."""
    members = host_permissions()
    reading = read_surfaces(qtbot, monkeypatch, tmp_path, [m.value for m in members])
    return identities(bullet_lines(reading.prompt), reading.prompt_lookups, members)


def not_yet_comparable(code: str, ids: Dict[str, Identity]) -> Optional[str]:
    """Return why ``code`` cannot be compared on the names, or ``None`` if it can."""
    missing = [p for p, messages in ids.items() if not messages]
    if missing:
        if code == FALLBACK_LANGUAGE:
            return None  # the English cases fail on these, naming them
        return (
            f"no catalogue message names {missing} yet, so {code} has "
            "nothing to compare"
        )
    unfinished = sorted(
        {
            message[1]
            for messages in ids.values()
            for message in messages
            if finished_text(code, message[0], message[1]) is None
        }
    )
    if unfinished:
        return f"the name messages {unfinished} are unfinished in {code}"
    return None


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-5: the prompt                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_016_5_the_prompt_names_each_declared_permission_in_words(
    code, language, qtbot, monkeypatch, tmp_path, capsys
):
    """SC-L10N-UI-016-5: one line per declared permission, each the catalogue's finished
    name.

    A plugin declares every permission the plugin host defines. The prompt shows
    exactly one line for each, each line holds the finished translation of the
    message that names it, and none is an identifier alone. The languages and the
    permissions examined are printed, the latter equal to the host's count.
    """
    members = host_permissions()
    english = english_identities(qtbot, monkeypatch, tmp_path)
    reason = not_yet_comparable(code, english)
    if reason:
        line = (
            f"[permission names] {code}: not yet comparable, {len(members)} "
            f"rows counted and not passed ({reason})"
        )
        write_line(line)
        with capsys.disabled():
            write_line(line)
        pytest.skip(f"not yet comparable: {reason}")
    language(code)
    reading = read_surfaces(qtbot, monkeypatch, tmp_path, [m.value for m in members])
    lines = bullet_lines(reading.prompt)
    findings = line_findings(lines, members)
    ids = identities(lines, reading.prompt_lookups, members)
    for member in members:
        messages = ids[member.value]
        if not messages:
            findings.append(
                f"the permission {member.value!r} is named by no catalogue message"
            )
            continue
        shown = names_of(lines, members)[member.value]
        for message in sorted(messages):
            expected = finished_text(code, message[0], message[1])
            if shown != expected:
                findings.append(
                    f"the line of {member.value!r} holds {shown!r}, the catalogue's "
                    f"finished text of {message} is {expected!r}"
                )
    if code == FALLBACK_LANGUAGE:
        findings += english_name_findings(names_of(lines, members))
    line = (
        f"[permission names] {code}: languages examined {len(LANGUAGES)}; permissions "
        f"examined {len(lines)} (the plugin host defines {len(members)}); prompt lines "
        f"{lines!r}"
    )
    write_line(line)
    with capsys.disabled():
        write_line(line)
    assert len(members) > 0 and len(lines) == len(members)
    assert not findings, f"[{code}] the prompt: " + "; ".join(findings)


def test_sc_l10n_ui_016_5_a_plugin_that_declares_one_permission_shows_one_line(
    qtbot, monkeypatch, tmp_path
):
    """SC-L10N-UI-016-5: a plugin declaring one permission has one line on the
    prompt."""
    member = host_permissions()[0]
    reading = read_surfaces(qtbot, monkeypatch, tmp_path, [member.value])
    assert len(bullet_lines(reading.prompt)) == 1, reading.prompt


def test_sc_l10n_ui_016_5_the_listing_before_the_change_fails_naming_its_first_line():
    """SC-L10N-UI-016-5: the identifier listing, planted, fails and names the first
    line."""
    members = host_permissions()
    planted = "\n".join(f"{BULLET}{member.value}" for member in members)
    findings = line_findings(bullet_lines(planted), members)
    assert findings, "the identifier listing passed"
    assert f"{BULLET}{members[0].value}" in findings[0]
    assert "identifier alone" in findings[0]


def test_sc_l10n_ui_016_5_a_permission_without_a_name_message_fails_naming_it():
    """SC-L10N-UI-016-5: a member added to a stand-in set with no name is named."""

    class _Planted:
        value = "planted_permission"

    stand_in: List[object] = [*host_permissions(), _Planted()]
    names: Dict[object, str] = {
        member: f"name of {member.value}" for member in host_permissions()
    }
    findings = member_findings(stand_in, names)
    assert findings == ["the permission 'planted_permission' has no name message"]
    assert member_findings(host_permissions(), names) == []


def test_sc_l10n_ui_016_5_a_name_holding_a_banned_phrase_is_found_in_any_letter_case():
    """SC-L10N-UI-016-5: an English name with "sandbox" or "cannot reach" fails,
    named."""
    assert english_name_findings({"read_document": "Read the document"}) == []
    assert english_name_findings({"read_document": "Runs in a SANDBOX"})
    assert english_name_findings({"read_document": "It Cannot Reach the disk"})


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-6: one permission to a line                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_016_6_no_two_permissions_share_a_name_in_any_language(
    code, qtbot, monkeypatch, tmp_path, capsys
):
    """SC-L10N-UI-016-6: the names of the host's permissions differ within each
    language.

    The name messages are those the English prompt looks up; their finished text
    in ``code`` is read from that language's own catalogue. The names compared are
    printed, as many as the permissions, non-zero.
    """
    members = host_permissions()
    english = english_identities(qtbot, monkeypatch, tmp_path)
    unnamed = [p for p, messages in english.items() if not messages]
    if code == FALLBACK_LANGUAGE:
        assert not unnamed, f"no name message for {unnamed}: nothing to compare"
    reason = not_yet_comparable(code, english)
    if reason:
        line = (
            f"[permission names] {code}: names not yet comparable, "
            f"{len(members)} rows counted and not passed ({reason})"
        )
        write_line(line)
        with capsys.disabled():
            write_line(line)
        pytest.skip(f"not yet comparable: {reason}")
    names = {
        permission: finished_text(code, *sorted(messages)[0][:2]) or ""
        for permission, messages in english.items()
        if messages
    }
    line = (
        f"[permission names] {code}: names compared {len(names)} of "
        f"{len(members)}: {names!r}"
    )
    write_line(line)
    with capsys.disabled():
        write_line(line)
    assert len(names) == len(members) > 0
    assert duplicate_findings(code, names) == []


def test_sc_l10n_ui_016_6_one_catalogue_planted_with_a_shared_name_fails_naming_both():
    """SC-L10N-UI-016-6: two permissions given one translation fail, naming language
    and both."""
    members = host_permissions()
    planted = {member.value: f"Name {index}" for index, member in enumerate(members)}
    planted[members[1].value] = planted[members[0].value]
    findings = duplicate_findings("fr", planted)
    assert len(findings) == 1
    assert "fr" in findings[0]
    assert members[0].value in findings[0] and members[1].value in findings[0]
    assert (
        duplicate_findings("fr", {m.value: f"Name {i}" for i, m in enumerate(members)})
        == []
    )


# --------------------------------------------------------------------------- #
# SC-L10N-UI-016-8: the panel's label                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_016_8_the_label_uses_the_prompts_name_messages(
    code, language, qtbot, monkeypatch, tmp_path, capsys
):
    """SC-L10N-UI-016-8: the label shows one entry per permission, from the prompt's
    messages.

    Selecting the plugin shows exactly one entry for each declared permission;
    each entry is the finished translation of the same source message that names
    the permission on the prompt (message identity, through the recording
    translator), the label's names equal the prompt's names permission by
    permission, and none is an identifier alone.
    """
    members = host_permissions()
    english = english_identities(qtbot, monkeypatch, tmp_path)
    reason = not_yet_comparable(code, english)
    if reason:
        line = (
            f"[permission names] {code}: label not yet comparable, "
            f"{len(members)} rows counted and not passed ({reason})"
        )
        write_line(line)
        with capsys.disabled():
            write_line(line)
        pytest.skip(f"not yet comparable: {reason}")
    language(code)
    reading = read_surfaces(qtbot, monkeypatch, tmp_path, [m.value for m in members])
    label_lines = bullet_lines(reading.label)
    prompt_lines = bullet_lines(reading.prompt)
    findings = line_findings(label_lines, members)
    label_ids = identities(label_lines, reading.label_lookups, members)
    prompt_ids = identities(prompt_lines, reading.prompt_lookups, members)
    findings += identity_findings(prompt_ids, label_ids)
    label_names = names_of(label_lines, members)
    prompt_names = names_of(prompt_lines, members)
    for member in members:
        if label_names.get(member.value) != prompt_names.get(member.value):
            findings.append(
                f"the label names {member.value!r} {label_names.get(member.value)!r}, "
                f"the prompt {prompt_names.get(member.value)!r}"
            )
        for message in sorted(label_ids[member.value]):
            expected = finished_text(code, message[0], message[1])
            if label_names[member.value] != expected:
                findings.append(
                    f"the label holds {label_names[member.value]!r} for "
                    f"{member.value!r}, "
                    f"the catalogue's finished text of {message} is {expected!r}"
                )
    line = (
        f"[permission names] {code}: languages examined {len(LANGUAGES)}; "
        "label entries "
        f"examined {len(label_lines)} (the plugin host defines {len(members)}); "
        f"label {reading.label!r}"
    )
    write_line(line)
    with capsys.disabled():
        write_line(line)
    assert len(members) > 0 and len(label_lines) == len(members)
    assert not findings, f"[{code}] the label: " + "; ".join(findings)


def test_sc_l10n_ui_016_8_a_plugin_that_declares_one_permission_shows_one_entry(
    qtbot, monkeypatch, tmp_path
):
    """SC-L10N-UI-016-8: a plugin declaring one permission has one entry on the
    label."""
    member = host_permissions()[0]
    reading = read_surfaces(qtbot, monkeypatch, tmp_path, [member.value])
    assert len(bullet_lines(reading.label)) == 1, reading.label


def test_sc_l10n_ui_016_8_the_label_before_the_change_fails_naming_its_first_entry():
    """SC-L10N-UI-016-8: the identifier label, planted, fails and names the first
    entry."""
    members = host_permissions()
    planted = "\n".join(f"{BULLET}{member.value}" for member in members)
    findings = line_findings(bullet_lines(planted), members)
    assert findings and f"{BULLET}{members[0].value}" in findings[0]


def test_sc_l10n_ui_016_8_an_entry_from_a_second_message_fails_naming_both_messages():
    """SC-L10N-UI-016-8: the same English from a second message fails, naming the
    permission and both."""
    members = host_permissions()
    first: MessageId = (CONTEXT, "Read the document", "")
    prompt: Dict[str, Identity] = {
        member.value: frozenset({(CONTEXT, f"Name {index}", "")})
        for index, member in enumerate(members)
    }
    prompt[members[0].value] = frozenset({first})
    label = dict(prompt)
    second: MessageId = (
        CONTEXT,
        "Read the document",
        "label",
    )  # same English, another message
    label[members[0].value] = frozenset({first, second})
    findings = identity_findings(prompt, label)
    assert len(findings) == 1
    assert members[0].value in findings[0]
    assert str(first) in findings[0] and str(second) in findings[0]
    label[members[0].value] = frozenset({second})
    assert identity_findings(prompt, label)
    assert identity_findings(prompt, dict(prompt)) == []


def test_sc_l10n_ui_016_5_and_8_the_recorder_matches_a_line_to_its_message():
    """SC-L10N-UI-016-5 and -8 control: a lookup whose text is a line's name is its
    message."""
    members = host_permissions()
    lookups = [
        Lookup((CONTEXT, f"source {i}", ""), f"text {i}") for i in range(len(members))
    ]
    lines = [f"{BULLET}text {i}" for i in range(len(members))]
    found = identities(lines, lookups, members)
    assert [found[m.value] for m in members] == [
        frozenset({lk.message}) for lk in lookups
    ]
    unmatched = identities([f"{BULLET}{members[0].value}"], lookups, members)
    assert unmatched[members[0].value] == frozenset()
    twice = lookups + [Lookup((CONTEXT, "source 0", "label"), "text 0")]
    both = identities(lines, twice, members)[members[0].value]
    assert both == frozenset({lookups[0].message, (CONTEXT, "source 0", "label")})


def test_sc_l10n_ui_016_5_6_and_8_the_line_is_written_whole_to_a_cp1252_stream():
    """SC-L10N-UI-016-5, -6 and -8: a line holding Cyrillic, Han, Hangul and kana is
    written whole to a cp1252 stream, without raising.

    The stream is a text wrapper over a byte buffer, never the console. Each
    character cp1252 can hold (here the e acute and the euro sign) arrives
    unchanged; each one it cannot hold arrives as its backslash escape.
    """
    held = "[permission names] ru Ж zh 读 ko 한 ja あ fr é €"
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, "cp1252", newline="\n", write_through=True)
    write_line(held, stream)
    written = buffer.getvalue()
    assert written == (
        b"[permission names] ru \\u0416 zh \\u8bfb ko \\ud55c ja \\u3042 fr "
        b"\xe9 \x80\n"
    )
    assert written.decode("cp1252").endswith("fr é €\n")
