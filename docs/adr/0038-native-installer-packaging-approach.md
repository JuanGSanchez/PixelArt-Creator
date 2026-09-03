# ADR-0038 — Native-installer / packaging approach: `pyside6-deploy` + PyInstaller per-OS, a CI build matrix, and credential-gated macOS signing (Phase-13)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-07 |
| Author | Architecture — packaging/CI executed by DevOps |
| Feature | `phase-13-cross-platform` (native installers) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0027 (`sync_backend`/`web_viewer` excluded from the desktop wheel), the shipped `.github/workflows/ci.yml` + `pyproject.toml` |

## Context

Phase-13 packages the shipped PySide6 desktop app as **native installers** for Windows, macOS, and
Linux so a non-technical user can install and launch it **without a Python environment** (REQ-P13-BUILD-002..
005), built by a **CI build matrix**. macOS store-distribution **mandates** Developer-ID signing +
notarization + hardened runtime + stapling (research Q3) — a hard requirement needing the **user's Apple
Developer ID**, a credential not yet available. This ADR rules the packaging **tool selection**, the **per-OS
targets**, the **CI build matrix** shape, and the **credential-gated, non-blocking** macOS signing posture
(Article XI). This is a **`BUILD`** (non-three-layer DevOps) concern owned by DevOps; it changes **no** product
code.

## Decision

### 1. Tooling: `pyside6-deploy` primary, PyInstaller fallback (Q3)

Package via **`pyside6-deploy`** — the **Qt-recommended** tool (a Nuitka-based wrapper Qt states produces "the
most optimized executable"), which **bundles the required Qt plugins** (platform/image-format/style — the
Windows/Cocoa/xcb `platforms` plugins etc.) automatically. **PyInstaller** (with the Qt-provided hooks) is the
**documented fallback** where a target needs it. The packaging config is **committed and reproducible** (a
`pysidedeploy.spec` per target under a `packaging/` top-level dir — ops config, not scanned by
`check_layering`), so each build is reproducible from the committed config.

### 2. Per-OS targets

- **Windows (BUILD-002):** an **`.exe`** and/or **`.msi`** installer; Qt plugins bundled; smoke-launches on a
  clean Windows env.
- **Linux (BUILD-004):** a **self-contained AppImage** (distro-agnostic); Qt plugins bundled; smoke-launches
  on a clean Linux env.
- **macOS (BUILD-003):** a **.app** wrapped in a **.dmg**. Shipped **unsigned / ad-hoc-signed now**, with the
  Gatekeeper-bypass documented for the unsigned case; smoke-launches on macOS.

The desktop distributable ships **only** `pixelart_creator*`; `sync_backend`, `web_viewer`, `tests`,
`scripts`, `docs` are excluded (the `pyproject` `exclude` list — ADR-0027 + ADR-0035 defence-in-depth).

### 3. CI build matrix (BUILD-005)

A **CI build matrix** (extending the 13A **test** matrix — REQ-P13-BUILD-001 — into a **build** matrix on a
**build/tag** trigger) builds the three distributables on their respective OS legs
(`ubuntu-latest`/`windows-latest`/`macos-latest`) and **publishes them as downloadable build artifacts**. A
per-leg build failure fails **that leg** visibly. The shipped concurrency guard + Python-3.12 pin are
preserved. The build matrix is separate from (but shares the OS matrix with) the always-on test matrix so PR
CI is not slowed by full packaging on every push.

### 4. macOS signing: documented, credential-gated, NON-blocking (Article XI)

Developer-ID **signing (`codesign --options=runtime` + entitlements) → notarization (`notarytool`) →
stapling (`stapler`)** is shipped as a **documented step that runs ONLY when an Apple Developer ID is
supplied** (as a CI secret). Its **absence does NOT fail** Phase 13 — the unsigned/ad-hoc .app/.dmg is the
accepted Phase-13 artifact. **No credential is committed** (Article XI / Article VII §3). When the credential
is later supplied, the same pipeline step signs + notarizes + staples without any other change.

## Alternatives Considered

- **Nuitka directly (not via `pyside6-deploy`).** Rejected as primary: `pyside6-deploy` is the Qt-recommended
  wrapper around Nuitka that also handles Qt-plugin collection; using it directly is the supported path.
  Nuitka's raw speed/size advantage (Q3) is inherited through the wrapper.
- **PyInstaller as primary.** Rejected as primary (kept as fallback): Q3 notes PyInstaller is the most popular
  but produces the largest binaries; `pyside6-deploy` is Qt's recommendation and optimizes better. Fallback
  where a target/plugin quirk needs it.
- **Briefcase (BeeWare).** Rejected this phase: Briefcase is the unified desktop+mobile packager but pulls in
  the BeeWare toolchain; Q3 lists it as viable, but `pyside6-deploy` is the Qt-native, lowest-friction choice
  for a PySide6 app and keeps the toolchain aligned with the framework.
- **Making macOS notarization a blocking criterion now.** Rejected (Article XI + spec non-goal): the Apple
  Developer ID is not available; blocking the phase on an unavailable credential would stall shipping. The
  credential-gated, non-blocking posture ships the pipeline + an unsigned artifact now.
- **Flatpak instead of AppImage for Linux.** Deferred: AppImage is a single self-contained executable (no
  runtime install), the lowest-friction "run without a distro package" target for Q3; Flatpak is a documented
  future addition behind the same build matrix.

## Consequences

**Positive.** Every OS gets a native installer from the **same automated, reproducible** CI build matrix, with
Qt plugins bundled (the deploy tools handle this); macOS ships now (unsigned) with a clean, credential-gated
upgrade path to notarization; no product code changes (a pure `BUILD` concern); the wheel-exclusion invariants
(ADR-0027/0035) keep `sync_backend`/`web_viewer` out of the desktop distributable.

**Negative / risk.** Three OS build legs add significant CI minutes (mitigated by the build/tag trigger, not
every push). Nuitka compile times can be long (a build-leg wall-time risk DevOps tunes per leg). The unsigned
macOS artifact requires a documented Gatekeeper bypass until a Developer ID is supplied — an accepted,
communicated limitation (spec non-goal).

## Grounding

- Spec §2 (13D scope), §4 REQ-P13-BUILD-002/-003/-004/-005, §5 (Article XI credential-gating; Article X §1
  `BUILD` tag), §8 DEP-1/DEP-2; `acceptance.md` SC-P13-BUILD-002-1/-003-1/-004-1/-005-1; `traceability.md`
  13D rows.
- Research note `acaae022` Q3 (`pyside6-deploy` = Qt-recommended Nuitka wrapper; PyInstaller most popular;
  Nuitka fastest/smallest; Qt plugins must be bundled; Windows exe/MSI, Linux AppImage/Flatpak, macOS
  .app/.dmg; macOS Developer-ID signing + notarization + hardened runtime + stapling MANDATORY for store dist;
  `notarytool` + `stapler`).
- Shipped `.github/workflows/ci.yml` (the test matrix this extends), `pyproject.toml` (wheel `exclude`).
  Constitution Article IV (CI), VIII (gates), X §1 (`BUILD`), XI (credential-gated irreversible/external
  steps; no committed secret). ADR-0027 / ADR-0035 (non-three-layer packages excluded from the wheel).

## Addendum A (2026-07-07) — a minimal shipped launch entry point

**What changed.** Building 13D surfaced that the app had **no shipped launch entry point**: the only launch
recipe was a `QApplication(...)` snippet in the README, and `Main_Window` **asserts** a pre-existing
`QApplication`. A native installer — and the pip `pixelart-creator` gui-script — both need a real, importable
callable to start. 13D therefore adds a **minimal, canonical, tested entry point**:

- **`pixelart_creator/ui/app.py`** — `create_app(argv) -> (QApplication, Main_Window)` (get-or-create the
  `QApplication`, set application/organisation name, construct + `show()` `Main_Window`, **no** `exec()` — the
  headless-testable seam) and `main(argv) -> int` (calls `create_app`, then `app.exec()`).
- **`pixelart_creator/__main__.py`** — a thin shim so `python -m pixelart_creator` calls `main()`.
- A CI/packaging **smoke-launch self-exit hook**: `main` honours `PIXELART_SMOKE_EXIT_MS` (a **positive
  integer** of milliseconds → `QTimer.singleShot(N, app.quit)`), so a packaged build can start, reach the event
  loop, paint, and exit `0` on a headless CI leg without blocking on `app.exec()` forever.

The packaged installers (`pysidedeploy-*.spec` retargeted at `pixelart_creator.__main__`), the AppImage script,
and the `pyproject` `[project.gui-scripts] pixelart-creator = "pixelart_creator.ui.app:main"` **all launch
through this single entry point**. The stopgap `packaging/app_entry.py` is deleted in favour of it.

**Why this refines "changes no product code".** The original Context/Consequences statement that 13D "changes
no product code" was written on the assumption that a launchable app already existed and only needed wrapping.
It did not. A native-installer target with a **clean, reproducible launch story** genuinely **required** a
shipped, tested entry point — packaging cannot depend on a README snippet. The refinement is therefore not a
scope creep but the **minimal product surface without which BUILD-002..005 cannot be fulfilled correctly**: the
smallest possible addition (create `QApplication` → build `Main_Window` → `exec`) that makes the app
launchable and the installers verifiable.

**Why it is architecturally minimal and clean.** The addition is **Article-I-clean**: `app.py` lives in the
`ui/` layer, where Qt is permitted, and adds **no** behaviour to any domain/logic/data path — startup
theme/i18n/font-fallback wiring is **not** duplicated here (it already lives in `Main_Window.__init__`). The
module is **import-side-effect-free** (no `QApplication` constructed at import). The smoke hook is
**eval-free and defensive** (plain `int()` with a `ValueError` guard; a bad value is ignored, never crashes the
launcher). The `__main__.py` shim sits at the package root **by Python convention** (`python -m` looks there
only) and imports **upward** into `ui/` (`ui.app.main`) — no logic/data module imports it. No module outside
`ui/` (other than that root-level shim) is touched.

**Gate result.** `check_layering.py` is clean on **both** roots (`--root pixelart_creator`: 179 modules;
`--root .`: 3 modules) and `check_cycles.py` reports **no cycles** (181 modules) — all exit `0`. `packaging/`
is **not** scanned (no `__init__.py`; ops config, per Decision §1). The new entry point adds **no forbidden
layer edge and no cycle**. This feature is **architecturally clear to commit**.

**Grounding (addendum).** Spec §4 REQ-P13-BUILD-002..005 (a launchable installed app); README launch snippet
(the pre-existing, unshipped recipe this canonicalises); Constitution Article I (layer discipline), Article XI
(no `eval`; defensive parse). Deterministic gates: `scripts/check_layering.py`, `scripts/check_cycles.py`.
This addendum records the decision; it does **not** alter the packaging tool selection, per-OS targets, CI
matrix, or macOS-signing posture of the original Decision.
