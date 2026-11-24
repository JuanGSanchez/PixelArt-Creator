"""The release notes state how the six new languages were reviewed, and one limit.

(REQ-L10N-BUILD-003, SC-L10N-BUILD-003-2, SC-L10N-UI-001-5.)

Three statements about ``CHANGELOG.md`` are checked, each on the real file and on
planted copies.

* **Where the notes live.** ``git ls-files`` lists exactly one changelog, the root
  ``CHANGELOG.md``, and ``docs/CHANGELOG.md`` is not tracked. The answer comes from
  git and never from the file system: the working copy of a product checkout can
  hold an ignored, untracked ``docs/CHANGELOG.md`` (``docs/*`` is ignored), and a
  check of the disk would trip on it.
* **The review statement.** The section that ships the six languages says there was
  no native-speaker review and invites corrections. That section is ``Unreleased``
  until the release preparation promotes it, and ``[0.5.0]`` afterwards; when both
  exist the promoted one is read. No such section fails.
* **The known limit.** The same section holds, word for word, the sentence that
  says the Undo and Redo names keep the language that was active when the action
  was performed. "Word for word" binds the words and characters, not where the
  source wraps: Markdown renders a single line break inside a paragraph as a
  space, so each run of spaces and tabs that holds at most one line break counts as
  one space. A blank line ends a paragraph and is NOT collapsed, and nothing else
  is normalised: no case folding, no Unicode normalisation, no change to the
  punctuation.

Every check runs the same function on the real file and on the planted copies, so
a function that says "yes" to everything, or "no", fails at once: a copy with the
statement removed, a copy with it moved to a tracked ``docs/CHANGELOG.md``, an
untracked ``docs/CHANGELOG.md`` that must change nothing, and four planted copies of
the sentence (wrapped across two lines of one bullet, one word changed, split by a
blank line, the full stop after "at the time" removed). Each control prints its
result.

The real-file cases read the repository this file sits in; ``CHANGELOG_L10N_REPO``
points them at another checkout. The files are only ever READ. The scratch
repositories live under ``tmp_path`` and only ``init``, ``config``, ``add`` and
``ls-files`` are run in them; nothing here writes to the repository under test.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

#: Repo root: testing/suites/release/test_changelog_l10n_disclaimer.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Environment variable that points the real-file cases at another checkout.
REPO_ENV = "CHANGELOG_L10N_REPO"

#: The one changelog the product tracks, and the one it must not.
CHANGELOG = "CHANGELOG.md"
DOCS_CHANGELOG = "docs/CHANGELOG.md"

#: Section names that can ship the six languages, in the order they are preferred:
#: the promoted release first, the running ``Unreleased`` section before it.
SHIPPING_SECTIONS = ("0.5.0", "Unreleased")

#: The languages the shipping section must name (it is the section that ships them).
LANGUAGES = ("French", "German", "Russian", "Chinese", "Korean", "Japanese")

#: The known-limit sentence: the four lines of the requirement's block quote, each
#: with its leading ``> `` removed, joined by one space.
KNOWN_LIMIT = (
    "Known limitation: if you switch the interface language while the app is "
    "running, the Undo and Redo commands keep showing the names of actions you "
    "performed before the switch in the language that was active at the time. "
    "Actions you perform after the switch are named in the new language."
)

#: The review statement as the model changelog of the controls words it. The real
#: file is matched by the patterns below, not by this string.
REVIEW_STATEMENT = (
    "The six new translations had no native-speaker review. Corrections are "
    "invited: if a translation reads wrongly to you, please open an issue."
)

#: "There was no native-speaker review", in either of its natural wordings.
NO_REVIEW = re.compile(
    r"\bno native[- ]speaker review\b"
    r"|\bnot (?:been )?reviewed by native[- ]speakers?\b",
    re.IGNORECASE,
)

#: "Corrections are invited", in either of its natural wordings.
INVITES_CORRECTIONS = re.compile(
    r"\bcorrections? (?:are |is )?(?:invited|welcome)\b"
    r"|\binvit\w* (?:\w+ )?corrections?\b",
    re.IGNORECASE,
)

#: A file name that is a changelog: ``CHANGELOG``, ``changelog.rst``, ...
_CHANGELOG_NAME = re.compile(r"changelog(\.[a-z0-9]+)?", re.IGNORECASE)

#: Every level-2 heading; ``title`` is what follows the two hashes.
_H2 = re.compile(r"^##[ \t]+(?P<title>[^\r\n]*)", re.MULTILINE)

GIT_TIMEOUT_S = 120

#: Git variables that would redirect a scratch repository to another one.
_GIT_REDIRECTS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
)


# --- git --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git -C repo ...`` and return the finished process (no exception)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REDIRECTS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=GIT_TIMEOUT_S,
        check=False,
    )


def _ok(done: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    """Return a git call that must have succeeded."""
    assert done.returncode == 0, "git failed: %s %s" % (done.args, done.stderr.strip())
    return done


def tracked_changelogs(repo: Path) -> list[str]:
    """Every changelog git tracks in ``repo``, by path, from ``git ls-files``.

    A changelog is any tracked file whose name is ``changelog`` with or without one
    extension, in any case and in any folder. The answer is git's: the working
    tree is never consulted. A repository git cannot list is an error, not an
    empty list.
    """
    listing = _ok(_git(repo, "ls-files", "-z")).stdout
    return sorted(
        path
        for path in listing.split("\0")
        if path and _CHANGELOG_NAME.fullmatch(PurePosixPath(path).name)
    )


def check_tracked(repo: Path) -> tuple[str, ...]:
    """The problems with where ``repo`` keeps its changelog; empty when none."""
    tracked = tracked_changelogs(repo)
    problems: list[str] = []
    if CHANGELOG not in tracked:
        problems.append(
            "the root %s is not tracked (tracked: %s)" % (CHANGELOG, tracked)
        )
    if DOCS_CHANGELOG in tracked:
        problems.append("%s is tracked" % DOCS_CHANGELOG)
    others = [p for p in tracked if p not in (CHANGELOG, DOCS_CHANGELOG)]
    if others:
        problems.append("other changelogs are tracked: %s" % others)
    return tuple(problems)


# --- the text ---------------------------------------------------------------------


def soft_breaks_to_spaces(text: str) -> str:
    """Make each run of spaces and tabs that holds at most one line break one space.

    A run is a maximal stretch of spaces, tabs and line-break characters. A run
    holding two or more line breaks is a blank line: it ends a paragraph, so it is
    left exactly as it is. Nothing outside such runs is touched.
    """

    def one_space(run: re.Match[str]) -> str:
        return " " if run.group().count("\n") <= 1 else run.group()

    return re.sub(r"[ \t\r\n]+", one_space, text)


@dataclass(frozen=True)
class Section:
    """One ``## [name]`` section of a changelog."""

    name: str
    heading: str
    text: str


def sections(text: str) -> list[Section]:
    """Split a changelog at its level-2 headings (the heading line starts each)."""
    found = list(_H2.finditer(text))
    out: list[Section] = []
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        title = match.group("title").strip()
        bracketed = re.match(r"\[([^\]]+)\]", title)
        out.append(
            Section(
                bracketed.group(1) if bracketed else title,
                "## " + title,
                text[match.start() : end],
            )
        )
    return out


def _shipping_section(text: str) -> tuple[Section | None, list[str]]:
    """The section that ships the six languages, and the problems finding it."""
    by_name: dict[str, Section] = {}
    for entry in sections(text):
        by_name.setdefault(entry.name, entry)
    for name in SHIPPING_SECTIONS:
        section = by_name.get(name)
        if section is None:
            continue
        missing = [lang for lang in LANGUAGES if lang not in section.text]
        if missing:
            return section, [
                "the section %s does not name the languages it ships: %s"
                % (section.heading, ", ".join(missing))
            ]
        return section, []
    return None, [
        "no section named %s was found (sections: %s)"
        % (" or ".join(SHIPPING_SECTIONS), [s.name for s in sections(text)])
    ]


def _sentences(flat: str) -> list[str]:
    """The sentences of text that went through ``soft_breaks_to_spaces``."""
    out: list[str] = []
    for piece in re.split(r"\n+|(?<=[.!?])[ \t]+", flat):
        piece = re.sub(r"^[ \t]*(?:[-*+][ \t]+)?", "", piece).strip()
        if piece:
            out.append(piece)
    return out


@dataclass(frozen=True)
class Finding:
    """What one check found: the section read, what matched, and what is wrong."""

    heading: str
    matched: tuple[str, ...]
    problems: tuple[str, ...]


def check_review_statement(text: str) -> Finding:
    """The shipping section says there was no native-speaker review and invites
    corrections."""
    section, problems = _shipping_section(text)
    if section is None:
        return Finding("-", (), tuple(problems))
    sentences = _sentences(soft_breaks_to_spaces(section.text))
    review = tuple(s for s in sentences if NO_REVIEW.search(s))
    invites = tuple(s for s in sentences if INVITES_CORRECTIONS.search(s))
    if not review:
        problems.append(
            "no sentence of %s states that there was no native-speaker review"
            % section.heading
        )
    if not invites:
        problems.append("no sentence of %s invites corrections" % section.heading)
    matched = review + tuple(s for s in invites if s not in review)
    return Finding(section.heading, matched, tuple(problems))


def check_known_limit(text: str) -> Finding:
    """The shipping section holds the known-limit sentence, soft breaks aside."""
    section, problems = _shipping_section(text)
    if section is None:
        return Finding("-", (), tuple(problems))
    if KNOWN_LIMIT not in soft_breaks_to_spaces(section.text):
        problems.append(
            "the known-limit sentence is not in %s, word for word" % section.heading
        )
        return Finding(section.heading, (), tuple(problems))
    return Finding(section.heading, (KNOWN_LIMIT,), tuple(problems))


def read_root_changelog(repo: Path) -> tuple[Path, str]:
    """The root changelog's path and its text, read as bytes (no newline change)."""
    path = repo / CHANGELOG
    if not path.is_file():
        return path, ""
    return path, path.read_bytes().decode("utf-8")


def check_repo(repo: Path) -> tuple[str, ...]:
    """Every problem with ``repo``'s changelog: where it lives and what it says."""
    _, text = read_root_changelog(repo)
    return (
        check_tracked(repo)
        + check_review_statement(text).problems
        + check_known_limit(text).problems
    )


# --- planted copies -----------------------------------------------------------------


def _model(
    *,
    heading: str = "## [Unreleased]",
    lead: str = "",
    review: str | None = REVIEW_STATEMENT,
    limit: str | None = KNOWN_LIMIT,
    older: str = "",
) -> str:
    """A model changelog; each argument plants one variation.

    ``heading`` heads the section that ships the languages, ``lead`` is a section
    placed above it, ``review`` and ``limit`` are the two bullets (``None`` leaves
    one out) and ``older`` is extra text in the ``[0.4.1]`` section.
    """
    lines = [
        "# Changelog",
        "",
        "All notable changes to this project are documented in this file.",
        "",
    ]
    if lead:
        lines += [lead.rstrip("\n"), ""]
    lines += [
        heading,
        "",
        "### Added",
        "",
        "- Six more interface languages: French, German, Russian, Simplified "
        "Chinese, Korean and Japanese.",
        "",
        "### Known limitations",
        "",
    ]
    if review is not None:
        lines.append("- " + review)
    if limit is not None:
        lines.append("- " + limit)
    lines += ["", "## [0.4.1] - 2026-11-14", "", "### Changed", ""]
    lines.append("- The minimum supported Python is raised.")
    if older:
        lines.append(older.rstrip("\n"))
    return "\n".join(lines) + "\n"


def _plant(text: str, old: str, new: str) -> str:
    """Replace ``old`` by ``new`` once, and fail if there was nothing to replace."""
    assert old in text, "the planted change found nothing to change: %r" % (old,)
    return text.replace(old, new, 1)


def _show(label: str, problems: tuple[str, ...], must_fail: bool) -> None:
    """Print one control's result and assert it is the one the control requires."""
    if problems:
        print("control %-46s FAILED (%s)" % (label, problems[0]))
    else:
        print("control %-46s PASSED" % label)
    if must_fail:
        assert problems, "control %r must fail and passed" % label
    else:
        assert not problems, "control %r must pass and failed: %s" % (label, problems)


def _scratch(
    root: Path, tracked: Mapping[str, str], untracked: Mapping[str, str]
) -> Path:
    """A scratch repository: ``tracked`` files are added, ``untracked`` only written.

    ``docs/*`` is ignored, as in the product, so a tracked ``docs/`` file is added
    with force and an untracked one stays ignored.
    """
    root.mkdir(parents=True)
    _ok(_git(root, "init", "-q"))
    _ok(_git(root, "config", "core.autocrlf", "false"))
    (root / ".gitignore").write_bytes(b"docs/*\n")
    for name, text in {**tracked, **untracked}.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    for name in tracked:
        _ok(_git(root, "add", "-f", "--", name))
    return root


def _repo_under_test() -> Path:
    override = os.environ.get(REPO_ENV)
    return Path(override) if override else REPO_ROOT


# --- the real repository --------------------------------------------------------------


def test_one_changelog_is_tracked_and_it_is_the_root_one():
    """SC-L10N-BUILD-003-2: ``git ls-files`` lists the root changelog and only it."""
    repo = _repo_under_test()
    tracked = tracked_changelogs(repo)
    print("repository: %s" % repo)
    print("git ls-files changelogs: %s" % tracked)
    print("%s tracked: %s" % (DOCS_CHANGELOG, DOCS_CHANGELOG in tracked))
    assert tracked == [CHANGELOG], check_tracked(repo)
    assert not check_tracked(repo)


def test_the_shipping_section_states_no_native_speaker_review_and_invites_corrections():
    """SC-L10N-BUILD-003-2: no native-speaker review is stated, corrections invited."""
    path, text = read_root_changelog(_repo_under_test())
    found = check_review_statement(text)
    print("file read: %s" % path)
    print("section: %s" % found.heading)
    for sentence in found.matched:
        print("matched: %s" % sentence)
    assert not found.problems, found.problems
    assert found.matched


def test_the_shipping_section_holds_the_known_limit_sentence_word_for_word():
    """SC-L10N-UI-001-5: the section holds the known-limit sentence, verbatim."""
    path, text = read_root_changelog(_repo_under_test())
    found = check_known_limit(text)
    print("file read: %s" % path)
    print("section: %s" % found.heading)
    for sentence in found.matched:
        print("matched: %s" % sentence)
    assert not found.problems, found.problems
    assert found.matched == (KNOWN_LIMIT,)


# --- the constant -----------------------------------------------------------------


def test_the_known_limit_constant_is_one_line_with_the_declared_ends():
    """SC-L10N-UI-001-5: the constant is one line of single-spaced words."""
    print("constant: %s" % KNOWN_LIMIT)
    assert KNOWN_LIMIT.startswith("Known limitation: if you switch")
    assert KNOWN_LIMIT.endswith("named in the new language.")
    assert "\n" not in KNOWN_LIMIT and "  " not in KNOWN_LIMIT
    assert KNOWN_LIMIT == KNOWN_LIMIT.strip()


# --- controls on the text: the known limit ----------------------------------------


def test_control_the_model_passes_and_a_wrapped_bullet_passes():
    """SC-L10N-UI-001-5 control: a sentence wrapped inside one bullet passes."""
    _show("model changelog", check_known_limit(_model()).problems, must_fail=False)
    wrapped = _plant(KNOWN_LIMIT, " and Redo", "\n  and Redo")
    text = _model(limit=wrapped)
    assert "\n  and Redo" in text
    _show("wrapped across two lines", check_known_limit(text).problems, must_fail=False)
    tabbed = _plant(KNOWN_LIMIT, " and Redo", " \t\n\t and Redo")
    _show(
        "wrapped, tabs and spaces around break",
        check_known_limit(_model(limit=tabbed)).problems,
        must_fail=False,
    )
    crlf = _model(limit=wrapped).replace("\n", "\r\n")
    _show("wrapped, CRLF line ends", check_known_limit(crlf).problems, must_fail=False)


def test_control_one_word_changed_fails():
    """SC-L10N-UI-001-5 control: one word of the sentence changed fails."""
    changed = _plant(KNOWN_LIMIT, "keep showing", "keep displaying")
    found = check_known_limit(_model(limit=changed))
    _show("one word changed", found.problems, must_fail=True)
    assert "not in" in found.problems[0]


def test_control_a_blank_line_inside_the_sentence_fails():
    """SC-L10N-UI-001-5 control: a sentence split by a blank line fails."""
    split = _plant(KNOWN_LIMIT, " and Redo", "\n\n  and Redo")
    _show(
        "split by a blank line",
        check_known_limit(_model(limit=split)).problems,
        must_fail=True,
    )
    spaced = _plant(KNOWN_LIMIT, " and Redo", "  \n \t\n  and Redo")
    _show(
        "split by a blank line holding spaces",
        check_known_limit(_model(limit=spaced)).problems,
        must_fail=True,
    )


def test_control_the_full_stop_after_at_the_time_removed_fails():
    """SC-L10N-UI-001-5 control: punctuation is not normalised."""
    stopless = _plant(KNOWN_LIMIT, "at the time.", "at the time")
    _show(
        "full stop after 'at the time' removed",
        check_known_limit(_model(limit=stopless)).problems,
        must_fail=True,
    )
    other = _plant(KNOWN_LIMIT, "Undo and Redo", "undo and redo")
    _show(
        "case changed",
        check_known_limit(_model(limit=other)).problems,
        must_fail=True,
    )


def test_control_the_sentence_left_out_or_in_the_wrong_section_fails():
    """SC-L10N-UI-001-5 control: absent, or in an older section only, fails."""
    _show("sentence left out", check_known_limit(_model(limit=None)).problems, True)
    older_only = _model(limit=None, older="- " + KNOWN_LIMIT)
    _show(
        "sentence only in the [0.4.1] section",
        check_known_limit(older_only).problems,
        True,
    )


# --- controls on the text: the review statement ------------------------------------


def test_control_the_review_statement_passes_and_removed_or_halved_fails():
    """SC-L10N-BUILD-003-2 control: the statement passes; any part left out fails."""
    found = check_review_statement(_model())
    _show("review statement present", found.problems, must_fail=False)
    assert len(found.matched) == 2
    _show(
        "review statement removed",
        check_review_statement(_model(review=None)).problems,
        True,
    )
    no_invite = "The six new translations had no native-speaker review."
    _show(
        "invitation removed",
        check_review_statement(_model(review=no_invite)).problems,
        True,
    )
    no_claim = "Corrections are invited: if a translation reads wrongly, open an issue."
    _show(
        "claim removed", check_review_statement(_model(review=no_claim)).problems, True
    )
    wrapped = _plant(REVIEW_STATEMENT, " Corrections", "\n  Corrections")
    _show(
        "statement wrapped",
        check_review_statement(_model(review=wrapped)).problems,
        False,
    )


def test_control_the_statement_in_an_older_section_does_not_count():
    """SC-L10N-BUILD-003-2 control: the section that ships the languages is read."""
    older = _model(review=None, older="- " + REVIEW_STATEMENT)
    _show(
        "statement only in the [0.4.1] section",
        check_review_statement(older).problems,
        True,
    )
    no_section = _model(heading="## [0.4.2] - 2026-11-20")
    found = check_review_statement(no_section)
    _show("no shipping section", found.problems, must_fail=True)
    assert "no section named" in found.problems[0]
    assert check_known_limit(no_section).problems


def test_control_the_promoted_section_is_read_once_it_exists():
    """SC-L10N-BUILD-003-2 control: [0.5.0] after promotion, Unreleased before."""
    promoted = _model(heading="## [0.5.0] - 2026-12-01", lead="## [Unreleased]\n")
    found = check_review_statement(promoted)
    _show("promoted: statement in [0.5.0]", found.problems, must_fail=False)
    assert found.heading.startswith("## [0.5.0]")
    _show(
        "promoted: known limit in [0.5.0]", check_known_limit(promoted).problems, False
    )
    stale_lead = "## [Unreleased]\n\n- %s\n- %s\n" % (REVIEW_STATEMENT, KNOWN_LIMIT)
    stale = _model(
        heading="## [0.5.0] - 2026-12-01", lead=stale_lead, review=None, limit=None
    )
    _show(
        "promoted: statements left in Unreleased",
        check_review_statement(stale).problems,
        True,
    )
    _show("promoted: limit left in Unreleased", check_known_limit(stale).problems, True)
    unreleased = check_review_statement(_model())
    assert unreleased.heading == "## [Unreleased]"


# --- controls on git: where the changelog lives -----------------------------------


def test_control_an_untracked_docs_changelog_on_disk_changes_nothing(tmp_path: Path):
    """SC-L10N-BUILD-003-2 control: the answer is git's, not the disk's."""
    good = {CHANGELOG: _model()}
    plain = _scratch(tmp_path / "plain", good, {})
    with_docs = _scratch(
        tmp_path / "with-docs", good, {DOCS_CHANGELOG: "# a stale private copy\n"}
    )
    assert (with_docs / DOCS_CHANGELOG).is_file()
    assert tracked_changelogs(with_docs) == tracked_changelogs(plain) == [CHANGELOG]
    _show("scratch repository, no docs changelog", check_repo(plain), must_fail=False)
    _show("untracked docs/CHANGELOG.md on disk", check_repo(with_docs), must_fail=False)
    assert check_repo(with_docs) == check_repo(plain)


def test_control_a_tracked_docs_changelog_fails(tmp_path: Path):
    """SC-L10N-BUILD-003-2 control: a second, tracked changelog fails."""
    repo = _scratch(
        tmp_path / "two", {CHANGELOG: _model(), DOCS_CHANGELOG: _model()}, {}
    )
    assert tracked_changelogs(repo) == [CHANGELOG, DOCS_CHANGELOG]
    problems = check_repo(repo)
    _show("tracked docs/CHANGELOG.md beside the root", problems, must_fail=True)
    assert any(DOCS_CHANGELOG in p and "tracked" in p for p in problems)


def test_control_the_statement_moved_to_a_tracked_docs_changelog_fails(tmp_path: Path):
    """SC-L10N-BUILD-003-2 control: the statements in docs/CHANGELOG.md do not count."""
    bare = _model(review=None, limit=None)
    repo = _scratch(tmp_path / "moved", {CHANGELOG: bare, DOCS_CHANGELOG: _model()}, {})
    problems = check_repo(repo)
    _show("statements moved to tracked docs/CHANGELOG.md", problems, must_fail=True)
    assert any("no native-speaker review" in p for p in problems)
    assert any("known-limit" in p for p in problems)
    assert any(DOCS_CHANGELOG in p for p in problems)


def test_control_the_root_changelog_must_be_tracked_not_merely_present(tmp_path: Path):
    """SC-L10N-BUILD-003-2 control: a file on disk that git does not track fails."""
    present = _scratch(tmp_path / "present", {}, {CHANGELOG: _model()})
    assert (present / CHANGELOG).is_file()
    problems = check_repo(present)
    _show("root CHANGELOG.md on disk, not tracked", problems, must_fail=True)
    assert "is not tracked" in problems[0]
    empty = _scratch(tmp_path / "empty", {}, {})
    _show("no changelog at all", check_repo(empty), must_fail=True)
    other = _scratch(
        tmp_path / "other", {CHANGELOG: _model(), "doc/changelog.rst": "x"}, {}
    )
    _show("another changelog elsewhere", check_repo(other), must_fail=True)


def test_control_a_directory_git_cannot_list_is_an_error(tmp_path: Path):
    """SC-L10N-BUILD-003-2 control: no repository is a failure, never an empty list."""
    nowhere = tmp_path / "not-a-repository"
    nowhere.mkdir()
    ceiling = _git(nowhere, "rev-parse", "--is-inside-work-tree")
    if ceiling.returncode == 0:
        pytest.fail("the scratch folder sits inside a repository: %s" % nowhere)
    with pytest.raises(AssertionError):
        tracked_changelogs(nowhere)
