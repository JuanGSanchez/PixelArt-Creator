# Asset dependencies & break detection

The **dependency graph** records how your assets reference one another — a sprite is a
frame *of* an animation, a sprite is the source image *of* a tileset, a tileset is used
*by* a tilemap — and the **break indicator** passively warns you when changing one asset
would break another that points at it. Both are reached from the **&Library** menu,
alongside the [asset library](asset-library.md) panels they build on.

!!! note "What a dependency is"
    A dependency is a **directed reference** from one catalog asset to another: the
    *referencing* asset (the source) points at the *referenced* asset (the target). The
    reference also remembers the target's content at the moment it was made, so the
    library can later tell whether the target has changed. Dependencies form a **directed
    acyclic graph** — the library refuses to record a reference that would create a cycle
    (an asset cannot, directly or transitively, end up depending on itself).

## Opening the dependency graph

The **&Library** menu gains a **Dependency Graph** dock toggle. The
**Dependency Graph** view visualises the references for either the whole catalog or the
single asset currently selected in the [Asset Library](asset-library.md) panel, in two
directions:

| Relation | Reads as | Shows |
| --- | --- | --- |
| **Depends on** | what this asset *references* | the assets the selected asset points at |
| **Referenced by** | what *references* this asset | the assets that point at the selected asset |

Both relations are shown as stable, alphabetically ordered lists. By default the view
shows the **direct** neighbours; the same relations can be read transitively (the full
chain — for example every asset a tilemap ultimately draws on, through its tilesets and
their source sprites).

!!! tip "Why the graph never hangs"
    Because the stored graph is always acyclic, the view only ever lists the direct
    neighbours the model returns — it performs no recursive walk of its own. Even a
    deliberately tangled set of references cannot make the view spin: a cycle is caught
    when the reference is recorded and reported plainly, and a very deep chain is bounded
    rather than followed forever.

## The passive break indicator

When you change an asset, anything that references it may now be pointing at content that
no longer matches. The library surfaces this **passively** — it flags the problem, it
does **not** block your edit:

- **Breaks are flagged, never blocked.** You can always make the change; the indicator
  simply tells you that a reference is now broken so you can decide what to do. Nothing is
  prevented, and no modal dialog interrupts you.
- **It refreshes on catalog change.** The indicator re-evaluates whenever the catalog or
  the graph changes, so it always reflects the current state — you never have to ask it to
  recheck.
- **It is shown in place.** The Dependency Graph view shows a break summary and per-
  reference status, and the [Asset Library](asset-library.md) list carries a **Status**
  column so a broken asset is visible right where you browse.

A reference is reported broken for one of two reasons:

| Reason | Meaning |
| --- | --- |
| **Missing** | the referenced asset is no longer in the catalog (it was removed). |
| **Hash mismatch** | the referenced asset is still present, but its content has changed since the reference was made. |

An asset whose references are all still valid shows no indicator; only a genuinely broken
reference is flagged, so the warning stays meaningful (no false positives).

## Accessibility, themes & language

The Dependency Graph view's controls each have an accessible name and are reachable from
the keyboard, every label is fully translatable, and the view and the Status column render
correctly in both the light and dark themes.

## Related

Dependency tracking and break detection build on the [asset library](asset-library.md)
catalog. The companion capability — an append-only **version history** per asset, plus
**cross-project reuse**, **export/import** and **optional cloud backing** — is documented in
[Asset versioning & cross-project reuse](asset-versioning.md). A reused asset is a reference
like any other, so the break indicator described here flags a reuse whose target later goes
missing or changes.
