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
- Each installer spec gains 6 Qt catalogue lines (18 across the three specs) and one `NOTICE` line;
  package data gains the
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

## Amendment (2026-11-18) — the chain tag: Qt's font cache shares a family list's tail

This record was committed before the decision below was taken. The decision text above is left as
written; this section adds to decision 1.

### Context: the cache behaviour, as measured

In one process, a font whose family list has the **same first family, pixel size and weight** as a
font drawn earlier is drawn with the **earlier list's later families**. Measured first on Windows 11
(PySide6 6.11.1, the `offscreen` platform plugin, application-registered fixture faces, the drawing
family read from `QTextLayout` glyph runs): `[Nifen Art, A]` drawn first, then `[Nifen Art, B]`, and
the second draws its Han and Hangul from `A`. A different pixel size, weight, italic, stretch, style
hint, style strategy or style name gets its own tail. Letter spacing, kerning and underline do not.
`QApplication.setFont`, `QFont.insertSubstitutions` and idle time do not clear it. The sharing was
then reproduced on **Linux, Windows and macOS** by the pull request's CI legs.

The chains of decision 1 are exposed. The Simplified and Japanese lists share their first family
(Nifen Art, or the platform family), and the language selector shows 简体中文 and 日本語 at once, so
the second list built would draw its Han in the first list's forms (SC-L10N-UI-012-1, -2). **The
mirror is measured too:** a one-family font drawn after an untagged chain of the same first family
draws its Han from that chain's tail. The reverse order was measured not to happen.

### Decision

1. **The invariant.** Two fonts the application draws with must not agree on every attribute that
   Qt's font cache keys on unless their family lists are equal. As measured, those attributes are
   the first family, pixel size, weight, italic, stretch, style hint, style strategy and style name;
   the families after the first are not among them.
2. **The one-family rule.** An untagged style strategy belongs to one-family fonts only. Every
   family list of two or more families that the application draws with carries a tag, and a family
   reaches a font in `ui/` only through `chain_font`. A one-family list has no tail to share, and
   it is what every font Qt builds by itself already is.
3. **The mechanism: a chain tag carried in the style strategy.**
   - `logic/font_chain.py` (Qt-free): `ChainTagRegistry(capacity)` with
     `tag_for(families) -> int | None`. The same list always gets the same tag. Family names are
     compared case-insensitively, as Qt compares them. Two different lists with the same first
     family get different tags, and lists with different first families are allocated
     independently. A one-family list returns `None` (untagged) and uses no capacity. A first family
     that would need more lists than the capacity raises `ChainTagsExhausted`, naming the family; an
     empty list raises `ValueError`. **The capacity is not a tuning value:** it is the length of
     the flag table in `ui/`, passed in by the caller, so `logic/constants.py` gains no constant and
     `logic/` holds no Qt-derived number.
   - `ui/app_font.py`: `_CHAIN_TAG_STRATEGIES` holds one combination of the kept flags per tag, and
     one module-level registry is sized by it. **`chain_font(base, families) -> QFont` is the only
     place a family list is put on a font:** it copies `base`, calls `setFamilies(families)`, clears
     every tag flag from the base's style strategy and sets the list's flags (clearing first, so a
     flag already on the base cannot mask the tag). A `setFamilies(` or `setFamily(` call elsewhere
     in `ui/`, or a family name passed to a `QFont` constructor other than the base that
     `interface_font()` hands to `chain_font`, is a defect.
   - On `ChainTagsExhausted`, `chain_font` logs a warning naming the list and returns **the first
     family alone, untagged**. Its Han then comes from substitution or the operating system's
     fallback: visibly wrong and logged, but drawn from no other font's face, and no other font is
     changed. An untagged chain is exactly the font that produced the mirror, so the exhausted path
     never makes one.
4. **The kept flags, and what grounds them.** `QFont.StyleStrategy.PreferMatch`, `PreferQuality`,
   `PreferOutline` and `ForceOutline`, **all four kept on all three operating systems** by the
   pull request's three-OS measurement step. Each flag separates (it gives a list its own tail) and
   is neutral (no difference in glyph runs, layout pixels, label pixels or eight font metrics at 12,
   13 and 24 px). The 15 non-empty combinations each draw their own tail.
   - **Documentation:** the Qt 6.6 and current `QFont` pages
     (<https://doc.qt.io/qt-6.6/qfont.html>, <https://doc.qt.io/qt-6/qfont.html>) describe the four
     only as font-type and size-selection hints. No page says they affect glyph selection, merging,
     fallback, hinting, antialiasing or metrics.
   - **Source, Qt 6.11:** the style strategy is part of `QFontDef`'s comparison and hash
     (<https://raw.githubusercontent.com/qt/qtbase/6.11/src/gui/text/qfont_p.h>), and each fallback
     engine is requested with a copy of the primary font's definition, so a tag reaches every cache
     layer read. The fontconfig backend reads none of the four
     (<https://raw.githubusercontent.com/qt/qtbase/6.11/src/gui/text/unix/qfontconfigdatabase.cpp>).
     `PreferMatch`, `PreferQuality` and `ForceOutline` are read in foundry and size selection
     (<https://raw.githubusercontent.com/qt/qtbase/6.11/src/gui/text/qfontdatabase.cpp>).
   - **Not grounded by reading:** the DirectWrite, GDI and CoreText handling of the four flags. The
     measurement on the Windows and macOS legs covers that. That the style strategy is part of the
     cache key is **measured and read in the source; it is not documented**.
5. **The table's order: fewest flags first, the size-matching flags before the outline ones**
   (`PreferMatch`, `PreferQuality`, `PreferOutline`, `ForceOutline`). Tags 1 to 3 are
   `{PreferMatch}`, `{PreferQuality}` and `{PreferOutline}`. Today's two lists per first family take
   tags 1 and 2, so **no tag the product allocates today carries an outline flag.** A third list
   would take tag 3, `{PreferOutline}`, which the three-OS measurement of the kept flags found
   neutral at 12, 13 and 24 px. A fallback face with a bitmap style is not measured.
   Reason: `ForceOutline` is a filter in foundry selection that skips styles that are
   not smoothly scalable, and the outline flags' documented subject is outline against bitmap. A
   platform or fallback face behind the CJK faces is where a bitmap style could exist, and that case
   is not measured. This is a minimal-exposure choice, not a claim that the outline flags misbehave.

### Alternatives considered

- **Distinct first families per chain.** Rejected: the Nifen-mode chains would then collide with the
  system-font chains whenever the guide page and the interface share one process, and putting the
  CJK families first in the platform chain would change the platform text's line box on every
  machine, which the maintainer's family-order ruling (above, "What has no detector") excluded.
- **A distinct tail length per chain.** Rejected: a source reading suggests that the multi-engine
  key orders fallback lists by their size only. That reading is unresolved, it is not Qt's
  documented behaviour, and it was not measured as the cause. It also cannot tell the Simplified
  and Japanese chains apart, which have equal length, without padding the ruled family lists.
- **Clearing the font cache on a language switch.** Rejected: application-font registration and
  removal clear Qt's font cache as a side effect (6.11 source), which is not a documented contract.
  Whether a clear equals a fresh process is unresolved, and it cannot help the selector, where both
  forms are on screen at once.
- **A stateless tag that encodes only the Han form.** Rejected: it is enough for the two forms, but
  not for two per-class platform fonts with different Han-capable families.
- **Stretch, style hint or style name as the carrier.** Rejected: stretch has only two neutral
  values; the style hint may steer fallback under fontconfig (not verified); the style name changes
  which face is matched.

### Consequences

- One more font engine per tagged list, a handful per process.
- A third Han form (Traditional Chinese) needs one more list per first family and fits the
  capacity. Past the capacity, the exception names the family; nothing is silent.
- **Tests.** `testing/suites/logic/test_font_chain.py`: the registry's injectivity, against a copy
  keyed on the first family only, as Qt's cache is (it must fail). The three-OS mechanism module
  `testing/suites/ui/test_font_family_chain_mechanism.py`: an untagged pair shares a tail where the
  platform shares at all, a tagged pair does not, and tagged and untagged renderings are
  pixel-identical. The application-level and glyph-level checks walk every font the application
  holds and draw both selector labels in each build order, each beside an untagged control.

### Escalation route

If a later Qt or platform shares tails and the style strategy does not separate them there, the
three-OS mechanism test is red on that platform. The decision then returns to architecture. The
directions known within the maintainer's family-order ruling would be used up, so the question goes
to the maintainer as a re-opening of that ruling. An implementer does not change it.

## Amendment (2026-11-18) — soft line breaks in guide pages (`REQ-L10N-UI-014`)

This record was committed before the decision below was taken. The decision text above is left as
written. Grounded by the feature's implementation plan, section 9.17, as revised in its sections
9.19, 9.20, 9.22 and 9.23 (a design record kept outside this repository), and by `REQ-L10N-UI-014`.

### Context

Markdown shows a line ending inside a paragraph as a space. Where a translator wrapped Japanese or
Chinese text, the guide window then shows a stray space between two ideographs. `REQ-L10N-UI-014`
decides, for each such break, from the visible characters on either side and in the spec's clause
order, whether the window removes it.

### Decision

1. **The seam.** One Qt-free module, `logic/guide_softbreak.py`, holds the rule. Its public surface
   is `decide(before, after, language) -> SoftBreakClause` and
   `apply_soft_break_rule(markdown, language) -> SoftBreakResult`, which returns the text to show and
   every break it examined, removed or kept, with the clause that decided it. It imports the standard
   library and `logic.constants` only. `ui/user_guide.py` applies it between the content reader and
   `QTextDocument.setMarkdown`. **`data/guide_content.read_content` stays the raw-source reader.** A
   page in which no break is removed is returned byte for byte, and the transform is idempotent
   (a stated property of its contract, checked by a property test).
   - Rejected: **inside `read_content`.** Other readers, and the guide's structure checks, count the
     source's lines and tokens, and the rule is a display decision over characters, not I/O
     (Article I).
   - Rejected: **post-processing the `QTextDocument` in `ui/`.** The domain rule could then be tested
     only through Qt, and Qt exposes no map from source positions to document positions.
   - Rejected: **a CommonMark library at run time.** It is not a declared dependency, and it is not
     the renderer: Qt's own Markdown parser is.
   - Rejected: **unwrapping the content.** The maintainer ruled it out.
   - Rejected: **iterating the transform to a fixed point.** It would hide a guard's inconsistency
     instead of removing it, and break the linear bound.
2. **The joiner, and its measurement.** A removed break joins two lines. The joiner is empty, except
   where the source characters at the join would form Markdown syntax, and then it is an empty HTML
   comment, `<!---->` (`SOFT_BREAK_JOINER`). Let L be the source character before the break and R the
   one after it. The comment is inserted when L or R is `*`, `_` or `~`; when both are a backtick;
   when L is `]` and R is `(`, `[` or `:`; or when L is `!` and R is `[`.
   - **Measured** with PySide6 6.11.1 (`setMarkdown`, then `toPlainText` and the bold fragments,
     offscreen): `**移動。**`, a line ending, then `を選ぶ` shows 移動。 in bold. Joined plainly, the
     closing run is no longer right-flanking, and the literal `**` shows with no bold. Joined with the
     comment, 移動。 is bold again and the comment shows nothing.
   - A paragraph whose parse the join would change keeps its breaks. Tables start and end where Qt
     starts and ends them.
   - The joiner's effect is measured on 6.11.1 only, not at the 6.6 floor.
3. **The tables: their version and source.** Script=Hangul, Script=Latin and Emoji are not in
   `unicodedata`. They are therefore inclusive range tables in `logic/constants.py`
   (`GUIDE_HANGUL_SCRIPT_RANGES`, `GUIDE_LATIN_SCRIPT_RANGES`, `GUIDE_EMOJI_RANGES`), with
   `GUIDE_UCD_TABLES_VERSION = "16.0.0"`.
   - They were generated deterministically from byte-exact copies of Unicode 16.0.0's `Scripts.txt`
     and `emoji/emoji-data.txt`. Each table's total equals its file's own "Total" line (Emoji:
     `GUIDE_EMOJI_TOTAL_ELEMENTS = 1431`), and both files' SHA-256 are quoted in the module's
     docstring.
   - East Asian Width, the general category and decimal digits come from the running `unicodedata`.
   - **Invariant:** the tables' version equals the UCD version of the interpreter that
     `.python-version` names. The tables are not `HANGUL_RANGES`, which is the Hangul Syllables block
     for font coverage and excludes the jamo that clause 2 counts as Hangul.
   - Rejected: **keeping 15.1.0 with a declared version split.** It would commit about 296 KB of UCD
     data, and the rule would read Script and Emoji at one version and East Asian Width at another.
   - **Recurrence, accepted:** each interpreter move that changes `unidata_version` needs a new
     byte-exact pair of files.
4. **Clause 4's marks are data.** `GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS` in `logic/constants.py` maps a
   page language to its marks, as `REQ-L10N-UI-014` clause 4 lists them: `ja` → 、 。 「 」 『 』;
   `zh_CN` → 、 。 ， ； ： ！ ？ （ ） 《 》 “ ”. A mark not in its page's list leaves the break as a
   space. The languages of clauses 3 and 4 are data too (`CLAUSE3_LANGUAGES`, and
   `CLAUSE4_LANGUAGES`, derived from the mapping). Changing a list is a data edit plus scenario
   rows, not a code change.

### Consequences

- The Simplified Chinese guide tree takes the rule with no code change.
- If the guide's full-body search is ever built, it indexes the rule's output, the text the reader
  sees, never the raw source.
- **Tests:** `testing/suites/logic/test_guide_softbreak.py`, `test_guide_softbreak_join.py`,
  `test_guide_softbreak_tablemodel.py` and `test_guide_softbreak_tables.py` (the logic layer and the
  tables), and `testing/suites/ui/test_user_guide_softbreak.py` (what the window shows).
- **What has no detector:** idempotence is argued from the rules and checked by a property test, not
  proven. The joiner's effect is known for PySide6 6.11.1 only.
