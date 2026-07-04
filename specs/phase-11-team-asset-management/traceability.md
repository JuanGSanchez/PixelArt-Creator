# Traceability matrix — Phase 11: Team & Asset Management

REQ ↔ dossier S-id ↔ constitution article ↔ acceptance scenario ↔ (future) test. Proves every
requirement is specified and has an acceptance scenario. **All 26 REQs are `covered`** — the eight
formerly-PENDING rows were finalised after CL-P11-1..4 were adjudicated (spec §10, grounded in the
Researcher report). Tests are authored later by AGT-04 (logic/data) / AGT-06 (ui, acceptance).

| REQ-ID | Layer | Traces (S-id / primitive / article) | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P11-DATA-001 | data | S6, S7, Art XI, ROADMAP P11 | acceptance.md · "Asset catalog persistence and retrieval" | `test_asset_catalog` | DRAFTED |
| REQ-P11-DATA-002 | data | PIO-1, Art VII §1/§2, S7 | acceptance.md · "Untrusted asset metadata …" | `test_asset_catalog_validate` | DRAFTED |
| REQ-P11-DATA-003 | data | S6, ROADMAP P11, Art XI | acceptance.md · "Tagging assets" | `test_asset_tags_persist` | DRAFTED |
| REQ-P11-DATA-004 | data | S7, ROADMAP P11, Art X (P10 reuse), Art VII, Research §3/§4 | acceptance.md · "Asset version control — … revision store" | `test_asset_revision_store` | COVERED (CL-1) |
| REQ-P11-DATA-005 | data | S6, ROADMAP P11, Art VII, Research §4 | acceptance.md · "Cross-project reuse — CAS + reference-not-copy" | `test_cas_reference_reuse` | COVERED (CL-2) |
| REQ-P11-DATA-006 | data | S7, Art I, P10 `data/cloud/`, Research §4.2/§6 | acceptance.md · "Asset-library storage substrate — local-first …" | `test_storage_substrate` | COVERED (CL-3) |
| REQ-P11-DATA-007 | data | PIO-1, DOC-1, Art I, Art VII | acceptance.md · "Asset catalog …" (round-trip) | `test_asset_pixproj_roundtrip` | DRAFTED |
| REQ-P11-LOGIC-001 | logic | P2, S11, Art I, Art X | acceptance.md · "Asset catalog …" | `test_asset_descriptor` | DRAFTED |
| REQ-P11-LOGIC-002 | logic | P2, S11, HIS-1, Art I | acceptance.md · "Tagging assets" (reversible) | `test_tag_ops_reversible` | DRAFTED |
| REQ-P11-LOGIC-003 | logic | P2, S11, ROADMAP P11 | acceptance.md · "Search and filter …" | `test_catalog_query` | DRAFTED |
| REQ-P11-LOGIC-004 | logic | P2, S11, Art I, ROADMAP P11 | acceptance.md · "Dependency graph is queryable" | `test_dependency_graph` | DRAFTED |
| REQ-P11-LOGIC-005 | logic | P2, S11, ROADMAP P11, Research §2, Art VI | acceptance.md · "Break detection — passive flag …" | `test_break_detection` | COVERED (CL-4) |
| REQ-P11-LOGIC-006 | logic | P2, S11, Art X, P10 REQ-P10-LOGIC-003, Research §3 | acceptance.md · "Asset version control — … DAG" | `test_asset_version_model` | COVERED (CL-1) |
| REQ-P11-LOGIC-007 | logic | Art II, Art VII, S12 | acceptance.md · "Bounded numerics …" | `test_constants` | DRAFTED |
| REQ-P11-LOGIC-008 | logic | Art VI, S1, S12 | acceptance.md · "… batch posture" | `test_asset_ops_offloop` | DRAFTED |
| REQ-P11-UI-001 | ui | REQ-P11-DATA-001, LOGIC-001, S6, Art V | acceptance.md · "Library panel reflects the catalog" | `test_asset_library_panel` | DRAFTED |
| REQ-P11-UI-002 | ui | REQ-P11-DATA-003, LOGIC-002, Art V | acceptance.md · "Tagging assets" | `test_tagging_ui` | DRAFTED |
| REQ-P11-UI-003 | ui | REQ-P11-LOGIC-003, Art V | acceptance.md · "Search and filter …" | `test_search_filter_ui` | DRAFTED |
| REQ-P11-UI-004 | ui | REQ-P11-DATA-004, LOGIC-006, Art V | acceptance.md · "Version browser restores a revision append-only" | `test_version_browser` | COVERED (CL-1) |
| REQ-P11-UI-005 | ui | REQ-P11-LOGIC-004, S6, Art V | acceptance.md · "Dependency-graph view renders …" | `test_dependency_graph_view` | DRAFTED |
| REQ-P11-UI-006 | ui | REQ-P11-LOGIC-005, UI-005, Art V | acceptance.md · "The UI surfaces breaks passively …" | `test_break_warning_surface` | COVERED (CL-4) |
| REQ-P11-UI-007 | ui | REQ-P11-DATA-005, Art V | acceptance.md · "Reuse UI references a shared asset without copying" | `test_cross_project_reuse_ui` | COVERED (CL-2) |
| REQ-P11-UI-008 | ui | Art V §1 | acceptance.md · "Accessibility audit passes" | `test_a11y` (a11y-audit) | DRAFTED |
| REQ-P11-UI-009 | ui | Art V §3 | acceptance.md · "Both themes render correctly" | `test_themes` | DRAFTED |
| REQ-P11-UI-010 | ui | Art V §2, F6 | acceptance.md · "All user-visible strings translatable" | `test_string_audit` | DRAFTED |
| REQ-P11-UI-011 | ui | REQ-P11-LOGIC-008, Art VI, S1 | acceptance.md · "… stays responsive" | `test_asset_ops_responsive` | DRAFTED |

## Coverage summary

- **REQs total:** 26 — DATA 7, LOGIC 8, UI 11.
- **Covered (acceptance + Gherkin + trace):** 26 / 26 — **0 pending, 0 blocked.**
- **Finalised via §10 adjudication (grounded in the Researcher report):** 8 — DATA-004 (CL-1), DATA-005 (CL-2), DATA-006 (CL-3), LOGIC-005 (CL-4), LOGIC-006 (CL-1), UI-004 (CL-1), UI-006 (CL-4), UI-007 (CL-2).
- **Every REQ** traces to a dossier S-id / shipped primitive + a constitution article + ≥1 Gherkin scenario. **No REQ is untraced or uncovered.**
- **Gate:** the matrix is **complete** — `sdd-analyze` / `sdd-plan` (AGT-01) are **UNBLOCKED**.
