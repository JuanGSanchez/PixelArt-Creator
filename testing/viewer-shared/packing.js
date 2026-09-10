/* packing.js — the circle packing, the labels and the colormaps, once.

   WHY THIS IS SHARED RATHER THAN COPIED. The memory viewer's Repo and History
   frames and the coverage viewer's Coverage frame draw the SAME picture of a
   file tree: front-chain packing, a radius anchored at the smallest file,
   a folder's name at its rim and a file's at its centre. Every one of those
   rules was paid for — the spiral packer this replaced was quadratic, packed
   at one part in eighty of the area it needed, and could place a circle
   OVERLAPPING another when it ran out of guard, silently. A second copy is a
   second place for each of those lessons to be re-learned by whoever edits
   only one of them; the same argument `viewer_serving.py` makes about the
   launcher text.

   IT TOUCHES NO DOM AND HOLDS NO STATE except the constants below. It is
   loaded as a plain script BEFORE the page's own viewer, defines one global,
   and does nothing else — so a page that parses it and never uses it has paid
   nothing.

   Everything here is a pure function of its arguments. `makeLabel` builds one
   <text> element and returns it; the caller decides where it goes.
*/
(function () {
"use strict";

/* The SVG namespace `makeLabel` creates its <text> in, and the channel
   formatter the colormaps round with. Both were the page's; both are
   needed here, and a second copy of a rounding rule that disagrees on 8
   of 256 entries is a second colormap. */
var NS = "http://www.w3.org/2000/svg";
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

/* ==== cmap ==== */
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
  /* A name this file does not know. The CALLER supplies its own
     neutral — which is what the page's `NO_EXT_COLOR` always was
     here, and keeping it there is what frees this file of the
     page's palette. */
  return null;
}
/* A single observed value is not a range: it sits mid-scale rather than
 * pinning one end and telling the reader something the data does not. */
function cmapNorm(value, lo, hi) {
  if (!(hi > lo)) { return 0.5; }
  return (value - lo) / (hi - lo);
}

/* --- the colormap legend strip -------------------------------------- */
/* THE KEY IS DRAWN WITH THE MAP: the same cmapHex() calls that coloured
 * the circles, so it cannot drift from them. Only the WORDS differ between
 * the two viewers, so the caller supplies every string, and whatever it
 * wants BELOW the note (the coverage viewer's "never measured" swatch) it
 * appends itself afterwards. `cmapName` is one of CMAP_NAMES, so cmapHex
 * always answers and the caller needs no neutral of its own. */
var LEGEND_STEPS = 28;
function cmapStrip(box, cmapName, loText, hiText, noteText) {
  var bar = document.createElement("div");
  bar.className = "cmap-bar";
  for (var k = 0; k < LEGEND_STEPS; k++) {
    var cell = document.createElement("span");
    cell.style.background = cmapHex(cmapName, k / (LEGEND_STEPS - 1));
    bar.appendChild(cell);
  }
  box.appendChild(bar);
  var limits = document.createElement("div");
  limits.className = "cmap-limits";
  var low = document.createElement("span");
  low.textContent = loText;
  var high = document.createElement("span");
  high.textContent = hiText;
  limits.appendChild(low);
  limits.appendChild(high);
  box.appendChild(limits);
  var note = document.createElement("div");
  note.className = "hint legend-note";
  note.textContent = noteText;
  box.appendChild(note);
}

/* ==== consts ==== */
var PACK_PAD = 2, DIR_PAD = 6;
var LEAF_R_BASE = 3, LEAF_R_UNIFORM = 7;

/* ==== scale ==== */
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

/* ==== tree ==== */
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

/* ==== label ==== */
/* EVERY CIRCLE IS NAMED. What these numbers replaced, and why.
 *
 * The label used to be dropped twice over: below `LABEL_MIN_SIZE` it was
 * not drawn at all, and a circle too narrow for three characters got
 * nothing either. On a real tree that is almost every circle — measured
 * on a 400-file fixture, 502 circles carried 8 labels. A map whose
 * circles are anonymous is a map you cannot read without clicking, and
 * the thing a reader wants to know first is WHICH FILE that is.
 *
 * So: no minimum size, no suppression, and one size rule for folders and
 * files alike. What remains is the width rule — a label never leaves its
 * own circle, so nothing overlaps at any zoom — and a circle too narrow
 * for `LABEL_MIN_CHARS` at its computed size gets the size that fits
 * them, not silence. On the smallest circles the glyphs are sub-pixel
 * until you zoom in, and zooming in is what they are for: the text
 * scales with the frame, so a name that is a smudge at the fit is
 * legible the moment you look at it. */
var LABEL_MAX_FILE = 36;      /* 2x again: 4x the 9px the stylesheet had */
var LABEL_MIN_CHARS = 3;      /* what "elided" must still manage to say */
var LABEL_MAX_CHARS = 20;     /* the cap, before the width test */
var LABEL_CHAR_W = 0.58;      /* mean glyph width as a fraction of size */
/* THE HALO, AS A FRACTION OF THE LABEL'S OWN SIZE. A name is drawn ON its
 * circle, and a circle's fill is DATA — a file type, a connection count, a
 * percentage of lines that ran. Dark text on a dark end of a ramp is not a
 * name anybody reads, and lightening the text instead would lose it on the
 * light end. So every label is painted with a halo of the page's own
 * background, `paint-order: stroke` (the stylesheet's half), which reads
 * over any fill either way round.
 *
 * IT IS SET PER ELEMENT, NOT IN THE STYLESHEET, for the same reason
 * `font-size` is: a fixed `stroke-width` is a smear over a 0.03px label and
 * invisible on a 36px one. A stylesheet rule would either win over this or
 * be dead, and a dead rule is a lie somebody maintains. */
var LABEL_HALO = 0.16;

/* A label is a fraction of ITS OWN circle, capped.
 *
 * WHAT THIS REPLACED, AND WHY IT WAS WRONG. The size used to be
 * `LABEL_MAX_FILE * (radius / maxRadius)` — a fraction of the frame's LARGEST
 * circle of that kind. Two consequences, both visible:
 *
 *   1. Folders and files were normalised against DIFFERENT maxima — folders
 *      against the root, files against the biggest file — so on this
 *      container's own map every folder came out at font/radius = 0.0583 and
 *      every file at 0.2069. A folder's name was three and a half times
 *      smaller, relative to the circle carrying it, than a file's.
 *   2. `maxRadius` is a property of the FRAME, so the same folder drawn on two
 *      frames got two different sizes, which is what made the Repo and History
 *      maps disagree about a name they were both drawing.
 *
 * Anchoring on the circle itself removes both at once: the ratio is the same
 * everywhere, and a bigger circle always carries a bigger name until the cap.
 *
 * THE TWO RATIOS ARE THE KNOBS. `LABEL_R_RATIO_FILE` is set to what files
 * effectively received before, so their appearance is unchanged;
 * `LABEL_R_RATIO_DIR` is the one that was implicitly ~0.058 and is now a
 * number somebody chose. Raise it for louder folder names, lower it if they
 * begin to crowd the children they enclose. */
var LABEL_R_RATIO_FILE = 0.207;
var LABEL_R_RATIO_DIR = 0.120;

function labelSize(radius, isDir) {
  var ratio = isDir ? LABEL_R_RATIO_DIR : LABEL_R_RATIO_FILE;
  return Math.min(LABEL_MAX_FILE, radius * ratio);
}

/* Outline weight, likewise a fraction of the circle rather than one number for
 * every circle on the map. A flat 0.5 is a heavy ring around a 3-px file and
 * an invisible hairline around a 300-px folder, so the same declaration reads
 * as two different design decisions depending on where you look.
 *
 * Returned as a pair because hover is a MULTIPLE of the resting weight, not a
 * second absolute: thickening to three times its own width is legible at every
 * size, where a jump to a fixed 1.5 is dramatic on a small circle and
 * imperceptible on a large one. Clamped at both ends so a hairline stays
 * visible and a giant circle is not drawn as a doughnut. */
var STROKE_RATIO = 0.012;
var STROKE_MIN = 0.4;
var STROKE_MAX = 3.0;
var STROKE_HOVER_MULT = 3;

function strokeFor(radius) {
  var w = Math.max(STROKE_MIN, Math.min(STROKE_MAX, radius * STROKE_RATIO));
  return { width: w, hover: w * STROKE_HOVER_MULT };
}

/* Set the two custom properties the stylesheet reads. Inline, per circle, so
 * the RULES stay in packing.css — `stroke-width: var(--leaf-stroke)` and its
 * hover — and only the VALUES vary. Writing `stroke-width` directly as a
 * presentation attribute would be outranked by that rule and do nothing, which
 * is the same trap the colour ramps fell into. */
function applyStroke(el, radius) {
  var s = strokeFor(radius);
  el.style.setProperty("--leaf-stroke", s.width.toFixed(2));
  el.style.setProperty("--leaf-stroke-hover", s.hover.toFixed(2));
  el.style.setProperty("--dir-stroke", s.width.toFixed(2));
  return s;
}

/* How many characters this circle holds at this size. */
function labelChars(radius, size) {
  return Math.floor((radius * 1.8) / (size * LABEL_CHAR_W));
}
/* The largest size at which this circle can hold the WHOLE name — never
 * larger than the size the radius already earned.
 *
 * WHAT THIS FIXES. `labelSize` scales the font linearly with `r / maxRadius`,
 * so `r` CANCELS out of `labelChars`: every leaf on a frame ends up with the
 * same character cap, and that cap is set by the frame's LARGEST circle
 * (`floor(1.8 * maxRadius / (LABEL_MAX_FILE * LABEL_CHAR_W))`). Measured on
 * the two frames that prompted this: maxRadius 130 gives every label 11
 * characters, maxRadius 400 gives 34. So the same file was written in full on
 * one frame and elided on another, for a reason that has nothing to do with
 * the circle carrying the label.
 *
 * The observed case: a leaf of radius 130 at font 36 has 234 px of room and
 * spent 229.7 of it printing `memory_gra…` — it elided a 15-character name
 * while nearly the whole width sat unused, because the only question ever
 * asked was "how many characters fit at the size I already chose?". Nothing
 * asked the inverse, which is the one that has an answer: "how large may the
 * size be so the whole word fits?".
 *
 * So the name is now an INPUT. The floor is `LABEL_MAX_CHARS`, which is
 * already the hard cap on characters — this function will shrink far enough
 * to show that many and no further, and `labelText` elides whatever is still
 * too long. The old guarantee is unchanged and is simply the `need ==
 * LABEL_MIN_CHARS` case: called with two arguments, this returns exactly what
 * it always did, because `min(size, size_at_MIN_CHARS)` is `size` precisely
 * when MIN_CHARS already fit. */
function labelFit(radius, size, name) {
  var need = String(name == null ? "" : name).length;
  if (need > LABEL_MAX_CHARS) { need = LABEL_MAX_CHARS; }
  if (need < LABEL_MIN_CHARS) { need = LABEL_MIN_CHARS; }
  return Math.min(size, (radius * 1.8) / (need * LABEL_CHAR_W));
}
function labelText(name, radius, size) {
  var cap = Math.min(LABEL_MAX_CHARS,
                     Math.max(LABEL_MIN_CHARS, labelChars(radius, size)));
  var text = String(name || "");
  return text.length > cap ? text.slice(0, cap - 1) + "\u2026" : text;
}

/* `circle` is {cx, cy, r, name}; `kind` is "dir" or "leaf". Returns the
 * <text> element, or null when there is no room to say anything. */
/* `maxRadius` is gone from this signature. It was the frame's biggest circle,
 * and a label that depends on it is a label that changes when a file somewhere
 * else in the tree grows — which is exactly how two frames came to draw one
 * name at two sizes. Every caller passed it; none needs it now. */
function makeLabel(circle, kind, classPrefix) {
  var isDir = kind === "dir";
  /* The name is passed so the size can be fitted to the WORD, not merely to a
   * character count derived from the frame's biggest circle. Every frame that
   * draws a packed map goes through here, so all of them are fixed at once. */
  var size = labelFit(circle.r, labelSize(circle.r, isDir), circle.name);
  var shown = labelText(circle.name, circle.r, size);
  if (!shown) { return null; }   /* a circle with no name of its own */
  var lbl = document.createElementNS(NS, "text");
  lbl.setAttribute("class", classPrefix + (isDir ? "dir-label" : "leaf-label"));
  lbl.setAttribute("font-size", size.toFixed(2));
  lbl.setAttribute("stroke-width", (size * LABEL_HALO).toFixed(3));
  lbl.setAttribute("x", circle.cx.toFixed(1));
  /* A folder's name hangs its own font-size below the rim; a file's sits on
   * the centre line (the +0.34em is the optical middle of a cap-height run,
   * not a nudge). Orientation and centring are unchanged from before. */
  lbl.setAttribute("y", isDir
    ? (circle.cy - circle.r + size).toFixed(1)
    : (circle.cy + size * 0.34).toFixed(1));
  lbl.textContent = shown;
  return lbl;
}

/* ==== pack ==== */
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

/* The one global. Named for what it is rather than for the page that first
   held it: neither viewer owns this. */
/* ==== stage ==== */
/* ONE CONTROLLER FOR THREE PACKED FRAMES. The memory viewer's Repo and
 * History stages and the coverage viewer's Coverage stage were the same
 * eighty lines written three times, differing only in the names they
 * spelled; the wheel arithmetic and the fit were word for word identical in
 * all three. (The memory viewer's GRAPH stage is NOT one of them and is not
 * here: it drags nodes, which is a different gesture on the same events.)
 *
 * `opts.state` is the caller's own {tx, ty, k, floor, root} record and stays
 * the caller's — this writes the four numbers and reads `root`. `fitPad` is
 * the margin the fit leaves around the packing, in the packing's own units.
 *
 * ONSELECT IS WHAT MAKES A STAGE SELECTABLE, and its absence is a feature.
 * Given one, a `pointerdown` on a leaf CLAIMS the press through `press(ev,
 * id)` and the matching `pointerup` selects it -- because the stage captures
 * the pointer, so the `click` that ends the gesture is delivered to the
 * <svg> and not to the circle, and a leaf that only listened for `click` is
 * never selected at all. That same pointerup then suppresses the click, or
 * the stage's own "put the current file down" handler would undo the
 * selection one event later. Given NO onSelect, as the History stage gives
 * none, no `click` listener is attached at all: that frame pans and zooms
 * and selects nothing, because its commit is chosen from the list beside
 * it. */
function attachStage(svg, viewport, opts) {
  var state = opts.state;
  var minK = opts.minK, maxK = opts.maxK, fitPad = opts.fitPad;
  var onSelect = opts.onSelect || null;
  var panning = null, suppress = false, pressed = null;

  function applyTransform() {
    viewport.setAttribute("transform",
      "translate(" + state.tx.toFixed(2) + "," + state.ty.toFixed(2) +
      ") scale(" + state.k.toFixed(4) + ")");
  }
  /* A FIT THAT CAN ACTUALLY FIT. The floor comes from the CONTENT, never
   * from a constant. Run through a constant minimum, a packing whose true
   * fit falls below it opens far too close and no amount of scrolling out
   * reaches the whole graph -- every wheel step is clamped by the same
   * number. The Repo frame learned this the hard way at 7779 files. `minK`
   * stays the floor for ordinary trees; a tree that needs less sets its
   * own, with room to spare beneath it, so "the whole thing" is a place
   * you can arrive at rather than a limit you press against. */
  function clampK(k) {
    return Math.max(state.floor, Math.min(maxK, k));
  }
  function fit() {
    var root = state.root;
    if (!root) { return; }
    var bw = svg.clientWidth || 800, bh = svg.clientHeight || 600;
    var R = root.r + fitPad;
    var k = Math.min(bw, bh) / (2 * R);
    state.floor = Math.min(minK, k * 0.5);
    state.k = clampK(k);
    state.tx = bw / 2 - root.cx * state.k;
    state.ty = bh / 2 - root.cy * state.k;
    applyTransform();
  }
  function startPan(ev) {
    panning = { x: ev.clientX, y: ev.clientY, tx: state.tx, ty: state.ty,
      moved: false };
    svg.classList.add("panning");
    try { svg.setPointerCapture(ev.pointerId); } catch (err) { /* ok */ }
  }
  function press(ev, id) {
    suppress = false;
    pressed = id;
    startPan(ev);
  }
  function endPointer(ev) {
    if (!panning) { return; }
    if (panning.moved) { suppress = true; }
    else if (onSelect && pressed !== null) {
      onSelect(pressed);
      suppress = true;
    }
    try { svg.releasePointerCapture(ev.pointerId); } catch (err) { /* */ }
    panning = null;
    svg.classList.remove("panning");
  }
  svg.addEventListener("pointerdown", function (ev) {
    suppress = false;
    pressed = null;              /* a press on the background selects nothing */
    startPan(ev);
  });
  svg.addEventListener("pointermove", function (ev) {
    if (!panning) { return; }
    var dx = ev.clientX - panning.x, dy = ev.clientY - panning.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) { panning.moved = true; }
    state.tx = panning.tx + dx;
    state.ty = panning.ty + dy;
    applyTransform();
  });
  svg.addEventListener("pointerup", endPointer);
  svg.addEventListener("pointercancel", endPointer);
  if (onSelect) {
    svg.addEventListener("click", function () {
      if (suppress) { suppress = false; return; }
      /* A press that landed on nothing, and did not pan: the reader is
       * putting the current file down. */
      onSelect(null);
    });
  }
  /* `{ passive: false }` is load-bearing: a passive wheel listener may not
   * call preventDefault, and the page would scroll instead of zooming. */
  svg.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
    var nk = clampK(state.k * factor);
    factor = nk / state.k;       /* the factor the CLAMP allowed, not the ask */
    var rect = svg.getBoundingClientRect();
    var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    state.tx = mx - (mx - state.tx) * factor;
    state.ty = my - (my - state.ty) * factor;
    state.k = nk;
    applyTransform();
  }, { passive: false });
  return { fit: fit, press: press };
}

window.OrchPacking = {
  /* geometry */
  PACK_PAD: PACK_PAD, DIR_PAD: DIR_PAD,
  LEAF_R_BASE: LEAF_R_BASE, LEAF_R_UNIFORM: LEAF_R_UNIFORM,
  leafRadiusScale: leafRadiusScale,
  buildTree: buildTree, packDir: packDir, placeDir: placeDir,
  /* labels */
  LABEL_MAX_FILE: LABEL_MAX_FILE,
  LABEL_MAX_CHARS: LABEL_MAX_CHARS, LABEL_CHAR_W: LABEL_CHAR_W,
  LABEL_MIN_CHARS: LABEL_MIN_CHARS, LABEL_HALO: LABEL_HALO,
  labelSize: labelSize, labelText: labelText,
  LABEL_R_RATIO_FILE: LABEL_R_RATIO_FILE,
  LABEL_R_RATIO_DIR: LABEL_R_RATIO_DIR,
  STROKE_RATIO: STROKE_RATIO, STROKE_MIN: STROKE_MIN,
  STROKE_MAX: STROKE_MAX, STROKE_HOVER_MULT: STROKE_HOVER_MULT,
  strokeFor: strokeFor, applyStroke: applyStroke,
  labelChars: labelChars, labelFit: labelFit,
  makeLabel: makeLabel,
  /* colour. `cmapHex` answers null for a name it does not know, so the
     CALLER supplies its own neutral — which is what the fallback always
     was, and keeps this file free of the page's palette. */
  cmapHex: cmapHex, cmapNorm: cmapNorm, cmapIndex: cmapIndex,
  cmapStrip: cmapStrip, LEGEND_STEPS: LEGEND_STEPS,
  attachStage: attachStage,
  hex2: hex2, roundHalfEven: roundHalfEven, NS: NS,
  cmapNames: CMAP_NAMES
};
}());
