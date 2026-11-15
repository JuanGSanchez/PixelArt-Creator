# ADR-0075 — Failure messages name the kind of failure, never the exception's text, and stand on a line of their own after a lead-in

| Field | Value |
| --- | --- |
| Status | **Proposed** — becomes Accepted when the change that implements it merges |
| Date | 2026-11-15 |
| Author | Architecture |
| Feature | Six more interface languages — failure messages (`REQ-L10N-UI-018`) and the junction between a lead-in and its failure sentence (`REQ-L10N-UI-020`) |
| Grounded by | `REQ-L10N-UI-018` (no message the interface shows carries an exception's text; the failure sentences are translated); `REQ-L10N-UI-020` (the failure sentence never continues on its lead-in's line, with one outcome in all eight languages; the lead-in keeps what it says; a surface that cannot hold two lines is raised, not exempted); `REQ-L10N-UI-017` (the "no real-time transport configured" reason keeps its frame); the project owner's ruling for the status bar, recorded with `REQ-L10N-UI-020`; Article I (layering); `scripts/check_layering.py` and `scripts/check_cycles.py` (output quoted below); `scripts/check_exception_text.py` |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0073 (this release's placement record), ADR-0076 (the formatting locale, the same release) |

## Context

Before this change, an interface failure was shown by putting the exception's own text into a message: a message box body, a template's placeholder, a worker's signal, or a field stored for later display. That text is English, or whatever the operating system or a library produced, in every language the interface speaks, and it can carry paths and internal names. `REQ-L10N-UI-018` forbids it: a failure is shown as a translated sentence that says only what the failure's class establishes, and the exception may still be written to a log.

A second force arrived with the translations. Many failures are shown inside a frame that names the operation first, a **lead-in** (`Could not import the asset: %1`), with the sentence in place of the placeholder. In seventeen such templates the sentence followed the lead-in on the same line in thirteen and on its own line in four. `REQ-L10N-UI-020` asks for one outcome in all eight languages: the sentence never continues on the lead-in's line. A measurement of the eight catalogues found every one of the seventeen templates in all eight, with the placeholder last in every translation, so the junction was the only thing that had to change.

One of the thirteen is not a box or a label but the main window's **status bar**, which shows a temporary message on one line. A line break is not available there, and its lead-in, `Real-time`, is a label rather than a sentence. The same frame also carries a reason that is not a failure sentence (`REQ-L10N-UI-017`), which must keep its form.

## Decision

### D1 — One module owns the failure sentences: `pixelart_creator/ui/failure_messages.py`

- `FailureKind` (an `enum.Enum`) has six kinds, and each kind has one English source sentence, translated in context `Failure_Messages`:

  | Order | First matching class | Kind | English source sentence |
  | --- | --- | --- | --- |
  | 1 | `TimeoutError` | `TIMEOUT` | The operation timed out. |
  | 2 | `ConnectionError` | `CONNECTION` | The connection failed. |
  | 3 | `FileNotFoundError` | `NOT_FOUND` | The file or folder could not be found. |
  | 4 | `PermissionError` | `PERMISSION` | Access to the file or folder was denied. |
  | 5 | `ValueError` and its subclasses | `INVALID_VALUE` | A value was not valid for this operation. |
  | 6 | anything else, any other `OSError` included | `GENERIC` | The operation could not be completed. |

- `failure_kind(exc)` walks the exception, each `__cause__` and a `URLError`'s reason, outermost first, with a private bound on the chain's length. The first timeout, connection, not-found or permission class decides. Otherwise another `OSError` or an `ImportError` gives the generic kind, a `ValueError` gives the invalid-value kind, and anything else gives the generic kind. Each sentence names only what its class establishes.
- `failure_text(kind)` returns the translated sentence. `log_failure(exc)` and `logged_failure_kind(exc)` write the detail the interface never shows to the log.
- **How each channel uses it.** A message box keeps its title, and its body is the sentence. A translated template keeps its text, and its placeholder takes the sentence. A worker emits the kind's value, never text, and the GUI thread translates it when it shows the message, so it follows a live language switch and no translation runs on a worker thread. A failure stored for later display stores the kind, and the text is made when it is shown.

### D2 — The sentence stands on its own line by composition in the interface, not by changed source strings

`failure_on_own_line(template, placeholder, sentence)`, in the same module, splits the **translated** template at the placeholder, drops the whitespace at the end of the head, and returns the head, a line break and the sentence. Any text a translation puts after the placeholder goes on a further line of its own. A head that already ends in a line break is kept as it is, and a template without the placeholder is returned unchanged.

The twelve multi-line surfaces that showed the sentence inline call it in place of a plain replacement:
- five message boxes in `ui/asset_library_actions.py`;
- one label each in `ui/dependency_graph_view.py` and `ui/provider_config_dialog.py`;
- one message box in `ui/script_runner_panel.py`;
- two message boxes in `ui/tilemap_io_actions.py`;
- the assistant dock's transcript in `ui/assistant_dock.py`;
- a list row in `ui/batch_export_panel.py`.

The four templates that already put the sentence on its own line are not edited. **No source message changed and none was added** for this part.

### D3 — The status bar: a second frame, used only for a failure sentence

On the main window's status bar, a failure sentence is shown in its own frame, English source `Real-time. {msg}` (context `Main_Window`). The frame keeps the lead-in's text and closes it with a sentence-ending mark. `Real-time: {msg}` is unchanged and keeps carrying the "no real-time transport configured" reason. This is the option the project owner chose for this surface, and it applies **to this surface only**: no other lead-in is cured by closing a label with a sentence-ending mark unless the same question has first been raised for that surface.

**The frame is chosen by the message's kind, never by comparing the shown text** with a translation. The real-time client (`ui/realtime_worker.py`) and session (`ui/realtime_actions.py`) declare `errorOccurred = Signal(str, bool)`, carrying `(message, is_failure)`. Every failure emit passes `True`; the session's four failure sites go through one private `_report_failure(exc)`. The reason passes `False`. `Main_Window._on_realtime_error(message, is_failure=False)` picks the frame from the flag. The session's relay slot gives the flag a default, so a test double that still declares `Signal(str)` keeps working. The signal keeps its name, because the lead-in test finds the status bar through a receiver of one of the named failure signals.

### D4 — Placement

`ui/failure_messages.py` imports only the standard library and `PySide6.QtCore`. Its consumers import it in **module form** (`import pixelart_creator.ui.failure_messages`): with the package form (`from pixelart_creator.ui import …`), a planted cycle through it was **not** reported by `check_cycles`, because the edge lands on the package. It has no `logic/` twin: it has one consumer layer, `ui/`, and no consumer outside Qt is named, so a `logic/` home would be generality bought for nothing.

**Placement, proven before the module was built** (a scratch copy of the package with a stub module and its planned imports):
- layering exit 0 (245 modules scanned, 0 violations, 0 unregistered);
- cycles exit 0 (247 modules, 904 edges).

Controls on that copy:
- a `logic → ui` import gave layering exit 1;
- a `PySide6.QtCore` import in `logic/` gave layering exit 1;
- an import of `ui.main_window` planted in the stub gave cycles exit 1 (one cycle of 12 modules).

**On the branch as built (2026-11-15):**
- `python scripts/check_layering.py --root pixelart_creator --json` exit 0, `{"scanned": 247, "violations": [], "unregistered": [], "root_modules": ["__init__.py", "__main__.py"], "exempt": {}}`;
- `python scripts/check_cycles.py --root pixelart_creator --json` exit 0, `{"modules": 249, "edges": 958, "cycles": []}`.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| Keep the exception's text and sanitise it (strip paths, shorten) | It stays untranslated in every language, and no sanitiser can establish that what is left is true for the user. `REQ-L10N-UI-018` forbids the text, not only its worst parts |
| The classifier as a pure module in `logic/` | A few lines with one consumer layer. No consumer outside Qt is named, so it would add a module and edges with nothing to absorb |
| Cure the junction in the source strings (a line break written into each of the thirteen inline templates) | Thirteen source messages change, and so do 13 × 7 = 91 translations, including an accepted batch. Each translation would remain free to put the sentence back on the lead-in's line, so the outcome would hold by review in each language rather than by code in all of them |
| Status bar: show the failure sentence alone | The reader loses which feature failed, and dropping the lead-in would be an exemption the requirement does not grant |
| Status bar: send real-time failures to a surface that holds two lines (a message box or the real-time panel) | A modal box for a background error that can repeat on every reconnect |
| Status bar: a sentence-shaped lead-in with a word added (English `Real-time error. {msg}`) | It reads best, but it changes what the lead-in says, which needed the requirement relaxed for this surface; the owner chose the frame that keeps the lead-in's text |
| Choose the status-bar frame by comparing the shown text with a translation | It breaks in seven languages, and it cannot tell a failure sentence from the reason once both are translated |
| A second signal with a new name for failures | The lead-in test's inventory finds the status bar only through a receiver of a named failure signal; with a new name the surface claimed no site and four inventory cases failed (tried, then replaced) |

## Consequences

**Accepted costs.**
- The user sees what kind of failure happened, not its detail; the detail is in the log only.
- A message composed from a lead-in and a sentence is no longer one catalogue entry. The requirement that a shown message equals the catalogue's finished translation is checked **of each part**: the lead-in as its catalogue form up to the placeholder, the sentence as its own.
- One more source message (`Real-time. {msg}`), translated in each language like any other.
- `errorOccurred` changed its signature on two classes. Any new receiver must accept `(message, is_failure)`, or rely on the slot default that the relay keeps.
- The exception-text check follows taint within a module only. A helper in another module that formats the exception is not followed; the runtime tests are the backstop.

**What this enables.**
- A new failure site needs no new string: it calls `failure_kind` and `failure_text`, and `failure_on_own_line` when it shows a lead-in.
- The junction holds in every language by code. A translator cannot rejoin the sentence to the lead-in.

**What it constrains.**
- Every failure site in `ui/` shows a `FailureKind`'s sentence, never exception text.
- Every lead-in that carries a failure sentence on a surface that holds two lines composes through `failure_on_own_line`.
- The status bar's failure-only frame is the single surface where a closing mark cures the junction.
- `ui/failure_messages.py` stays standard library + `QtCore`, imported in module form.

## Compliance

- `python scripts/check_exception_text.py` — a static scan of `pixelart_creator/ui/`. It exits 1 on any handler that puts the exception's name, its `str`/`repr`, its arguments or its type name into a message box, a translated template, a worker signal or a field stored for display. On the branch (2026-11-15): exit 0; 117 files examined, 74 sites in 72 handlers, 0 tainted.
- `testing/suites/ui/test_failure_lead_ins.py` — derives every lead-in surface from the code and fails when a failure sentence continues on a lead-in's line. That includes the status bar, where it checks three things: the failure-only frame, the reason kept in `Real-time: {msg}`, and a planted reason in the failure-only frame, which must fail. It also prints, without asserting, every composition that passes because the text before the sentence ends with a sentence-ending mark, so a second surface cured that way is seen.
- `testing/suites/ui/test_failure_messages_language.py` — the sentences per language; the dependency-cycle frame is asserted per part.
- `testing/suites/ui/test_script_runner.py` — the invalid-JSON box: the lead-in on its own line, then the literal English sentence.
- `scripts/check_layering.py` and `scripts/check_cycles.py` — the module's placement and its module-form imports.
- **No detector:** whether a sentence is *true* of its kind (that each names only what its class establishes) is a review judgment, not a check.
