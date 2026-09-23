/* ThinkUI — product site behaviour.
   Deliberately small and defensive: nothing here is allowed to be the only
   reason content is readable. Reveals are progressive enhancement (content is
   visible by default and only hidden once JS has confirmed it can un-hide it),
   and every feature degrades to a working baseline without it. */
(function () {
  "use strict";

  var doc = document;
  doc.documentElement.className += " js";

  /* ---------------------------------------------------------------- header */
  var header = doc.querySelector(".header");
  if (header) {
    var stuck = false;
    var onScroll = function () {
      var y = window.pageYOffset || doc.documentElement.scrollTop || 0;
      var next = y > 8;
      if (next !== stuck) {
        stuck = next;
        header.classList.toggle("is-stuck", stuck);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    var burger = header.querySelector(".burger");
    if (burger) {
      burger.addEventListener("click", function () {
        var open = header.classList.toggle("is-open");
        burger.setAttribute("aria-expanded", open ? "true" : "false");
      });
      // a tap on a link should close the sheet, not leave it over the page
      header.addEventListener("click", function (ev) {
        if (ev.target.closest && ev.target.closest(".nav a") && header.classList.contains("is-open")) {
          header.classList.remove("is-open");
          burger.setAttribute("aria-expanded", "false");
        }
      });
    }
  }

  /* ---------------------------------------------------------------- reveals */
  function revealAll() {
    var nodes = doc.querySelectorAll("[data-rise]");
    for (var i = 0; i < nodes.length; i++) { nodes[i].classList.add("in"); }
  }

  function initReveals() {
    var nodes = doc.querySelectorAll("[data-rise]");
    if (!nodes.length) { return; }

    // Above the fold reveals synchronously on first paint: if anything below
    // fails, the top of the page was never hidden in the first place.
    var fold = window.innerHeight || 800;
    var below = [];
    for (var i = 0; i < nodes.length; i++) {
      var r = nodes[i].getBoundingClientRect();
      if (r.top < fold * 0.9) { nodes[i].classList.add("in"); } else { below.push(nodes[i]); }
    }

    var usesObserver = false;
    if (below.length && typeof window.IntersectionObserver === "function") {
      try {
        var io = new IntersectionObserver(function (entries) {
          for (var j = 0; j < entries.length; j++) {
            if (entries[j].isIntersecting) {
              entries[j].target.classList.add("in");
              io.unobserve(entries[j].target);
            }
          }
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
        for (var k = 0; k < below.length; k++) { io.observe(below[k]); }
        usesObserver = true;
      } catch (e) { usesObserver = false; }
    }

    // Second, independent mechanism: a scroll-driven rect sweep plus timed
    // fallbacks, so a page whose observer never fires still reveals itself.
    var sweep = function () {
      for (var n = below.length - 1; n >= 0; n--) {
        var el = below[n];
        if (el.getBoundingClientRect().top < (window.innerHeight || 800) * 0.94) {
          el.classList.add("in");
          below.splice(n, 1);
        }
      }
      if (!below.length) { window.removeEventListener("scroll", sweep); }
    };
    window.addEventListener("scroll", sweep, { passive: true });
    window.addEventListener("resize", sweep, { passive: true });
    window.setTimeout(sweep, 120);
    if (!usesObserver) { window.setTimeout(revealAll, 1400); }
    window.setTimeout(sweep, 2600);

    // Never print blank paper.
    window.addEventListener("beforeprint", revealAll);
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      revealAll();
    }
  }

  /* ------------------------------------------------------------------- copy */
  function legacyCopy(text, done) {
    try {
      var ta = doc.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      doc.body.appendChild(ta);
      ta.select();
      doc.execCommand("copy");
      doc.body.removeChild(ta);
      done();
    } catch (e) { /* the code is selectable anyway */ }
  }

  function initCopy() {
    var buttons = doc.querySelectorAll("[data-copy]");
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.addEventListener("click", function () {
        var host = btn.closest(".code");
        var pre = host && host.querySelector("pre");
        if (!pre) { return; }
        var text = pre.innerText || pre.textContent || "";
        var label = btn.querySelector("span");
        var prev = label ? label.textContent : "";
        var done = function () {
          btn.classList.add("is-done");
          if (label) { label.textContent = "Copied"; }
          window.setTimeout(function () {
            btn.classList.remove("is-done");
            if (label) { label.textContent = prev; }
          }, 1900);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { legacyCopy(text, done); });
        } else {
          legacyCopy(text, done);
        }
      });
    });
  }

  /* --------------------------------------------------------------- ticker */
  // Duplicate the strip once so the marquee loops seamlessly and always has
  // enough content to fill the widest viewport.
  function initTicker() {
    var row = doc.querySelector(".ticker__row");
    if (!row) { return; }
    row.innerHTML += row.innerHTML;
  }

  function boot() {
    initReveals();
    initCopy();
    initTicker();
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
