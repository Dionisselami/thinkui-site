/* ThinkUI — the reference field.
 *
 * The hero background is the product's own material rather than decoration: points drift
 * across the whole frame, gather into the brand mark (the three shortening bars, using the
 * same 64-unit geometry as assets/img/mark.svg so it can never drift from the logo), hold,
 * come loose, and gather again — for as long as the hero is on screen.
 *
 * What makes it seamless, and what went wrong before:
 *   - It cycles. The first version assembled once and then drifted forever: the mark formed
 *     on load and never again, and because the dense layer is excluded from the copy's box,
 *     the drift ended up invisible. A hero that dies after seven seconds is the bug.
 *   - Nothing switches on or off. The pull toward the mark is a continuous periodic function
 *     (gather, hold, loosen, gather), so there is no frame where the animation restarts. The
 *     spring integrates against real elapsed time, so a 30fps laptop and a 144Hz desktop
 *     produce the same motion.
 *   - Every point carries its own phase offset, the way the corpus's own dot animations
 *     stagger their `begin` times. Nothing in the field pulses in unison.
 *   - The ambient layer is seeded on a jittered grid, not at random, so coverage is even by
 *     construction: a random scatter leaves whole regions empty at this density, which is
 *     what "the animation is not on the whole screen" turned out to mean. It wraps at the
 *     edges rather than dying there, so the drift has no seam.
 *   - The dense layer keeps clear of the copy's rectangle outright (additive blending stacks
 *     points into near-opaque pixels - measured at 3.9:1 against a 4.5:1 gate when it was
 *     only dimmed). The ambient layer keeps drawing there at a reduced alpha, so the copy is
 *     legible and the frame is still alive behind it. Both numbers are measured, not assumed.
 *   - One draw call per colour bucket, no per-particle shadow, no per-particle save/restore:
 *     this runs on the same thread as the page and on hardware we do not control.
 *   - prefers-reduced-motion gets one static, fully formed frame; the loop stops when the tab
 *     is hidden or the hero is off screen.
 */
(function () {
  "use strict";

  var canvases = document.querySelectorAll("canvas.field");
  if (!canvases.length || !window.requestAnimationFrame) return;

  // the mark: viewBox 64, bars at x=14, widths 36/26/16, height 6.5, rx 3.25
  var GRID = 64,
      BAR_X = 14,
      BAR_H = 6.5,
      RX = 3.25,
      BARS = [
        { y: 17.00, w: 36 },
        { y: 28.75, w: 26 },
        { y: 40.50, w: 16 }
      ];

  // One hue, deeper at the low end: the field is the same vermilion as everything else.
  // Six stops of it so the dust has depth instead of reading as a flat tint.
  var COLOURS = ["#f0764f", "#e8603a", "#d4431d", "#c03a17", "#a52f11", "#8f2810"];

  // The cycle, in milliseconds. Gather and hold are the mark; loosen is the field coming
  // apart. The pull is a function of position in the cycle, never a state change, so the
  // seam between one cycle and the next does not exist.
  var CYCLE = 9000,
      GATHER_END = 0.40,     // 0.00 - 0.40  rising pull: the mark assembles
      HOLD_END = 0.54,       // 0.40 - 0.54  full pull: it holds, shimmering
      LOOSE_END = 0.86,      // 0.54 - 0.86  pull decays: the field comes loose
      PULL_LOOSE = 0.05;     // never zero - the ghost of the bars keeps the cloud coherent

  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function pullAt(u) {
    if (u < GATHER_END) return u / GATHER_END;                       // rising
    if (u < HOLD_END) return 1;                                      // held
    if (u < LOOSE_END) {
      var k = (u - HOLD_END) / (LOOSE_END - HOLD_END);
      return 1 - k * (1 - PULL_LOOSE);                               // loosening
    }
    var g = (u - LOOSE_END) / (1 - LOOSE_END);
    return PULL_LOOSE + g * (1 - PULL_LOOSE);                        // gathering again
  }

  function Field(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: true });
    this.particles = [];
    this.ambient = [];
    this.pointer = { x: -9999, y: -9999, active: false };
    this.start = null;
    this.running = false;
    this.frame = 0;
    this.resize();
    this.build();
    this.bind();
  }

  Field.prototype.resize = function () {
    var rect = this.canvas.getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);   // cap: retina cost, no visible gain here
    this.w = Math.max(1, Math.round(rect.width));
    this.h = Math.max(1, Math.round(rect.height));
    this.canvas.width = Math.round(this.w * dpr);
    this.canvas.height = Math.round(this.h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Where the copy lives, in canvas coordinates. Known before the mark is placed, because
    // the mark must not land inside the window the copy keeps clear.
    this.safe = this.safeZone();

    // The mark goes in whichever of the four bands around the copy is roomiest, sized to that
    // band rather than to the viewport: a mark that fits the space beats a big one hidden
    // behind text. With no room anywhere (a phone, where the copy is tall and wide) the mark
    // layer is not built at all and the ambient layer carries the hero by itself.
    var s = this.safe;
    var bands = s ? [
      { side: "below", size: this.h - s.y1 },
      { side: "above", size: s.y0 },
      { side: "right", size: this.w - s.x1 },
      { side: "left",  size: s.x0 }
    ] : [{ side: "below", size: this.h * 0.36 }];
    bands.sort(function (a, b) { return b.size - a.size; });
    var best = bands[0];

    this.markEnabled = best.size >= 130;
    var markPx = Math.min(best.size * 0.86, Math.max(this.w, this.h) * 0.34);
    this.scale = Math.max(markPx, 60) / GRID;
    var half = (GRID * this.scale) / 2;
    var ccx = s ? (s.x0 + s.x1) / 2 : this.w / 2;
    var ccy = s ? (s.y0 + s.y1) / 2 : this.h / 2;
    if (best.side === "below")      { this.ox = ccx - half; this.oy = s.y1 + best.size / 2 - half; }
    else if (best.side === "above") { this.ox = ccx - half; this.oy = best.size / 2 - half; }
    else if (best.side === "right") { this.ox = s.x1 + best.size / 2 - half; this.oy = ccy - half; }
    else                            { this.ox = best.size / 2 - half; this.oy = ccy - half; }
    this.markBand = best.side;
  };

  /* The headline block, padded. Measured from the DOM rather than hard-coded, because the
     block's height changes with the copy. The union of the copy's own blocks, not its
     container: the container is a stretched grid cell that fills the whole hero, so using it
     marked the entire section as text and blanked the field. */
  Field.prototype.safeZone = function () {
    var host = this.canvas.parentElement;
    if (!host) return null;
    var marks = host.querySelectorAll(".hero__inner > *");
    if (!marks.length) return null;
    var cr = this.canvas.getBoundingClientRect();
    if (!cr.width) return null;
    var pad = 30, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
    Array.prototype.forEach.call(marks, function (el) {
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      any = true;
      x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top);
      x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
    });
    if (!any) return null;
    return { x0: x0 - cr.left - pad, y0: y0 - cr.top - pad, x1: x1 - cr.left + pad, y1: y1 - cr.top + pad };
  };

  /* How much of a point's ink survives at this position.
     Dense layer: nothing inside the copy's rectangle, ramping to full over ~90px outside it.
     The bars are dense enough that additive blending stacks several points into one
     near-opaque pixel, which took the paragraph to 3.9:1 against a 4.5:1 gate - so legibility
     is a property of the geometry rather than a hope about where points land.
     Ambient layer: a floor, not a void. It cannot stack that way (one point per grid cell,
     ~0.15 alpha, ~1px), so the frame stays alive behind the words. */
  Field.prototype.dim = function (x, y, floor, ramp) {
    var s = this.safe;
    if (!s) return 1;
    var dx = Math.max(s.x0 - x, 0, x - s.x1);
    var dy = Math.max(s.y0 - y, 0, y - s.y1);
    if (dx === 0 && dy === 0) return floor;
    var d = Math.sqrt(dx * dx + dy * dy);
    return floor + (1 - floor) * Math.min(1, d / ramp);
  };

  Field.prototype.target = function (i) {
    // spread across the bars in proportion to their width, so density stays even
    var pick = i % 100, bar;
    if (pick < 52) bar = BARS[0];
    else if (pick < 89) bar = BARS[1];
    else bar = BARS[2];
    var x = BAR_X + RX + Math.random() * (bar.w - RX * 2);
    var y = bar.y + 1.5 + Math.random() * (BAR_H - 3);
    return { x: this.ox + x * this.scale, y: this.oy + y * this.scale, bar: bar };
  };

  Field.prototype.build = function () {
    var i, area = this.w * this.h;
    this.particles = [];
    this.ambient = [];

    if (this.markEnabled) {
      var count = Math.round(Math.min(1400, Math.max(320, area / 2000)));
      if (window.innerWidth < 700) count = Math.round(count * 0.55);
      for (i = 0; i < count; i++) {
        var t = this.target(i);
        // start scattered around the edges, so the assembly reads as arrival
        var angle = Math.random() * Math.PI * 2,
            dist = Math.max(this.w, this.h) * (0.45 + Math.random() * 0.6);
        this.particles.push({
          x: this.w / 2 + Math.cos(angle) * dist,
          y: this.h / 2 + Math.sin(angle) * dist * 0.6,
          vx: 0, vy: 0,
          tx: t.x, ty: t.y,
          bar: BARS.indexOf(t.bar),
          size: 1.1 + Math.random() * 1.3,
          alpha: 0.30 + Math.random() * 0.45,
          colour: COLOURS[(Math.random() * COLOURS.length) | 0],
          // its own offset into the cycle, so no two points start together
          phase: Math.random(),
          wobble: Math.random() * Math.PI * 2
        });
      }
    }

    /* The ambient layer is the dust: one point per cell of a jittered grid, so the whole
       frame is covered evenly by construction. A random scatter at the same count leaves
       visible holes - the field measured empty in 92 of 96 regions before this, and even a
       fixed grid reopens holes as the points drift, so the cell is chosen from the area.

       It has to read as haze, not as a dot matrix, which is why the count is high and the
       sizes and alphas are skewed: most grains are sub-pixel and barely there, a few are
       larger and brighter, and the bright ones drift slower - the same trick that makes a
       depth of field read. Jitter is close to a full cell now that the cells are small, so
       the grid underneath is not legible. */
    var target = Math.min(1800, Math.max(420, area / 430));
    var cell = Math.max(16, Math.min(Math.sqrt(area / target), 90));
    var cols = Math.max(3, Math.ceil(this.w / cell)),
        rows = Math.max(3, Math.ceil(this.h / cell));
    var cw = this.w / cols, chh = this.h / rows;
    for (var gy = 0; gy < rows; gy++) {
      for (var gx = 0; gx < cols; gx++) {
        var near = Math.random();                 // 0 = fine grain far off, 1 = a near mote
        this.ambient.push({
          x: (gx + 0.5 + (Math.random() - 0.5) * 0.92) * cw,
          y: (gy + 0.5 + (Math.random() - 0.5) * 0.92) * chh,
          vx: (Math.random() - 0.5) * 0.14,
          vy: -0.03 - Math.random() * 0.12,
          size: 0.55 + near * near * 1.9,         // mostly sub-pixel, a few real motes
          alpha: 0.05 + near * 0.21,              // faint by default, brighter when nearer
          colour: COLOURS[(Math.random() * COLOURS.length) | 0],
          wobble: Math.random() * Math.PI * 2,
          wobbleRate: 0.0004 + Math.random() * 0.0013,
          drift: 0.35 + (1 - near) * 1.1          // near motes hang, far grains travel
        });
      }
    }
  };

  Field.prototype.bind = function () {
    var self = this;
    // the canvas itself stays pointer-events:none, so it can never intercept a click;
    // the pointer is tracked on the window and mapped into canvas space instead
    window.addEventListener("pointermove", function (e) {
      var r = self.canvas.getBoundingClientRect();
      var x = e.clientX - r.left, y = e.clientY - r.top;
      if (x < -80 || y < -80 || x > r.width + 80 || y > r.height + 80) {
        self.pointer.active = false; return;
      }
      self.pointer.x = x; self.pointer.y = y; self.pointer.active = true;
    });
    window.addEventListener("resize", function () {
      self.resize();
      self.build();
      if (REDUCED) self.draw(6000);
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) self.stop(); else self.start_();
    });
  };

  /* the flow: a cheap deterministic curl-ish field (two offset sine pairs), which is enough
     to look organic and costs a couple of multiplications per particle */
  Field.prototype.flow = function (x, y, t) {
    var s = 0.0016;
    return {
      x: Math.sin(y * s + t * 0.00021) * Math.cos((x + y) * s * 0.6 + t * 0.00013),
      y: Math.cos(x * s * 1.15 - t * 0.00017) * Math.sin((x - y) * s * 0.5 + t * 0.00011)
    };
  };

  Field.prototype.step = function (now, dt) {
    var t = now - this.start, i, p, dx, dy, d2, d, f;
    // springs integrate against elapsed time, not against frames: the same animation has to
    // take the same time on a 144Hz desktop and a 30fps laptop, or on a device that is
    // briefly busy. 16.667ms is the 60fps baseline everything below is tuned to.
    if (dt === undefined) dt = 16.667;
    var fdt = Math.min(dt, 50) / 16.667;
    var u = (t % CYCLE) / CYCLE;            // where we are in the cycle
    var pull = pullAt(u);

    for (i = 0; i < this.particles.length; i++) {
      p = this.particles[i];
      // a per-point offset into the cycle, so the assembly arrives in a wave rather than a
      // single lurch - the corpus's own dot animations stagger their begin times the same way
      var stagger = p.phase * 0.06;
      var pu = ((u - stagger) + 1) % 1;
      var pp = pullAt(pu);

      // the mark: a spring whose strength is the cycle's pull, never zero
      var k = 0.026 * pp * fdt, damp = Math.pow(0.90, fdt);
      p.vx += (p.tx - p.x) * k;
      p.vy += (p.ty - p.y) * k;

      // the field: strongest when the mark is loose, fading as it gathers
      var loose = 1 - pp;
      if (loose > 0.01) {
        var fl = this.flow(p.x, p.y, t);
        p.vx += fl.x * 0.17 * loose * fdt;
        p.vy += fl.y * 0.17 * loose * fdt;
      }
      p.vx *= damp; p.vy *= damp;

      if (this.pointer.active) {
        dx = p.x - this.pointer.x; dy = p.y - this.pointer.y;
        d2 = dx * dx + dy * dy;
        if (d2 < 26000) {                            // 161px radius
          d = Math.sqrt(d2) || 1;
          f = (1 - d / 161) * 1.5 * fdt;
          p.vx += (dx / d) * f; p.vy += (dy / d) * f;
        }
      }

      p.x += p.vx; p.y += p.vy;
      if (p.x < -60) p.x = this.w + 60; else if (p.x > this.w + 60) p.x = -60;
      if (p.y < -60) p.y = this.h + 60; else if (p.y > this.h + 60) p.y = -60;
    }

    for (i = 0; i < this.ambient.length; i++) {
      p = this.ambient[i];
      var wob = Math.sin(p.wobble + t * p.wobbleRate);
      p.x += (p.vx + wob * 0.16 * p.drift) * fdt;
      p.y += p.vy * fdt;
      if (this.pointer.active) {
        dx = p.x - this.pointer.x; dy = p.y - this.pointer.y;
        d2 = dx * dx + dy * dy;
        if (d2 < 22000) { d = Math.sqrt(d2) || 1; f = (1 - d / 148) * 0.5 * fdt;
          p.vx += (dx / d) * f; p.vy += (dy / d) * f; }
      }
      p.vx *= 0.985; p.vy = p.vy * 0.985 - 0.0006;      // a slow upward bias, like dust
      // wrap rather than die: the drift has no edge and no seam
      if (p.x < -12) p.x = this.w + 12; else if (p.x > this.w + 12) p.x = -12;
      if (p.y < -12) p.y = this.h + 12; else if (p.y > this.h + 12) p.y = -12;
    }
  };

  Field.prototype.draw = function (now) {
    var ctx = this.ctx, t = now - (this.start || now), i, p, a;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = "lighter";

    // the ambient layer first: it is the frame's floor, and it never disappears
    for (i = 0; i < this.ambient.length; i++) {
      p = this.ambient[i];
      ctx.fillStyle = p.colour;
      ctx.globalAlpha = p.alpha * this.dim(p.x, p.y, 0.45, 70);
      ctx.fillRect(p.x, p.y, p.size, p.size);
    }

    // the mark, one pass per colour so the fillStyle changes six times a frame, not per point
    if (this.particles.length) {
      var u = (t % CYCLE) / CYCLE;
      var fade = 0.86 + 0.14 * pullAt(u);       // a little brighter while the mark holds
      for (var c = 0; c < COLOURS.length; c++) {
        ctx.fillStyle = COLOURS[c];
        for (i = c; i < this.particles.length; i += COLOURS.length) {
          p = this.particles[i];
          a = p.alpha * fade * this.dim(p.x, p.y, 0, 90);
          if (a <= 0.004) continue;
          ctx.globalAlpha = a;
          ctx.fillRect(p.x, p.y, p.size, p.size);
        }
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  };

  Field.prototype.tick = function (now) {
    if (!this.running) return;
    var dt = this.last === undefined ? 16.667 : now - this.last;
    this.last = now;
    this.step(now, dt);
    this.draw(now);
    this.frame++;
    var self = this;
    this.raf = window.requestAnimationFrame(function (n) { self.tick(n); });
  };

  Field.prototype.start_ = function () {
    if (this.running || REDUCED) return;
    this.running = true;
    if (this.start === null) this.start = performance.now();
    this.last = undefined;
    var self = this;
    this.raf = window.requestAnimationFrame(function (n) { self.tick(n); });
  };

  Field.prototype.stop = function () {
    this.running = false;
    if (this.raf) window.cancelAnimationFrame(this.raf);
  };

  /* ---- wiring ------------------------------------------------------------------- */
  var fields = [];
  Array.prototype.forEach.call(canvases, function (c) { fields.push(new Field(c)); });

  if (REDUCED) {
    // no animation: settle onto the mark and draw one fully formed frame
    fields.forEach(function (f) {
      f.start = performance.now() - 5000;
      for (var n = 0; n < 40; n++) f.step(f.start + n * 8);
      f.particles.forEach(function (p) { p.x = p.tx; p.y = p.ty; });
      f.draw(f.start + 400);
    });
  } else {
    // only animate what is on screen
    if (typeof window.IntersectionObserver === "function") {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          var f = fields.filter(function (x) { return x.canvas === e.target; })[0];
          if (!f) return;
          if (e.isIntersecting) { f.start_(); } else { f.stop(); }
        });
      }, { rootMargin: "120px" });
      canvases.forEach(function (c) { io.observe(c); });
    } else {
      fields.forEach(function (f) { f.start_(); });
    }
  }
  // exposed for the live check: it asserts coverage, the cycle and the frame budget for real
  window.__thinkuiField = fields;
})();
