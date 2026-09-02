# Shared projects, comments, presence & real-time

The **collaboration layer** lets several people work around one cloud project. You can
**share a project** with a named set of members (each with a role), leave and resolve
**comments** on it, see **who else is present**, **co-edit in real time** with other
editors' **live cursors** on your canvas, and **branch** the artwork like source code.
Everything here builds on the [cloud layer](cloud-and-collaboration.md) — a shared
project is still a `.pixproj` stored through the same provider-agnostic cloud port.

Everything in this guide is driven from the **Cloud menu**, which carries the
collaboration dock panels and the real-time controls below the version-history entry:

- **Cloud → Shared Projects** — share the current project and manage its members.
- **Cloud → Comments** — add, thread, and resolve comments.
- **Cloud → Presence** — see who is present and announce yourself.
- **Cloud → Start Real-time… / Stop Real-time** — join or leave a live co-editing session.
- **Cloud → Show Live Cursors** — toggle other editors' live cursors on your canvas.
- **Cloud → Branching** — open the branch / switch / merge panel.

Each dock entry toggles the matching panel on or off, so you can arrange them alongside the
layer, timeline, and other workflow docks.

> **One provider-agnostic port — no lock-in.** Just like single-user cloud saves,
> collaboration never talks to a specific provider directly. Sharing, membership, comments,
> and presence all go through the **same provider-agnostic interface** (the *cloud port*
> family), so the app behaves identically regardless of which provider backs it.

## Sharing a project and managing the member roster

Sharing a project is done from the **Shared Projects** panel. Open it with **Cloud →
Shared Projects**.

### Creating (sharing) a project

1. In the **Shared-project name** field, type the name your shared project will be keyed
   under (for example `team-sprite`). Reuse the same name later to keep working on the same
   shared project.
2. Build the **roster to share** using the add-member row:
    - Type a **member id** (the collaborator's identifier) in the *Member id to invite*
      field.
    - Pick a **role** from the role selector — **Owner**, **Editor**, or **Viewer**.
    - Click **Add Member**. The member appears in the editable *Roster to share* list with
      their role.
3. Repeat step 2 for each collaborator. To drop someone before sharing, select the row and
   click **Remove**.
4. When the roster is ready, click **Share / Update**. The project is shared with exactly
   that roster, and the committed members appear in the read-only *Current members* list
   below.

> **Roles.** A role is a provider-agnostic permission marker attached to each member:
> **Owner** — full control of the shared project; **Editor** — can edit the artwork and
> comment; **Viewer** — can view and comment. Roles are stored with the membership and
> shown in both the editable roster and the current-members list.

> **The member cap.** A shared project may have at most **32** members. The panel refuses
> to add a member past that cap with a clear message, and the storage layer enforces the
> same limit as a second line of defence. Duplicate member ids are also refused.

### Updating the roster

To change who is on a shared project, adjust the editable roster (add or remove members)
and click **Share / Update** again. Re-sharing **replaces** the roster with the current
draft — there is no separate "add one member" step, so make sure the draft lists everyone
who should have access before you commit it.

### Opening a shared project

Enter an existing shared-project name and share it (or re-share it with the same roster) to
make it the **active shared project**. The Comments and Presence panels always operate on
the active shared project, so opening one here wires all three panels to the same project
at once.

## Adding and viewing comments

Comments live on the active shared project. Open the thread with **Cloud → Comments**.

### Reading the thread

The comment view is a **threaded tree** with three columns:

- **Author** — the member id that wrote the comment.
- **Comment** — the comment text.
- **Status** — **Open** or **Resolved**.

Replies are nested under the comment they answer, so a discussion reads as an indented
thread.

### Adding a comment

1. Enter **your member id** in the *Your member id* field (this is recorded as the
   comment's author).
2. Type your comment in the text box at the bottom. A live **byte counter** shows how much
   of the per-comment budget you have used (for example `18 / 4096 bytes`).
3. *(Optional)* To reply to an existing comment, select it in the thread and enable
   **Reply to selected** — your new comment will be threaded beneath it.
4. Click **Add Comment**. The comment appears in the thread (nested under its parent if it
   was a reply) with status **Open**.

### Resolving a comment

Select a comment in the thread and click **Resolve**. Its status changes to **Resolved**.
Resolving is a one-way mark that a comment has been dealt with; the comment stays in the
thread for the record.

> **Comment limits.** Two limits apply, both enforced at the panel edge with feedback and
> re-checked by the storage layer: **Comment size** — a single comment may be at most
> **4096 bytes** (measured on the **UTF-8 byte length**, so accented or non-Latin text
> counts its real byte cost); and **Comment count** — a shared project may hold at most
> **1024** comments.

> **Comments are validated, never executed.** Comment text is treated as **untrusted
> input**: it is schema- and size-checked before it is stored and is **never** evaluated or
> executed as code. A malformed or oversized payload is rejected with a clear error, never
> a crash.

## Seeing who is present

The **Presence** panel shows a live roster of *who is currently present* in the active
shared project. Open it with **Cloud → Presence**.

1. Enter **your member id** in the presence field.
2. Click **Join** to announce yourself as present. Your id appears in the *Present members*
   list.
3. Click **Leave** to clear your presence when you step away.

> **Presence is ephemeral.** Presence is **never saved into the project file** or its
> collaboration state — it is a live, in-memory signal of who is around right now. Closing
> a shared project or leaving clears your presence.

> **Presence roster vs. live cursors.** The Presence panel shows the **presence roster** —
> the list of who is present. Drawing other collaborators' **live cursors and selections**
> on your canvas is a separate feature — see *Real-time co-editing* below.

## How concurrent edits converge

When several members edit a shared project, their changes are reconciled by a
**deterministic hybrid convergence model**, so everyone ends up with the **same** project
regardless of the order edits arrive in:

- **Structured metadata** — the layer tree, layer attributes (name, opacity, visibility,
  lock), and per-frame layer order — converges through a **sequence / tree CRDT**.
- **Raster pixels** converge through **per-tile last-writer-wins**: the canvas is split
  into 64-pixel tiles, and concurrent edits to *different* tiles both survive, while
  concurrent edits to the *same* tile resolve by a deterministic logical-clock + site-id
  tiebreak.

The outcome is **deterministic**: given the same set of edits, every participant converges
to a byte-identical project — the merge reads no wall clock, randomness, or locale. This is
the **batch** reconciliation model; applying edits **live** as they happen is the real-time
path described next.

## Real-time co-editing

Real-time co-editing applies each participant's edits to **every** peer's canvas as they
happen, converging with the same deterministic model as the batch merge above. Edits travel
through a dedicated **real-time sync backend** (see the operator note at the end).

### Starting or joining a session

1. Open the document you want to co-edit (a shared project or any open tab).
2. Choose **Cloud → Start Real-time…**.
3. Enter **your member id** when prompted — this is how peers see you (and it labels your
   live cursor). The app joins the document's real-time relay.
4. When you connect, the **Show Live Cursors** overlay is switched on automatically.

Everyone who starts real-time on the **same document** joins the same session. If a shared
project is open, the session is keyed to that shared project so the whole team converges on
one document; otherwise it is keyed to your local document.

To leave, choose **Cloud → Stop Real-time**. You can reconnect at any time; leaving clears
the live cursors.

> **Late joiners catch up automatically.** The sync backend **persists** each document's
> stream of edits, so a collaborator who joins after editing has started **replays the
> backlog** and arrives at the same converged document as everyone else.

> **Real-time stays responsive.** Inbound edits are received on a background worker and
> applied to the live document on the UI thread, repainting **only the tiles that changed**
> (a dirty-rect redraw). A single incoming edit costs the size of that edit, not the whole
> canvas, so co-editing stays smooth even at the 8K canvas size.

> **Untrusted by construction.** Every inbound edit and cursor payload is **schema- and
> size-validated** before it is applied and is **never** executed as code. A malformed or
> oversized message is rejected with a status-bar notice, never a crash.

### Live cursors and selection

While real-time is connected, **Cloud → Show Live Cursors** toggles an overlay that draws
other editors' cursors and selections on your canvas, each labelled with the peer's member
id.

- Cursors are **ephemeral** — they are a live signal only and are **never** written into
  the `.pixproj` or into the project's saved state.
- Toggle the overlay off any time to declutter; your own editing is unaffected.

## Art branching

Branching lets you fork the current project into an independent line of edits, work on it
without disturbing the mainline, and **merge** it back with **no manual conflict
resolution** — the same CRDT/last-writer-wins model that powers convergence merges the two
lines automatically. Open the panel with **Cloud → Branching**.

### Creating a branch

1. With a project open, click **New Branch** in the Branching panel.
2. Enter a **branch name** (for example `experiment`). The branch is forked from the
   current document and appears in the branch list; **mainline** is always present.

### Switching branches

Select a branch in the list and click **Switch**. The selected branch's document is loaded
into the active tab, so you edit that branch's independent copy. Switching to **mainline**
returns to the trunk.

### Reviewing before you merge

Select a feature branch and click **Open Diff** — a separate affordance from **Merge**,
enabled under the same conditions. It opens a **modeless, read-only** diff dialog that
computes the divergence between the branch and mainline once, when it opens, and lists
the **Affected regions** — every changed area, reported at a fixed pixel-tile
granularity so even a one-pixel edit shows as a full tile — plus a supervision warning
when one applies. The dialog performs no merge itself; from it you choose **Continue to
merge** (which runs the same merge described below) or **Close** to go back without
merging.

### Merging a branch

Select a feature branch and click **Merge**. Its edits are merged into **mainline**
conflict-free, the merged document is loaded into the active tab, and the panel shows a
**merge outcome** line summarising what happened (for example *"Merged branch 'experiment'
(12 edits) into mainline"*).

> **Merges never ask you to resolve a conflict.** Because the underlying model is
> commutative and deterministic, a merge always succeeds and always produces the same
> result regardless of the order edits were made — there is no manual conflict-resolution
> step. Branching is session state and is **not** an undo step on the undo stack.
> **Open Diff** is optional — you can merge directly without reviewing the diff first.

<!-- split-with: docs/site/pages/en/usage/hosting.md (that page extracts and expands this section's deployment detail; this section stays the bundle's single mention) -->

## Operator note: running the sync backend

Real-time co-editing needs a **sync backend** — a small, separate service that relays and
persists edits between collaborators. It is **not** part of the desktop app's three-layer
core; it lives in its own top-level `sync_backend/` package and talks to clients only over
the real-time transport.

- The backend imports **no** UI, data, or Qt code, and it **never** receives or stores your
  cloud provider tokens — those stay in the desktop client's keyring.
- For local development and the automated test suite, the backend is started **in-process
  on an ephemeral loopback port**, so the full client ↔ backend loop runs over `127.0.0.1`
  with no external network and no accounts.
- Running the backend as a standalone, network-reachable service for a distributed team is a
  **deployment concern** (host, port, and process management), separate from the desktop
  app.

Connecting a real cloud provider is covered in the
[cloud guide](cloud-and-collaboration.md).
