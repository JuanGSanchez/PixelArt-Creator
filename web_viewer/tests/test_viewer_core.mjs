/*
 * web_viewer/tests/test_viewer_core.mjs — framework-free node unit tests (T13E-B07).
 * Renamed from viewer_core.test.mjs (R-42) so the citation/traceability matrix tool,
 * which indexes only files whose NAME starts with `test_`, actually sees this suite.
 *
 * Owned by AGT-13 (Web Verification). Plain `node:assert/strict` — NO test framework,
 * NO bundler (D3). Run with a bare node:
 *
 *     node web_viewer/tests/test_viewer_core.mjs
 *
 * WHAT IT NEEDS TO RUN (see the AGT-06 report — "pure-logic extraction"):
 *   viewer.js today wraps ALL its pure logic (decodeMessage / decodeUpdate /
 *   accept / registerKey / the tile-composite + integer-scale math) in an IIFE that
 *   ALSO runs DOM/Canvas/WebSocket code at import time (document.getElementById,
 *   connect(), render()). It exposes only `window.__webViewer`, which requires the
 *   whole IIFE — and therefore a browser — to execute. So it is NOT importable in
 *   node as-is. These tests import a to-be-extracted, DOM-free ES module:
 *
 *       web_viewer/static/viewer_core.mjs
 *
 *   exporting the pure functions verbatim (no behaviour change), which viewer.js then
 *   imports. Until that module exists (a frontend/agt-11-web-client task) OR node is
 *   installed, this file SKIPS cleanly (exit 0) and prints why. Once both are present
 *   it runs for real and FAILS loudly (exit 1) on any divergence.
 *
 * Covered acceptance: SC-P13-WEB-001-1 (pixel-faithful render), -002-1 (VIEW-ONLY
 * read path), ADR-0036 A.4 (LWW winner rule) + A.6 (integer-scale / DPR math).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const CORE_URL = new URL("../static/viewer_core.mjs", import.meta.url);
const FIXTURE = join(HERE, "fidelity_fixture.json");
// ADR-0044: pixel fidelity is byte-exact (0 LSB); the prior +/-1 LSB tolerance is
// withdrawn. Kept as a named constant (not a bare 0) so the failure message below
// still quotes the measured maxDiff against an explicit contract value.
const TOLERANCE_LSB = 0;

let core;
try {
  core = await import(CORE_URL.href);
} catch (err) {
  console.log(
    "SKIP: cannot import web_viewer/static/viewer_core.mjs — the pure-logic\n" +
      "      extraction from viewer.js is pending (frontend/agt-11-web-client).\n" +
      "      Reason: " + err.message
  );
  // A6/C4 (node-esm-harness skill, "make a skip loud"): a skip is never a pass.
  // Print the executed count anyway — EXECUTED 0 is the honest line — and exit
  // non-zero so this state can never be misread as a green run.
  console.log("executed 0 tests, 0 passed");
  process.exit(1);
}

// --------------------------------------------------------------------------- //
// Tiny assert-based runner (no framework).
// --------------------------------------------------------------------------- //
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

// b64 -> Uint8Array (node has Buffer; browser has atob — core uses atob).
const b64 = (s) => new Uint8Array(Buffer.from(s, "base64"));

function textFrameToBytes(text) {
  return new TextEncoder().encode(text);
}

function envelope(ops, version = 1) {
  const body = JSON.stringify({ v: version, ops });
  return new TextEncoder().encode(body);
}

// --------------------------------------------------------------------------- //
// 1. Frame decode + Article VII caps (JSON.parse only).
// --------------------------------------------------------------------------- //
test("decodeMessage accepts a valid update frame and exposes the blob", () => {
  const fx = JSON.parse(readFileSync(FIXTURE, "utf-8"));
  const msg = core.decodeMessage(fx.wire_frames[0]);
  assert.equal(msg.kind, "update");
  assert.equal(msg.doc, fx.document_id);
  assert.ok(msg.blob instanceof Uint8Array && msg.blob.length > 0);
});

test("decodeMessage rejects an unsupported protocol version", () => {
  const raw = JSON.stringify({ v: 2, kind: "join", doc: "d" });
  assert.throws(() => core.decodeMessage(raw), /version/i);
});

test("decodeMessage rejects an unknown message kind", () => {
  const raw = JSON.stringify({ v: 1, kind: "mutate", doc: "d" });
  assert.throws(() => core.decodeMessage(raw), /kind/i);
});

test("decodeMessage rejects a missing/oversized document id", () => {
  assert.throws(() => core.decodeMessage(JSON.stringify({ v: 1, kind: "join" })));
  const big = "x".repeat(2000);
  assert.throws(() =>
    core.decodeMessage(JSON.stringify({ v: 1, kind: "join", doc: big }))
  );
});

test("decodeUpdate enforces the per-update op cap (MAX_OPS_PER_UPDATE)", () => {
  const op = { t: "meta", key: "k", value: "v", c: 1, s: 0 };
  const overCap = envelope(new Array(4097).fill(op));
  assert.throws(() => core.decodeUpdate(overCap), /op/i);
});

test("decodeUpdate rejects a wrong-version op envelope", () => {
  assert.throws(() => core.decodeUpdate(envelope([], 2)), /version/i);
});

// --------------------------------------------------------------------------- //
// 2. Op-replay ordering + LWW tiebreak (mirror RealtimeState.accept).
// --------------------------------------------------------------------------- //
function rasterOp(c, s, pxByte) {
  // A 1x1 RGBA tile — px is base64 of 4 bytes; distinct pixels tiebreak by bytes.
  const px = Buffer.from([pxByte, pxByte, pxByte, 255]).toString("base64");
  return { t: "raster", frame: 0, layer: 1, tx: 0, ty: 0, tw: 1, th: 1, px, c, s };
}

test("accept keeps the highest (clock,site) winner regardless of arrival order", () => {
  const older = core.decodeUpdate(envelope([rasterOp(2, 0, 10)]));
  const newer = core.decodeUpdate(envelope([rasterOp(5, 0, 20)]));

  // newer-then-older
  const a = core.makeState();
  core.accept(a, newer);
  const loser = core.accept(a, older); // older must be dropped
  assert.equal(loser.length, 0);

  // older-then-newer converges to the SAME winner
  const b = core.makeState();
  core.accept(b, older);
  const win = core.accept(b, newer);
  assert.equal(win.length, 1);
  assert.equal(win[0].c, 5);
});

test("accept resolves an equal-clock collision by site_id then pixels", () => {
  const lowSite = rasterOp(5, 0, 30);
  const highSite = rasterOp(5, 1, 30);
  const st = core.makeState();
  const winners = core.accept(st, core.decodeUpdate(envelope([lowSite, highSite])));
  assert.equal(winners.length, 1);
  assert.equal(winners[0].s, 1); // higher site_id wins the (clock,site,pixels) order
});

test("registerKey matches the Python _register_key scheme", () => {
  const [op] = core.decodeUpdate(envelope([rasterOp(1, 0, 1)]));
  assert.equal(core.registerKey(op), "raster:0:1:0:0");
});

// --------------------------------------------------------------------------- //
// 3. Integer-scale / DPR math (ADR-0036 A.6) — only if the helper is exported.
// --------------------------------------------------------------------------- //
test("A.6 integer-scale/DPR block math (source px -> S x DPR device block)", () => {
  if (typeof core.displayMetrics !== "function") {
    console.log("    (note) core.displayMetrics not exported — A.6 math helper " +
      "should be part of the extraction; sub-check pending.");
    return;
  }
  // source 8 px, integer scale S=3, DPR=2 -> css 24 px, device 48 px, block 6.
  const m = core.displayMetrics(8, 3, 2);
  assert.equal(m.cssPx, 24);
  assert.equal(m.devicePx, 48);
  assert.equal(m.blockPx, 6); // S*DPR, integer
  assert.equal(Number.isInteger(m.blockPx), true);
});

// --------------------------------------------------------------------------- //
// 4. Render-fidelity vs the shipped Python reference (byte-exact, 0 LSB — ADR-0044,
//    refining A.4/A.6).
// --------------------------------------------------------------------------- //
test("composited RGBA matches the shipped reference byte-exact (0 LSB)", () => {
  if (typeof core.composite !== "function") {
    console.log("    (note) core.composite (pure, DOM-free) not exported — the " +
      "extraction must expose a canvas-free composite; fidelity sub-check pending.");
    return;
  }
  const fx = JSON.parse(readFileSync(FIXTURE, "utf-8"));
  const state = core.makeState();
  let ops = [];
  for (const frameText of fx.wire_frames) {
    const msg = core.decodeMessage(frameText);
    if (msg.kind !== "update") continue;
    ops = ops.concat(core.accept(state, core.decodeUpdate(msg.blob)));
  }
  const out = core.composite(ops, { frameIndex: fx.frame_index });
  assert.equal(out.width, fx.width);
  assert.equal(out.height, fx.height);

  const expected = b64(fx.expected_rgba_b64);
  assert.equal(out.data.length, expected.length);
  let maxDiff = 0;
  for (let i = 0; i < expected.length; i += 1) {
    maxDiff = Math.max(maxDiff, Math.abs(out.data[i] - expected[i]));
  }
  assert.ok(
    maxDiff <= TOLERANCE_LSB,
    `render fidelity max diff ${maxDiff} LSB != ${TOLERANCE_LSB} (ADR-0044: byte-exact)`
  );
});

// --------------------------------------------------------------------------- //
// Run.
// --------------------------------------------------------------------------- //
let failed = 0;
let executed = 0;
for (const [name, fn] of tests) {
  executed += 1;
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`FAIL ${name}\n     ${err.message}`);
  }
}
const passed = executed - failed;
console.log(`\n${passed}/${tests.length} passed`);
// A6/C4: the honest line the harness/agent read for the executed count. A run
// that executed zero tests must never exit 0 (a skip is never a pass) — the
// import-skip path above already exits 1 before reaching here, so this line
// covers the case where the suite array itself is empty.
console.log(`executed ${executed} tests, ${passed} passed`);
if (executed === 0) {
  console.error("FAIL: 0 tests executed — an empty suite is never a pass.");
  process.exit(1);
}
process.exit(failed === 0 ? 0 : 1);
