"""Contract tests for ``packaging/check_payload.sh`` (the payload content check).

REQ-L10N-BUILD-002 (SC-L10N-BUILD-002-1: the check every distribution is put
through) and REQ-L10N-BUILD-008 (SC-L10N-BUILD-008-1's passing case and
SC-L10N-BUILD-008-2's two defects: the root ``NOTICE`` travels with every
payload). Closes the gap that the script, which CI runs on the wheel and on each
installer's unpacked payload, had no test module of its own.

Placed under ``testing/suites/deploy/`` (ADR-0043 §1: ``packaging/**`` is a
pipeline vehicle this root's owner maintains) and deliberately NOT
``@pytest.mark.integration``: the check must run on every leg of the
quality-gate matrix, the Windows leg included, because that is the only place
the "which ``bash``" question below is answered by a run and not by reading.

HOW THE SCRIPT IS DRIVEN. The script derives the repository it compares against
from its OWN location (``packaging/..``), so every case builds a throwaway
fixture repository under ``tmp_path``: a copy of the real script, the real
``pixelart_creator/fonts`` and ``pixelart_creator/themes`` files, and the real
root ``NOTICE``. A payload is a second folder holding a copy of those data
files beside a ``pixelart_creator`` folder. Each defect case starts from the
complete fixture and plants ONE defect, so a complete payload passing (the
positive control) is what makes every red case attributable to its defect.

EVERY REGRESSION CASE FAILS AGAINST A BROKEN COPY. A case that checks the script
refuses something is re-run against a copy of the script with the responsible
block neutralised (``MUTATIONS``); it must then NOT produce the refusal. Each
mutation is applied through ``_mutated_script``, which asserts the text it
replaces occurs exactly once, so a mutation can never silently do nothing and
leave a case "proven" against an unmodified script.

WHICH ``bash``. The workflows run the script with ``bash`` (``shell: bash``). On
the Windows leg that is Git for Windows' ``bash.exe``; ``bash.exe`` found on
``PATH`` may instead be the WSL launcher in ``System32`` or ``WindowsApps``,
which cannot run this script against Windows paths. ``_find_bash`` therefore
accepts a ``bash`` on ``PATH`` only when it is not one of those, then tries the
Git for Windows install next to ``git``. A leg where none is found FAILS, naming
what was looked at; it never skips (a skip would turn the Windows leg green on
an unexercised check).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pytest

from .conftest import REPO_ROOT

REAL_SCRIPT = REPO_ROOT / "packaging" / "check_payload.sh"
REAL_PKG = REPO_ROOT / "pixelart_creator"
REAL_NOTICE = REPO_ROOT / "NOTICE"
DATA_DIRS = ("fonts", "themes")

#: How many of the real theme files a fixture carries. The script's per-file
#: ``cmp`` is slow under Git Bash on Windows (about 50 ms a process), and the
#: block under test does not depend on how many theme files there are: every
#: font file and the first few theme files are enough to exercise the loop.
THEME_FILES_IN_A_FIXTURE = 4

#: The FONTLOG that must travel with the CJK families. A stub is written into a
#: fixture whose source tree does not carry it yet, so this module tests the
#: SCRIPT and not the state of the tree it happens to sit in.
CJK_FONTLOG = "FONTLOG-CJK.txt"

_WSL_LAUNCHER_PARTS = ("system32", "windowsapps")


# --------------------------------------------------------------------------- #
# Resolving the bash the workflows use
# --------------------------------------------------------------------------- #
def _is_wsl_launcher(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(f"/{part}/" in lowered for part in _WSL_LAUNCHER_PARTS)


def _find_bash() -> Tuple[Optional[str], List[str]]:
    """Return (bash path or None, what was looked at)."""
    looked: List[str] = []
    on_path = shutil.which("bash")
    looked.append(f"bash on PATH: {on_path}")
    if on_path and not _is_wsl_launcher(on_path):
        return on_path, looked
    if os.name == "nt":
        git = shutil.which("git")
        looked.append(f"git on PATH: {git}")
        candidates: List[Path] = []
        if git:
            git_root = Path(git).resolve().parent.parent
            candidates += [git_root / "bin" / "bash.exe", git_root / "usr" / "bin" / "bash.exe"]
        for var in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                candidates.append(Path(base) / "Git" / "bin" / "bash.exe")
        for cand in candidates:
            looked.append(f"candidate: {cand}")
            if cand.is_file():
                return str(cand), looked
    return None, looked


@pytest.fixture(scope="module")
def bash() -> str:
    found, looked = _find_bash()
    if found is None:
        pytest.fail(
            "no usable bash found (Git Bash on Windows, bash elsewhere); "
            "check_payload.sh cannot be exercised, and a skip would hide that. "
            "Looked at: " + "; ".join(looked),
            pytrace=False,
        )
    return found


# --------------------------------------------------------------------------- #
# Fixture repositories and payloads
# --------------------------------------------------------------------------- #
def _real_data_files() -> List[Path]:
    """Every real font file and the first few real theme files, in a fixed order."""
    files: List[Path] = []
    for data in DATA_DIRS:
        found = sorted(p for p in (REAL_PKG / data).rglob("*") if p.is_file())
        files += found if data == "fonts" else found[:THEME_FILES_IN_A_FIXTURE]
    return files


def _copy_data(src_pkg: Path, dst_pkg: Path) -> int:
    """Copy the fixture's data files under dst_pkg; return how many."""
    count = 0
    for data in DATA_DIRS:
        found = sorted(p for p in (src_pkg / data).rglob("*") if p.is_file())
        for src in found if data == "fonts" else found[:THEME_FILES_IN_A_FIXTURE]:
            dst = dst_pkg / src.relative_to(src_pkg)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            count += 1
    return count


def _ensure_cjk_fontlog(pkg: Path) -> None:
    target = pkg / "fonts" / CJK_FONTLOG
    if not target.is_file():
        target.write_bytes(b"stand-in FONTLOG-CJK.txt for the fixture\n")


def _make_repo(root: Path, script_bytes: bytes) -> Path:
    """A fixture repository: the script under test, the data files, the NOTICE."""
    (root / "packaging").mkdir(parents=True)
    (root / "packaging" / "check_payload.sh").write_bytes(script_bytes)
    _copy_data(REAL_PKG, root / "pixelart_creator")
    _ensure_cjk_fontlog(root / "pixelart_creator")
    (root / "NOTICE").write_bytes(REAL_NOTICE.read_bytes())
    return root


class Fixture:
    """One repository and one payload built from it, plus the defect hooks."""

    def __init__(self, base: Path, script_bytes: bytes) -> None:
        self.repo = _make_repo(base / "repo", script_bytes)
        self.parent = base / "payload"
        self.pkg = self.parent / "pixelart_creator"
        self.files = _copy_data(self.repo / "pixelart_creator", self.pkg)
        self.notice = self.repo / "NOTICE"
        # The complete payload: NOTICE where the installers place it.
        self.put_notice(self.parent / "NOTICE")

    def put_notice(self, where: Path, data: Optional[bytes] = None) -> Path:
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_bytes(self.notice.read_bytes() if data is None else data)
        return where

    def drop_notice(self) -> None:
        (self.parent / "NOTICE").unlink()

    @property
    def script(self) -> Path:
        return self.repo / "packaging" / "check_payload.sh"


class Result:
    def __init__(self, proc: subprocess.CompletedProcess) -> None:
        self.rc = proc.returncode
        self.out = proc.stdout
        self.err = proc.stderr

    @property
    def both(self) -> str:
        return self.out + self.err


def _run(bash_exe: str, script: Path, *args: Path | str) -> Result:
    proc = subprocess.run(
        [bash_exe, script.as_posix(), *[a.as_posix() if isinstance(a, Path) else a for a in args]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return Result(proc)


def _run_payload(bash_exe: str, fx: Fixture, label: str = "fixture") -> Result:
    return _run(bash_exe, fx.script, fx.parent, label)


# --------------------------------------------------------------------------- #
# The broken copies: one neutralised block each
# --------------------------------------------------------------------------- #
#: name -> list of (text in the real script, replacement). Every "old" must occur
#: exactly once in the script (asserted when applied).
MUTATIONS: Dict[str, List[Tuple[str, str]]] = {
    "no-notice-block": [
        ('    check_notice "${pkg}"\n', "    : # NOTICE block skipped\n"),
    ],
    "no-name-list-entry": [
        (" FONTLOG.txt FONTLOG-CJK.txt; do", " FONTLOG.txt; do"),
    ],
    # The comparison loop also reports a payload file missing from the payload,
    # so the "FONTLOG-CJK.txt is absent" case is only attributable to the name
    # list and the comparison together; both are neutralised.
    "no-cjk-fontlog-checks": [
        (" FONTLOG.txt FONTLOG-CJK.txt; do", " FONTLOG.txt; do"),
        (
            'problem "${data}/${rel} is missing from the payload"',
            'echo "${data}/${rel} is missing from the payload"',
        ),
    ],
    "no-byte-comparison": [
        (
            'problem "${data}/${rel} differs from the repository copy"',
            'echo "${data}/${rel} differs from the repository copy"',
        ),
    ],
    "no-donor-line-check": [
        (
            'problem "OFL.txt lacks the Ark Pixel Font line: ${DONOR_LINE}"',
            'echo "OFL.txt lacks the Ark Pixel Font line: ${DONOR_LINE}"',
        ),
    ],
    "no-empty-folder-refusal": [
        (
            'if [ "${pkg_dirs}" -eq 0 ]; then',
            'if false; then',
        ),
        (
            'if [ "${files_examined}" -eq 0 ]; then',
            'if false; then',
        ),
    ],
    "no-self-comparison-refusal": [
        ('if [ "${ROOT_ABS}" = "${REPO_ROOT}" ]; then', "if false; then"),
    ],
}


def _mutated_script(name: str) -> bytes:
    data = REAL_SCRIPT.read_bytes()
    for old, new in MUTATIONS[name]:
        old_b, new_b = old.encode(), new.encode()
        assert data.count(old_b) == 1, (
            f"mutation {name!r}: expected exactly one occurrence of {old!r} in "
            f"check_payload.sh, found {data.count(old_b)}; the script changed and "
            "the mutation no longer proves anything"
        )
        data = data.replace(old_b, new_b)
    assert data != REAL_SCRIPT.read_bytes()
    return data


# --------------------------------------------------------------------------- #
# Cases: (id, plant the defect, expected message, mutation that blinds the check)
# --------------------------------------------------------------------------- #
def _alter_one_line(path: Path, marker: str) -> None:
    """Change one line of a text file by one character, keeping its shape."""
    text = path.read_bytes().decode("utf-8")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if marker in line:
            lines[i] = line + " (changed)"
            break
    else:
        raise AssertionError(f"no line holding {marker!r} in {path}")
    path.write_bytes("\n".join(lines).encode("utf-8"))


def _notice_one_line_different(fx: Fixture) -> None:
    data = fx.notice.read_bytes().decode("utf-8").split("\n")
    data[0] = data[0] + " (different)"
    fx.drop_notice()
    fx.put_notice(fx.parent / "NOTICE", "\n".join(data).encode("utf-8"))


def _notice_absent(fx: Fixture) -> None:
    fx.drop_notice()


def _notice_only_deeper(fx: Fixture) -> None:
    fx.drop_notice()
    fx.put_notice(fx.parent / "somepkg" / "NOTICE")


def _notice_only_in_the_package_folder(fx: Fixture) -> None:
    fx.drop_notice()
    fx.put_notice(fx.pkg / "NOTICE")


def _one_good_one_different(fx: Fixture) -> None:
    other = fx.notice.read_bytes() + b"one more line\n"
    fx.put_notice(fx.parent / "pixelart_creator-1.dist-info" / "licenses" / "NOTICE", other)


def _fontlog_cjk_missing_from_payload(fx: Fixture) -> None:
    (fx.pkg / "fonts" / CJK_FONTLOG).unlink()


def _fontlog_cjk_missing_everywhere(fx: Fixture) -> None:
    (fx.pkg / "fonts" / CJK_FONTLOG).unlink()
    (fx.repo / "pixelart_creator" / "fonts" / CJK_FONTLOG).unlink()


def _ofl_differs_by_one_copyright_line(fx: Fixture) -> None:
    # The typeface's own line, not the donor's: the donor-line check must stay
    # satisfied so that only the byte comparison can refuse this payload.
    _alter_one_line(fx.pkg / "fonts" / "OFL.txt", "JuanGSanchez")


def _ofl_lacks_the_donor_line_in_both(fx: Fixture) -> None:
    # Same edit in the repository and the payload: the byte comparison passes,
    # so only the donor-line check can refuse it.
    for ofl in (fx.pkg / "fonts" / "OFL.txt", fx.repo / "pixelart_creator" / "fonts" / "OFL.txt"):
        text = ofl.read_bytes().decode("utf-8")
        assert "TakWolf" in text
        ofl.write_bytes(text.replace("TakWolf", "Somebody Else").encode("utf-8"))


def _empty_payload(fx: Fixture) -> None:
    shutil.rmtree(fx.pkg)
    for stray in list(fx.parent.iterdir()):
        if stray.is_file():
            stray.unlink()


class Case:
    def __init__(
        self,
        case_id: str,
        plant: Callable[[Fixture], None],
        expect: str,
        mutation: str,
    ) -> None:
        self.id = case_id
        self.plant = plant
        self.expect = expect
        self.mutation = mutation


REFUSALS: List[Case] = [
    Case("notice-absent", _notice_absent, "NOTICE is missing from the payload", "no-notice-block"),
    Case(
        "notice-differs-by-one-line",
        _notice_one_line_different,
        "NOTICE differs from the repository's root NOTICE",
        "no-notice-block",
    ),
    Case(
        "notice-only-at-a-deeper-path",
        _notice_only_deeper,
        "NOTICE is missing from the payload",
        "no-notice-block",
    ),
    Case(
        "notice-only-inside-the-package-folder",
        _notice_only_in_the_package_folder,
        "NOTICE is missing from the payload",
        "no-notice-block",
    ),
    Case(
        "one-notice-identical-another-different",
        _one_good_one_different,
        "NOTICE differs from the repository's root NOTICE",
        "no-notice-block",
    ),
    Case(
        "fontlog-cjk-absent-from-the-payload",
        _fontlog_cjk_missing_from_payload,
        CJK_FONTLOG,
        "no-cjk-fontlog-checks",
    ),
    Case(
        "fontlog-cjk-absent-everywhere-the-name-list-is-the-floor",
        _fontlog_cjk_missing_everywhere,
        f"fonts/{CJK_FONTLOG} is not in the payload",
        "no-name-list-entry",
    ),
    Case(
        "ofl-differs-by-one-copyright-line",
        _ofl_differs_by_one_copyright_line,
        "OFL.txt differs from the repository copy",
        "no-byte-comparison",
    ),
    Case(
        "ofl-lacks-the-donor-line",
        _ofl_lacks_the_donor_line_in_both,
        "OFL.txt lacks the Ark Pixel Font line",
        "no-donor-line-check",
    ),
    Case(
        "empty-folder",
        _empty_payload,
        "the check examined nothing",
        "no-empty-folder-refusal",
    ),
]

_SUMMARY = re.compile(
    r"check_payload \[(?P<label>[^\]]*)\]: (?P<dirs>\d+) payload package folder\(s\), "
    r"(?P<files>\d+) file\(s\) compared, (?P<lines>\d+) notice line\(s\) found, "
    r"(?P<notices>\d+) NOTICE file\(s\) compared"
)


# --------------------------------------------------------------------------- #
# The passing cases
# --------------------------------------------------------------------------- #
def test_complete_payload_exits_0_and_prints_its_denominators(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    res = _run_payload(bash, fx)
    assert res.rc == 0, res.both
    assert "check_payload [fixture]: PASSED" in res.out
    match = _SUMMARY.search(res.out)
    assert match is not None, f"no denominators line in:\n{res.out}"
    own = len(
        re.findall(
            r"^Copyright \(c\) 20[0-9]{2}, ",
            (fx.pkg / "fonts" / "OFL.txt").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert int(match["dirs"]) == 1
    assert int(match["files"]) == fx.files
    assert int(match["lines"]) == 1 + own + 1  # donor line, own dated lines, RFN
    assert int(match["notices"]) == 1
    assert CJK_FONTLOG in res.out, "the FONTLOG-CJK.txt size line is printed"


@pytest.mark.parametrize(
    "where",
    [
        pytest.param(("NOTICE",), id="installer-form-beside-the-package-folder"),
        pytest.param(("pixelart_creator-1.0.dist-info", "licenses", "NOTICE"), id="wheel-licenses-form"),
        pytest.param(("pixelart_creator-1.0.dist-info", "NOTICE"), id="wheel-older-form"),
    ],
)
def test_notice_at_each_of_the_three_candidate_paths_passes_and_is_printed(bash, tmp_path, where):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    fx.drop_notice()
    fx.put_notice(fx.parent.joinpath(*where))
    res = _run_payload(bash, fx)
    assert res.rc == 0, res.both
    printed = [line for line in res.out.splitlines() if line.lstrip().startswith("NOTICE ")]
    assert len(printed) == 1, res.out
    # The script prints the payload path in its own (MSYS) spelling on Windows,
    # so the check is on the part below the fixture's payload folder.
    assert "payload/" + "/".join(where) in printed[0], f"path printed: {printed}"
    assert "identical to the repository's root NOTICE" in printed[0]
    assert int(_SUMMARY.search(res.out)["notices"]) == 1


def test_a_third_party_notice_deeper_in_the_payload_is_neither_required_nor_compared(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    fx.put_notice(fx.parent / "somepkg" / "NOTICE", b"a bundled package's own notice\n")
    res = _run_payload(bash, fx)
    assert res.rc == 0, res.both
    assert int(_SUMMARY.search(res.out)["notices"]) == 1
    assert "somepkg" not in res.out


def test_two_matching_candidates_are_both_compared(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    fx.put_notice(fx.parent / "pixelart_creator-1.0.dist-info" / "licenses" / "NOTICE")
    res = _run_payload(bash, fx)
    assert res.rc == 0, res.both
    assert int(_SUMMARY.search(res.out)["notices"]) == 2


def test_a_payload_whose_fonts_hold_an_extra_file_passes(bash, tmp_path):
    # The check runs repository -> payload, stated: a file only the payload has
    # is not a defect of this check.
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    (fx.pkg / "fonts" / "extra-only-in-the-payload.txt").write_bytes(b"extra\n")
    res = _run_payload(bash, fx)
    assert res.rc == 0, res.both


# --------------------------------------------------------------------------- #
# The refusals, each against the real script and against its broken copy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", REFUSALS, ids=[c.id for c in REFUSALS])
def test_the_defect_is_refused_with_exit_1_naming_it(bash, tmp_path, case):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    case.plant(fx)
    res = _run_payload(bash, fx)
    assert res.rc == 1, f"expected exit 1, got {res.rc}:\n{res.both}"
    assert case.expect in res.both, f"{case.expect!r} not named in:\n{res.both}"
    assert "check_payload [fixture]: PASSED" not in res.out


@pytest.mark.parametrize("case", REFUSALS, ids=[c.id for c in REFUSALS])
def test_the_same_defect_is_not_refused_by_the_broken_copy(bash, tmp_path, case):
    """The case fails against a copy that skips the responsible block."""
    fx = Fixture(tmp_path, _mutated_script(case.mutation))
    case.plant(fx)
    res = _run_payload(bash, fx)
    refused = res.rc == 1 and case.expect in res.both
    assert not refused, (
        f"mutation {case.mutation!r} still refuses {case.id!r}: the case does not "
        f"prove the block it names.\n{res.both}"
    )


def test_a_notice_absent_payload_lists_the_three_paths_it_looked_in(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    fx.drop_notice()
    res = _run_payload(bash, fx)
    assert res.rc == 1
    assert "payload/NOTICE" in res.err
    assert "payload/*.dist-info/licenses/NOTICE" in res.err
    assert "payload/*.dist-info/NOTICE" in res.err


def test_a_notice_that_differs_names_the_path_it_found(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    _notice_one_line_different(fx)
    res = _run_payload(bash, fx)
    assert res.rc == 1
    assert res.err.count("payload/NOTICE") == 1, res.err


def test_the_repository_without_a_root_notice_fails_rather_than_passing_blind(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    fx.notice.unlink()
    res = _run_payload(bash, fx)
    assert res.rc == 1
    assert "holds no root NOTICE" in res.err


# --------------------------------------------------------------------------- #
# Invocation errors
# --------------------------------------------------------------------------- #
def test_the_source_checkout_given_as_the_payload_root_exits_1(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    res = _run(bash, fx.script, fx.repo, "self")
    assert res.rc == 1, res.both
    assert "refusing to compare it with itself" in res.err


def test_the_source_checkout_as_the_payload_root_passes_blind_in_the_broken_copy(bash, tmp_path):
    fx = Fixture(tmp_path, _mutated_script("no-self-comparison-refusal"))
    res = _run(bash, fx.script, fx.repo, "self")
    assert res.rc == 0, f"the control needs the refusal removed to pass blind:\n{res.both}"


def test_a_payload_root_that_does_not_exist_exits_1(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    res = _run(bash, fx.script, tmp_path / "no-such-folder", "missing")
    assert res.rc == 1
    assert "payload root not found" in res.err


def test_wrong_argument_count_exits_2(bash, tmp_path):
    fx = Fixture(tmp_path, REAL_SCRIPT.read_bytes())
    res = _run(bash, fx.script, fx.parent)
    assert res.rc == 2
    assert "usage:" in res.err


# --------------------------------------------------------------------------- #
# The instrument itself
# --------------------------------------------------------------------------- #
def test_every_mutation_changes_the_script_exactly_where_it_says():
    for name in MUTATIONS:
        _mutated_script(name)  # asserts one occurrence per replacement


def test_the_real_script_names_the_cjk_fontlog_and_checks_the_notice():
    text = REAL_SCRIPT.read_text(encoding="utf-8")
    assert CJK_FONTLOG in text
    assert "check_notice" in text
    assert _real_data_files(), "the real tree holds data files to build fixtures from"
