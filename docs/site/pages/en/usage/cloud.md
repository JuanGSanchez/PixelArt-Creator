# Cloud: save, versions & autosave

In this release the **cloud layer** runs on a built-in, in-memory adapter, so
the version history and the autosaved copy last only until you close the app;
they do not protect you from a crash or power loss. Save a local copy of the
project for anything you want to keep. Within that limit, the cloud layer lets
you **connect**, **save** the current project, **open** it again, browse a
**version history** and **restore** an earlier save, and keep an **autosaved
working copy** while you work.

Everything in this guide is driven from the **Cloud menu** in the menu bar.

!!! note "One provider-agnostic port — no lock-in"
    The app never talks to a specific provider directly. All cloud work goes
    through **one provider-agnostic interface** (the *cloud port*): connect,
    save, open, list versions, restore, and the autosave/recovery slot. The app
    behaves **identically** regardless of which provider backs it, so you are not
    locked in, and a new provider is just a new adapter behind the same port.
    See **ADR-0026** (cloud-port design) for the architecture.

!!! success "What works in this release, and what does not connect"
    What works: the provider-agnostic port, a fully-tested built-in adapter,
    `.pixproj` cloud round-trip, version history + restore, and autosave
    (Slice A); **shared projects, comments and presence** (Slice B — see the
    [Shared projects & comments](collaboration.md) guide), which run on an
    in-memory adapter inside one app window, so another window or another
    person's copy cannot see them; and local **art branching** (Slice C). What
    does not connect: **real-time co-editing and live cursors** cannot connect,
    and the **real Google Drive / OneDrive / Dropbox providers** (Slice C) are
    implemented in the storage layer but cannot be selected from the Cloud menu.
    The providers are covered in
    [Connecting a real cloud provider](#connecting-a-real-cloud-provider) below.

## Connecting a cloud provider

Cloud actions are disabled until you connect.

1. Open the **Cloud** menu.
2. Choose **Connect…**. This connects the built-in adapter through the cloud
   port and enables the rest of the Cloud menu (**Save to Cloud…**,
   **Open from Cloud…**, **Version History…**, and **Disconnect**).
3. To sign out, choose **Cloud ▸ Disconnect**. This releases the connection and
   re-disables the cloud actions until you connect again.

!!! note "Your credentials never leave the storage layer"
    When a real provider adapter is used, the sign-in flow (OAuth) runs
    **entirely inside the storage layer** — the app only ever launches your
    system browser for you. Tokens are **never** shown to the UI, **never**
    written into a `.pixproj`, and **never** written to logs. The UI only ever
    sees a plain *connected / not connected* state.

!!! tip "The built-in adapter"
    The connection in this release is a built-in, in-memory adapter that is
    deterministic and needs no network or account — it makes the whole save /
    version workflow usable within a session. Because it lives in memory,
    everything it holds is gone when you close the app. The real online
    providers are described in
    [Connecting a real cloud provider](#connecting-a-real-cloud-provider), but
    they cannot be chosen from the Cloud menu in this release.

## Connecting a real cloud provider

The storage layer contains **real** Google Drive, OneDrive and Dropbox providers
that sit behind the **same** cloud port as the built-in adapter. When such a
provider is used, the steps in this guide (save, open, version history) work the
same way on top of your online storage. This
release has no Cloud menu command that selects one: **Connect…** connects the
built-in adapter.

!!! note "Credential-gated feature"
    The real providers are **credential-gated**: each would need an OAuth **client id**
    for the chosen service and live network access, so they are not on by
    default, and this release has no Cloud menu command that turns one on (they
    are exercised manually, outside the automated CI gate). The built-in adapter above needs none of this.

### How sign-in works

1. Using a storage-layer provider starts its sign-in. **Cloud ▸ Connect…** does
   not do this in this release: it connects the built-in adapter.
2. The sign-in opens your **system browser** to the provider's sign-in / consent page.
   PixelArt Creator uses the standard desktop **OAuth Authorization Code + PKCE over
   a loopback redirect** flow — there is **no embedded web view** and **no client
   secret** stored in the app.
3. Approve access in the browser. The browser redirects back to the app, which
   completes the connection. The Cloud menu's save/open/version actions then
   enable just as they do for the built-in adapter.
4. To sign out, choose **Cloud ▸ Disconnect**.

!!! warning "Your credentials never leave the storage layer"
    The whole sign-in runs **entirely inside the storage layer**. Your **refresh
    token is stored in the operating-system keyring** (keyed per provider); the
    short-lived access token is held in memory only and refreshed automatically.
    Tokens are **never** shown to the UI, **never** written into a `.pixproj`, and
    **never** written to logs. The rest of the app only ever
    sees a plain *connected / not connected* state.

!!! note "Same behaviour, any provider"
    Because every provider sits behind the one cloud port, saving and browsing
    versions work the same way whether the built-in adapter or Drive / OneDrive /
    Dropbox backs them. That is the no-lock-in design;
    choosing a provider from the Cloud menu is not available in this release.

## Saving a project to the cloud

1. With a project open and a provider connected, choose **Cloud ▸ Save to Cloud…**.
2. Enter a **cloud project name** when prompted. This is the key your project is
   stored under; reuse the same name to keep adding versions to the same project.
3. The app serialises the project to a `.pixproj` and stores it as a **new
   version**. When it finishes, the status bar shows *"Saved to cloud."*

Each save is transported as a whole `.pixproj` — the **same** validated,
versioned save format used for local files. The cloud layer adds no new format of
its own; it simply carries the `.pixproj` as the atomic *sync unit*.

!!! note "Saving never freezes the app"
    The serialise + upload runs **off the GUI thread**, so the window stays
    responsive even for a large (up to 8K) project — you can keep working while a
    save completes.

!!! warning "Every save is a new version"
    Saving does **not** overwrite the previous cloud save — it appends a new
    entry to the version history (see below). The history is capped at the most
    recent **100** versions per project.

## Opening a project from the cloud

1. Choose **Cloud ▸ Open from Cloud…**.
2. Enter the **cloud project name** to open.
3. The app fetches the project's latest version and opens it in a **new tab**.

Opening does **not** replace or disturb whatever you are currently working on —
the cloud project comes in as its own tab.

!!! warning "Cloud files are treated as untrusted"
    A `.pixproj` fetched from the cloud is validated defensively exactly like a
    local file: every field is type- and bounds-checked, the payload is
    size-capped, and a malformed, oversized, or unknown-version file is rejected
    with a **clear error** — never a crash and **never** by executing any code
    from the file. If a fetched project cannot be validated,
    you get a warning dialog and your current work is left intact.

## Browsing version history and restoring a version

Every save creates a new, ordered version, and you can go back to any of them.
Version history lasts for the current session only: the built-in adapter keeps
it in memory and starts empty the next time you launch the app. Save a local
copy of the project for anything you want to keep.

1. Choose **Cloud ▸ Version History…** (if you have not opened or saved a cloud
   project this session, you will be asked for the cloud project name first).
2. The **Cloud Version History** dialog lists every stored version, oldest to
   newest, with these columns:
    - **Version** — the version's ordinal / identifier.
    - **Marker** — the ordering marker for the version.
    - **Size (bytes)** — the stored `.pixproj` size.
    - **Pinned** — whether the version is pinned (kept) — *Yes* / *No*.
    - **Parent** — the version this save followed.
3. Select a version to see its details in the preview area below the list.
4. Click **Restore** (or double-click the row, or press **Enter**) to bring that
   version back.

!!! note "Restore is safe — it opens a new tab"
    Restoring a prior version fetches and validates it, then opens it in a **new
    tab**. It does **not** overwrite your current work or your latest cloud save —
    you decide what to do with the restored copy.

The version list is fetched off the GUI thread before the dialog opens, so
browsing history never freezes the app.

## Autosave and the recovery slot

While you work on a connected project, the app **autosaves** your working copy to
a dedicated **recovery slot** in the background. In this release the slot is
held in memory only, so it protects your work within the session, not across a
crash.

- Autosave runs on a fixed cadence (default **every 2 minutes**) and **only when
  the document has unsaved changes** — a clean document is never autosaved.
- The recovery slot is **separate from your version history**. Autosaving never
  creates a visible version and **never overwrites your last explicit save to the
  cloud**.
- Autosave runs off the GUI thread, so it never interrupts your drawing.

### The recovery prompt on restart

Restart recovery is not available in this release. The built-in adapter does
not keep the recovery slot across a restart, and the **Recover Unsaved Work**
prompt is checked only once, as the app starts, before you can connect. After a
crash or power loss, no prompt appears the next time you start the app. Until a
persistent provider can be selected, rely on saving a local copy of the project.

The prompt itself offers two choices (you will not see it in this release):

- **Recover** — fetches and validates the autosaved copy and opens it in a **new
  tab**. Your last explicit save is not affected.
- **Discard** — dismisses the prompt and leaves everything as it was.

!!! note "Recovery is decoded defensively too"
    The recovered copy goes through the same untrusted-input validation as any
    cloud file, so a malformed recovery slot is rejected with a clear error
    instead of being opened.

!!! tip "Autosave needs a connection"
    Autosave operates through the cloud port, so it runs only while you are
    **connected**. It protects your work within the session, not across a crash.

## The rest of the cloud & collaboration milestone

This page covers single-user cloud work — save, versions, autosave — plus the
storage-layer providers. The collaboration features, which run on their own in-memory adapter (per app
window) in this release, with real-time co-editing unable to connect, are
documented in the
[Shared projects & comments](collaboration.md) guide:

- **Shared projects & membership** — share a project with named members
  (owner / editor / viewer roles).
- **Comments** — thread and resolve comments on a shared project.
- **Presence** — see who else is currently present in a shared project.
- **Deterministic convergence** — concurrent edits merge deterministically via a
  hybrid tree-CRDT (structure) + per-tile last-writer-wins (raster) model.
- **Real-time co-editing & live cursors** — live, converging multi-user editing
  with other editors' cursors shown on your canvas (the app cannot connect to a
  real-time session in this release).
- **Art branching** — branch a project, edit independently, and merge back
  conflict-free.

The architecture behind these is recorded in **ADR-0026** (cloud-port design),
**ADR-0027** (sync-backend placement + real-time) and **ADR-0028** (hybrid
convergence model + git-like branching).
