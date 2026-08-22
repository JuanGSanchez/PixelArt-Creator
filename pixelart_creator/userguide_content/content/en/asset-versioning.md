# Asset versioning & cross-project reuse

The asset library keeps an **append-only version history** for each asset, lets you
**reuse one shared asset across several projects without duplicating its bytes**,
**export and import** the assets a project references as a self-contained bundle, and —
when you connect a cloud provider — **back the shared blobs in the cloud** while still
working fully offline. These are reached from the **Library** menu, alongside the
[asset library](asset-library.md) and [dependency](asset-dependencies.md) panels they build
on.

> **Reference, not copy.** Everything here rests on one idea already used by the library: an
> asset's bytes are stored **once**, keyed by their content, in a content-addressable store,
> and a project holds only a **reference** (a stable id plus the content hash it expects).
> Versioning, reuse and export all move references and verify content — they never make a
> second copy of your artwork.

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
- **Bounded.** An asset keeps up to a fixed maximum number of revisions; exceeding it is
  reported with a clear error rather than silently dropping history.

### Browsing and restoring revisions

The **Asset Version Browser** lists the selected asset's revisions in order. Select one to
**inspect** it, or **restore** a prior revision to make it current again.

> **Restore adds a new revision — it never rewrites history.** Restoring an earlier revision
> does **not** delete the revisions that came after it. Instead, the browser re-records the
> chosen revision's (content-hash-verified) bytes as a **new head** revision. The history
> only ever grows, so you can always step back again.

When you restore, the browser also verifies the revision's bytes against the hash the record
expects; a blob that no longer matches its recorded hash is **rejected with a clear error**
(tamper / corruption defence) rather than being loaded.

## Cross-project reuse (reference, don't copy)

The **Asset Reuse** panel lets you **reference an existing shared asset into another
project**. Because the library references assets rather than copying them, reuse costs
nothing in storage:

- **Referencing copies no bytes.** Adding a shared asset to a project records the
  reference; the shared bytes continue to live **once** in the content-addressable store.
  The stored-blob count is **unchanged** by referencing.
- **Shared assets are marked.** When more than one project references the same asset, the
  panel shows it as **Shared**, so you can see which assets are used in several places.
- **Presence is checked, never written.** Before it references a shared asset, the panel
  confirms the shared bytes are actually present; if they are missing it reports a clear
  error instead of creating a dangling reference. It only reads — it never writes a new copy.

> **Why this is safe.** Reuse and the [dependency graph](asset-dependencies.md) work
> together: a reused asset is a reference like any other, so the passive break indicator will
> flag a reuse whose target later goes missing or changes.

## When a shared asset changes

Opening a project that references a library asset which has since been edited shows the
**Library Asset Updated** prompt, once per changed asset:

- **Pick Up the Change** resolves the asset's current library content from now on; the
  project's reference moves to the library's latest revision.
- **Keep the Referenced Version** keeps resolving exactly the content the project already
  references — nothing about the reference changes.

Cancelling or closing the prompt behaves the same as **Keep the Referenced Version**.
Ticking **Don't ask again** while choosing either option remembers that choice for future
edits of this asset, in this project; you can restore the prompt later from **Edit →
Project confirmations → When a referenced library asset changes**.

## Export & import a project's assets

**Export Project Bundle** bundles exactly the assets a project references into a
**self-contained, portable artifact** so the project opens complete on another machine;
**Import Project Bundle** brings such a bundle back in. Both commands are reached from the
**Library** menu.

- **Exactly the referenced assets — no more, no fewer.** Export resolves the project's
  reference set and bundles precisely those assets' blobs, each stored once by content, plus
  a catalog index and per-asset sidecars.
- **Reuses the shipped project format.** The bundle composes the existing catalog and
  project machinery — there is no new format to learn.
- **Import is defensive.** A bundle is treated as **untrusted input**: it is parsed without
  executing anything, size- and shape-checked, and **every path is confirmed to stay inside
  the bundle** (path-traversal defence). Each blob is **content-hash verified** as it is
  read, so a tampered or corrupt bundle is rejected with a clear error.

## Optional cloud backing

By default the library stores every blob **locally** and works **fully offline**. If you
connect a cloud provider (see [Cloud, versions & recovery](cloud-and-collaboration.md)), the
library can also **back the shared blobs in the cloud** — without changing anything about how
you use it:

- **Local-first.** When no provider is connected, the library is purely local; the cloud is
  engaged **only when a provider is connected**.
- **The same storage interface.** Cloud backing is just another blob backend behind the same
  interface the local store uses, so the catalog, revisions and reuse behave identically
  whether the backing is local or shared.
- **Cloud data is verified and cached.** A blob fetched from the cloud is **content-hash
  verified** before it is used, and then cached locally so later reads stay offline.
- **No provider detail leaks.** No provider name, credential or SDK type appears in the
  library — the cloud backing depends only on the same provider-agnostic cloud interface the
  rest of the app uses.

## Accessibility, themes & language

Every control on the version browser and the reuse panel has an accessible name and is
reachable from the keyboard, all labels are fully translatable, and both panels render
correctly in the light and dark themes.
