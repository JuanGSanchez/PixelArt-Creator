/*
 * web_viewer/static/viewer_core.mjs — DOM-free, side-effect-free ES module.
 *
 * The PURE logic of the VIEW-ONLY web companion viewer, extracted from viewer.js so
 * it is importable in node for framework-free unit tests (web_viewer/tests/
 * viewer_core.test.mjs, T13E-B07) AND re-imported by viewer.js as the single source
 * of truth for the browser client. BEHAVIOUR-NEUTRAL vs the previous inlined copy.
 *
 * This module contains NO DOM, NO WebSocket, NO Canvas, and NO top-level side
 * effects — only pure functions + plain data. It reuses only ECMAScript globals that
 * exist identically in browsers and node (>=16): JSON, TextEncoder/TextDecoder, atob,
 * Uint8Array, Uint8ClampedArray. Wire input is parsed with JSON.parse ONLY — never
 * eval / new Function — and size/shape-capped mirroring the shipped pure logic/
 * (cloud_validation / sync_protocol / realtime_apply / convergence), per ADR-0036
 * Addendum A (A.4 op-replay + LWW convergence; A.6 integer-scale/DPR render math).
 *
 * Caps + vocabulary mirrored from the shipped pure logic/ (single-sourced by
 * contract; ADR-0035 Addendum A). Keep in lockstep with:
 *   logic/constants.py      : CRDT_TILE_SIZE_PX, MAX_CRDT_UPDATE_BYTES
 *   logic/sync_protocol.py  : _PROTOCOL_VERSION, _MAX_FRAME_BYTES,
 *                             _MAX_DOCUMENT_ID_CHARS, ControlKind
 *   logic/realtime_apply.py : _UPDATE_VERSION, _MAX_OPS_PER_UPDATE
 *   logic/convergence.py    : LAYER_ATTRS
 */

export const PROTOCOL_VERSION = 1; // sync_protocol._PROTOCOL_VERSION
export const UPDATE_VERSION = 1; // realtime_apply._UPDATE_VERSION
export const CRDT_TILE_SIZE_PX = 64; // constants.CRDT_TILE_SIZE_PX
export const MAX_CRDT_UPDATE_BYTES = 1048576; // constants.MAX_CRDT_UPDATE_BYTES
export const MAX_FRAME_BYTES = MAX_CRDT_UPDATE_BYTES * 2 + 4096; // sync_protocol._MAX_FRAME_BYTES
export const MAX_DOCUMENT_ID_CHARS = 1024; // sync_protocol._MAX_DOCUMENT_ID_CHARS
export const MAX_OPS_PER_UPDATE = 4096; // realtime_apply._MAX_OPS_PER_UPDATE
export const CONTROL = { JOIN: "join", LEAVE: "leave", UPDATE: "update", PRESENCE: "presence" };
const LAYER_ATTRS = new Set(["name", "opacity", "visible", "locked"]); // convergence.LAYER_ATTRS

// --------------------------------------------------------------------------- //
// Small untrusted-input helpers (Article VII). Never eval/new Function.
// --------------------------------------------------------------------------- //

/** True for a non-negative safe integer (mirrors _require_nonneg_int; bool excluded). */
function isNonNegInt(v) {
  return typeof v === "number" && Number.isInteger(v) && v >= 0;
}

/** True for a strictly-positive safe integer (mirrors layer_id > 0). */
function isPosInt(v) {
  return typeof v === "number" && Number.isInteger(v) && v > 0;
}

/** Decode a standard-base64 string to a Uint8Array; throws on malformed input. */
function base64ToBytes(b64) {
  if (typeof b64 !== "string") throw new Error("base64 body must be a string");
  // atob throws on invalid base64 — mirrors b64decode(validate=True). It is a
  // standard global in both browsers and node (>=16), not a DOM API.
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i) & 0xff;
  return out;
}

const _utf8 = new TextDecoder("utf-8", { fatal: true });

/** Lexicographic compare of two Uint8Arrays (mirrors Python bytes comparison). */
function cmpBytes(a, b) {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  if (a.length === b.length) return 0;
  return a.length < b.length ? -1 : 1;
}

const EMPTY = new Uint8Array(0);

// --------------------------------------------------------------------------- //
// sync_protocol.decode_message — mirror. Returns {kind, doc, blob?} or throws.
// --------------------------------------------------------------------------- //
export function decodeMessage(raw) {
  // `raw` is a WS text (string) or binary (ArrayBuffer/Uint8Array) frame.
  let bytes;
  if (typeof raw === "string") {
    bytes = new TextEncoder().encode(raw);
  } else if (raw instanceof ArrayBuffer) {
    bytes = new Uint8Array(raw);
  } else if (raw instanceof Uint8Array) {
    bytes = raw;
  } else {
    throw new Error("sync frame must be text or binary");
  }
  if (bytes.length > MAX_FRAME_BYTES) {
    throw new Error("sync frame exceeds MAX_FRAME_BYTES"); // cap BEFORE decode
  }
  let frame;
  try {
    frame = JSON.parse(_utf8.decode(bytes)); // JSON only — never eval
  } catch (e) {
    throw new Error("sync frame is not valid UTF-8 JSON");
  }
  if (frame === null || typeof frame !== "object" || Array.isArray(frame)) {
    throw new Error("sync frame must decode to a JSON object");
  }
  if (frame.v !== PROTOCOL_VERSION) throw new Error("unsupported sync protocol version");
  const kind = frame.kind;
  if (kind !== CONTROL.JOIN && kind !== CONTROL.LEAVE &&
      kind !== CONTROL.UPDATE && kind !== CONTROL.PRESENCE) {
    throw new Error("unknown sync message kind");
  }
  const doc = frame.doc;
  if (typeof doc !== "string" || doc.length === 0 || doc.length > MAX_DOCUMENT_ID_CHARS) {
    throw new Error("invalid document_id");
  }
  if (kind === CONTROL.UPDATE) {
    if (typeof frame.blob !== "string") throw new Error("update 'blob' must be base64 str");
    const blob = base64ToBytes(frame.blob);
    // validate_crdt_update: non-empty + <= MAX_CRDT_UPDATE_BYTES (post-decode size).
    if (blob.length === 0) throw new Error("CRDT update is empty");
    if (blob.length > MAX_CRDT_UPDATE_BYTES) throw new Error("CRDT update oversize");
    return { kind: kind, doc: doc, blob: blob };
  }
  // JOIN / LEAVE / PRESENCE carry no raster payload the viewer consumes.
  return { kind: kind, doc: doc };
}

// --------------------------------------------------------------------------- //
// realtime_apply op-codec decode — mirror decode_update + _decode_op.
// Ops are validated at "construction" exactly like the Python dataclasses.
// --------------------------------------------------------------------------- //
export function decodeUpdate(blob) {
  // blob already size-capped by decodeMessage (validate_crdt_update equivalent).
  let payload;
  try {
    payload = JSON.parse(_utf8.decode(blob)); // JSON only — never eval
  } catch (e) {
    throw new Error("update blob is not valid UTF-8 JSON");
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("update blob must decode to a JSON object");
  }
  if (payload.v !== UPDATE_VERSION) throw new Error("unsupported update version");
  const items = payload.ops;
  if (!Array.isArray(items)) throw new Error("update blob 'ops' must be a list");
  if (items.length > MAX_OPS_PER_UPDATE) throw new Error("update exceeds op cap");
  return items.map(decodeOp);
}

function decodeOp(item) {
  if (item === null || typeof item !== "object" || Array.isArray(item)) {
    throw new Error("operation must be a mapping");
  }
  const kind = item.t;
  if (kind === "meta") {
    if (typeof item.key !== "string" || item.key.length === 0) throw new Error("meta key");
    if (typeof item.value !== "string") throw new Error("meta value must be str");
    requireStamp(item);
    return { t: "meta", key: item.key, value: item.value, c: item.c, s: item.s };
  }
  if (kind === "attr") {
    if (!isNonNegInt(item.frame)) throw new Error("attr frame");
    if (!isPosInt(item.layer)) throw new Error("attr layer_id must be positive int");
    if (!LAYER_ATTRS.has(item.attr)) throw new Error("attr not in LAYER_ATTRS");
    requireStamp(item);
    return {
      t: "attr", frame: item.frame, layer: item.layer,
      attr: item.attr, value: item.value, c: item.c, s: item.s,
    };
  }
  if (kind === "order") {
    if (!isNonNegInt(item.frame)) throw new Error("order frame");
    const order = item.order;
    if (!Array.isArray(order)) throw new Error("order 'order' must be a list");
    const seen = new Set();
    for (const lid of order) {
      if (!isPosInt(lid)) throw new Error("order layer_id must be positive int");
      if (seen.has(lid)) throw new Error("order has duplicate layer_ids");
      seen.add(lid);
    }
    requireStamp(item);
    return { t: "order", frame: item.frame, order: order.slice(), c: item.c, s: item.s };
  }
  if (kind === "raster") {
    if (!isNonNegInt(item.frame)) throw new Error("raster frame");
    if (!isPosInt(item.layer)) throw new Error("raster layer_id must be positive int");
    if (!isNonNegInt(item.tx) || !isNonNegInt(item.ty)) throw new Error("raster tile index");
    const tw = item.tw;
    const th = item.th;
    if (!isPosInt(tw) || tw > CRDT_TILE_SIZE_PX) throw new Error("raster tile_width");
    if (!isPosInt(th) || th > CRDT_TILE_SIZE_PX) throw new Error("raster tile_height");
    if (typeof item.px !== "string") throw new Error("raster 'px' must be base64 str");
    const px = base64ToBytes(item.px);
    const cells = tw * th;
    // indexed (cells) or RGBA (cells*4), mirroring RasterOp.__post_init__.
    if (px.length !== cells && px.length !== cells * 4) throw new Error("raster px length");
    requireStamp(item);
    return {
      t: "raster", frame: item.frame, layer: item.layer,
      tx: item.tx, ty: item.ty, tw: tw, th: th,
      rgba: px.length === cells * 4, px: px, c: item.c, s: item.s,
    };
  }
  throw new Error("unknown operation kind");
}

function requireStamp(item) {
  if (!isNonNegInt(item.c)) throw new Error("logical_clock must be non-negative int");
  if (!isNonNegInt(item.s)) throw new Error("site_id must be non-negative int");
}

// --------------------------------------------------------------------------- //
// LWW streaming apply — mirror realtime_apply.RealtimeState.accept +
// convergence winner resolution. Per register key keep the winner with the
// highest stamp (logical_clock, site_id, pixels) compared lexicographically;
// drop an op that is not STRICTLY newer than the applied stamp. Order-independent
// (strong eventual consistency) — identical to the Python read path.
// --------------------------------------------------------------------------- //

/** registerKey(op) — mirrors realtime_apply._register_key. */
export function registerKey(op) {
  switch (op.t) {
    case "meta": return "meta:" + op.key;
    case "attr": return "attr:" + op.frame + ":" + op.layer + ":" + op.attr;
    case "order": return "order:" + op.frame;
    case "raster": return "raster:" + op.frame + ":" + op.layer + ":" + op.tx + ":" + op.ty;
    default: throw new Error("unknown operation type");
  }
}

/** stamp(op) = [logical_clock, site_id, pixels] — mirrors realtime_apply._stamp. */
function stampOf(op) {
  return [op.c, op.s, op.t === "raster" ? op.px : EMPTY];
}

/** Lexicographic (c, s, pixels) compare, mirroring the Python tuple order. */
function cmpStamp(a, b) {
  if (a[0] !== b[0]) return a[0] < b[0] ? -1 : 1;
  if (a[1] !== b[1]) return a[1] < b[1] ? -1 : 1;
  return cmpBytes(a[2], b[2]);
}

/** RealtimeState factory: registerKey -> stamp. */
export function makeState() {
  return { stamps: new Map() };
}

/**
 * RealtimeState.accept: return the ops that win against the recorded clocks and
 * record their stamps. Byte-for-byte the Python algorithm: among the incoming ops
 * keep the highest stamp per register; drop any op not strictly newer than what is
 * already applied.
 */
export function accept(state, ops) {
  const winners = new Map();
  const winnerStamps = new Map();
  for (const op of ops) {
    const key = registerKey(op);
    const stamp = stampOf(op);
    const applied = state.stamps.get(key);
    if (applied !== undefined && cmpStamp(stamp, applied) <= 0) continue;
    const current = winnerStamps.get(key);
    if (current === undefined || cmpStamp(stamp, current) > 0) {
      winners.set(key, op);
      winnerStamps.set(key, stamp);
    }
  }
  for (const [key, stamp] of winnerStamps) state.stamps.set(key, stamp);
  // Deterministic order (sorted keys) — does not affect the converged result.
  return [...winners.keys()].sort().map((k) => winners.get(k));
}

// --------------------------------------------------------------------------- //
// Reconstructed document model. accept() has already resolved LWW winners, so
// applying an accepted op simply overwrites its register in the model — exactly
// as apply_operations overwrites the tile/attr/order/meta in the live Document.
// The model is a plain data structure created per-owner (no shared module state).
// --------------------------------------------------------------------------- //

/** Create an empty document model (owned by the caller). */
export function makeModel() {
  return {
    meta: new Map(), // key -> value (string)
    frames: new Map(), // frameIndex(int) -> Frame
  };
}

function getFrame(model, fi) {
  let f = model.frames.get(fi);
  if (!f) {
    f = { layers: new Map(), order: null, layerSeen: [] };
    model.frames.set(fi, f);
  }
  return f;
}

function getLayer(frame, lid) {
  let L = frame.layers.get(lid);
  if (!L) {
    L = { tiles: new Map(), attrs: {} };
    frame.layers.set(lid, L);
    frame.layerSeen.push(lid);
  }
  return L;
}

/** Apply an accepted op into `model` (overwrites its register). */
export function applyOp(model, op) {
  if (op.t === "meta") {
    model.meta.set(op.key, op.value);
  } else if (op.t === "attr") {
    getLayer(getFrame(model, op.frame), op.layer).attrs[op.attr] = op.value;
  } else if (op.t === "order") {
    getFrame(model, op.frame).order = op.order.slice();
  } else if (op.t === "raster") {
    getLayer(getFrame(model, op.frame), op.layer).tiles.set(op.tx + ":" + op.ty, op);
  }
}

/** Sorted (ascending) list of frame indices present in the model. */
export function frameIndicesOf(model) {
  return [...model.frames.keys()].sort((a, b) => a - b);
}

// --------------------------------------------------------------------------- //
// Source size. The wire ops do NOT carry the document's native width/height (only
// tile edits). Prefer numeric meta "width"/"height" if published; otherwise DERIVE
// the source size from the bounding box of painted tiles across all frames/layers.
// --------------------------------------------------------------------------- //
function intMeta(model, key) {
  const raw = model.meta.get(key);
  if (typeof raw !== "string") return 0;
  const n = parseInt(raw, 10);
  return Number.isInteger(n) && n > 0 ? n : 0;
}

export function sourceSize(model) {
  const mw = intMeta(model, "width");
  const mh = intMeta(model, "height");
  if (mw && mh) return { w: mw, h: mh };
  let w = 0;
  let h = 0;
  for (const frame of model.frames.values()) {
    for (const L of frame.layers.values()) {
      for (const op of L.tiles.values()) {
        w = Math.max(w, op.tx * CRDT_TILE_SIZE_PX + op.tw);
        h = Math.max(h, op.ty * CRDT_TILE_SIZE_PX + op.th);
      }
    }
  }
  return { w: Math.max(1, w), h: Math.max(1, h) };
}

// --------------------------------------------------------------------------- //
// Compositing. NORMAL source-over only: the wire attr vocabulary carries no blend
// mode (LAYER_ATTRS = name/opacity/visible/locked), so every layer composites
// straight-alpha over the backdrop scaled by opacity. This mirrors
// logic/blend._blend_over_arrays (the NORMAL float path) so the render matches the
// editor. Layers composite bottom-to-top (blend.composite_stack CL-4); the order
// list is bottom->top, unnamed layers keep insertion order after (convergence
// _reorder_top_level). Indexed-mode tiles need a palette the ops do not carry —
// those tiles are skipped (RGBA projects render fully; FLAGGED in the report).
// --------------------------------------------------------------------------- //

/** Bottom->top layer draw order for a frame (order list, then insertion order). */
export function layerDrawOrder(frame) {
  const present = new Set(frame.layers.keys());
  const ordered = [];
  const placed = new Set();
  if (frame.order) {
    for (const lid of frame.order) {
      if (present.has(lid) && !placed.has(lid)) {
        ordered.push(lid);
        placed.add(lid);
      }
    }
  }
  for (const lid of frame.layerSeen) {
    if (!placed.has(lid)) {
      ordered.push(lid);
      placed.add(lid);
    }
  }
  return ordered;
}

export function clampOpacity(v) {
  if (typeof v !== "number" || !Number.isFinite(v)) return 1;
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

/**
 * Blend one RGBA tile op into the dst RGBA buffer (source-over, opacity-scaled).
 * `dst` MUST be a Uint8ClampedArray: assigning a float to it performs ECMAScript
 * ToUint8Clamp (round-half-to-EVEN + clip), matching numpy's np.round + clip in the
 * shipped _blend_over_arrays — the exact rounding that produced the 0-LSB match.
 * Indexed-mode tiles (no palette on the wire) are skipped.
 */
function blendTile(dst, w, h, op, opacity) {
  if (!op.rgba) return; // indexed tile: palette not carried on the wire — skip.
  const x0 = op.tx * CRDT_TILE_SIZE_PX;
  const y0 = op.ty * CRDT_TILE_SIZE_PX;
  const px = op.px;
  for (let r = 0; r < op.th; r += 1) {
    const y = y0 + r;
    if (y < 0 || y >= h) continue;
    for (let c = 0; c < op.tw; c += 1) {
      const x = x0 + c;
      if (x < 0 || x >= w) continue;
      const si = (r * op.tw + c) * 4;
      const sr = px[si];
      const sg = px[si + 1];
      const sb = px[si + 2];
      const sa = (px[si + 3] / 255) * opacity; // effective source alpha 0..1
      if (sa <= 0) continue; // clear -> dst unchanged
      const di = (y * w + x) * 4;
      if (sa >= 1) {
        dst[di] = sr; dst[di + 1] = sg; dst[di + 2] = sb; dst[di + 3] = 255;
        continue;
      }
      const da = dst[di + 3] / 255;
      const oneMinus = 1 - sa;
      const outA = sa + da * oneMinus;
      const safeA = outA > 0 ? outA : 1;
      dst[di] = (sr * sa + dst[di] * da * oneMinus) / safeA;
      dst[di + 1] = (sg * sa + dst[di + 1] * da * oneMinus) / safeA;
      dst[di + 2] = (sb * sa + dst[di + 2] * da * oneMinus) / safeA;
      dst[di + 3] = outA * 255;
    }
  }
}

/**
 * Composite the visible layers of `frameIndex` in `model` into an RGBA buffer.
 * `hidden` is an optional Set of view-local "frameIndex:layerId" toggles to skip.
 * Returns {width, height, data} where `data` is a Uint8ClampedArray of width*height*4.
 * DOM-free: the caller (viewer.js) owns the Canvas / putImageData step.
 */
export function compositeModel(model, frameIndex, hidden) {
  const { w, h } = sourceSize(model);
  const data = new Uint8ClampedArray(w * h * 4); // zero-filled = transparent backdrop
  if (frameIndex !== null && frameIndex !== undefined && model.frames.has(frameIndex)) {
    const frame = model.frames.get(frameIndex);
    for (const lid of layerDrawOrder(frame)) {
      if (hidden && hidden.has(frameIndex + ":" + lid)) continue; // view-local toggle
      const L = frame.layers.get(lid);
      if (L.attrs.visible === false) continue; // remote visibility attr
      const opacity = clampOpacity(L.attrs.opacity);
      for (const op of L.tiles.values()) blendTile(data, w, h, op, opacity);
    }
  }
  return { width: w, height: h, data: data };
}

/**
 * Pure convenience composite over a FLAT op list (already accept-winnowed): build a
 * fresh model, apply every op, then composite `opts.frameIndex` (default: the first
 * frame). Used by the node unit tests; equivalent to compositeModel over an
 * incrementally-built model. Returns {width, height, data}.
 */
export function composite(ops, opts) {
  const model = makeModel();
  for (const op of ops) applyOp(model, op);
  const indices = frameIndicesOf(model);
  let fi;
  if (opts && opts.frameIndex !== undefined && opts.frameIndex !== null) {
    fi = opts.frameIndex;
  } else {
    fi = indices.length ? indices[0] : null;
  }
  return compositeModel(model, fi, null);
}

// --------------------------------------------------------------------------- //
// Render metrics (ADR-0036 A.6). Integer-scale + DPR block math. Given a source
// pixel span, an integer display scale S, and the device pixel ratio DPR (integer
// on iOS Safari, {2,3}), the CSS span is source*S and the physical/device span is
// source*S*DPR, so each source pixel maps to an S*DPR flat block of device pixels
// (nearest-neighbour via image-rendering:pixelated) — no interpolation.
// --------------------------------------------------------------------------- //
export function displayMetrics(sourcePx, scale, dpr) {
  const s = scale;
  const d = dpr === undefined || dpr === null ? 1 : dpr;
  const cssPx = sourcePx * s;
  const blockPx = s * d;
  const devicePx = sourcePx * blockPx; // == sourcePx * s * d
  return { cssPx: cssPx, devicePx: devicePx, blockPx: blockPx };
}
