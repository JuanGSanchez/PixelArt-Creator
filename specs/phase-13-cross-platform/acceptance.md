# Acceptance scenarios (Gherkin) — Phase 13: Cross-platform Compatibility

> Emitted by AGT-02 (`sdd-clarify` output step). Grounded in The Researcher's report
> (`docs/subagent-report-the-researcher-acaae022-20260707T093800.md`) + the shipped architecture.
> Consumed by AGT-04 (logic/data regression) / AGT-06 (UI + acceptance) / AGT-09 (CI matrix + packaging +
> VPS artifacts) as tests, one per criterion (Article IV).
>
> **Scope note.** **All 23 REQs across 13A–13E are FULLY specified** — each has complete, resolvable
> Gherkin. The **5 WEB REQs of 13E** had D1 (serving stack/dependency), D2 (auth model), and D3 (vanilla
> vs SPA) as `[NEEDS CLARIFICATION]`; the **USER DECIDED all three on 2026-07-07** (grounded by research
> `a4c7da21`): **D1** = reuse existing stack, NO new dependency (static via Nginx / stdlib-dev; data over
> existing `websockets`); **D2** = signed share-link token (validate signature + expiry + issuer/audience;
> scope to the shared project); **D3** = vanilla HTML/CSS/JS (Canvas `pixelated` faithful render; iOS
> Safari + Android Chrome). The 13E scenarios below now encode those decisions; **no scenario is marked
> PARTIAL and no `[NEEDS CLARIFICATION]` deferral remains.**
>
> **Invariant note.** Article I (three-layer purity) and Article VII (no `eval`/`exec`) are NOT relaxed —
> the bundle-import (SC-P13-DATA-008-*) and web-input (SC-P13-WEB-005-1) scenarios prove them.

Feature: Portable path handling and encoding across OSes (Slice 13A, Researcher Q5)
  # REQ-P13-DATA-001, REQ-P13-DATA-002, REQ-P13-DATA-003, REQ-P13-DATA-004

  Scenario: SC-P13-DATA-001-1 All read/write paths are pathlib, no hardcoded separators
    Given the data/ read and write sites for projects, assets, bundles, and exports
    When path_portability_check runs over them in the CI matrix
    Then it reports zero hardcoded-separator or non-pathlib path constructions
    And a project saved with asset references on one OS resolves those references on another OS with no backslash-vs-forward-slash failure

  Scenario: SC-P13-DATA-002-1 Non-ASCII names round-trip byte-faithfully across OSes
    Given a project whose display names and metadata contain accented, CJK, and emoji characters
    When it is saved on one OS and loaded on another with UTF-8 explicitly specified at every I/O site
    Then the loaded names and metadata are byte-faithful to the originals with no mojibake and no UnicodeDecodeError
    And no read or write site relies on the platform default encoding

  Scenario: SC-P13-DATA-003-1 Text artifacts are byte-identical regardless of authoring OS
    Given an identical logical text artifact produced on Windows and on POSIX
    When their bytes are compared
    Then they are byte-equal with no CRLF-versus-LF divergence
    And the binary .pixproj zlib payload is unaffected

  Scenario: SC-P13-DATA-004-1 Case-distinct asset names resolve correctly on Linux
    Given a project whose assets differ only in filename case, such as Hero.png and hero.png
    When it is round-tripped and resolved on case-sensitive Linux
    Then each reference resolves to its exact-case file with no collision and no wrong-file resolution
    And no lookup depends on case-folding

Feature: Cross-OS project round-trip is byte-faithful (Slice 13A headline)
  # REQ-P13-DATA-005

  Scenario: SC-P13-DATA-005-1 A project authored on any OS opens byte-faithfully on any other
    Given a representative project with multiple layers, animation, a tilemap, non-ASCII names, and case-distinct assets
    When it is saved on a source OS and loaded on a target OS for each ordered pair of Windows, Linux, and macOS
    Then the reconstructed document model on the target OS is equal to the model on the source OS
    And the re-saved payload is stable per the shipped deterministic serialiser
    And the round-trip is exercised in the CI matrix

Feature: Font availability and DPI/scaling correctness across OSes (Slice 13A)
  # REQ-P13-UI-001, REQ-P13-UI-002

  Scenario: SC-P13-UI-001-1 UI text renders with a resolvable font on every OS
    Given the UI running on Windows, Linux, and macOS
    When primary UI text is rendered via the defined role-based fallback chain
    Then all text renders with a resolvable font and no missing-glyph or .notdef boxes
    And the fallback chain is defined once, not per-widget
    And both light and dark themes are unaffected

  Scenario: SC-P13-UI-002-1 UI lays out correctly under differing per-OS display scaling
    Given the app at scale factors of 100%, 150%, and 200% on each OS
    When the canvas, docks, and overlays are laid out
    Then nothing is truncated, double-scaled, or blurred and the nearest-neighbour pixel canvas stays crisp
    And the app does not manually multiply the device-pixel ratio
    And the 16 ms FRAME_BUDGET_MS is not relaxed

Feature: Windows/Linux/macOS CI matrix runs the suite green (Slice 13A)
  # REQ-P13-BUILD-001

  Scenario: SC-P13-BUILD-001-1 The 3-OS CI matrix passes and gates portability
    Given a CI workflow defining a Windows, Linux, and macOS matrix
    When each leg runs the full suite headless including lint, type, tests, coverage gate, path_portability_check, and the cross-OS round-trip tests
    Then every leg passes green
    And a deliberate cross-OS regression fails the matrix and blocks merge
    And the concurrency guard and Python pin are preserved

Feature: Self-contained portable bundle export/import across OSes (Slice 13B, extends asset_export.py)
  # REQ-P13-DATA-006, REQ-P13-DATA-007

  Scenario: SC-P13-DATA-006-1 Export produces a self-contained bundle embedding referenced assets
    Given a project that references CAS asset blobs
    When it is exported as a portable bundle via the extended asset_export
    Then the bundle contains the project payload and every referenced CAS blob with no dangling external reference
    And exporting the same project on Windows, Linux, and macOS produces functionally equivalent importable bundles
    And the exporter reuses the shipped asset_export reference resolution with no re-implemented CAS logic

  Scenario: SC-P13-DATA-007-1 A bundle exported on one OS imports self-contained on another
    Given a portable bundle exported on a source OS
    When it is imported on a target OS for each ordered pair of Windows, Linux, and macOS
    Then it reconstructs a model-equal project with all referenced assets present and resolvable
    And non-ASCII and case-distinct asset names are preserved

Feature: Bundle import is path-traversal-defended and eval/exec-free (Slice 13B, Article VII)
  # REQ-P13-DATA-008

  Scenario: SC-P13-DATA-008-1 A traversal-crafted bundle is rejected and writes nothing outside the target
    Given a bundle crafted with a traversal entry such as ../ , an absolute path, or a symlink escape
    When it is imported
    Then the import is rejected and nothing is written outside the import target
    And each embedded entry's destination is resolved and constrained within the import target

  Scenario: SC-P13-DATA-008-2 A malformed or oversized bundle raises a user-facing error without partial write
    Given an oversized, malformed, or unknown-version bundle
    When it is imported
    Then a defined user-facing error is raised with no crash and no partial-valid write
    And a source audit confirms zero eval/exec on the import path

Feature: VPS deployment artifacts for the shipped sync_backend (Slice 13C, Researcher Q4)
  # REQ-P13-BACKEND-001, REQ-P13-BACKEND-002, REQ-P13-BACKEND-003

  Scenario: SC-P13-BACKEND-001-1 Docker and systemd artifacts run the unchanged backend, proven over localhost
    Given a Docker image definition and a systemd unit for the shipped sync_backend
    When the backend is launched via either artifact bound to 0.0.0.0 with LimitNOFILE or ulimit at least 65535
    Then a client connecting over localhost/loopback reproduces the shipped multi-client convergence
    And the backend source is unmodified
    And no live external server is required for acceptance

  Scenario: SC-P13-BACKEND-002-1 Nginx TLS/WSS config keeps idle WebSocket connections alive past 60s
    Given the shipped Nginx reverse-proxy config that terminates TLS, proxies the Upgrade and Connection headers, and sets proxy_read_timeout well above the 60s default
    When a WebSocket connection is established through the config over localhost with a loopback certificate
    Then the idle connection is sustained past 60 seconds without being dropped
    And the backend serves plain WS behind the TLS-terminating proxy
    And no live external server or public certificate is required

  Scenario: SC-P13-BACKEND-003-1 VPS hosting is one option and changes no default
    Given documentation presenting localhost, cloud-adapter, and VPS as co-equal hosting options
    When a user ignores the VPS artifacts
    Then the app and backend behave identically to today with no code change required
    And adopting the VPS artifacts changes no default

Feature: Native desktop installers via a CI build matrix (Slice 13D, Researcher Q3)
  # REQ-P13-BUILD-002, REQ-P13-BUILD-003, REQ-P13-BUILD-004, REQ-P13-BUILD-005

  Scenario: SC-P13-BUILD-002-1 Windows exe/MSI installs and launches with Qt plugins bundled
    Given the Windows CI leg using pyside6-deploy or PyInstaller
    When it builds the distributable
    Then it produces an installable exe or MSI that smoke-launches on a clean Windows environment with Qt plugins bundled
    And the build is reproducible from the committed packaging config

  Scenario: SC-P13-BUILD-003-1 macOS .app/.dmg ships unsigned now with notarization credential-gated and non-blocking
    Given the macOS CI leg
    When it builds the distributable
    Then it produces an unsigned or ad-hoc-signed .app wrapped in a .dmg that smoke-launches on macOS with Gatekeeper-bypass documented
    And the Developer-ID signing, notarization, hardened-runtime, and stapling step is documented and runs only when an Apple Developer ID is supplied
    And the absence of notarization does not fail the phase
    And no credential is committed

  Scenario: SC-P13-BUILD-004-1 Linux AppImage runs on a clean environment with Qt plugins bundled
    Given the Linux CI leg using pyside6-deploy or PyInstaller
    When it builds the distributable
    Then it produces a runnable AppImage that smoke-launches on a clean Linux environment with Qt plugins bundled
    And the build is reproducible from the committed config

  Scenario: SC-P13-BUILD-005-1 One CI build matrix produces all three installers
    Given a single CI build matrix on a build or tag trigger
    When it runs
    Then it produces the Windows exe/MSI, the macOS unsigned .app/.dmg, and the Linux AppImage as downloadable artifacts
    And a failure to build any leg fails that leg visibly
    And the macOS signing step is the credential-gated non-blocking addition

Feature: Web companion viewer — user-facing contract (Slice 13E, D1/D2/D3 DECIDED 2026-07-07)
  # REQ-P13-WEB-001..005 — fully specified; D1 = reuse existing stack / no new dependency, D2 = signed
  # share-link token, D3 = vanilla HTML/CSS/JS (spec §10, research a4c7da21)

  Scenario: SC-P13-WEB-001-1 A shared project renders pixel-faithfully in a vanilla browser client
    Given a shared project reachable over the existing sync_backend websockets relay
    And a vanilla HTML/CSS/JS client served as static files by the already-planned Nginx with no new Python web framework
    When a browser opens the client and it receives the shared project's layers and frames
    Then the client renders the current shared visual state read-mostly using the Canvas API
    And the pixel art is rendered faithfully with image-rendering pixelated, imageSmoothingEnabled false, and integer scale so pixels are crisp and never blurred
    And the project data flows over the existing sync_backend transport with the dependency manifest unchanged aside from the existing websockets

  Scenario: SC-P13-WEB-002-1 The viewer offers light interaction only and exposes no editing
    Given the vanilla browser viewer of a shared project opened with a valid view-scoped share-link token
    When a user interacts with it
    Then only light interactions are permitted, namely toggling layer visibility, stepping through frames, and pan and zoom of the canvas
    And no control mutates the shared project and the client emits no editing or mutation message
    And the PySide6 desktop app remains the sole editor of record
    And an attempt to send a non-view mutation message with a view-scoped token is rejected by the backend

  Scenario: SC-P13-WEB-003-1 The viewer renders pixel-faithfully on iOS Safari and Android Chrome
    Given a shared project and the vanilla no-build-step client
    When the viewer is opened on iOS Safari, on Android Chrome, and on a desktop browser
    Then it loads, connects over the existing websockets transport, and renders the shared project pixel-faithfully on each
    And on iOS Safari verified on a real device the image-rendering pixelated and imageSmoothingEnabled false settings produce crisp non-blurred pixels
    And no build-step or transpile toolchain is required for any target browser
    # GROUNDED: Researcher Q2a confirms mobile Safari and Chrome support the WebSocket transport with no compatibility issue; iOS Safari device-test is an explicit verification concern (spec REQ-P13-WEB-003)

  Scenario: SC-P13-WEB-004-1 web_viewer is a top-level Qt-free component with no new web-framework dependency
    Given the web_viewer directory as a top-level sibling of pixelart_creator and sync_backend containing only static vanilla client assets plus thin Qt-free serving/token glue
    When a layering check runs over web_viewer
    Then it imports no Qt and no ui layer
    And it introduces no new Python web-framework dependency
    And the three desktop layers do not import web_viewer
    And Article I three-layer purity is preserved

  Scenario: SC-P13-WEB-005-1 A valid signed share-link token serves the scoped project; input is untrusted and eval/exec-free
    Given a per-shared-project short-lived signed share-link token presented over HTTPS
    When the viewer requests the shared project's data over the sync_backend
    Then the backend validates the token signature, expiry, and issuer and audience and scopes access to exactly the project the token names before serving any data
    And all web-client input is schema and size validated reusing the shipped eval-free cloud_validation and sync_protocol discipline
    And a source audit confirms zero eval/exec on any web-input path
    And no new web-framework dependency is introduced by the serving or token path

  Scenario: SC-P13-WEB-005-2 An expired, wrong-audience, or bad-signature token is rejected and serves no data
    Given a share-link token that is expired, or has a wrong audience, or carries an invalid signature
    When the viewer presents it to the backend
    Then the backend rejects the token and serves no project data
    And a token scoped to one shared project cannot access a different shared project
