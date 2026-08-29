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
var LABEL_FOLDER_BUMP = 0;    /* a folder reads at a file's size, as asked */
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

/* The largest circle of each kind, so "proportional" has something to be
 * proportional TO. Walked once per build, not per label. */
function maxRadii(root) {
  var out = { dir: root ? root.r || 0 : 0, file: 0 };
  (function walk(dir) {
    if (!dir) { return; }
    if (dir.r > out.dir) { out.dir = dir.r; }
    (dir.items || []).forEach(function (it) {
      if (it.dir) { walk(it.dir); }
      else if (it.leaf && it.leaf.r > out.file) { out.file = it.leaf.r; }
    });
  })(root);
  return out;
}

function labelSize(radius, maxRadius, isDir) {
  var scale = maxRadius > 0 ? Math.min(1, radius / maxRadius) : 0;
  return LABEL_MAX_FILE * scale + (isDir ? LABEL_FOLDER_BUMP : 0);
}

/* How many characters this circle holds at this size. */
function labelChars(radius, size) {
  return Math.floor((radius * 1.8) / (size * LABEL_CHAR_W));
}
/* The size at which the circle can hold `LABEL_MIN_CHARS`, when its own
 * computed size cannot. This is where "every circle is named" and "no
 * label leaves its circle" are reconciled: the label shrinks rather than
 * disappearing or spilling. */
function labelFit(radius, size) {
  if (labelChars(radius, size) >= LABEL_MIN_CHARS) { return size; }
  return (radius * 1.8) / (LABEL_MIN_CHARS * LABEL_CHAR_W);
}
function labelText(name, radius, size) {
  var cap = Math.min(LABEL_MAX_CHARS,
                     Math.max(LABEL_MIN_CHARS, labelChars(radius, size)));
  var text = String(name || "");
  return text.length > cap ? text.slice(0, cap - 1) + "\u2026" : text;
}

/* `circle` is {cx, cy, r, name}; `kind` is "dir" or "leaf". Returns the
 * <text> element, or null when there is no room to say anything. */
function makeLabel(circle, kind, maxRadius, classPrefix) {
  var isDir = kind === "dir";
  var size = labelFit(circle.r, labelSize(circle.r, maxRadius, isDir));
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
window.OrchPacking = {
  /* geometry */
  PACK_PAD: PACK_PAD, DIR_PAD: DIR_PAD,
  LEAF_R_BASE: LEAF_R_BASE, LEAF_R_UNIFORM: LEAF_R_UNIFORM,
  leafRadiusScale: leafRadiusScale,
  buildTree: buildTree, packDir: packDir, placeDir: placeDir,
  /* labels */
  LABEL_MAX_FILE: LABEL_MAX_FILE, LABEL_FOLDER_BUMP: LABEL_FOLDER_BUMP,
  LABEL_MAX_CHARS: LABEL_MAX_CHARS, LABEL_CHAR_W: LABEL_CHAR_W,
  LABEL_MIN_CHARS: LABEL_MIN_CHARS, LABEL_HALO: LABEL_HALO,
  maxRadii: maxRadii, labelSize: labelSize, labelText: labelText,
  labelChars: labelChars, labelFit: labelFit,
  makeLabel: makeLabel,
  /* colour. `cmapHex` answers null for a name it does not know, so the
     CALLER supplies its own neutral — which is what the fallback always
     was, and keeps this file free of the page's palette. */
  cmapHex: cmapHex, cmapNorm: cmapNorm, cmapIndex: cmapIndex,
  hex2: hex2, roundHalfEven: roundHalfEven, NS: NS,
  cmapNames: CMAP_NAMES
};
}());
