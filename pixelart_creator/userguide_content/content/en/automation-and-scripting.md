# Automation, macros, scripting & plugins

The **automation system** lets you record, script, replay and batch the editor's own
operations, and generate content procedurally — all
through **one** engine that the GUI and the headless `pixelart-run` command line share, so
an automation runs **identically** whether you trigger it from a panel or from a build
script.

> **Security by design — no `eval`, ever.** Scripting is a **bounded, data-driven command
> DSL**, not arbitrary Python. An automation is a *validated list of operations*
> (`{name, params, seed}`), never a language: there is **no `eval` / `exec` / `compile` /
> `__import__` of your input anywhere** on this path — there is no interpreter to escape.
> A single trusted dispatcher checks each operation's name against an **allow-list** and
> its parameters against a declared schema before building the reversible command it maps
> to.

## Macros — record, replay, and the `.pixmacro` format

The **Macros** panel records the operations you perform and replays them later:

- **Record** captures the *inputs* of each step — the resolved parameters and, for any
  random step, the **seed** — not a pixel diff. What you record is what a replay re-runs.
- **Replay** re-applies the recorded operations to the current document as **one undo
  step**, so undo backs out the whole macro at once.

A macro is stored as a **`.pixmacro`** file — plain JSON with a versioned envelope:

```
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

- **`schema_version` / `api_version` / `min_app_version`** are checked on load: an unknown
  or unsupported version **fails loudly** with a clear error rather than mis-replaying.
- **`params`** are JSON-native, so saving then loading a macro yields an **identical**
  macro — colours and index maps travel as lists.
- **`seed`** is recorded for every stochastic step so replay is reproducible.

> **Deterministic replay.** Replaying the same macro on the same starting document twice
> yields a **state-identical** document. Every random step draws only from its recorded
> seed — no wall clock, no unseeded randomness, no locale dependence. This is what makes a
> macro safe to run in a build pipeline.

Loading a `.pixmacro` is **defensive**: every field is type-, bounds- and version-checked,
a malformed or out-of-bounds document raises a clear error, and the content is **never**
passed to `eval`/`exec`.

## Running scripts

The **Script Runner** dispatches a list of operations through the same trusted dispatcher
a macro replay uses. A script run is **atomic**:

1. **Every operation is validated up front** — all op-names are checked against the
   allow-list and all parameters against their schema **before anything is applied**.
2. The whole run is applied as **one grouped, reversible command**.
3. If any operation fails partway through, the already-applied operations are **rolled
   back in reverse order**, so a failed multi-operation run leaves the document
   **unchanged** — never half-applied.

Because the run is one grouped command, a completed script is a **single undo step**.

## Plugins — the manager, consent, and the trust model

The **Plugins** panel lists plugins, shows the permissions of each plugin whose manifest
you have loaded, and enables and disables them. A plugin is meant to extend the editor by
registering new DSL operations. **In this release the app has no step that loads or runs a
plugin's code:** discovering a plugin, loading a manifest, enabling and disabling
never call a plugin. The permissions a manifest declares describe the plugin's intended use;
they are not a limit on what the plugin's own code can do (see the note below).

- **Discovery only lists plugins.** The app finds installed plugins through standard Python entry
  points, but it reads only their names and versions: it does **not** load or run their
  code. A discovered plugin shows no permissions and cannot be enabled, because the app
  does not read permissions from the plugin itself. They come from a manifest file that
  you add to the panel from disk, which appears as its own entry in the list. The app
  does not check that a manifest belongs to a plugin you have installed.
- **Consent covers the manifest, not the plugin's code.** **Enable** shows the permissions the
  manifest declares and asks you to confirm. You approve them as a whole, or you do not
  enable the plugin. The app does not check the manifest against what the plugin's code
  actually does. Enabling records the permissions you approved, in memory, and marks the
  plugin as enabled; it does not run the plugin's code, because the app has no step
  that does. Your consent is not saved: every plugin is disabled again when you close the
  editor. The plugin host is written so that, if a caller gave it code to run when a plugin
  is enabled, that code would be handed a permission object, and a call through that object
  that was not granted would be refused; nothing in this release gives it any such code. Operations
  registered through that object get the plugin's name as a prefix, so they cannot match
  the name of a built-in operation, and a read permission through it returns the
  document it is passed, not a copy. Code that does not go through the object is not limited by
  it: it can register or remove operations directly, built-in ones included.
- **Disable removes operations, not the plugin's code.** **Disable** unregisters the operations
  that were registered through the permission object; in this release there are none,
  because nothing registers any. It does not undo anything a plugin's own code has
  already done.

> **Plugins are not sandboxed.** A plugin is not isolated from your computer, and the app
> provides no isolation for any plugin in this release. Installing a plugin puts someone
> else's Python code on your computer, and the app neither performs nor checks the
> installation. A package can also ask Python to run code each time Python starts in the
> environment where the package is installed, which includes the editor, so installing a plugin can
> be enough for its code to run, even if you never open the **Plugins** panel. Code that
> runs in the editor's own process, however it got there, has the same access to your
> files and network as the editor itself, whatever permissions the plugin declared.
> Install and enable only plugins you trust.

## Batch recolour

**Batch recolour** applies one colour remap across **many targets at once** as a **single
transactional, reversible command**:

- For **indexed** targets it remaps palette indices (`old_index → new_index`); for
  **RGBA** targets it remaps colours (`old_rgba → new_rgba`). It reuses the editor's
  existing recolour operations, so a batched target is **byte-identical** to recolouring
  that target on its own with the same mapping.
- It is **transactional**: every target is validated and its per-target step is built
  **before anything is applied**. An invalid target fails naming the offending target with
  **zero mutation**. The whole batch is **one undo step**.

## Procedural generation

The **Procedural Generation** panel fills a region with generated content. Five in-house, **seeded**
generators are available:

| Generator | What it produces |
| --- | --- |
| **Value noise** | Seeded value-grid noise. |
| **Gradient noise** | Perlin-style gradient noise. |
| **OpenSimplex noise** | A patent-safe simplex-grid gradient noise. |
| **Cellular automata** | Cellular-automata patterns. |
| **Dithered gradient** | A smooth two-colour gradient dithered onto the document palette, so the result stays within the palette. |

Every generator is a **pure, deterministic function of its parameters and seed** — the
same seed and parameters always produce the same output. Generated content is written
through the **reversible-command path**, so any generation is a single undo step. Output
is bounded per axis by the platform's procgen dimension ceiling.

## Reversibility and responsiveness

Every automation — a macro replay, a script run, a batch recolour, a procedural fill —
goes onto the **normal undo stack as one step**, so you can back any of them out. In the
GUI, automation runs on a **background worker thread** with deterministic teardown, so a
long batch or a large procedural fill does not freeze the window.

## The `pixelart-run` command line

For automation and CI, `pixelart-run` replays a `.pixmacro` over a `.pixproj` **headlessly**
(no GUI) through the **exact same** trusted dispatcher the GUI drives — so the resulting
document is **state-identical** to the GUI running the same automation on the same input.

```
pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj [options]
```

| Flag | Meaning |
| --- | --- |
| `--input PATH` | **(required)** the source `.pixproj` project to run the macro over. |
| `--macro PATH` | **(required)** the `.pixmacro` macro to replay. |
| `--output PATH` | **(required)** the `.pixproj` path to write the result to. |
| `--seed N` | override the seed for operations that recorded none (a recorded seed always wins). |
| `--param KEY=VALUE` | inject or override a macro parameter; repeatable. |

**Exit codes:** `0` success; `1` an automation failure (a script / macro / batch
/ procgen error, or a write failure); `2` bad arguments or a malformed / unreadable input
project or macro.

> **Console entry point.** `pixelart-run` is installed as a console script on
> `pip install`.

## What is not covered

- **Arbitrary Python scripting** — **not supported by design.** Scripting is a bounded,
  allow-listed command DSL, not a general-purpose interpreter; this is a deliberate
  security boundary, not a limitation to be lifted.
- **Untrusted third-party plugin isolation** — **deferred.** Plugins are not
  sandboxed in this release; install and enable only plugins you trust.

## Related topics

- Automations compose the same operations you drive by hand — see
  [layers](layers.md), [export](export-and-pipeline.md), and the
  [colour hub](colour-hub.md).
