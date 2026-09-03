# ADR-0056 — Per-project confirmation preferences live in one registry with enumerated domains

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-17 (`phase-5-timeline-grid` plan §2, §3.3, §7); **recorded 2026-08-19** |
| Author | Architecture |
| Feature | `phase-5-timeline-grid` (D-04) — settled once on behalf of four claimant slices |
| Grounded by | `REQ-P5-DATA-004`, `REQ-P5-UI-033`; the three other claimants — `phase-2-floating-selection` `REQ-P2-DATA-030` / `REQ-P2-UI-037` (Q-19 ruling, "per-project, settings-changeable"), `phase-6-mode-toggle-undo` `REQ-P6-DATA-031`, `phase-11-asset-ingress` `REQ-P11-DATA-010`; Article I / S11 (layer purity) |
| Owed by | `phase-5-timeline-grid` (owner the documentation) — see "Why this record is late" |
| Relates to | ADR-0025 (`.pixproj` v5 — the schema version this decision deliberately does **not** move), ADR-0057 (the grid whose confirmation is the registry's first consumer), ADR-0004 (per-machine Favourites — the *other* scope, deliberately not this one) |

## Context

Four separate slices, planned in the same batch, each arrived at the same shape of
requirement: *the user should be able to say "don't ask me again" to a confirmation, and be
able to take it back.*

- `phase-5-timeline-grid` `REQ-P5-DATA-004` — the cel-overwrite confirmation;
- `phase-2-floating-selection` `REQ-P2-DATA-030` — the canvas selection-drag warning;
- `phase-6-mode-toggle-undo` `REQ-P6-DATA-031` — the destructive mode-conversion warning;
- `phase-11-asset-ingress` `REQ-P11-DATA-010` — the asset-library edit preference.

The failure mode all four specs name explicitly is the same: four ad-hoc boolean fields
invented in four slices, four spellings in the `.pixproj` file, four places to look for
"where is that setting", and a fifth slice that finds none of them reusable. Phase-11's spec
§8 states the obligation outright — *"architecture must settle the shape once … rather than letting
four specs each invent a key."*

Two constraints make this a real question rather than a naming exercise.

**First, the shapes are not all boolean.** Three of the four preferences are two-valued
(*ask* / *suppressed*); phase-11's is **three-state**. A boolean registry would ship, then
have to be widened by the next slice that landed — a cross-slice change to a mechanism four
slices already depend on.

**Second, this is per *project*, not per machine.** The Q-19 ruling puts the memory in the
document, which means the mechanism must be persisted in `.pixproj` — and touching that
format has a version cost. ADR-0004's Favourites precedent (per-machine, `QStandardPaths`)
is therefore the wrong scope, and cannot be reused however similar it looks.

There was also a surface question with an owner conflict: `REQ-P5-UI-033` requires a
*reachable* restore control **now** ("a control the user can find, showing current state,
and it is not the suppressed dialog"), while `phase-6-mode-toggle-undo` `REQ-P6-UI-039` owns
the eventual project-settings **dialog**. Building a dialog here would be the "one dialog per
slice" outcome three specs forbid.

## Decision

**We will declare every per-project confirmation preference in one Qt-free registry —
`logic/project_prefs.py`, each key carrying an enumerated string value domain and a default,
with `absent -> default` — persist the set as one optional `.pixproj` root object `"prefs"`
without moving `FORMAT_VERSION`, and render the registry as an `&Edit -> Project
confirmations` submenu until phase-6's settings dialog exists.**

Concretely, and in this shape only:

1. **The domain is enumerated, and it is a set of strings — never a raw `bool`.** A
   `PrefKey` is `(name, domain: FrozenSet[str], default: str)`. A two-valued preference is a
   two-member domain (`{"ask", "suppressed"}`); phase-11's three-state preference is a
   three-member one. **The mechanism does not special-case either**, so the three later
   claimants add a *key*, not a mechanism change. The on-disk shape is the same enumerated
   string the domain validates, so there is one representation end to end.

2. **`absent -> default`, everywhere and at every level.** An unset key on a `ProjectPrefs`
   snapshot reads as its declared default; an absent `"prefs"` object reads as all-defaults;
   a v1–v4 project loads unchanged. Absence is never a third value.

3. **`register()` is the seam; this module mints no id it does not own.** A later slice adds
   its key by calling `register(PrefKey(...))` from **its own module** at import time — never
   by editing `logic/project_prefs.py`. A name collision between two slices raises rather than
   silently overwriting. This slice ships exactly one key, `CONFIRM_CEL_OVERWRITE`.

4. **`FORMAT_VERSION` stays 5. No bump.** `data/project_io.deserialize` reads keys by name
   with no unknown-key rejection, so a preference written by a newer build is simply not read
   by an older one, and the cost of that is **one click to set it again**. Bumping would make
   an older build refuse the *whole project* in order to protect a preference — a worse
   outcome than the thing it protects. (Phase-11's reference set reverses this calculus and is
   decided separately.)

5. **The key is omitted when empty.** `serialize` writes `"prefs"` only when a preference has
   actually been set, so a project that never touches one serialises **byte-for-byte as it did
   before the field existed**.

6. **Out-of-domain is refused; unrecognised is ignored.** A *recognised* key holding a value
   outside its declared domain raises `ProjectIOError` — never coerced, because a coerced
   preference is one the user did not set. A key this build does not recognise (a newer
   build's, added through the `register` seam) is **dropped**, matching the format's
   established forward-tolerance.

7. **A preference is not document content.** Setting one pushes no
   `logic/history.Command` / `QUndoCommand` and plays no part in document equality or dirty
   tracking. It is a preference about a dialog, not an edit to the artwork.

8. **The surface now is a submenu, not a dialog.** `ui/project_prefs_actions.py` renders **one
   entry per registered key** into `&Edit -> Project confirmations`: checked reflects
   "suppressed", activating restores the declared default. N preferences produce N entries in
   **one** place. When phase-6's `REQ-P6-UI-039` dialog lands it renders **this same
   registry**, so the entries *move* rather than multiply.

9. **The registry is `logic/`, Qt-free, and does no I/O.** Persistence is `data/project_io.py`'s
   job; rendering is `ui/project_prefs_actions.py`'s. This is deliberately **not** a settings
   framework: no UI schema, no grouping, no migration engine, no per-machine scope.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| **Four ad-hoc fields, one per slice** | The failure mode all four specs name by hand. Four spellings of one concept in one file format, and the fifth claimant reuses none of them. |
| **A boolean-only registry** | Phase-11's preference is three-state, so the registry would have to be widened by a later slice — a cross-slice change to a mechanism four slices already depend on. An enumerated domain absorbs both shapes from the outset, at the cost of one `frozenset` per key. |
| **Bumping `FORMAT_VERSION` for `"prefs"`** | Would make an older build refuse an entire project to protect a preference whose loss costs one click. The protection is worth less than what it destroys. |
| **A settings dialog in this slice** | `phase-6-mode-toggle-undo` `REQ-P6-UI-039` owns that surface. Building a second one here is the "one dialog per slice" outcome three specs forbid — and the eventual dialog would then have two registries to reconcile. |
| **A restore control inside the confirmation dialog itself** | Impossible by definition: once suppressed, the dialog never appears again. `REQ-P5-UI-033` says so directly. |
| **Per-machine storage, as ADR-0004 does for Favourites** | Wrong scope. The Q-19 ruling is explicit that the memory is *per project*; a per-machine store would silence the warning in a project the user never opened. |
| **Storing raw `bool` values** | Forces a second representation (`bool` in memory, string on disk) and cannot express phase-11's third state without a type change at every call site. |
| **Coercing an out-of-domain value to the default** | A silently coerced preference is indistinguishable from one the user set. Refusal is the honest failure. |

## Consequences

**Accepted costs.** Every preference now costs a `PrefKey` declaration with an explicit domain
— more ceremony than a boolean field for the two-valued majority. Because `FORMAT_VERSION`
does not move, an older build silently **drops** a newer build's preference on save-through:
that data loss is chosen, bounded (one click) and stated, not prevented. The registry is a
**mutable module-level dict** so later slices can register at import time, which means the set
of keys depends on which modules have been imported — the submenu renders what is registered
*at build time*, and a slice that registers lazily would not appear. And four slices now share
one mechanism: a change to its *shape* after the second claimant registers is a cross-slice
change, which is precisely why the domain is enumerated from the start.

**What this enables.** Three later slices add a preference with one `register()` call from their
own module and get persistence, validation, forward-tolerance and a restore control for free —
no `.pixproj` change, no menu change, no `FORMAT_VERSION` decision. Phase-6's settings dialog,
when commissioned, renders the same registry and inherits every key registered since.

**What it constrains.**

- `logic/project_prefs.py` stays Qt-free and I/O-free (Article I / S11). It is imported by
  `data/project_io.py`, `logic/document.py` and `ui/project_prefs_actions.py` /
  `ui/timeline_grid_view.py` — never the reverse.
- No slice may add a preference by editing `logic/project_prefs.py`'s `REGISTRY` literal; the
  `register()` seam is the only sanctioned path.
- No slice may add a second per-project preference container, or a per-preference `.pixproj`
  root key.
- `FORMAT_VERSION` is not moved on account of a preference.
- Setting a preference must not push an undo command or set the dirty flag.

## Compliance

The layering half has detectors, and they were **run** — not read — in the `fix-adr-citations`
worktree at `267d64a`:

```
$ python scripts/check_layering.py --json
{ ..., "scanned": 207, "unregistered": [], "violations": [] }
exit 0
$ python scripts/check_cycles.py --json
{ "cycles": [], "edges": 761, "modules": 209 }
exit 0
```

`logic/project_prefs.py` imports nothing but `typing` (verified by reading its import block), so
its Qt-freedom is structural rather than merely asserted; `check_layering` is what keeps it so
as consumers accumulate.

Behavioural coverage: `tests/data/test_project_io_prefs.py` (round trip, absent object, absent
key, out-of-domain refusal, unrecognised-key tolerance) and
`tests/ui/test_project_prefs_actions.py` (one entry per registered key, checked state, restore).

**What has no detector, stated rather than implied.** No script can tell that a fifth slice
introduced a *second* preference container, that a preference was persisted under its own root
key, or that setting one pushed an undo command. Those are review invariants. The
`register()`-seam rule is likewise unenforced — a slice editing the `REGISTRY` literal directly
would pass every gate. Accepted risk, recorded here so it is not mistaken for coverage.

## What this record does not verify

- **Only one key is registered today.** `CONFIRM_CEL_OVERWRITE` is the entire registry at
  `267d64a`; no `register()` call exists anywhere in `pixelart_creator/`. The three-state shape
  is therefore *designed for* and unit-exercised, but **no shipped consumer has used it** — the
  claim that a three-state key needs no mechanism change is an argument from the code's shape,
  not an observation of it.
- **The eight citation sites were read; the eight modules were not read in full.**
  `ui/main_window.py` (3,600+ lines) was read only around its submenu wiring.
- **No suite was run for this record.** The named test modules were read for their subject
  matter, not executed here; `tests/scripts/test_check_doc_references.py` is the only suite this
  ADR's own change ran.

## Why this record is late

The decision was made on 2026-08-17 and its ADR was assigned as a task in `phase-5-timeline-grid`
(owner the documentation), which was never executed while the code that cites it shipped. Eight files
across `logic/`, `data/`, `ui/` and `tests/` cite `ADR-0056`, and three *other* slices' plans
name it as the decision they consume. The number is fixed by those citations, not chosen here:
writing at `0056` rather than at `highest + 1` is the deliberate exception to the adr-author
numbering rule, because renumbering would break the trail this record exists to restore.
