/* ThinkUI — the reference field.
 *
 * The hero background is the product's own material rather than decoration: a few hundred
 * points fly in, assemble into the brand mark (the three shortening bars, using the same
 * 64-unit geometry as assets/img/mark.svg so it can never drift from the logo), hold, and
 * then come loose as a slow flow field that the pointer pushes around.
 *
 * Decisions worth keeping:
 *   - the targets are the shipped mark's rectangles, not eyeballed positions;
 *   - motion uses spring momentum (velocity + damping) rather than fixed durations, so
 *     pointer input blends into whatever is already happening instead of restarting it;
 *   - one draw call per colour bucket and no per-particle shadow, because this runs on the
 *     same thread as the page and on hardware we do not control;
 *   - the loop stops when the tab is hidden or the canvas is off screen, and
 *     prefers-reduced-motion gets one static, fully formed frame instead of an animation.
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
      ],
      INK = { x0: BAR_X, x1: BAR_X + 36, y0: 17, y1: 47 };

  // One hue, deeper at the low end: the field is the same vermilion as everything else.
  // Six stops of it so the dust has depth instead of reading as a flat tint.
  var COLOURS = ["#f0764f", "#e8603a", "#d4431d", "#c03a17", "#a52f11", "#8f2810"];
  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function Field(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: true });
    this.particles = [];
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

    // Where the copy lives, in canvas coordinates. This has to be known before the mark is
    // placed, because the mark must not land inside the window the copy keeps clear.
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

  /* The headline block, padded. Particles keep drawing in here, at a fifth of their alpha,
     so the words never depend on luck about where a point happens to land. Measured from the
     DOM rather than hard-coded, because the block's height changes with the copy. */
  Field.prototype.safeZone = function () {
    var host = this.canvas.parentElement;
    if (!host) return null;
    // the union of the copy's own blocks, not its container: the container is a stretched
    // grid cell that fills the whole hero, so using it marked the entire section as text.
    var marks = host.querySelectorAll(".hero__inner [data-rise]");
    if (!marks.length) marks = host.querySelectorAll(".hero__inner > *");
    if (!marks.length) return null;
    var cr = this.canvas.getBoundingClientRect();
    if (!cr.width) return null;
    var pad = 34, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
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

  /* The copy gets a clean window: no ink at all inside its rectangle, ramping up to full
     density over the next ~110px. Dimming was not enough - the bars are dense enough that
     additive blending stacks several points into one near-opaque pixel, which took the
     paragraph to 3.9:1 against the 4.5:1 gate. Excluding the rectangle outright makes
     legibility a property of the geometry rather than a hope about where points land. */
  Field.prototype.dim = function (x, y) {
    var s = this.safe;
    if (!s) return 1;
    var dx = Math.max(s.x0 - x, 0, x - s.x1);
    var dy = Math.max(s.y0 - y, 0, y - s.y1);
    var inside = (dx === 0 && dy === 0);
    // The dense layer is excluded outright: stacked points add up to a near-opaque pixel, which
    // took the paragraph to 3.9:1 against a 4.5:1 gate. The sparse ambient layer is only dimmed
    // - it cannot stack that way, and it is what keeps the hero alive on a phone, where the copy
    // is wide enough that a hard cut would blank the whole canvas.
    var floor = this.markEnabled ? 0 : 0.32;
    if (inside) return floor;
    var d = Math.sqrt(dx * dx + dy * dy);
    return floor + (1 - floor) * Math.min(1, d / 110);
  };

  Field.prototype.target = function (i) {
    // spread across the bars in proportion to their width, so density stays even
    var pick = i % 100, bar;
    if (pick < 52) bar = BARS[0];
    else if (pick < 89) bar = BARS[1];
    else bar = BARS[2];
    var jitterX = Math.random(), jitterY = Math.random();
    var x = BAR_X + RX + jitterX * (bar.w - RX * 2);
    var y = bar.y + 1.5 + jitterY * (BAR_H - 3);
    return { x: this.ox + x * this.scale, y: this.oy + y * this.scale, bar: bar };
  };

  Field.prototype.build = function () {
    var area = this.w * this.h;
    var count = this.markEnabled ? Math.round(Math.min(1100, Math.max(320, area / 2600))) : 0;
    if (window.innerWidth < 700) count = Math.round(count * 0.55);
    this.particles = [];
    for (var i = 0; i < count; i++) {
      var t = this.target(i);
      // start scattered around the edges, so the assembly reads as arrival
      var angle = Math.random() * Math.PI * 2, dist = Math.max(this.w, this.h) * (0.45 + Math.random() * 0.6);
      this.particles.push({
        x: this.w / 2 + Math.cos(angle) * dist,
        y: this.h / 2 + Math.sin(angle) * dist * 0.6,
        vx: 0, vy: 0,
        tx: t.x, ty: t.y,
        bar: BARS.indexOf(t.bar),
        size: 1.1 + Math.random() * 1.3,
        alpha: 0.30 + Math.random() * 0.45,
        colour: COLOURS[(Math.random() * COLOURS.length) | 0],
        phase: Math.random() * Math.PI * 2,
        release: 0
      });
    }

    // A second, sparser layer that never assembles into anything: fine points drifting on
    // their own, so the whole hero is alive rather than only the middle of it. They are
    // deliberately dim and small - this layer has to survive the same legibility gate the
    // mark does, and the gate is measured, not eyeballed.
    var ambientCount = Math.round(Math.min(220, Math.max(60, area / 9000)));
    if (window.innerWidth < 700) ambientCount = Math.round(ambientCount * 0.5);
    this.ambient = [];
    for (var j = 0; j < ambientCount; j++) {
      this.ambient.push({
        x: Math.random() * this.w,
        y: Math.random() * this.h,
        vx: (Math.random() - 0.5) * 0.16,
        vy: -0.05 - Math.random() * 0.16,
        size: 0.8 + Math.random() * 0.7,
        alpha: 0.08 + Math.random() * 0.13,
        colour: COLOURS[(Math.random() * COLOURS.length) | 0],
        wobble: Math.random() * Math.PI * 2,
        wobbleRate: 0.0004 + Math.random() * 0.0009
      });
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
    var hold = 4200, release = 2600;
    // springs integrate against elapsed time, not against frames: the same animation has to
    // take the same time on a 144Hz desktop and a 30fps laptop, or on a device that is
    // briefly busy. 16.667ms is the 60fps baseline everything below is tuned to.
    if (dt === undefined) dt = 16.667;
    var fdt = Math.min(dt, 50) / 16.667;
    for (i = 0; i < this.particles.length; i++) {
      p = this.particles[i];

      if (t < hold) {
        // assemble: bar 0 first, then 1, then 2 - the order the mark is drawn in
        var delay = p.bar * 520 + (p.phase / (Math.PI * 2)) * 260;
        if (t > delay) {
          var k = 0.028 * fdt, damp = Math.pow(0.90, fdt);   // spring toward the target
          p.vx += (p.tx - p.x) * k;
          p.vy += (p.ty - p.y) * k;
          p.vx *= damp; p.vy *= damp;
        }
      } else {
        // release: the mark comes loose and keeps only a weak memory of its lines
        var age = Math.min(1, (t - hold) / release);
        p.release = age;
        var fl = this.flow(p.x, p.y, t);
        p.vx += fl.x * 0.16 * age * fdt;
        p.vy += fl.y * 0.16 * age * fdt;
        p.vx += (p.tx - p.x) * 0.0009 * (1 - age * 0.55) * fdt;   // the ghost of the bars
        p.vy += (p.ty - p.y) * 0.0009 * (1 - age * 0.55) * fdt;
        var d2k = Math.pow(0.965, fdt); p.vx *= d2k; p.vy *= d2k;
      }

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
      p.x += p.vx + wob * 0.18 * fdt;
      p.y += p.vy * fdt;
      if (this.pointer.active) {
        dx = p.x - this.pointer.x; dy = p.y - this.pointer.y;
        d2 = dx * dx + dy * dy;
        if (d2 < 22000) { d = Math.sqrt(d2) || 1; f = (1 - d / 148) * 0.5 * fdt;
          p.vx += (dx / d) * f; p.vy += (dy / d) * f; }
      }
      p.vx *= 0.985; p.vy = p.vy * 0.985 - 0.0006;      // a slow upward bias, like dust
      if (p.x < -20) p.x = this.w + 20; else if (p.x > this.w + 20) p.x = -20;
      if (p.y < -20) p.y = this.h + 20; else if (p.y > this.h + 20) p.y = -20;
    }
  };

  Field.prototype.draw = function (now) {
    var ctx = this.ctx, t = now - (this.start || now), i, p;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = "lighter";
    for (var a = 0; a < this.ambient.length; a++) {
      p = this.ambient[a];
      ctx.fillStyle = p.colour;
      ctx.globalAlpha = p.alpha * this.dim(p.x, p.y);
      ctx.fillRect(p.x, p.y, p.size, p.size);
    }
    for (var c = 0; c < COLOURS.length; c++) {
      ctx.fillStyle = COLOURS[c];
      for (i = c; i < this.particles.length; i += COLOURS.length) {
        p = this.particles[i];
        var a = p.alpha * (t < 4200 ? 1 : 0.86) * this.dim(p.x, p.y);
        ctx.globalAlpha = a;
        ctx.fillRect(p.x, p.y, p.size, p.size);
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
    // no animation: settle the particles onto the mark and draw it once, fully formed
    fields.forEach(function (f) {
      f.start = performance.now() - 6000;
      for (var n = 0; n < 40; n++) f.step(f.start + n * 8);
      f.particles.forEach(function (p) { p.x = p.tx; p.y = p.ty; });
      f.draw(f.start + 400);
    });
  } else {
    // only animate what is on screen
    if (typeof window.IntersectionObserver === "function") {
      var seen = new WeakSet();
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          var f = fields.filter(function (x) { return x.canvas === e.target; })[0];
          if (!f) return;
          if (e.isIntersecting) { seen.add(e.target); f.start_(); } else { f.stop(); }
        });
      }, { rootMargin: "120px" });
      canvases.forEach(function (c) { io.observe(c); });
    } else {
      fields.forEach(function (f) { f.start_(); });
    }
    // expose for the live check: it asserts the assembly and the frame budget for real
    window.__thinkuiField = fields;
  }
})();
