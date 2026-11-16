# ADR-0073 — Six more interface languages: localisation vehicles, guide locale metadata and the Nifen Art CJK face

| Field | Value |
| --- | --- |
| Status | **Proposed** — becomes Accepted when the change that implements it merges |
| Date | 2026-10-24 |
| Author | Architecture |
| Feature | Six more interface languages: French, German, Russian, Simplified Chinese, Korean, Japanese (`REQ-L10N-UI-*`, `REQ-L10N-DATA-*`, `REQ-L10N-BUILD-*`) |
| Grounded by | `REQ-L10N-UI-002`, `-003`, `-008`, `-012`; `REQ-L10N-BUILD-001`, `-002`, `-007`, `-008`; Article I (layering), Article II (numeric and range data in `logic/constants.py`), Article V.2 (wrapped strings), Article VIII §3 (no weakened gate); `scripts/check_layering.py` and `scripts/check_cycles.py` run on the base and over a scratch copy of the package carrying the planned imports (output quoted below); ADR-0043 §1 (scope of `testing/suites/deploy/`), ADR-0047 (scope of `testing/suites/scripts/`), ADR-0068 and its Amendment (2026-10-10); Qt rendering measurements on Windows 11 with PySide6 6.11.1 (an internal measurement record outside this repository) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0029, ADR-0043, ADR-0047, ADR-0067, ADR-0068 (and its Amendment (2026-10-10) — font sources adapted from another font), ADR-0071 (and its two Amendments (2026-10-10) — the Bold dock-title mechanism and the guide faces; the hiragana adapted from Ark Pixel Font, the widened kana cell and the Reserved Font Name) |

## Context

The product ships `en` and `es`. This release adds six languages — `fr`, `de`, `ru`, `zh_CN`,
`ko`, `ja` — a translated user guide in each, and an original CJK extension of Nifen Art, because
the existing face holds no Han and no Hangul character (771 code points per weight, 0 Han,
0 Hangul, measured at the base). Each new file needs exactly one location, a statement of whether
it ships, and a test home. Three facts constrain placement:

1. `logic/` and `data/` import no Qt (Article I).
2. ADR-0068: sources do not ship, and whatever is read at run time is package data in the wheel
   and in all three installer specs.
3. ADR-0047: `testing/suites/scripts/` tests the repository's CI-gate scripts; asset build tools
   are tested under `testing/suites/asset_pipeline/`.

Two records this decision builds on changed after they were first written, and their amendments
govern here. ADR-0068's Amendment (2026-10-10) records that the hiragana sources in
`fonts-src/nifen-art/` are adapted from another OFL-licensed pixel font and that placement did not
move. ADR-0071's Amendment (2026-10-10) on the hiragana records that Nifen Art is original
**except** those 89 hiragana, and that `OFL.txt` carries the donor's copyright line, then Nifen
Art's line with the Reserved Font Name "Nifen Art". ADR-0071's other Amendment (2026-10-10) records
that Bold dock titles are a stylesheet weight, `QDockWidget { font-weight: bold; }`, not a font
object.

## Decision

1. **Locale, language and font-chain logic** are Qt-free modules in `pixelart_creator/logic/`:
   `locale_match.py`, `language_names.py` and `font_chain.py`. `ui/i18n.py`, `ui/main_window.py`
   and the font-registration module `ui/app_font.py` apply them. `ui/app_font.py` exposes no
   font-role API; the family chain is applied inside the functions that build each target font
   (the interface font, the system-mode font and its per-class fonts, the guide page font), not in a
   second application step, so the module's own "is the font already applied" comparisons stay
   true. The Han and Hangul code-point ranges are one data table in `logic/constants.py`
   (`HAN_RANGES`, `HANGUL_RANGES`), the single source for `ui/` and for the font scripts; no range
   literal is restated elsewhere (Article II).
2. **Endonyms are data**, held in `logic/language_names.py`, not catalogue messages. **Reading of
   Article V.2 (stated):** Article V.2 ("every user-visible string is wrapped in `tr()` /
   `translate()`") exists so that text can be translated. A language's self-name is not
   translatable text: `REQ-L10N-UI-003` fixes the same eight byte strings for every active language
   and forbids translating them. So Article V.2 does not cover language self-names, and wrapping
   them would contradict the requirement. The precedent is the raw-code label the selector shipped
   unwrapped (`QAction(code, self)`). **The evidence is the byte-exact endonym test**
   (`testing/suites/logic/test_language_names.py`) and the application-level invariance test
   (`testing/suites/ui/test_l10n_languages.py`, SC-L10N-UI-003-2). The string audit is **not**
   evidence for this reading: its scope, `pixelart_creator/ui`, does not read `logic/`, so its
   result shows only where the strings live. Each entry is drawn with its own
   language's family chain (`font_chain.label_chain`), so 简体中文 always shows Simplified forms and
   日本語 Japanese forms (maintainer ruling, 2026-10-11).
3. **Guide locale metadata** lives in each locale tree as
   `userguide_content/content/<lang>/meta.json`, owned by the tree's owner. `manifest.json` remains
   the English and structural source of the guide bundle (ADR-0029). Package data gains `userguide_content/content/*/*.json`
   (today's `userguide_content/*.json` glob reaches `manifest.json` only).
4. **Catalogue and distribution vehicles.**
   - `scripts/check_catalogues.py` (catalogue lint, with the plural inventory),
     `scripts/ts_worklist.py` (worklist export and import), `scripts/i18n_extract.py`
     (count-guarded extraction) and `scripts/check_l10n_typography.py` (typography rules) are
     CI-gate scripts, maintained by the localisation owner;
   - `scripts/check_vocabulary_regrowth.py` gains a scoped mode over the shipped catalogues and
     guide trees;
   - all of the above are tested in `testing/suites/scripts/` (ADR-0047 scope);
   - `packaging/check_payload.sh` (the payload content check the wheel and each installer already
     pass through) gains the CJK files in its required list and a test module in
     `testing/suites/deploy/` (ADR-0043 §1: that suite owns `packaging/**`); it runs on the wheel in
     PR CI and on each installer in the installer workflow, each time followed by a negative
     control. There is no second distribution checker: a script beside it would examine the same
     payloads for an overlapping property, two drift surfaces for one rule;
   - **`NOTICE` in every distribution (`REQ-L10N-BUILD-008`).** The wheel already carries the root
     `NOTICE` under its `.dist-info` licence files (measured: byte-identical to the root file), so
     it needs no change. Each `packaging/pysidedeploy-<os>.spec` gains
     `--include-data-files=NOTICE=NOTICE`, which places `NOTICE` beside the distribution's
     `pixelart_creator/` data folder. `check_payload.sh` compares, for each payload package folder
     `<parent>/pixelart_creator` it finds, exactly these candidates: `<parent>/NOTICE`,
     `<parent>/*.dist-info/licenses/NOTICE` and `<parent>/*.dist-info/NOTICE`. At least one must
     exist, every one that exists must equal the checkout's root `NOTICE` byte for byte, each path
     compared is printed, and zero compared fails.
5. **The CJK face** follows ADR-0068's anticipated layout ("`fonts-src/` is the root for every
   future non-shipped font source"):
   - sources in `fonts-src/nifen-art-cjk/` (not shipped); the grid is read from
     `fonts-src/nifen-art/metrics.txt`, never restated;
   - built by `scripts/font/build_nifen_art.py --face nifen-art-cjk`;
   - measured by `scripts/font/measure_cjk_set.py`, and covered by the extended
     `scripts/font/check_glyph_coverage.py`;
   - shipped as `pixelart_creator/fonts/NifenArtCJK{JP,SC,KR}-{Regular,Bold}.ttf` with
     `FONTLOG-CJK.txt`, under OFL-1.1 with the existing `OFL.txt`, whose copyright lines and
     Reserved Font Name (ADR-0071, Amendment (2026-10-10) on the hiragana) already cover the CJK
     families.

   Every CJK glyph is drawn for this project or composed by recipe from Nifen Art's own glyphs; the
   face takes no donor, and the font build's donor gate keeps the two files ADR-0068's Amendment
   (2026-10-10) names as the only donor-derived sources. The wheel names each new file in package
   data. The installers already include `pixelart_creator/fonts` whole. The scripts are tested in
   `testing/suites/asset_pipeline/`.
6. **Three families, not one.** Two Han form sets cannot share one character map without `locl`,
   and Qt selects the shaping language per process (Qt's documented per-process shaping language;
   the separate-family alternative is the documented one). Each family ships a Bold file whose
   glyphs equal Regular's, because Qt synthesises Bold when a family has no Bold face (measured).
   Bold dock titles need no separate call: they inherit the application font's family list as a
   stylesheet weight, and Qt picks each family's Bold file.
7. **The existing face is frozen** at the merge of the visual-identity work by
   `fonts-src/nifen-art-cjk/existing-face.sha256`, checked by an asset-pipeline test. A separate
   `FONTLOG-CJK.txt` is what lets every file of the existing face, its change log included, stay
   byte-identical.
8. **Qt's own catalogues.** Each installer spec lists
   `--include-package-data=PySide6:translations/qtbase_<code>.qm` for the six new codes. That is
   18 lines, following the specs' own comment ("ADD the matching `qtbase_<code>.qm` entry here
   whenever a new UI language ships", ADR-0067).
9. **Release-evidence tests** live in a new test package, `testing/suites/release/`. It holds tests
   over repository state that a release ships with, not over product code: the branch's ancestry to
   a recorded merge, the gate thresholds against a recorded base sha, and the release CHANGELOG's
   required statements. No test there imports `pixelart_creator.ui`. `testing/` is outside the
   `pixelart_creator` import graph (`check_layering --root .` reports it exempt), and `testpaths`
   already collects `testing/suites`. **Consequence:** the ancestry test holds a recorded sha (the
   merge of the visual-identity work); the threshold test compares the pull request's head with the
   merge base of that head and `main`, so a threshold change that lands on `main` in the meantime,
   once taken into the branch, moves the merge base and is not counted as the pull request's
   change. A threshold change made on the branch itself, ruled by the maintainer, is a difference
   the test reports; it must be declared in the test's expected values in the same commit, visibly
   (Article VIII §3).

New modules import internal modules in the module form,
`from pixelart_creator.<layer>.<module> import <name>`, never `from pixelart_creator.<layer> import
<module>` or `from . import <module>` (see "What has no detector").

**Proof (scripts, not reading).** Baseline on the branch at the base (2026-10-24, Python 3.13):
`check_layering --root pixelart_creator` exit 0,
`{"scanned": 240, "unregistered": [], "violations": []}`; `check_layering --root .` exit 0,
`testing`, `scripts`, `deploy` and `memory` reported `ungoverned`, `pixelart_creator` `delegated`,
`"violations": []`; `check_cycles --root pixelart_creator` exit 0,
`{"cycles": [], "edges": 893, "modules": 242}`. On a scratch copy of the package with stubs carrying
the planned imports in the module form (`logic/locale_match.py`; `logic/language_names.py`;
`logic/font_chain.py` → `logic.language_names`, `logic.constants`; `ui/i18n.py` →
`logic.locale_match`; `ui/main_window.py` → `logic.language_names`, `logic.font_chain`; the real
`ui/app_font.py` → `logic.font_chain`, `logic.constants`): `check_layering` exit 0,
`{"scanned": 243, "unregistered": [], "violations": []}`; `check_cycles` exit 0,
`{"cycles": [], "edges": 900, "modules": 245}`. Controls on the same copy: a PySide6 import in
`logic/font_chain.py` → `check_layering` exit 1 naming `logic/font_chain.py`; an import of
`pixelart_creator.ui.main_window` written in the module form in `ui/app_font.py` → `check_cycles`
exit 1, cycle `ui.app_font → ui.main_window → ui.user_guide`; the same back-edge written
`from pixelart_creator.ui import main_window` → exit 0, no cycle (the blind spot below). The edge
`ui/main_window.py` → `ui/app_font.py` already exists at the base, so this change adds no edge into
the font module, and the font module must never import `main_window` back.

## Alternatives Considered

- **Endonyms as catalogue messages.** Rejected: `REQ-L10N-UI-003` fixes the same byte strings in
  every active language and forbids translating them; a catalogue entry is by construction
  translatable, so each of seven catalogues would carry a message whose only correct translation
  is the source, with nothing to stop it drifting.
- **One CJK family with `locl` for both Han form sets.** Rejected: Qt selects the shaping language
  per process, so one family cannot show Simplified and Japanese forms side by side in the language
  selector.
- **A CJK family without a Bold file.** Rejected: Qt then synthesises a Bold (measured) for the
  Bold dock titles instead of drawing a face this project built and checks.
- **Guide locale metadata inside `manifest.json`.** Rejected: seven trees' owners would edit one
  shared file; per-tree `meta.json` lets each tree's owner edit only its own folder, and a ninth
  tree is a folder.
- **A separate distribution-notice script beside `check_payload.sh`.** Rejected as duplication:
  the existing check already compares every shipped font and theme file byte for byte on the wheel
  and on each installer payload.
- **A tracked copy `pixelart_creator/NOTICE`, shipped as package data.** Rejected: a second,
  editable copy of the file in the repository, kept equal only by a test.
- **A search for any file named `NOTICE` anywhere in a payload.** Rejected: a bundled third-party
  package's own `NOTICE` would become a failure, or a pass. The candidate set is fixed and named.
- **Release-evidence tests in `testing/suites/scripts/`.** Rejected: that root tests the
  repository's CI-gate scripts (ADR-0047); these tests read repository state, not a script.
- **For the family-chain order: the platform family first everywhere** (it would draw Han in the
  platform's forms) **or the CJK families first everywhere** (every machine would take the CJK
  face's line metrics). Rejected by the maintainer in favour of the rule under "What has no
  detector".
- **Declined as speculative generality:** a plugin or registry for languages; a rule language for
  the typography check (a per-language table is enough for six languages); a face count beyond the
  two `--face` values.

## Consequences

**What this enables.**

- A ninth language is a catalogue, a guide tree with `meta.json`, an endonym row, a matching-table
  row (if it has territory or script forms), three spec lines and, if it is CJK, a form set.
- A Traditional Chinese form set is one more family name in the chain, not a code change in
  `ui/`.
- A fourth distribution form (for example a `.deb`) joins the `NOTICE` check by adding one
  candidate path, with its test case.
- A shipped catalogue with no endonym fails a test instead of showing a raw code in the selector.

**Accepted costs (maintenance).**

- An English guide edit must reach seven trees, or the parity gate fails.
- A translation that adds a Han or Hangul character fails coverage until it is drawn.
- An English string change must reach seven catalogues through the worklist export and import.
- Each installer spec gains 18 Qt catalogue lines and one `NOTICE` line; package data gains the
  six CJK fonts, `FONTLOG-CJK.txt` and the `meta.json` glob.

**What it constrains.** `logic/locale_match.py`, `logic/language_names.py` and
`logic/font_chain.py` stay Qt-free (`check_layering`); `ui/app_font.py` never imports
`ui/main_window.py` (`check_cycles`, in the module form); range data stays in
`logic/constants.py`; `fonts-src/nifen-art-cjk/` holds no `.py` and no `__init__.py`; the existing
face stays byte-identical to `existing-face.sha256`; `check_payload.sh` stays the one payload
check.

## What has no detector, stated rather than implied

- `check_cycles` does not see `from pixelart_creator.logic import font_chain`-style imports, nor
  `from . import <module>` (ADR-0068, "What has no detector"; reproduced on this base by the
  controls above). Resolving that form at the base adds 35 edges the script does not count and
  still finds 0 cycles, so the base's verdict holds; but the script's exit 0 is not proof for code
  written in that form, which 39 files under `pixelart_creator/` use today. New modules use the
  module form, and that is a review rule until the script resolves the package form.
- The ordering of the family chain on Linux and macOS is proven only by the 3-OS tests
  (`testing/suites/ui/test_font_family_chain_mechanism.py`,
  `testing/suites/ui/test_l10n_glyph_coverage.py`), not by a static check. On Windows the
  `offscreen` platform plugin sees only application-registered fonts and has no operating-system
  fallback beyond the list, so those tests register every family they judge, and the
  operating-system fallback clause is proven on the Linux leg only.
- **The family-chain order rule:** no family placed before the CJK families may hold a Han or
  Hangul character. On a machine whose platform UI font holds a shipped Han or Hangul character (a
  check made at run time, per font role), that platform family is placed after the CJK families; on
  every other machine the platform family stays first. The maintainer chose this trade-off over the
  alternatives (keeping the platform family first everywhere, which would let it draw Han; or
  putting the CJK families first everywhere). **The accepted cost:** on such a machine, text in the
  platform-font roles keeps the system glyphs but takes the CJK face's line metrics — and this
  includes the guide's page text, whose default font is the platform font. The truncation test's
  vertical check measures that cost as clipping on labels and guide pages.
- Where Nuitka places `--include-data-files=NOTICE=NOTICE` on each operating system, and whether a
  plain file at that position affects macOS signing, is not measured when this record is written.
  The fonts and themes are already plain files in the same tree, which is a precedent, not a proof;
  the installer workflow's check prints the path it compared on each leg, and a `NOTICE` outside
  the candidate set is a placement question, never a reason to widen the set.
- Whether `QFont` equality treats a family list as the application's "already applied" comparisons
  need is not measured; the change that puts the chain into `ui/app_font.py` measures it.
