# Automation & extensibility

The **automation system** lets you record, script, replay and batch the editor's
own operations, generate content procedurally, and extend the app with trusted
plugins — all through **one** engine that the GUI and the headless
`pixelart-run` command line share, so an automation runs **identically** whether
you trigger it from a panel or from a build script.

!!! note "Security by design — no `eval`, ever"
    Scripting is a **bounded, data-driven command DSL**, not arbitrary Python. An
    automation is a *validated list of operations* (`{name, params, seed}`), never
    a language: there is **no `eval` / `exec` / `compile` / `__import__` of your
    input anywhere** on this path — there is no interpreter to escape (constitution
    Article VII, satisfied by construction). A single trusted dispatcher checks
    each operation's name against an **allow-list** and its parameters against a
    declared schema before building the reversible command it maps to.

## Macros — record, replay, and the `.pixmacro` format

The **macro panel** records the operations you perform and replays them later:

- **Record** captures the *inputs* of each step — the resolved parameters and, for
  any random step, the **seed** — not a pixel diff. What you record is what a
  replay re-runs.
- **Replay** re-applies the recorded operations to the current document as **one
  undo step**, so undo backs out the whole macro at once.

A macro is stored as a **`.pixmacro`** file — plain JSON with a versioned
envelope:

```json
{
  "format": "pixmacro",
  "schema_version": "1",
  "min_app_version": "0.8.0",
  "api_version": "1",
  "ops": [
    { "op": "batch_recolour", "params": { }, "seed": null },
    { "op": "procgen",        "params": { }, "seed": 12345 }
  ]
}
```

- **`schema_version` / `api_version` / `min_app_version`** are checked on load: an
  unknown or unsupported version **fails loudly** with a clear error rather than
  mis-replaying against an incompatibly-changed operation.
- **`params`** are JSON-native (numbers, strings, booleans, `null`, lists, nested
  objects), so saving then loading a macro yields an **identical** macro — colours
  and index maps travel as lists (`[[r, g, b, a], …]` / `[[src, dst], …]`).
- **`seed`** is recorded for every stochastic step so replay is reproducible.

!!! note "Deterministic replay"
    Replaying the same macro on the same starting document twice yields a
    **state-identical** document. Every random step draws only from its recorded
    seed — there is no wall clock, no unseeded randomness, no locale dependence,
    and no order-unstable iteration. This is what makes a macro safe to run in a
    build pipeline.

Loading a `.pixmacro` is **defensive**: every field is type-, bounds- and
version-checked (the same posture as loading a `.pixproj`), a malformed or
out-of-bounds document raises a clear error, and the content is **never** passed
to `eval`/`exec`.

## Running scripts

The **script runner** dispatches a list of operations through the same trusted
dispatcher a macro replay uses. A script run is **atomic**:

1. **Every operation is validated up front** — all op-names are checked against the
   allow-list and all parameters against their schema **before anything is
   applied**.
2. The whole run is applied as **one grouped, reversible command**.
3. If any operation fails partway through, the already-applied operations are
   **rolled back in reverse order**, so a failed multi-operation run leaves the
   document **unchanged** — never half-applied.

Because the run is one grouped command, a completed script is a **single undo
step**.

## Plugins — the manager, consent, and the trust model

The **plugin manager** discovers, enables and disables plugins. Plugins extend the
editor by registering new DSL operations — and only that.

- **Discovery is inert.** Installed plugins are *found* (via standard Python entry
  points) but **nothing is loaded or run** just because it is installed. You see
  them listed; they do nothing until you act.
- **Deny by default, with explicit consent.** Enabling a plugin hands it a
  **capability object whose only surface is the DSL command registry**. A plugin
  cannot `eval`/`exec`, cannot reach the UI, and cannot touch the filesystem or
  network outside the capabilities you grant it — **every capability it did not
  declare and you did not grant is denied**. Its operations are namespaced under
  the plugin, so a plugin cannot shadow a built-in operation.
- **Disable is clean.** Disabling a plugin unregisters the operations it added.

!!! warning "Trusted-with-consent, this release"
    Because *loading* a Python plugin is itself running code, the in-process
    capability model is **advisory-strength** — adequate for **trusted extensions
    you install and consent to**, not for arbitrary code from an untrusted
    marketplace. Full OS-level isolation of untrusted third-party plugins is
    **deferred** to a later phase (constitution Article XI). Only install plugins
    you trust.

## Batch recolour

**Batch recolour** applies one colour remap across **many targets at once** as a
**single transactional, reversible command**:

- For **indexed** targets it remaps palette indices (`old_index → new_index`); for
  **RGBA** targets it remaps colours (`old_rgba → new_rgba`). It reuses the
  editor's existing recolour operations, so a batched target is **byte-identical**
  to recolouring that target on its own with the same mapping.
- It is **transactional**: every target is validated and its per-target step is
  built **before anything is applied**. An invalid target (a mode mismatch or an
  out-of-range mapping) fails naming the offending target with **zero mutation** —
  a bad target never corrupts the others. The whole batch is **one undo step**.

## Procedural generation

The **procgen panel** fills a region with generated content. Five in-house,
**seeded** generators are available:

| Generator | What it produces |
| --- | --- |
| **Value noise** | Seeded value-grid noise. |
| **Gradient noise** | Perlin-style gradient noise. |
| **OpenSimplex** | A patent-safe simplex-grid gradient noise. |
| **Cellular** | Cellular-automata patterns. |
| **Dithered gradient** | A smooth two-colour gradient dithered onto the document palette (using the shipped ordered / Floyd–Steinberg dithering), so the result stays within the palette. |

Every generator is a **pure, deterministic function of its parameters and seed** —
the same seed and parameters always produce the same output (randomness is drawn
only from the seed, never the wall clock). Generated content is written through
the **reversible-command path**, so any generation is a single undo step. Output is
bounded per axis by the platform's procgen dimension ceiling.

## Reversibility and responsiveness

Every automation — a macro replay, a script run, a batch recolour, a procedural
fill — goes onto the **normal undo stack as one step**, so you can back any of them
out. In the GUI, automation runs on a **background worker thread** with
deterministic teardown, so a long batch or a large procedural fill does not freeze
the window.

## The `pixelart-run` command line

For automation and CI, `pixelart-run` replays a `.pixmacro` over a `.pixproj`
**headlessly** (no GUI) through the **exact same** trusted dispatcher the GUI
drives — so the resulting document is **state-identical** to the GUI running the
same automation on the same input. It loads both the project and the macro through
the same defensive, validated loaders the app uses.

```
pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj [options]
```

| Flag | Meaning |
| --- | --- |
| `--input PATH` | **(required)** the source `.pixproj` project to run the macro over. |
| `--macro PATH` | **(required)** the `.pixmacro` macro to replay. |
| `--output PATH` | **(required)** the `.pixproj` path to write the result to. |
| `--seed N` | override the seed for operations that recorded none (a recorded seed always wins, so replay stays deterministic). |
| `--param KEY=VALUE` | inject or override a macro parameter; repeatable. A numeric value is parsed as an integer, otherwise it is kept as a string. |

**Exit codes:** `0` success; `1` an automation failure (a script / macro / plugin /
batch / procgen error, or a write failure); `2` bad arguments or a malformed /
unreadable input project or macro.

!!! tip "Same path as the GUI"
    Because the CLI and the GUI drive the same dispatcher, you can record a macro
    interactively and then replay it exactly in a build script — the output is
    state-identical.

!!! note "Console entry point"
    `pixelart-run` is installed as a console script on `pip install`.

## What is not covered

- **Arbitrary Python scripting** — **not supported by design.** Scripting is a
  bounded, allow-listed command DSL, not a general-purpose interpreter; this is a
  deliberate security boundary (Article VII), not a limitation to be lifted.
- **Untrusted third-party plugin isolation** — **deferred.** Plugins are
  trusted-with-consent for this release; OS-level sandboxing of untrusted
  marketplace plugins is a later-phase follow-up (Article XI). Install only plugins
  you trust.
