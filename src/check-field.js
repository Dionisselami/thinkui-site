/* Run the real assets/js/field.js under a stubbed DOM and check what it seeds.
 *
 * The browser harness wedged, and the phone path is the one case the desktop pixels cannot
 * prove: markEnabled is false there, so the dust layer carries the hero alone. This loads
 * the shipped file itself - not a reimplementation - so a drift between the check and the
 * code is impossible.
 *
 *   node check-field.js
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "assets", "js", "field.js");

function run(width, height, copyBlocks) {
  const ctx = {
    setTransform() {}, clearRect() {}, fillRect() {}, getImageData: (x, y, w, h) => ({ data: new Uint8ClampedArray(4) }),
    globalAlpha: 1, globalCompositeOperation: "source-over", fillStyle: "#000"
  };
  const canvas = {
    width: 0, height: 0, style: {},
    getContext: () => ctx,
    getBoundingClientRect: () => ({ width, height, left: 0, top: 0, right: width, bottom: height })
  };
  // the copy: the union of these rects is what the exclusion is built from
  const blocks = copyBlocks.map(([x, y, w, h]) => ({
    getBoundingClientRect: () => ({ width: w, height: h, left: x, top: y, right: x + w, bottom: y + h })
  }));
  canvas.parentElement = { querySelectorAll: (sel) => (sel.indexOf("hero__inner") >= 0 ? blocks : []) };

  const win = {
    innerWidth: width, devicePixelRatio: 2,
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
    addEventListener() {},
    IntersectionObserver: undefined
  };
  const doc = { querySelectorAll: (s) => (s === "canvas.field" ? [canvas] : []), addEventListener() {}, hidden: false };

  const src = fs.readFileSync(SRC, "utf8");
  const fn = new Function("window", "document", "performance", src + "\nreturn window.__thinkuiField;");
  const fields = fn(win, doc, { now: () => 1000 });
  return { field: fields && fields[0], canvas };
}

function report(label, width, height, blocks) {
  const { field, canvas } = run(width, height, blocks);
  if (!field) { console.log("%s: the script built no field", label); return; }
  const f = field;
  console.log("\n%s  (%dx%d css)", label, width, height);
  console.log("  markEnabled: %s   band: %s", f.markEnabled, f.markBand);
  console.log("  dust points: %d   dense points: %d", f.ambient.length, f.particles.length);
  const sizes = f.ambient.map(p => p.size).sort((a, b) => a - b);
  const alphas = f.ambient.map(p => p.alpha).sort((a, b) => a - b);
  const q = (a, x) => a[Math.floor(a.length * x)].toFixed(2);
  console.log("  size  p10 %s  median %s  p90 %s", q(sizes, .1), q(sizes, .5), q(sizes, .9));
  console.log("  alpha p10 %s  median %s  p90 %s", q(alphas, .1), q(alphas, .5), q(alphas, .9));

  // coverage: how many measurement cells hold at least one grain, and by how much
  const GX = 8, GY = 10, cw = width / GX, ch = height / GY;
  const cells = new Array(GX * GY).fill(0);
  for (const p of f.ambient) {
    const gx = Math.min(GX - 1, Math.max(0, Math.floor(p.x / cw)));
    const gy = Math.min(GY - 1, Math.max(0, Math.floor(p.y / ch)));
    cells[gy * GX + gx]++;
  }
  const empty = cells.filter(c => c === 0).length;
  console.log("  coverage: %d of %d cells empty, min %d, mean %s",
              empty, cells.length, Math.min(...cells), (cells.reduce((a, b) => a + b, 0) / cells.length).toFixed(1));
  return { empty, count: f.ambient.length, markEnabled: f.markEnabled };
}

// desktop, as measured in the browser: the copy sits in a centred column
const desktop = report("desktop", 1535, 599, [[230, 96, 900, 22], [230, 138, 900, 73], [230, 234, 743, 133], [230, 399, 900, 58], [230, 481, 900, 22]]);
// phone: the copy is nearly the whole width and tall, so no band clears the threshold
const phone = report("phone", 390, 664, [[24, 76, 342, 44], [24, 126, 342, 180], [24, 322, 342, 150], [24, 488, 342, 50], [24, 552, 342, 44]]);
// a wide monitor
const wide = report("wide", 2560, 900, [[480, 120, 1100, 22], [480, 162, 1100, 73], [480, 258, 900, 133], [480, 423, 1100, 58], [480, 505, 1100, 22]]);

console.log("\n%s", phone.markEnabled ? "PHONE STILL BUILDS A MARK - unexpected" : "phone correctly has no dense layer; dust carries it");
console.log("empty cells across all three: %d", desktop.empty + phone.empty + wide.empty);
