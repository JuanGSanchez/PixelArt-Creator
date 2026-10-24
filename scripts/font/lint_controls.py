"""Injected-defect controls for the source lint.

Each control copies the glyph sources, applies one edit that breaks a rule,
runs the lint on the copy and requires a non-zero exit and the expected rule
flagged. A lint that cannot fail proves nothing; this shows that it can.

A control with the option cjk lints the second face instead (--face nifen-art-cjk) on a
fixture of three records in a scratch folder, with the planted defect made in the CJK
sources, the licence files, the notice file or a built font. A control whose expected
rule is SCENARIO runs a named scenario that also requires a clean result where one is
due. The undamaged fixture is linted first, so a quiet check cannot pass.

A control whose expected rule is NAME0 exercises the build's name ID 0 check instead:
the copy is built in process (Regular only), the listed damage is done to name ID 0 of
the built file (an edit whose file is "name ID 0" or "name ID 0 (Macintosh)"; any other
file is a source edit made before the build), and the check must report the expected
text. The undamaged build must be clean first, so a quiet check cannot pass.

    python scripts/font/lint_controls.py
"""

import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
PY = sys.executable
REPO = os.path.dirname(os.path.dirname(HERE))
SOURCES = os.path.join(REPO, "fonts-src", "nifen-art")
CJK_SOURCES = os.path.join(REPO, "fonts-src", "nifen-art-cjk")
FONTS = os.path.join(REPO, "pixelart_creator", "fonts")
NOTICE = os.path.join(REPO, "NOTICE")
SCRATCH = tempfile.gettempdir()


def show_child_output(r, tail=12):
    """Print what the lint child said when a control is not caught (never silent)."""
    err = r.stderr.strip()
    print("    child exit code: %d" % r.returncode)
    print("    child stderr: %s" % ("" if err else "(empty)"))
    for ln in err.splitlines():
        print("      | " + ln.encode("ascii", "backslashreplace").decode("ascii"))
    lines = r.stdout.rstrip().splitlines()
    print(
        "    child stdout, last %d of %d lines:" % (min(tail, len(lines)), len(lines))
    )
    for ln in lines[-tail:]:
        print("      | " + ln.encode("ascii", "backslashreplace").decode("ascii"))


_PRISTINE = []


def pristine_findings(build):
    """What the name ID 0 check says about the untouched sources, built once per run."""
    if not _PRISTINE:
        d = tempfile.mkdtemp(dir=SCRATCH)
        try:
            srcs = build.parse_sources(SOURCES)
            p = os.path.join(d, "NifenArt-Regular.ttf")
            build.build_font(srcs, build.Font(srcs), "regular", p)
            _PRISTINE.append(build.name0_scan({"regular": p}, srcs))
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return _PRISTINE[0]


def run_name0(name, edits, expect_text):
    """Build a copy, damage name ID 0, require the build's check to report it."""
    sys.path.insert(0, HERE)
    import build_nifen_art as build
    from fontTools.ttLib import TTFont

    d = tempfile.mkdtemp(dir=SCRATCH)
    try:
        dst = os.path.join(d, "src")
        shutil.copytree(SOURCES, dst)
        damage = []
        for fname, old, new in edits:
            if fname.startswith("name ID 0"):
                damage.append((fname, old, new))
                continue
            path = os.path.join(dst, fname)
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                print("%-44s skipped (record not in the sources)" % name)
                return None
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        srcs = build.parse_sources(dst)
        out = os.path.join(d, "out")
        paths = {"regular": os.path.join(out, "NifenArt-Regular.ttf")}
        build.build_font(srcs, build.Font(srcs), "regular", paths["regular"])
        clean = pristine_findings(build)
        if clean:
            print("%-44s the undamaged build is not clean: %s" % (name, clean))
            return False
        with TTFont(paths["regular"]) as font:
            hit_records = 0
            for rec in list(font["name"].names):
                if rec.nameID != 0:
                    continue
                text = rec.toUnicode()
                for fname, old, new in damage:
                    if fname.endswith("(Macintosh)") and rec.platformID != 1:
                        continue
                    if old not in text:
                        print("%-44s skipped (text not in name ID 0)" % name)
                        return None
                    text = text.replace(old, new, 1)
                if text != rec.toUnicode():
                    hit_records += 1
                    font["name"].setName(
                        text, 0, rec.platformID, rec.platEncID, rec.langID
                    )
            font.save(paths["regular"])
        found = build.name0_scan(paths, srcs)
        hit = [ln for ln in found if expect_text in ln]
        print(
            "%-44s %d violation(s) over %d damaged record(s), %r reported: %s"
            % (name, len(found), hit_records, expect_text, "YES" if hit else "NO")
        )
        if not hit:
            for ln in found:
                print(
                    "      | " + ln.encode("ascii", "backslashreplace").decode("ascii")
                )
        return bool(hit)
    finally:
        shutil.rmtree(d, ignore_errors=True)


class Scratch:
    """A scratch copy of everything the lint reads: the existing face's sources, the
    folder with the licence files and the built fonts, and, in CJK mode, a CJK source
    folder (a small fixture of the three sets, never the real glyph records) and a
    notice file. Every edit is made on the copy."""

    def __init__(self, cjk=False):
        self.d = tempfile.mkdtemp(dir=SCRATCH)
        self.cjk = cjk
        self.src = os.path.join(self.d, "src")
        shutil.copytree(SOURCES, self.src)
        self.fonts = os.path.join(self.d, "fonts")
        os.makedirs(self.fonts)
        for fname in ("OFL.txt", "FONTLOG.txt", "FONTLOG-CJK.txt"):
            shutil.copy(os.path.join(FONTS, fname), os.path.join(self.fonts, fname))
        self.cjk_dir = os.path.join(self.d, "cjk")
        self.notice = os.path.join(self.d, "NOTICE")
        if cjk:
            make_cjk_fixture(self.cjk_dir)
            shutil.copy(NOTICE, self.notice)
            for fname in os.listdir(FONTS):
                if fname.endswith(".ttf") and fname.startswith("NifenArt-"):
                    shutil.copy(os.path.join(FONTS, fname), self.fonts)
            built = fixture_fonts()
            for fname in os.listdir(built):
                if fname.startswith("NifenArtCJK"):
                    shutil.copy(os.path.join(built, fname), self.fonts)

    def edit(self, base, edits, label):
        """Apply (file, old, new) edits under base; old=None appends new to the file.
        Returns False when an edit targets text that is not there."""
        for fname, old, new in edits:
            path = os.path.join(base, fname)
            if old is None:
                text = (
                    open(path, "rb").read().decode("utf-8")
                    if os.path.exists(path)
                    else ""
                )
                open(path, "wb").write((text + new).encode("utf-8"))
                continue
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                print("%-44s skipped (record not in the sources)" % self.name)
                return False
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        return True

    def lint(self):
        args = [
            PY,
            os.path.join(HERE, "build_nifen_art.py"),
            "--lint",
            "--src",
            self.src,
            "--licence-dir",
            self.fonts,
        ]
        if self.cjk:
            args += [
                "--face",
                "nifen-art-cjk",
                "--cjk-src",
                self.cjk_dir,
                "--notice",
                self.notice,
                "--out",
                self.fonts,
            ]
        return subprocess.run(
            args,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONIOENCODING="utf-8",
                PYTHONUTF8="1",
            ),
        )

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


def run(name, edits, expect_rule, expect_text=None, licence_edits=(), opts=None):
    if expect_rule == "NAME0":
        return run_name0(name, edits, expect_text)
    if expect_rule == "SCENARIO":
        return SCENARIOS[expect_text](name)
    opts = opts or {}
    sc = Scratch(cjk=bool(opts.get("cjk")))
    sc.name = name
    try:
        if opts.get("cjk") and not cjk_fixture_is_clean(name):
            return False
        if not sc.edit(sc.fonts, licence_edits, "the licence files"):
            return None
        if not sc.edit(sc.src, edits, "the sources"):
            return None
        if not sc.edit(sc.cjk_dir, opts.get("cjk_edits", ()), "the CJK sources"):
            return None
        for old, new in opts.get("notice_edits", ()):
            if not sc.edit(
                os.path.dirname(sc.notice),
                [(os.path.basename(sc.notice), old, new)],
                "NOTICE",
            ):
                return None
        for rel in opts.get("remove", ()):
            os.remove(os.path.join(sc.d, rel))
        if opts.get("ttf_fix"):
            opts["ttf_fix"](sc.fonts)
        r = sc.lint()
        hit = [
            ln
            for ln in r.stdout.split("\n")
            if ln.startswith(expect_rule) and "violations   0" not in ln
        ]
        if expect_text is not None:
            hit = [
                ln
                for ln in r.stdout.split(chr(10))
                if expect_text in ln and "VIOLATION" in ln
            ]
        if expect_rule == "source error":
            hit = [ln for ln in r.stdout.split("\n") if ln.startswith("source error")]
        print(
            "%-44s exit %d  expected rule %s flagged: %s"
            % (name, r.returncode, expect_rule, "YES" if hit else "NO")
        )
        caught = r.returncode != 0 and bool(hit)
        if not caught or r.stderr.strip():
            show_child_output(r)
        return caught
    finally:
        sc.close()


# --------------------------------------------------------------------------
# The CJK fixture
# --------------------------------------------------------------------------
# The controls of the CJK face never touch the real glyph records: they lint a small
# fixture of three records (one per set) in a scratch folder. The drawing is a plain
# plus sign, a fixture and not a character; the code points are in the rarest ranges
# (Extension A, the first Hangul syllable), so a real record cannot collide with them.

PLUS = "\n".join([".....#....."] * 4 + ["###########"] + [".....#....."] * 6) + "\n"
SC_HEAD = "glyph U+3400 set=sc src=drawn top=10 x=0\n"
KR_HEAD = "glyph U+AC00 set=kr src=drawn top=10 x=0\n"
# The plus sign with a 2x2 block at its crossing.
BLOCK = PLUS.replace(
    ".....#.....\n###########\n.....#.....\n",
    ".....##....\n###########\n.....##....\n",
    1,
)
FIXTURE_FILES = {
    "han-jp.txt": "# fixture\nglyph U+3400 set=jp src=drawn same-as=sc\n",
    "han-sc.txt": "# fixture\n" + SC_HEAD + PLUS,
    "hangul.txt": "# fixture\n" + KR_HEAD + PLUS,
    "r05-exemptions.txt": "# fixture: no entry\n",
}
_FIXTURE = {}


def make_cjk_fixture(dst):
    os.makedirs(dst)
    for fname in ("face.txt", "existing-face.sha256"):
        shutil.copy(os.path.join(CJK_SOURCES, fname), os.path.join(dst, fname))
    for fname, text in FIXTURE_FILES.items():
        open(os.path.join(dst, fname), "wb").write(text.encode("utf-8"))


def fixture_fonts():
    """The six fonts of the fixture, built once per process (and again if the folder
    was removed). Every CJK control starts from copies of them."""
    held = _FIXTURE.get("fonts")
    if held and os.path.isdir(held):
        return held
    root = tempfile.mkdtemp(dir=SCRATCH)
    cjk = os.path.join(root, "cjk")
    make_cjk_fixture(cjk)
    out = os.path.join(root, "fonts")
    os.makedirs(out)
    for fname in ("OFL.txt", "FONTLOG.txt", "FONTLOG-CJK.txt"):
        shutil.copy(os.path.join(FONTS, fname), os.path.join(out, fname))
    r = subprocess.run(
        [
            PY,
            os.path.join(HERE, "build_nifen_art.py"),
            "--build",
            "--face",
            "nifen-art-cjk",
            "--cjk-src",
            cjk,
            "--out",
            out,
            "--licence-dir",
            out,
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"),
    )
    if r.returncode != 0:
        show_child_output(r)
        raise RuntimeError("the CJK fixture does not build")
    _FIXTURE["fonts"] = out
    atexit.register(shutil.rmtree, root, True)
    return out


def cjk_fixture_is_clean(name):
    """The undamaged fixture must lint clean before any plant is believed."""
    if _FIXTURE.get("clean"):
        return True
    sc = Scratch(cjk=True)
    sc.name = name
    try:
        r = sc.lint()
    finally:
        sc.close()
    if r.returncode != 0:
        print("%-44s the undamaged CJK fixture does not lint clean" % name)
        show_child_output(r)
        return False
    _FIXTURE["clean"] = True
    return True


def exempt_count(stdout):
    found = re.search(r"exempted glyphs: (\d+)", stdout)
    return int(found.group(1)) if found else None


def scenario_declared_block_counted(name):
    """A 2x2 block planted in a glyph that is then declared with a reason passes R05
    and raises the printed exemption count by one, naming the glyph."""
    if not cjk_fixture_is_clean(name):
        return False
    sc = Scratch(cjk=True)
    sc.name = name
    try:
        before = exempt_count(sc.lint().stdout)
        sc.edit(
            sc.cjk_dir,
            [
                ("han-sc.txt", SC_HEAD + PLUS, SC_HEAD + BLOCK),
                (
                    "r05-exemptions.txt",
                    None,
                    "U+3400 set=sc reason=the crossing is a solid square\n",
                ),
            ],
            "the CJK sources",
        )
        r = sc.lint()
        after = exempt_count(r.stdout)
        r05 = [ln for ln in r.stdout.split("\n") if ln.startswith("R05")]
        named = "exempt U+3400 set=sc [list]" in r.stdout
        ok = (
            r.returncode == 0
            and before is not None
            and after == before + 1
            and named
            and r05
            and "violations   0" in r05[0]
        )
        print(
            "%-44s exit %d  exemptions %s -> %s, named: %s, R05 clean: %s"
            % (name, r.returncode, before, after, named, "YES" if ok else "NO")
        )
        if not ok:
            show_child_output(r)
        return bool(ok)
    finally:
        sc.close()


def scenario_solid_with_reason_counted(name):
    """A glyph flagged solid with a reason passes R05 and is counted and named."""
    if not cjk_fixture_is_clean(name):
        return False
    sc = Scratch(cjk=True)
    sc.name = name
    try:
        before = exempt_count(sc.lint().stdout)
        sc.edit(
            sc.cjk_dir,
            [
                (
                    "han-sc.txt",
                    SC_HEAD + PLUS,
                    SC_HEAD.rstrip("\n") + " solid reason=a filled square\n" + BLOCK,
                )
            ],
            "the CJK sources",
        )
        r = sc.lint()
        after = exempt_count(r.stdout)
        named = "exempt U+3400 set=sc [solid]: a filled square" in r.stdout
        ok = r.returncode == 0 and before is not None and after == before + 1 and named
        print(
            "%-44s exit %d  exemptions %s -> %s, named: %s"
            % (name, r.returncode, before, after, named)
        )
        if not ok:
            show_child_output(r)
        return bool(ok)
    finally:
        sc.close()


def scenario_bold_identity_of_built_fonts(name):
    """The built Bold file must hold the Regular outlines: the clean fixture passes the
    comparison, and a Bold outline moved by one pixel fails it, naming the glyph."""
    sys.path.insert(0, HERE)
    import build_nifen_art as build
    from fontTools.ttLib import TTFont

    d = tempfile.mkdtemp(dir=SCRATCH)
    try:
        built = fixture_fonts()
        paths = {}
        for s in ("jp", "sc", "kr"):
            for w in ("regular", "bold"):
                fname = "NifenArtCJK%s-%s.ttf" % (
                    s.upper(),
                    "Bold" if w == "bold" else "Regular",
                )
                shutil.copy(os.path.join(built, fname), d)
                paths[(s, w)] = os.path.join(d, fname)
        pairs, clean = build.bold_identity(paths)
        if clean or pairs == 0:
            print("%-44s the undamaged fixture is not clean: %s" % (name, clean))
            return False
        with TTFont(paths[("sc", "bold")]) as font:
            glyph = font["glyf"]["uni3400"]
            coords = glyph.getCoordinates(font["glyf"])[0]
            coords[0] = (coords[0][0] + 128, coords[0][1])
            font.save(paths[("sc", "bold")])
        _pairs, found = build.bold_identity(paths)
        hit = [ln for ln in found if "uni3400" in ln and "NifenArtCJKSC-Bold" in ln]
        print(
            "%-44s %d pair(s) compared, %d violation(s), glyph named: %s"
            % (name, pairs, len(found), "YES" if hit else "NO")
        )
        return bool(hit)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def scenario_freeze(kind):
    """The freeze comparison on a scratch root: the existing face's files and the
    manifest, damaged in one way."""

    def scenario(name):
        d = tempfile.mkdtemp(dir=SCRATCH)
        try:
            root = os.path.join(d, "root")
            shutil.copytree(SOURCES, os.path.join(root, "fonts-src", "nifen-art"))
            out = os.path.join(root, "pixelart_creator", "fonts")
            os.makedirs(out)
            for fname in (
                "NifenArt-Regular.ttf",
                "NifenArt-Bold.ttf",
                "FONTLOG.txt",
                "OFL.txt",
            ):
                shutil.copy(os.path.join(FONTS, fname), out)
            cjk = os.path.join(root, "fonts-src", "nifen-art-cjk")
            os.makedirs(cjk)
            manifest = os.path.join(cjk, "existing-face.sha256")
            shutil.copy(os.path.join(CJK_SOURCES, "existing-face.sha256"), manifest)

            def verify():
                return subprocess.run(
                    [
                        PY,
                        os.path.join(HERE, "build_nifen_art.py"),
                        "--verify-freeze",
                        "--root",
                        root,
                        "--cjk-src",
                        cjk,
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                )

            clean = verify()
            if clean.returncode != 0:
                print("%-44s the undamaged scratch root is not clean" % name)
                show_child_output(clean)
                return False
            src = os.path.join(root, "fonts-src", "nifen-art")
            want = {
                "changed source": "latin-basic.txt differs from the manifest",
                "changed font": "NifenArt-Bold.ttf differs from the manifest",
                "missing file": "symbols.txt is listed but missing",
                "added file": "extra.txt is not in the manifest",
                "bad manifest line": "is not '<sha256>  <path>'",
                "missing manifest": "existing-face.sha256 is missing",
            }[kind]
            if kind == "changed source":
                with open(os.path.join(src, "latin-basic.txt"), "ab") as fh:
                    fh.write(b"\n# one more line\n")
            elif kind == "changed font":
                path = os.path.join(out, "NifenArt-Bold.ttf")
                data = bytearray(open(path, "rb").read())
                data[len(data) // 2] ^= 1
                open(path, "wb").write(bytes(data))
            elif kind == "missing file":
                os.remove(os.path.join(src, "symbols.txt"))
            elif kind == "added file":
                open(os.path.join(src, "extra.txt"), "wb").write(b"# extra\n")
            elif kind == "bad manifest line":
                with open(manifest, "ab") as fh:
                    fh.write(b"not a hash line\n")
            else:
                os.remove(manifest)
            r = verify()
            hit = [ln for ln in r.stdout.split("\n") if want in ln]
            print(
                "%-44s exit %d  expected %r reported: %s"
                % (name, r.returncode, want, "YES" if hit else "NO")
            )
            if not (r.returncode != 0 and hit):
                show_child_output(r)
            return r.returncode != 0 and bool(hit)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    return scenario


def fix_existing_name0(fonts):
    """Credit a second copyright holder in name ID 0 of the existing Regular font."""
    from fontTools.ttLib import TTFont

    path = os.path.join(fonts, "NifenArt-Regular.ttf")
    with TTFont(path) as font:
        for rec in list(font["name"].names):
            if rec.nameID == 0:
                font["name"].setName(
                    rec.toUnicode() + " Copyright (c) 2019, Someone Else.",
                    0,
                    rec.platformID,
                    rec.platEncID,
                    rec.langID,
                )
        font.save(path)


def fix_cjk_name0_donor(fonts):
    """Put the donor's copyright line into name ID 0 of a CJK font."""
    from fontTools.ttLib import TTFont

    path = os.path.join(fonts, "NifenArtCJKSC-Regular.ttf")
    with TTFont(path) as font:
        for rec in list(font["name"].names):
            if rec.nameID == 0:
                font["name"].setName(
                    "Copyright (c) 2021, TakWolf (https://takwolf.com). "
                    + rec.toUnicode(),
                    0,
                    rec.platformID,
                    rec.platEncID,
                    rec.langID,
                )
        font.save(path)


def fix_cjk_cmap_space(fonts):
    """Add U+0020 to the character map of a built CJK font."""
    from fontTools.ttLib import TTFont

    path = os.path.join(fonts, "NifenArtCJKSC-Regular.ttf")
    with TTFont(path) as font:
        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[0x20] = "uni3400"
        font.save(path)


SCENARIOS = {
    "declared block counted": scenario_declared_block_counted,
    "solid with reason counted": scenario_solid_with_reason_counted,
    "bold identity of built fonts": scenario_bold_identity_of_built_fonts,
}
for _kind in (
    "changed source",
    "changed font",
    "missing file",
    "added file",
    "bad manifest line",
    "missing manifest",
):
    SCENARIOS["freeze: " + _kind] = scenario_freeze(_kind)


CONTROLS = [
    (
        "2x2 block in Regular H",
        [
            (
                "latin-basic.txt",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n##..#\n#####",
            )
        ],
        "R05",
    ),
    (
        "orphan pixel added to o",
        [
            (
                "latin-basic.txt",
                "glyph U+006F adv=6 top=5 ext=0..5\n.###.",
                "glyph U+006F adv=6 top=7 ext=0..7\n#....\n.....\n.###.",
            )
        ],
        "R04",
    ),
    (
        "Bold overlay for Omega removed",
        [("bold-overlays.txt", "bold U+03A9", "bold U+03A8")],
        "R08",
    ),
    (
        "wrong advance on A",
        [("latin-basic.txt", "glyph U+0041 adv=6", "glyph U+0041 adv=7")],
        "R03",
    ),
    (
        "height wrong (H lacks a row)",
        [
            (
                "latin-basic.txt",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####",
                "glyph U+0048 adv=6 top=6 ext=0..7\n#...#\n#...#\n#...#\n#####",
            )
        ],
        "R02",
    ),
    (
        "capital X drawn 8 rows (ascender height, not cap height)",
        [
            (
                "latin-basic.txt",
                "glyph U+0058 adv=6 top=7 ext=0..7\n#...#\n#...#\n.#.#.",
                "glyph U+0058 adv=6 top=8 ext=0..8\n#...#\n#...#\n#...#\n.#.#.",
            )
        ],
        "R02",
        "U+0058 capital ext top 8",
    ),
    (
        "capital drawn with a free extent but not an accented form",
        [
            (
                "latin-basic.txt",
                "glyph U+0058 adv=6 top=7 ext=0..7",
                "glyph U+0058 adv=6 top=7 ext=free",
            )
        ],
        "R02",
        "U+0058 capital declares ext=free",
    ),
    (
        "accented capital I diaeresis drawn 8 rows (gap row filled)",
        [
            (
                "latin1.txt",
                "glyph U+00CF adv=5 top=9 ext=free dots=2 tab\n#.#\n...\n###\n.#.",
                "glyph U+00CF adv=5 top=9 ext=free dots=2 tab\n#.#\n###\n.#.\n.#.",
            )
        ],
        "R02",
        "U+00CF accented capital body",
    ),
    (
        "forbidden token in a comment",
        [("greek.txt", "# Greek block.", "# Greek block, drawn by an A" + "I model.")],
        "R09",
    ),
    (
        "duplicate codepoint",
        [("symbols.txt", "glyph U+00D7 adv=6", "glyph U+0041 adv=6")],
        "R07",
    ),
    (
        "recipe base missing",
        [("recipes.txt", "recipe U+00E1 = mark U+0061", "recipe U+00E1 = mark U+E000")],
        "source error",
    ),
    (
        "ink outside the em box",
        [
            (
                "latin-basic.txt",
                "glyph U+0045 adv=6 top=7 ext=0..7",
                "glyph U+0045 adv=6 top=12 ext=0..7",
            )
        ],
        "R01",
    ),
    (
        "Bold overlay of @ removed (eye fills in)",
        [
            (
                "bold-overlays.txt",
                "bold U+0040",
                "bold U+0024 adv=7 top=7 ext=free\n..#..\n\nbold U+3042",
            )
        ],
        "R08",
    ),
    (
        "joined mark no longer touches (cedilla lowered)",
        [
            (
                "recipes.txt",
                "recipe U+00C7 = mark U+0043 cedilla join=1",
                "recipe U+00C7 = mark U+0043 cedilla join=1 rise=-1",
            )
        ],
        "R06",
    ),
    (
        "accent sunk into its letter (acute rise=-2)",
        [
            (
                "recipes.txt",
                "recipe U+00E1 = mark U+0061 acute.low",
                "recipe U+00E1 = mark U+0061 acute.low rise=-2",
            )
        ],
        "R06",
    ),
    (
        "space (and its alias) with the wrong width",
        [("latin-basic.txt", "glyph U+0020 adv=3", "glyph U+0020 adv=4")],
        "R03",
        "U+00A0 blank advance",
    ),
    (
        "ogonek no longer touches its letter (align removed)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0104 = mark U+0041 ogonek align=right join=1",
                "recipe U+0104 = mark U+0041 ogonek join=1",
            )
        ],
        "R06",
    ),
    (
        "ligature Bold parts fuse (gap removed from IJ)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0132 = cat U+0049 U+004A gap=1",
                "recipe U+0132 = cat U+0049 U+004A",
            )
        ],
        "R08",
    ),
    (
        "macron sunk into its capital (rise=-3)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0100 = mark U+0041 macron.cap",
                "recipe U+0100 = mark U+0041 macron.cap rise=-3",
            )
        ],
        "R06",
    ),
    (
        "declared join but the acute floats (l acute dx=3)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+013A = mark U+006C acute.low rise=2 dx=1 join=1",
                "recipe U+013A = mark U+006C acute.low rise=2 dx=3 join=1",
            )
        ],
        "R06",
    ),
    (
        "Bold overlay of U ring removed (cup closes)",
        [("bold-overlays.txt", "bold U+016E", "bold U+0176")],
        "R08",
        "U+016E derived Bold",
    ),
    (
        "tick moved against the stem (l tick, Bold fuses)",
        [
            (
                "latin-ext-a.txt",
                "glyph U+013E adv=5 top=8 ext=0..8\n#..#\n#..#",
                "glyph U+013E adv=4 top=8 ext=0..8\n#.#.\n#.#.",
            )
        ],
        "R08",
        "U+013E derived Bold",
    ),
    (
        "wrong advance on L with stroke",
        [("latin-ext-a.txt", "glyph U+0141 adv=6", "glyph U+0141 adv=7")],
        "R03",
    ),
    (
        "solid flag removed from the black circle (2x2 blocks)",
        [
            (
                "symbols.txt",
                "glyph U+25CF adv=7 top=6 ext=free solid",
                "glyph U+25CF adv=7 top=6 ext=free",
            )
        ],
        "R05",
    ),
    (
        "orphan pixel in the euro sign",
        [("symbols.txt", "###...\n.#....\n###...", "###...\n.#...#\n###...")],
        "R04",
    ),
    (
        "black star with the wrong advance",
        [("symbols.txt", "glyph U+2605 adv=8", "glyph U+2605 adv=7")],
        "R03",
    ),
    (
        "alias to a code point with no drawing",
        [("aliases.txt", "alias U+2212 = U+2013", "alias U+2212 = U+E000")],
        "source error",
    ),
    (
        "double acute too narrow (Bold strokes touch)",
        [
            (
                "marks.txt",
                "mark doubleacute.low attach=2 top=8\n.#...#\n#...#.",
                "mark doubleacute.low attach=2 top=8\n.#..#\n#..#.",
            )
        ],
        "R08",
        "mark doubleacute.low derived Bold",
    ),
    (
        "comma below on K loses its Bold overlay",
        [("bold-overlays.txt", "bold U+0136", "bold U+0176")],
        "R08",
        "U+0136 derived Bold",
    ),
    (
        "thin space with the wrong advance",
        [("latin-basic.txt", "glyph U+2009 adv=2", "glyph U+2009 adv=3")],
        "R03",
        "U+2009 blank advance",
    ),
    (
        "Djerv leg shortened (Bold closes the counter)",
        [
            (
                "cyrillic.txt",
                "glyph U+0402 adv=6 top=7 ext=-2..7\n#####\n.#...\n.#...\n.###.\n"
                ".#..#\n.#..#\n.#..#\n....#\n...#.",
                "glyph U+0402 adv=6 top=7 ext=-1..7\n#####\n.#...\n.#...\n.###.\n"
                ".#..#\n.#..#\n.#..#\n...#.",
            )
        ],
        "R08",
        "U+0402 derived Bold",
    ),
    (
        "alias of the middle dot loses the tab flag",
        [
            (
                "latin1.txt",
                "glyph U+00B7 adv=3 top=4 ext=free dots=1 tab",
                "glyph U+00B7 adv=3 top=4 ext=free dots=1",
            )
        ],
        "R03",
        "U+0387 Regular left sidebearing",
    ),
    (
        "numero sign parts fuse in Bold (gap removed)",
        [
            (
                "recipes-b5.txt",
                "recipe U+2116 = cat U+004E U+00BA gap=1",
                "recipe U+2116 = cat U+004E U+00BA",
            )
        ],
        "R08",
        "U+2116 derived Bold",
    ),
    (
        "orphan pixel in Greek capital Gamma",
        [
            (
                "greek.txt",
                "glyph U+0393 adv=6 top=7 ext=0..7\n#####\n#....\n#....",
                "glyph U+0393 adv=6 top=7 ext=0..7\n#####\n#....\n#..#.",
            )
        ],
        "R04",
    ),
    (
        "ideographic space with the wrong advance",
        [
            (
                "cjk-fullwidth.txt",
                "glyph U+3000 adv=12 top=0 x=0",
                "glyph U+3000 adv=11 top=0 x=0",
            )
        ],
        "R03",
        "U+3000 blank advance",
    ),
    (
        "hiragana i shifted out of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9",
                "glyph U+3044 adv=12 x=4 cell=full ext=free top=9",
            )
        ],
        "R01",
        "U+3044",
    ),
    (
        "hiragana i drawn 12 columns wide (the cell takes 11)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n"
                "#.......#..\n#.......#..\n#........#.\n#........#.\n#........#.\n"
                "#.........#\n",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n"
                "#.......#...\n#.......#...\n#........#..\n#........#..\n#........#..\n"
                "#.........##\n",
            )
        ],
        "R01",
        "U+3044 regular kana ink columns 0..11",
    ),
    (
        "katakana e shifted two columns right (ink to column 12)",
        [
            (
                "katakana.txt",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8",
                "glyph U+30A8 adv=12 x=3 cell=full ext=free top=8",
            )
        ],
        "R01",
        "U+30A8 regular kana ink columns",
    ),
    (
        "half-width H with its advance cut to 4 (ink past the advance)",
        [("latin-basic.txt", "glyph U+0048 adv=6", "glyph U+0048 adv=4")],
        "R01",
        "U+0048 regular ink columns",
    ),
    (
        "orphan pixel in hiragana i",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n#.......#..\n"
                "#.......#..",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n#.......#.#\n"
                "#.......#..",
            )
        ],
        "R04",
        "U+3044",
    ),
    (
        "2x2 block in katakana e",
        [
            (
                "katakana.txt",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8\n..######..\n"
                ".....#....\n.....#....\n",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8\n..######..\n"
                "....##....\n....##....\n",
            )
        ],
        "R05",
        "U+30A8",
    ),
    (
        "voiced mark touches its base (trim removed from ZE)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30BC = overlay U+30BB U+309B trim=1",
                "recipe U+30BC = overlay U+30BB U+309B",
            )
        ],
        "R06",
        "U+30BC",
    ),
    (
        "trim cut undeclared (GU loses cut=1)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30B0 = overlay U+30AF U+309B trim=1 cut=1",
                "recipe U+30B0 = overlay U+30AF U+309B trim=1",
            )
        ],
        "R06",
        "U+30B0",
    ),
    (
        "cut declared but not needed (GE)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30B2 = overlay U+30B1 U+309B trim=1",
                "recipe U+30B2 = overlay U+30B1 U+309B trim=1 cut=1",
            )
        ],
        "R06",
        "U+30B2 declares cut",
    ),
    (
        "trim limit exceeded (limit 2 pixels)",
        [("metrics.txt", "trim_max_px = 20", "trim_max_px = 2")],
        "R06",
        "trim removes",
    ),
    (
        "Bold overlay of small hiragana a removed",
        [("bold-overlays-ark-pixel.txt", "bold U+3041 ", "bold U+3042 ")],
        "R08",
        "U+3041 derived Bold",
    ),
    (
        "Bold overlay of the voiced kana pu removed",
        [("bold-overlays-ark-pixel.txt", "bold U+3077 ", "bold U+3076 ")],
        "R08",
        "U+3077 derived Bold",
    ),
    (
        "alias of the full-width tilde to nothing",
        [("aliases.txt", "alias U+FF5E = U+301C", "alias U+FF5E = U+E000")],
        "source error",
    ),
    (
        "small ya floats above the bottom row",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=9",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small ya moved to the right half of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3083 adv=12 x=3 cell=full ext=free top=8",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small a moved two pixels off the centre of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3041 adv=12 x=2 cell=full ext=free top=8",
            )
        ],
        "R12",
        "U+3041 regular small kana is not centred",
    ),
    (
        "small a drawn 10 rows tall (the limit is 9)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=9\n....#......\n",
            )
        ],
        "R12",
        "U+3041 regular small kana is 10 rows tall",
    ),
    (
        "small a drawn 10 columns wide (the limit is 9)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n"
                "....#......\n..#######..\n",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n"
                "....#......\n..#########\n",
            )
        ],
        "R12",
        "U+3041 regular small kana is 10 columns wide",
    ),
    (
        "base of a composed voiced katakana touches the mark (GA)",
        [
            (
                "kana.txt",
                "glyph U+30AB adv=12 top=8 x=1 cell=full ext=free"
                "\n...#......\n.########.",
                "glyph U+30AB adv=12 top=8 x=1 cell=full ext=free"
                "\n...#....#.\n.########.",
            )
        ],
        "R13",
        "U+30AC regular: 1 pixel",
    ),
    (
        "donor copyright line missing from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "# Copyright (c) 2021, TakWolf (https://takwolf.com).\n",
                "",
            )
        ],
        "R14",
        "header does not state the donor copyright line",
    ),
    (
        "donor name removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "adapted from Ark Pixel Font, 12 px,",
                "adapted from a donor font, 12 px,",
            ),
            (
                "hiragana-ark-pixel.txt",
                "# Ark Pixel Font is licensed",
                "# The donor font is licensed",
            ),
        ],
        "R14",
        "header does not state the donor name",
    ),
    (
        "donor version removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "version 2026.09.25 (https",
                "version (https",
            )
        ],
        "R14",
        "header does not state the donor version",
    ),
    (
        "donor version altered in the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "version 2026.09.25 (https",
                "version 2026.09.24 (https",
            )
        ],
        "R14",
        "header does not state the donor version",
    ),
    (
        "donor licence removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "licensed under the SIL Open Font License, Version 1.1 and declares",
                "licensed under an open licence and declares",
            )
        ],
        "R14",
        "header does not state the donor licence",
    ),
    (
        "donor name removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "adapted from Ark Pixel Font 12 px",
                "adapted from a donor font 12 px",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor name",
    ),
    (
        "donor version removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "version 2026.09.25; https",
                "version; https",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor version",
    ),
    (
        "donor version altered in the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "version 2026.09.25; https",
                "version 2026.09.24; https",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor version",
    ),
    (
        "donor licence removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "SIL Open Font License, Version 1.1,",
                "an open licence,",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor licence",
    ),
    (
        "donor copyright line removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "Copyright (c) 2021, TakWolf (https://takwolf.com); ",
                "",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor copyright",
    ),
    (
        "Bold correction file left out of the derived-file list",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = hiragana-ark-pixel.txt",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt mentions the donor (Ark Pixel Font) but is not",
    ),
    (
        "an unlisted source file that mentions the donor",
        [
            (
                "cyrillic.txt",
                "# Cyrillic block. ",
                "# Cyrillic block, a few shapes after Ark Pixel Font. ",
            )
        ],
        "R14",
        "cyrillic.txt mentions the donor (Ark Pixel Font) but is not listed",
    ),
    (
        "an unlisted source file that mentions the donor across a line break",
        [
            (
                "cyrillic.txt",
                "# Cyrillic block. ",
                "# Cyrillic block, a few shapes after Ark Pixel\n# font. ",
            )
        ],
        "R14",
        "cyrillic.txt mentions the donor (Ark Pixel Font) but is not listed",
    ),
    (
        "glyph donor file left out of the derived-file list",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = bold-overlays-ark-pixel.txt",
            )
        ],
        "R14",
        "donor file hiragana-ark-pixel.txt is not listed in donor_derived_files",
    ),
    (
        "derived file named in the metrics is not among the sources",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = hiragana-ark-pixel.txt bold-overlays-ark.txt",
            )
        ],
        "R14",
        "donor-derived file bold-overlays-ark.txt is not among the sources",
    ),
    (
        "donor file named in the metrics is not among the sources",
        [
            (
                "metrics.txt",
                "donor_files = hiragana-ark-pixel.txt",
                "donor_files = hiragana-ark.txt",
            )
        ],
        "R14",
        "is not among the sources",
    ),
    (
        "prior copyright line removed from the metrics (name ID 0 would lose it)",
        [
            (
                "metrics.txt",
                "copyright_prior_line_1 = Copyright (c) 2021, TakWolf "
                "(https://takwolf.com).",
                "copyright_prior_line_1 =",
            )
        ],
        "R14",
        "declared together",
    ),
    (
        "a donor letter also composed by a recipe",
        [
            (
                "recipes.txt",
                "recipe U+30AC = overlay U+30AB U+309B ",
                "recipe U+3042 = overlay U+3044 U+309B trim=1"
                "\nrecipe U+30AC = overlay U+30AB U+309B ",
            )
        ],
        "R14",
        "U+3042 is both a donor drawing and a recipe",
    ),
    (
        "donor copyright line missing from the licence file",
        [],
        "R14",
        "OFL.txt does not state",
        [("OFL.txt", "Copyright (c) 2021, TakWolf (https://takwolf.com).\n", "")],
    ),
    (
        "donor code points not named in the change log",
        [],
        "R14",
        "FONTLOG.txt does not state",
        [("FONTLOG.txt", "Code points adapted from", "Code points taken from")],
    ),
    (
        "gap overlay of r wider than the Bold box",
        [
            (
                "bold-overlays-b7.txt",
                "##.##\n###..\n##...\n##...\n##...",
                "##.###\n###...\n##....\n##....\n##....",
            )
        ],
        "R03",
        "U+0072 Bold right sidebearing",
    ),
    (
        "gap overlay of m with a one-pixel run",
        [("bold-overlays-b7.txt", "##.##.##\n########", "##.##.#.\n########")],
        "R05",
        "U+006D",
    ),
    (
        "gap overlay of Cyrillic Ya loses its leg join",
        [
            (
                "bold-overlays-b7.txt",
                ".#####\n.##.##\n##..##\n##..##\n\n# Cyrillic ya (lowercase)",
                ".#####\n......\n##..##\n##..##\n\n# Cyrillic ya (lowercase)",
            )
        ],
        "R08",
        "U+042F",
    ),
    (
        "needless Bold overlay on H",
        [
            (
                "bold-overlays.txt",
                "bold U+0023",
                "bold U+0048 adv=7 top=7 ext=free\n##..##\n##..##\n##..##\n######\n"
                "##..##\n##..##\n##..##\n\nbold U+0023",
            )
        ],
        "R08",
    ),
    (
        "licence file: clause missing from the typeface's line",
        [],
        "R14",
        "does not end with",
        [("OFL.txt", ' with Reserved Font Name "Nifen Art".', "")],
    ),
    (
        "licence file: clause altered on the typeface's line",
        [],
        "R14",
        "does not end with",
        [("OFL.txt", 'Reserved Font Name "Nifen Art".', 'Reserved Font Name "Nifen".')],
    ),
    (
        "licence file: clause moved to the donor line",
        [],
        "R14",
        "carries 'Reserved Font Name'",
        [
            ("OFL.txt", ' with Reserved Font Name "Nifen Art".', ""),
            (
                "OFL.txt",
                "(https://takwolf.com).\n",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".\n',
            ),
        ],
    ),
    (
        "licence file: clause also on the donor line",
        [],
        "R14",
        "carries 'Reserved Font Name'",
        [
            (
                "OFL.txt",
                "(https://takwolf.com).\n",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".\n',
            )
        ],
    ),
    (
        "metrics clause reworded (the lint refuses it)",
        [
            (
                "metrics.txt",
                'copyright_rfn_clause = with Reserved Font Name "Nifen Art".',
                "copyright_rfn_clause = with no declaration.",
            )
        ],
        "R14",
        "copyright_rfn_clause is",
    ),
    (
        "name ID 0: clause missing from the typeface's line",
        [("name ID 0", ' with Reserved Font Name "Nifen Art".', "")],
        "NAME0",
        "does not end with",
    ),
    (
        "name ID 0: clause altered on the typeface's line",
        [
            (
                "name ID 0",
                'Reserved Font Name "Nifen Art".',
                'Reserved Font Name "Nifen".',
            )
        ],
        "NAME0",
        "does not end with",
    ),
    (
        "name ID 0: clause moved to the donor line",
        [
            ("name ID 0", ' with Reserved Font Name "Nifen Art".', ""),
            (
                "name ID 0",
                "(https://takwolf.com).",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".',
            ),
        ],
        "NAME0",
        "is attached to a prior copyright line",
    ),
    (
        "name ID 0: clause also on the donor line",
        [
            (
                "name ID 0",
                "(https://takwolf.com).",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".',
            )
        ],
        "NAME0",
        "is attached to a prior copyright line",
    ),
    (
        "name ID 0: clause missing at the Macintosh record only",
        [("name ID 0 (Macintosh)", ' with Reserved Font Name "Nifen Art".', "")],
        "NAME0",
        "does not end with",
    ),
    (
        "metrics clause reworded (the built name ID 0 follows it)",
        [
            (
                "metrics.txt",
                'copyright_rfn_clause = with Reserved Font Name "Nifen Art".',
                "copyright_rfn_clause = with no declaration.",
            )
        ],
        "NAME0",
        "does not end with",
    ),
]


# --------------------------------------------------------------------------
# Controls of the CJK face and of the donor gate
# --------------------------------------------------------------------------
# Each of these lints the CJK fixture (never the real records) with one defect planted
# in the sources, the licence files, the notice file or a built font, and requires the
# named violation. The scenario controls also require a clean result where one is due:
# a declared block passes and is counted, the clean built fonts compare equal, the
# frozen face compares equal.


def cjk(name, rule, text, cjk_edits=(), edits=(), licence_edits=(), **opts):
    opts.update(cjk=True, cjk_edits=list(cjk_edits))
    return (name, list(edits), rule, text, tuple(licence_edits), opts)


def plus_record(head):
    return "\n" + head + PLUS


FONTLOG_ANCHOR = "Project: https://github.com/JuanGSanchez/PixelArt-Creator\n"
DERIVED = "donor_derived_files = hiragana-ark-pixel.txt bold-overlays-ark-pixel.txt"

CONTROLS.extend(
    [
        # R05 with a declared, reasoned, counted exemption list
        cjk(
            "CJK: 2x2 block in a glyph not on the exemption list",
            "R05",
            "U+3400 set=sc Regular has a 2x2 block",
            [("han-sc.txt", SC_HEAD + PLUS, SC_HEAD + BLOCK)],
        ),
        cjk(
            "CJK: 2x2 block, exemption entry gives no reason",
            "R05",
            "exemption entry U+3400 set=sc (r05-exemptions.txt:2) gives no reason",
            [
                ("han-sc.txt", SC_HEAD + PLUS, SC_HEAD + BLOCK),
                ("r05-exemptions.txt", None, "U+3400 set=sc\n"),
            ],
        ),
        cjk(
            "CJK: 2x2 block, exemption entry with an empty reason=",
            "R05",
            "exemption entry U+3400 set=sc (r05-exemptions.txt:2) gives no reason",
            [
                ("han-sc.txt", SC_HEAD + PLUS, SC_HEAD + BLOCK),
                ("r05-exemptions.txt", None, "U+3400 set=sc reason=\n"),
            ],
        ),
        (
            "CJK: a declared 2x2 block passes and is counted",
            [],
            "SCENARIO",
            "declared block counted",
        ),
        cjk(
            "CJK: glyph flagged solid without a reason",
            "R05",
            "U+3400 set=sc is flagged solid with no reason",
            [("han-sc.txt", SC_HEAD + PLUS, SC_HEAD.rstrip("\n") + " solid\n" + BLOCK)],
        ),
        (
            "CJK: glyph flagged solid with a reason is counted",
            [],
            "SCENARIO",
            "solid with reason counted",
        ),
        cjk(
            "CJK: exemption entry for a glyph with no block",
            "R05",
            "is declared exempt (list) but holds no 2x2 block",
            [("r05-exemptions.txt", None, "U+3400 set=sc reason=none needed\n")],
        ),
        cjk(
            "CJK: exemption entry for a glyph with no record",
            "R05",
            "names a glyph that has no record in the set",
            [("r05-exemptions.txt", None, "U+3401 set=sc reason=none\n")],
        ),
        cjk(
            "CJK: glyph declared by the list and by the solid flag",
            "R05",
            "declare it once",
            [
                (
                    "han-sc.txt",
                    SC_HEAD + PLUS,
                    SC_HEAD.rstrip("\n") + " solid reason=a filled square\n" + BLOCK,
                ),
                ("r05-exemptions.txt", None, "U+3400 set=sc reason=a filled square\n"),
            ],
        ),
        # The character map holds Han and Hangul only
        cjk(
            "CJK cmap: U+0020 in a source",
            "R15",
            "U+0020 set=sc is neither Han nor Hangul",
            [
                (
                    "han-sc.txt",
                    None,
                    plus_record("glyph U+0020 set=sc src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: a kana in a source",
            "R15",
            "U+3042 set=jp is neither Han nor Hangul",
            [
                (
                    "han-jp.txt",
                    None,
                    plus_record("glyph U+3042 set=jp src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: a Latin letter in the Hangul source",
            "R15",
            "U+0041 set=kr is neither Han nor Hangul",
            [
                (
                    "hangul.txt",
                    None,
                    plus_record("glyph U+0041 set=kr src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: a conjoining jamo in the Hangul source",
            "R15",
            "U+1100 set=kr is neither Han nor Hangul",
            [
                (
                    "hangul.txt",
                    None,
                    plus_record("glyph U+1100 set=kr src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: a Hangul syllable in a Han set",
            "R15",
            "U+AC01 set=jp is Hangul: the jp set holds Han only",
            [
                (
                    "han-jp.txt",
                    None,
                    plus_record("glyph U+AC01 set=jp src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: a Han character in the Hangul set",
            "R15",
            "U+3401 set=kr is Han: the kr set holds Hangul only",
            [
                (
                    "hangul.txt",
                    None,
                    plus_record("glyph U+3401 set=kr src=drawn top=10 x=0\n"),
                )
            ],
        ),
        cjk(
            "CJK cmap: U+0020 in the map of a built font",
            "R15",
            "NifenArtCJKSC-Regular.ttf: U+0020 is in the character map",
            ttf_fix=fix_cjk_cmap_space,
        ),
        # Provenance: drawn, or a recipe of drawn glyphs; never another font
        cjk(
            "CJK: provenance names a font",
            "R16",
            "src=copied:Galmuri names another font (Galmuri)",
            [
                (
                    "han-sc.txt",
                    SC_HEAD,
                    "glyph U+3400 set=sc src=copied:Galmuri top=10 x=0\n",
                )
            ],
        ),
        cjk(
            "CJK: a copied-from attribute",
            "R16",
            "copied-from=SomeFont records a font as the source",
            [
                (
                    "han-sc.txt",
                    SC_HEAD,
                    "glyph U+3400 set=sc src=drawn copied-from=SomeFont top=10 x=0\n",
                )
            ],
        ),
        cjk(
            "CJK: a record without src=",
            "R16",
            "U+3400 set=sc: no src=",
            [("han-sc.txt", SC_HEAD, "glyph U+3400 set=sc top=10 x=0\n")],
        ),
        cjk(
            "CJK: a recipe built from a hiragana",
            "R06",
            "U+3042 set=sc: there is no such record",
            [("han-sc.txt", None, "\nglyph U+3401 set=sc src=recipe:U+3042 at=0:0\n")],
        ),
        cjk(
            "CJK: a recipe that names a font",
            "R06",
            "bad glyph reference 'Galmuri'",
            [("han-sc.txt", None, "\nglyph U+3401 set=sc src=recipe:Galmuri at=0:0\n")],
        ),
        # Bold is Regular
        cjk(
            "CJK: a Bold drawing",
            "R08",
            "a bold record: refused",
            [("han-sc.txt", None, plus_record("bold U+3400 adv=12 top=10 x=0\n"))],
        ),
        (
            "CJK: the built Bold file equals the Regular file",
            [],
            "SCENARIO",
            "bold identity of built fonts",
        ),
        # The donor gate
        cjk(
            "gate: a second donor in the metrics",
            "R14",
            "metrics.txt declares donor_name_2: a second donor is refused",
            edits=[("metrics.txt", None, "donor_name_2 = Galmuri Font\n")],
        ),
        cjk(
            "gate: a third donor-derived file",
            "R14",
            "bold-overlays-b7.txt is listed as a donor-derived file: a third one",
            edits=[("metrics.txt", DERIVED, DERIVED + " bold-overlays-b7.txt")],
        ),
        cjk(
            "gate: a donor-derived code point outside the 89",
            "R14",
            "U+3105 is donor-derived",
            edits=[
                (
                    "hiragana-ark-pixel.txt",
                    None,
                    "\nglyph U+3105 adv=12 x=0 cell=full ext=free top=9\n#\n",
                )
            ],
        ),
        cjk(
            "gate: a donor-derived mark between the two spans",
            "R14",
            "U+309B is donor-derived",
            edits=[
                (
                    "hiragana-ark-pixel.txt",
                    None,
                    "\nglyph U+309B adv=12 x=0 cell=full ext=free top=9\n#\n",
                )
            ],
        ),
        cjk(
            "gate: a donor-derived Bold drawing outside the 89",
            "R14",
            "U+3105 is donor-derived",
            edits=[
                (
                    "bold-overlays-ark-pixel.txt",
                    None,
                    "\nbold U+3105 adv=12 top=9 x=0 cell=full ext=free\n##\n",
                )
            ],
        ),
        cjk(
            "gate: a second copyright holder in OFL.txt",
            "R14",
            "OFL.txt: a copyright line credits 'Someone Else'",
            licence_edits=[
                (
                    "OFL.txt",
                    "Copyright (c) 2021, TakWolf (https://takwolf.com).\n",
                    "Copyright (c) 2021, TakWolf (https://takwolf.com).\n"
                    "Copyright (c) 2019, Someone Else (https://example.org).\n",
                )
            ],
        ),
        cjk(
            "gate: a second donor credited in FONTLOG.txt",
            "R14",
            "FONTLOG.txt: a credit sentence names no declared donor",
            licence_edits=[
                (
                    "FONTLOG.txt",
                    FONTLOG_ANCHOR,
                    FONTLOG_ANCHOR
                    + "\nSome Latin letters are adapted from Examplefont Sans.\n",
                )
            ],
        ),
        cjk(
            "gate: a known other font named in FONTLOG.txt",
            "R14",
            "FONTLOG.txt: names another font (Galmuri)",
            licence_edits=[
                (
                    "FONTLOG.txt",
                    FONTLOG_ANCHOR,
                    FONTLOG_ANCHOR + "\nThanks to the makers of Galmuri.\n",
                )
            ],
        ),
        cjk(
            "gate: a second donor credited in FONTLOG-CJK.txt",
            "R14",
            "FONTLOG-CJK.txt: a credit sentence names no declared donor",
            licence_edits=[
                (
                    "FONTLOG-CJK.txt",
                    FONTLOG_ANCHOR,
                    FONTLOG_ANCHOR
                    + "\nThe Hangul are adapted from Examplefont Sans.\n",
                )
            ],
        ),
        cjk(
            "gate: the donor named in FONTLOG-CJK.txt",
            "R14",
            "FONTLOG-CJK.txt: names the donor; the CJK face declares no donor",
            licence_edits=[
                (
                    "FONTLOG-CJK.txt",
                    FONTLOG_ANCHOR,
                    FONTLOG_ANCHOR
                    + "\nSome strokes are adapted from Ark Pixel Font.\n",
                )
            ],
        ),
        cjk(
            "gate: a second donor credited in NOTICE",
            "R14",
            "NOTICE: a credit sentence names no declared donor",
            notice_edits=[
                (
                    "This software depends on",
                    "  - Examplefont Sans -- the Hangul are adapted from it.\n\n"
                    "This software depends on",
                )
            ],
        ),
        cjk(
            "gate: a second copyright holder in NOTICE",
            "R14",
            "NOTICE: a copyright line credits 'Someone Else'",
            notice_edits=[
                (
                    "This software depends on",
                    "  - Copyright (c) 2019, Someone Else.\n\nThis software depends on",
                )
            ],
        ),
        cjk(
            "gate: a second holder in a name table of the existing face",
            "R14",
            "NifenArt-Regular.ttf name ID 0: a copyright line credits 'Someone Else'",
            ttf_fix=fix_existing_name0,
        ),
        cjk(
            "gate: the donor line in a CJK name table",
            "R14",
            "NifenArtCJKSC-Regular.ttf name ID 0: names the donor",
            ttf_fix=fix_cjk_name0_donor,
        ),
        cjk(
            "gate: the CJK face record declares a donor key",
            "R11",
            "face.txt declares donor_name: the CJK face declares no donor",
            [("face.txt", None, "donor_name = Ark Pixel Font\n")],
        ),
        cjk(
            "gate: the CJK face record declares a prior copyright line",
            "R11",
            "face.txt declares copyright_prior_line_1",
            [
                (
                    "face.txt",
                    None,
                    "copyright_prior_line_1 = Copyright (c) 2021, TakWolf.\n",
                )
            ],
        ),
        cjk(
            "gate: a CJK record file names the donor",
            "R14",
            "han-sc.txt: names the donor; the CJK face declares no donor",
            [("han-sc.txt", None, "# adapted from Ark Pixel Font\n")],
        ),
        cjk(
            "gate: a donor-derived file under the CJK folder",
            "R14",
            "a file of the CJK face named for the donor",
            [("hangul-ark-pixel.txt", None, "# a file\n")],
        ),
        cjk(
            "gate: a second copyright holder in a CJK source",
            "R14",
            "han-jp.txt: a copyright line credits 'Someone Else'",
            [("han-jp.txt", None, "# Copyright (c) 2019, Someone Else.\n")],
        ),
        cjk(
            "gate: NOTICE missing",
            "R14",
            "NOTICE is missing: a scanned file is never skipped",
            remove=["NOTICE"],
        ),
        cjk(
            "gate: FONTLOG-CJK.txt missing",
            "R14",
            "FONTLOG-CJK.txt is missing: a scanned file is never skipped",
            remove=["fonts/FONTLOG-CJK.txt"],
        ),
        cjk(
            "gate: OFL.txt missing",
            "R14",
            "OFL.txt is missing: a scanned file is never skipped",
            remove=["fonts/OFL.txt"],
        ),
        cjk(
            "gate: a font of the existing face missing",
            "R14",
            "NifenArt-Bold.ttf is missing: a scanned font is never skipped",
            remove=["fonts/NifenArt-Bold.ttf"],
        ),
        cjk(
            "gate: a CJK font missing while its set has glyphs",
            "R14",
            "NifenArtCJKJP-Bold.ttf is missing: the jp set has 1 glyph records",
            remove=["fonts/NifenArtCJKJP-Bold.ttf"],
        ),
        # The existing face stays as the merge left it
        (
            "freeze: a changed source file",
            [],
            "SCENARIO",
            "freeze: changed source",
        ),
        ("freeze: a changed font", [], "SCENARIO", "freeze: changed font"),
        ("freeze: a missing file", [], "SCENARIO", "freeze: missing file"),
        ("freeze: an added file", [], "SCENARIO", "freeze: added file"),
        ("freeze: a bad manifest line", [], "SCENARIO", "freeze: bad manifest line"),
        ("freeze: the manifest missing", [], "SCENARIO", "freeze: missing manifest"),
    ]
)


def main():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
    ok = True
    n = skipped = 0
    for ctl in CONTROLS:
        res = run(*ctl)
        if res is None:
            skipped += 1
            continue
        n += 1
        ok &= res
    print("controls run: %d   skipped (record not in the sources): %d" % (n, skipped))
    print("ALL CONTROLS CAUGHT" if ok else "SOME CONTROL MISSED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
