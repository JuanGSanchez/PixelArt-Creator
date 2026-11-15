# ADR-0076 — The formatting locale is stored by the language manager and read explicitly, never set as Qt's default; the main window's fields take it once at startup

| Field | Value |
| --- | --- |
| Status | **Proposed** — becomes Accepted when the change that implements it merges |
| Date | 2026-11-15 |
| Author | Architecture |
| Feature | Six more interface languages — numbers formatted for the active language (`REQ-L10N-UI-015`) |
| Grounded by | `REQ-L10N-UI-015` (one formatting locale, taken when the interface language is set at startup or from the selector; the system's own locale where it maps to the active language, else the language's; numeric input fields included; a field that exists at a switch keeps the locale it was created with until it is created again); the Qt documentation of `QLocale::setDefault` (set it at application startup, before any non-GUI thread is created; not reentrant; read for Qt 5 and 6.2 to 6.12); Article I (layering); Article II (numeric parameters in `logic/constants.py`); `scripts/check_layering.py` and `scripts/check_cycles.py` (output quoted below) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0073 (this release's placement record), ADR-0075 (failure messages, the same release) |

## Context

With eight interface languages, a number the interface formats must follow the language as well as the system. That covers a data size, a scale, and a value in a numeric field. `REQ-L10N-UI-015` asks for one **formatting locale**, chosen when the language is set: the system's own locale when that locale maps to the active interface language, and the interface language's otherwise.

The first design installed that locale as Qt's process-wide default with `QLocale.setDefault`. The Qt documentation reverses that choice. It says the default should be set at application startup, before any non-GUI thread is created, and that the call is not reentrant. The application starts worker threads, and the language can change at any time from the selector. The documentation also leaves two things unsaid: whether `setDefault` changes what `QLocale.system()` returns, and whether a widget reads the default only when it is built.

A second force was found by measurement. The main window builds its panels **before** it installs the language. Of the 45 integer fields in the interface, 18 are built when a dialog opens and 27 are built once, with the main window. A field that reads the formatting locale when it is built therefore gets the language manager's initial locale, not the installed language's. The requirement says that a field which already exists at a later switch keeps its locale until it is created again, and that a field built once with the main window keeps it until the application starts again.

## Decision

### D1 — No `QLocale.setDefault` call; the language manager stores the locale and consumers read it explicitly

- `LanguageManager.set_language` computes the formatting locale after the catalogues are installed and **before** it emits `languageChanged`, and stores it (`LanguageManager.formatting_locale() -> QLocale`).
  - The choice of locale is a pure rule in `logic/locale_match.py`, `formatting_locale_name(system_name, ui_language, available) -> str`, with zero Qt.
  - The system locale is read through one injectable reader, `_read_system_locale()` in `ui/i18n.py`. It is read and never written.
- One module function, `current_formatting_locale() -> QLocale` in `ui/i18n.py`, returns the application manager's locale. With no manager it returns `QLocale()`, Qt's untouched default.
- **Each consumer reads it explicitly:**
  - a data size is formatted with it and then passed through `logic/number_format.with_unit_space`;
  - a scale is formatted as `LocaleDecimal` with its decimal point;
  - every numeric field calls `setLocale(i18n.current_formatting_locale())` right after it is constructed. That is 9 `QDoubleSpinBox` and 37 `QSpinBox` constructions in `ui/`; the two helpers that build several fields, `_make_spin` and `_make_dim_spin`, do it inside the helper.

### D2 — One startup pass for the fields the main window built before the language was installed

`Main_Window.__init__` calls one private method, `_apply_formatting_locale_to_spin_boxes()`, **directly and once, immediately after** `self._language_manager.install_from_locale()`. The method reads the formatting locale once and sets it on every `QSpinBox` and `QDoubleSpinBox` among the window's children. It is **not** connected to `languageChanged`, so a live switch leaves the window-built fields as they were built, as the requirement states.

**The order of handlers, measured (2026-11-15).** `languageChanged` occurs only in `ui/i18n.py`: no slot is connected to it anywhere in the package. While the language is installed, Qt's `LanguageChange` event runs the already-built widgets' own retranslation handlers, inside the install call and before the pass. In `ui/`, `setLocale` occurs only on the field-construction lines, so none of those handlers sets or resets a field's locale. The pass is therefore the last thing that sets the window-built fields' locale at startup.

### D3 — Placement

- The startup pass is a private method of `Main_Window` in `ui/main_window.py`, with no new module.
- `ui/main_window.py` imports `pixelart_creator.ui.i18n` in module form. Its earlier `from … import LanguageManager` alone did not give it `current_formatting_locale`.
- Every file that gained a field line imports `ui.i18n` in module form. A planted `ui.i18n → ui.transform_dialog` import gave cycles exit 1 on a scratch copy, and `ui/i18n.py` imports no dialog.

**On the branch as built (2026-11-15):**
- `python scripts/check_layering.py --root pixelart_creator --json` exit 0, `{"scanned": 247, "violations": [], "unregistered": [], "root_modules": ["__init__.py", "__main__.py"], "exempt": {}}`;
- `python scripts/check_cycles.py --root pixelart_creator --json` exit 0, `{"modules": 249, "edges": 958, "cycles": []}`.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| `QLocale.setDefault` with the formatting locale at every language change | Against the documented thread guidance once worker threads exist. Its effect on `QLocale.system()` and on widgets already built is undocumented, and it would couple text shaping to the number locale |
| Install the language before the main window builds its panels | It reorders about 640 lines of the window's construction for a one-line need, and every handler that runs at install would then meet a half-built window. Measured afterwards, no slot is connected to `languageChanged` today; the reordering is still unbounded |
| Refresh every field's locale on `languageChanged`, at install and at every switch | It makes the requirement's sentence false: a field that exists at a switch must keep the locale it was created with |
| A helper in `ui/i18n.py` that walks a window's fields | It would buy room only for a second window that builds fields before it installs a language, and none is named. A private method of the one window that does is enough |
| Rely on the per-construction lines alone | The 27 window-built fields stay on the manager's initial locale. The integer-field test showed that this state fails |

## Consequences

**Accepted costs.**
- A numeric field whose construction forgets `setLocale` shows the system's format. A static guard in the tests catches that.
- The fields built with the main window do not follow a live language switch until the application starts again. That is what the requirement states, not a defect. If a future requirement asks them to follow, the startup pass becomes a `languageChanged` handler, in this one method.

**What this enables.**
- Qt's default locale and `QLocale.system()` are never written, so what the system reports stays true by construction.
- No locale call runs against the documented thread guidance.

**What it constrains.**
- Every new `QSpinBox` or `QDoubleSpinBox` in `ui/` is followed by `setLocale(i18n.current_formatting_locale())` in the same function.
- No module calls `QLocale.setDefault`.
- The startup pass stays immediately after `install_from_locale()`.

## Compliance

- `testing/suites/ui/test_formatting_locale.py` covers three things:
  - it walks every numeric field in both themes, with French active on an `es_ES` system: the dialogs' fields and the main window's;
  - it carries an AST guard that every `QSpinBox(` and `QDoubleSpinBox(` construction in `ui/` is followed by the `setLocale` line on the same object, with a planted control;
  - it checks that the real system locale is never changed, and that no module sets an application-wide default locale, the latter with a planted call that the scan must find.

  The implementing change's report gives its counts on 2026-11-15: 76 passed; it printed 30 decimal and 45 integer fields examined, 27 of them in the main window's panels, and 37 `QSpinBox` and 9 `QDoubleSpinBox` constructions.
- `testing/suites/ui/test_language_switch_cycle.py` and `testing/suites/ui/test_set_once_texts_retranslate.py` — a live switch still behaves as before.
- `QLocale.setDefault` is called nowhere in `pixelart_creator/` (2026-11-15: the only occurrence of the name is a docstring in `ui/i18n.py` stating that it is not called; every other `setDefault` is a push button's).
- `scripts/check_layering.py` and `scripts/check_cycles.py` — the placement above.
- **No detector:** that the startup pass stays *after* the install call is held by the integer-field test, which fails if the pass runs too early, not by a structural check.
