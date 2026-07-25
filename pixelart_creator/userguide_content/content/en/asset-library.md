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

## What is not covered yet

The asset library ships in slices. This release delivers the **catalog, tagging and
search/filter**, plus **dependency tracking and break detection** (see
[Asset dependencies & break detection](asset-dependencies.md) — a queryable graph of how
assets reference one another, and a passive warning when changing one asset breaks another
that references it). Arriving in later slices:

- **Version history** — an append-only record of each asset's revisions, with the ability
  to inspect and restore an earlier revision.
- **Cross-project reuse** — referencing one shared asset from several projects without
  duplicating its bytes, and bundling the referenced assets on export.
