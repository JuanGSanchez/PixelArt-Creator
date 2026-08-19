# Asset version control & cross-project reuse

The asset library keeps an **append-only version history** for each asset, lets you
**reuse one shared asset across several projects without duplicating its bytes**,
**export and import** the assets a project references as a self-contained bundle, and —
when you connect a cloud provider — **back the shared blobs in the cloud** while still
working fully offline. These are reached from the **&Library** menu, alongside the
[asset library](asset-library.md) and [dependency](dependency-graph.md) panels they build
on.

!!! note "Reference, not copy"
    Everything here rests on one idea already used by the library: an asset's bytes are
    stored **once**, keyed by their content, in a content-addressable store, and a project
    holds only a **reference** (a stable id plus the content hash it expects). Versioning,
    reuse and export all move references and verify content — they never make a second copy
    of your artwork.

## Version history

Every time you record a new state of an asset, the library appends a **revision** to that
asset's history:

- **Append-only and immutable.** A revision is never changed or deleted in place. Recording
  a new state adds a new revision at the head; the earlier revisions stay exactly as they
  were, so the history is a faithful record of how the asset evolved.
- **Addressed by content.** Each revision is identified by the **content hash** of its
  bytes and linked to the revision it followed, so the history forms a content-addressed
  chain. Two revisions with identical bytes share one stored blob (de-duplication).
- **Recording the same content twice does nothing.** If you record content whose hash
  matches the current head, it is a **no-op** — no new revision and no new blob are added.
  This is the same "did this asset actually change?" test the library uses elsewhere.
- **Bounded.** An asset keeps up to a fixed maximum number of revisions; exceeding it is
  reported with a clear error rather than silently dropping history.

### Browsing and restoring revisions

The **Asset Version Browser** lists the selected asset's revisions in order. Select one to
**inspect** it, or **restore** a prior revision to make it current again.

!!! tip "Restore adds a new revision — it never rewrites history"
    Restoring an earlier revision does **not** delete the revisions that came after it.
    Instead, the browser re-records the chosen revision's (content-hash-verified) bytes as a
    **new head** revision. The history only ever grows, so you can always step back again —
    restoring is itself an undoable, recoverable step in the record.

When you restore, the browser also verifies the revision's bytes against the hash the record
expects; a blob that no longer matches its recorded hash is **rejected with a clear error**
(tamper / corruption defence) rather than being loaded.

## Cross-project reuse (reference, don't copy)

The **Asset Reuse** panel lets you **reference an existing shared asset into another
project**. Because the library references assets rather than copying them, reuse costs
nothing in storage:

- **Referencing copies no bytes.** Adding a shared asset to a project records the
  reference (its stable id and expected content hash); the shared bytes continue to live
  **once** in the content-addressable store. The stored-blob count is **unchanged** by
  referencing.
- **Shared assets are marked.** When more than one project references the same asset, the
  panel shows it as **Shared**, so you can see at a glance which assets are used in several
  places (and think twice before changing one).
- **Presence is checked, never written.** Before it references a shared asset, the panel
  confirms the shared bytes are actually present; if they are missing it reports a clear
  error instead of creating a dangling reference. It only reads — it never writes a new copy.

!!! note "Why this is safe"
    Reuse and the [dependency graph](dependency-graph.md) work together: a reused asset is a
    reference like any other, so the passive break indicator will flag a reuse whose target
    later goes missing or changes — you keep the benefit of single-copy sharing without
    losing track of what depends on what.

## Export & import a project's assets

**Export** bundles exactly the assets a project references into a **self-contained,
portable artifact** so the project opens complete on another machine; **import** brings such
a bundle back in.

- **Exactly the referenced assets — no more, no fewer.** Export resolves the project's
  reference set and bundles precisely those assets' blobs, each stored once by content, plus
  a catalog index and per-asset sidecars. Nothing the project does not reference is included,
  and nothing it does reference is left out.
- **Reuses the shipped project format.** The bundle composes the existing catalog and
  `.pixproj` machinery — there is no new format to learn, and the bundle inherits the app's
  normal, defensive load path.
- **Import is defensive.** A bundle is treated as **untrusted input** on import: it is
  parsed without executing anything, size- and shape-checked, and **every path is confirmed
  to stay inside the bundle** (path-traversal defence). Each blob is **content-hash
  verified** as it is read, so a tampered or corrupt bundle is rejected with a clear error
  rather than loaded.

## Optional cloud backing

By default the library stores every blob **locally** and works **fully offline**. If you
connect a cloud provider (see [Cloud, versions & recovery](cloud.md)), the library can also
**back the shared blobs in the cloud** — without changing anything about how you use it:

- **Local-first.** When no provider is connected, the library is purely local; the cloud is
  engaged **only when a provider is connected**. Nothing about versioning, reuse or export
  requires the cloud.
- **The same storage interface.** Cloud backing is just another blob backend behind the same
  interface the local store uses, so the catalog, revisions and reuse behave identically
  whether the backing is local or shared — they never learn a provider is involved.
- **Cloud data is verified and cached.** A blob fetched from the cloud is
  **content-hash verified** before it is used (the cloud is untrusted input, exactly like a
  local file), and then cached locally so later reads stay offline.
- **No provider detail leaks.** No provider name, credential or SDK type appears in the
  library — the cloud backing depends only on the same provider-agnostic cloud interface the
  rest of the app uses.

## Accessibility, themes & language

Every control on the version browser and the reuse panel has an accessible name and is
reachable from the keyboard, all labels are fully translatable, and both panels render
correctly in the light and dark themes.

## Phase 11 complete

With version control, cross-project reuse, export/import and optional cloud backing, the
**team & asset-management** milestone is fully delivered: catalog, tags and search
([asset library](asset-library.md)); the dependency graph and passive break detection
([asset dependencies](dependency-graph.md)); and the versioning, reuse and portability
covered here.
