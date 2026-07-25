# Traceability Matrix — Phase 14: `phase-14-ai-assistant`

REQ-ID ↔ dossier `S-id` / principle / article / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) (`acceptance.md`) ↔ **landed** test id(s).

**Mode:** POST-IMPLEMENTATION — **COMPLETE & LANDED** (all six slices 14A–14F shipped; synced by AGT-01 at
the T14-X01 final analyze gate, 2026-07-08). **24 REQs**: `REQ-P14-LOGIC-001..008` (8) +
`REQ-P14-DATA-001..008` (8) + `REQ-P14-UI-001..008` (8). Every REQ has **≥1 acceptance scenario in
`acceptance.md`** AND **≥1 landed test** (was `pending` at `specify`; now flipped to the shipped test id).
**No `uncovered`/`pending` rows remain.** Live-provider adapter scenarios (SC-D004-2, SC-D005-2) landed as
`@pytest.mark.assistant_live` smoke tests, **deselected in the default gate** (`-m "not assistant_live"`,
mirrors `cloud_live`).

> **Test-layout note (editorial drift resolved):** the forward matrix predicted per-concern test modules
> (`test_tool_schema.py`, `test_tiered_safety.py`, `test_credential_gating.py`, a `tests/data/llm/`
> subdir, separate `tests/ui/test_provider_config.py` etc.). The shipped suite consolidated them: the
> 14A tool contract into `tests/logic/test_tool_catalog.py`; the 14C loop/gate/injection/bounds into
> `tests/logic/test_assistant_loop.py` (+ value types & no-eval audit in `tests/logic/test_assistant.py`);
> the `data/llm/` tests **flat** under `tests/data/test_llm_*.py`; and the whole 14E UI surface into
> `tests/ui/test_assistant_dock.py`. Coverage is unchanged — this note records the path reality.

Status legend:
- **covered (landed)** — has ≥1 Gherkin acceptance scenario in `acceptance.md` AND ≥1 landed, passing test.

Inherited-primitive keys: **SCR-1** = Phase-8 `logic/scripting.py` (allow-listed registry + trusted
`dispatch`); **MAC-1** = Phase-8 `logic/macro.py` (`Op`/`Macro`); **PLG-1** = Phase-8 `logic/plugins.py`
(consent-gated capability); **HIS-1** = Phase-1 `logic/history.py` (`Command`/`GroupCommand` undo stack);
**CLD-1** = Phase-10 `data/cloud/` (port + fake adapter + `token_store` + `cloud_live` extra/marker).

## Slice 14A — LOGIC — safe tool-catalog + JSON-schema introspection (`logic/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-LOGIC-001 | **SCR-1**, **PLG-1**, S7, S11, Article I, Article XI | §2 (14A), §4, §10.1 (D1) | SC-L001-1, SC-L001-2 | `tests/logic/test_tool_catalog.py` (`test_catalog_has_one_descriptor_per_registered_op`, `test_catalog_tracks_registered_plugin_op`, `test_catalog_reflects_unregistration`) | covered (landed) |
| REQ-P14-LOGIC-002 | **SCR-1** (`ParamSchema`), S11, Article I, Article XI, Researcher `ad2616c7` | §2 (14A), §4 | SC-L002-1 | `tests/logic/test_tool_catalog.py` (`test_projection_is_never_wider_than_validate`, `test_projection_required_and_additional_properties_match_paramschema`, `test_projection_*_type_*`, `test_projection_fails_loud_on_unmappable_type`) | covered (landed) |
| REQ-P14-LOGIC-003 *(invariant: whitelist)* | **SCR-1** (dispatch allow-list + atomicity), **MAC-1**, Article VII, Article I, S11, Researcher `ad2616c7` | §2 (14A), §4, §5, §10.2 | SC-L003-1, SC-L003-2, SC-L003-3 | `tests/logic/test_tool_catalog.py` (`test_execute_unknown_op_raises_scripterror_and_leaves_document_identical`, `test_execute_*_raises_and_leaves_document_identical`, `test_regression_rejected_tool_call_is_atomic_bytes_identical`, `test_execute_valid_tool_call_applies_as_one_undoable_group`) | covered (landed) |

## Slice 14C — LOGIC — agentic conversation loop + tiered-safety enforcement (`logic/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-LOGIC-004 *(invariant: tiered-safety)* | **HIS-1**, **SCR-1**, Article VII, Article I, S11, D3, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.1 (D3) | SC-L004-1, SC-L004-2, SC-L004-3 | `tests/logic/test_assistant_loop.py` (`test_classify_whitelisted_ops_are_reversible`, `test_classify_unknown_op_defaults_destructive`, `test_reversible_tool_call_auto_runs_without_confirm`, `test_destructive_tool_call_denied_by_default_is_not_executed`, `test_destructive_tool_call_runs_when_approved`, `test_regression_gate_defaults_closed_when_no_confirm_supplied`) | covered (landed) |
| REQ-P14-LOGIC-005 | **SCR-1**, **HIS-1** (Command revert), S7, S11, Article I, Article VI (batch), Article II, D1, Researcher `ad2616c7` | §2 (14C), §4, §5 | SC-L005-1, SC-L005-2, **SC-L005-3** | `tests/logic/test_assistant_loop.py` (`test_run_turn_terminates_on_final_message`, `test_run_turn_multi_step_sequence_of_tool_turns`, `test_assistant_session_maintains_state_across_turns`; **turn-atomicity: `test_mid_turn_llm_error_after_apply_wraps_and_exposes_applied_commands`, `test_mid_turn_error_exposes_all_applied_commands_property`, `test_bound_breach_after_apply_annotates_applied_commands`, `test_no_apply_llm_error_propagates_raw_unwrapped`, `test_session_conversation_not_advanced_after_mid_turn_error`**) | covered (landed) |
| REQ-P14-LOGIC-006 *(invariant: injection)* | Article VII, Article II, **SCR-1**, **CLD-1** (`cloud_validation`-style caps), S13, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.2 | SC-L006-1, SC-L006-2, SC-L006-3 | `tests/logic/test_assistant_loop.py` (`test_malicious_result_cannot_execute_non_whitelisted_op`, `test_unknown_tool_from_model_rejected_document_byte_identical`, `test_narration_content_is_inert_data_and_executes_nothing`, `test_bound_tool_result_truncates_oversized_ascii`, `test_bound_tool_result_is_always_within_cap`, `test_tool_result_messages_in_transcript_are_bounded`) | covered (landed) |
| REQ-P14-LOGIC-007 | Article II, Article VII, S12 | §2 (14C), §4, §5, §10.2 | SC-L007-1 | `tests/logic/test_assistant_loop.py` (`test_exceeding_tool_calls_per_turn_raises_and_applies_nothing`, `test_max_tool_calls_per_turn_exactly_is_allowed`, `test_exceeding_assistant_turn_budget_raises`, `test_exceeding_conversation_message_budget_raises` — caps read from `logic/constants.py`, no literals) | covered (landed) |
| REQ-P14-LOGIC-008 *(invariant: no-eval/exec)* | Article VII, **SCR-1** (ADR-0021/0022), S11, S13, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.2 | SC-L008-1 | static source audit landed in **three** modules: `tests/logic/test_assistant.py::test_assistant_module_contains_no_eval_or_exec`, `tests/logic/test_assistant_loop.py::test_assistant_loop_has_no_eval_exec_compile_import_call`, `tests/logic/test_tool_catalog.py::test_tool_catalog_has_no_eval_exec_compile_import_call` | covered (landed) |

## Slice 14B — DATA — model-agnostic LLM port + fake adapter + credential gating (`data/llm/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-001 | **CLD-1** (`data/cloud/port.py`), S7, S11, Article I, Article XI, D4, Researcher `ad2616c7` | §2 (14B), §4, §10.1 (D4) | SC-D001-1 | `tests/data/test_llm_port.py` (provider-neutral chat/function-calling `LLMPort`; no provider/HTTP/credential type; Qt-free) + `tests/logic/test_assistant.py` (`Role`/`Message`/`Conversation`/`AssistantReply` value types + `ChatBackend` Protocol structurally satisfied) | covered (landed) |
| REQ-P14-DATA-002 *(invariant: credential-gating)* | **CLD-1** (fake in CI), S13, Article IV, S11, D5, Researcher `ad2616c7` | §2 (14B), §4, §5, §10.1 (D5) | SC-D002-1 | `tests/data/test_llm_fake_adapter.py` (whole contract driven with no key/network; deterministic scripted responses; OpenAI+Anthropic shape emulation) | covered (landed) |
| REQ-P14-DATA-003 *(invariant: credential-gating)* | **CLD-1** (`token_store.py` + `cloud_live` extra/marker), Article VII (no secrets), S11, Article I, D5 | §2 (14B), §4, §5, §10.1 (D5) | SC-D003-1, SC-D003-2 | `tests/data/test_llm_token_store.py` (`test_keyring_import_is_lazy_not_module_level`, `test_llm_subpackage_import_did_not_pull_in_keyring_at_module_level`, `test_store_load_delete_raise_when_keyring_absent`, `test_key_never_appears_in_logs_stdout_or_repr`) | covered (landed) |

## Slice 14D — DATA — real generic provider adapter (`data/llm/`, credential-gated/out-of-CI)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-004 | **CLD-1**, S8 (no new hard dep), Article I, D4, Researcher `ad2616c7` | §2 (14D), §4 | SC-D004-1, SC-D004-2 *(@out-of-ci)* | `tests/data/test_llm_openai_compatible.py` (stdlib/`urllib` only; no new hard dep; same port; not-configured degrades) + `tests/data/test_llm_http.py` (shared transport) + `test_llm_openai_compatible.py::test_live_openai_smoke` **[assistant_live, deselected]** | covered (landed) |
| REQ-P14-DATA-005 *(invariant: model-agnostic)* | **CLD-1**, S8, Article I, Article XI, D4, Researcher `ad2616c7` | §2 (14D), §4, §5 | SC-D005-1, SC-D005-2 *(@out-of-ci)* | `tests/data/test_llm_adapter_parity.py` (`test_*_parity_across_providers`, `test_parity_property_across_all_three`, `test_equivalent_scripts_run_turn_identically_regardless_of_shape`) + `tests/data/test_llm_anthropic_translator.py` (native-Anthropic same port) + `test_llm_anthropic_translator.py::test_live_anthropic_smoke` **[assistant_live, deselected]** | covered (landed) |
| REQ-P14-DATA-006 *(invariant: credential-gating)* | Article VII (no secrets), Article IV, **CLD-1** (`cloud_live` posture), D4/D5, S13 | §2 (14D), §4, §5, §10.2 | SC-D006-1, SC-D006-2 | `tests/data/test_llm_token_store.py` (key only in keyring, never in `.pixproj`/logs) + `tests/data/test_llm_openai_compatible.py` / `test_llm_anthropic_translator.py` (not-configured degrades cleanly via the `_base.py` lazy-key posture) | covered (landed) |
| REQ-P14-DATA-007 | Article I, S11, **CLD-1** | §2 (14D), §4, §5, §10.2 | SC-D007-1 | `tests/data/test_llm_port.py` + `tests/data/test_llm_http.py` (no `urllib`/`json`/provider type leaks above the port) + `check_layering`/`check_cycles` exit 0 on all five roots (`data/llm` Qt-free, `data→logic` only) | covered (landed) |

## Slice 14F — DATA — headless `pixelart-assistant` CLI (`data/`, Qt-free)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-008 *(invariant: tiered-safety in CLI)* | **CLD-1**, `pixelart-run` precedent, S11, Article I, Article IV, D2, Article VII | §2 (14F), §4, §10.1 (D2) | SC-D008-1, SC-D008-2 | `tests/data/test_assistant_cli.py` (`test_reversible_auto_applies_and_saves`, `test_destructive_default_deny_leaves_document_byte_identical`, `test_destructive_runs_with_approve_flag`, `test_interactive_prompt_yes_approves`, `test_destructive_default_deny_invariant`, `test_error_path_after_partial_apply_does_not_save`) — loop over `.pixproj`, Qt-free, saved back; destructive never auto-runs; fake adapter in CI | covered (landed) |

## Slice 14E — UI — chat dock + provider/key config + tiered-confirm + docs (`ui/`; only Qt)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Landed test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-UI-001 | REQ-P14-LOGIC-005, S7, Article V, D2 | §2 (14E), §4, §10.1 (D2) | SC-UI-001-1 `[light][dark]` | `tests/ui/test_assistant_dock.py` (`test_dock_send_drives_loop_and_renders_transcript`, `test_dock_surfaces_turn_error_not_swallowed`, `test_main_window_wraps_turn_edits_in_one_assistant_command`, `test_main_window_chat_only_turn_pushes_no_command`) | covered (landed) |
| REQ-P14-UI-002 *(invariant: no secrets)* | REQ-P14-DATA-003, -006, Article VII, Article V | §2 (14E), §4, §5 | SC-UI-002-1 `[light][dark]` | `tests/ui/test_assistant_dock.py` (`test_config_key_to_keyring_never_in_settings_or_repr`, `test_config_saves_non_secret_without_a_key`, `test_build_backend_is_provider_agnostic`, `test_dock_degrades_gracefully_when_not_configured`) | covered (landed) |
| REQ-P14-UI-003 *(invariant: tiered-safety)* | REQ-P14-LOGIC-004, Article V, Article VII, D3 | §2 (14E), §4, §5, §10.1 (D3) | SC-UI-003-1 `[light][dark]` | `tests/ui/test_assistant_dock.py` (`test_reversible_op_auto_runs_without_dialog`, `test_destructive_op_confirm_approve_executes`, `test_destructive_op_deny_or_dismiss_not_executed`, `test_dock_never_relaxes_the_gate_for_an_unregistered_op`, `test_mid_turn_error_reverts_and_records_no_undo_step`) | covered (landed) |
| REQ-P14-UI-004 (NFR) | REQ-P14-LOGIC-005, S7, Article VI | §2 (14E), §4, §5 | SC-UI-004-1 | `tests/ui/test_assistant_dock.py` (`test_dock_close_shuts_down_the_worker`, `test_main_window_shutdown_drains_assistant_controller` — loop runs off the GUI thread on the window-owned `QThreadPool` via `ui/assistant_worker.py`) | covered (landed) |
| REQ-P14-UI-005 (NFR) | Article V §1 | §2 (14E), §4, §5 | SC-UI-005-1 `[light][dark]` | `tests/ui/test_assistant_dock.py` (`test_dock_accessible_names_present`, `test_config_dialog_accessible_names_present`, `test_dock_keyboard_send_drives_a_turn`) | covered (landed) |
| REQ-P14-UI-006 (NFR) | Article V §3 | §2 (14E), §4, §5 | SC-UI-006-1 (+ every UI scenario `[light]`/`[dark]`) | `tests/ui/test_assistant_dock.py::test_dock_and_dialog_render_in_current_theme` (parametrized `[light][dark]`, role-based colours) | covered (landed) |
| REQ-P14-UI-007 (NFR) | Article V §2, F6 | §2 (14E), §4, §5 | SC-UI-007-1 | `tests/ui/test_assistant_dock.py::test_dock_retranslates_without_crash` (tr()-wrapped + `changeEvent`); AGT-07 `string_audit_check` clean over `ui/assistant_*` | covered (landed) |
| REQ-P14-UI-008 | Article V, `logic/guide_model.py` (`REQUIRED_AREAS`), docs precedent, standing docs rule | §2 (14E), §4 | SC-UI-008-1, SC-UI-008-2 | `tests/logic/test_guide_model.py` (`REQUIRED_AREAS` still 12) + `tests/data/test_guide_content.py` (`test_real_bundle_loads_and_builds`, `test_read_content_of_real_bundle_returns_markdown`) — shipped `userguide_content/manifest.json` has **12 sections**, `ai-assistant` topic **under** `automation-and-scripting`; `content/en/ai-assistant.md` authored (AGT-08) + README launch surface | covered (landed) |

## Coverage summary

- **24 / 24 REQs** have ≥1 acceptance scenario (`acceptance.md`) AND ≥1 landed test → **0 uncovered, 0 pending**.
- **Tests: all LANDED** (was `pending` in forward mode). Logic/data headless via the fake `LLMPort`; UI both
  themes. Live-provider tests (`SC-D004-2`, `SC-D005-2`) landed as `@pytest.mark.assistant_live` smoke tests,
  **deselected in the default gate** (`-m "not assistant_live"`; also self-skip without a real key/endpoint).
- **Six mandated security/agentic invariants — all covered by landed tests:**
  - tiered-safety boundary → REQ-P14-LOGIC-004 (`test_assistant_loop.py`), REQ-P14-UI-003
    (`test_assistant_dock.py`), REQ-P14-DATA-008 (`test_assistant_cli.py`);
  - whitelist enforcement (doc byte-unchanged) → REQ-P14-LOGIC-003 (`test_tool_catalog.py`),
    REQ-P14-LOGIC-006 (`test_malicious_result_cannot_execute_non_whitelisted_op`);
  - prompt-injection resistance → REQ-P14-LOGIC-006 (`test_assistant_loop.py`);
  - credential-gating (fake adapter in CI, keys never in `.pixproj`/logs) → REQ-P14-DATA-002/-003/-006
    (`test_llm_fake_adapter.py`, `test_llm_token_store.py`);
  - model-agnostic (one port, OpenAI-compatible + Anthropic via the fake) → REQ-P14-DATA-005
    (`test_llm_adapter_parity.py`);
  - zero `eval`/`exec` source audit → REQ-P14-LOGIC-008 (three-module static audit).
- **NEW turn-atomicity (SC-L005-3):** landed under REQ-P14-LOGIC-005 — `AssistantError.applied_commands`
  exposes the ordered applied commands, non-`AssistantError` cause wrapped with `__cause__` preserved,
  revert → byte-identical (`test_mid_turn_llm_error_after_apply_wraps_and_exposes_applied_commands` et al.).
- **Gap list: EMPTY.** No REQ lacks a scenario or a landed test; no duplicate/collision REQ-IDs; no dangling
  reference.
- **Deterministic Article-I evidence:** `check_layering --root pixelart_creator` clean (194 modules) exit 0;
  `--root .` clean (5) exit 0; `check_cycles --root {pixelart_creator, sync_backend, web_viewer}` no cycles
  exit 0 (196 / 3 / 9). All five roots green (2026-07-08 Phase-14 final gate).
