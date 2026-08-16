# ADR-0051 — The asset store's default root is resolved in `ui/` (AppLocalDataLocation) and injected into `default_content_store()`

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-08-16 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-11-team-asset-management` — D-26, the durable app asset store (decision-batch WP-4.3) |
| Grounded by | D-26 / CF-119 (qualified `20260816-decision-batch:R-7`); REQ-P11-DATA-006 (local-first / cloud-optional storage behind an abstraction), REQ-P11-DATA-007; Article I / S11 (layer purity); the placement ruling in `design-docs/auxiliary/module-map.md`, "Placement ruling — 2026-08-16 (D-26 / WP-4.3)" |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0004 (the sibling precedent this deliberately diverges from), ADR-0030 (no new payload serialiser), ADR-0032 (local-first / cloud-optional backend swap), ADR-0038 (native installers) |

## Context

Phase 11 shipped the asset library with its store constructed bare in the UI:

```python
# pixelart_creator/ui/main_window.py:803
self._asset_content_store = ContentAddressableStore()
```

`ContentAddressableStore()` with no argument composes an **in-memory** backend, so
every asset a user registers dies with the session. That is D-26 / CF-119, and
`20260816-decision-batch:R-7` requires the filesystem CAS backend to become the app's
store with tests proving assets survive a simulated restart.

The obvious fix — make the bare constructor filesystem-backed — is not available, and
the reason is recorded in the data layer itself: many headless tests and
transient-session callers rely on that ephemeral, disk-free construction, and changing
its default would make every one of them write real files to the host filesystem as a
side effect. So the durable path is a **separate, explicit factory**,
`data/asset_cas.py::default_content_store()`, and the real question is not *whether* to
use the filesystem backend but **which root the application gives it**.

Two candidates were put to Architecture:

- **(a)** the stdlib root the data layer already computes —
  `default_asset_root()` → `~/.pixelart_creator/assets` — used as the app default;
- **(b)** a `QStandardPaths`-resolved location wired at construction in `ui/`,
  mirroring the Favourites precedent (ADR-0004).

The constraint that makes this a real question is **Article I / S11**: Qt is forbidden
everywhere below `ui/`, so `data/` cannot ask `QStandardPaths` anything. (b) is therefore
admissible *only* in the ADR-0004 shape — Qt resolves the path in `ui/`, and `data/`
receives a `pathlib.Path` whose origin it cannot tell. And ADR-0004, which established
that shape, chose a location *kind* — `AppConfigLocation` — that is wrong for this
payload, so following the precedent literally is itself a decision that has to be
justified rather than inherited.

## Decision

**We will resolve the GUI's asset-store root in `ui/` from
`QStandardPaths.writableLocation(StandardLocation.AppLocalDataLocation)`, fall back to
the stdlib `default_asset_root()` when Qt names nothing, and inject the result as a
`pathlib.Path` into the `data/` factory `default_content_store(root)` — never by
composing a backend in `ui/`.**

Concretely, and in this shape only:

1. **`AppLocalDataLocation`, not ADR-0004's `AppConfigLocation`.** This is a deliberate
   divergence from the sibling precedent, not an oversight. Favourites is a few hundred
   bytes of *preference*, and `AppConfigLocation` is right for it. The CAS is a **bulk
   blob store**, capped per blob by `MAX_BLOB_BYTES` and unbounded in total. On Windows
   `AppConfigLocation` resolves under the **roaming** profile: a blob store that
   replicates on every domain login is an operational defect, not a preference.
   `AppLocalDataLocation` is the non-roaming bulk-data home on all three shipped targets
   (`%LOCALAPPDATA%\<org>\<app>`, `~/.local/share/<org>/<app>`,
   `~/Library/Application Support/<org>/<app>`).

2. **The injection keeps `data/` Qt-free.** The factory takes a `Path` and cannot tell
   whether Qt produced it. Its signature, as shipped on this branch at `d3d235d`:

   ```python
   def default_content_store(root: Optional[Path] = None) -> ContentAddressableStore:
   ```

   defaulting to `default_asset_root()` when omitted. No Qt symbol crosses the boundary;
   S11 is preserved with no relaxation requested and none granted.

3. **The injection point is the FACTORY, not the constructor.** `ui/` must **not** write
   `ContentAddressableStore(LocalBlobBackend(path))`. That expression hard-codes into the
   presentation layer *which backend a CAS composes*, which is a `data/`-internal
   decision — and it is the precise leak that would later turn ADR-0032's local→shared
   backend swap (`asset_shared_backend`) from a `data/` change into a `ui/` edit. The
   factory is the seam that keeps that swap where ADR-0032 put it.

4. **`default_asset_root()` is the fallback, not a second root.** It is what the UI uses
   when `QStandardPaths` yields an empty string, and what any future headless caller
   gets — both branches land on the same directory when Qt cannot name one, exactly as
   `_favourites_path()` already falls back to `Path.home() / ".pixelart_creator"`. One
   authoritative location per machine; the platform's path whenever the platform can
   name it.

5. **Resolution is side-effect-free: no `mkdir`.** The `ui/` helper *computes* the path
   and stops. `LocalBlobBackend.put_blob` already creates the root on first write, so no
   directory appears until an asset is genuinely stored. (`_favourites_path()` mkdirs
   because it is about to open a JSON file for reading or writing; this is not that, and
   copying its `mkdir` would make merely launching the editor litter the disk.)

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| **(a)** `default_asset_root()` (`~/.pixelart_creator/assets`) as the app default | Two defeats. It is the wrong home on two of the three shipped targets — Phase 13 ships cross-platform and ADR-0038 ships native installers, and a dotdir directly in `C:\Users\<user>\` is neither what an installed Windows application owns nor where an uninstaller or a backup policy looks. Decisively: it would make **every UI test write into the developer's real home**. `tests/ui/conftest.py`'s autouse `_isolate_app_config` fixture monkeypatches `QStandardPaths.writableLocation` with `staticmethod(lambda *_a, **_k: str(cfg))` — i.e. it intercepts *every* location kind, not only `AppConfigLocation` — onto a per-test `tmp_path`, and ~25 modules construct a `Main_Window`. A stdlib `Path.home()` is intercepted by no fixture, so each of those tests would root a **live filesystem CAS** at the real user home. A suite that writes outside its sandbox is not a style preference. |
| **(b′)** `AppConfigLocation`, mirroring ADR-0004 exactly | Roams on Windows. Consistency with the precedent is not worth replicating a blob store across every domain login; the precedent's *shape* is followed, its *location kind* is not. |
| Composing `ContentAddressableStore(LocalBlobBackend(root))` at the `ui/` call site | Leaks a `data/`-internal composition into the presentation layer and converts ADR-0032's backend swap into a `ui/` edit — the one consequence that seam exists to prevent. |
| Changing bare `ContentAddressableStore()` to default to the filesystem | Would give every headless test and transient-session caller a real on-disk side effect. The ephemeral default is load-bearing and stays. |
| `mkdir` at resolve time, as `_favourites_path()` does | Launching the app would create an asset directory before any asset exists. Creation stays deferred to the first successful `put_blob`. |
| Recording the root in a config file / QSettings | Adds a second source of truth for a location the platform already names, and pushes persistence into Qt — the same objection ADR-0004 §4 already sustained. |

## Consequences

**Accepted costs.** The application now writes under **two different platform
directories** — Favourites in `AppConfigLocation` (ADR-0004) and assets in
`AppLocalDataLocation` — so any support answer, uninstaller manifest or "where is my
data" document must name both, and the divergence must be explained every time somebody
notices it. The rewiring is also **ordered across two agents and two layers**: the `data/`
widening must land before the `ui/` call site changes, or the UI is forced into exactly
the composition point 3 forbids. And `ui/` now imports one `data/` name purely as a
fallback, which is a coupling that has to be kept to a single expression on purpose.

**What this enables.** ADR-0032's local→shared backend swap stays a `data/`-only change,
because no `ui/` file names a backend. WP-5.1 (D-02 asset ingress) can make this store
the destination of real user content with its location already correct and user-visible.
ADR-0038's installers get a root an uninstaller can reason about. And UI tests get asset
isolation **for free**, from a fixture that already exists and already carries its
xdist-race rationale — no new fixture, no new patch target.

**What it constrains.** The following are now invariants, and each names where it is
enforced:

- Nothing in `ui/` may import `LocalBlobBackend` (point 3).
- Nothing in `ui/` may import `default_asset_root` except the single fallback expression
  inside the private `_asset_root()` helper — a second import site forks the fallback
  logic across layers (point 4).
- `pixelart_creator/data/` stays free of every Qt symbol (S11 / Article I), which is what
  makes the injection legal at all.
- The `ui/` rewiring is: add `_asset_root() -> Path` beside `_favourites_path()` in
  `ui/main_window.py` (same file, same pattern, `AppLocalDataLocation`, fallback
  `default_asset_root()`, **no `mkdir`**), then change line 803 from
  `ContentAddressableStore()` to `default_content_store(self._asset_root())`. The next
  line, `AssetRevisionStore(self._asset_content_store)`, is unchanged — it composes
  whatever CAS it is handed.
- The D-26 durability test roots its store at a `tmp_path`, never at
  `default_asset_root()`.

## Compliance

`check_layering.py` and `check_cycles.py` are the detectors for the layering half of this
decision, and they were run — not read — in the `fix-logic-contracts` worktree at tip
`d3d235d`, with the widened factory in the tree:

```
$ python scripts/check_layering.py
check_layering: clean (194 modules; 2 root module(s), 0 exempt top-level package(s), 0 unregistered).
exit 0
$ python scripts/check_cycles.py
check_cycles: no cycles (196 modules).
exit 0
```

The `ui/` rewiring adds **no new import edge** — `ui → data` already exists — so a
non-zero exit from either script after it lands means something else moved, and the
rewiring is rejected on that ground alone.

**What has no detector, stated rather than implied.** No script can tell that
`AppLocalDataLocation` was chosen over `AppConfigLocation`, that the helper avoided
`mkdir`, or that `ui/` called the factory rather than composing a backend. Points 1, 3
and 5 are enforced by review plus two grep-shaped gates a reviewer must actually run
(`LocalBlobBackend` and `default_asset_root` in `pixelart_creator/ui/`), and by the
AGT-06 assertion named below. That is accepted risk, recorded here so it is not
mistaken for coverage.

## What this record does not verify

- **The `ui/` rewiring does not exist at the time of this ADR.** At `d3d235d`,
  `ui/main_window.py:803` still constructs the bare in-memory store; only the `data/`
  factory has been widened. This record fixes the decision, not its landing.
- **The test-isolation gain is read, not measured.** The autouse fixture was read and its
  `writableLocation` patch quoted above, but no suite has been run under the new wiring.
  AGT-06 must confirm it with one assertion that the constructed store's root is under
  `tmp_path`; if that cannot be made to hold, the decision returns to AGT-01 *before* the
  rewiring lands.
- **Headless reach into the CAS is grep-inferred, not proven.** The only *production*
  construction site found is `ui/main_window.py:803` (`asset_export.py` builds
  bundle-local stores; `asset_revision_store.py` composes an injected one). If a CLI
  consumer appears, point 3 is the rule it follows.
- **The `QStandardPaths` value under an unset application/organisation identity was not
  measured.** `ui/app.py` sets both, but a `Main_Window` can be constructed without
  `create_app`; the fallback covers the empty-string case only.
- `ui/asset_library_actions.py` (WP-5.1's ingress home) was not read. This decision fixes
  the **root**; it says nothing about the ingress path.
