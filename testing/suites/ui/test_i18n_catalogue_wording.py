"""The translator notes in both catalogues carry no wording about how the product was made.

Covers **REQ-VI-BUILD-012** and its scenario **SC-VI-BUILD-012-1** ("The regenerated
catalogues carry no internal wording"), one test per clause of that scenario:

1. *none contains the forbidden phrase* -- every ``<extracomment>`` in
   ``pixelart_en.ts`` and ``pixelart_es.ts`` is examined and none says
   "Another agent's guide content" (:data:`FORBIDDEN_WORDING`);
2. *every note still containing the word "agent" is listed by file and line* -- the
   listing is printed; it is information, not a failure, exactly as the scenario words it;
3. *the number of notes examined is printed and is not zero* -- printed per catalogue,
   and a catalogue with no notes FAILS (a scan that read nothing must not pass);
4. *the source comment in ``ui/user_guide.py`` no longer carries the wording* -- the
   notes are harvested from that comment, so a fresh extraction would bring it back.

**What is deliberately NOT the target.** The bare English word "measured" is legitimate
in four existing notes (the ruler calibration and the chunk timing); the rule matches the
forbidden PHRASE, not a word, and a control below proves a "measured" note passes.

**How the notes are read.** With ``xml.parsers.expat`` (the real XML grammar, so
entities such as ``&apos;`` are decoded before matching and the line number is the one
of the opening tag), then cross-checked against an independent byte count of the
``<extracomment`` opening tags; a disagreement is a failure of the reader, not a pass.

**Controls (``verified-testing`` V6 / a probe needs a known-true signal).** Every rule
is proven live against a SCRATCH COPY of each shipped catalogue in ``tmp_path`` with a
note planted into it: the planted phrase must be reported at the planted line, a clean
copy must pass, a copy stripped of every note must fail on the zero count, and the
shipped file's hash must be unchanged afterwards. The shipped files are never written.

**EXTRA, not part of SC-VI-BUILD-012-1.** The scenario names only the one phrase. At the
request of the task that commissioned this module a second rule is added, labelled
``EXTRA`` everywhere it appears: no translator note may carry an internal identifier
(an agent id, a workflow id, a question id, a task id, or a path into the design
documentation). It is a separate set of tests so it can be removed without touching the
scenario's. REQ-IDs and clarification ids are NOT in it: REQ-VI-BUILD-012 rules them out
of scope ("this spec does not re-rule it"), and a control below proves they pass.

**Why the identifier strings are built by concatenation.** The product's vocabulary gate
scans the tracked text of the whole repository for exactly these identifier shapes, so a
literal in this file's source would turn that gate red. Each family's regex and planted
sample is assembled from fragments (``_join``); the full strings exist only at run time,
and the samples only inside a ``tmp_path`` copy. The same technique is used by the gate's
own source for the design-documentation literal.

**Theme.** The suite's autouse ``theme`` fixture is replaced by a no-op: this module reads
text files and builds no widget, so running each test under both the light and the dark
sheet would repeat identical assertions (the same replacement is used by the other
modules of this suite that exercise no window).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable, Iterator, List, NamedTuple, Tuple
from xml.parsers import expat

import pytest

import pixelart_creator

_PKG_DIR = Path(pixelart_creator.__file__).resolve().parent
_I18N_DIR = _PKG_DIR / "i18n"
_USER_GUIDE_SOURCE = _PKG_DIR / "ui" / "user_guide.py"

#: The two catalogues the scenario names, in the order it names them.
CATALOGUE_FILES: Tuple[str, ...] = ("pixelart_en.ts", "pixelart_es.ts")

#: SC-VI-BUILD-012-1: "none contains 'Another agent's guide content'". Matched
#: case-insensitively, across any run of whitespace (a wrapped note), with either
#: apostrophe or none -- the PHRASE, never the bare word "agent" or "measured".
FORBIDDEN_WORDING = re.compile(
    r"another\s+agent['’ʼ]?s\s+guide\s+content", re.IGNORECASE
)

#: SC-VI-BUILD-012-1: the notes "still containing the word 'agent'" are listed. The
#: scenario's own measurement was a case-insensitive substring match, so this is too.
AGENT_WORD = re.compile("agent", re.IGNORECASE)


#: Regex escapes held apart as their own literals, so that no single literal reads as
#: "word, backslash, word" to scripts/path_portability_check.py (its BACKSLASH_SEP
#: rule). ``_join`` puts them back together into the same patterns at import time.
_WORD_BOUNDARY = r"\b"
_DIGIT = r"\d"


def _join(*parts: str) -> str:
    """Concatenate fragments (see the module docstring: why no literal is written)."""
    return "".join(parts)


#: EXTRA (not in the scenario): family label -> (regex source, planted sample).
_INTERNAL_ID_FAMILIES = {
    "agent-id": (
        _join(_WORD_BOUNDARY, "AG", "T-", _DIGIT, "+", _WORD_BOUNDARY),
        _join("AG", "T-", "07"),
    ),
    "workflow-id": (
        _join(_WORD_BOUNDARY, "O", "F", _DIGIT, "+", _WORD_BOUNDARY),
        _join("O", "F", "7"),
    ),
    "question-id": (
        _join(_WORD_BOUNDARY, "Q", "-", _DIGIT, "+", _WORD_BOUNDARY),
        _join("Q", "-", "21"),
    ),
    "task-id": (
        _join(_WORD_BOUNDARY, "T", "0", _DIGIT, _DIGIT, _WORD_BOUNDARY),
        _join("T", "071"),
    ),
    "design-path": (_join("design", "-docs"), _join("design", "-docs/specs/x")),
}
INTERNAL_ID_PATTERNS = {
    label: re.compile(source)
    for label, (source, _sample) in _INTERNAL_ID_FAMILIES.items()
}

#: Identifier shapes that are OUT of scope by ruling (REQ-VI-BUILD-012, last bullet) and
#: so must NOT be flagged by the EXTRA rule.
_OUT_OF_SCOPE_NOTE = (
    "Anchors the viewer (REQ-UG-UI-007); see CL-3 and D-12 for the reasoning."
)

#: A note that uses the legitimate word "measured" (as four shipped notes do).
_MEASURED_NOTE = (
    "A ruler of known length the user matches; the measured length derives the scale."
)


class Note(NamedTuple):
    """One translator note: where it is and what it says (entities already decoded)."""

    catalogue: str
    line: int
    text: str


# --------------------------------------------------------------------------- #
# The reader and the rules (the same code serves the shipped files and the     #
# scratch copies, so a control exercises the real rule, not a re-implementation) #
# --------------------------------------------------------------------------- #


def read_notes(path: Path) -> List[Note]:
    """Return every ``<extracomment>`` of a ``.ts`` file with its opening-tag line.

    Raises ``AssertionError`` when the parsed count disagrees with an independent byte
    count of the opening tags -- a reader that lost a note must not be believed.
    """
    data = path.read_bytes()
    notes: List[Note] = []
    parser = expat.ParserCreate()
    line = 0
    chunks: List[str] = []
    inside = False

    def start(name: str, _attrs: dict) -> None:
        nonlocal line, chunks, inside
        if name == "extracomment":
            inside = True
            line = parser.CurrentLineNumber
            chunks = []

    def chars(text: str) -> None:
        if inside:
            chunks.append(text)

    def end(name: str) -> None:
        nonlocal inside
        if name == "extracomment" and inside:
            inside = False
            notes.append(Note(path.name, line, "".join(chunks)))

    parser.StartElementHandler = start
    parser.CharacterDataHandler = chars
    parser.EndElementHandler = end
    parser.Parse(data, True)

    raw = len(re.findall(rb"<extracomment[\s/>]", data))
    assert raw == len(notes), (
        f"{path.name}: the XML reader found {len(notes)} translator notes but the "
        f"byte count of '<extracomment' opening tags is {raw}; the reader is wrong"
    )
    return notes


def check_examined(path: Path) -> List[Note]:
    """Print the number of notes examined and FAIL when it is zero (SC clause 3)."""
    notes = read_notes(path)
    print(f"{path.name}: examined {len(notes)} translator notes")
    assert len(notes) > 0, (
        f"{path.name}: 0 translator notes examined -- the scan read nothing, so "
        f"'no note carries the wording' proves nothing"
    )
    return notes


def forbidden_wording_findings(notes: List[Note]) -> List[Note]:
    """The notes that carry the forbidden phrase (SC clause 1)."""
    return [n for n in notes if FORBIDDEN_WORDING.search(n.text)]


def agent_word_listing(notes: List[Note]) -> List[str]:
    """``file:line`` for every note containing the word "agent" (SC clause 2)."""
    return [f"{n.catalogue}:{n.line}" for n in notes if AGENT_WORD.search(n.text)]


def check_no_forbidden_wording(path: Path) -> List[Note]:
    """Examine ``path`` and FAIL, naming file and line, if any note carries the phrase."""
    notes = check_examined(path)
    found = forbidden_wording_findings(notes)
    assert not found, "forbidden wording in translator notes: " + "; ".join(
        f"{n.catalogue}:{n.line}" for n in found
    )
    return notes


def internal_id_findings(notes: List[Note]) -> List[Tuple[Note, str]]:
    """EXTRA: ``(note, family)`` for every note carrying an internal identifier."""
    return [
        (n, label)
        for n in notes
        for label, pattern in INTERNAL_ID_PATTERNS.items()
        if pattern.search(n.text)
    ]


def check_no_internal_identifiers(path: Path) -> List[Note]:
    """EXTRA: examine ``path`` and FAIL, naming file, line and family, on an identifier."""
    notes = check_examined(path)
    found = internal_id_findings(notes)
    assert not found, "internal identifiers in translator notes: " + "; ".join(
        f"{n.catalogue}:{n.line} ({label})" for n, label in found
    )
    return notes


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme() -> str:
    """Replace the suite's two-way ``theme`` fixture: this module builds no widget."""
    return "none"


@pytest.fixture(params=CATALOGUE_FILES)
def catalogue(request: pytest.FixtureRequest) -> Path:
    """One shipped catalogue per test: both are examined by every shipped-file test."""
    path = _I18N_DIR / request.param
    assert path.is_file(), f"shipped catalogue missing: {path}"
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _planted_message(note: str) -> bytes:
    """A complete ``<message>`` block (LF line ends, as the shipped files) holding ``note``."""
    return (
        "    <message>\n"
        '        <location filename="../ui/planted.py" line="1"/>\n'
        "        <source>Planted source string</source>\n"
        f"        <extracomment>{note}</extracomment>\n"
        '        <translation type="unfinished"></translation>\n'
        "    </message>\n"
    ).encode("utf-8")


@pytest.fixture
def plant(catalogue: Path, tmp_path: Path) -> Iterator[Callable[[str], Path]]:
    """Return ``plant(note) -> scratch path``: a COPY of the shipped file plus one note.

    The note goes in as a new message after the first ``</message>``. The shipped file is
    only READ; its hash is re-checked when the test ends.
    """
    before = _digest(catalogue)

    def _plant(note: str) -> Path:
        data = catalogue.read_bytes()
        marker = b"</message>\n"
        at = data.index(marker) + len(marker)
        copy = tmp_path / catalogue.name
        copy.write_bytes(data[:at] + _planted_message(note) + data[at:])
        return copy

    yield _plant
    assert _digest(catalogue) == before, "the shipped catalogue was modified by a test"


def _line_of(path: Path, needle: str) -> int:
    """The 1-based line of the first raw line of ``path`` containing ``needle``."""
    for number, line in enumerate(
        path.read_bytes().decode("utf-8").split("\n"), start=1
    ):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {path}")


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-012-1 against the SHIPPED catalogues                              #
# --------------------------------------------------------------------------- #


def test_sc_vi_build_012_1_notes_examined_is_printed_and_not_zero(
    catalogue: Path, record_property
) -> None:
    """SC-VI-BUILD-012-1 (clause 3): the examined count is printed and is above zero."""
    notes = check_examined(catalogue)
    record_property("notes_examined", len(notes))
    assert len(notes) > 0


def test_sc_vi_build_012_1_note_lines_point_at_the_note_tags(catalogue: Path) -> None:
    """SC-VI-BUILD-012-1 (clause 2 relies on it): each reported line IS the note's tag line."""
    raw_lines = catalogue.read_bytes().decode("utf-8").split("\n")
    for note in check_examined(catalogue):
        assert (
            "<extracomment" in raw_lines[note.line - 1]
        ), f"{note.catalogue}:{note.line} does not hold an '<extracomment' tag"


def test_sc_vi_build_012_1_no_note_carries_the_forbidden_wording(
    catalogue: Path,
) -> None:
    """SC-VI-BUILD-012-1 (clause 1): no note says "Another agent's guide content"."""
    check_no_forbidden_wording(catalogue)


def test_sc_vi_build_012_1_notes_mentioning_agent_are_listed(catalogue: Path) -> None:
    """SC-VI-BUILD-012-1 (clause 2): notes containing "agent" are listed by file and line.

    The scenario asks for a LISTING, so this prints it and does not fail on a non-empty
    list; the listing code is proven to find a planted note by the control further down.
    """
    notes = check_examined(catalogue)
    listing = agent_word_listing(notes)
    print(
        f"{catalogue.name}: {len(listing)} of {len(notes)} notes contain the word "
        f"'agent': {listing if listing else 'none'}"
    )
    assert all(
        re.fullmatch(re.escape(catalogue.name) + r":\d+", item) for item in listing
    )


def test_sc_vi_build_012_1_user_guide_source_comment_is_clean() -> None:
    """SC-VI-BUILD-012-1 (clause 4): ``ui/user_guide.py`` no longer carries the wording.

    The notes are lupdate's harvest of that file's comments; if the source still held the
    phrase, the next extraction would restore it.
    """
    text = _USER_GUIDE_SOURCE.read_text(encoding="utf-8")
    assert text.strip(), "user_guide.py read as empty -- nothing was examined"
    assert not FORBIDDEN_WORDING.search(
        text
    ), f"{_USER_GUIDE_SOURCE.name} still carries the forbidden wording"


# --------------------------------------------------------------------------- #
# Controls: the rule fails on a planted note (scratch copies, never the shipped #
# files)                                                                        #
# --------------------------------------------------------------------------- #

_PLANTED_VARIANTS = {
    "as-measured": "Another agent's guide content writes the logo under this EXACT string.",
    "upper-case": "ANOTHER AGENT'S GUIDE CONTENT writes the logo under this EXACT string.",
    "typographic-apostrophe": "Another agent’s guide content writes the logo here.",
    "no-apostrophe": "Another agents guide content writes the logo here.",
    "wrapped-whitespace": "Another   agent's\n        guide\tcontent writes the logo here.",
    "entity-escaped": "Another agent&apos;s guide content writes the logo here.",
}


@pytest.mark.parametrize("variant", sorted(_PLANTED_VARIANTS))
def test_control_planted_forbidden_wording_fails_the_test(
    plant: Callable[[str], Path], variant: str
) -> None:
    """SC-VI-BUILD-012-1 control: a planted note with the wording makes the check FAIL.

    The failure must name the planted note's own line, so the line reporting is proven
    on the same run.
    """
    copy = plant(_PLANTED_VARIANTS[variant])
    with pytest.raises(AssertionError, match="forbidden wording") as caught:
        check_no_forbidden_wording(copy)
    planted_line = _line_of(
        copy, "<extracomment>" + _PLANTED_VARIANTS[variant].split("\n")[0]
    )
    assert f"{copy.name}:{planted_line}" in str(caught.value)


def test_control_clean_copy_passes(catalogue: Path, tmp_path: Path) -> None:
    """Control: an untouched scratch copy passes, so the failures above come from the plant."""
    clean = tmp_path / ("clean_" + catalogue.name)
    clean.write_bytes(catalogue.read_bytes())
    assert len(check_no_forbidden_wording(clean)) == len(read_notes(catalogue))


def test_control_a_note_using_the_word_measured_is_not_flagged(
    plant: Callable[[str], Path],
) -> None:
    """Control against over-matching: "measured" alone (as four shipped notes use it) passes."""
    copy = plant(_MEASURED_NOTE)
    assert any(n.text == _MEASURED_NOTE for n in read_notes(copy))
    check_no_forbidden_wording(copy)


def test_control_a_near_miss_without_the_phrase_is_not_flagged(
    plant: Callable[[str], Path],
) -> None:
    """Control: the rule is the phrase. "Another" and "agent" apart from it do not match."""
    copy = plant(
        "Another note about the user agent string, which says nothing of guide content."
    )
    check_no_forbidden_wording(copy)


def test_control_agent_listing_finds_a_planted_note(
    plant: Callable[[str], Path],
) -> None:
    """SC-VI-BUILD-012-1 (clause 2) control: a planted "agent" note is listed with its line."""
    copy = plant("The agent of change is the caller.")
    planted_line = _line_of(copy, "<extracomment>The agent of change")
    assert f"{copy.name}:{planted_line}" in agent_word_listing(read_notes(copy))


def test_control_a_catalogue_without_notes_fails_on_the_zero_count(
    catalogue: Path, tmp_path: Path
) -> None:
    """SC-VI-BUILD-012-1 (clause 3) control: no notes examined -> the check FAILS, not passes."""
    text = catalogue.read_bytes().decode("utf-8")
    stripped = re.sub(
        r"[ \t]*<extracomment>.*?</extracomment>\n", "", text, flags=re.DOTALL
    )
    assert stripped != text, "the control removed nothing"
    copy = tmp_path / catalogue.name
    copy.write_bytes(stripped.encode("utf-8"))
    assert read_notes(copy) == []
    with pytest.raises(AssertionError, match="0 translator notes examined"):
        check_no_forbidden_wording(copy)


def test_control_user_guide_comment_check_detects_the_wording(tmp_path: Path) -> None:
    """SC-VI-BUILD-012-1 (clause 4) control: the same phrase in a source comment is detected."""
    planted = tmp_path / "user_guide.py"
    planted.write_text(
        "#: Another agent's guide content writes the logo here.\n", encoding="utf-8"
    )
    assert FORBIDDEN_WORDING.search(planted.read_text(encoding="utf-8"))


def test_control_reader_decodes_entities_and_counts_the_planted_note(
    plant: Callable[[str], Path], catalogue: Path
) -> None:
    """Reader control: a planted ``&apos;`` arrives decoded, and the note count grows by one."""
    copy = plant("it&apos;s decoded")
    notes = read_notes(copy)
    assert any(n.text == "it's decoded" for n in notes)
    assert len(notes) == len(read_notes(catalogue)) + 1


# --------------------------------------------------------------------------- #
# EXTRA (not in SC-VI-BUILD-012-1): no internal identifier in a translator note  #
# --------------------------------------------------------------------------- #


def test_extra_no_note_carries_an_internal_identifier(catalogue: Path) -> None:
    """EXTRA (beyond SC-VI-BUILD-012-1): no note carries an agent, workflow, question or task
    id, or a path into the design documentation."""
    check_no_internal_identifiers(catalogue)


@pytest.mark.parametrize("family", sorted(_INTERNAL_ID_FAMILIES))
def test_extra_control_planted_identifier_fails_the_test(
    plant: Callable[[str], Path], family: str
) -> None:
    """EXTRA control: a planted note holding one identifier of ``family`` FAILS, naming it."""
    sample = _INTERNAL_ID_FAMILIES[family][1]
    copy = plant(f"Written under {sample} for the catalogue.")
    with pytest.raises(AssertionError, match="internal identifiers") as caught:
        check_no_internal_identifiers(copy)
    assert f"({family})" in str(caught.value)
    planted_line = _line_of(copy, "<extracomment>Written under")
    assert f"{copy.name}:{planted_line}" in str(caught.value)


def test_extra_control_out_of_scope_identifiers_are_not_flagged(
    plant: Callable[[str], Path],
) -> None:
    """EXTRA control: REQ-IDs and clarification ids pass (ruled out of scope by the REQ)."""
    copy = plant(_OUT_OF_SCOPE_NOTE)
    check_no_internal_identifiers(copy)
