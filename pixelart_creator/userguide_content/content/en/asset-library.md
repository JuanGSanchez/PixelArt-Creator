# The asset library: browse, tag & search

The **asset library** is a studio-level catalog of your reusable assets — sprites,
animations, tilesets, tilemaps and palettes — in one place. Register the entities you
have already made as **named assets**, organise them with free-form **tags**, and find
the right one fast with **search and filter**. The library and its three panels are
reached from the **Library** menu.

> **What an asset is.** An asset is a **catalog entry** that *references* one of the
> entities you have already authored — it does not make a second copy of your artwork.
> Each entry carries a **stable id**, a **kind** (sprite, animation, tileset, tilemap or
> palette), a display **name**, its **tags**, and a little metadata. The entry points at
> the entity's canonical saved form (the same `.pixproj` payload the rest of the app
> uses) — the library adds no new save format for the artwork itself.

## Opening the library

The **Library** menu holds three dock toggles, each showing or hiding one panel:

| Menu entry | Panel | What it is for |
| --- | --- | --- |
| **Asset Library** | the catalog list | Browse every asset by name, kind and tags. |
| **Asset Search** | the search / filter controls | Narrow the list by name, tag and/or kind. |
| **Asset Tagging** | the tag editor | Add and remove tags on the selected asset. |

Each entry is a normal dock toggle (consistent with the app's other workflow panels), so
you can arrange the three panels however suits you. The panels share **one** in-memory
catalog, so a change made in one panel is reflected immediately in the others.

## Registering an asset

Before anything shows up in the catalog, it has to be **registered**. Three places in
the app start a registration, and all three end at the same shared **Register Asset**
prompt:

- **Register Active Document**, in the **Library** menu, registers the document open in
  the active tab. Registering the same document again later appends a new revision to its
  existing catalog entry instead of creating a duplicate — see
  [Asset versioning & cross-project reuse](asset-versioning.md).
- **Register Selection**, also in the **Library** menu, registers only the pixels inside
  your current selection. For a non-rectangular selection, everything outside the selected
  pixels is transparent in the registered asset. With nothing selected, there is nothing to
  register.
- **Also add to the asset library**, a checkbox on the export dialog (see
  [Export & pipeline integration](export-and-pipeline.md)), registers the exported artifact
  in the same step as exporting it.

All three open the same **Register Asset** dialog, which asks for:

| Field | What it asks |
| --- | --- |
| **Name** | A display name for the new catalog entry. |
| **Kind** | One of the five asset kinds — Sprite, Animation, Tileset, Tilemap, Palette. |
| **Tags** | An optional, comma-separated set of tags, checked against the same length and count caps as the tagging panel below. |

The dialog validates as you type: an empty name, or a tag set over the length/count caps,
disables the **Register** button with a clear reason shown until you fix it. Cancelling the
dialog registers nothing.

## Moving one asset in or out

Two further **Library** menu commands move a single artifact file, as distinct from a whole
project:

- **Export Asset** exports the currently selected catalog entry — or, with nothing
  selected, every entry in the open catalog — as one importable artifact file.
- **Import Asset** reads such an artifact back into the open library, merging it into the
  catalog.

These are separate from **Export Project Bundle** / **Import Project Bundle**, which move a
whole project plus everything it references — see
[Asset versioning & cross-project reuse](asset-versioning.md).

## Browsing the catalog

The **Asset Library** panel lists the catalog in three columns — **name**, **kind** and
**tags**. It always shows exactly what the catalog holds: adding, removing or tagging an
asset updates the list straight away. Selecting a row picks that asset, which is what the
**Asset Tagging** panel then edits.

- The list is driven entirely by the shared catalog; the panel itself does no filtering
  or ordering of its own.
- When the **Asset Search** panel has an active query, the library list shows only the
  matching entries (see below); clearing the query restores the full list.

## Tagging assets

The **Asset Tagging** panel edits the tags of the asset selected in the library. Type a
tag and add it; select a tag and remove it. Tags are free-form labels — for example
`hero`, `enemy`, or `tileset-a` — that let you organise assets by meaning.

- **Tag edits are undoable.** Adding or removing a tag is a single step on the shared
  undo stack, so **Undo** restores the exact prior tag set and **Redo** re-applies the
  edit — the same undo/redo you use everywhere else (see
  [Getting started & the workspace](app-basics.md)).
- **Adding a tag that is already present does nothing** (it is a no-op), and removing a
  tag that is not there is likewise harmless.
- **Tags are bounded.** A single tag has a maximum length, and each asset has a maximum
  number of tags. A tag that is too long, or one that would push the asset over its tag
  limit, is **rejected with a clear message** and is not added — nothing is silently
  truncated.

## Searching & filtering

The **Asset Search** panel narrows the library list with three controls that work
together:

| Control | Matches on |
| --- | --- |
| **Name** | Assets whose name *contains* the text you type (a substring match). |
| **Tags** | Assets carrying the tag(s) you enter (comma-separated for more than one). |
| **Kind** | Assets of the chosen kind; an **All kinds** entry clears the kind filter. |

- The three filters **intersect** — a result must match the name *and* the tags *and* the
  kind you set. Leave a control empty to ignore that dimension.
- **Results are stable and deterministic:** the same catalog and the same query always
  produce the same list in the same order.
- **Clearing every control restores the full catalog**, in its normal order.

> **Find by meaning, not by file.** Because assets are tagged and searchable, you can pull
> up "every `enemy` sprite" or "the tilesets tagged `dungeon`" without hunting through
> folders. Give assets a small, consistent tag vocabulary and the filters do the rest.

## How assets are stored

Behind the panels, the library keeps a **catalog** of asset entries and a
**content-addressable store** for their bytes:

- **Stored once, by content.** Each asset's bytes are stored keyed by the *content*
  itself, so registering the same content twice does not duplicate it — identical bytes
  are kept only once (**de-duplication**).
- **Referenced by a stable id, not a path.** An asset is identified by a stable id that
  travels with it, so **moving or renaming** the underlying file does **not** break the
  catalog entry.
- **The artwork keeps its normal save format.** The catalog reuses the existing
  `.pixproj` project format for the payload and stores only references and metadata
  alongside it — there is no second format for your artwork to worry about.
- **Loading is defensive.** A catalog or its metadata is treated as untrusted input on
  load: it is size- and shape-checked, never executes anything, and every referenced path
  is confirmed to stay inside the library — a malformed or out-of-bounds catalog is
  rejected with a clear error rather than crashing or corrupting anything.

## The rest of the asset library

The asset library was delivered in slices; the whole milestone now ships. Beyond the
catalog, tagging and search/filter above:

- **[Asset dependencies & break detection](asset-dependencies.md)** — a queryable graph of
  how assets reference one another (`sprite -> animation -> tileset -> tilemap`) and a
  passive warning when changing one asset breaks another that references it.
- **[Asset versioning & cross-project reuse](asset-versioning.md)** — an append-only
  revision history per asset (inspect and restore), reference-not-copy reuse of a shared
  asset across projects, export/import of a project's referenced assets as a self-contained
  bundle, and optional cloud backing of the shared blobs.
