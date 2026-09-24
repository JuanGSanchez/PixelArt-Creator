# ADR-0067 — About dialog: one link seam, text-role links, a call-time version, and Qt's own catalogues

| Field | Value |
|---|---|
| Status | **Accepted** (decided 2026-09-24; implementation lands on branch `feat-about-dialog-version`, not yet merged) |
| Date | 2026-09-24 |
| Author | Architecture |
| Feature | Show the application version in the app (issue #72) |
| Grounded by | REQ-AV-UI-001, REQ-AV-UI-005, REQ-AV-UI-010, REQ-AV-UI-011, REQ-AV-UI-012, REQ-AV-LOGIC-001; Article I (layering), Article II §1 (no magic numbers in `ui/`), Article V §2–§3 (localisation, colours defined once by role); WCAG 2.x 1.4.1 and 1.4.3; the Qt sources and catalogue cited under Part 4 |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0065 (test paths are `testing/suites/…`) |

## Scope of this record

This record holds **four** decisions that were taken together for one feature: the window title
shows the version, and a new **Help ▸ About PixelArt Creator** entry opens an About dialog. The
decisions are recorded in one file because none of them has a consumer outside this feature yet.
Each one is numbered (Part 1 to Part 4), and a later ADR that changes one of them supersedes **that
part by number** and leaves the others standing.

## Context

Before this change the desktop application showed its version nowhere. The only place
`pixelart_creator.__version__` reached a user was the metadata of an exported file. A user filing a
bug could not say which build they were running. The feature adds the version to the main window
title and adds an About dialog with the name, version, licence, three links (repository,
documentation, releases), a one-line environment summary and a Copy button.

Four constraints made the obvious implementation unavailable.

1. **Nothing in the application opened an external URL before this.** A search of
   `pixelart_creator/` for `QDesktopServices`, `openUrl` and `webbrowser` finds nothing. The one
   rich-text surface, the User Guide viewer, deliberately disables external links
   (`setOpenExternalLinks(False)` and `setOpenLinks(False)` in `ui/user_guide.py`) and resolves every
   anchor inside the guide. The About dialog is therefore the first place where a click leaves the
   application. It is also a place where the tests must prove two things: a click hands off the
   right address, and opening the dialog opens nothing (REQ-AV-UI-005, REQ-AV-UI-011).
2. **Qt's default link colour fails in the dark theme.** A rich-text anchor with no style renders
   in the palette's `Link` colour, `#0000ff`. Against the dark `background` role (`#2b2b2b`) that is
   **1.65:1**, far below the 4.5:1 that REQ-AV-UI-010 requires. The product's `accent` role, the
   natural "link-looking" colour, is **2.88:1** against the same background, which also fails.
3. **The version must be read when it is shown, not when a module is imported.** The product's
   existing idiom, `from pixelart_creator import __version__` (used by `logic/export.py`), binds the
   value once at import time. REQ-AV-UI-001 requires the title and the dialog to show the version
   the running package reports, and the tests prove that by installing a different value at run
   time. An import-time binding cannot see it.
4. **On macOS, Qt discards the About action's own text.** An action with
   `QAction.MenuRole.AboutRole` is moved into the application menu, and its label there is generated
   by Qt's Cocoa platform plugin as `QCoreApplication.translate("MAC_APPLICATION_MENU", "About %1")`
   with the bundle name substituted. That string is translated only by **Qt's own** catalogue
   (`qtbase_<locale>.qm`), never by the application's. Until now the application installed no Qt
   catalogue, and all three installer specs passed `--noinclude-qt-translations`, so the macOS entry
   would read "About PixelArt Creator" in a Spanish session. REQ-AV-UI-012 requires the entry to
   follow the interface language.

## Decision

### Part 1 — Every external link goes through one seam

**We will route every external-URL hand-off in the About dialog through one module-level function,
`_open_url(url: str) -> None` in `pixelart_creator/ui/about_dialog.py`.** It is the only caller of
`QDesktopServices.openUrl` in that module. Each link is its own `QLabel` with
`openExternalLinks=False`, whose `linkActivated` signal calls `_open_url`. Each label carries a `url`
property equal to its `href`, so a test can read the target without parsing HTML. The three
addresses are constants in `pixelart_creator/logic/about_info.py`, `REPOSITORY_URL`,
`DOCUMENTATION_URL` and `RELEASES_URL`, and nowhere else. The dialog imports nothing from
`QtNetwork` and nothing that opens a socket.

This is the product's **first external-URL surface**. It sets the pattern for any later one: a
single named seam, addresses held as constants, and no automatic link opening.

### Part 2 — Links use the `text` role, underlined

**We will colour each link with the theme's existing `text` role and underline it.** The colour is
reached through a new accessor, `theme.link_colour(name) -> QColor`, which returns the `text` role.
The anchor carries an inline `color:<text role>; text-decoration: underline`. No new role and no new
hex value are added. The underline is the non-colour cue that marks the text as a link (WCAG 1.4.1),
so the link does not depend on a hue difference from body text.

Measured contrast against each theme's `background` role (WCAG relative-luminance formula, computed
from the role values in `ui/theme.py` and re-checked when this record was written):

| Candidate | Light (`#f0f0f0`) | Dark (`#2b2b2b`) | Meets 4.5:1 in both? |
|---|---|---|---|
| `text` role (`#202020` / `#e0e0e0`) | **14.30** | **10.73** | yes |
| `accent` role (`#1f6fb2` / `#2a72c0`) | 4.64 | **2.88** | no, fails dark |
| Qt palette default link (`#0000ff`) | 7.54 | **1.65** | no, fails dark |

The **rendered** measurement agrees. Grabbing a `QLabel` anchor on the dark background and taking
the most-contrasting glyph pixel gives 10.73:1 with the inline text-role style and 1.65:1 with the
palette default.

### Part 3 — The version is read at call time; name and version are composed in `logic/`

**We will read the version through `about_info.app_version()`, which imports the package and reads
`pixelart_creator.__version__` on every call. The title is built by
`about_info.window_title(self.tr("PixelArt Creator"))`, which returns `"<translated name> <version>"`.**
The environment line is composed by the Qt-free function
`about_info.compose_environment_line(facts, unknown)`. It always returns exactly one line, and each
missing fact shows the caller's translated placeholder in its own slot only. The two facts that need
Qt (the runtime Qt version and the PySide6 version) are read in `ui/about_dialog.py`, each through
its own function that returns `None` on failure. They are then passed into the logic composition.

Joining the translated name and the version in `logic/` is **not** a translated-string
concatenation. The project's string audit flags `tr(...) + ...` because joining translated
fragments fixes word order that another language may need to change. A product name followed by its
version number is an identity pair, not a sentence: no language reorders it, and the version is
never translated. Keeping the join outside `tr()` has two further effects. The existing
`PixelArt Creator` catalogue message is reused unchanged. And no translation can drop the version,
which a `%1` placeholder inside a translated string would allow.

### Part 4 — The application installs Qt's own catalogues, and the installers ship them

**We will have `LanguageManager` (`pixelart_creator/ui/i18n.py`) install a second `QTranslator` that
loads `qtbase_<code>.qm` from `QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)`. It is
swapped together with the application catalogue on every language change. The three
`pyside6-deploy` specs will stop passing `--noinclude-qt-translations`.** If Qt's catalogue cannot be
loaded, the failure is logged and does not change `set_language`'s return value: the application's
own catalogue stays authoritative.

The maintainer chose this option on 2026-09-24, over the alternative of accepting English for that
one macOS entry.

## Alternatives considered

| Part | Alternative | Why it was not chosen |
|---|---|---|
| 1 | `QLabel.setOpenExternalLinks(True)` | Qt opens the browser itself and bypasses any seam, so a test can neither observe which address was handed off nor prove that opening the dialog opens nothing. |
| 1 | One label holding all three anchors | A single accessible name cannot describe three destinations (REQ-AV-UI-009), and the three links could not be separate Tab stops with their own focus. |
| 1 | Flat `QPushButton`s styled to look like links | Assistive technology announces a button, not a link. Underlining a button through QSS `text-decoration` was not verified. |
| 2 | The `accent` role | 2.88:1 against the dark background, below 4.5:1. |
| 2 | Setting the application palette's `Link` role in `apply_theme` | It restyles every rich-text link in the application, including the User Guide viewer, which this feature does not change. |
| 2 | A new `link` role | Its value would duplicate `text` in both themes. Article V §3 defines each colour once, by role. |
| 3 | `from pixelart_creator import __version__` in the UI | Binds at import time, so a value installed at run time is never seen. |
| 3 | `self.tr("PixelArt Creator") + " " + version` in the UI | A string-audit finding (`tr-concatenation`). |
| 3 | A new message `tr("PixelArt Creator %1")` | Retires the existing, already-translated message and churns both catalogues. A translation could also drop `%1`, and the version with it. |
| 3 | Reading the Qt and PySide6 versions in `logic/` | That is a PySide6 import in `logic/`, which the layering gate rejects. |
| 4 | Accept English for the macOS application-menu entry | The maintainer's other option. The entry would stay English in Spanish sessions, and REQ-AV-UI-012 would have to be amended to say so. |
| 4 | Change `ui/i18n.py` only | The installers exclude Qt's catalogues, so the change would work from source and do nothing in any shipped build. |
| 4 | Supply the application's own translation under context `QMenuBar`, source `About %1` | Qt's Cocoa plugin checks that context first, but the hook appears only in Qt's source, not in its documented API, so it may change without notice. |

## Consequences

**Accepted costs.**

- Part 4 makes every installer larger by the size of Qt's catalogues. The increase is measured per
  operating system on the pull request that removes the flag.
- Part 4 has a side effect: Qt's standard dialog texts (for example `QDialogButtonBox` and
  `QMessageBox` buttons, and `QFileDialog`) now also follow the interface language. They were
  English in Spanish sessions before this change. A test that asserted the English standard text
  in a Spanish session would now fail. That is a correction of such a test, not a regression.
- Part 4 relies on `QLibraryInfo`'s translations path still resolving inside a frozen, standalone
  bundle. This is **not verified by this record**. The pull request that ships the catalogues
  proves it per operating system with a build, and a missing file only logs a warning.
- Live retranslation of the macOS application-menu entry after an in-session language switch is
  **not verified**. Qt generates that text, and the documentation does not say whether it is
  regenerated on `LanguageChange`. It remains a manual check on a real macOS display, because the
  headless macOS CI has no native menu bar.
- Part 2 means a link looks the same colour as body text. The underline alone marks it. This is a
  deliberate trade for contrast, and it is WCAG-conformant (1.4.1 needs a non-colour cue, which the
  underline is).
- Part 2's inline style was rendered and measured on Windows only. Linux and macOS rendering is
  inferred.

**What this enables.**

- `about_info` needs no Qt, so a later `--version` command-line option can print the version and
  the environment line without importing PySide6. So can the bug-report form's "App version" field.
- Any future external link has a pattern to follow (Part 1) that tests can observe.
- Spanish sessions get Spanish Qt standard texts across the application, which closes a pre-existing
  localisation gap under Article V §2.

**What it constrains.**

- `QDesktopServices` may be called in `ui/about_dialog.py` only from `_open_url`. The three
  addresses live only in `logic/about_info.py`.
- Rich-text links take their colour from `theme.link_colour`, never from a literal or from the
  palette default.
- The version is read only through `about_info.app_version()` in the title and the About dialog,
  never through an import-time binding.
- `tr()` is never combined with `+`, `.format()` or an f-string. A link's rich text is built from an
  already-translated, HTML-escaped caption.
- `LanguageManager` owns two translators. Any future change to language switching must swap both.
- The installer specs must not reintroduce `--noinclude-qt-translations`.

## Compliance

| Part | Detector |
|---|---|
| 1 | `testing/suites/ui/test_about_dialog.py` monkeypatches `_open_url` and asserts the address each link hands off. With socket creation made to raise, opening the dialog never calls `_open_url` and shows no error. The review in the feature's pull request confirms that nothing else in the module calls `QDesktopServices`. **No static gate enforces the single-caller rule**; it is review-enforced, which is an accepted risk. |
| 2 | `testing/suites/ui/test_about_dialog.py` measures the **rendered** contrast of each link in both themes. The threshold and luminance helper are imported from `testing/suites/ui/test_a11y_theme.py`, not restated. A control forces the palette default in dark and must fail. |
| 3 | `testing/suites/logic/test_about_info.py` (including a Hypothesis property over every subset of missing facts) and `testing/suites/ui/test_window_title_version.py`, which installs a different version at run time and expects to see it. `scripts/string_audit_check.py` flags any `tr()` concatenation. `scripts/check_layering.py` rejects a PySide6 import in `logic/`. |
| 4 | `testing/suites/ui/test_i18n_qt_base.py`: after `set_language("es")`, `translate("MAC_APPLICATION_MENU", "About %1")` and a standard Cancel button resolve to Spanish, and both revert for `en`. A missing Qt catalogue logs and leaves `set_language`'s return value unchanged. The shipped-bundle half is proven per operating system by an installer build. The macOS menu text itself is a manual check (see Accepted costs). |

## References

- Qt, *QAction Class*, `MenuRole` — https://doc.qt.io/qt-6/qaction.html
- Qt, *QMenuBar Class*, "Qt for macOS" — https://doc.qt.io/qt-6/qmenubar.html
- Qt source, `qcocoamenuitem.mm` (`qt_mac_applicationmenu_string`) —
  https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/cocoa/qcocoamenuitem.mm
- Qt source, `qcocoahelpers.mm` at `v6.8.0` (application name from `CFBundleName`) —
  https://github.com/qt/qtbase/blob/v6.8.0/src/plugins/platforms/cocoa/qcocoahelpers.mm
- Qt translations, `qtbase_es.ts`, context `MAC_APPLICATION_MENU` (`About %1` → `Acerca de %1`) —
  https://github.com/qt/qttranslations/blob/dev/translations/qtbase_es.ts
- W3C, WCAG 2.2, Success Criteria 1.4.1 (Use of Color) and 1.4.3 (Contrast, Minimum)
