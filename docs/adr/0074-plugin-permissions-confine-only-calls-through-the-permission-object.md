# ADR-0074 — Plugin permissions confine only calls through the permission object: ADR-0021's plugin-confinement statements are withdrawn

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-11-15 |
| Author | Architecture |
| Feature | Six more interface languages — the plugin consent prompt and the guide's plugin passage (`REQ-L10N-UI-016`, `REQ-L10N-DATA-006`) |
| Grounded by | `REQ-L10N-UI-016` (the consent prompt states truthfully what enabling a plugin does); `REQ-L10N-DATA-006` (the guide's plugin-safety passage states truthfully what a plugin can do); the guide passage `pixelart_creator/userguide_content/content/en/automation-and-scripting.md`, section "Plugins — the manager, consent, and the trust model" (SHA-256 below); the test modules `testing/suites/logic/test_plugin_host_facts.py` and `testing/suites/ui/test_plugin_consent_prompt.py` (cases named below); public issue #85 (the plugin "sandboxed" claim) |
| Supersedes | ADR-0021, **in part**: the six statements quoted under Decision, and nothing else. ADR-0021's scripting surface, its no-`eval`/`exec` invariant and the rest of its plugin model **stand unchanged** (listed under "What stays in force"). |
| Superseded by | — |
| Relates to | ADR-0021 (the record corrected), ADR-0022 (atomic dispatch, cited by ADR-0021), ADR-0073 (this release's placement record) |

## Context

ADR-0021 (2026-07-04) chose the automation and scripting security model: a data-driven command
DSL with no `eval`/`exec`, and a trusted-with-consent plugin model. Its research grounding said,
correctly, that loading a Python plugin is code execution and that in-process confinement is
advisory at best.

Several of its plugin statements say more than that. They describe a plugin as confined to a
permission object — able to do only what it was granted, unable to reach the file system, the
network or the interface outside its grants, and inert until enabled. The code on this branch does
not behave that way, and this release's requirements now bind two user-facing texts to the facts:

- `REQ-L10N-UI-016` requires the consent prompt shown by **Enable** to state truthfully what
  enabling a plugin does — in particular, no claim that the plugin runs sandboxed or isolated or
  cannot reach the interface, file system or network, and no claim that enabling runs its code.
- `REQ-L10N-DATA-006` requires the guide's plugin passage to state truthfully what a plugin can
  do.

Both texts were corrected against the code and the tests named below. A decision record in the
same repository that states the opposite would contradict them in public; public issue #85
already names the plugin "sandboxed" claim. Decision records are immutable, so the correction
is this new record, and ADR-0021 changes only in its Status and Superseded-by rows.

**The passage this record cites.** The section of
`pixelart_creator/userguide_content/content/en/automation-and-scripting.md` from the line
`## Plugins — the manager, consent, and the trust model` up to, and not including, the line
`## Batch recolour` — the bytes of those lines joined by LF, plus one final LF (the blank line
before the next heading included). Measured on 2026-11-15: **3,304 bytes, LF only, SHA-256
`724587d351ae418a3521e8c3a64597afbcbcebc18f0ec50239fbcace1fc28f14`**. Quotations below marked
"passage" are from those bytes.

## Decision

**We withdraw the six statements of ADR-0021 quoted below, and record in their place that a
plugin's permissions are checked only on calls made through the permission object, that a
plugin's own code is not limited by them and is not isolated, and that in this release the app
has no step that loads or runs a plugin's code.**

Each withdrawn statement is quoted exactly as ADR-0021 has it, followed by what is true and the
evidence for it. "Route 1" below is a call made through the permission object; "route 2" is a
call made directly to the app's command registry, without the object.

### W1 — ADR-0021, Decision (the summary paragraph)

> "whose plugins may only register/invoke DSL commands (they cannot reach `eval`/`exec`, `ui/`,
> the filesystem/network outside grants, or the reversible-command path)"

**True instead.** The permissions confine route 1 only. A plugin's own code runs in the editor's
process and thread, with the editor's access, whatever it was granted; and it can register,
remove and dispatch operations through the registry directly.

- Passage: "The permissions a manifest declares describe the plugin's intended use; they are not
  a limit on what the plugin's own code can do"; "Code that runs in the editor's own process,
  however it got there, has the same access to your files and network as the editor itself,
  whatever permissions the plugin declared."
- Cases: `test_read_only_plugin_runs_in_this_process_and_writes_a_file`,
  `test_file_access_does_not_depend_on_the_permissions_granted`,
  `test_plugin_code_can_open_a_network_socket`,
  `test_code_that_skips_the_object_registers_with_nothing_granted`,
  `test_code_that_skips_the_object_can_remove_a_built_in`,
  `test_code_that_skips_the_object_dispatches_with_nothing_granted`.
- **Not tested separately:** no case has a plugin call `eval`/`exec` or import `ui/`. Those two
  parts of the parenthesis are withdrawn because they rest on the same premise — that a plugin's
  code is confined to the permission object — which the cases above show is false for file
  access, the network and the registry.

### W2 — ADR-0021, Plugin trust model, third bullet

> "A plugin's **only API surface** is the DSL command registry: it receives a **capability
> object** exposing *only* the command-registration/dispatch API and its granted resources. It
> **registers command factories**; it does not gain raw mutation access, cannot `import` `ui/`,
> and cannot touch the filesystem/network outside its grants (REQ-P8-LOGIC-009)."

**True instead.** The permission object is the only surface the *object* offers, but it is not
the plugin's only surface (W1). In this release no plugin receives the object at all: the host
hands it only to an activation step that a caller supplies to `enable`, and the one caller of
`enable` in the product supplies none.

- Passage: "The plugin host is written so that, if a caller gave it code to run when a plugin is
  enabled, that code would be handed a permission object, and a call through that object that
  was not granted would be refused; nothing in this release gives it any such code."
- Cases: `test_a_supplied_activation_step_is_the_only_way_plugin_code_runs`,
  `test_only_the_manager_panel_calls_enable_and_passes_no_activation_step`,
  `test_enable_and_disable_without_an_activation_step_run_nothing`; for "cannot touch the
  filesystem/network outside its grants", the W1 cases.
- "does not gain raw mutation access" is withdrawn on the passage: "a read permission through
  it returns the document it is passed, not a copy." This record names no test case for that
  sentence.

### W3 — ADR-0021, Plugin trust model, fourth bullet (one clause)

> "no silent bypass"

(in: "any capability a plugin did not declare and was not granted is denied with a domain error
— no silent bypass, no partial-then-corrupt state (REQ-P8-LOGIC-010)")

**True instead.** Denial by default holds on route 1; route 2 bypasses it, and nothing refuses or
reports the bypass.

- Route 1 holds: `test_object_with_nothing_granted_refuses_every_operation`,
  `test_operation_allowed_only_with_its_own_permission`,
  `test_same_dispatch_through_the_object_with_nothing_granted_is_refused` (the same dispatch as
  the route-2 case, refused through the object, document unchanged).
- Route 2 bypasses: the three `test_code_that_skips_the_object_…` cases under W1. Controls showing
  the registry does refuse what it checks (names, not grants):
  `test_direct_registration_of_an_existing_name_is_refused`,
  `test_direct_dispatch_of_an_unregistered_name_is_refused`.
- Passage: "Code that does not go through the object is not limited by it: it can register or
  remove operations directly, built-in ones included."

The rest of that sentence — denial with a domain error, and no partial state on a refused call
through the object — **stands** (`test_refused_registration_leaves_the_registry_unchanged`,
`test_ungranted_call_inside_the_activation_step_fails_the_enable`).

### W4 — ADR-0021, Plugin trust model, fourth bullet (the no-auto-run sentence)

> "**No auto-run**: a discovered plugin is inert until the user explicitly enables it (the
> Blender "off-by-default auto-exec" precedent)."

**True instead.** Enabling does not run a plugin's code either: in this release the app has no
step that loads or runs it. And the app's not running a plugin does not make it inert: a package
can run code whenever Python starts in the environment where it is installed.

- Passage: "**In this release the app has no step that loads or runs a plugin's code:**
  discovering a plugin, loading a manifest, enabling and disabling never call a plugin"; "A
  package can also ask Python to run code each time Python starts in the environment where the
  package is installed, which includes the editor, so installing a plugin can be enough for its
  code to run, even if you never open the **Plugins** panel."
- Cases: `test_sc_l10n_ui_016_2_clause_5_enabling_from_the_panel_runs_no_plugin_code` with its
  control `test_sc_l10n_ui_016_2_clause_5_control_loading_the_plugin_writes_the_marker`;
  `test_enable_and_disable_without_an_activation_step_run_nothing`;
  `test_product_source_has_no_step_that_loads_or_runs_plugin_code`.
- **Not tested in the suite:** code run at Python start-up by an installed package. That part
  rests on the passage alone.

### W5 — ADR-0021, Consequences, Negative / risk

> "In-process plugin isolation is advisory-strength — mitigated by default-deny + explicit
> consent + no-auto-run + the honest "trusted-only" framing"

**True instead.** There is no plugin isolation in this release, advisory or otherwise; and
default-deny and consent do not mitigate what a plugin's own code does (W1, W3). What remains as
mitigation is the trusted-only framing, which the guide and the prompt now state to the user.

- Passage: "**Plugins are not sandboxed.** A plugin is not isolated from your computer, and the
  app provides no isolation for any plugin in this release."
- Cases: `test_product_has_no_process_isolation_machinery` (controls
  `test_isolation_scan_flags_planted_machinery`, `test_isolation_scan_ignores_plain_code`),
  `test_read_only_plugin_runs_in_this_process_and_writes_a_file` (control
  `test_another_process_has_another_pid`).

### W6 — ADR-0021, Context (read as a statement of what was delivered)

> "whose plugins **cannot bypass the layer boundaries or their granted permissions**
> (REQ-P8-LOGIC-009/-010)"

This sentence records an acceptance that the phase-8 specification set; this record does not
rewrite what was required. It is withdrawn **as a description of the product**: for calls made
through the permission object it holds (W3, route 1); for a plugin's own code it does not (W1,
W3, route 2). This record does not reread the phase-8 specification or its tests; it quotes
ADR-0021's paraphrase of them only.

### What stays in force from ADR-0021, unchanged

- The scripting surface (Option A): the command registry, the trusted dispatcher, atomic
  multi-op dispatch (with ADR-0022), one `{op, params}` artifact for script, macro and command
  line, and the rejection of RestrictedPython.
- The invariant that no input is passed to `eval`, `exec` or an equivalent on any automation code
  path of the app's own code. **Not re-verified by this record**; nothing here contradicts it. It
  concerns what the app executes, not what a plugin's own code may do.
- Discovery by entry points without loading or running anything (passage: "**Discovery only lists
  plugins.**").
- Defensive manifest validation; the panel showing the declared permissions before the user
  enables a plugin (passage: "**Enable** shows the permissions the manifest declares and asks you
  to confirm").
- Deny by default **through the permission object** (W3, route 1).
- The "Honesty about strength" paragraph — with one clarification: route 2 needs no introspection;
  a plain direct call to the registry crosses the boundary (W1).
- The record of OS-level isolation as not shipped, and the Alternatives Considered table. This
  record adds no plan, date or promise about isolation.
- `MAX_PLUGINS_LOADED` — **not re-verified by this record**.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| Edit ADR-0021's body in place | Decision records are immutable; a rewritten body erases what was decided and on what grounds. ADR-0021 changes only in its Status and Superseded-by rows (the form ADR-0048 and ADR-0043 use). |
| Leave ADR-0021 as it stands and fix only the prompt and the guide | The repository would then contain one public text stating that plugins cannot reach the file system or network outside their grants and two stating the opposite; issue #85 already names the claim. |
| Supersede ADR-0021 whole | Most of it is true and in force (the DSL, the no-`eval`/`exec` invariant, discovery, validation, consent display, deny-by-default through the object). Replacing all of it would hide that only the confinement statements were false. |
| Build the confinement ADR-0021 described, so its statements become true | Out of this release's requirements: `REQ-L10N-UI-016` and `REQ-L10N-DATA-006` bind the texts to the code as built, not the code to the texts. No isolation and no loading step exist in this release, and this record does not plan either. |

## Consequences

**What the user-facing texts now say.** All three agree with the code and the cases above.

- **The guide** (the passage, SHA-256 above): the app has no step that loads or runs a plugin's
  code; the permissions are not a limit on the plugin's own code; code that does not go through
  the permission object is not limited by it; plugins are not sandboxed and not isolated;
  installing a plugin can be enough for its code to run; install and enable only plugins you
  trust.
- **The consent prompt** shown by the plugin manager panel's **Enable**, English source text:
  "Enable %1 and approve these permissions?" / "%2" / "Plugins are not isolated from your
  computer. Only enable plugins you trust. These permissions are checked only on requests made
  through the app's permission object, not on what the plugin's own code can do." It makes no
  claim of a sandbox, of isolation, of "cannot reach", or that enabling runs the plugin's code
  (`test_sc_l10n_ui_016_1_panel_source_text_is_acceptable`; the planted earlier texts fail,
  `test_sc_l10n_ui_016_1_planted_earlier_text_fails_naming_what_it_holds`).
- **The panel's behaviour**: **Enable** records the approved permissions and runs nothing
  (`test_only_the_manager_panel_calls_enable_and_passes_no_activation_step`,
  `test_sc_l10n_ui_016_2_clause_5_enabling_from_the_panel_runs_no_plugin_code`).
- Translations: `REQ-L10N-DATA-006` covers the passage in all eight languages. This record attests
  to the English texts only.

**What remains unbuilt.** No sandbox and no isolation of any kind for plugins, and no step that
loads or runs a plugin's code, in this release. The permission object and its route-1 checks exist
in the plugin host, but nothing in this release hands a plugin the object, so no plugin request is
checked in practice. This record states these as facts of the release; it records no plan to
change them.

**Accepted costs.** Two records must now be read together for the plugin model: ADR-0021 for the
DSL and the consent design, this record for what the permissions do and do not confine. A reader
who stops at ADR-0021 would be misled; its Status and Superseded-by rows point here.

**What this enables.** The decision records, the guide and the consent prompt make one consistent
statement in public, each tied to cases that fail if the code changes.

**What it constrains.** Any future text — documentation, prompt or record — describing plugin
permissions as a limit on a plugin's own code, or plugins as sandboxed, isolated, or unable to
reach the file system, network or interface, contradicts this record and the cases above. A change
that gives plugins real confinement would need a new record superseding this one, with its own
evidence.

## Compliance

- **Detectors.** `testing/suites/logic/test_plugin_host_facts.py` fails if a plugin's own code
  stops reaching the file system or network, if direct registry calls start being refused, if
  route-1 denial stops, or if any product step starts loading or running plugin code.
  `testing/suites/ui/test_plugin_consent_prompt.py` fails if the prompt's source text regains
  "sandbox", "cannot reach" or the earlier "through the app's own commands" wording, or if
  enabling from the panel runs plugin code.
- **No detector.** Nothing checks this record, or ADR-0021, against the code; a new decision
  record could reintroduce a confinement claim unnoticed. Nothing in the suite measures a package
  running code at Python start-up (W4); that statement rests on the passage. No case has a plugin
  call `eval`/`exec` or import `ui/` (W1). Recorded as accepted risk.
