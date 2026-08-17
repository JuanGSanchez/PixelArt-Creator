/* graph-view.js — memory graph viewer behaviour (FROZEN ASSET).
 *
 * Copied byte-identically into every delivered system next to
 * graph-view.html; never edited per project. Constraints:
 *   - vanilla ES5-compatible JS, no dependencies, no network access,
 *     must work from file:// (fetch() is unavailable there, which is why
 *     the data travels inline in the HTML).
 *   - data contract: the page carries the graph payload in
 *     <script type="application/json" id="graph-data">, injected by
 *     memory_viz.py in place of a block-comment __GRAPH_DATA__
 *     placeholder (see template.html for the exact marker).
 *   - determinism: every layout is a pure function of
 *     (visible node set, edge set, layout mode). Layouts always restart
 *     from a deterministically seeded state (mulberry32 keyed by the
 *     sorted visible ids) and the finished positions are cached per
 *     (mode, filter-signature), so toggling Force <-> DAG or flipping a
 *     filter back returns every node to exactly where it was.
 *
 * Sections: data loading / helpers / indexes / state / graph DOM /
 * visibility / layout determinism / force layout / DAG layout /
 * rendering / interaction / detail panel / sidebar controls /
 * status surfaces / tabs / repo view / boot.
 */
(function () {
"use strict";

/* ================================================================== */
/* data loading                                                       */
/* ================================================================== */
function fatal(message) {
  var p = document.createElement("p");
  p.style.cssText = "padding:24px;font:14px system-ui,sans-serif;";
  p.textContent = "graph-view.html could not load its data: " + message +
    " Regenerate the page with memory_viz.py.";
  document.body.innerHTML = "";
  document.body.appendChild(p);
}

var DATA;
try {
  var dataEl = document.getElementById("graph-data");
  var rawText = dataEl ? dataEl.textContent : "";
  /* an unrendered template still carries the block-comment placeholder;
   * valid JSON can never begin with a slash */
  if (/^\s*\//.test(rawText)) {
    throw new Error("the data placeholder was never rendered.");
  }
  DATA = JSON.parse(rawText);
  if (!DATA || typeof DATA !== "object") {
    throw new Error("payload is not an object.");
  }
} catch (loadErr) {
  fatal(String((loadErr && loadErr.message) || loadErr));
  return;
}

var NODES = DATA.nodes || [], RAW_EDGES = DATA.edges || [];
var META = DATA.meta || {};
/* The repository's history, as memory_viz.py collected it. `state` is
 * always set: anything other than "ok" means the History view explains
 * itself instead of drawing an empty stage. */
var GIT = DATA.git || { state: "off", commits: [] };
if (!GIT.commits) { GIT.commits = []; }
if (!GIT.base) { GIT.base = { sha: "", files: [] }; }
var N = NODES.length;
var NODE_R = 9, IDEAL = 110, CELL = 220, BUDGET = 1500;
var MIN_K = 0.05, MAX_K = 20;

/* ================================================================== */
/* generic helpers                                                    */
/* ================================================================== */
/* FNV-1a string hash - the seed base for the layout PRNG. */
function hashStr(s) {
  var h = 2166136261 >>> 0;
  for (var j = 0; j < s.length; j++) {
    h = Math.imul(h ^ s.charCodeAt(j), 16777619);
  }
  return h >>> 0;
}
/* mulberry32 - tiny deterministic PRNG; same seed, same sequence. */
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    var t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/* Deterministic palette over a sorted list of category names. */
function palette(types, sat, light) {
  var map = {}, len = Math.max(types.length, 1);
  types.forEach(function (t, k) {
    map[t] = "hsl(" + Math.round((k * 360) / len) + " " + sat + "% " +
      light + "%)";
  });
  return map;
}
function uniqSorted(list) {
  var seen = {}, out = [];
  list.forEach(function (v) {
    if (!Object.prototype.hasOwnProperty.call(seen, v)) {
      seen[v] = 1; out.push(v);
    }
  });
  return out.sort();
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

/* ================================================================== */
/* colour: perceptual space, extension palette, colormaps             */
/* ================================================================== */
/* Everything the Repo and History views paint with is decided here,
 * under two rules.
 *
 * 1. CATEGORICAL colour (file extensions) is chosen in OKLCh, not HSL.
 *    Ten family anchors sit far enough apart that all four vision types
 *    - normal, protanopia, deuteranopia, tritanopia - still tell them
 *    apart, and every registered extension is a small, deterministic
 *    offset from its family's anchor. The offsets are bounded so that a
 *    colour is always nearest its OWN anchor under every one of those
 *    four: whatever else a reader can or cannot separate, "this is a
 *    build file, that is an image" survives. Extensions the registry
 *    does not know still get their own colour rather than a shared
 *    "other" bucket - derived by splitting the widest unused arc of the
 *    hue circle, and deliberately low-chroma, so unregistered reads as
 *    unregistered instead of impersonating a family.
 *    Hue picked for variety, lightness for safety: hue is the axis
 *    dichromacy destroys, so it may not be the only thing separating
 *    two families.
 *
 * 2. CONTINUOUS colour (counts, lines changed) is the matplotlib
 *    colormap of that name - plasma, rainbow, summer - reproduced
 *    exactly rather than approximated: the same 256-entry lookup, the
 *    same index arithmetic, the same round-half-to-even at 8 bits. The
 *    test suite compares all 256 entries of each against matplotlib.
 */

/* --- OKLab / OKLCh -> sRGB (Ottosson) ------------------------------ */
/* Ties round to even, because that is what numpy/matplotlib do and a
 * colormap that disagrees on 8 of its 256 entries is not that colormap. */
function roundHalfEven(v) {
  var f = Math.floor(v), d = v - f;
  if (d > 0.5) { return f + 1; }
  if (d < 0.5) { return f; }
  return (f % 2) ? f + 1 : f;
}
function hex2(v) {
  var n = roundHalfEven(255 * Math.min(1, Math.max(0, v)));
  return (n < 16 ? "0" : "") + n.toString(16);
}
function oklabLinear(L, a, b) {
  var l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  var m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  var s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  var l = l_ * l_ * l_, m = m_ * m_ * m_, s = s_ * s_ * s_;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
}
function gammaEncode(c) {
  return c <= 0.0031308 ? 12.92 * c
    : 1.055 * Math.pow(Math.max(c, 0), 1 / 2.4) - 0.055;
}
function inGamut(rgb) {
  for (var k = 0; k < 3; k++) {
    if (rgb[k] < -0.0005 || rgb[k] > 1.0005) { return false; }
  }
  return true;
}
/* Out-of-gamut requests lose chroma until the colour exists. Clipping
 * the channels instead is what collapses two different requests onto one
 * pixel value - and with it two extensions onto one colour. */
function oklchHex(L, C, H) {
  var rad = H * Math.PI / 180;
  function at(c) { return oklabLinear(L, c * Math.cos(rad), c * Math.sin(rad)); }
  var rgb = at(C);
  if (C > 0 && !inGamut(rgb)) {
    var lo = 0, hi = C, mid;
    for (var k = 0; k < 12; k++) {
      mid = (lo + hi) / 2;
      if (inGamut(at(mid))) { lo = mid; } else { hi = mid; }
    }
    rgb = at(lo);
  }
  return "#" + hex2(gammaEncode(rgb[0])) + hex2(gammaEncode(rgb[1])) +
    hex2(gammaEncode(rgb[2]));
}

/* --- the registry -------------------------------------------------- */
/* Ten families, ordered inside each by how often the extension is met:
 * the head of the list gets the most widely separated colours (see
 * MEMBER_LATTICE), the long tail fills the gaps in between. An
 * extension listed twice keeps its first family. */
var EXT_FAMILIES = [
  { key: "systems", label: "systems & compiled",
    L: 0.72, C: 0.16, H: 62,
    exts: "c h cpp hpp cc cxx hh hxx rs go swift zig m mm d nim asm s " +
      "cu cuh ada adb ads f90 f95 f03 f08 for ftn f pas pp dpr v sv svh " +
      "vhd vhdl wat ll cl ino cbl cob ipp inl c++" },
  { key: "managed", label: "managed & functional",
    L: 0.46, C: 0.10, H: 98,
    exts: "java kt kts scala sc groovy clj cljs cljc edn cs csx fs fsi " +
      "fsx vb dart ex exs erl hrl elm hs lhs ml mli re res cr jl" },
  { key: "web", label: "web behaviour",
    L: 0.86, C: 0.14, H: 122,
    exts: "js ts jsx tsx mjs cjs mts cts vue svelte astro coffee" },
  { key: "scripting", label: "scripting & dynamic",
    L: 0.74, C: 0.10, H: 170,
    exts: "py pyi pyw pyx pxd ipynb rb rake gemspec php phtml pl pm lua " +
      "r rmd tcl awk sed sh bash zsh fish ksh csh ps1 psm1 psd1 bat cmd " +
      "vbs applescript scpt el lisp lsp scm ss rkt vim nu exp" },
  { key: "data", label: "data & config",
    L: 0.86, C: 0.15, H: 203,
    exts: "json jsonc json5 jsonl ndjson yaml yml toml ini cfg conf " +
      "config properties env csv tsv sql ddl psql prisma graphql gql " +
      "proto thrift avsc avro parquet orc arrow plist xsd dtd ron hjson " +
      "cson" },
  { key: "markup", label: "markup & style",
    L: 0.58, C: 0.11, H: 242,
    exts: "html htm xhtml xml xsl xslt svg css scss sass less styl pug " +
      "jade hbs handlebars ejs mustache twig liquid njk jinja jinja2 " +
      "haml slim erb jsp aspx ascx cshtml vbhtml razor tpl dust" },
  { key: "build", label: "build & infrastructure",
    L: 0.46, C: 0.17, H: 272,
    exts: "dockerfile containerfile makefile mk mak cmake gradle bzl " +
      "bazel nix tf tfvars hcl sbt gn gni ninja meson gyp gypi csproj " +
      "vbproj fsproj sln vcxproj podspec rockspec cabal nimble opam " +
      "spec ebuild service nomad jsonnet libsonnet cue" },
  { key: "docs", label: "documents & text",
    L: 0.74, C: 0.16, H: 302,
    exts: "md markdown mdx rst txt text adoc asciidoc asc tex sty cls " +
      "bib org rtf pdf doc docx odt epub man po pot mo srt vtt" },
  { key: "media", label: "media & assets",
    L: 0.44, C: 0.17, H: 344,
    exts: "png jpg jpeg gif webp avif bmp ico icns tif tiff psd ai eps " +
      "xcf sketch fig mp3 wav ogg flac aac m4a mid midi mp4 mov webm " +
      "avi mkv wmv ttf otf woff woff2 eot obj fbx gltf glb blend stl " +
      "dae 3ds" },
  { key: "binary", label: "binaries & archives",
    L: 0.60, C: 0.10, H: 23,
    exts: "exe dll so dylib a lib o class jar war ear pyc pyo pyd wasm " +
      "bin dat db sqlite sqlite3 mdb zip tar gz tgz bz2 xz 7z rar whl " +
      "deb rpm dmg iso apk msi cab log lock map pdb cache bak swp" }
];
/* A file with no extension is not a category, so it takes no hue. */
var NO_EXT = "(none)";
var NO_EXT_COLOR = oklchHex(0.62, 0, 0);

/* --- where a family member sits relative to its anchor -------------- */
/* Offsets in (lightness, chroma, hue). Chroma only ever decreases: the
 * anchors already sit near the edge of sRGB, and pushing past it makes
 * two different requests clip onto one colour. */
var MEMBER_L_STEP = 0.010, MEMBER_C_STEP = 0.024, MEMBER_H_STEP = 3;
var MEMBER_L_HALF = 3, MEMBER_C_HALF = 1, MEMBER_H_HALF = 2;
var MEMBER_TYPICAL_C = 0.13;
/* Walked farthest-point first, not nearest-first: the head of a family's
 * list is what a reader actually meets (.py, .c, .js), so those take the
 * most widely separated offsets and the rare tail fills in between. */
function memberLattice() {
  var span = function (half) {
    var out = [0];
    for (var i = 1; i <= half; i++) { out.push(i); out.push(-i); }
    return out.sort(function (a, b) { return a - b; });
  };
  var pts = [], ls = span(MEMBER_L_HALF), hs = span(MEMBER_H_HALF);
  for (var a = 0; a < ls.length; a++) {
    for (var c = 0; c <= MEMBER_C_HALF; c++) {
      for (var b = 0; b < hs.length; b++) { pts.push([ls[a], -c, hs[b]]); }
    }
  }
  pts.sort(function (p, q) {
    return p[0] - q[0] || p[1] - q[1] || p[2] - q[2];
  });
  function weighted(p) {
    return [p[0] * MEMBER_L_STEP, p[1] * MEMBER_C_STEP,
      p[2] * MEMBER_H_STEP * Math.PI / 180 * MEMBER_TYPICAL_C];
  }
  function gap(p, q) {
    var u = weighted(p), v = weighted(q), t = 0;
    for (var k = 0; k < 3; k++) { t += (u[k] - v[k]) * (u[k] - v[k]); }
    return Math.sqrt(t);
  }
  var out = [[0, 0, 0]];
  var rest = pts.filter(function (p) {
    return p[0] !== 0 || p[1] !== 0 || p[2] !== 0;
  });
  while (rest.length) {
    var best = 0, bestKey = null;
    for (var i = 0; i < rest.length; i++) {
      var near = Infinity;
      for (var j = 0; j < out.length; j++) {
        near = Math.min(near, gap(rest[i], out[j]));
      }
      /* rounded before comparing so the tie-break, not floating-point
       * noise, decides between two equally distant points */
      var key = [Math.round(near * 1e9), -Math.abs(rest[i][0]),
        -Math.abs(rest[i][1]), -Math.abs(rest[i][2]),
        rest[i][0], rest[i][1], rest[i][2]];
      if (bestKey === null || cmpArr(key, bestKey) > 0) {
        best = i; bestKey = key;
      }
    }
    out.push(rest[best]);
    rest.splice(best, 1);
  }
  return out;
}
function cmpArr(a, b) {
  for (var k = 0; k < a.length; k++) {
    if (a[k] !== b[k]) { return a[k] < b[k] ? -1 : 1; }
  }
  return 0;
}
var MEMBER_LATTICE = memberLattice();

var EXT_REGISTRY = Object.create(null);
var EXT_FAMILY_OF = Object.create(null);
EXT_FAMILIES.forEach(function (fam) {
  fam.list = fam.exts.split(" ");
  fam.color = oklchHex(fam.L, fam.C, fam.H);
  fam.list.forEach(function (ext, j) {
    if (hasOwn(EXT_REGISTRY, ext)) { return; }
    var p = MEMBER_LATTICE[j % MEMBER_LATTICE.length];
    EXT_REGISTRY[ext] = oklchHex(fam.L + MEMBER_L_STEP * p[0],
      Math.max(0, fam.C + MEMBER_C_STEP * p[1]),
      ((fam.H + MEMBER_H_STEP * p[2]) % 360 + 360) % 360);
    EXT_FAMILY_OF[ext] = fam.key;
  });
});
EXT_REGISTRY[NO_EXT] = NO_EXT_COLOR;

/* --- extensions the registry has never seen ------------------------ */
/* Colour theory, not a hash: each new extension takes the middle of the
 * widest arc the palette is not yet using, so the first unknown lands as
 * far from every family as the circle allows and each one after it
 * halves the largest remaining gap. Low chroma marks them as derived.
 * The result depends only on the SET of unknown extensions present (they
 * are sorted first), so the same project always renders the same
 * colours; adding a new unknown extension can move the other derived
 * ones, and never moves a registered one. */
var DERIVED_C = 0.06;
var DERIVED_L = [0.66, 0.50, 0.80, 0.58, 0.74, 0.44, 0.86];
function widestHueGap(used) {
  var sorted = used.slice().sort(function (a, b) { return a - b; });
  var best = 0, bestGap = -1;
  for (var k = 0; k < sorted.length; k++) {
    var lo = sorted[k];
    var hi = (k + 1 < sorted.length) ? sorted[k + 1] : sorted[0] + 360;
    if (hi - lo > bestGap + 1e-9) { bestGap = hi - lo; best = lo + bestGap / 2; }
  }
  return ((best % 360) + 360) % 360;
}
function deriveExtColors(exts) {
  var used = EXT_FAMILIES.map(function (f) { return f.H; });
  var out = Object.create(null);
  exts.slice().sort().forEach(function (ext, k) {
    var hue = widestHueGap(used);
    used.push(hue);
    out[ext] = oklchHex(DERIVED_L[k % DERIVED_L.length], DERIVED_C, hue);
  });
  return out;
}
/* One colour per extension, registered or not. */
function extColorMap(exts) {
  var colors = Object.create(null), unknown = [];
  uniqSorted(exts).forEach(function (ext) {
    if (hasOwn(EXT_REGISTRY, ext)) { colors[ext] = EXT_REGISTRY[ext]; }
    else { unknown.push(ext); }
  });
  var derived = deriveExtColors(unknown);
  Object.keys(derived).forEach(function (ext) { colors[ext] = derived[ext]; });
  return { colors: colors, derived: derived };
}

/* --- matplotlib colormaps ------------------------------------------ */
/* `summer` and `rainbow` are matplotlib's own channel functions sampled
 * on its own 256-entry grid (x = i * (1/255), the multiplication numpy's
 * linspace performs - i/255 differs in the last bit and that is enough
 * to flip a rounding tie). `plasma` is a listed colormap, so its 256
 * entries travel verbatim. */
var PLASMA_LUT =
  "0d088710078813078916078a19068c1b068d1d068e20068f2206902406912605912805922a05932c05942e05952f0596" +
  "31059733059735049837049938049a3a049a3c049b3e049c3f049c41049d43039e44039e46039f48039f4903a04b03a1" +
  "4c02a14e02a25002a25102a35302a35502a45601a45801a45901a55b01a55c01a65e01a66001a66100a76300a76400a7" +
  "6600a76700a86900a86a00a86c00a86e00a86f00a87100a87201a87401a87501a87701a87801a87a02a87b02a87d03a8" +
  "7e03a88004a88104a78305a78405a78606a68707a68808a68a09a58b0aa58d0ba58e0ca48f0da4910ea3920fa39410a2" +
  "9511a19613a19814a099159f9a169f9c179e9d189d9e199da01a9ca11b9ba21d9aa31e9aa51f99a62098a72197a82296" +
  "aa2395ab2494ac2694ad2793ae2892b02991b12a90b22b8fb32c8eb42e8db52f8cb6308bb7318ab83289ba3388bb3488" +
  "bc3587bd3786be3885bf3984c03a83c13b82c23c81c33d80c43e7fc5407ec6417dc7427cc8437bc9447aca457acb4679" +
  "cc4778cc4977cd4a76ce4b75cf4c74d04d73d14e72d24f71d35171d45270d5536fd5546ed6556dd7566cd8576bd9586a" +
  "da5a6ada5b69db5c68dc5d67dd5e66de5f65de6164df6263e06363e16462e26561e26660e3685fe4695ee56a5de56b5d" +
  "e66c5ce76e5be76f5ae87059e97158e97257ea7457eb7556eb7655ec7754ed7953ed7a52ee7b51ef7c51ef7e50f07f4f" +
  "f0804ef1814df1834cf2844bf3854bf3874af48849f48948f58b47f58c46f68d45f68f44f79044f79143f79342f89441" +
  "f89540f9973ff9983ef99a3efa9b3dfa9c3cfa9e3bfb9f3afba139fba238fca338fca537fca636fca835fca934fdab33" +
  "fdac33fdae32fdaf31fdb130fdb22ffdb42ffdb52efeb72dfeb82cfeba2cfebb2bfebd2afebe2afec029fdc229fdc328" +
  "fdc527fdc627fdc827fdca26fdcb26fccd25fcce25fcd025fcd225fbd324fbd524fbd724fad824fada24f9dc24f9dd25" +
  "f8df25f8e125f7e225f7e425f6e626f6e826f5e926f5eb27f4ed27f3ee27f3f027f2f227f1f426f1f525f0f724f0f921";
var CMAP_STEP = 1 / 255;
var CMAP_NAMES = ["plasma", "rainbow", "summer"];
/* matplotlib maps a float onto the 256-entry table with int(x * N); 1.0
 * would land one past the end and is clamped, and anything NaN/negative
 * takes the first entry. */
function cmapIndex(t) {
  if (!(t > 0)) { return 0; }
  if (t >= 1) { return 255; }
  return Math.floor(t * 256);
}
function cmapHex(name, t) {
  var i = cmapIndex(t), x = i * CMAP_STEP;
  if (name === "plasma") { return "#" + PLASMA_LUT.substr(i * 6, 6); }
  if (name === "rainbow") {
    return "#" + hex2(Math.min(1, Math.abs(2 * x - 0.5))) +
      hex2(Math.sin(Math.PI * x)) + hex2(Math.cos(Math.PI * x / 2));
  }
  if (name === "summer") {
    return "#" + hex2(x) + hex2(0.5 + 0.5 * x) + hex2(0.4);
  }
  return NO_EXT_COLOR;
}
/* A single observed value is not a range: it sits mid-scale rather than
 * pinning one end and telling the reader something the data does not. */
function cmapNorm(value, lo, hi) {
  if (!(hi > lo)) { return 0.5; }
  return (value - lo) / (hi - lo);
}

/* Read-only seam for the test suite. The colour rules are pure functions
 * with no DOM; asserting them through rendered SVG attributes would test
 * the renderer instead. Nothing in this page reads it back. */
window.graphViewColor = {
  oklchHex: oklchHex, cmapHex: cmapHex, cmapNorm: cmapNorm,
  cmapIndex: cmapIndex, cmapNames: CMAP_NAMES,
  families: EXT_FAMILIES, registry: EXT_REGISTRY, familyOf: EXT_FAMILY_OF,
  extColorMap: extColorMap, lattice: MEMBER_LATTICE, noExt: NO_EXT
};

/* ================================================================== */
/* indexes (built once)                                               */
/* ================================================================== */
/* NODES arrive sorted by id from memory_viz.py, so index order is id
 * order everywhere below - the backbone of the layout determinism. */
var IDX = Object.create(null);
for (var i = 0; i < N; i++) { IDX[NODES[i].id] = i; }
var EDGES = [], SELF_LOOPS = 0, ORPHAN_EDGES = 0;
for (i = 0; i < RAW_EDGES.length; i++) {
  var e = RAW_EDGES[i];
  var s = IDX[e.src], d = IDX[e.dst];
  /* An endpoint that is not in the payload cannot be drawn — but it must not
   * vanish without a word either. `verify` calls this a dangling edge, so a
   * page that silently omits it disagrees with the gate about what is in the
   * store; the count is surfaced in the status line. */
  if (s === undefined || d === undefined) { ORPHAN_EDGES++; continue; }
  if (s === d) { SELF_LOOPS++; }
  EDGES.push({ e: e, s: s, d: d, self: s === d });
}
var superseded = Object.create(null);
for (i = 0; i < EDGES.length; i++) {
  var ee = EDGES[i].e;
  if (ee.type === "supersedes" && !ee.invalid_at) {
    superseded[ee.dst] = ee.src;
  }
}
var DEG = new Int32Array(N);
for (i = 0; i < EDGES.length; i++) { DEG[EDGES[i].s]++; DEG[EDGES[i].d]++; }

/* searchable text, indexed once */
var SEARCH = new Array(N);
for (i = 0; i < N; i++) {
  var n = NODES[i];
  var tags = (n.props && n.props.tags) || "";
  if (Object.prototype.toString.call(tags) === "[object Array]") {
    tags = tags.join(" ");
  }
  SEARCH[i] = [n.id, n.name, n.summary, n.type, n.path, tags]
    .filter(Boolean).join(" ").toLowerCase();
}

var nodeTypes = uniqSorted(NODES.map(function (nn) {
  return nn.type || "unknown";
}));
var edgeTypes = uniqSorted(EDGES.map(function (x) {
  return x.e.type || "unknown";
}));
var nodeColor = palette(nodeTypes, 62, 46);
var edgeColor = palette(edgeTypes, 45, 58);

/* ================================================================== */
/* state                                                              */
/* ================================================================== */
/* Simulation state on plain typed arrays. */
var PX = new Float64Array(N), PY = new Float64Array(N);
var DXA = new Float64Array(N), DYA = new Float64Array(N);
var VIS = new Uint8Array(N), MATCH = new Uint8Array(N);
var W = 900, H = 700;

var state = {
  tab: "graph",
  layout: "force", query: "", types: {}, edgeOn: {}, showInvalid: false,
  selected: null, tx: 0, ty: 0, k: 1, ackBudget: false, overBudget: false,
  visibleCount: 0, visibleEdges: 0,
  repo: { tx: 0, ty: 0, k: 1, builtFor: null, root: null, leafCount: 0,
          dirCount: 0, mode: "type", range: null },
  history: { tx: 0, ty: 0, k: 1, builtFor: null, root: null, commit: null,
             range: null }
};
nodeTypes.forEach(function (t) { state.types[t] = true; });
edgeTypes.forEach(function (t) { state.edgeOn[t] = true; });

/* ================================================================== */
/* graph SVG scaffolding                                              */
/* ================================================================== */
var NS = "http://www.w3.org/2000/svg";
var svg = document.getElementById("svg");
var viewport = document.getElementById("viewport");
var gEdges = document.getElementById("gEdges");
var gNodes = document.getElementById("gNodes");
var defs = document.getElementById("defs");
var MARKER_W = 8;
/* markerUnits=userSpaceOnUse + radius-derived refX keeps arrowheads on
 * the node rim at every zoom level. */
var REF_X = (NODE_R + 3) / (MARKER_W / 10);
var arrowIdx = {};
edgeTypes.forEach(function (t, k) {
  arrowIdx[t] = k;
  var m = document.createElementNS(NS, "marker");
  m.setAttribute("id", "arrow" + k);
  m.setAttribute("viewBox", "0 0 10 10");
  m.setAttribute("refX", String(REF_X));
  m.setAttribute("refY", "5");
  m.setAttribute("markerUnits", "userSpaceOnUse");
  m.setAttribute("markerWidth", String(MARKER_W));
  m.setAttribute("markerHeight", String(MARKER_W));
  m.setAttribute("orient", "auto-start-reverse");
  var p = document.createElementNS(NS, "path");
  p.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  p.setAttribute("fill", edgeColor[t]);
  m.appendChild(p); defs.appendChild(m);
});

var edgeEls = EDGES.map(function (x) {
  var g = document.createElementNS(NS, "g");
  g.setAttribute("class", "edge");
  var p = document.createElementNS(NS, "path");
  p.setAttribute("stroke", edgeColor[x.e.type || "unknown"]);
  p.setAttribute("marker-end", "url(#arrow" +
    arrowIdx[x.e.type || "unknown"] + ")");
  var title = document.createElementNS(NS, "title");
  title.textContent = x.e.src + " -" + x.e.type + "-> " + x.e.dst;
  g.appendChild(p); g.appendChild(title); gEdges.appendChild(g);
  return { x: x, g: g, p: p, vis: true, cls: "edge", d: "" };
});
var nodeEls = NODES.map(function (nn, k) {
  var g = document.createElementNS(NS, "g");
  g.setAttribute("class", "node");
  g.setAttribute("tabindex", "0");
  g.setAttribute("role", "button");
  g.setAttribute("aria-label", nn.name || nn.id);
  var c = document.createElementNS(NS, "circle");
  c.setAttribute("r", String(NODE_R));
  c.setAttribute("fill", nodeColor[nn.type || "unknown"]);
  var label = document.createElementNS(NS, "text");
  label.setAttribute("dx", String(NODE_R + 3));
  label.setAttribute("dy", "4");
  label.textContent = nn.name || nn.id;
  var title = document.createElementNS(NS, "title");
  title.textContent = nn.id + (nn.invalid_at ? " [invalidated]" : "") +
    (hasOwn(superseded, nn.id) ? " [superseded]" : "");
  g.appendChild(c); g.appendChild(label); g.appendChild(title);
  attachNodeHandlers(g, k);
  gNodes.appendChild(g);
  return { i: k, g: g, vis: true, cls: "node", tr: "" };
});

/* ================================================================== */
/* visibility + filtering                                             */
/* ================================================================== */
function isInvalid(k) { return !!NODES[k].invalid_at; }
function edgeEnabled(x) { return !!state.edgeOn[x.e.type || "unknown"]; }
function edgeVisible(x) {
  return VIS[x.s] === 1 && VIS[x.d] === 1 && edgeEnabled(x);
}
function computeVisible() {
  var pre = [], k;
  for (k = 0; k < N; k++) {
    var nn = NODES[k];
    var ok = !!state.types[nn.type || "unknown"] &&
      (state.showInvalid || !nn.invalid_at);
    VIS[k] = ok ? 1 : 0;
    if (ok) { pre.push(k); }
  }
  state.overBudget = pre.length > BUDGET;
  var vis = pre;
  if (state.overBudget && !state.ackBudget) {
    /* degree-ranked top-N keeps huge graphs responsive */
    var ranked = pre.slice().sort(function (a, b) {
      if (DEG[b] !== DEG[a]) { return DEG[b] - DEG[a]; }
      return NODES[a].id < NODES[b].id ? -1 : 1;
    }).slice(0, BUDGET);
    for (k = 0; k < N; k++) { VIS[k] = 0; }
    ranked.forEach(function (idx) { VIS[idx] = 1; });
    vis = ranked.slice().sort(function (a, b) { return a - b; });
  }
  state.visibleCount = vis.length;
  var ec = 0;
  for (k = 0; k < EDGES.length; k++) {
    if (edgeVisible(EDGES[k])) { ec++; }
  }
  state.visibleEdges = ec;
  updateBanner(pre.length);
  updateStats();
  updateEmpty();
  return vis;
}
function applyQuery() {
  var q = state.query;
  for (var k = 0; k < N; k++) {
    MATCH[k] = (!q || SEARCH[k].indexOf(q) !== -1) ? 1 : 0;
  }
}
applyQuery();

/* ================================================================== */
/* layout determinism: signature + position cache                     */
/* ================================================================== */
/* A layout is a pure function of (mode, visible node set, edge set).
 * The signature captures exactly those inputs; finished positions are
 * cached under it, so re-entering an already-seen configuration (mode
 * toggle, filter round-trip) restores identical coordinates instantly.
 * Node drags mutate PX/PY only until the next relayout - they are a
 * transient user override, never part of the layout function. */
function layoutSig(vis) {
  var h = 2166136261 >>> 0;
  for (var k = 0; k < vis.length; k++) {
    h = Math.imul(h ^ hashStr(NODES[vis[k]].id), 16777619) >>> 0;
  }
  var eon = [];
  edgeTypes.forEach(function (t) { if (state.edgeOn[t]) { eon.push(t); } });
  return state.layout + "|" + (state.showInvalid ? 1 : 0) + "|" +
    vis.length + ":" + h + "|" + eon.join(",");
}
var LAYOUT_CACHE = Object.create(null);
function cachePositions(sig, vis) {
  var buf = new Float64Array(vis.length * 2);
  for (var k = 0; k < vis.length; k++) {
    buf[k * 2] = PX[vis[k]]; buf[k * 2 + 1] = PY[vis[k]];
  }
  LAYOUT_CACHE[sig] = buf;
}
function applyCached(sig, vis) {
  var buf = LAYOUT_CACHE[sig];
  if (!buf || buf.length !== vis.length * 2) { return false; }
  for (var k = 0; k < vis.length; k++) {
    PX[vis[k]] = buf[k * 2]; PY[vis[k]] = buf[k * 2 + 1];
  }
  return true;
}
/* Seed every visible node from scratch: same signature, same start. */
function seedPositions(vis, sig) {
  var rnd = mulberry32(hashStr(sig) || 1);
  for (var k = 0; k < vis.length; k++) {
    PX[vis[k]] = W / 2 + (rnd() - 0.5) * W * 0.8;
    PY[vis[k]] = H / 2 + (rnd() - 0.5) * H * 0.8;
  }
}

/* ================================================================== */
/* force layout (spatial-grid repulsion, animated but deterministic)  */
/* ================================================================== */
var layoutGen = 0, rafId = 0;
function cancelLayout() {
  if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
  layoutGen++;
}
function visibleLinks() {
  var out = [];
  for (var k = 0; k < EDGES.length; k++) {
    var x = EDGES[k];
    if (x.self || !edgeVisible(x)) { continue; }
    /* invalidated edges still anchor their endpoints, weakly */
    out.push({ s: x.s, d: x.d, w: x.e.invalid_at ? 0.008 : 0.02 });
  }
  return out;
}
function step(vis, links) {
  var m = vis.length, k, a, b, dx, dy, d2, dd, f;
  for (k = 0; k < m; k++) { a = vis[k]; DXA[a] = 0; DYA[a] = 0; }
  /* uniform spatial grid: repulsion only within the 3x3 neighbourhood */
  var buckets = {}, gx, gy, key;
  for (k = 0; k < m; k++) {
    a = vis[k];
    gx = Math.floor(PX[a] / CELL); gy = Math.floor(PY[a] / CELL);
    key = gx + ":" + gy;
    if (!buckets[key]) { buckets[key] = []; }
    buckets[key].push(a);
  }
  for (k = 0; k < m; k++) {
    a = vis[k];
    gx = Math.floor(PX[a] / CELL); gy = Math.floor(PY[a] / CELL);
    for (var ox = -1; ox <= 1; ox++) {
      for (var oy = -1; oy <= 1; oy++) {
        var arr = buckets[(gx + ox) + ":" + (gy + oy)];
        if (!arr) { continue; }
        for (var t = 0; t < arr.length; t++) {
          b = arr[t];
          if (b === a) { continue; }
          dx = PX[b] - PX[a]; dy = PY[b] - PY[a];
          d2 = dx * dx + dy * dy;
          if (d2 < 0.01) {
            /* deterministic jitter for coincident points */
            dx = ((a % 7) - 3) * 0.1 + 0.1; dy = ((a % 5) - 2) * 0.1 + 0.1;
            d2 = dx * dx + dy * dy;
          }
          dd = Math.sqrt(d2);
          f = Math.min(2200 / d2, 6);
          DXA[a] -= (dx / dd) * f; DYA[a] -= (dy / dd) * f;
        }
      }
    }
  }
  for (k = 0; k < links.length; k++) {
    var L = links[k]; a = L.s; b = L.d;
    dx = PX[b] - PX[a]; dy = PY[b] - PY[a];
    dd = Math.sqrt(dx * dx + dy * dy) || 0.01;
    f = (dd - IDEAL) * L.w;
    DXA[a] += (dx / dd) * f; DYA[a] += (dy / dd) * f;
    DXA[b] -= (dx / dd) * f; DYA[b] -= (dy / dd) * f;
  }
  var cx = 0, cy = 0;
  for (k = 0; k < m; k++) { cx += PX[vis[k]]; cy += PY[vis[k]]; }
  cx /= (m || 1); cy /= (m || 1);
  var gxp = (W / 2 - cx) * 0.05, gyp = (H / 2 - cy) * 0.05;
  var maxDisp = 0;
  for (k = 0; k < m; k++) {
    a = vis[k];
    dx = DXA[a] + gxp; dy = DYA[a] + gyp;
    var mag = Math.sqrt(dx * dx + dy * dy);
    if (mag > 30) { dx = dx * 30 / mag; dy = dy * 30 / mag; mag = 30; }
    PX[a] += dx; PY[a] += dy;
    if (mag > maxDisp) { maxDisp = mag; }
  }
  return maxDisp;
}
function forceLayout() {
  cancelLayout();
  var myGen = layoutGen;
  var vis = computeVisible();
  if (!vis.length) { positionAll(); return; }
  var sig = layoutSig(vis);
  if (applyCached(sig, vis)) { positionAll(); fit(); return; }
  seedPositions(vis, sig);
  var links = visibleLinks();
  var maxTicks = 120;   /* fixed cap: same inputs, same tick sequence */
  var ticks = 0;
  function tick() {
    rafId = 0;
    if (myGen !== layoutGen || state.layout !== "force") { return; }
    var disp = step(vis, links);
    ticks++;
    if (ticks % 3 === 0) { positionAll(); }   /* DOM every 3rd tick */
    if (disp < 0.5 || ticks >= maxTicks) {    /* energy threshold */
      cachePositions(sig, vis);
      positionAll();
      fit();
      return;
    }
    rafId = requestAnimationFrame(tick);
  }
  positionAll();
  rafId = requestAnimationFrame(tick);
}

/* ================================================================== */
/* DAG layout (layered, deterministic by construction)                */
/* ================================================================== */
function dagLayout() {
  cancelLayout();
  var vis = computeVisible();
  if (!vis.length) { positionAll(); return; }
  var sig = layoutSig(vis);
  if (applyCached(sig, vis)) { positionAll(); fit(); return; }
  var inSet = Object.create(null);
  vis.forEach(function (k) { inSet[k] = true; });
  var links = [];
  for (var k = 0; k < EDGES.length; k++) {
    var x = EDGES[k];
    if (x.self || x.e.invalid_at || !edgeEnabled(x) ||
        !inSet[x.s] || !inSet[x.d]) { continue; }
    links.push(x);
  }
  var indeg = {}, out = {}, preds = {};
  vis.forEach(function (a) { indeg[a] = 0; out[a] = []; preds[a] = []; });
  links.forEach(function (x) {
    indeg[x.d]++; out[x.s].push(x.d); preds[x.d].push(x.s);
  });
  var layer = {}, queue = [], remaining = {}, settled = {};
  vis.forEach(function (a) {
    remaining[a] = indeg[a];
    if (!indeg[a]) { queue.push(a); settled[a] = true; layer[a] = 0; }
  });
  var head = 0;
  while (head < queue.length) {
    var u = queue[head++];
    out[u].forEach(function (v) {
      layer[v] = Math.max(layer[v] === undefined ? 0 : layer[v],
        layer[u] + 1);
      if (--remaining[v] === 0) { queue.push(v); settled[v] = true; }
    });
  }
  /* resolved layers first, THEN one condensed layer for cycle members:
   * a node reached from outside a cycle may carry a layer without being
   * settled, so liveness is decided by `settled`, not by `layer`. */
  var maxResolved = 0, hasResolved = false, unresolved = [];
  vis.forEach(function (a) {
    if (!settled[a]) { unresolved.push(a); return; }
    hasResolved = true;
    if (layer[a] > maxResolved) { maxResolved = layer[a]; }
  });
  var cycleLayer = maxResolved;
  if (unresolved.length && hasResolved) { cycleLayer = maxResolved + 1; }
  unresolved.forEach(function (a) { layer[a] = cycleLayer; });
  var layers = [];
  for (var L = 0; L <= cycleLayer; L++) { layers.push([]); }
  vis.slice().sort(function (a, b) {
    return NODES[a].id < NODES[b].id ? -1 : 1;
  }).forEach(function (a) { layers[layer[a]].push(a); });
  /* one median-heuristic sweep to cut crossings */
  for (L = 1; L < layers.length; L++) {
    var pos = Object.create(null);
    layers[L - 1].forEach(function (a, ii) { pos[a] = ii; });
    var keyed = layers[L].map(function (a, ii) {
      var ps = preds[a].map(function (p) { return pos[p]; })
        .filter(function (v) { return v !== undefined; })
        .sort(function (p, q) { return p - q; });
      var med = ii;
      if (ps.length) {
        med = ps.length % 2 ? ps[(ps.length - 1) / 2] :
          (ps[ps.length / 2 - 1] + ps[ps.length / 2]) / 2;
      }
      return { a: a, med: med, ii: ii };
    });
    keyed.sort(function (p, q) { return p.med - q.med || p.ii - q.ii; });
    layers[L] = keyed.map(function (p) { return p.a; });
  }
  layers.forEach(function (arr, Li) {
    arr.forEach(function (a, ii) {
      PX[a] = 120 + Li * 220;
      PY[a] = H / 2 + (ii - (arr.length - 1) / 2) * 64;  /* centred */
    });
  });
  cachePositions(sig, vis);
  positionAll();
  fit();
}
function relayout() {
  if (state.layout === "force") { forceLayout(); } else { dagLayout(); }
}

/* ================================================================== */
/* graph rendering                                                    */
/* ================================================================== */
function selfLoopPath(x, y) {
  return "M " + (x + 4).toFixed(1) + " " + (y - 7).toFixed(1) +
    " A 11 11 0 1 1 " + (x - 4).toFixed(1) + " " + (y - 7).toFixed(1);
}
function positionAll() {
  var k, el;
  for (k = 0; k < N; k++) {
    el = nodeEls[k];
    var v = VIS[k] === 1;
    if (el.vis !== v) { el.g.style.display = v ? "" : "none"; el.vis = v; }
    if (!v) { continue; }
    var tr = "translate(" + PX[k].toFixed(1) + "," + PY[k].toFixed(1) + ")";
    if (el.tr !== tr) { el.g.setAttribute("transform", tr); el.tr = tr; }
    var cls = "node";
    if (NODES[k].invalid_at || hasOwn(superseded, NODES[k].id)) {
      cls += " dimmed";
    }
    if (!MATCH[k]) { cls += " faded"; }
    if (state.selected === NODES[k].id) { cls += " selected"; }
    if (el.cls !== cls) { el.g.setAttribute("class", cls); el.cls = cls; }
  }
  for (k = 0; k < edgeEls.length; k++) {
    el = edgeEls[k];
    var x = el.x;
    var ev = edgeVisible(x);
    if (el.vis !== ev) { el.g.style.display = ev ? "" : "none"; el.vis = ev; }
    if (!ev) { continue; }
    var dstr = x.self ? selfLoopPath(PX[x.s], PY[x.s]) :
      "M " + PX[x.s].toFixed(1) + " " + PY[x.s].toFixed(1) + " L " +
      PX[x.d].toFixed(1) + " " + PY[x.d].toFixed(1);
    if (el.d !== dstr) { el.p.setAttribute("d", dstr); el.d = dstr; }
    var ecls = "edge";
    if (x.e.invalid_at || isInvalid(x.s) || isInvalid(x.d)) {
      ecls += " dimmed";
    }
    if (!MATCH[x.s] && !MATCH[x.d]) { ecls += " faded"; }
    if (el.cls !== ecls) { el.g.setAttribute("class", ecls); el.cls = ecls; }
  }
}
function applyTransform() {
  viewport.setAttribute("transform", "translate(" + state.tx.toFixed(2) +
    "," + state.ty.toFixed(2) + ") scale(" + state.k.toFixed(4) + ")");
}
function clampK(k) { return Math.max(MIN_K, Math.min(MAX_K, k)); }
function fit() {
  var pts = [], k;
  for (k = 0; k < N; k++) {
    if (VIS[k] && !NODES[k].invalid_at) { pts.push(k); }
  }
  if (!pts.length) {
    for (k = 0; k < N; k++) { if (VIS[k]) { pts.push(k); } }
  }
  if (!pts.length) { return; }
  var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (k = 0; k < pts.length; k++) {   /* reduce loop: no variadic spread */
    var px = PX[pts[k]], py = PY[pts[k]];
    if (px < minX) { minX = px; }
    if (px > maxX) { maxX = px; }
    if (py < minY) { minY = py; }
    if (py > maxY) { maxY = py; }
  }
  minX -= 60; maxX += 160; minY -= 60; maxY += 60;
  var bw = svg.clientWidth || 800, bh = svg.clientHeight || 600;
  state.k = clampK(Math.min(bw / (maxX - minX || 1),
    bh / (maxY - minY || 1), 1.6));
  state.tx = (bw - (maxX + minX) * state.k) / 2;
  state.ty = (bh - (maxY + minY) * state.k) / 2;
  applyTransform();
}

/* ================================================================== */
/* graph interaction: pan, zoom, node drag                            */
/* ================================================================== */
var panning = null, dragging = null, suppressClick = false;
function toGraph(ev) {
  var rect = svg.getBoundingClientRect();
  return {
    x: (ev.clientX - rect.left - state.tx) / state.k,
    y: (ev.clientY - rect.top - state.ty) / state.k
  };
}
svg.addEventListener("pointerdown", function (ev) {
  if (dragging) { return; }
  /* A fresh press always starts from a clean slate: a suppression flag left
   * over from an interaction whose click never arrived must not swallow this
   * one. */
  suppressClick = false;
  panning = { x: ev.clientX, y: ev.clientY, tx: state.tx, ty: state.ty,
    moved: false, id: ev.pointerId };
  svg.classList.add("panning");
  try { svg.setPointerCapture(ev.pointerId); } catch (err) { /* ignore */ }
});
svg.addEventListener("pointermove", function (ev) {
  if (dragging) {
    /* transient user override; the next relayout recomputes it away */
    var p = toGraph(ev);
    PX[dragging.i] = p.x - dragging.ox;
    PY[dragging.i] = p.y - dragging.oy;
    if (Math.abs(ev.clientX - dragging.cx) +
        Math.abs(ev.clientY - dragging.cy) > 3) { dragging.moved = true; }
    positionAll();
    return;
  }
  if (!panning) { return; }
  var dx = ev.clientX - panning.x, dy = ev.clientY - panning.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) { panning.moved = true; }
  state.tx = panning.tx + dx; state.ty = panning.ty + dy;
  applyTransform();
});
function endPointer(ev) {
  if (dragging) {
    if (!dragging.moved) { select(NODES[dragging.i].id); }
    /* Selection is decided HERE, on pointerup, where the target is
     * unambiguous — never on the click that follows. While a pointer capture
     * taken on pointerdown is in effect, browsers deliver that click to the
     * capture element (this <svg>) rather than to the node group, so the
     * node's own stopPropagation never runs and the background handler below
     * would clear the selection the instant it was made. Suppressing the
     * click covers both deliveries; the next pointerdown clears the flag, so
     * a click that DID reach the node cannot swallow a later background one. */
    suppressClick = true;
    try { svg.releasePointerCapture(ev.pointerId); } catch (err) { /* ok */ }
    dragging = null;
    positionAll();
    return;
  }
  if (panning) {
    if (panning.moved) { suppressClick = true; }
    try { svg.releasePointerCapture(ev.pointerId); } catch (err) { /* ok */ }
    panning = null;
    svg.classList.remove("panning");
  }
}
svg.addEventListener("pointerup", endPointer);
svg.addEventListener("pointercancel", endPointer);
svg.addEventListener("click", function () {
  if (suppressClick) { suppressClick = false; return; }
  select(null);
});
svg.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  var nk = clampK(state.k * factor);
  factor = nk / state.k;
  var rect = svg.getBoundingClientRect();
  var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  state.tx = mx - (mx - state.tx) * factor;
  state.ty = my - (my - state.ty) * factor;
  state.k = nk;
  applyTransform();
}, { passive: false });

function attachNodeHandlers(g, k) {
  g.addEventListener("pointerdown", function (ev) {
    ev.stopPropagation();
    suppressClick = false;      /* same clean slate as a background press */
    var p = toGraph(ev);
    dragging = { i: k, ox: p.x - PX[k], oy: p.y - PY[k], moved: false,
      cx: ev.clientX, cy: ev.clientY };
    try { svg.setPointerCapture(ev.pointerId); } catch (err) { /* ignore */ }
  });
  g.addEventListener("click", function (ev) { ev.stopPropagation(); });
  g.addEventListener("keydown", function (ev) {  /* Enter/Space selects */
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault(); ev.stopPropagation(); select(NODES[k].id);
    }
  });
}

/* ================================================================== */
/* detail panel                                                       */
/* ================================================================== */
function inlineMd(s) {
  var t = esc(s);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return t;
}
function renderCard(src) {
  var lines = String(src).replace(/\r\n/g, "\n").split("\n");
  var out = [], inCode = false, listOpen = false, j, line, m;
  function closeList() {
    if (listOpen) { out.push("</ul>"); listOpen = false; }
  }
  function openList() {
    if (!listOpen) { out.push("<ul>"); listOpen = true; }
  }
  var start = 0;
  if (lines[0] === "---") {
    var end = -1;
    for (j = 1; j < lines.length; j++) {
      if (lines[j] === "---") { end = j; break; }
    }
    if (end > 0) {
      out.push('<div class="fm">');
      for (j = 1; j < end; j++) {
        if (lines[j].trim()) {
          out.push("<span>" + esc(lines[j]) + "</span>");
        }
      }
      out.push("</div>");
      start = end + 1;
    }
  }
  for (j = start; j < lines.length; j++) {
    line = lines[j];
    if (line.indexOf("```") === 0) {
      if (inCode) { out.push("</code></pre>"); inCode = false; }
      else {
        closeList(); out.push('<pre class="code"><code>'); inCode = true;
      }
      continue;
    }
    if (inCode) { out.push(esc(line)); continue; }
    if (!line.trim()) { closeList(); continue; }
    m = /^(#{1,6})\s+(.*)$/.exec(line);
    if (m) {
      closeList(); out.push("<h4>" + inlineMd(m[2]) + "</h4>"); continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
      closeList(); out.push("<hr>"); continue;
    }
    m = /^\s*[-*+]\s+(.*)$/.exec(line) || /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (m) {
      openList(); out.push("<li>" + inlineMd(m[1]) + "</li>"); continue;
    }
    m = /^\s*>\s?(.*)$/.exec(line);
    if (m) {
      closeList();
      out.push("<blockquote>" + inlineMd(m[1]) + "</blockquote>");
      continue;
    }
    closeList();
    out.push("<p>" + inlineMd(line) + "</p>");
  }
  if (inCode) { out.push("</code></pre>"); }
  closeList();
  return out.join("\n");
}
function detailPlaceholder() {
  return '<p class="muted">Select a node (click, or Tab + Enter) to ' +
    "inspect its fields, card and linked nodes.</p>";
}
function select(id) {
  state.selected = id;
  var body = document.getElementById("detailBody");
  if (id === null || id === undefined || IDX[id] === undefined) {
    state.selected = null;
    body.innerHTML = detailPlaceholder();
    positionAll();
    repoRestyle();
    return;
  }
  var n = NODES[IDX[id]];
  var props = n.props || {};
  var html = "<h2>" + esc(n.name || n.id) + "</h2>";
  html += '<div><span class="badge">' + esc(n.type || "unknown") + "</span>";
  if (n.invalid_at) { html += '<span class="badge warn">invalidated</span>'; }
  if (hasOwn(superseded, n.id)) {
    html += '<span class="badge warn">superseded by ' +
      esc(superseded[n.id]) + "</span>";
  }
  html += "</div><dl>";
  [["id", n.id], ["path", n.path], ["summary", n.summary],
   ["source", n.source], ["episode", n.episode],
   ["created_at", n.created_at], ["invalid_at", n.invalid_at],
   ["confidence", props.confidence],
   ["last_confirmed", props.last_confirmed],
   ["card", n.card]].forEach(function (kv) {
    if (kv[1] !== undefined && kv[1] !== null && kv[1] !== "") {
      html += "<dt>" + esc(kv[0]) + "</dt><dd>" + esc(kv[1]) + "</dd>";
    }
  });
  html += "</dl>";                    /* props block stays OUTSIDE the dl */
  if (Object.keys(props).length) {
    html += "<h2>props</h2><pre class='props'>" +
      esc(JSON.stringify(props, null, 2)) + "</pre>";
  }
  if (n.card_body) {
    html += "<h2>card" + (n.card_truncated ? " (truncated)" : "") +
      "</h2>" + '<div class="card">' + renderCard(n.card_body) + "</div>";
  }
  /* What the Repo view draws when this file is selected, named. A curve
   * across a packed map tells you THAT two files are related; only the
   * list tells you which file, which way round, and by what. */
  if (hasOwn(STRUCTURAL, n.type) && typeof n.path === "string" && n.path) {
    var conn = repoConnections(IDX[id]);
    if (conn.length) {
      var outgoing = conn.filter(function (c) { return c.outgoing; });
      var incoming = conn.filter(function (c) { return !c.outgoing; });
      var external = conn.filter(function (c) { return c.external; });
      html += "<h2>Connections (" + conn.length + ")</h2>";
      html += '<p class="conn-sum">' + outgoing.length +
        " outgoing · " + incoming.length + " incoming" +
        (external.length ? " · " + external.length + " outside the tree" : "")
        + "</p>";
      [["out", "→ this file depends on", outgoing],
        ["in", "← depends on this file", incoming]].forEach(function (group) {
        if (!group[2].length) { return; }
        html += '<div class="conn-group conn-' + group[0] + '">' +
          '<div class="conn-head">' + esc(group[1]) + "</div>";
        group[2].forEach(function (link) {
          /* Aggregated: `×12` is twelve edges between the same two files,
           * which is one relationship and one curve. An endpoint outside
           * the file tree has no circle to link to, so it is named rather
           * than made clickable. */
          var many = link.count > 1 ? " ×" + link.count : "";
          html += '<div class="rel"><span class="etype">' + esc(link.type) +
            many + (link.invalid ? " (invalidated)" : "") + "</span> ";
          if (link.external) {
            html += '<span class="muted">' + esc(link.label) +
              " (outside the tree)</span>";
          } else {
            html += '<a class="nlink" href="#" data-id="' +
              esc(NODES[link.other].id) + '">' + esc(link.label) + "</a>";
          }
          html += "</div>";
        });
        html += "</div>";
      });
    }
  }
  var rels = EDGES.filter(function (x) {
    return x.e.src === id || x.e.dst === id;
  });
  if (rels.length) {
    html += "<h2>Linked (" + rels.length + ")</h2>";
    rels.forEach(function (x) {
      var other = x.e.src === id ? x.e.dst : x.e.src;
      var dir = x.e.src === id ? "→" : "←";
      var on = NODES[IDX[other]];
      html += '<div class="rel"><span class="etype">' + dir + " " +
        esc(x.e.type) + (x.e.invalid_at ? " (invalidated)" : "") +
        "</span> " +
        '<a class="nlink" href="#" data-id="' + esc(other) + '">' +
        esc(on ? (on.name || on.id) : other) + "</a></div>";
    });
  }
  body.innerHTML = html;
  Array.prototype.forEach.call(body.querySelectorAll("a.nlink"),
    function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        select(a.getAttribute("data-id"));
      });
    });
  positionAll();
  repoRestyle();
}
/* Directory circles have no graph node; show a lightweight summary. */
function showDirDetail(dir) {
  var body = document.getElementById("detailBody");
  /* The reader has asked about a directory, so the file they had chosen
   * is no longer the subject — leaving its curves drawn under a panel
   * describing something else is the page contradicting itself. */
  state.selected = null;
  repoRestyle();
  var html = "<h2>" + esc(dir.name || "(repository root)") + "</h2>";
  html += '<div><span class="badge">directory</span></div><dl>';
  if (dir.path) { html += "<dt>path</dt><dd>" + esc(dir.path) + "</dd>"; }
  html += "<dt>subdirectories</dt><dd>" + dir.nDirs + "</dd>";
  html += "<dt>files (recursive)</dt><dd>" + dir.nLeaves + "</dd>";
  html += "</dl>";
  body.innerHTML = html;
}

/* ================================================================== */
/* sidebar controls                                                   */
/* ================================================================== */
var tf = document.getElementById("typeFilters");
nodeTypes.forEach(function (t) {
  var lbl = document.createElement("label");
  lbl.className = "type";
  var cb = document.createElement("input");
  cb.type = "checkbox"; cb.checked = true;
  cb.addEventListener("change", function () {
    state.types[t] = cb.checked;
    relayout();
  });
  var sw = document.createElement("span");
  sw.className = "swatch"; sw.style.background = nodeColor[t];
  lbl.appendChild(cb); lbl.appendChild(sw);
  lbl.appendChild(document.createTextNode(t + " (" +
    NODES.filter(function (nn) {
      return (nn.type || "unknown") === t;
    }).length + ")"));
  tf.appendChild(lbl);
});
if (!nodeTypes.length) {
  tf.innerHTML = '<span class="muted">none</span>';
}
var ef = document.getElementById("edgeFilters");
edgeTypes.forEach(function (t) {
  var lbl = document.createElement("label");
  lbl.className = "etype-filter";
  var cb = document.createElement("input");
  cb.type = "checkbox"; cb.checked = true;
  cb.addEventListener("change", function () {
    state.edgeOn[t] = cb.checked;
    relayout();
  });
  var ln = document.createElement("span");
  ln.className = "line"; ln.style.borderColor = edgeColor[t];
  lbl.appendChild(cb); lbl.appendChild(ln);
  lbl.appendChild(document.createTextNode(t));
  ef.appendChild(lbl);
});
if (!edgeTypes.length) {
  ef.innerHTML = '<span class="muted">none</span>';
}

var searchTimer = 0;
document.getElementById("search").addEventListener("input", function (ev) {
  var v = ev.target.value.trim().toLowerCase();
  if (searchTimer) { clearTimeout(searchTimer); }
  searchTimer = setTimeout(function () {   /* debounce ~120 ms */
    searchTimer = 0;
    state.query = v;
    applyQuery();
    positionAll();      /* search fades, it never moves nodes */
    updateEmpty();
  }, 120);
});

var cbInvalid = document.getElementById("cbInvalid");
var payloadInvalid = NODES.filter(function (nn) {
  return !!nn.invalid_at;
}).length;
cbInvalid.addEventListener("change", function () {
  state.showInvalid = cbInvalid.checked;
  relayout();
  state.repo.builtFor = null;          /* repo tree must be rebuilt */
  if (state.tab === "repo") { ensureRepo(); }
});
if (!payloadInvalid) {
  cbInvalid.disabled = true;
  document.getElementById("invalidHint").textContent =
    META.invalidated_nodes_hidden ?
      META.invalidated_nodes_hidden +
        " invalidated node(s) excluded from this payload - regenerate " +
        "with --include-invalidated to inspect them" :
      "no invalidated records in this payload";
}

function setLayout(mode) {
  state.layout = mode;
  document.getElementById("btnForce").classList.toggle("active",
    mode === "force");
  document.getElementById("btnDag").classList.toggle("active",
    mode === "dag");
  relayout();
}
document.getElementById("btnForce").addEventListener("click", function () {
  setLayout("force");
});
document.getElementById("btnDag").addEventListener("click", function () {
  setLayout("dag");
});
document.getElementById("btnFit").addEventListener("click", function () {
  fit();
});
document.getElementById("btnAllNodes").addEventListener("click",
  function () {
    state.ackBudget = true;
    relayout();
  });

/* ================================================================== */
/* status surfaces (banner, stats, empty states)                      */
/* ================================================================== */
function updateBanner(preCount) {
  var banner = document.getElementById("banner");
  if (state.overBudget && !state.ackBudget) {
    document.getElementById("bannerText").textContent =
      "Large graph: showing the top " + BUDGET + " of " + preCount +
      " visible nodes by degree. Filter, use DAG mode, or regenerate " +
      "with --limit N --rank degree.";
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
}
function updateStats() {
  var hiddenInvalid = (META.invalidated_nodes_hidden || 0) +
    (state.showInvalid ? 0 : payloadInvalid);
  var txt = state.visibleCount + " of " + N + " nodes shown · " +
    state.visibleEdges + " of " + EDGES.length + " edges";
  if (hiddenInvalid) {
    txt += " · " + hiddenInvalid + " invalidated hidden";
  }
  if (SELF_LOOPS) { txt += " · " + SELF_LOOPS + " self-loop(s)"; }
  if (ORPHAN_EDGES) {
    txt += " · " + ORPHAN_EDGES + " edge(s) with a missing endpoint";
  }
  if (META.malformed) {
    txt += " · " + META.malformed + " malformed line(s)";
  }
  if (META.limited) {
    txt += " · payload limited to top " + META.limit;
  }
  document.getElementById("stats").textContent = txt;
}
/* Empty-state overlay. Shown ONLY when the store is empty, the active
 * filters genuinely exclude every node, or the search matches nothing.
 * (The old single-file viewer's overlay stuck permanently once shown:
 * its #empty rule declared display:flex, which outranks the UA default
 * for [hidden] - fixed in graph-view.css with [hidden]{display:none
 * !important}. The logic below is the second half of that fix.) */
function updateEmpty() {
  var box = document.getElementById("empty");
  var txt = document.getElementById("emptyText");
  if (!N) {
    txt.innerHTML = "<b>The memory graph is empty.</b><br>" +
      "Populate the store, then regenerate this page.";
    box.hidden = false;
  } else if (!state.visibleCount) {
    txt.innerHTML = "<b>No nodes match the current filters.</b><br>" +
      "Re-enable a node type, or show invalidated records.";
    box.hidden = false;
  } else {
    var anyMatch = false;
    for (var k = 0; k < N; k++) {
      if (VIS[k] && MATCH[k]) { anyMatch = true; break; }
    }
    if (!anyMatch) {
      txt.innerHTML = "<b>No visible node matches the search.</b><br>" +
        "Clear the search box to bring the graph back.";
      box.hidden = false;
    } else {
      box.hidden = true;
    }
  }
}
document.getElementById("footer").textContent =
  "memory graph · " + (META.source || "") +
  " · newest record " + (META.generated_at || "unknown");

/* ================================================================== */
/* tabs                                                               */
/* ================================================================== */
var TABS = [
  { key: "graph", button: "tabGraph", stage: "stageGraph", title: "Graph" },
  { key: "repo", button: "tabRepo", stage: "stageRepo", title: "Repo" },
  { key: "history", button: "tabHistory", stage: "stageHistory",
    title: "History" }
];
function setTab(name) {
  state.tab = name;
  var title = document.getElementById("frameTitle");
  TABS.forEach(function (tab) {
    if (tab.key === name && title) { title.textContent = tab.title; }
    /* one body class per tab, so a sidebar block declares the tab it
     * belongs to (`repo-only`) instead of every block having to know
     * about every other tab */
    document.body.classList.toggle("tab-" + tab.key, tab.key === name);
    document.getElementById(tab.button).classList.toggle("active",
      tab.key === name);
    document.getElementById(tab.stage).hidden = tab.key !== name;
  });
  if (name === "repo") { ensureRepo(); }
  if (name === "history") { ensureHistory(); }
}
TABS.forEach(function (tab) {
  document.getElementById(tab.button).addEventListener("click", function () {
    setTab(tab.key);
  });
});

/* ================================================================== */
/* repo view: nested circle packing of the file tree                  */
/* ================================================================== */
/* In the spirit of the GitHub Next repo-visualization
 * (githubnext.com/projects/repo-visualization): directories are
 * enclosing circles, files are leaves whose radius scales with size
 * (props.size / bytes / loc / lines when present, else uniform) and
 * whose fill is keyed by file extension. The packing is fully
 * deterministic: siblings are sorted (radius desc, name asc) and packed
 * by front chain, each circle tangent to two already placed - see
 * `frontChain` for what that replaced and why.
 *
 * Dependency connections belong to the SELECTION, not to hover. The
 * reference page drew them on hover ("I only show connections from & to
 * a file on hover") and that is unusable on a packed map: the pointer
 * has to leave the circle to follow a curve to its other end, and the
 * curves vanish on the way. Hover is emphasis only; selecting a file
 * draws its imports / calls / depends_on edges, outgoing and incoming
 * styled separately, and holds them still while the panel names them.
 * `test_37_viewer_repo_links.py` is the gate for that split. */
var svgRepo = document.getElementById("svgRepo");
var viewportRepo = document.getElementById("viewportRepo");
var STRUCTURAL = { file: 0, module: 1, test: 2, config: 3 };
var PACK_PAD = 2, DIR_PAD = 6;
var LEAF_R_BASE = 3, LEAF_R_UNIFORM = 7;

/* One scale for every leaf on a frame, anchored at the SMALLEST file
 * present: r(f) = LEAF_R_BASE * sqrt(lines(f) / lines_min).
 *
 * WHAT IT REPLACED. `LEAF_R_MIN + (LEAF_R_MAX - LEAF_R_MIN) *
 * sqrt(size / max)` — anchored on the biggest file, over a 4-px pedestal,
 * and capped at 26. The pedestal is the problem: with it, area goes as
 * `(4 + k*sqrt(lines))^2`, which is NOT proportional to the line count,
 * and the whole claim of the frame is that a circle's ink is its size.
 * Every small file was inflated toward the same 4-px floor, so a 2-line
 * file and the 137-line median differed by 4.1 px against 7.6 px — the
 * size channel carrying almost nothing across the range where most files
 * live. Anchoring on the maximum made it worse: one outlier compressed
 * everything else toward the floor.
 *
 * With no pedestal and the smallest file as the unit, area is exactly
 * proportional: four times the lines is four times the ink. There is no
 * cap either, because the packing measures whatever the circles come to
 * and the fit scales the frame — clamping a large file would make it lie
 * about its size to protect a layout that adapts anyway. */
function leafRadiusScale(leaves) {
  var vmin = 0;
  leaves.forEach(function (lf) {
    if (lf.size > 0 && (!vmin || lf.size < vmin)) { vmin = lf.size; }
  });
  return function (leaf) {
    if (!vmin || !leaf.size) { return LEAF_R_UNIFORM; }
    if (leaf.size <= vmin) { return LEAF_R_BASE; }
    return LEAF_R_BASE * Math.sqrt(leaf.size / vmin);
  };
}

/* How big a file is, for the circle that stands for it.
 *
 * Lines first, and by a wide margin: it is what `scan` records, what the
 * History view can reconstruct at any commit from git's own add/del
 * counts, and what a reader means by "a big file". Byte size only stands
 * in for a store whose nodes predate line counting — it ranks the same
 * files very differently (one minified asset outweighs a package), so it
 * is a fallback, never the measure. */
var SIZE_KEYS = ["lines", "loc", "size", "bytes", "size_bytes"];
var SIZE_UNITS = { lines: "lines", loc: "lines", size: "bytes",
  bytes: "bytes", size_bytes: "bytes" };
function leafSizeEntry(nn) {
  var p = nn.props || {};
  for (var k = 0; k < SIZE_KEYS.length; k++) {
    var v = p[SIZE_KEYS[k]];
    if (typeof v === "number" && isFinite(v) && v > 0) {
      return { value: v, unit: SIZE_UNITS[SIZE_KEYS[k]] };
    }
  }
  return { value: 0, unit: "" };
}
function leafSizeOf(nn) { return leafSizeEntry(nn).value; }
function extOf(path) {
  var base = path.slice(path.lastIndexOf("/") + 1);
  var dot = base.lastIndexOf(".");
  if (dot <= 0) { return "(none)"; }
  return base.slice(dot + 1).toLowerCase();
}
function normPath(p) {
  return String(p).replace(/\\/g, "/").replace(/^\.\//, "")
    .replace(/^\/+/, "").replace(/\/+$/, "");
}

/* The FILE each node belongs to, by index — its own `path` when it has
 * one, otherwise the path of the nearest ancestor reached by `contains`.
 *
 * This is what makes the Repo frame's connection layer possible at all.
 * The frame draws files, but the edges worth drawing mostly do not join
 * files: `calls` joins two function nodes, and `imports` leaves a module
 * node. An edge is a relationship between the FILES its endpoints live
 * in, and that is the question this answers.
 *
 * The `contains` walk is bounded (64 hops) because a malformed store
 * could otherwise present a cycle, and a viewer that hangs on a bad
 * store is worse than one that draws less of it. */
var OWNER_PATH = (function () {
  var owner = new Array(N), parent = Object.create(null), k;
  for (k = 0; k < EDGES.length; k++) {
    if (EDGES[k].e.type === "contains" && parent[EDGES[k].d] === undefined) {
      parent[EDGES[k].d] = EDGES[k].s;
    }
  }
  for (k = 0; k < N; k++) {
    var own = NODES[k].path;
    if (typeof own === "string" && own.trim()) {
      owner[k] = normPath(own);
      continue;
    }
    var cur = k, hops = 0;
    while (parent[cur] !== undefined && hops++ < 64) {
      cur = parent[cur];
      var up = NODES[cur].path;
      if (typeof up === "string" && up.trim()) {
        owner[k] = normPath(up);
        break;
      }
    }
  }
  return owner;
})();

/* The node a path is DRAWN as, by the same precedence collectLeaves
 * uses (file, then module/test/config; ties by id). The filter state is
 * deliberately not consulted: this answers "which circle stands for
 * this path", and a link whose far end is currently hidden is skipped
 * by the drawing code, which already knows how. */
var LEAF_BY_PATH = (function () {
  var best = Object.create(null), order = [], k;
  for (k = 0; k < N; k++) {
    if (!hasOwn(STRUCTURAL, NODES[k].type)) { continue; }
    if (typeof NODES[k].path !== "string" || !NODES[k].path.trim()) {
      continue;
    }
    order.push(k);
  }
  order.sort(function (a, b) {
    var ta = STRUCTURAL[NODES[a].type], tb = STRUCTURAL[NODES[b].type];
    if (ta !== tb) { return ta - tb; }
    return NODES[a].id < NODES[b].id ? -1 : 1;
  });
  order.forEach(function (k) {
    var p = normPath(NODES[k].path);
    if (p && best[p] === undefined) { best[p] = k; }
  });
  return best;
})();

/* --- hierarchy ---------------------------------------------------- */
function collectLeaves() {
  /* `file` nodes first, then module/test/config on paths not already
   * claimed - each normalized path yields at most one leaf. */
  var picked = [], seen = Object.create(null);
  var candidates = [];
  for (var k = 0; k < N; k++) {
    var nn = NODES[k];
    if (!hasOwn(STRUCTURAL, nn.type)) { continue; }
    if (typeof nn.path !== "string" || !nn.path.trim()) { continue; }
    if (nn.invalid_at && !state.showInvalid) { continue; }
    candidates.push(k);
  }
  candidates.sort(function (a, b) {
    var ta = STRUCTURAL[NODES[a].type], tb = STRUCTURAL[NODES[b].type];
    if (ta !== tb) { return ta - tb; }
    return NODES[a].id < NODES[b].id ? -1 : 1;
  });
  candidates.forEach(function (k) {
    var path = normPath(NODES[k].path);
    if (!path || seen[path]) { return; }
    seen[path] = 1;
    var size = leafSizeEntry(NODES[k]);
    picked.push({ idx: k, path: path, size: size.value, unit: size.unit,
      ext: extOf(path) });
  });
  return picked;
}
function buildTree(leaves) {
  var root = { name: "", path: "", dirs: Object.create(null), leaves: [] };
  leaves.forEach(function (leaf) {
    var parts = leaf.path.split("/");
    var cur = root;
    for (var k = 0; k < parts.length - 1; k++) {
      var part = parts[k];
      if (!part) { continue; }
      if (!cur.dirs[part]) {
        cur.dirs[part] = { name: part,
          path: cur.path ? cur.path + "/" + part : part,
          dirs: Object.create(null), leaves: [] };
      }
      cur = cur.dirs[part];
    }
    leaf.name = parts[parts.length - 1];
    cur.leaves.push(leaf);
  });
  return root;
}
/* --- what a circle's colour is answering --------------------------- */
/* Three questions over one map, so the shapes stay put and only the
 * meaning of the colour changes: what KIND of file is this, how
 * CONNECTED is it, how OFTEN has it changed. Each mode owns a legend
 * (they share the sidebar slot, since only one can be true at a time)
 * and its scale is fitted to the values actually present - a fixed
 * scale on a repository whose busiest file has four commits would paint
 * everything the same colour. */
var REPO_MODES = [
  { key: "type", label: "File type", title: "File types",
    hint: "fixed colour per extension" },
  { key: "connections", label: "Connections", title: "Connections",
    cmap: "plasma", unit: "connections",
    hint: "imports / calls / depends_on touching the file" },
  { key: "commits", label: "Commits", title: "Commits",
    cmap: "rainbow", unit: "commits",
    hint: "commits in the inlined history that changed the file" }
];
function repoMode(key) {
  for (var k = 0; k < REPO_MODES.length; k++) {
    if (REPO_MODES[k].key === key) { return REPO_MODES[k]; }
  }
  return REPO_MODES[0];
}
function extCounts(leaves) {
  var count = Object.create(null);
  leaves.forEach(function (lf) { count[lf.ext] = (count[lf.ext] || 0) + 1; });
  return count;
}
/* --- deterministic sibling packing -------------------------------- */
/* FRONT-CHAIN packing (Wang, Wang, Dai & Wang 2006) — the algorithm
 * d3-hierarchy uses, minus its shuffle, so the result stays a pure
 * function of the sorted input.
 *
 * WHAT IT REPLACED, AND WHY. The first implementation walked an
 * Archimedean spiral from the parent's centre and took the first
 * collision-free point, testing against every circle already placed. It
 * was chosen for being obviously deterministic, and it is — but it is
 * also quadratic in the sibling count with a 100 000-iteration escape
 * hatch, and it packs badly enough to make the frame unreadable.
 * Measured on this system's own store (407 files): enclosing radius
 * 3191 where the circles themselves need 655, i.e. roughly one part in
 * eighty of the area actually holding a file, at a cost of 205 844
 * collision tests. Fitted to a 600-px stage that is a map whose circles
 * are 0.4 to 2.4 px across. Scaled to a real client site it is worse
 * than slow: the spiral's step is `r/2 / rad`, so a small circle looking
 * for a home outside a large frontier advances in 0.05-radian
 * increments and can exhaust the guard — at which point it is placed
 * OVERLAPPING whatever was in the way, silently, because running out of
 * guard is not an error anybody reports.
 *
 * The front chain places each circle tangent to two others and keeps
 * only the hull as candidates, so it is linear in practice and needs no
 * escape hatch at all. Same input, same store: enclosing radius 668,
 * 1 785 intersection tests. Determinism is unchanged — siblings are
 * still sorted (radius desc, name asc) before packing. */
function packPlace(a, b, c) {
  /* Put `c` tangent to both `a` and `b`. */
  var dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy, x, y;
  if (d2) {
    var a2 = (a.r + c.r) * (a.r + c.r);
    var b2 = (b.r + c.r) * (b.r + c.r);
    if (a2 > b2) {
      x = (d2 + b2 - a2) / (2 * d2);
      y = Math.sqrt(Math.max(0, b2 / d2 - x * x));
      c.x = b.x - x * dx - y * dy;
      c.y = b.y - x * dy + y * dx;
    } else {
      x = (d2 + a2 - b2) / (2 * d2);
      y = Math.sqrt(Math.max(0, a2 / d2 - x * x));
      c.x = a.x + x * dx - y * dy;
      c.y = a.y + x * dy + y * dx;
    }
  } else {
    c.x = a.x + c.r;
    c.y = a.y;
  }
}
/* Tangency is not overlap: the epsilon is what stops two circles placed
 * deliberately touching from reading as a collision. */
function packIntersects(a, b) {
  var dr = a.r + b.r - 1e-6, dx = b.x - a.x, dy = b.y - a.y;
  return dr > 0 && dr * dr > dx * dx + dy * dy;
}
function packScore(node) {
  var a = node.c, b = node.next.c, ab = a.r + b.r;
  var dx = (a.x * b.r + b.x * a.r) / ab;
  var dy = (a.y * b.r + b.y * a.r) / ab;
  return dx * dx + dy * dy;
}
function frontChain(circles) {
  var n = circles.length;
  if (!n) { return; }
  circles[0].x = 0; circles[0].y = 0;
  if (n < 2) { return; }
  circles[0].x = -circles[1].r;
  circles[1].x = circles[0].r;
  circles[1].y = 0;
  if (n < 3) { return; }
  packPlace(circles[1], circles[0], circles[2]);
  var na = { c: circles[0] }, nb = { c: circles[1] }, nc = { c: circles[2] };
  na.next = nb; nb.next = nc; nc.next = na;
  na.prev = nc; nb.prev = na; nc.prev = nb;
  var a = na, b = nb, i = 3;
  pack: while (i < n) {
    packPlace(a.c, b.c, circles[i]);
    var node = { c: circles[i], prev: null, next: null };
    /* Walk the hull outward from the placing pair in both directions,
     * always extending the cheaper side first. The first circle the new
     * one runs into becomes half of the next placing pair. */
    var j = b.next, k = a.prev, sj = b.c.r, sk = a.c.r;
    do {
      if (sj <= sk) {
        if (packIntersects(j.c, node.c)) {
          b = j; a.next = b; b.prev = a; continue pack;
        }
        sj += j.c.r; j = j.next;
      } else {
        if (packIntersects(k.c, node.c)) {
          a = k; a.next = b; b.prev = a; continue pack;
        }
        sk += k.c.r; k = k.prev;
      }
    } while (j !== k.next);
    node.prev = a; node.next = b;
    a.next = node; b.prev = node;
    b = node;
    /* the tightest gap on the new hull is where the next one goes */
    var best = packScore(a), cur = node, score;
    while ((cur = cur.next) !== b) {
      score = packScore(cur);
      if (score < best) { a = cur; best = score; }
    }
    b = a.next;
    i++;
  }
}
/* --- smallest circle containing all of them ----------------------- */
/* Welzl's move-to-front construction, taken in the given order rather
 * than a random one: the input is sorted radius-descending, so the
 * largest circle is tried first and usually swallows most of the rest
 * before the inner loops are ever entered. Deterministic by
 * construction — no shuffle, no clock, no PRNG. */
function encloseContains(circ, c) {
  var dx = circ.x - c.x, dy = circ.y - c.y;
  return Math.sqrt(dx * dx + dy * dy) + c.r <= circ.r + 1e-6;
}
function enclose1(a) { return { x: a.x, y: a.y, r: a.r }; }
function enclose2(a, b) {
  var dx = b.x - a.x, dy = b.y - a.y, dr = Math.sqrt(dx * dx + dy * dy);
  if (dr + a.r <= b.r + 1e-9) { return enclose1(b); }
  if (dr + b.r <= a.r + 1e-9) { return enclose1(a); }
  var l = (dr + a.r + b.r) / 2, t = dr ? (l - a.r) / dr : 0;
  return { x: a.x + t * dx, y: a.y + t * dy, r: l };
}
function enclose3(a, b, c) {
  var a2 = 2 * (a.x - b.x), b2 = 2 * (a.y - b.y), c2 = 2 * (b.r - a.r);
  var d2 = a.x * a.x + a.y * a.y - a.r * a.r
         - b.x * b.x - b.y * b.y + b.r * b.r;
  var a3 = 2 * (a.x - c.x), b3 = 2 * (a.y - c.y), c3 = 2 * (c.r - a.r);
  var d3 = a.x * a.x + a.y * a.y - a.r * a.r
         - c.x * c.x - c.y * c.y + c.r * c.r;
  var ab = a3 * b2 - a2 * b3;
  if (!ab) { return enclose2(a, b); }   /* collinear centres */
  var xa = (b2 * d3 - b3 * d2) / ab - a.x, xb = (b3 * c2 - b2 * c3) / ab;
  var ya = (a3 * d2 - a2 * d3) / ab - a.y, yb = (a2 * c3 - a3 * c2) / ab;
  var A = xb * xb + yb * yb - 1;
  var B = 2 * (a.r + xa * xb + ya * yb);
  var C = xa * xa + ya * ya - a.r * a.r;
  var r = A ? -(B + Math.sqrt(Math.max(0, B * B - 4 * A * C))) / (2 * A)
            : (B ? C / B : 0);
  return { x: a.x + xa + xb * r, y: a.y + ya + yb * r, r: r };
}
function encloseCircles(circles) {
  var circ = null, i, j, k;
  for (i = 0; i < circles.length; i++) {
    if (circ && encloseContains(circ, circles[i])) { continue; }
    circ = enclose1(circles[i]);
    for (j = 0; j < i; j++) {
      if (encloseContains(circ, circles[j])) { continue; }
      circ = enclose2(circles[i], circles[j]);
      for (k = 0; k < j; k++) {
        if (encloseContains(circ, circles[k])) { continue; }
        circ = enclose3(circles[i], circles[j], circles[k]);
      }
    }
  }
  return circ || { x: 0, y: 0, r: 0 };
}
function packSiblings(items) {
  /* Mutates each item with x/y relative to the parent centre; returns
   * the enclosing radius. Deterministic: sorted order, then a placement
   * that makes no choices of its own.
   *
   * The gap between siblings is carried in the PACKING radius, not in
   * the collision test: the front chain places circles tangent, so a
   * pair asked to touch must already be a padding-width apart. Drawing
   * still uses `it.r`, which is untouched. */
  var sorted = items.slice().sort(function (a, b) {
    if (b.r !== a.r) { return b.r - a.r; }
    return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
  });
  var circles = sorted.map(function (it) {
    return { it: it, r: it.r + PACK_PAD, x: 0, y: 0 };
  });
  frontChain(circles);
  var enc = encloseCircles(circles);
  circles.forEach(function (c) {
    c.it.x = c.x - enc.x;
    c.it.y = c.y - enc.y;
  });
  return enc.r;
}
function packDir(dir, radiusFor) {
  var items = [];
  Object.keys(dir.dirs).sort().forEach(function (name) {
    var sub = dir.dirs[name];
    packDir(sub, radiusFor);
    items.push({ r: sub.r, key: "d:" + name, dir: sub });
  });
  dir.leaves.slice().sort(function (a, b) {
    return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  }).forEach(function (leaf) {
    leaf.r = radiusFor(leaf);
    items.push({ r: leaf.r, key: "f:" + leaf.name, leaf: leaf });
  });
  dir.nDirs = Object.keys(dir.dirs).length;
  dir.nLeaves = dir.leaves.length;
  Object.keys(dir.dirs).forEach(function (name) {
    dir.nDirs += dir.dirs[name].nDirs;
    dir.nLeaves += dir.dirs[name].nLeaves;
  });
  if (!items.length) { dir.items = []; dir.r = 10; return; }
  var R = packSiblings(items);
  dir.items = items;
  dir.r = R + DIR_PAD;
}
function placeDir(dir, cx, cy, depth) {
  dir.cx = cx; dir.cy = cy; dir.depth = depth;
  dir.items.forEach(function (it) {
    if (it.dir) { placeDir(it.dir, cx + it.x, cy + it.y, depth + 1); }
    else { it.leaf.cx = cx + it.x; it.leaf.cy = cy + it.y; }
  });
}
/* --- repo rendering ----------------------------------------------- */
var repoLeafEls = [];
/* connections: leaf node-index -> {x, y}, plus the curve layer */
var REPO_LINK_TYPES = { imports: 1, calls: 1, depends_on: 1 };
var repoPosByIdx = Object.create(null);
var repoLinkGroup = null;
function repoClearLinks() {
  if (repoLinkGroup) {
    while (repoLinkGroup.firstChild) {
      repoLinkGroup.removeChild(repoLinkGroup.firstChild);
    }
  }
}
/* Every live dependency relationship touching this leaf.
 *
 * WHAT THIS REPLACED, AND WHY. The first implementation kept only edges
 * whose endpoint index IS the leaf's own node. Almost nothing matched:
 * `calls` joins two FUNCTION nodes and `imports` leaves a MODULE node,
 * so on a real scan 1923 of 1930 dependency edges were invisible and
 * selecting a file drew nothing at all. The frame looked like a feature
 * that had been built and never wired up, and in effect it was.
 *
 * Endpoints are lifted to the file that owns them (OWNER_PATH) and then
 * to the circle that file is drawn as (LEAF_BY_PATH). Twelve functions
 * in one file calling three in another is ONE relationship between two
 * circles, not twelve; drawing it twelve times stacks twelve identical
 * curves and prints twelve identical rows. The multiplicity is kept and
 * shown, because "calls x12" and "calls x1" are different facts.
 *
 * An endpoint with no file of its own — an `external_dep`, which is most
 * of what `imports` points at — is a real dependency and is reported as
 * one, with `other: -1` so nothing tries to find a circle for it.
 * Dropping those silently would understate the very files that depend on
 * the most.
 *
 * A call from one function to another INSIDE the same file is not a
 * connection between two circles and is left out.
 *
 * Indexed ONCE per (payload, filter state) rather than rescanned per leaf
 * per repaint: `connections` mode asks this of every circle on every
 * paint, which made the old form quadratic in the store.
 *
 * The panel summary and the drawn curves read the SAME list, so what is
 * listed is exactly what is drawn. */
var connIndex = null, connIndexShows = null;
function connectionIndex() {
  if (connIndex && connIndexShows === state.showInvalid) { return connIndex; }
  var byLeaf = Object.create(null);
  function add(leaf, other, label, outgoing, type, invalid) {
    var key = other + "|" + (outgoing ? "1" : "0") + "|" + type;
    var list = byLeaf[leaf] || (byLeaf[leaf] = { order: [],
                                                 seen: Object.create(null) });
    var have = list.seen[key];
    if (have) {
      have.count++;
      if (!invalid) { have.invalid = false; }
      return;
    }
    have = { other: other, label: label, outgoing: outgoing, type: type,
             invalid: invalid, count: 1, external: other < 0 };
    list.seen[key] = have;
    list.order.push(have);
  }
  for (var k = 0; k < EDGES.length; k++) {
    var ed = EDGES[k];
    if (!hasOwn(REPO_LINK_TYPES, ed.e.type)) { continue; }
    if (ed.e.invalid_at && !state.showInvalid) { continue; }
    var sp = OWNER_PATH[ed.s], dp = OWNER_PATH[ed.d];
    var sl = sp === undefined ? undefined : LEAF_BY_PATH[sp];
    var dl = dp === undefined ? undefined : LEAF_BY_PATH[dp];
    if (sl === undefined && dl === undefined) { continue; }
    if (sl !== undefined && sl === dl) { continue; }   /* same file */
    var bad = !!ed.e.invalid_at;
    if (sl !== undefined) {
      add(sl, dl === undefined ? -1 : dl,
          dl === undefined ? (NODES[ed.d].name || NODES[ed.d].id)
                           : (NODES[dl].path || NODES[dl].id),
          true, ed.e.type, bad);
    }
    if (dl !== undefined) {
      add(dl, sl === undefined ? -1 : sl,
          sl === undefined ? (NODES[ed.s].name || NODES[ed.s].id)
                           : (NODES[sl].path || NODES[sl].id),
          false, ed.e.type, bad);
    }
  }
  connIndex = byLeaf;
  connIndexShows = state.showInvalid;
  return connIndex;
}
function repoConnections(idx) {
  var all = connectionIndex();
  return hasOwn(all, idx) ? all[idx].order : [];
}
/* A quadratic bow, not a straight line: two files joined in both
 * directions would otherwise draw one segment over the other, and a
 * bundle of chords across a packed circle reads as a scribble. The bow
 * scales with the chord so near neighbours get a gentle arc. */
function repoLinkPath(from, to) {
  var dx = to.x - from.x, dy = to.y - from.y;
  var len = Math.sqrt(dx * dx + dy * dy) || 1;
  var bow = Math.min(len * 0.22, 160);
  var cx = (from.x + to.x) / 2 - dy / len * bow;
  var cy = (from.y + to.y) / 2 + dx / len * bow;
  return "M" + from.x.toFixed(1) + " " + from.y.toFixed(1) +
    " Q" + cx.toFixed(1) + " " + cy.toFixed(1) +
    " " + to.x.toFixed(1) + " " + to.y.toFixed(1);
}
/* Drawn for the SELECTED file, not the hovered one. Hover is a pointer
 * moving across a packed map - connections that appear and vanish under
 * it cannot be read, let alone followed to their other end. Selection
 * holds them still, and the right-hand panel names them. */
function repoDrawLinks() {
  repoClearLinks();
  if (!repoLinkGroup || state.selected === null) { return; }
  var idx = IDX[state.selected];
  if (idx === undefined || repoPosByIdx[idx] === undefined) { return; }
  var from = repoPosByIdx[idx];
  repoConnections(idx).forEach(function (link) {
    /* An endpoint outside the file tree has no circle to draw a curve
     * to. It is still listed in the panel, which can name it. */
    if (link.external) { return; }
    var to = repoPosByIdx[link.other];
    if (to === undefined) { return; }
    var path = document.createElementNS(NS, "path");
    path.setAttribute("class", "rlink " +
      (link.outgoing ? "rline-out" : "rline-in") +
      (link.invalid ? " dimmed" : ""));
    path.setAttribute("d", repoLinkPath(from, to));
    var title = document.createElementNS(NS, "title");
    title.textContent = (link.outgoing ? "→ " : "← ") + link.type +
      (link.count > 1 ? " ×" + link.count : "") + " " + link.label;
    path.appendChild(title);
    repoLinkGroup.appendChild(path);
  });
}
/* --- the value each mode paints ------------------------------------ */
/* How many commits in the inlined window touched each path. Built once:
 * a repository with 200 commits and a few thousand files is a single
 * pass here and a lookup per circle afterwards.
 *
 * A rename is counted against the name the file ended up with — the
 * question a reader is asking of a circle on today's map is "how often
 * has THIS file changed", and the pre-rename name is not on the map. */
var COMMIT_COUNTS = (function () {
  var counts = Object.create(null);
  GIT.commits.forEach(function (commit) {
    (commit.files || []).forEach(function (entry) {
      if (!entry || typeof entry.path !== "string") { return; }
      counts[entry.path] = (counts[entry.path] || 0) + 1;
    });
  });
  return counts;
})();
/* Graph paths are relative to the scan root, git's to the repository
 * root. They are the same string only when the two roots coincide. */
function gitPath(rel) {
  return GIT.prefix ? GIT.prefix + "/" + rel : rel;
}
function commitCountFor(path) {
  var key = gitPath(path);
  return hasOwn(COMMIT_COUNTS, key) ? COMMIT_COUNTS[key] : 0;
}
function connectionCountFor(idx) { return repoConnections(idx).length; }
function leafValue(leaf, mode) {
  if (mode === "connections") { return connectionCountFor(leaf.idx); }
  if (mode === "commits") { return commitCountFor(leaf.path); }
  return 0;
}
function commitsAvailable() {
  return GIT.state === "ok" && GIT.commits.length > 0;
}

/* --- colouring the circles ----------------------------------------- */
var repoExtColors = { colors: Object.create(null),
  derived: Object.create(null) };
var repoExtCount = Object.create(null);
function applyRepoColors() {
  var mode = repoMode(state.repo.mode);
  var leaves = repoLeafEls;
  var lo = Infinity, hi = -Infinity, values = [];
  if (mode.cmap) {
    leaves.forEach(function (entry) {
      var value = leafValue(entry.leaf, mode.key);
      values.push(value);
      if (value < lo) { lo = value; }
      if (value > hi) { hi = value; }
    });
    if (!leaves.length) { lo = hi = 0; }
  }
  leaves.forEach(function (entry, k) {
    var fill;
    if (mode.cmap) {
      fill = cmapHex(mode.cmap, cmapNorm(values[k], lo, hi));
    } else {
      fill = repoExtColors.colors[entry.leaf.ext] || NO_EXT_COLOR;
    }
    entry.el.setAttribute("fill", fill);
    entry.el.setAttribute("data-value", mode.cmap ? values[k] : entry.leaf.ext);
  });
  state.repo.range = mode.cmap ? { lo: lo, hi: hi } : null;
  renderRepoLegend(mode, lo, hi);
}
function legendSwatch(color) {
  var sw = document.createElement("span");
  sw.className = "swatch";
  sw.style.background = color;
  return sw;
}
/* Built as an element, not assigned as innerHTML: these strings carry a
 * git error message, and the only reason to hand user- or tool-authored
 * text to an HTML parser is to be surprised by it. */
function legendMessage(box, message) {
  var span = document.createElement("span");
  span.className = "muted";
  span.textContent = message;
  box.appendChild(span);
}
/* The continuous legend is drawn as a strip of samples rather than a CSS
 * gradient: the strip is made of the very same cmapHex() calls that
 * coloured the circles, so the key cannot drift from the map. */
var LEGEND_STEPS = 28;
function renderCmapLegend(box, mode, lo, hi) {
  var bar = document.createElement("div");
  bar.className = "cmap-bar";
  for (var k = 0; k < LEGEND_STEPS; k++) {
    var cell = document.createElement("span");
    cell.style.background = cmapHex(mode.cmap, k / (LEGEND_STEPS - 1));
    bar.appendChild(cell);
  }
  box.appendChild(bar);
  var limits = document.createElement("div");
  limits.className = "cmap-limits";
  var low = document.createElement("span");
  var high = document.createElement("span");
  if (hi > lo) {
    low.textContent = String(lo);
    high.textContent = String(hi);
  } else {
    low.textContent = high.textContent = String(hi === -Infinity ? 0 : hi);
  }
  limits.appendChild(low);
  limits.appendChild(high);
  box.appendChild(limits);
  var note = document.createElement("div");
  note.className = "hint legend-note";
  note.textContent = hi > lo ? mode.unit + " · " + mode.cmap
    : "every file has the same number of " + mode.unit;
  box.appendChild(note);
}
function renderRepoLegend(mode, lo, hi) {
  var box = document.getElementById("repoLegend");
  var title = document.getElementById("repoLegendTitle");
  if (title) { title.textContent = mode.title; }
  if (!box) { return; }
  box.innerHTML = "";
  if (mode.key === "commits" && !commitsAvailable()) {
    legendMessage(box, gitUnavailableReason());
    return;
  }
  if (mode.cmap) { renderCmapLegend(box, mode, lo, hi); return; }
  var exts = Object.keys(repoExtCount).sort(function (a, b) {
    return repoExtCount[b] - repoExtCount[a] || (a < b ? -1 : 1);
  });
  if (!exts.length) {
    legendMessage(box, "none");
    return;
  }
  exts.forEach(function (ext) {
    var row = document.createElement("label");
    row.className = "type" +
      (hasOwn(repoExtColors.derived, ext) ? " derived" : "");
    row.appendChild(legendSwatch(repoExtColors.colors[ext] || NO_EXT_COLOR));
    row.appendChild(document.createTextNode(
      ext + " (" + repoExtCount[ext] + ")"));
    if (hasOwn(repoExtColors.derived, ext)) {
      row.title = "not in the registry — colour derived from the palette";
    }
    box.appendChild(row);
  });
}
function gitUnavailableReason() {
  if (GIT.state === "ok") { return "no commits were inlined"; }
  if (GIT.state === "off") { return "history collection was switched off"; }
  return GIT.detail || ("no history: " + GIT.state);
}
function setRepoMode(key) {
  var mode = repoMode(key);
  if (mode.key === "commits" && !commitsAvailable()) { mode = repoMode("type"); }
  state.repo.mode = mode.key;
  Array.prototype.forEach.call(
    document.getElementById("repoModes").children || [], function (btn) {
      btn.classList.toggle("active",
        btn.getAttribute("data-mode") === mode.key);
    });
  if (state.repo.root) { applyRepoColors(); }
}

function ensureRepo() {
  if (state.repo.builtFor === state.showInvalid) { return; }
  state.repo.builtFor = state.showInvalid;
  buildRepo();
}
function buildRepo() {
  while (viewportRepo.firstChild) {
    viewportRepo.removeChild(viewportRepo.firstChild);
  }
  repoLeafEls = [];
  repoPosByIdx = Object.create(null);
  repoLinkGroup = null;
  var leaves = collectLeaves();
  var emptyBox = document.getElementById("repoEmpty");
  var emptyTxt = document.getElementById("repoEmptyText");
  state.repo.leafCount = leaves.length;
  if (!leaves.length) {
    emptyTxt.innerHTML = "<b>No file tree to draw.</b><br>" +
      "The store has no file / module / test / config nodes with paths.";
    emptyBox.hidden = false;
    state.repo.root = null;
    repoExtCount = Object.create(null);
    renderRepoLegend(repoMode(state.repo.mode), 0, 0);
    document.getElementById("repoStats").textContent = "";
    return;
  }
  emptyBox.hidden = true;
  repoExtCount = extCounts(leaves);
  repoExtColors = extColorMap(Object.keys(repoExtCount));
  var root = buildTree(leaves);
  packDir(root, leafRadiusScale(leaves));
  placeDir(root, 0, 0, 0);
  state.repo.root = root;
  state.repo.dirCount = root.nDirs;
  renderRepoDir(root);
  /* the hover-connection layer sits above every circle */
  repoLinkGroup = document.createElementNS(NS, "g");
  repoLinkGroup.setAttribute("class", "rlinks");
  viewportRepo.appendChild(repoLinkGroup);
  /* fills and the legend come from the active mode, never from the
   * builder — the two must not be able to disagree */
  applyRepoColors();
  document.getElementById("repoStats").textContent =
    leaves.length + " files · " + root.nDirs + " directories";
  fitRepo();
  /* a selection made before this rebuild still owns its curves */
  repoRestyle();

  function renderRepoDir(dir) {
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "rdir");
    c.setAttribute("cx", dir.cx.toFixed(1));
    c.setAttribute("cy", dir.cy.toFixed(1));
    c.setAttribute("r", dir.r.toFixed(1));
    var t = document.createElementNS(NS, "title");
    t.textContent = (dir.path || "(root)") + " · " + dir.nLeaves +
      " file(s)";
    c.appendChild(t);
    c.addEventListener("click", function (ev) {
      ev.stopPropagation();
      showDirDetail(dir);
    });
    viewportRepo.appendChild(c);
    if (dir.r >= 28 && dir.name) {
      var maxChars = Math.floor((dir.r * 1.5) / 6.5);
      if (maxChars >= 3) {
        var lbl = document.createElementNS(NS, "text");
        lbl.setAttribute("class", "rdir-label");
        lbl.setAttribute("x", dir.cx.toFixed(1));
        lbl.setAttribute("y", (dir.cy - dir.r + 13).toFixed(1));
        lbl.textContent = dir.name.length > maxChars ?
          dir.name.slice(0, maxChars - 1) + "…" : dir.name;
        viewportRepo.appendChild(lbl);
      }
    }
    dir.items.forEach(function (it) {
      if (it.dir) { renderRepoDir(it.dir); }
      else { renderRepoLeaf(it.leaf); }
    });
  }
  function renderRepoLeaf(leaf) {
    var nn = NODES[leaf.idx];
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "rleaf" + (nn.invalid_at ? " dimmed" : ""));
    c.setAttribute("cx", leaf.cx.toFixed(1));
    c.setAttribute("cy", leaf.cy.toFixed(1));
    c.setAttribute("r", leaf.r.toFixed(1));
    var t = document.createElementNS(NS, "title");
    t.textContent = leaf.path +
      (leaf.size ? " · " + leaf.size + " " + leaf.unit : "") +
      " · " + connectionCountFor(leaf.idx) + " connection(s)" +
      (commitsAvailable() ? " · " + commitCountFor(leaf.path) + " commit(s)"
        : "") +
      (nn.invalid_at ? " [invalidated]" : "");
    c.appendChild(t);
    /* Claim the press so pointerup can select this leaf whichever element
     * the click is ultimately delivered to. Panning still starts from here,
     * so a drag that begins on a circle pans the view as before. */
    c.addEventListener("pointerdown", function (ev) {
      ev.stopPropagation();
      repoSuppress = false;
      repoPressed = nn.id;
      startRepoPan(ev);
    });
    c.addEventListener("click", function (ev) {
      ev.stopPropagation();
      select(nn.id);
    });
    viewportRepo.appendChild(c);
    repoPosByIdx[leaf.idx] = { x: leaf.cx, y: leaf.cy };
    repoLeafEls.push({ el: c, id: nn.id, invalid: !!nn.invalid_at,
      leaf: leaf });
    if (leaf.r >= 10) {
      var fname = leaf.name;
      var maxChars = Math.floor((leaf.r * 2 - 4) / 5.4);
      if (maxChars >= 4) {
        var lbl = document.createElementNS(NS, "text");
        lbl.setAttribute("class", "rleaf-label");
        lbl.setAttribute("x", leaf.cx.toFixed(1));
        lbl.setAttribute("y", (leaf.cy + 3).toFixed(1));
        lbl.textContent = fname.length > maxChars ?
          fname.slice(0, maxChars - 1) + "…" : fname;
        viewportRepo.appendChild(lbl);
      }
    }
  }
}
/* re-stroke leaves and redraw connections when the selection changes */
function repoRestyle() {
  for (var k = 0; k < repoLeafEls.length; k++) {
    var r = repoLeafEls[k];
    var cls = "rleaf" + (r.invalid ? " dimmed" : "") +
      (state.selected === r.id ? " selected" : "");
    if (r.el.getAttribute("class") !== cls) {
      r.el.setAttribute("class", cls);
    }
  }
  repoDrawLinks();
}
/* --- repo pan / zoom ---------------------------------------------- */
function applyRepoTransform() {
  viewportRepo.setAttribute("transform",
    "translate(" + state.repo.tx.toFixed(2) + "," +
    state.repo.ty.toFixed(2) + ") scale(" + state.repo.k.toFixed(4) + ")");
}
function fitRepo() {
  var root = state.repo.root;
  if (!root) { return; }
  var bw = svgRepo.clientWidth || 800, bh = svgRepo.clientHeight || 600;
  var R = root.r + 20;
  state.repo.k = clampK(Math.min(bw, bh) / (2 * R));
  state.repo.tx = bw / 2 - root.cx * state.repo.k;
  state.repo.ty = bh / 2 - root.cy * state.repo.k;
  applyRepoTransform();
}
var repoPanning = null, repoSuppress = false, repoPressed = null;
function startRepoPan(ev) {
  repoPanning = { x: ev.clientX, y: ev.clientY, tx: state.repo.tx,
    ty: state.repo.ty, moved: false };
  svgRepo.classList.add("panning");
  try { svgRepo.setPointerCapture(ev.pointerId); } catch (err) { /* ok */ }
}
svgRepo.addEventListener("pointerdown", function (ev) {
  repoSuppress = false;
  repoPressed = null;          /* a press on the background selects nothing */
  startRepoPan(ev);
});
svgRepo.addEventListener("pointermove", function (ev) {
  if (!repoPanning) { return; }
  var dx = ev.clientX - repoPanning.x, dy = ev.clientY - repoPanning.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) { repoPanning.moved = true; }
  state.repo.tx = repoPanning.tx + dx;
  state.repo.ty = repoPanning.ty + dy;
  applyRepoTransform();
});
function endRepoPointer(ev) {
  if (!repoPanning) { return; }
  if (repoPanning.moved) { repoSuppress = true; }
  else if (repoPressed !== null) {
    /* Same reason as the graph tab: the click that follows a captured
     * pointer is delivered to this <svg>, not to the leaf circle, so a leaf
     * that only listened for `click` was never selected at all. */
    select(repoPressed);
    repoSuppress = true;
  }
  try { svgRepo.releasePointerCapture(ev.pointerId); } catch (err) { /* */ }
  repoPanning = null;
  svgRepo.classList.remove("panning");
}
svgRepo.addEventListener("pointerup", endRepoPointer);
svgRepo.addEventListener("pointercancel", endRepoPointer);
svgRepo.addEventListener("click", function () {
  if (repoSuppress) { repoSuppress = false; return; }
  /* A press that landed on nothing, and did not pan: the reader is
   * putting the current file down. The Graph tab has always done this;
   * here the handler only ever consumed the suppression flag, which was
   * invisible until a selection started holding connection curves on
   * screen — with nothing to dismiss them, they stayed forever. */
  select(null);
});
svgRepo.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  var nk = clampK(state.repo.k * factor);
  factor = nk / state.repo.k;
  var rect = svgRepo.getBoundingClientRect();
  var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  state.repo.tx = mx - (mx - state.repo.tx) * factor;
  state.repo.ty = my - (my - state.repo.ty) * factor;
  state.repo.k = nk;
  applyRepoTransform();
}, { passive: false });
document.getElementById("btnRepoFit").addEventListener("click", fitRepo);

/* --- mode buttons --------------------------------------------------- */
(function buildRepoModeButtons() {
  var box = document.getElementById("repoModes");
  if (!box) { return; }
  REPO_MODES.forEach(function (mode) {
    var btn = document.createElement("button");
    btn.setAttribute("data-mode", mode.key);
    btn.textContent = mode.label;
    var blocked = mode.key === "commits" && !commitsAvailable();
    if (blocked) {
      /* A button that silently does nothing is worse than one that says
       * why it cannot: without a repository there are no commits to
       * count, and the reader should not be left testing it. */
      btn.disabled = true;
      btn.title = gitUnavailableReason();
    } else {
      btn.title = mode.hint;
      btn.addEventListener("click", function () { setRepoMode(mode.key); });
    }
    if (mode.key === state.repo.mode) { btn.classList.add("active"); }
    box.appendChild(btn);
  });
})();

/* ================================================================== */
/* history view: the same circles, walked backwards through time       */
/* ================================================================== */
/* The Repo view draws what the store knows about now. This one draws
 * what the REPOSITORY held at a chosen commit, so the tree itself
 * changes as you move through the list: files that had not been written
 * yet are absent, files deleted since are back.
 *
 * The page holds one tree (the oldest commit's, inlined by
 * memory_viz.py) and replays the diffs forward over it. That is why the
 * payload is proportional to the number of commits and not to commits
 * times files - and why the commit list must be a first-parent chain,
 * where each entry's diff is exactly the step between two neighbours.
 *
 * Colour answers one question here and it is a different one from the
 * Repo view's: how much of this commit landed in this file. Only the
 * files the commit touched are coloured; everything else stays
 * uncoloured, which is what makes a change visible at a glance. */
var svgHist = document.getElementById("svgHistory");
var viewportHist = document.getElementById("viewportHistory");
var HIST_NEUTRAL_L = 0.78;
var histLeafEls = [];
var histSizeByPath = (function () {
  var sizes = Object.create(null);
  for (var k = 0; k < N; k++) {
    var nn = NODES[k];
    if (!hasOwn(STRUCTURAL, nn.type)) { continue; }
    if (typeof nn.path !== "string" || !nn.path.trim()) { continue; }
    var size = leafSizeOf(nn);
    if (size) { sizes[gitPath(normPath(nn.path))] = size; }
  }
  return sizes;
})();

/* --- the file set at a commit -------------------------------------- */
/* `index` is a position in GIT.commits (newest first); -1 means "now",
 * the state after the newest commit shown. */
function commitIndex(sha) {
  for (var k = 0; k < GIT.commits.length; k++) {
    if (GIT.commits[k].sha === sha) { return k; }
  }
  return -1;
}
/* One step of the replay: which files exist, and how long each one is.
 * Line counts ride along with the tree because git already reports every
 * commit's added and deleted lines - so the only tree that has to be
 * measured directly is the oldest one, which memory_viz.py inlines. */
function applyCommitToState(state, commit) {
  (commit.files || []).forEach(function (entry) {
    if (!entry || typeof entry.path !== "string") { return; }
    if (entry.status === "D") {
      delete state.files[entry.path];
      delete state.lines[entry.path];
      return;
    }
    var before = 0;
    if (entry.from) {
      /* a rename is a delete and an add, and forgetting the delete leaves
       * a file on the map under a name the repository no longer has */
      before = state.lines[entry.from] || 0;
      delete state.files[entry.from];
      delete state.lines[entry.from];
    } else if (hasOwn(state.lines, entry.path)) {
      before = state.lines[entry.path];
    }
    state.files[entry.path] = 1;
    if (entry.add === null || entry.add === undefined ||
        entry.del === null || entry.del === undefined) {
      /* binary: git counts no lines, so neither do we - the circle falls
       * back to the uniform radius rather than claiming a length */
      delete state.lines[entry.path];
      return;
    }
    state.lines[entry.path] = Math.max(0, before + entry.add - entry.del);
  });
}
/* `index` is a position in GIT.commits (newest first); -1 means "now". */
function stateAt(index) {
  var state = { files: Object.create(null), lines: Object.create(null) };
  (GIT.base.files || []).forEach(function (p) { state.files[p] = 1; });
  var baseLines = GIT.base.lines || {};
  Object.keys(baseLines).forEach(function (p) {
    state.lines[p] = baseLines[p];
  });
  /* commits are newest first, so replay from the end forward and stop
   * at the one asked for */
  for (var k = GIT.commits.length - 2; k >= (index < 0 ? 0 : index); k--) {
    applyCommitToState(state, GIT.commits[k]);
  }
  return state;
}
function changedInCommit(commit) {
  var out = Object.create(null);
  (commit.files || []).forEach(function (entry) {
    if (!entry || typeof entry.path !== "string") { return; }
    if (entry.status === "D") { return; }   /* not on this commit's map */
    var lines = (entry.add === null || entry.add === undefined ||
      entry.del === null || entry.del === undefined)
      ? null : entry.add + entry.del;
    out[entry.path] = { lines: lines, status: entry.status };
  });
  return out;
}

/* --- building the tree --------------------------------------------- */
/* Sized by the line count the replay arrived at; the store's own count is
 * the fallback for a file git measured as binary. */
function historyLeaves(state) {
  return Object.keys(state.files).sort().map(function (raw) {
    var path = normPath(raw);
    var lines = hasOwn(state.lines, raw) ? state.lines[raw]
      : (histSizeByPath[path] || 0);
    return { path: path, name: path.slice(path.lastIndexOf("/") + 1),
      ext: extOf(path), size: lines, unit: "lines", idx: -1 };
  });
}
function historyAvailable() {
  return GIT.state === "ok" && GIT.commits.length > 0;
}
function ensureHistory() {
  var key = state.history.commit === null ? "@head" : state.history.commit;
  if (state.history.builtFor === key) { return; }
  state.history.builtFor = key;
  buildHistory();
}
function buildHistory() {
  while (viewportHist.firstChild) {
    viewportHist.removeChild(viewportHist.firstChild);
  }
  histLeafEls = [];
  var emptyBox = document.getElementById("historyEmpty");
  var emptyTxt = document.getElementById("historyEmptyText");
  if (!historyAvailable()) {
    emptyTxt.innerHTML = "<b>No commit history.</b><br>" +
      esc(gitUnavailableReason());
    emptyBox.hidden = false;
    state.history.root = null;
    document.getElementById("historyStats").textContent = "";
    renderHistoryLegend(null, "");
    return;
  }
  var index = state.history.commit === null ? -1
    : commitIndex(state.history.commit);
  var leaves = historyLeaves(stateAt(index));
  if (!leaves.length) {
    emptyTxt.innerHTML = "<b>Nothing was tracked at this commit.</b>";
    emptyBox.hidden = false;
    state.history.root = null;
    renderHistoryLegend(null, "");
    return;
  }
  emptyBox.hidden = true;
  var root = buildTree(leaves);
  packDir(root, leafRadiusScale(leaves));
  placeDir(root, 0, 0, 0);
  state.history.root = root;
  renderHistoryDir(root);
  applyHistoryColors();
  document.getElementById("historyStats").textContent =
    leaves.length + " files · " + root.nDirs + " directories" +
    (index < 0 ? " · now" : " · at " + GIT.commits[index].short);
  fitHistory();

  function renderHistoryDir(dir) {
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "rdir");
    c.setAttribute("cx", dir.cx.toFixed(1));
    c.setAttribute("cy", dir.cy.toFixed(1));
    c.setAttribute("r", dir.r.toFixed(1));
    var t = document.createElementNS(NS, "title");
    t.textContent = (dir.path || "(root)") + " · " + dir.nLeaves + " file(s)";
    c.appendChild(t);
    viewportHist.appendChild(c);
    if (dir.r >= 28 && dir.name) {
      var maxChars = Math.floor((dir.r * 1.5) / 6.5);
      if (maxChars >= 3) {
        var lbl = document.createElementNS(NS, "text");
        lbl.setAttribute("class", "rdir-label");
        lbl.setAttribute("x", dir.cx.toFixed(1));
        lbl.setAttribute("y", (dir.cy - dir.r + 13).toFixed(1));
        lbl.textContent = dir.name.length > maxChars ?
          dir.name.slice(0, maxChars - 1) + "…" : dir.name;
        viewportHist.appendChild(lbl);
      }
    }
    dir.items.forEach(function (it) {
      if (it.dir) { renderHistoryDir(it.dir); }
      else { renderHistoryLeaf(it.leaf); }
    });
  }
  function renderHistoryLeaf(leaf) {
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "hleaf");
    c.setAttribute("cx", leaf.cx.toFixed(1));
    c.setAttribute("cy", leaf.cy.toFixed(1));
    c.setAttribute("r", leaf.r.toFixed(1));
    var t = document.createElementNS(NS, "title");
    t.textContent = leaf.path + (leaf.size ? " · " + leaf.size + " lines" : "");
    c.appendChild(t);
    viewportHist.appendChild(c);
    histLeafEls.push({ el: c, leaf: leaf, title: t });
    if (leaf.r >= 10) {
      var maxChars = Math.floor((leaf.r * 2 - 4) / 5.4);
      if (maxChars >= 4) {
        var lbl = document.createElementNS(NS, "text");
        lbl.setAttribute("class", "rleaf-label");
        lbl.setAttribute("x", leaf.cx.toFixed(1));
        lbl.setAttribute("y", (leaf.cy + 3).toFixed(1));
        lbl.textContent = leaf.name.length > maxChars ?
          leaf.name.slice(0, maxChars - 1) + "…" : leaf.name;
        viewportHist.appendChild(lbl);
      }
    }
  }
}

/* --- colouring by what the commit changed --------------------------- */
var HIST_NEUTRAL = oklchHex(HIST_NEUTRAL_L, 0, 0);
function applyHistoryColors() {
  var index = state.history.commit === null ? -1
    : commitIndex(state.history.commit);
  var changed = index < 0 ? Object.create(null)
    : changedInCommit(GIT.commits[index]);
  var lo = Infinity, hi = -Infinity;
  Object.keys(changed).forEach(function (path) {
    var lines = changed[path].lines;
    if (lines === null) { return; }         /* binary: no number to scale */
    if (lines < lo) { lo = lines; }
    if (lines > hi) { hi = lines; }
  });
  histLeafEls.forEach(function (entry) {
    var hit = hasOwn(changed, entry.leaf.path) ? changed[entry.leaf.path]
      : null;
    var cls = "hleaf";
    var fill = HIST_NEUTRAL;
    var note = "";
    if (hit) {
      if (hit.lines === null) {
        /* changed, but git counts no lines in a binary file. Painting it
         * at the bottom of the scale would say "barely touched", which
         * is not something anyone knows. */
        cls += " changed unknown";
        note = " · changed (binary, lines not counted)";
      } else {
        cls += " changed";
        fill = cmapHex("summer", cmapNorm(hit.lines, lo, hi));
        note = " · " + hit.lines + " line(s) changed";
      }
    }
    entry.el.setAttribute("class", cls);
    entry.el.setAttribute("fill", fill);
    entry.el.setAttribute("data-lines",
      hit ? (hit.lines === null ? "binary" : String(hit.lines)) : "");
    entry.title.textContent = entry.leaf.path +
      (entry.leaf.size ? " · " + entry.leaf.size + " lines" : "") + note;
  });
  state.history.range = hi >= lo ? { lo: lo, hi: hi } : null;
  renderHistoryLegend(state.history.range, index < 0
    ? "select a commit to colour the files it changed"
    : "this commit changed no counted lines");
}
function renderHistoryLegend(range, note) {
  var box = document.getElementById("historyLegend");
  if (!box) { return; }
  box.innerHTML = "";
  if (!historyAvailable()) {
    legendMessage(box, gitUnavailableReason());
    return;
  }
  if (!range) {
    legendMessage(box, note || "nothing to colour");
    return;
  }
  renderCmapLegend(box, { cmap: "summer", unit: "lines changed" },
    range.lo, range.hi);
}

/* --- the commit list ------------------------------------------------ */
/* SHA as the title and the subject under it: a reader looking for a
 * commit they know scans shas, and a reader reading the history scans
 * subjects. The description belongs to neither scan, so it stays rolled
 * up until the commit is chosen. */
function renderCommitList() {
  var box = document.getElementById("commitList");
  if (!box) { return; }
  box.innerHTML = "";
  if (!historyAvailable()) {
    var why = document.createElement("p");
    why.className = "muted";
    why.textContent = gitUnavailableReason();
    box.appendChild(why);
    return;
  }
  GIT.commits.forEach(function (commit) {
    var item = document.createElement("div");
    item.className = "commit";
    item.setAttribute("data-sha", commit.sha);
    var head = document.createElement("div");
    head.className = "commit-head";
    var sha = document.createElement("span");
    sha.className = "commit-sha";
    sha.textContent = commit.short || commit.sha.slice(0, 7);
    var when = document.createElement("span");
    when.className = "commit-date";
    when.textContent = (commit.date || "").slice(0, 10);
    head.appendChild(sha);
    head.appendChild(when);
    var title = document.createElement("div");
    title.className = "commit-title";
    title.textContent = commit.title || "(no subject)";
    var body = document.createElement("div");
    body.className = "commit-body";
    var inner = document.createElement("div");
    inner.className = "commit-body-inner";
    inner.textContent = commit.body || "";
    body.appendChild(inner);
    item.appendChild(head);
    item.appendChild(title);
    item.appendChild(body);
    item.addEventListener("click", function () {
      selectCommit(state.history.commit === commit.sha ? null : commit.sha);
    });
    box.appendChild(item);
  });
  markSelectedCommit();
}
function markSelectedCommit() {
  var box = document.getElementById("commitList");
  if (!box) { return; }
  Array.prototype.forEach.call(box.children || [], function (item) {
    var on = item.getAttribute("data-sha") === state.history.commit;
    item.classList.toggle("selected", on);
    /* aria-expanded, not just a class: the roll-down is the only signal
     * a sighted reader gets that there is more text here. */
    item.setAttribute("aria-expanded", on ? "true" : "false");
  });
}
function selectCommit(sha) {
  state.history.commit = sha === undefined ? null : sha;
  markSelectedCommit();
  ensureHistory();
}

/* --- pan / zoom ----------------------------------------------------- */
function applyHistoryTransform() {
  viewportHist.setAttribute("transform",
    "translate(" + state.history.tx.toFixed(2) + "," +
    state.history.ty.toFixed(2) + ") scale(" +
    state.history.k.toFixed(4) + ")");
}
function fitHistory() {
  var root = state.history.root;
  if (!root) { return; }
  var bw = svgHist.clientWidth || 800, bh = svgHist.clientHeight || 600;
  var R = root.r + 20;
  state.history.k = clampK(Math.min(bw, bh) / (2 * R));
  state.history.tx = bw / 2 - root.cx * state.history.k;
  state.history.ty = bh / 2 - root.cy * state.history.k;
  applyHistoryTransform();
}
var histPanning = null;
svgHist.addEventListener("pointerdown", function (ev) {
  histPanning = { x: ev.clientX, y: ev.clientY, tx: state.history.tx,
    ty: state.history.ty };
  svgHist.classList.add("panning");
  try { svgHist.setPointerCapture(ev.pointerId); } catch (err) { /* ok */ }
});
svgHist.addEventListener("pointermove", function (ev) {
  if (!histPanning) { return; }
  state.history.tx = histPanning.tx + (ev.clientX - histPanning.x);
  state.history.ty = histPanning.ty + (ev.clientY - histPanning.y);
  applyHistoryTransform();
});
function endHistoryPointer(ev) {
  if (!histPanning) { return; }
  try { svgHist.releasePointerCapture(ev.pointerId); } catch (err) { /* */ }
  histPanning = null;
  svgHist.classList.remove("panning");
}
svgHist.addEventListener("pointerup", endHistoryPointer);
svgHist.addEventListener("pointercancel", endHistoryPointer);
svgHist.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  var nk = clampK(state.history.k * factor);
  factor = nk / state.history.k;
  var rect = svgHist.getBoundingClientRect();
  var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  state.history.tx = mx - (mx - state.history.tx) * factor;
  state.history.ty = my - (my - state.history.ty) * factor;
  state.history.k = nk;
  applyHistoryTransform();
}, { passive: false });
document.getElementById("btnHistoryFit").addEventListener("click", fitHistory);
document.getElementById("btnHistoryHead").addEventListener("click",
  function () { selectCommit(null); });

/* ================================================================== */
/* theme toggle                                                       */
/* ================================================================== */
/* The resolution itself already ran, inline in <head>, before the first
 * paint — this only wires the control. The button stays hidden until
 * that happens, because a toggle that cannot toggle (no script, no
 * `window.viewerTheme`) is worse than no toggle: the CSS media query
 * still themes the page correctly without it. */
(function wireTheme() {
  var theme = window.viewerTheme;
  var btn = document.getElementById("themeToggle");
  if (!theme || !btn) { return; }
  var icon = document.getElementById("themeIcon");
  var name = document.getElementById("themeName");
  var resolved = document.getElementById("themeResolved");
  var status = document.getElementById("themeStatus");
  var LABEL = { system: "System", light: "Light", dark: "Dark" };
  var ICON = { system: "◐", light: "☀", dark: "☾" };

  function paint(announce) {
    var mode = theme.mode;
    var now = theme.resolve(mode);
    if (icon) { icon.textContent = ICON[mode]; }
    if (name) { name.textContent = LABEL[mode]; }
    /* Only "System" needs to say what it currently resolves to: on the
     * explicit modes the name already is the answer. */
    if (resolved) {
      resolved.textContent = mode === "system" ? "(" + now + ")" : "";
    }
    btn.setAttribute("aria-label", "Theme: " + LABEL[mode] +
      (mode === "system" ? " (" + now + ")" : "") + " — click to change");
    if (announce && status) {
      status.textContent = "Theme " + LABEL[mode] +
        (mode === "system" ? ", currently " + now : "");
    }
  }

  btn.hidden = false;
  paint(false);
  btn.addEventListener("click", function () {
    var next = theme.MODES[(theme.MODES.indexOf(theme.mode) + 1) %
      theme.MODES.length];
    theme.mode = next;
    theme.remember(next);
    theme.apply(next);
    paint(true);
  });

  /* A live system change is honoured ONLY while in System mode — an
   * explicit choice must not be undone by the operating system. */
  var media = theme.query();
  if (media) {
    var onChange = function () {
      if (theme.mode !== "system") { return; }
      theme.apply("system");
      paint(false);
    };
    if (media.addEventListener) { media.addEventListener("change", onChange); }
    else if (media.addListener) { media.addListener(onChange); }
  }
})();

/* ================================================================== */
/* boot                                                               */
/* ================================================================== */
computeVisible();
if (N) { relayout(); } else { positionAll(); }
renderCommitList();
setTab("graph");
})();
