# ADR-0058 — A project's asset reference set lives inline in `.pixproj` at `FORMAT_VERSION 6`, keyed by `asset_id → content_hash`

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-21 (`phase-11-asset-ingress` plan §1, §2, §2.1, §2.2); recorded 2026-08-22 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-11-asset-ingress` (job `20260821-reachability-remediation`) — `REQ-P11-UI-021`, `REQ-P11-DATA-005`, `REQ-P11-LOGIC-005` |
| Grounded by | Parent `REQ-P11-DATA-005` / `REQ-P11-LOGIC-005` (the mandated `asset_id → content_hash` reference tuple and its break-detection rule); `REQ-P11-UI-022`/`-023` (the update prompt); Article I §8 (no weakening a shipped requirement); the delivered asset-reuse-and-versioning brief (seven-product survey) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0051 (the durable asset store this reference set points into), ADR-0056 (the preference registry that carries this slice's three-state key, cited not extended) |

## Context

`phase-11-asset-ingress` needed a way for a project to point at a library asset without copying its
bytes into the project. A commissioned brief surveyed seven comparable products (Unity, Unreal,
Krita, and others) and recommended two things together: persist the reference set **inline in the
project file** rather than in a sidecar, and identify each reference by **content hash alone** —
`{hash, kind, library_path_hint, last_known_name}`, with no separate asset identifier.

The parent specification had already mandated a different identity shape. `REQ-P11-DATA-005` states
that *"each project holds a reference (`asset_id` → `content_hash`), never a byte copy"*, and
`REQ-P11-LOGIC-005` defines a broken reference as *"only a deleted id or a hash mismatch"*. Both
name `asset_id` as part of the tuple. Article I §8 forbids a downstream plan from weakening a shipped
requirement, and a research brief does not outrank one — so the brief's step 2 (hash-only identity)
could not be adopted as written, while its other four steps could.

A second, independent pressure sharpened the departure rather than merely permitting it. Mid-slice,
the update-prompt requirement was added — `REQ-P11-UI-022`/`-023`: when a referenced library asset's
content changes, the project's owner is asked to *"pick up the change"* or *"keep the referenced
version"*. Under hash-only identity there is no way to phrase that question: a changed hash is not a
changed asset, it is an unresolvable reference, because nothing survives the edit to say "this is
still the same thing, just newer." The brief's own newest requirement needs the field its own step 2
proposed dropping.

## Decision

**The reference set is persisted inline in `.pixproj`, as the brief's step 1 recommended, but each
entry is keyed by the parent's `asset_id → content_hash` tuple, not by content hash alone. The format
version is bumped from 5 to 6 to protect it. `kind` and `last_known_name` are carried as display
labels, never as resolution keys.**

Concretely, the brief's steps 1, 3, 4 and 5 are adopted, step 2 is not, and each is stated on its own
terms below.

1. **Step 1 — inline persistence, adopted.** The reference set lives as one optional root array,
   `"asset_refs"`, in the same `.pixproj` file the user already saves, backs up and versions. This
   avoids outright the Unity-style sidecar failure mode the brief documented (a reference file that
   can be lost independently of the project that names it), and it needs no new file format, no new
   save path and no new migration surface beyond the version bump below.
2. **Step 2 — hash-only identity, rejected.** The brief's proposed entry shape
   `{hash, kind, library_path_hint, last_known_name}` carries no asset identifier. Adopting it would
   weaken the shipped `REQ-P11-DATA-005` tuple and collapse `REQ-P11-LOGIC-005`'s break-detection rule
   to hash comparison alone. It would also make `REQ-P11-UI-022`/`-023` — decided after the brief —
   unphraseable: under hash-only identity, a library-side content edit is not a changed asset, it is
   an unresolvable reference, because there is no identity that survives the edit to ask the question
   against. **This is the one recorded departure**, and nothing else the brief argued for is lost: the
   store stays content-addressed, the hash is still what a reference is *verified* against, and dedup
   and re-import resolution are unchanged (plan §2.1).
3. **Step 3 — display labels, adopted.** `kind` and `last_known_name` are carried in each entry
   (`.pixproj` model at plan §4.1), but they resolve nothing. Showing a stale label is a display
   defect; resolving a reference by one would be a correctness defect — so the loader never falls
   back to a name or a kind, only to `asset_id` and `content_hash`.
4. **Step 4 — the resolve-state indicator, adopted.** A per-reference **resolve state** — does this
   `content_hash` resolve against the local library right now — is computed from the durable set,
   never stored (plan §4.2).
5. **Step 5 — cross-project honesty, adopted.** The parent's separate **shared state** — is this
   `asset_id` referenced by more than one project — is computed by comparing the reference sets of
   whichever projects the application currently has **open**. It is stated as a bound, not glossed:
   an asset **not** marked shared is not a claim that no other project references it, only that no
   other *open* project does. A library-side back-index that could answer the stronger question
   exists in no frozen input, no shipped code and no step of the brief, so the surface states what it
   can actually see rather than implying more.

**The two predicates — resolve state and shared state — stay two, deliberately.** The brief's step-4
indicator is a *resolve* predicate; the parent's `REQ-P11-UI-007` is a *multiplicity* predicate.
`ui/asset_reuse_panel.py` already computed something calling itself the shared-state predicate before
this slice, but over a `Dict[str, AssetCatalog]` that no production caller filled — a predicate
computed over nothing durable, not a missing predicate. This slice's contribution is making the input
to both predicates real (the durable, per-project reference sets), not inventing a third predicate or
merging the two into one.

**The version bump, and why it is asymmetric with `"prefs"`.** `.pixproj` gains two optional root
keys in the same slice — `"asset_refs"` (this decision) and `"prefs"` (ADR-0056's registry, extended
by this slice per `tasks.md` T14/T15) — and they are treated differently on purpose. Both keys are
read with no unknown-key rejection, so an unrecognised root key written by a newer build is silently
ignored, and dropped, by an older one on its next save. The two entries differ only in what that
silent loss costs:

- **`"prefs"` does not bump the format version.** A lost preference costs the user one click to set
  it again. Refusing the whole project to protect a one-click setting would be a worse outcome than
  the loss it prevents.
- **`"asset_refs"` bumps `FORMAT_VERSION` from 5 to 6.** A lost reference set is content the user
  cannot reconstruct — which library assets a project used, silently gone, with no click that
  restores it. An older build meeting a v6 file refuses it by name, loudly, instead of quietly
  discarding the array it does not recognise. The bump is unconditional — every save from this build
  writes `6` whether or not the project has any references at all — because a version that depends on
  whether a feature happens to be used would not describe the schema; it is precisely how a file
  becomes "loads but is wrong."

This is landed, running code, cited rather than forecast:

```
pixelart_creator/data/project_io.py:86   FORMAT_VERSION = 6
pixelart_creator/data/project_io.py:87   _SUPPORTED_VERSIONS = (1, 2, 3, 4, 5, 6)
pixelart_creator/data/project_io.py:282-291
    # One optional root key (REQ-P5-DATA-004, ADR-0056): omitted entirely when
    # no preference has been explicitly set ...
    if prefs_mapping: payload["prefs"] = prefs_mapping
    # Another optional root key (REQ-P11-UI-021, T12): omitted entirely when no
    # reference set was supplied or it is empty, matching "prefs"'s own convention —
    # unlike "prefs" this key's presence is what bumps FORMAT_VERSION (plan §2.2), so
    # the bump itself is unconditional even while the key stays optional.
    if reference_set is not None and reference_set.entries(): payload["asset_refs"] = [...]
pixelart_creator/data/project_io.py:360-387   _parse_prefs() — the forward-tolerant docstring;
    line 381: `continue  # forward-tolerant: an unrecognised preference is dropped`
pixelart_creator/data/project_io.py:924   prefs = _parse_prefs(payload.get("prefs", {}))
```

`_SUPPORTED_VERSIONS` stays `(1, 2, 3, 4, 5, 6)`: versions 1–5 load with an **empty** reference set,
which is correct behaviour, not a migration.

**The reusable command seam, named at its honest size.** Ruling P11-R7 (plan §3.9) chooses the
existing `ui/main_window.py` Library menu as the command surface for registration, over building a
new UI module, because it buys no durable invariant of its own — a note here is the whole of what it
is owed. The seam that *is* durable is that the registration commands
(`register_active_document` / `register_selection` / `register_export_artifact`) are
`Asset_Library_Session`'s own public methods (`ui/asset_library_actions.py`), not menu-bound logic —
so a second front-end (`web_viewer/`, ADR-0035) or a future command palette re-uses the session, not
the menu. That is deliberately the whole scope of what this ADR records about P11-R7; a second ADR
for a menu-vs-module choice that creates no invariant would overstate it.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| **Brief step 2 as written — hash-only identity** | Weakens the shipped `REQ-P11-DATA-005`/`REQ-P11-LOGIC-005` tuple and makes `REQ-P11-UI-022`/`-023`'s update prompt unphraseable — a content edit becomes an unresolvable reference instead of a question the user can answer (§2.1) |
| **Unity-style sidecar file** | The brief's own documented failure mode: a reference file that can be lost independently of the project that names it |
| **Unreal-style redirectors** | Accumulates debt — every rename leaves a forwarding entry that itself must be tracked and eventually cleaned |
| **Krita-style local cache** | Non-portable: the reference set must travel with the project (`REQ-P11-UI-021`), and a local cache does not |
| **A purely additive `"asset_refs"` key with no version bump** | Makes an older build silently drop the reference set on re-save — the one loss this slice's governing principle (loud refusal over silent loss, matching phase-9's and phase-10's precedent) will not accept for content the user cannot reconstruct |
| **Merging resolve state and shared state into one predicate** | They answer different questions (per-project resolvability vs. cross-project multiplicity) and the parent already separates them (`REQ-P11-UI-007` vs. the brief's step 4); merging would lose one of the two answers |
| **A library-side back-index so "shared" means every project, not just open ones** | Not proposed by any frozen input, not shipped, and not a step of the brief — building it now would answer a stronger question than the slice was asked, at unbounded cost |
| **A new asset-registration UI module for the command surface (P11-R7)** | Rejected: it buys no invariant the existing Library menu extension does not already buy, and the durable seam (the session's public methods) exists independently of where the menu entries live |

## Consequences

**Accepted costs.** A `.pixproj` written by this build cannot be opened by a pre-v6 build, even for a
project with zero references — the bump is unconditional. Every consumer of `.pixproj` gains one more
optional root array to validate, bound and migrate-check. The shared-state predicate is honest but
weaker than a naive reading of "shared" would suggest: a reference held by a currently-closed project
is invisible to it.

**What this enables.** A project can point at a library asset with no byte copy and no separate file
to lose; the reference travels wherever the project file travels. `REQ-P11-UI-022`/`-023`'s update
prompt is phraseable because the identity survives a legitimate content edit. Re-import resolution and
dedup are unaffected — the store's own content addressing is untouched by this decision.

**What it constrains.** Any future reference-shaped field must resolve through `asset_id` and
`content_hash` only, never through `kind` or `last_known_name` as a fallback. Any future *content the
user cannot reconstruct* added to `.pixproj` must bump `FORMAT_VERSION`, by the same reasoning applied
here; anything recoverable in one click should not, following `"prefs"`'s precedent. A claim of
"shared" anywhere in the UI must continue to mean "referenced by an open project," not "referenced
anywhere," until and unless a library-side back-index is separately decided.

## Compliance

Layering was not re-run for this ADR specifically; the current baseline is T26's, quoted in
ADR-0059's Compliance section, and this decision introduces no import edge of its own — `"asset_refs"`
is a `data/project_io.py` schema change, not a new module.

The cited lines above were read directly in the `feat-asset-ingress` worktree on 2026-08-22, not
copied from the plan's forecast of them (the plan's own citations at `:69-70`, `:250`, `:311`, `:814`
and `:325-327` describe an earlier state of the same file and are superseded here by the lines this
decision actually landed at).

## What this record does not verify

- **No suite was run for this record.** `main/tests/data/test_project_io.py` (or its successor) is
  the detector for the version-bump and forward-tolerance behaviour described above; it was not
  executed while writing this ADR.
- **The `.pixproj` back-compat load fixtures (versions 1–5) were not exercised here.** Plan §6 names
  them as the gate; this record cites the parsing code, not a fixture run.
- **The update-prompt UI (`ui/asset_update_prompt.py`) itself is out of this record's scope.** This
  ADR records why the identity tuple makes the prompt phraseable, not the prompt's own implementation
  or its acceptance.
