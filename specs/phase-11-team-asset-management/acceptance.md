# Acceptance scenarios (Gherkin) — Phase 11: Team & Asset Management

> Emitted by AGT-02 (`sdd-clarify` output step). **All 26 REQs now have acceptance scenarios.** The eight
> formerly-PENDING REQs (DATA-004/-005/-006, LOGIC-005/-006, UI-004/-006/-007) are finalised below from the
> §10 adjudications (spec §10), grounded in the Researcher report. Feature → consumed by AGT-06 as
> acceptance tests (one test per criterion, Article IV).
>
> **Scenario-id reconciliation (T11-X01, 2026-07-30).** This file originally carried **37 prose
> `Scenario:` titles and no ids** — the only acceptance file in the tree without them, which made
> `traceability.md` the only matrix that could not be machine-checked in either direction. The ids
> below were **minted from the scenarios already present**; **no scenario was added, removed, split or
> reworded.** Scheme (the one the other 17 phases use): `SC-P11-<LAYER>-<NNN>-<k>` — `SC-` + the owning
> REQ-ID's layer and number, plus a `-k` ordinal for the k-th scenario of that REQ. Each scenario carries
> **exactly one** id, formed from the REQ in its own `# REQ-P11-…` Feature comment that it most directly
> exercises (layer + asserted behaviour).
>
> **Four REQs have no dedicated scenario of their own** and are exercised by a scenario minted under a
> sibling REQ in the same Feature block. This is recorded, not papered over — `traceability.md` cites the
> shared id for each and repeats this note:
> `REQ-P11-DATA-007` → `SC-P11-DATA-001-1` (the reload round-trip leg; DATA-007 appears in **no** Feature
> comment in this file); `REQ-P11-UI-002` → `SC-P11-DATA-003-1` + `SC-P11-LOGIC-002-1/-2`;
> `REQ-P11-UI-003` → `SC-P11-LOGIC-003-1/-2/-3`; `REQ-P11-UI-011` → `SC-P11-LOGIC-008-1` (whose
> `And the result is observable in the same synchronous call (no worker thread, timer, or poller)` line
> *is* the UI-011 criterion — **rewritten by T11-X02, see the note below**; it previously read
> `Then the GUI thread is not blocked (the UI stays responsive)`).
>
> **T11-X02 re-adjudication (2026-07-30) — one scenario rewritten, none added, removed or renumbered.**
> `SC-P11-LOGIC-008-1` asserted an off-GUI-thread mechanism that **does not exist in the product** (no
> `QThread`/`QThreadPool`/`QRunnable`/`threading`/`concurrent.futures` in any Phase-11 asset or dependency
> module; the modules' own docstrings state the work is synchronous). Its steps are corrected in place to
> the shipped synchronous behaviour, matching the re-adjudicated REQ-P11-LOGIC-008 / REQ-P11-UI-011 in
> `spec.md`. **Its previous text, quoted in full** — the block below is a *quotation of deleted text*
> inside this blockquote (every line carries the `> ` prefix), **not a live scenario**: this file still
> contains exactly **37** live `Scenario:` lines with **37 distinct ids**, unchanged from T11-X01, so a
> bijection check must not count the quoted `Scenario:` line below (an unanchored grep will see it twice):
> ```
>   Scenario: SC-P11-LOGIC-008-1 Asset operations stay off the per-frame loop and responsive
>     Given a large catalog
>     When a catalog scan, search, or dependency-graph query runs
>     Then the GUI thread is not blocked (the UI stays responsive)
>     And the operation is not gated by the 16 ms per-frame budget
> ```
> The `Then the GUI thread is not blocked (the UI stays responsive)` step was the false one. The id, the
> scenario count (37) and the Feature block are unchanged. The off-GUI-thread ambition is tracked as
> **future work FW-P11-1** (`spec.md` §6), not as an acceptance criterion.

Feature: Asset catalog persistence and retrieval
  # REQ-P11-DATA-001, REQ-P11-LOGIC-001, REQ-P11-UI-001
  # (also the round-trip leg for REQ-P11-DATA-007 — see the header note)

  Scenario: SC-P11-DATA-001-1 Cataloged assets persist and enumerate
    Given N shipped entities (sprites, animations, tilesets) registered as assets
    When the catalog is reloaded in a new session
    Then enumeration returns exactly those N entries
    And each entry retains its id, kind, display name, tags, and metadata

  Scenario: SC-P11-LOGIC-001-1 Retrieval by id
    Given an asset with a known id in the catalog
    When I retrieve by that id
    Then the matching entry is returned
    And retrieval by an unknown id yields a clean not-found result without a crash

  Scenario: SC-P11-UI-001-1 Library panel reflects the catalog
    Given the asset-library panel is open
    When an asset is added to or removed from the catalog
    Then the panel's listed entries update to match the catalog
    And the panel contains no domain logic (it binds to the logic layer)

Feature: Untrusted asset metadata and imported catalogs (Article VII)
  # REQ-P11-DATA-002

  Scenario: SC-P11-DATA-002-1 Malformed or oversized metadata is rejected
    Given an imported catalog or metadata payload that is malformed, oversized, or exceeds a cap
    When it is loaded
    Then a clear domain error is raised
    And the payload is never passed to eval or exec

  Scenario: SC-P11-DATA-002-2 Path-traversal defence on referenced asset paths
    Given a referenced asset path containing ".." or an absolute path escaping the library root
    When the reference is resolved
    Then the reference is rejected with a domain error
    And no referenced path resolves outside the library root

Feature: Tagging assets
  # REQ-P11-DATA-003, REQ-P11-LOGIC-002, REQ-P11-UI-002

  Scenario: SC-P11-DATA-003-1 Tags persist across sessions
    Given an asset with tags added
    When the catalog is reloaded
    Then the added tags are present
    And a removed tag is absent

  Scenario: SC-P11-LOGIC-002-1 Tagging is reversible and idempotent
    Given an asset with a known tag set
    When I add a tag and then undo
    Then the tag set returns exactly to the prior state
    And adding an already-present tag is a no-op

  Scenario: SC-P11-LOGIC-002-2 Tag bounds enforced
    Given an asset at the maximum tag count or a tag exceeding the byte limit
    When I attempt to add the tag
    Then a domain error is raised with a translatable message rather than silent truncation

Feature: Search and filter over the catalog
  # REQ-P11-LOGIC-003, REQ-P11-UI-003

  Scenario: SC-P11-LOGIC-003-1 Filter by tag
    Given a catalog with entries carrying various tags
    When I query by a specific tag
    Then exactly the entries carrying that tag are returned in a stable order

  Scenario: SC-P11-LOGIC-003-2 Combined name, tag, and kind filters intersect
    Given a catalog of mixed kinds and tags
    When I apply a name substring, a tag, and a kind together
    Then the result is the intersection of all three filters
    And clearing the query restores the full catalog

  Scenario: SC-P11-LOGIC-003-3 Query determinism
    Given the same catalog snapshot and the same query
    When the query is run twice
    Then the two result sets are byte-identical

Feature: Dependency graph is queryable
  # REQ-P11-LOGIC-004, REQ-P11-UI-005

  Scenario: SC-P11-LOGIC-004-1 Query dependents of a sprite
    Given sprite S is a frame of animation A and the source image of tileset T, and tilemap M uses T
    When I query the dependents of S
    Then the direct dependents include A and T
    And the transitive dependents include M

  Scenario: SC-P11-LOGIC-004-2 Query dependencies of a tilemap
    Given tilemap M references tileset T which uses sprite S
    When I query the dependencies of M
    Then the direct dependencies include T
    And the transitive dependencies include S

  Scenario: SC-P11-LOGIC-004-3 Cycle is detected, not looped
    Given a reference cycle among assets
    When I traverse the graph
    Then the cycle is detected and reported
    And traversal terminates without hanging

  Scenario: SC-P11-UI-005-1 Dependency-graph view renders the query
    Given a selected asset in the dependency-graph view
    Then the view shows its direct dependencies and dependents matching the model
    And a cycle is shown without hanging the view

Feature: Bounded numerics and synchronous posture
  # (T11-X02, 2026-07-30: this Feature title previously read "Bounded numerics and batch posture";
  #  "batch" named a worker mechanism that does not exist — see the header note. No id changed.)
  # REQ-P11-LOGIC-007, REQ-P11-LOGIC-008, REQ-P11-UI-011

  Scenario: SC-P11-LOGIC-007-1 Tuning values are named constants
    Given the Phase-11 logic and data modules
    When they are inspected for numeric literals at call sites
    Then every tuning value resolves to a named constant in logic/constants.py

  # SC-P11-LOGIC-008-1 was rewritten by T11-X02 (2026-07-30) — prior text quoted in the header note.
  Scenario: SC-P11-LOGIC-008-1 Asset operations are bounded, pure, and finish in the triggering call
    Given a catalog, tag set, and dependency graph within the bounds named in logic/constants.py
    When a catalog scan, search, tagging, or dependency-graph query runs
    Then it returns a deterministic result over the immutable in-memory value (identical input, identical result)
    And it imports no Qt (check_layering passes over logic/ and data/)
    And exceeding MAX_CATALOG_ASSETS, MAX_TAGS_PER_ASSET, or MAX_DEPENDENCY_DEPTH raises a domain error instead of proceeding
    And the result is observable in the same synchronous call (no worker thread, timer, or poller)
    And the operation is never invoked from a paint or timer path, so it is not gated by the 16 ms per-frame budget

Feature: Accessibility, theming, and internationalisation (Article V)
  # REQ-P11-UI-008, REQ-P11-UI-009, REQ-P11-UI-010

  Scenario: SC-P11-UI-008-1 Accessibility audit passes
    Given the Phase-11 UI surfaces (library, tagging, search/filter, dependency-graph view)
    When the a11y audit runs
    Then no missing accessible name, unreachable control, or invisible focus is reported

  Scenario: SC-P11-UI-009-1 Both themes render correctly
    Given each Phase-11 surface
    When rendered in light and in dark theme
    Then it renders correctly in both, with no per-widget hard-coded colour

  Scenario: SC-P11-UI-010-1 All user-visible strings are translatable
    Given the Phase-11 ui files
    When the string audit runs
    Then no unwrapped user-visible string is found

Feature: Asset version control — append-only, content-addressable revision store (CL-1)
  # REQ-P11-DATA-004, REQ-P11-LOGIC-006, REQ-P11-UI-004

  Scenario: SC-P11-DATA-004-1 Recording a revision appends an immutable, content-hash-keyed descriptor
    Given an asset with existing content
    When a new revision of the asset is recorded
    Then an immutable revision descriptor keyed by its content hash is appended
    And the asset bytes are stored once in the content-addressable store
    And no existing revision is mutated or deleted in place

  Scenario: SC-P11-DATA-004-2 Identical bytes do not create a duplicate revision (content-hash dedup)
    Given an asset whose current content hash is H
    When bytes with the same canonicalized content (hash H) are recorded again
    Then no new revision is created
    And no duplicate blob is stored (a dedup no-op)

  Scenario: SC-P11-DATA-004-3 A prior revision is retrievable and hash-verified
    Given an asset with several recorded revisions
    When I retrieve a prior revision by its content-hash / revision pointer
    Then the matching revision's bytes are returned and verify against the recorded hash
    And a blob whose content hash mismatches the record is rejected

  Scenario: SC-P11-DATA-004-4 Asset revisions do not route through the live-collab CRDT
    Given the asset-version store and the Phase-10 live-collaboration CRDT
    When asset revisions are recorded
    Then they are stored in the content-addressable revision store only
    And they never pass through the CRDT (which serves live documents only)
    And check_layering confirms the store is Qt-free data/

  Scenario: SC-P11-LOGIC-006-1 The version model is an ordered, immutable, content-hash-addressed DAG
    Given an asset's revision history
    When the history is constructed
    Then it yields ordered immutable descriptors, each carrying a content hash and a parent link
    And a content-hash comparison reports "unchanged" for identical bytes and "changed" otherwise
    And the model imports no Qt and has no CRDT dependency

  Scenario: SC-P11-UI-004-1 Version browser restores a revision append-only
    Given an asset with a revision history shown in the version browser
    When I restore a prior revision
    Then that revision's content is reinstated as a new head revision
    And the earlier revisions remain in the history (append-only, not rewritten)
    And the widget contains no domain logic and both themes render correctly

Feature: Cross-project reuse — CAS + reference-not-copy (CL-2)
  # REQ-P11-DATA-005, REQ-P11-UI-007

  Scenario: SC-P11-DATA-005-1 A shared asset's bytes are stored once across projects
    Given an asset referenced by two different projects
    When both references resolve to the same content hash
    Then the asset bytes are stored exactly once in the content-addressable store
    And each project holds a reference (asset id to content hash), not a byte copy
    And a second project referencing the same content is a dedup no-op

  Scenario: SC-P11-DATA-005-2 Export bundles the referenced blobs for portability
    Given a project that references shared assets by id/hash
    When the project is exported
    Then the export bundles exactly the blobs its references resolve to
    And the exported project opens self-contained

  Scenario: SC-P11-DATA-005-3 Imported reference is path-traversal-defended
    Given an imported asset reference whose path escapes the library root or violates a cap
    When the reference is resolved
    Then it is rejected with a domain error
    And no referenced path resolves outside the library root

  Scenario: SC-P11-UI-007-1 Reuse UI references a shared asset without copying
    Given a shared asset in the library
    When I reference it into a project via the reuse UI
    Then the asset appears in the project without duplicating its payload (the CAS blob count is unchanged)
    And the UI marks an asset referenced by more than one project as shared
    And the widget contains no domain logic

Feature: Asset-library storage substrate — local-first, cloud optional (CL-3)
  # REQ-P11-DATA-006

  Scenario: SC-P11-DATA-006-1 The library works fully offline against a local store
    Given no Phase-10 provider is connected
    When catalog, tag, version, and CAS operations run
    Then they all succeed against the local store with no cloud requirement

  Scenario: SC-P11-DATA-006-2 A connected provider transparently backs the same operations
    Given a Phase-10 provider is connected
    When the same library / CAS operations run
    Then they are served by the shared backend transparently through the abstraction layer
    And callers above the storage port are unchanged
    And no module above the port names a specific provider

  Scenario: SC-P11-DATA-006-3 Cloud-fetched blobs are content-hash verified
    Given a blob fetched from the shared store
    When its content hash does not match the recorded hash
    Then the blob is rejected

Feature: Break detection — passive flag from a reference-validation pass (CL-4)
  # REQ-P11-LOGIC-005, REQ-P11-UI-006

  Scenario: SC-P11-LOGIC-005-1 A missing or changed target flags the referencing edge as broken
    Given asset B references asset A
    When A is deleted, or A's recorded dependency content-hash no longer matches the current A
    Then the reference-validation pass flags B's reference to A as BROKEN
    And the flag is surfaced on the dependency query result

  Scenario: SC-P11-LOGIC-005-2 A valid reference is never falsely flagged
    Given asset B references a present, unchanged asset A
    When the reference-validation pass runs
    Then B's reference to A is not flagged

  Scenario: SC-P11-LOGIC-005-3 Revalidation is content-hash-gated and triggered on catalog change
    Given a catalog change alters the content hash of some nodes
    When revalidation runs
    Then only dependents of the changed nodes are revalidated
    And the pass is pure, deterministic, and pull-based (no event push)
    And the model imports no Qt

  Scenario: SC-P11-UI-006-1 The UI surfaces breaks passively and refreshes on catalog change
    Given an asset with a broken reference
    When the dependency-graph view or library is shown
    Then a passive break indicator is displayed matching the validation pass
    And the indicator refreshes after a catalog change
    And an asset with only valid references shows no break indicator
    And there is no live push notification (future enhancement)
