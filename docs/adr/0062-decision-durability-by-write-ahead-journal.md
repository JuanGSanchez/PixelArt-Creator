# ADR-0062 — A per-project decision is made durable by a write-ahead journal, not by writing the project file

| Field | Value |
| --- | --- |
| Status | **Proposed** (the mechanism this record describes has not been implemented yet) |
| Date | Decided 2026-08-22 (`phase-11-asset-ingress` plan §3.15 — ruling P11-R13, mid-execution, the user's `REQ-P11-DATA-010` durability ruling); recorded 2026-08-22 |
| Author | Architecture |
| Feature | `phase-11-asset-ingress` (job `20260821-reachability-remediation`) — `REQ-P11-DATA-010`, `SC-P11-DATA-010-1` through `-5` |
| Grounded by | `spec.md` §0.4 and `REQ-P11-DATA-010`'s amendment ("Neither is the DURABILITY mechanism, and that omission is deliberate"); the user's 2026-08-22 behaviour ruling and the `CL-P11-8` never-saved-project ruling, both quoted verbatim below; ADR-0056 (the registry this decision consumes, not revises); ADR-0004 (the app-level-file, temp-and-replace contract this decision follows) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0056 (per-project confirmation preferences in one registry — the `"prefs"` key this decision leaves exactly where that ADR put it), ADR-0059 §2 (ruling P11-R1 — the atomic-write posture this decision restates and, in one place, tightens beyond), ADR-0004 (the shipped `data/favourites_io.py` temp-file / `os.replace` contract this journal follows) |

## Context

`REQ-P11-DATA-010` asks the asset-library-edit prompt to remember the user's answer. The
requirement's own amendment states plainly that the durability mechanism was left open on
purpose: *"Neither is the DURABILITY mechanism, and that omission is deliberate."* This record
is the architecture answer that closes it, routed to architecture by `spec.md` §0.4.

**The two user rulings this must satisfy, quoted rather than paraphrased** (both 2026-08-22):

- **Ruling 1 — behaviour:** *"user's decision in the window, whether is tick or not, is
  automatically saved in the preferences."* Both branches — ticked and unticked — are decisions,
  and both are in force the next time the project is opened, independent of whether the project
  is saved afterward.
- **Ruling 2 — `CL-P11-8`, the never-saved project, asked and answered explicitly:** the decision
  is held for as long as the project it belongs to is held, and becomes durable the moment that
  project first acquires a file. A discarded never-saved project takes the decision with it —
  nothing observable is lost and nothing asks twice — but the decision must not be dropped in the
  meantime: the first save contains it. The user chose this **over** the alternative of surviving
  a discarded project, explicitly to avoid forcing the key out of per-project storage.

Ruling 2 bounds the answer to Ruling 1. The branch the user declined — moving the key to
application-level storage — is **not taken**, and is recorded below as rejected by the user, not
by this agent (alternative (a)). If satisfying Ruling 1 had required leaving per-project storage,
that would have been a conflict to escalate rather than a branch to take quietly. It did not: the
mechanism below leaves the key exactly where ADR-0056 put it.

**Four constraints bound the design, none of them this decision's to move.**

1. The preference registry is per-project, under the project file's `"prefs"` root key
   (`data/project_io.py`).
2. Preferences deliberately do not dirty the document (`REQ-P5-DATA-004`, ADR-0056) —
   intentional, and stated at the point of assignment.
3. Writing the project file is therefore not an admissible reading of "saved immediately": it
   would also write the user's unsaved canvas work, a worse surprise than the bug being fixed.
4. The unticked decision is per-EDIT, not per-project. `PrefKey` is an enumerated string domain
   and cannot represent a set of decided edits, so the unticked case needs somewhere that is not
   a `PrefKey`.

**The defect this decision closes is two defects and one absence, measured in the committed
branch.** The ticked path reaches disk only through an explicit project save. The unticked path
never reaches disk at all — the session-memory bucket that records it is explicitly documented as
never persisted, and is discarded on tab close. There is nothing to prompt with: a preference
assignment pushes no undo command, so the document's dirtiness never reflects an unticked
decision and the close guard never fires. This is why the remedy cannot be "make the preference
dirty the document" — see alternative (c) below.

## Decision

### 1. The project file stays the home of the value; durability is bought by a journal beside it

Both decisions continue to live in `.pixproj`. `"prefs"` remains exactly where ADR-0056 put it;
a new per-edit ledger joins it in the same file under a new optional root key,
`"asset_edit_decisions"`. The journal this decision adds is **not** a second home for the value —
it is a durability buffer, keyed one record per project, retired the moment the project file
catches up.

- **Ticked → the shipped registry, unchanged.** The three-state `ASSET_LIBRARY_EDIT` value is
  written through `logic/project_prefs.with_value` onto `document.prefs` exactly as today, and
  serialised under `"prefs"` exactly as today. Not one line of that path changes.
- **Unticked → a new per-project value**, because constraint 4 forbids a `PrefKey`. A new module,
  `logic/asset_edit_decisions.py`, declares an immutable `AssetEditDecisions` — a mapping
  `asset_id -> (edit_token, outcome)` — persisted under `"asset_edit_decisions"`. One entry per
  `asset_id`, holding the token it was decided at: a new token supersedes the old row, so the
  ledger is bounded by the reference set and a *different* edit of the same asset asks again.
  The cost of that bound: an asset reverted in the library to a token the user had already
  decided about asks again, because the superseded row is gone. Asking again is the safe
  direction.
- The outcome domain (`OUTCOME_PICK_UP` / `OUTCOME_KEEP`) moves to `logic/asset_edit_decisions.py`
  with byte-identical values; the existing `ui/` names become aliases, so no call site moves.

### 2. The mechanism — a write-ahead journal, app-level, keyed by absolute project path

`data/asset_decision_journal.py` is an app-level file holding per-project records, written by
`data/`, located by `ui/`. It receives a `Path` and never resolves one itself, and imports no Qt
— the same contract the shipped `data/favourites_io.py` already follows (ADR-0004). `ui/`
resolves the journal's location from `QStandardPaths.AppConfigLocation`, beside the favourites
store it already resolves there.

One record per **absolute project path**:

```json
{"prefs": {"asset_library_edit": "..."}, "edits": {"<asset_id>": {"token": "...", "outcome": "..."}}}
```

- **Written inside the same `decide()` call.** `Asset_Update_Prompt_Dialog.decide` gains one
  optional parameter, `on_decided`, invoked exactly once, synchronously, after the outcome has
  been recorded in memory (in `prefs` for a tick, in the session bucket otherwise) and **before**
  `decide()` returns to its caller. In a project with five edited references, the first decision
  is durable before the second dialog is shown. It is not invoked for a dismissal, and not
  invoked when a remembered "always" value short-circuits the dialog, because no decision was
  made. `None` preserves today's behaviour byte-for-byte.
- **Every write of the decision goes through the journal** — the prompt's write-through and the
  confirmations submenu's existing preference-change callback both land in the same window-side
  function. There is no second route, which is what makes precedence at load decidable.
- **Merged over the file at load, journal wins per key.** `data/project_io.load_project_bundle`
  loads the project's `Document`, `ReferenceSet` and `AssetEditDecisions`; the window then reads
  the journal record for that absolute path and merges it over the loaded pair before priming the
  prompt's session memory. A journal record can only be non-empty if a decision was made after
  the last save, so it is never staler than the file — sound only because every write goes
  through the journal (previous bullet); if a future write path skips the journal, this rule
  breaks and must be revisited before that path lands.
- **Retired on successful save.** Saving the project writes the decision into the file and then
  drops that path's journal record. This drop is not the removal capability ruling P11-R1
  refused: that refusal concerned widening a published port ABC shared by three implementers over
  a content-addressed, deduplicating store with no reference count. This journal is
  single-owner, single-writer, not content-addressed, and shared with nothing.
- **A malformed journal file is treated as absent, not as an error** — the user is asked again
  rather than blocked from opening a project. This is a named loss: a journal that cannot be
  parsed is a journal that cannot be honoured, and Article VII's "never crash" governs the
  choice.

### 3. The never-saved project — Ruling 2, implemented rather than restated

A never-saved tab has no file, so it has no journal key, and no record is written for it. The
decision lives on the tab instead: the open-document record gains a `decided_edits` field beside
the reference set it already holds, and the ticked value lives where it already lives, on
`document.prefs`. What carries it into the first save is the save path that already forwards the
reference set to `save_project`; it now forwards `decided_edits` the same way, and `prefs` is
serialised as it always has been. "The first save contains it" is therefore true by construction,
not by a step someone must remember.

The durable project identity used to key the journal (the file path) is deliberately **not** the
tab's session identity (its `project_key`, a `uuid4().hex` for an unsaved tab): the two have
different jobs, and conflating them would re-key a project's shared-state bucket mid-session. A
first save sets the file identity and leaves the session identity alone.

### 4. Atomicity, stated in ruling P11-R1's shape — and stricter in one place

> **Guaranteed absolutely — nothing is ever remembered that the user did not choose.** A
> dismissal writes nothing; a short-circuited "always" value rewrites nothing; an unticked answer
> never becomes a standing rule.
> **Guaranteed absolutely — a journal write, once completed, survives process death.** The whole
> journal is re-serialised to a temp file, flushed, `fsync`ed and moved into place with
> `os.replace` — the same Windows-safe pattern already shipped elsewhere in this codebase. A
> reader sees the whole previous journal or the whole new one, never a truncation.
> **Not guaranteed, deliberately — survival of a kill *during* that write.** If the process dies
> between the user's click and the completion of the journal write, the decision is lost and the
> user is asked again at the next open. That is the safe failure, and it is the pre-decision
> behaviour: the converse — recording an outcome the user never chose — is never permitted.
> **Not guaranteed, deliberately — that the journal contains no superseded record.** Nothing
> scans it and nothing garbage-collects it. A record whose retire-write failed is tolerated: it
> is bounded to one per project path, and merging it is idempotent, because it holds the value
> the project file already holds.

This is the same posture as ruling P11-R1 (ADR-0059 §2) and the same trade: guarantee one
direction absolutely, tolerate an invisible, bounded, self-reclaiming residue in the other, rather
than buy the converse with machinery that is hard to withdraw.

**One place this decision is stricter than P11-R1, and it is deliberate.** P11-R1 tolerates a
bare `Path.write_text` for the catalog index, because that is a pre-existing property of a shipped
module written during an explicit user save. The journal is a **new** file, written on a mere
**click** rather than an explicit save, so its write frequency is far higher and the same
tolerance would be a different bet. It therefore gets temp-file-plus-`os.replace`, not a bare
write.

**An honesty bound, stated plainly rather than left as a caveat.** This record does not claim the
decision is crash-proof, and a record that did would be false. A kill between the user's click
and the completion of the journal write loses the decision, and the user is asked again. That is
the deliberately-chosen safe failure; recording an outcome the user did not choose is the one
thing this design never permits, in either direction.

### 5. The extension point, and the one deliberately not built

The journal's `"prefs"` section admits exactly one key, `ASSET_LIBRARY_EDIT` — a value under any
other key is ignored on read and never written. The other three per-confirmation preferences
(`spec.md` §8) keep today's durable-only-on-save behaviour, because the user ruled on this one
prompt and extending the other three would be unrequested behaviour change. The named extension
point is the admitted-key list itself: the concrete future load it is sized for is the
project-settings dialog that will render the same registry (a later phase's requirement) — when
that dialog lands, one entry added to that list is what extends the guarantee, not a new
mechanism.

**No generic "prompt decision ledger" is built.** Nothing concrete needs one today; building it
now would be speculative generality. What would warrant one is a *second* prompt needing
per-subject memory — there is none today.

## What this decision does NOT make true

**An ADR claiming this makes the decision crash-proof would be false, and this record does not
make that claim.** As stated in §4, a kill between the user's click and the completion of the
journal write loses the decision, and the user is asked again at the next open. That is the
deliberately-chosen safe failure. This record also does not claim: that the ticked and unticked
paths are unified into one representation (they remain two distinct mechanisms sharing one
journal file, by constraint 4); that `FORMAT_VERSION` records durability retroactively for
projects saved by an earlier build (a v6 file written by this build and re-saved by a build
without this key silently loses the ledger — the same bet `"prefs"` already takes); or that two
tabs open on the same project file are arbitrated (untested, stated rather than verified below).

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| (a) Move the preference to application-level storage (`QSettings` or a per-app JSON store) | **Rejected by the user, not by this agent** (`CL-P11-8`, answered 2026-08-22). It would have made the never-saved case trivial; the user weighed that against forcing the key out of per-project storage and chose per-project. Recording who rejected it matters: a later pass must not read this as an architecture preference it may overturn on architecture grounds |
| (b) Write the project file at the moment of the click | Rejected on the spec's own constraint: it would write the user's unsaved canvas work, and the acceptance clause requiring the project to still report no unsaved changes would fail |
| (c) Make the preference dirty the document, so the close guard prompts | Rejected — it contradicts `REQ-P5-DATA-004` and ADR-0056 head-on, it would make an untouched canvas offer to be saved, and it fixes the ticked path only, because the unticked session bucket is not document state at all and a save would not write it |
| (d) Autosave / the snapshot store | Rejected. Both persist document content by design — the snapshot store is built on the project serialiser, so routing a preference through it writes the canvas, which is (b) with more steps. It is also recovery-scoped: a recovery artifact is consumed and discarded, and a decision must not be |
| (e) Put the unticked decision on the asset reference itself as a fifth field | Rejected on coupling, the closest call. The reference set is specified as the resolution key plus display labels, and a decision is neither; putting interaction history there puts it in front of the pure, content-only reference predicates, and a future "edited but decided" state would find the field already sitting there. Keeping the ledger separate keeps the predicate content-only and keeps the persisted shape a one-for-one mirror of the session bucket it makes durable |
| (f) A generic per-project "prompt decisions" ledger keyed by (prompt, subject, token) | Rejected as speculative generality. The other three per-confirmation preferences are two-state and fully served by the registry; no second prompt needs per-subject memory today |
| (g) Keep the session-memory bucket as the only unticked store and persist it wholesale at close | Rejected: it re-introduces exactly the defect being fixed — a decision that survives only if a later event happens — and the close path is not reached by a crash, a kill, or a power loss |

## Consequences

**Accepted costs.** The project now has two places that can hold the same decision transiently —
the file and the journal — and a reader wanting the full durability story must read both this
record and ADR-0056. The journal introduces a new app-level file the user never sees, keyed by
absolute path, which will not follow a project file that is moved or renamed outside the
application (the journal record for the old path becomes stale and unreachable; the new path
starts with no record, which is the same "asked again" safe failure already accepted elsewhere in
this decision). `data/asset_decision_journal.py` is a new write path that every future preference
extension must route through if it wants this decision's durability guarantee.

**What this enables.** `REQ-P11-DATA-010`'s durability half is now answered without touching
ADR-0056's registry shape, without writing unsaved canvas work, and without a boolean-only
mechanism that could not represent the per-edit unticked case. The one-key admission list gives a
concrete, low-cost path to extend the guarantee to the project-settings dialog when that phase
lands, without building a mechanism nothing concrete needs yet.

**What it constrains.** No future write path may assign to `document.prefs`'s
`ASSET_LIBRARY_EDIT` key or to the per-edit ledger without also routing through the journal —
doing so would break the "journal never staler than the file" precedence rule this decision
depends on. No future change may treat the journal drop-on-save as the removal capability ruling
P11-R1 refused; it is a different thing for the reasons stated in §2. `logic/asset_edit_decisions.py`
must stay a leaf — importing nothing from `pixelart_creator` — so that `data/`'s two new edges
into it and `ui/`'s two new edges into it cannot close a cycle.

## What has no detector, stated rather than implied

No script proves that a future write path bypasses the journal and writes `document.prefs`'s
`ASSET_LIBRARY_EDIT` key or the per-edit ledger directly, or that the retire-on-save step is
skipped. Those are review invariants against this decision's mechanism, not a gate that runs.

## What this record does not verify

- **This decision is not yet implemented.** Tasks owned elsewhere in the feature plan
  write `logic/asset_edit_decisions.py`, `data/asset_decision_journal.py`, the
  `data/project_io.py` extensions, and the `ui/` wiring this record describes. This ADR is
  authored first, deliberately, because CI's documentation-reference gate requires every
  `ADR-NNNN` citation in product source to resolve to a file under `docs/adr/` before that source
  can cite it.
- **Two open tabs on one project file** — the journal is keyed by absolute path, so two tabs of
  the same file would share one record while holding two distinct session identities. Whether the
  window prevents opening the same file twice was not read for this record, and no task changes
  it. If it is possible, the last decision written wins; no corruption results, but a tab's
  in-memory ledger may be older than the record.
- **A project file edited outside the application** while a journal record for its path exists:
  the journal wins and the decision is re-applied on next open. Accepted; untested.
- **Journal growth over the application's lifetime** is not measured. Retire-on-save makes the
  steady state one record per project carrying an undischarged decision — normally zero — but no
  task here measures it; the per-entry count cap is a defensive input bound, not a growth policy.
- **This record does not itself run `pytest`, `check_layering.py` or `check_cycles.py`** — no
  code exists yet for those gates to measure. The layering delta this decision predicts (two new
  `data/` and `ui/` edges into `logic/asset_edit_decisions`, one new `data/` edge into
  `data/asset_decision_journal`, zero `logic -> data` edges) is recorded in the feature plan
  (`phase-11-asset-ingress` plan.md §3.15 (10)) as a prediction, and its measurement is owed by
  the implementing tasks, not by this ADR.
