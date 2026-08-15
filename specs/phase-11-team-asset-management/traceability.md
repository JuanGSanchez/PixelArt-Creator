# Traceability matrix — Phase 11: Team & Asset Management

REQ ↔ dossier S-id ↔ constitution article ↔ acceptance scenario ↔ **landed test**. Proves every
requirement is specified, has an acceptance scenario, and names the test that covers it. **All 26 REQs
are specified and scenario-covered**; the eight formerly-PENDING rows were finalised after CL-P11-1..4
were adjudicated (spec §10, grounded in the Researcher report). **24 of 26 are covered by a landed test;
the remaining 2 (LOGIC-008, UI-011) were RE-ADJUDICATED on 2026-07-30 (T11-X02) and are now PARTIALLY
COVERED — see Q1 below.**

*(This header sentence previously read: "**24 of 26 are covered by a landed test; 2 (LOGIC-008, UI-011)
have no test located and are recorded below as UNCOVERED — UNDER INVESTIGATION.**" That reading was
accurate against the **old** requirement text, which promised a mechanism the product does not have; the
two requirements have since been corrected in `spec.md`, and the tests that cover the **corrected**
properties are now named in their rows.)*

**T11-X01 editorial reconciliation (2026-07-30).** This matrix previously read *"↔ (future) test"*,
*"Tests are authored later by AGT-04 / AGT-06"* and a `DRAFTED` / `COVERED (CL-n)` status on every row —
for a phase whose tests had already landed. It also cited **bare stems with no directory, 20 of which
named a file that does not exist on disk** (`test_asset_catalog_validate`, `test_tag_ops_reversible`,
`test_constants`, …), and two that were ambiguous (`test_version_browser` matched two real files;
`test_a11y` collided with three unrelated `test_a11y_*.py` modules from other phases). Following the
Phase-13 precedent (T13-X01), the **Test** column below now names the **actual landed test files** as
repo-root-relative paths — several landed under **consolidated filenames** that differ from the early
"(future)" placeholder names (26 planned stems → 23 landed files). **Every path in the Test column was
verified to exist.** The `(CL-n)` adjudication provenance has been moved out of **Status** — where it
conflated *"clarification resolved"* with *"test exists"* — into the coverage summary below.

The **Acceptance scenario** column cites the `SC-P11-*` ids minted in `acceptance.md` by the same
T11-X01 pass (the file previously had 37 prose scenario titles and **no** ids, which made this the only
one of the 18 phase matrices that was machine-uncheckable in either direction). Four REQs have no
dedicated scenario of their own and cite the sibling scenario that exercises them — marked **(shared)**
and explained in the `acceptance.md` header note.

**Evidence basis for the Test column.** HIGH = an explicit `REQ-P11-…` string appears in the test file
itself (verified by an exhaustive scan of `main/tests/**/*.py` that expands the shorthand suffix form
`REQ-P11-DATA-001/-002/-003/-007` into its member ids — a scan that does *not* expand it under-reports
five DATA rows as uncovered). MEDIUM = established by import/assertion convention with **no** REQ-ID
string. Test *bodies* were not executed as part of this reconciliation.

| REQ-ID | Layer | Traces (S-id / primitive / article) | Acceptance scenario | Test | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P11-DATA-001 | data | S6, S7, Art XI, ROADMAP P11 | acceptance.md · SC-P11-DATA-001-1 | `tests/logic/test_asset_catalog.py` + `tests/data/test_asset_catalog_io.py` | IMPLEMENTED (HIGH) |
| REQ-P11-DATA-002 | data | PIO-1, Art VII §1/§2, S7 | acceptance.md · SC-P11-DATA-002-1/-2 | path-traversal legs: `test_asset_paths.py::test_safe_asset_id_rejects_dot_and_dotdot`, `::test_safe_asset_id_rejects_forward_slash`, `::test_safe_asset_id_rejects_backslash`, `::test_safe_asset_id_rejects_out_of_charset`, `::test_resolve_within_rejects_dotdot_escape`, `::test_resolve_within_rejects_absolute_escape`, `::test_resolve_within_rejects_deep_traversal`, `::test_resolve_within_rejects_drive_letter_escape`, `::test_load_rejects_sidecar_path_escaping_root`; untrusted-catalog validation: `test_asset_catalog_io.py::test_load_index_not_json_raises`, `::test_load_unsupported_schema_version_raises`, `::test_load_over_max_catalog_assets_raises`, `::test_sidecar_invalid_content_hash_raises`, `::test_sidecar_unknown_kind_raises`, `::test_sidecar_metadata_not_object_raises`, `::test_load_asset_rejects_non_json_payload` | IMPLEMENTED (HIGH; traversal legs MEDIUM) |
| REQ-P11-DATA-003 | data | S6, ROADMAP P11, Art XI | acceptance.md · SC-P11-DATA-003-1 | `tests/data/test_asset_catalog_io.py` + `tests/logic/test_asset_tags.py` | IMPLEMENTED (HIGH) |
| REQ-P11-DATA-004 | data | S7, ROADMAP P11, Art X (P10 reuse), Art VII, Research §3/§4 | acceptance.md · SC-P11-DATA-004-1/-2/-3/-4 | `tests/data/test_asset_revision_store.py` + `tests/data/test_asset_cas.py` + `tests/logic/test_content_hash.py` | IMPLEMENTED (HIGH) |
| REQ-P11-DATA-005 | data | S6, ROADMAP P11, Art VII, Research §4 | acceptance.md · SC-P11-DATA-005-1/-2/-3 | `tests/data/test_asset_cas.py` + `tests/data/test_asset_export.py` | IMPLEMENTED (HIGH) |
| REQ-P11-DATA-006 | data | S7, Art I, P10 `data/cloud/`, Research §4.2/§6 | acceptance.md · SC-P11-DATA-006-1/-2/-3 | `tests/data/test_asset_storage.py` + `tests/data/test_asset_shared_backend.py` | IMPLEMENTED (HIGH) |
| REQ-P11-DATA-007 | data | PIO-1, DOC-1, Art I, Art VII | acceptance.md · SC-P11-DATA-001-1 **(shared** — reload round-trip leg; DATA-007 appears in no Feature comment**)** | `test_asset_catalog_io.py::test_store_then_load_asset_reconstructs_equivalent_document` (the asset reloads through the shipped `.pixproj`/PIO-1 form, not a second serialiser), `::test_catalog_roundtrip_preserves_entries`, `::test_store_identical_documents_dedup_to_same_hash`, `::test_sidecar_roundtrip_via_crafted` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-001 | logic | P2, S11, Art I, Art X | acceptance.md · SC-P11-LOGIC-001-1 | `tests/logic/test_asset_catalog.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-002 | logic | P2, S11, HIS-1, Art I | acceptance.md · SC-P11-LOGIC-002-1/-2 | `tests/logic/test_asset_tags.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-003 | logic | P2, S11, ROADMAP P11 | acceptance.md · SC-P11-LOGIC-003-1/-2/-3 | `tests/logic/test_asset_query.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-004 | logic | P2, S11, Art I, ROADMAP P11 | acceptance.md · SC-P11-LOGIC-004-1/-2/-3 | `tests/logic/test_dependency_graph.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-005 | logic | P2, S11, ROADMAP P11, Research §2, Art VI | acceptance.md · SC-P11-LOGIC-005-1/-2/-3 | `tests/logic/test_break_detection.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-006 | logic | P2, S11, Art X, P10 REQ-P10-LOGIC-003, Research §3 | acceptance.md · SC-P11-LOGIC-006-1 | `tests/logic/test_asset_version.py` + `tests/logic/test_content_hash.py` | IMPLEMENTED (HIGH) |
| REQ-P11-LOGIC-007 | logic | Art II, Art VII, S12 | acceptance.md · SC-P11-LOGIC-007-1 | `test_asset_version.py::test_version_bound_is_the_named_constant`, `::test_constructor_at_bound_ok_over_bound_rejected`, `::test_append_at_bound_is_rejected` + `test_dependency_graph.py::test_depth_bound_is_the_named_constant`, `::test_chain_deeper_than_depth_bound_raises`; `MAX_TAG_BYTES` / `MAX_TAGS_PER_ASSET` are imported from `logic.constants` (never inlined) in `tests/logic/test_asset_catalog.py`, `tests/logic/test_asset_tags.py`, `tests/ui/test_asset_tagging.py` | **IMPLEMENTED** — resolved from MEDIUM by AGT-02 (PA-08, 2026-08-15): the constant-identity assertions are now named per test, so the trace no longer rests on a convention a reader has to infer |
| REQ-P11-LOGIC-008 | logic | Art VI, S1, S12 | acceptance.md · SC-P11-LOGIC-008-1 *(rewritten by T11-X02)* | `tests/logic/test_asset_catalog.py` (`test_catalog_constructor_count_cap` L226, `test_add_at_cap_raises` L262, `test_max_catalog_assets_is_the_named_constant` L234 — bound → domain error) + `tests/logic/test_dependency_graph.py` (`test_depth_bound_is_the_named_constant` L255, `test_chain_within_depth_bound_traverses` L268, `test_chain_deeper_than_depth_bound_raises` L274, + the Hypothesis determinism block from L280) + `tests/logic/test_asset_query.py` (pure/deterministic query — Hypothesis determinism, module docstring L3–L7) + the `check_layering` CI gate (Qt-free leg; `.github/workflows/ci.yml`, job `quality-gate`, step **"Architecture layering + cycle checks (P11 scripts)"**) | **RE-ADJUDICATED (T11-X02) — PARTIALLY COVERED (MEDIUM)**: the *bounded*, *pure/deterministic* and *Qt-free* legs of the corrected requirement are covered by the tests/gate named here (opened and read; none carries a `REQ-P11-LOGIC-008` annotation, hence MEDIUM). The *"never invoked from a paint/timer path"* leg has **NO test — one must be authored** (AGT-04). **Not** counted as fully covered. |
| REQ-P11-UI-001 | ui | REQ-P11-DATA-001, LOGIC-001, S6, Art V | acceptance.md · SC-P11-UI-001-1 | `tests/ui/test_asset_library_panel.py` + `tests/ui/test_asset_library_integration.py` | IMPLEMENTED (HIGH) |
| REQ-P11-UI-002 | ui | REQ-P11-DATA-003, LOGIC-002, Art V | acceptance.md · SC-P11-DATA-003-1 + SC-P11-LOGIC-002-1/-2 **(shared)** | `tests/ui/test_asset_tagging.py` + `tests/ui/test_asset_library_integration.py` | IMPLEMENTED (HIGH) |
| REQ-P11-UI-003 | ui | REQ-P11-LOGIC-003, Art V | acceptance.md · SC-P11-LOGIC-003-1/-2/-3 **(shared)** | `tests/ui/test_asset_search_panel.py` + `tests/ui/test_asset_library_integration.py` | IMPLEMENTED (HIGH) |
| REQ-P11-UI-004 | ui | REQ-P11-DATA-004, LOGIC-006, Art V | acceptance.md · SC-P11-UI-004-1 | `tests/ui/test_asset_version_browser.py` (**not** `tests/ui/test_version_history_browser.py`, which is a different, Phase-10-lineage module — the old `test_version_browser` stem was ambiguous between the two) | IMPLEMENTED (HIGH) |
| REQ-P11-UI-005 | ui | REQ-P11-LOGIC-004, S6, Art V | acceptance.md · SC-P11-UI-005-1 | `tests/ui/test_dependency_graph_view.py` | IMPLEMENTED (HIGH) |
| REQ-P11-UI-006 | ui | REQ-P11-LOGIC-005, UI-005, Art V | acceptance.md · SC-P11-UI-006-1 | `tests/ui/test_break_warning.py` + `tests/ui/test_dependency_graph_view.py` (break-indicator legs) | IMPLEMENTED (HIGH) |
| REQ-P11-UI-007 | ui | REQ-P11-DATA-005, Art V | acceptance.md · SC-P11-UI-007-1 | `tests/ui/test_asset_reuse.py` | IMPLEMENTED (HIGH) |
| REQ-P11-UI-008 | ui | Art V §1 | acceptance.md · SC-P11-UI-008-1 | `tests/ui/test_asset_library_a11y_theme.py` (a11y legs) + `tests/ui/test_break_warning.py` (a11y leg) | IMPLEMENTED (HIGH) |
| REQ-P11-UI-009 | ui | Art V §3 | acceptance.md · SC-P11-UI-009-1 | `tests/ui/test_asset_library_a11y_theme.py` (both-themes legs) + `tests/ui/test_break_warning.py` (both-themes leg) | IMPLEMENTED (HIGH) |
| REQ-P11-UI-010 | ui | Art V §2, F6 | acceptance.md · SC-P11-UI-010-1 | `tests/ui/test_asset_library_a11y_theme.py` (translatable-string leg) | IMPLEMENTED (HIGH) |
| REQ-P11-UI-011 | ui | REQ-P11-LOGIC-008, Art VI, S1 | acceptance.md · SC-P11-LOGIC-008-1 **(shared** — its `And the result is observable in the same synchronous call (no worker thread, timer, or poller)` line is the UI-011 criterion; **rewritten by T11-X02** — it previously read `Then the GUI thread is not blocked`**)** | `tests/ui/test_asset_search_panel.py` (synchronous-completion leg: `test_name_substring_narrows_to_matches` L71–L75 sets the input and asserts the resulting panel state **in the next statement**, and the module contains **zero** `waitSignal`/`waitUntil`/`qWait` calls — verified by search) + `tests/ui/test_asset_library_integration.py` § *"Teardown regression guard (AGT-05 §3: no worker introduced)"* (`test_standalone_panels_are_registered_in_the_drain_set` L145, `test_window_with_asset_panels_disposes_cleanly` L159 — the nothing-to-tear-down leg) | **RE-ADJUDICATED (T11-X02) — PARTIALLY COVERED (MEDIUM)**: the *completes-in-the-triggering-call* and *no-worker-to-tear-down* legs are covered by the tests named here (opened and read; both are annotated to UI-003 / the AGT-05 teardown contract, **not** to UI-011, hence MEDIUM). The static leg — *no Phase-11 panel/session references `QThread`/`QThreadPool`/`QRunnable`/`threading`/`concurrent.futures` or exposes a `shutdown_*`* — has **NO test; one must be authored** (AGT-06). **Not** counted as fully covered. |

## Q1 — RESOLVED 2026-07-30 by re-adjudication (T11-X02); a test-authoring residue remains

**Q1 as originally posed is CLOSED.** It read, in full:

> ## Q1 — the two uncovered requirements (open, not closed)
>
> `REQ-P11-LOGIC-008` ("Asset operations are batch, off the interactive render loop") and
> `REQ-P11-UI-011` ("Asset operations keep the UI responsive") have **no test located**. The exhaustive
> REQ-ID scan returns zero hits for either id; the old stems `test_asset_ops_offloop` /
> `test_asset_ops_responsive` name no file; and targeted searches for `QThreadPool`, `QRunnable`,
> `processEvents`, `per-frame` and `16 ms` across the Phase-11 asset tests returned nothing. They are
> recorded here as **uncovered**, not as covered — the exact source text is `acceptance.md`
> `SC-P11-LOGIC-008-1`.
>
> **Open question for the owner (not resolved by this pass):** were LOGIC-008 / UI-011 satisfied by an
> architectural argument (the logic layer is Qt-free by construction, therefore trivially off-loop) and
> deliberately left untested, or is this a real coverage gap? The artifacts do not say. Note the
> asymmetry: the *same* Feature block's third requirement, LOGIC-007, does have (MEDIUM-confidence)
> coverage, so "the whole block was waived" is not the obvious reading.

**The answer was neither branch of that question: the requirements themselves were wrong.** No
off-GUI-thread mechanism exists in Phase 11 — `QThread`, `QThreadPool`, `QRunnable`, `threading` and
`concurrent.futures` return **zero** hits across the Phase-11 asset and dependency modules, while the same
search finds five worker modules serving other phases (`ui/export_worker.py`, `ui/automation_worker.py`,
`ui/cloud_worker.py`, `ui/realtime_worker.py`, `ui/assistant_worker.py`), so the project is not simply
unfamiliar with the pattern. Three Phase-11 module docstrings say the work is synchronous outright, and the
`ui/asset_worker.py` module `plan.md` §7 names **does not exist on disk**. No test was missing: **there was
nothing true to test.** The user adjudicated the record to the shipped synchronous behaviour;
`spec.md` REQ-P11-LOGIC-008 and REQ-P11-UI-011 are corrected in place (T11-X02, prior text quoted there),
`acceptance.md` `SC-P11-LOGIC-008-1` is rewritten (prior text quoted in its header note), and the two rows
above now cite the tests that cover the corrected properties. **The requirements were deliberately
weakened.**

**Residue — a test-authoring gap, NOT a specification question (for AGT-04 / AGT-06):** two legs of the
corrected requirements have no test and are honestly recorded as such rather than marked covered:
1. **LOGIC-008** — *"no Phase-11 asset/graph operation is invoked from a paint or timer path."* No test
   asserts this today.
2. **UI-011** — *"no Phase-11 asset panel or session references `QThread`/`QThreadPool`/`QRunnable`/
   `threading`/`concurrent.futures`, and none exposes a `shutdown_*` teardown path."* True of the code as
   it stands (verified by search on 2026-07-30) but **not** asserted by any test, so nothing guards the
   regression.

**Future work, not a lost requirement:** the off-GUI-thread capability with progress + cancel is recorded
as **FW-P11-1** in `spec.md` §6. It needs a new REQ-ID in its owning future phase and a measured latency
justification — Phase 11 never measured the synchronous cost, so no threshold exists to state.

## Coverage summary

- **REQs total:** 26 — DATA 7, LOGIC 8, UI 11.
- **Specified + acceptance-scenario covered:** 26 / 26 — every REQ cites a minted `SC-P11-*` id
  (22 REQs own a dedicated scenario; 4 — DATA-007, UI-002, UI-003, UI-011 — cite a shared sibling
  scenario, marked **(shared)** above).
- **Covered by a landed test:** **24 / 26** — 23 at HIGH confidence (explicit REQ-ID annotation in the
  test file), 1 at MEDIUM (LOGIC-007, convention-inferred).
- **Partially covered after re-adjudication (T11-X02, 2026-07-30):** **2** — LOGIC-008, UI-011 (Q1 above).
  Each now names real, opened tests for the *corrected* properties (bounded / pure-deterministic / Qt-free;
  completes-in-the-triggering-call / nothing-to-tear-down) at MEDIUM confidence, and each still has **one
  leg with no test**, recorded in Q1 for AGT-04 / AGT-06. They are **not** counted among the 24.
  *(This bullet previously read: "**Uncovered / under investigation:** **2** — LOGIC-008, UI-011 (Q1
  above). These are **not** counted as covered." — accurate against the pre-correction requirement text.)*
- **Landed test files cited:** 23 distinct modules — logic 7 (`test_asset_catalog`, `test_asset_tags`,
  `test_asset_query`, `test_dependency_graph`, `test_break_detection`, `test_asset_version`,
  `test_content_hash`), data 7 (`test_asset_catalog_io`, `test_asset_paths`,
  `test_asset_revision_store`, `test_asset_cas`, `test_asset_export`, `test_asset_storage`,
  `test_asset_shared_backend`), ui 9 (`test_asset_library_panel`, `test_asset_library_integration`,
  `test_asset_tagging`, `test_asset_search_panel`, `test_asset_version_browser`,
  `test_dependency_graph_view`, `test_break_warning`, `test_asset_reuse`,
  `test_asset_library_a11y_theme`). **All 23 verified to exist on disk.**
- **Finalised via §10 adjudication (grounded in the Researcher report):** 8 — DATA-004 (CL-1),
  DATA-005 (CL-2), DATA-006 (CL-3), LOGIC-005 (CL-4), LOGIC-006 (CL-1), UI-004 (CL-1), UI-006 (CL-4),
  UI-007 (CL-2). *(Moved here from the Status column — clarification provenance is not test evidence.)*
- **Every REQ** traces to a dossier S-id / shipped primitive + a constitution article + ≥1 Gherkin
  scenario. **No REQ is untraced.**
- **Re-adjudicated (T11-X02, 2026-07-30):** 2 — LOGIC-008, UI-011. Both requirement statements, the
  `SC-P11-LOGIC-008-1` scenario, and the §2/§3 US-6/§5/§7/§8 cross-references in `spec.md` were corrected
  **in place with the prior text quoted**, because they promised an off-GUI-thread mechanism the product
  does not contain. The ambition is preserved as future work **FW-P11-1** (`spec.md` §6).
- **Gate:** the specification side of the matrix is **complete** (`sdd-plan` / `sdd-analyze` unblocked).
  A **ship** gate (`sdd-checklist`, AGT-06 — "every REQ has a passing test") is **still NOT** satisfied:
  Q1's *specification* question is closed, but the **two test-authoring legs listed in Q1 remain open**.
  *(This bullet previously ended: "is **NOT** satisfied while Q1 is open.")*
