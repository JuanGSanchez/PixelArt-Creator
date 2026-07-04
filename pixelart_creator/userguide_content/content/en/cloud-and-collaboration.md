# Cloud: save, versions, autosave & recovery

The **cloud layer** lets a project live in the cloud instead of only on one machine. You
can **connect a cloud provider**, **save** the current project to the cloud, **open** it
again from any session, browse a full **version history** and **restore** an earlier
save, and rely on **autosave + crash recovery** so an unclean shutdown never loses your
unsaved work.

Everything in this guide is driven from the **Cloud menu** in the menu bar.

> **One provider-agnostic port — no lock-in.** The app never talks to a specific provider
> directly. All cloud work goes through **one provider-agnostic interface** (the *cloud
> port*): connect, save, open, list versions, restore, and the autosave/recovery slot.
> The app behaves **identically** regardless of which provider backs it, so you are not
> locked in, and a new provider is just a new adapter behind the same port.

The full cloud & collaboration milestone ships in this release: the provider-agnostic
port, a fully-tested built-in adapter, `.pixproj` cloud round-trip, version history +
restore, and autosave/crash recovery; **shared projects, comments and presence**; and
**real-time co-editing, live cursors and art branching** plus the **real Google Drive /
OneDrive / Dropbox providers**. Sharing, comments, presence, real-time and branching are
covered in [Shared projects, comments, presence & real-time](collaboration.md).

## Connecting a cloud provider

Cloud actions are disabled until you connect.

1. Open the **Cloud** menu.
2. Choose **Connect…**. This establishes a provider-agnostic connection through the cloud
   port and enables the rest of the Cloud menu (**Save to Cloud**, **Open from Cloud**,
   **Version History**, and **Disconnect**).
3. To sign out, choose **Cloud → Disconnect**. This releases the connection and
   re-disables the cloud actions until you connect again.

> **Your credentials never leave the storage layer.** When a real provider adapter is
> used, the sign-in flow (OAuth) runs **entirely inside the storage layer** — the app only
> ever launches your system browser for you. Tokens are **never** shown to the UI,
> **never** written into a `.pixproj`, and **never** written to logs. The UI only ever
> sees a plain *connected / not connected* state.

> **The built-in adapter.** The default connection is a built-in, in-memory adapter that
> is deterministic and needs no network or account — it exists so the whole save /
> version / recovery workflow is complete and usable end to end. To use a real online
> provider instead, see *Connecting a real cloud provider* below.

## Connecting a real cloud provider

You can connect a **real** Google Drive, OneDrive, or Dropbox account behind the **same**
Connect flow, so every step in this guide (save, open, version history, autosave/recovery)
works identically on top of your online storage.

> **Credential-gated feature.** The real providers are **credential-gated**: each needs an
> OAuth **client id** for the chosen service and live network access, so they are
> configured deliberately rather than being on by default. The built-in adapter above
> needs none of this.

### How sign-in works

1. Choose **Cloud → Connect…** and pick the real provider you configured.
2. The app opens your **system browser** to the provider's sign-in / consent page.
   PixelArt Creator uses the standard desktop **OAuth Authorization Code + PKCE over a
   loopback redirect** flow — there is **no embedded web view** and **no client secret**
   stored in the app.
3. Approve access in the browser. The browser redirects back to the app, which completes
   the connection. The Cloud menu's save/open/version actions enable just as they do for
   the built-in adapter.
4. To sign out, choose **Cloud → Disconnect**.

> **Your credentials never leave the storage layer.** The whole sign-in runs **entirely
> inside the storage layer**. Your **refresh token is stored in the operating-system
> keyring** (keyed per provider); the short-lived access token is held in memory only and
> refreshed automatically. Tokens are **never** shown to the UI, written into a
> `.pixproj`, or written to logs.

> **Same behaviour, any provider.** Because every provider sits behind the one cloud port,
> switching from the built-in adapter to Drive / OneDrive / Dropbox — or between them —
> changes **nothing** about how you save, browse versions, or recover work.

## Saving a project to the cloud

1. With a project open and a provider connected, choose **Cloud → Save to Cloud…**.
2. Enter a **cloud project name** when prompted. This is the key your project is stored
   under; reuse the same name to keep adding versions to the same project.
3. The app serialises the project to a `.pixproj` and stores it as a **new version**. When
   it finishes, the status bar shows *"Saved to cloud."*

Each save is transported as a whole `.pixproj` — the **same** validated, versioned save
format used for local files. The cloud layer adds no new format of its own; it simply
carries the `.pixproj` as the atomic *sync unit*.

> **Saving never freezes the app.** The serialise + upload runs **off the GUI thread**, so
> the window stays responsive even for a large (up to 8K) project — you can keep working
> while a save completes.

> **Every save is a new version.** Saving does **not** overwrite the previous cloud save —
> it appends a new entry to the version history. The history is capped at the most recent
> **100** versions per project.

## Opening a project from the cloud

1. Choose **Cloud → Open from Cloud…**.
2. Enter the **cloud project name** to open.
3. The app fetches the project's latest version and opens it in a **new tab**.

Opening does **not** replace or disturb whatever you are currently working on — the cloud
project comes in as its own tab.

> **Cloud files are treated as untrusted.** A `.pixproj` fetched from the cloud is
> validated defensively exactly like a local file: every field is type- and bounds-checked,
> the payload is size-capped, and a malformed, oversized, or unknown-version file is
> rejected with a **clear error** — never a crash and **never** by executing any code from
> the file. If a fetched project cannot be validated, you get a warning dialog and your
> current work is left intact.

## Browsing version history and restoring a version

Every save creates a new, ordered version, and you can go back to any of them.

1. Choose **Cloud → Version History…** (if you have not opened or saved a cloud project
   this session, you will be asked for the cloud project name first).
2. The **Cloud Version History** dialog lists every stored version, oldest to newest, with
   these columns:
    - **Version** — the version's ordinal / identifier.
    - **Marker** — the ordering marker for the version.
    - **Size (bytes)** — the stored `.pixproj` size.
    - **Pinned** — whether the version is pinned (kept) — *Yes* / *No*.
    - **Parent** — the version this save followed.
3. Select a version to see its details in the preview area below the list.
4. Click **Restore** (or double-click the row, or press **Enter**) to bring that version
   back.

> **Restore is safe — it opens a new tab.** Restoring a prior version fetches and validates
> it, then opens it in a **new tab**. It does **not** overwrite your current work or your
> latest cloud save — you decide what to do with the restored copy.

The version list is fetched off the GUI thread before the dialog opens, so browsing history
never freezes the app.

## Autosave and crash recovery

While you work on a connected project, the app **autosaves** your working copy to a
dedicated **recovery slot** in the background.

- Autosave runs on a fixed cadence (default **every 2 minutes**) and **only when the
  document has unsaved changes** — a clean document is never autosaved.
- The recovery slot is **separate from your version history**. Autosaving never creates a
  visible version and **never overwrites your last explicit save to the cloud**.
- Autosave runs off the GUI thread, so it never interrupts your drawing.

### The recovery prompt on restart

If the app is closed uncleanly (a crash or power loss) while you had unsaved work, the next
time you start it **and connect**, it detects the leftover recovery slot and shows a
**Recover Unsaved Work** prompt:

- **Recover** — fetches and validates the autosaved copy and opens it in a **new tab**.
  Your last explicit save is not affected.
- **Discard** — dismisses the prompt and leaves everything as it was.

> **Recovery is decoded defensively too.** The recovered copy goes through the same
> untrusted-input validation as any cloud file, so a corrupted recovery slot can never
> crash the app on startup — at worst you get a clear error and can carry on.

> **Autosave needs a connected provider.** Autosave and the restart recovery prompt operate
> through the cloud port, so they are active while you are **connected**. Connect a provider
> at the start of a session to keep a safety net running.

## The rest of the cloud & collaboration milestone

This page covers single-user cloud work — save, versions, autosave/recovery — plus
connecting a real provider. The collaboration features that build on top of it —
**shared projects & membership**, **comments**, **presence**, **deterministic
convergence**, **real-time co-editing & live cursors**, and **art branching** — are all
covered in [Shared projects, comments, presence & real-time](collaboration.md).
