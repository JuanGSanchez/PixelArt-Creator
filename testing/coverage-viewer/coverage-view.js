/* coverage-view.js — the test-coverage viewer's behaviour (FROZEN ASSET).
 *
 * Copied byte-identically next to coverage-view.html in every repository that
 * carries a viewer; never edited per project. Constraints:
 *   - vanilla ES5-compatible JS, no dependencies, no network access, must work
 *     from file:// (which is why the data travels inline in the HTML);
 *   - determinism: the page is a pure function of the payload. Nothing is
 *     sorted by anything the payload does not carry, and nothing is derived
 *     from the wall clock.
 *
 * TWO FRAMES, TWO DIFFERENT CLAIMS.
 *
 *   METRICS  counts MENTIONS of a name, read out of the source with `ast`.
 *            It can see a call nobody ever executes and cannot see a call
 *            made through dynamic dispatch. It is a map of what the suite
 *            SAYS it touches.
 *   COVERAGE counts lines that RAN, read out of the artefact the suite's own
 *            runner wrote. It knows nothing about names.
 *
 * A page that let a reader carry one frame's meaning into the other would be
 * believed for the wrong thing, so the caveat block sits ABOVE both and its
 * CONTENTS CHANGE WITH THE FRAME. On Metrics, "not mentioned" is never
 * called "uncovered" and a function reached only through another function is
 * labelled INDIRECT rather than folded into one total. On Coverage, a file
 * the artefact never saw is drawn apart and counted, never drawn as 0%.
 */
(function () {
"use strict";

function fatal(message) {
  var p = document.createElement("pre");
  p.style.cssText = "padding:24px;white-space:pre-wrap";
  p.textContent = "coverage-view.html could not load its data: " + message +
    " Regenerate the page with coverage_viz.py.";
  document.body.innerHTML = "";
  document.body.appendChild(p);
}

var DATA;
try {
  DATA = JSON.parse(document.getElementById("coverage-data").textContent);
} catch (err) {
  fatal(String(err && err.message || err));
  return;
}

var TESTS = DATA.tests || [];
var SOURCES = DATA.sources || [];
var COVERAGE = DATA.coverage || [];
var UNCOVERED = DATA.uncovered || [];
/* The Coverage frame's half. `EXEC.state` is always set and always says
 * which of four worlds this is — ok / stale / absent / unreadable — and the
 * page prints it beside every number it produced. An execution claim whose
 * provenance is not on screen is the kind of number people quote for years.
 * Both default to the shape they would have with nothing measured, so a
 * payload written before this frame existed renders the honest empty page
 * rather than throwing. */
var EXEC = DATA.execution || { state: "absent", detail: "", artefact: "",
                               measured_at: "", percent: null, files: {},
                               measured: 0, unmeasured: 0 };
var EXECUTED = DATA.executed || [];

function el(tag, cls, text) {
  var node = document.createElement(tag);
  if (cls) { node.className = cls; }
  if (text !== undefined && text !== null) { node.textContent = String(text); }
  return node;
}

function byId(id) { return document.getElementById(id); }

/* ---------- header and the caveat ---------------------------------- */
byId("project").textContent =
  DATA.project ? "· " + DATA.project + " (" + DATA.kind + ")" : "";
byId("declaredIn").textContent = DATA.declared_in || "no declaration";

/* WHERE THE MEASUREMENT CAME FROM, in one sentence, per state. Printed
 * FIRST in the Coverage frame's caveat block and again in its sidebar: a
 * reader meets it before the first number either way. */
function executionProvenance() {
  var where = EXEC.artefact || "the coverage artefact";
  if (EXEC.state === "absent") {
    return EXEC.detail || ("Nothing has been measured in this clone: " +
      where + " does not exist. Every file below is drawn as unmeasured.");
  }
  if (EXEC.state === "unreadable") {
    return "The measurement could not be read from " + where + " — " +
      (EXEC.detail || "unknown error") + ". Nothing below is a measurement.";
  }
  var line = "Measured " + EXEC.measured + " file(s), " +
    (EXEC.percent === null ? "no overall figure"
      : EXEC.percent.toFixed(1) + "% of lines overall") +
    ", from " + where +
    (EXEC.measured_at ? " written " + EXEC.measured_at : "") + ".";
  if (EXEC.state === "stale") {
    line += " " + (EXEC.detail || "A source has changed since.");
  }
  return line;
}

function renderLimits(frame) {
  var title = byId("limitTitle");
  var list = byId("limitList");
  list.textContent = "";
  if (frame === "coverage") {
    title.textContent = "What this measurement is, and is not";
    list.appendChild(el("li", null, executionProvenance()));
    (DATA.execution_limits || []).forEach(function (line) {
      list.appendChild(el("li", null, line));
    });
    return;
  }
  title.textContent = "What these numbers are, and are not";
  (DATA.limits || []).forEach(function (line) {
    list.appendChild(el("li", null, line));
  });
  if (!DATA.types_declared) {
    list.appendChild(el("li", null,
      "This repository declares no `types` map, so every suite below is " +
      "reported as unclassified. That is a finding, not a default: add " +
      "`types` to " + (DATA.declared_in || "the declaration file") +
      " and the level of each test becomes answerable by a program."));
  }
  if (DATA.truncated) {
    list.appendChild(el("li", null,
      "The walk stopped at its file limit, so this page is INCOMPLETE."));
  }
  (DATA.missing_roots || []).forEach(function (root) {
    list.appendChild(el("li", null,
      "Declared source root `" + root + "` does not exist. A stale " +
      "declaration is worse than none, because it looks answered."));
  });
}

/* ---------- the numbers -------------------------------------------- */
(function summary() {
  var testFns = 0;
  TESTS.forEach(function (t) { testFns += (t.functions || []).length; });
  var sourceFns = 0;
  SOURCES.forEach(function (s) { sourceFns += (s.functions || []).length; });
  var direct = COVERAGE.filter(function (c) {
    return (c.direct || []).length;
  }).length;

  var cards = [
    ["test files", TESTS.length, ""],
    ["test functions", testFns, ""],
    ["functions in source", sourceFns, ""],
    ["mentioned directly", direct, ""],
    ["reached only indirectly", COVERAGE.length - direct, ""],
    ["not mentioned anywhere", UNCOVERED.length, "gap"],
    ["unclassified suites", (DATA.unclassified || []).length,
     (DATA.unclassified || []).length ? "warn" : ""]
  ];
  var box = byId("summary");
  cards.forEach(function (entry) {
    var card = el("div", "card" + (entry[2] ? " " + entry[2] : ""));
    card.appendChild(el("div", "n", entry[1]));
    card.appendChild(el("div", "k", entry[0]));
    box.appendChild(card);
  });
}());

/* ---------- panes --------------------------------------------------- */
function typeBadge(kind) {
  return kind ? el("span", "badge type", kind)
              : el("span", "badge warn", "unclassified");
}

function renderSources(term) {
  var pane = byId("paneSources");
  pane.textContent = "";
  var shown = 0;
  COVERAGE.forEach(function (record) {
    var hay = (record.source + " " + record.function).toLowerCase();
    if (term && hay.indexOf(term) === -1) { return; }
    shown++;
    var row = el("div", "row");
    var head = el("div", "row-head");
    head.appendChild(el("span", "name", record.function));
    head.appendChild(el("span", "where",
      record.source + ":" + record.line));
    (record.types || []).forEach(function (kind) {
      head.appendChild(typeBadge(kind));
    });
    if (!(record.types || []).length) {
      head.appendChild(el("span", "badge warn", "unclassified"));
    }
    if (record.ambiguous) {
      head.appendChild(el("span", "badge warn", "ambiguous name"));
    }
    row.appendChild(head);
    appendList(row, "direct", record.direct);
    appendList(row, "indirect", record.indirect);
    pane.appendChild(row);
  });
  return shown;
}

function appendList(row, kind, entries) {
  entries = entries || [];
  if (!entries.length) { return; }
  var head = el("div", "sub");
  head.appendChild(el("span", "badge " + kind,
    kind + " · " + entries.length));
  row.appendChild(head);
  var list = el("ul");
  entries.forEach(function (nodeid) {
    list.appendChild(el("li", null, nodeid));
  });
  row.appendChild(list);
}

function renderTests(term) {
  var pane = byId("paneTests");
  pane.textContent = "";
  var shown = 0;
  TESTS.forEach(function (test) {
    if (term && test.path.toLowerCase().indexOf(term) === -1) { return; }
    shown++;
    var row = el("div", "row");
    var head = el("div", "row-head");
    head.appendChild(el("span", "name", test.path));
    head.appendChild(typeBadge(test.type));
    head.appendChild(el("span", "where",
      (test.functions || []).length + " test function(s)"));
    if (test.error) {
      head.appendChild(el("span", "badge none", test.error));
    }
    row.appendChild(head);
    if ((test.mentions || []).length) {
      var sub = el("div", "sub");
      sub.appendChild(el("span", "badge direct",
        "mentions · " + test.mentions.length));
      row.appendChild(sub);
      var list = el("ul");
      test.mentions.forEach(function (name) {
        list.appendChild(el("li", null, name));
      });
      row.appendChild(list);
    } else {
      row.appendChild(el("div", "sub",
        "No product function is mentioned by name here. That is expected for " +
        "a suite that drives a CLI in a subprocess — and it is exactly the " +
        "case this page cannot see into."));
    }
    pane.appendChild(row);
  });
  return shown;
}

function renderOutputs(term) {
  var pane = byId("paneOutputs");
  pane.textContent = "";
  var shown = 0;
  TESTS.forEach(function (test) {
    (test.functions || []).forEach(function (fn) {
      var nodeid = test.path + "::" + fn.name;
      if (term && nodeid.toLowerCase().indexOf(term) === -1) { return; }
      shown++;
      var row = el("div", "row");
      var head = el("div", "row-head");
      head.appendChild(el("span", "name", fn.name));
      head.appendChild(el("span", "where", test.path + ":" + fn.line));
      head.appendChild(typeBadge(test.type));
      row.appendChild(head);
      var list = el("ul");
      (fn.outputs || []).forEach(function (out) {
        var item = el("li");
        item.appendChild(el("span", "badge " +
          (out.kind === "workspace" ? "direct" : "indirect"), out.kind));
        item.appendChild(document.createTextNode(" " + out.value));
        list.appendChild(item);
      });
      row.appendChild(list);
      pane.appendChild(row);
    });
  });
  return shown;
}

function renderGaps(term) {
  var pane = byId("paneGaps");
  pane.textContent = "";
  pane.appendChild(el("div", "sub",
    "Functions no test mentions BY NAME, at any depth. This is a question, " +
    "not a verdict: a function reached only through dynamic dispatch, or " +
    "exercised by a suite that drives a CLI in a subprocess, is invisible " +
    "here and appears in this list."));
  var shown = 0;
  UNCOVERED.forEach(function (record) {
    var hay = (record.source + " " + record.function).toLowerCase();
    if (term && hay.indexOf(term) === -1) { return; }
    shown++;
    var row = el("div", "row");
    var head = el("div", "row-head");
    head.appendChild(el("span", "name", record.function));
    head.appendChild(el("span", "where",
      record.source + ":" + record.line));
    head.appendChild(el("span", "badge none", "not mentioned"));
    row.appendChild(head);
    pane.appendChild(row);
  });
  return shown;
}

/* ---------- tabs, filter -------------------------------------------- */
var PANES = [
  ["tabSources", "paneSources", renderSources],
  ["tabTests", "paneTests", renderTests],
  ["tabOutputs", "paneOutputs", renderOutputs],
  ["tabGaps", "paneGaps", renderGaps]
];
var active = 0;

function draw() {
  var term = (byId("filter").value || "").trim().toLowerCase();
  var shown = 0;
  PANES.forEach(function (entry, index) {
    byId(entry[1]).hidden = index !== active;
    byId(entry[0]).className = index === active ? "active" : "";
    if (index === active) { shown = entry[2](term); }
  });
  byId("count").textContent = shown + " shown";
  var empty = byId("empty");
  empty.hidden = shown !== 0;
  empty.textContent = term
    ? "Nothing here matches " + JSON.stringify(term) + "."
    : "Nothing to show in this view.";
}

PANES.forEach(function (entry, index) {
  byId(entry[0]).addEventListener("click", function () {
    active = index;
    draw();
  });
});
byId("filter").addEventListener("input", draw);

/* ==================================================================
   THE COVERAGE FRAME
   ==================================================================
   The memory viewer's Repo frame, drawn from the measurement rather than
   from the file tree: same circle packing, same label rule, same plasma
   ramp the Repo frame's "Connections" mode uses. All of it comes from
   `viewer-shared/packing.js`, loaded by the page ahead of this script —
   two copies of a packing solver are two places for every lesson in it to
   be re-learned, and the two frames would start disagreeing about how big
   a folder name is.

   SIZE IS BYTES, exactly as in the Repo frame, so one file is the SAME
   circle in both pages and only its colour changes. Colour is the fraction
   of the file's lines that ran. A file the artefact never saw is not 0% —
   it is unmeasured, drawn in the neutral fill with a dashed rim and counted
   separately, because "nothing imported this" and "this ran and its lines
   did not" are different findings and one colour for both hides the first.
   ================================================================== */
var PACKING = window.OrchPacking || null;
var COV_CMAP = "plasma";        /* the Repo frame's Connections ramp */
var COV_MIN_K = 0.05, COV_MAX_K = 12;
var covState = { built: false, root: null, k: 1, tx: 0, ty: 0,
                 floor: COV_MIN_K, selected: null };
var covLeafEls = [];
var svgCov = byId("svgCov");
var viewportCov = byId("viewportCov");

function covEmptyMessage(html) {
  var box = byId("covEmpty");
  byId("covEmptyText").innerHTML = html;
  box.hidden = false;
}

function covFill(rec) {
  /* `percent` is null for a file the artefact never saw. CSS owns that
   * colour so it re-themes with the rest of the page; a measured file gets
   * an explicit fill because it is data, not styling. */
  if (!rec.measured || rec.percent === null) { return null; }
  return PACKING.cmapHex(COV_CMAP, PACKING.cmapNorm(rec.percent, 0, 100));
}

/* ONE place that decides what a leaf's class list is, because the builder
 * and the selection restyle both write it and a leaf that changed kind
 * between them would be lying about one of the two. `nofigure` exists so
 * that "measured, but the artefact carries no percentage" has a colour
 * without borrowing the dashed rim that means "never seen at all". */
function covLeafClass(rec, selected) {
  return "cleaf" +
    (rec.measured ? (covFill(rec) === null ? " nofigure" : "") : " unmeasured") +
    (selected ? " selected" : "");
}

function covBucket(fn) {
  if (fn.percent === null || fn.percent === undefined) { return "unknown"; }
  if (fn.percent >= 100) { return "covered"; }
  if (fn.percent <= 0) { return "none"; }
  return "partial";
}

/* --- the legend ---------------------------------------------------- */
var COV_LEGEND_STEPS = 28;
function renderCovLegend() {
  var box = byId("covLegend");
  if (!box) { return; }
  box.textContent = "";
  /* The strip is made of the very same cmapHex() calls that coloured the
   * circles, so the key cannot drift from the map. */
  var bar = el("div", "cmap-bar");
  for (var k = 0; k < COV_LEGEND_STEPS; k++) {
    var cell = document.createElement("span");
    cell.style.background =
      PACKING.cmapHex(COV_CMAP, k / (COV_LEGEND_STEPS - 1));
    bar.appendChild(cell);
  }
  box.appendChild(bar);
  var limits = el("div", "cmap-limits");
  limits.appendChild(el("span", null, "0%"));
  limits.appendChild(el("span", null, "100%"));
  box.appendChild(limits);
  box.appendChild(el("div", "hint legend-note",
    "lines covered · " + COV_CMAP));
  var row = el("div", "legend-row");
  var sw = el("span", "swatch unmeasured-swatch");
  row.appendChild(sw);
  row.appendChild(el("span", null, "never measured"));
  box.appendChild(row);
}

function covStatsLine(drawn, dirs) {
  var line = drawn + " files · " + dirs + " directories";
  if (EXEC.unmeasured) {
    line += " · " + EXEC.unmeasured + " never measured";
  }
  return line + " · " + executionProvenance();
}

/* --- the right-hand panel ------------------------------------------- */
var COV_GROUPS = [
  ["covered", "Covered", "every line ran"],
  ["partial", "Partially covered", "some lines ran, some did not"],
  ["none", "Not covered", "no line in the function ran"],
  ["unknown", "No figure", "the artefact carries no percentage"]
];

function covDetailPlaceholder() {
  byId("covDetailTitle").textContent = "Functions";
  var body = byId("covDetailBody");
  body.textContent = "";
  body.appendChild(el("p", "muted",
    "Select a file (click a circle) to see every function in it, grouped " +
    "by how much of it ran."));
}

function renderCovDetail(rec) {
  byId("covDetailTitle").textContent = rec.path;
  var body = byId("covDetailBody");
  body.textContent = "";

  var head = el("div", "cov-file-head");
  if (!rec.measured) {
    head.appendChild(el("span", "badge warn", "never measured"));
    body.appendChild(head);
    body.appendChild(el("p", "muted",
      "This file does not appear in " + (EXEC.artefact || "the artefact") +
      " at all. That is not 0% coverage: nothing the suite ran ever " +
      "imported it, which is a different finding and usually a louder one."));
    return;
  }
  head.appendChild(el("span", "n",
    (rec.percent === null ? "—" : rec.percent.toFixed(1) + "%")));
  head.appendChild(el("span", "k",
    rec.covered + " of " + rec.statements + " statements"));
  body.appendChild(head);

  var fns = rec.functions || [];
  if (!fns.length) {
    body.appendChild(el("p", "muted",
      "The artefact records no function in this file — module-level code " +
      "only, or nothing importable."));
    return;
  }
  /* EVERY function, in all four groups: the complete set is the point.
   * A panel that listed only the gaps would answer a different question. */
  var counted = 0;
  COV_GROUPS.forEach(function (group) {
    var mine = fns.filter(function (fn) {
      return covBucket(fn) === group[0];
    });
    if (!mine.length) { return; }
    counted += mine.length;
    var section = el("div", "cov-group " + group[0]);
    var title = el("div", "cov-group-head");
    title.appendChild(el("span", "name", group[1]));
    title.appendChild(el("span", "badge " + group[0], String(mine.length)));
    section.appendChild(title);
    section.appendChild(el("div", "sub", group[2]));
    mine.sort(function (a, b) { return a.line - b.line; });
    mine.forEach(function (fn) {
      var row = el("div", "row");
      var rh = el("div", "row-head");
      rh.appendChild(el("span", "name", fn.name));
      rh.appendChild(el("span", "where", "line " + fn.line));
      rh.appendChild(el("span", "badge " + group[0],
        fn.percent === null || fn.percent === undefined
          ? "—" : fn.percent.toFixed(0) + "%"));
      row.appendChild(rh);
      if (fn.missing) {
        row.appendChild(el("div", "sub",
          fn.missing + " line(s) never ran, of " + fn.statements));
      }
      section.appendChild(row);
    });
    body.appendChild(section);
  });
  body.appendChild(el("p", "hint", counted + " function(s) in this file."));
}

function covSelect(path) {
  covState.selected = path;
  for (var k = 0; k < covLeafEls.length; k++) {
    var entry = covLeafEls[k];
    var cls = covLeafClass(entry.rec, entry.rec.path === path);
    if (entry.el.getAttribute("class") !== cls) {
      entry.el.setAttribute("class", cls);
    }
  }
  if (path === null) {
    covDetailPlaceholder();
    renderCovPie(null);
    return;
  }
  for (var j = 0; j < covLeafEls.length; j++) {
    if (covLeafEls[j].rec.path === path) {
      renderCovDetail(covLeafEls[j].rec);
      renderCovPie(covLeafEls[j].rec);
      return;
    }
  }
}

/* --- the pie --------------------------------------------------------
 *
 * WHAT IT COUNTS, AND WHY THAT AND NOT LINES. Functions — the same records
 * the panel on the right groups, from the same `covBucket`. The pie and the
 * list therefore cannot disagree, which they could if one sliced statements
 * and the other counted definitions. At line level "partially covered" has
 * no meaning at all: a line either ran or it did not, so a line pie would
 * only ever have two slices and would say less than the circle's own colour
 * already says.
 *
 * WITH NOTHING SELECTED it is every function in every MEASURED file, one
 * function one vote, so selecting a file zooms the same measurement in
 * rather than switching to a different one.
 *
 * A NEVER-MEASURED FILE IS NEVER FOLDED INTO "not covered". It contributes
 * no function to the overall pie — the artefact records none for it — so it
 * is counted in words underneath instead, and selecting one draws a single
 * hatched slice that says what it is. Painting it grey would make "nothing
 * ever imported this file" look exactly like "the suite ran it and missed
 * it", which is the one conflation this whole frame exists to refuse.
 */
var PIE_C = 100, PIE_R = 78;
/* The order the slices are laid out in, best answer first, so the eye reads
 * the same direction on every file. Same keys as `COV_GROUPS`. */
var PIE_ORDER = ["covered", "partial", "none", "unknown"];
var PIE_LABEL = { covered: "Covered", partial: "Partially covered",
                  none: "Not covered", unknown: "No figure" };

function tally(functions) {
  var out = { covered: 0, partial: 0, none: 0, unknown: 0 };
  (functions || []).forEach(function (fn) { out[covBucket(fn)] += 1; });
  return out;
}

function tallyAll() {
  var out = { covered: 0, partial: 0, none: 0, unknown: 0 };
  EXECUTED.forEach(function (rec) {
    if (!rec.measured) { return; }
    var one = tally(rec.functions);
    PIE_ORDER.forEach(function (key) { out[key] += one[key]; });
  });
  return out;
}

function pieArc(a0, a1) {
  var x0 = PIE_C + PIE_R * Math.cos(a0), y0 = PIE_C + PIE_R * Math.sin(a0);
  var x1 = PIE_C + PIE_R * Math.cos(a1), y1 = PIE_C + PIE_R * Math.sin(a1);
  var large = (a1 - a0) > Math.PI ? 1 : 0;
  return "M" + PIE_C + "," + PIE_C + " L" + x0.toFixed(2) + "," +
    y0.toFixed(2) + " A" + PIE_R + "," + PIE_R + " 0 " + large + " 1 " +
    x1.toFixed(2) + "," + y1.toFixed(2) + " Z";
}

function drawPie(counts, total) {
  var NS = PACKING ? PACKING.NS : "http://www.w3.org/2000/svg";
  var g = byId("pieSlices");
  while (g.firstChild) { g.removeChild(g.firstChild); }
  if (!total) {
    var ring = document.createElementNS(NS, "circle");
    ring.setAttribute("class", "pie-empty");
    ring.setAttribute("cx", PIE_C);
    ring.setAttribute("cy", PIE_C);
    ring.setAttribute("r", PIE_R);
    g.appendChild(ring);
    return;
  }
  var live = PIE_ORDER.filter(function (key) { return counts[key] > 0; });
  /* A full circle cannot be drawn as an arc — start and end coincide and
   * the path collapses to nothing. One slice is a circle. */
  if (live.length === 1) {
    var solo = document.createElementNS(NS, "circle");
    solo.setAttribute("class", "pie-slice pie-" + live[0]);
    solo.setAttribute("cx", PIE_C);
    solo.setAttribute("cy", PIE_C);
    solo.setAttribute("r", PIE_R);
    solo.appendChild(pieTitle(NS, live[0], counts[live[0]], total));
    g.appendChild(solo);
    return;
  }
  var angle = -Math.PI / 2;               /* twelve o'clock, clockwise */
  live.forEach(function (key) {
    var span = 2 * Math.PI * (counts[key] / total);
    var path = document.createElementNS(NS, "path");
    path.setAttribute("class", "pie-slice pie-" + key);
    path.setAttribute("d", pieArc(angle, angle + span));
    path.appendChild(pieTitle(NS, key, counts[key], total));
    g.appendChild(path);
    angle += span;
  });
}

function pieTitle(NS, key, count, total) {
  var node = document.createElementNS(NS, "title");
  node.textContent = PIE_LABEL[key] + " · " + count + " of " + total +
    " function(s) · " + pct(count, total);
  return node;
}

function pct(count, total) {
  return total ? (100 * count / total).toFixed(1) + "%" : "—";
}

function renderPieLegend(counts, total) {
  var box = byId("covPieLegend");
  box.textContent = "";
  if (!total) { return; }
  PIE_ORDER.forEach(function (key) {
    if (!counts[key]) { return; }
    var row = el("div", "pie-row");
    row.appendChild(el("span", "swatch pie-sw-" + key));
    row.appendChild(el("span", "name", PIE_LABEL[key]));
    row.appendChild(el("span", "n",
      counts[key] + " · " + pct(counts[key], total)));
    box.appendChild(row);
  });
}

function renderCovPie(rec) {
  var counts, total, note;
  if (rec && !rec.measured) {
    /* One slice, and it is not grey. */
    byId("covPieTitle").textContent = rec.path;
    counts = { covered: 0, partial: 0, none: 0, unknown: 1 };
    drawPie(counts, 1);
    var box = byId("covPieLegend");
    box.textContent = "";
    var row = el("div", "pie-row");
    row.appendChild(el("span", "swatch pie-sw-unknown"));
    row.appendChild(el("span", "name", "Never measured"));
    row.appendChild(el("span", "n", "100.0%"));
    box.appendChild(row);
    byId("covPieNote").textContent =
      "The artefact does not mention this file at all, so there is no " +
      "function in it to count. That is not 0% coverage.";
    return;
  }
  if (rec) {
    byId("covPieTitle").textContent = rec.path;
    counts = tally(rec.functions);
    note = (rec.functions || []).length
      ? "" : "The artefact records no function in this file — module-level " +
             "code only, or nothing importable.";
  } else {
    byId("covPieTitle").textContent = "All measured code";
    counts = tallyAll();
    note = EXEC.unmeasured
      ? EXEC.unmeasured + " file(s) the artefact never saw are NOT in this " +
        "pie: it records no function for them, so there is nothing to " +
        "count. They are on the map, drawn apart with a dashed rim; select " +
        "one to see it said."
      : "";
  }
  total = PIE_ORDER.reduce(function (sum, key) {
    return sum + counts[key];
  }, 0);
  drawPie(counts, total);
  renderPieLegend(counts, total);
  byId("covPieNote").textContent = total
    ? total + " function(s)" + (note ? " · " + note : "")
    : (note || "No function to count.");
}

/* --- pan / zoom ------------------------------------------------------ */
function applyCovTransform() {
  viewportCov.setAttribute("transform",
    "translate(" + covState.tx.toFixed(2) + "," + covState.ty.toFixed(2) +
    ") scale(" + covState.k.toFixed(4) + ")");
}
/* A FIT THAT CAN ACTUALLY FIT: the floor comes from the CONTENT, never from
 * a constant. On a packing whose true fit falls below a fixed minimum the
 * clamp raises it, the frame opens far too close, and no amount of
 * scrolling out reaches the whole graph — every step is clamped by the same
 * constant. The Repo frame learned this the hard way at 7779 files. */
function covFloor(fitK) { return Math.min(COV_MIN_K, fitK * 0.5); }
function clampCovK(k) {
  return Math.max(covState.floor, Math.min(COV_MAX_K, k));
}
function fitCov() {
  var root = covState.root;
  if (!root) { return; }
  var bw = svgCov.clientWidth || 800, bh = svgCov.clientHeight || 600;
  var R = root.r + 20;
  var fit = Math.min(bw, bh) / (2 * R);
  covState.floor = covFloor(fit);
  covState.k = clampCovK(fit);
  covState.tx = bw / 2 - root.cx * covState.k;
  covState.ty = bh / 2 - root.cy * covState.k;
  applyCovTransform();
}

var covPanning = null, covSuppress = false, covPressed = null;
function startCovPan(ev) {
  covPanning = { x: ev.clientX, y: ev.clientY, tx: covState.tx,
                 ty: covState.ty, moved: false };
  svgCov.classList.add("panning");
  try { svgCov.setPointerCapture(ev.pointerId); } catch (err) { /* ok */ }
}
svgCov.addEventListener("pointerdown", function (ev) {
  covSuppress = false;
  covPressed = null;           /* a press on the background selects nothing */
  startCovPan(ev);
});
svgCov.addEventListener("pointermove", function (ev) {
  if (!covPanning) { return; }
  var dx = ev.clientX - covPanning.x, dy = ev.clientY - covPanning.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) { covPanning.moved = true; }
  covState.tx = covPanning.tx + dx;
  covState.ty = covPanning.ty + dy;
  applyCovTransform();
});
function endCovPointer(ev) {
  if (!covPanning) { return; }
  if (covPanning.moved) { covSuppress = true; }
  else if (covPressed !== null) {
    /* The click that follows a captured pointer is delivered to this <svg>,
     * not to the circle, so a leaf that only listened for `click` would
     * never be selected at all. */
    covSelect(covPressed);
    covSuppress = true;
  }
  try { svgCov.releasePointerCapture(ev.pointerId); } catch (err) { /* */ }
  covPanning = null;
  svgCov.classList.remove("panning");
}
svgCov.addEventListener("pointerup", endCovPointer);
svgCov.addEventListener("pointercancel", endCovPointer);
svgCov.addEventListener("click", function () {
  if (covSuppress) { covSuppress = false; return; }
  covSelect(null);
});
svgCov.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
  var nk = clampCovK(covState.k * factor);
  factor = nk / covState.k;
  var rect = svgCov.getBoundingClientRect();
  var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  covState.tx = mx - (mx - covState.tx) * factor;
  covState.ty = my - (my - covState.ty) * factor;
  covState.k = nk;
  applyCovTransform();
}, { passive: false });
byId("btnCovFit").addEventListener("click", fitCov);

/* --- the build -------------------------------------------------------- */
function buildCoverage() {
  covState.built = true;
  while (viewportCov.firstChild) {
    viewportCov.removeChild(viewportCov.firstChild);
  }
  covLeafEls = [];
  covDetailPlaceholder();
  renderCovPie(null);
  byId("covEmpty").hidden = true;

  if (!PACKING) {
    /* The shared floor did not load. Say so rather than drawing nothing:
     * an empty frame reads as "no coverage", which is a different and much
     * more alarming claim than "this page is missing an asset". */
    covEmptyMessage("<b>The shared packing asset did not load.</b><br>" +
      "This frame is drawn by <code>viewer-shared/packing.js</code>, " +
      "which must be served beside the page. Nothing here is a statement " +
      "about coverage.");
    byId("covStats").textContent = "";
    return;
  }
  renderCovLegend();
  if (!EXECUTED.length) {
    covEmptyMessage("<b>No source files to draw.</b><br>" +
      "The declared source roots hold no Python file outside " +
      "<code>testing/</code>.");
    byId("covStats").textContent = executionProvenance();
    covState.root = null;
    return;
  }

  var leaves = EXECUTED.map(function (rec) {
    return { path: rec.path, size: rec.bytes, rec: rec };
  });
  var root = PACKING.buildTree(leaves);
  PACKING.packDir(root, PACKING.leafRadiusScale(leaves));
  PACKING.placeDir(root, 0, 0, 0);
  covState.root = root;
  var maxR = PACKING.maxRadii(root);
  var NS = PACKING.NS;

  (function renderDir(dir) {
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "cdir");
    c.setAttribute("cx", dir.cx.toFixed(1));
    c.setAttribute("cy", dir.cy.toFixed(1));
    c.setAttribute("r", dir.r.toFixed(1));
    var title = document.createElementNS(NS, "title");
    title.textContent = (dir.path || "(root)") + " · " + dir.nLeaves +
      " file(s)";
    c.appendChild(title);
    viewportCov.appendChild(c);
    if (dir.name) {
      var lbl = PACKING.makeLabel(dir, "dir", maxR.dir, "c");
      if (lbl) { viewportCov.appendChild(lbl); }
    }
    dir.items.forEach(function (it) {
      if (it.dir) { renderDir(it.dir); }
      else { renderLeaf(it.leaf); }
    });
  }(root));

  function renderLeaf(leaf) {
    var rec = leaf.rec;
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("class", covLeafClass(rec, false));
    c.setAttribute("cx", leaf.cx.toFixed(1));
    c.setAttribute("cy", leaf.cy.toFixed(1));
    c.setAttribute("r", leaf.r.toFixed(1));
    var fill = covFill(rec);
    if (fill) { c.setAttribute("fill", fill); }
    var title = document.createElementNS(NS, "title");
    title.textContent = rec.path + " · " + rec.bytes + " bytes · " +
      (rec.measured
        ? (rec.percent === null ? "no figure"
            : rec.percent.toFixed(1) + "% of lines") + " · " +
          rec.covered + "/" + rec.statements + " statements · " +
          (rec.functions || []).length + " function(s)"
        : "never measured — the artefact does not mention this file");
    c.appendChild(title);
    c.addEventListener("pointerdown", function (ev) {
      ev.stopPropagation();
      covSuppress = false;
      covPressed = rec.path;
      startCovPan(ev);
    });
    c.addEventListener("click", function (ev) {
      ev.stopPropagation();
      covSelect(rec.path);
    });
    viewportCov.appendChild(c);
    covLeafEls.push({ el: c, rec: rec });
    var lbl = PACKING.makeLabel(leaf, "leaf", maxR.file, "c");
    if (lbl) { viewportCov.appendChild(lbl); }
  }

  byId("covStats").textContent = covStatsLine(leaves.length, root.nDirs);
  fitCov();
}

/* --- the frames ------------------------------------------------------- */
var FRAMES = [
  ["frameMetrics", "stageMetrics", "metrics"],
  ["frameCoverage", "stageCoverage", "coverage"]
];
var frame = "metrics";

function setFrame(name) {
  frame = name;
  FRAMES.forEach(function (entry) {
    byId(entry[1]).hidden = entry[2] !== name;
    byId(entry[0]).className = entry[2] === name ? "active" : "";
  });
  renderLimits(name);
  if (name === "coverage") {
    /* Built once; re-fitted on EVERY entry. An SVG inside a hidden div has
     * no measured size, so a fit computed while the frame was hidden would
     * be computed against 0 x 0 and open at the wrong scale. */
    if (!covState.built) { buildCoverage(); }
    fitCov();
  }
}

FRAMES.forEach(function (entry) {
  byId(entry[0]).addEventListener("click", function () { setFrame(entry[2]); });
});

/* ---------- the theme control --------------------------------------- */
var THEME_UI = {
  system: { next: "light", icon: "◐", name: "System" },
  light: { next: "dark", icon: "☀", name: "Light" },
  dark: { next: "system", icon: "☾", name: "Dark" }
};

(function wireTheme() {
  var theme = window.coverageTheme;
  if (!theme) { return; }   /* the head block did not run: leave CSS alone */
  var button = byId("themeToggle");
  function paint(announce) {
    var ui = THEME_UI[theme.mode] || THEME_UI.system;
    byId("themeIcon").textContent = ui.icon;
    byId("themeName").textContent = ui.name;
    button.hidden = false;
    button.title = "Colour theme: " + ui.name + ". Click for " +
      THEME_UI[ui.next].name + ".";
    if (announce) {
      byId("themeStatus").textContent = "Colour theme: " + ui.name + ".";
    }
  }
  button.addEventListener("click", function () {
    theme.mode = (THEME_UI[theme.mode] || THEME_UI.system).next;
    theme.apply(theme.mode);
    theme.remember(theme.mode);
    paint(true);
  });
  var media = theme.query();
  if (media) {
    var onChange = function () {
      /* An explicit choice is never undone by the operating system. */
      if (theme.mode !== "system") { return; }
      theme.apply("system");
      paint(false);
    };
    if (media.addEventListener) { media.addEventListener("change", onChange); }
    else if (media.addListener) { media.addListener(onChange); }
  }
  paint(false);
}());

/* ---------- footer, and boot ---------------------------------------- */
byId("foot").textContent =
  "Read from " + (DATA.declared_in || "no declaration") +
  " · source roots: " + ((DATA.source_roots || []).join(", ") || "none") +
  " · " + (DATA.unclassified || []).length + " unclassified suite(s)" +
  " · Metrics reports mentions, never executions; Coverage reports lines " +
  "that ran, never correctness.";

setFrame("metrics");
draw();
}());
