/*
 * web_viewer/static/viewer.js — vanilla ES module, no build step / framework /
 * bundler (D3). Loaded via <script type="module"> (native ES modules).
 *
 * VIEW-ONLY browser companion viewer (ADR-0035, ADR-0036 + Addendum A). This file
 * owns ALL the DOM / WebSocket / Canvas wiring; every piece of PURE logic (wire-frame
 * decode, op-replay + LWW convergence, the tile composite, and the integer-scale/DPR
 * render math) lives in the DOM-free, node-importable module ./viewer_core.mjs and is
 * imported here as the SINGLE SOURCE OF TRUTH (shared verbatim with the node unit
 * tests). It:
 *   1. Presents a signed share-link token to the shipped sync_backend/ over a WSS
 *      connection as the `?token=` query parameter (Addendum A.1); token in MEMORY
 *      ONLY, never localStorage (a4c7da21 D2).
 *   2. JOINs exactly one project (document_id == token project_id, Addendum A.3),
 *      receives the JOIN backlog + ongoing UPDATE frames.
 *   3. Decodes + LWW-converges those frames via viewer_core (Addendum A.4). Wire input
 *      is parsed with JSON.parse ONLY (inside viewer_core) — never eval / new Function
 *      — and size/shape-capped mirroring cloud_validation / sync_protocol (Article VII).
 *   4. Renders pixel-faithfully on a Canvas (native-res backing store + integer CSS
 *      scale + image-rendering:pixelated + imageSmoothingEnabled=false, Addendum A.6).
 *   5. Offers light client-side interaction (layer toggle / frame nav / pan-zoom).
 *
 * VIEW-ONLY GUARANTEE: the only frames this client ever constructs are JOIN and LEAVE
 * (encodeControl). There is NO code path that builds an UPDATE (mutation) frame
 * (WEB-002). See the grep-able assertion note at encodeControl().
 */
import * as core from "./viewer_core.mjs";

// --------------------------------------------------------------------------- //
// DOM + view state.
// --------------------------------------------------------------------------- //
const canvas = document.getElementById("canvas");
const stage = document.getElementById("stage");
const statusEl = document.getElementById("status");
const overlay = document.getElementById("overlay");
const overlayMsg = document.getElementById("overlay-msg");
const frameLabel = document.getElementById("frame-label");
const zoomLabel = document.getElementById("zoom-label");
const layerList = document.getElementById("layer-list");

// The reconstructed document model (owned here, built incrementally from accepted
// wire ops) and the LWW convergence state — both from viewer_core.
const model = core.makeModel();
const state = core.makeState();

const view = {
  frameIndex: null, // currently displayed frame index
  scale: 1, // integer display scale S (Addendum A.6)
  hidden: new Set(), // view-local hidden layers, keyed "frameIndex:layerId"
  dirty: false,
  connected: false,
  hadData: false,
};

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", !!isError);
}

function showOverlay(message) {
  overlayMsg.textContent = message;
  overlay.hidden = false;
}

function render() {
  view.dirty = false;
  const indices = core.frameIndicesOf(model);
  if (view.frameIndex === null || !model.frames.has(view.frameIndex)) {
    view.frameIndex = indices.length ? indices[0] : null;
  }
  // Pure composite of the current frame's visible layers (viewer_core, DOM-free).
  const { width, height, data } = core.compositeModel(model, view.frameIndex, view.hidden);
  // Backing store == source pixel resolution (one texel per source pixel, A.6).
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false; // re-assert after every getContext (A.6/d)
  const img = ctx.createImageData(width, height);
  img.data.set(data); // copy the composited RGBA into the ImageData backing store
  ctx.putImageData(img, 0, 0);
  applyDisplayScale();
  updateControls(indices);
}

/** CSS display size = source_px * INTEGER scale; pixelated does the rest (A.6). */
function applyDisplayScale() {
  const dpr = window.devicePixelRatio || 1;
  // A.6 integer-scale/DPR math lives in viewer_core.displayMetrics (single-sourced
  // with the unit tests); the CSS span is source_px * S (DPR handled by the browser).
  canvas.style.width = core.displayMetrics(canvas.width, view.scale, dpr).cssPx + "px";
  canvas.style.height = core.displayMetrics(canvas.height, view.scale, dpr).cssPx + "px";
  zoomLabel.textContent = view.scale + "×";
}

function updateControls(indices) {
  // Frame label + nav enablement.
  if (view.frameIndex === null || indices.length === 0) {
    frameLabel.textContent = "—";
  } else {
    const pos = indices.indexOf(view.frameIndex) + 1;
    frameLabel.textContent = pos + " / " + indices.length;
  }
  document.getElementById("frame-prev").disabled = indices.length <= 1;
  document.getElementById("frame-next").disabled = indices.length <= 1;

  // Layer visibility list for the current frame.
  layerList.textContent = "";
  if (view.frameIndex === null) return;
  const frame = model.frames.get(view.frameIndex);
  // Show top-to-bottom (reverse of composite order) so it reads like a layer panel.
  const order = core.layerDrawOrder(frame).slice().reverse();
  for (const lid of order) {
    const L = frame.layers.get(lid);
    const li = document.createElement("li");
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    const key = view.frameIndex + ":" + lid;
    const remoteHidden = L.attrs.visible === false;
    cb.checked = !view.hidden.has(key) && !remoteHidden;
    cb.addEventListener("change", () => {
      if (cb.checked) view.hidden.delete(key);
      else view.hidden.add(key);
      scheduleRender();
    });
    const name = document.createElement("span");
    name.className = "layer-name";
    const attrName = typeof L.attrs.name === "string" ? L.attrs.name : "Layer " + lid;
    name.textContent = attrName;
    label.appendChild(cb);
    label.appendChild(name);
    li.appendChild(label);
    layerList.appendChild(li);
  }
}

function scheduleRender() {
  if (view.dirty) return;
  view.dirty = true;
  requestAnimationFrame(render);
}

function stepFrame(delta) {
  const indices = core.frameIndicesOf(model);
  if (indices.length <= 1) return;
  let i = indices.indexOf(view.frameIndex);
  if (i < 0) i = 0;
  i = (i + delta + indices.length) % indices.length;
  view.frameIndex = indices[i];
  scheduleRender();
}

function setScale(next) {
  view.scale = Math.max(1, Math.min(64, Math.round(next)));
  applyDisplayScale();
}

function fitScale() {
  const { w, h } = core.sourceSize(model);
  const availW = stage.clientWidth - 32;
  const availH = stage.clientHeight - 32;
  const s = Math.floor(Math.min(availW / w, availH / h));
  setScale(Number.isFinite(s) && s >= 1 ? s : 1);
}

// --------------------------------------------------------------------------- //
// Light interaction wiring (CLIENT-SIDE ONLY — no wire message, WEB-002/A.5).
// --------------------------------------------------------------------------- //
document.getElementById("frame-prev").addEventListener("click", () => stepFrame(-1));
document.getElementById("frame-next").addEventListener("click", () => stepFrame(1));
document.getElementById("zoom-in").addEventListener("click", () => setScale(view.scale + 1));
document.getElementById("zoom-out").addEventListener("click", () => setScale(view.scale - 1));
document.getElementById("zoom-fit").addEventListener("click", fitScale);

// Wheel zoom (desktop). Ctrl+wheel or plain wheel over the stage.
stage.addEventListener("wheel", (e) => {
  if (!e.ctrlKey && Math.abs(e.deltaY) < 1) return;
  e.preventDefault();
  setScale(view.scale + (e.deltaY < 0 ? 1 : -1));
}, { passive: false });

// Pointer-drag panning via the scroll container.
let panning = null;
stage.addEventListener("pointerdown", (e) => {
  panning = { x: e.clientX, y: e.clientY, sl: stage.scrollLeft, st: stage.scrollTop };
  stage.classList.add("panning");
  stage.setPointerCapture(e.pointerId);
});
stage.addEventListener("pointermove", (e) => {
  if (!panning) return;
  stage.scrollLeft = panning.sl - (e.clientX - panning.x);
  stage.scrollTop = panning.st - (e.clientY - panning.y);
});
function endPan(e) {
  if (!panning) return;
  panning = null;
  stage.classList.remove("panning");
  try { stage.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
}
stage.addEventListener("pointerup", endPan);
stage.addEventListener("pointercancel", endPan);

// Keyboard: arrows step frames, +/- zoom, 0 fits. Ignore when typing in a field.
document.addEventListener("keydown", (e) => {
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  switch (e.key) {
    case "ArrowRight": stepFrame(1); break;
    case "ArrowLeft": stepFrame(-1); break;
    case "+": case "=": setScale(view.scale + 1); break;
    case "-": case "_": setScale(view.scale - 1); break;
    case "0": fitScale(); break;
    default: return;
  }
  e.preventDefault();
});

// --------------------------------------------------------------------------- //
// WebSocket client. VIEW-ONLY: encodeControl only ever builds join/leave. There
// is deliberately NO encodeUpdate on the client (WEB-002).
// --------------------------------------------------------------------------- //

/**
 * Build a JOIN or LEAVE control frame (mirrors sync_protocol._encode for empty
 * bodies). NEVER call this with core.CONTROL.UPDATE — the viewer emits no mutation
 * frame. (Grep-able invariant: this file contains no "update" frame construction.)
 */
function encodeControl(kind, documentId) {
  if (kind !== core.CONTROL.JOIN && kind !== core.CONTROL.LEAVE) {
    throw new Error("viewer emits only join/leave (view-only)");
  }
  return JSON.stringify({ v: core.PROTOCOL_VERSION, kind: kind, doc: documentId });
}
// Local aliases so the ws.send(...) call sites read as encodeControl(CONTROL.JOIN|LEAVE ...).
const CONTROL = core.CONTROL;

let ws = null;
let projectId = null;
let token = null; // held IN MEMORY only — never localStorage (a4c7da21 D2)

function readShareLink() {
  const p = new URLSearchParams(window.location.search);
  // Static-page params (ADR-0036 §2 step 1): t = token, p = project_id hint,
  // ws = optional explicit WS base URL (dev; omitted in production).
  const t = p.get("t") || p.get("token");
  const proj = p.get("p") || p.get("project_id");
  const wsBase = p.get("ws");
  return { t: t, proj: proj, wsBase: wsBase };
}

function buildWsUrl(wsBase, tok) {
  let base;
  if (wsBase) {
    base = wsBase; // dev override, e.g. ws://127.0.0.1:8765/
  } else {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    base = scheme + "//" + window.location.host + "/"; // Nginx proxies "/" to backend
  }
  const u = new URL(base);
  u.searchParams.set("token", tok); // Addendum A.1: token on the WS query string
  return u.toString();
}

function scrubTokenFromAddressBar() {
  // Reduce token exposure in the address bar / browser history (A.2 spirit). The
  // token stays only in memory (the `token` variable) for the session.
  try {
    const p = new URLSearchParams(window.location.search);
    if (p.has("t") || p.has("token")) {
      p.delete("t");
      p.delete("token");
      const q = p.toString();
      const url = window.location.pathname + (q ? "?" + q : "") + window.location.hash;
      window.history.replaceState(null, "", url);
    }
  } catch (_) { /* history API unavailable — non-fatal */ }
}

function connect() {
  const link = readShareLink();
  if (!link.t) {
    setStatus("No share token in this link.", true);
    showOverlay("This link is missing its share token. Ask for a fresh share link.");
    return;
  }
  token = link.t;
  // The authoritative project id is the verified token claim on the backend; the
  // `p` hint is used only to filter inbound frames client-side (never trusted for
  // access — the backend binds to the token's project_id, Addendum A.3).
  projectId = link.proj || null;
  scrubTokenFromAddressBar();

  let url;
  try {
    url = buildWsUrl(link.wsBase, token);
  } catch (_) {
    setStatus("Malformed viewer link.", true);
    showOverlay("The viewer link is malformed.");
    return;
  }

  setStatus("Connecting…");
  try {
    ws = new WebSocket(url);
  } catch (_) {
    setStatus("Cannot open connection.", true);
    showOverlay("Could not open a connection to the server.");
    return;
  }
  ws.binaryType = "arraybuffer";

  ws.addEventListener("open", () => {
    view.connected = true;
    setStatus("Connected — loading project…");
    // JOIN the project. If the token carried no `p` hint we still must name the
    // document; we rely on the hint for the client-side JOIN target. The backend
    // rejects a JOIN whose doc != the verified token project_id (Addendum A.3).
    if (projectId) {
      ws.send(encodeControl(CONTROL.JOIN, projectId));
    } else {
      setStatus("Link is missing the project id (p=).", true);
      showOverlay("This link does not name a project (missing p=).");
    }
  });

  ws.addEventListener("message", (ev) => {
    let msg;
    try {
      msg = core.decodeMessage(ev.data); // decode + cap + validate (Article VII)
    } catch (_) {
      return; // drop malformed/oversized frames silently (mirrors backend defence)
    }
    if (msg.kind !== CONTROL.UPDATE) return; // viewer consumes UPDATE payloads only
    if (projectId && msg.doc !== projectId) return; // not our project — ignore
    let ops;
    try {
      ops = core.decodeUpdate(msg.blob);
    } catch (_) {
      return; // malformed op blob — drop per caps, never work around them
    }
    const winners = core.accept(state, ops); // LWW: keep strictly-newer per register
    if (winners.length === 0) return; // stale/duplicate — nothing to apply
    for (const op of winners) core.applyOp(model, op);
    if (!view.hadData) {
      view.hadData = true;
      overlay.hidden = true;
      setStatus("Viewing shared project.");
    }
    scheduleRender();
  });

  ws.addEventListener("close", () => {
    if (!view.hadData) {
      // Closed before any data arrived — most likely a rejected handshake
      // (401/403: expired / invalid / wrong-aud token) or an unreachable backend.
      setStatus("Link expired or invalid.", true);
      showOverlay("This share link has expired or is invalid, or the server is " +
        "unreachable. Ask for a fresh link.");
    } else if (view.connected) {
      setStatus("Disconnected. Showing last received state.", true);
    }
    view.connected = false;
  });

  ws.addEventListener("error", () => {
    if (!view.hadData) setStatus("Connection error.", true);
  });
}

// Leave cleanly on unload (best-effort read-oriented control frame, never mutation).
window.addEventListener("pagehide", () => {
  try {
    if (ws && ws.readyState === WebSocket.OPEN && projectId) {
      ws.send(encodeControl(CONTROL.LEAVE, projectId));
      ws.close();
    }
  } catch (_) { /* ignore */ }
});

// Re-apply the display scale on resize (source size unchanged).
window.addEventListener("resize", () => { applyDisplayScale(); });

// Kick off.
connect();
render();

// Expose a tiny read-only surface for headless render-fidelity tests:
// pure functions (from viewer_core) + the current model, no mutation of shared
// state. Attached only for test/debug; it constructs no wire message.
window.__webViewer = {
  decodeMessage: core.decodeMessage,
  decodeUpdate: core.decodeUpdate,
  accept: core.accept,
  makeState: core.makeState,
  registerKey: core.registerKey,
  composite: core.composite,
  displayMetrics: core.displayMetrics,
  model: model,
  render: render,
  sourceSize: () => core.sourceSize(model),
};
