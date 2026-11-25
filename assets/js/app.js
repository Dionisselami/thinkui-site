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
      var setMenu = function (open) {
        header.classList.toggle("is-open", open);
        burger.setAttribute("aria-expanded", open ? "true" : "false");
      };
      burger.addEventListener("click", function () {
        setMenu(!header.classList.contains("is-open"));
      });
      // a tap on a link should close the sheet, not leave it over the page
      header.addEventListener("click", function (ev) {
        if (ev.target.closest && ev.target.closest(".nav a") && header.classList.contains("is-open")) {
          setMenu(false);
        }
      });
      doc.addEventListener("keydown", function (ev) {
        if (ev.key !== "Escape" || !header.classList.contains("is-open")) { return; }
        setMenu(false);
        burger.focus();
      });
    }
  }

  /* ---------------------------------------------------------------- sign-in */
  /* Both ways in are OAuth, so a visitor who pressed "Get Pro" and then picked a
     provider would otherwise land on the account page with no plan chosen. The plan
     they clicked rides on the provider link; the server turns it into a checkout
     after the callback. */
  (function carryPlan() {
    var qs = new URLSearchParams(location.search);
    var plan = (qs.get("plan") || "").toLowerCase();
    if (["starter", "pro", "lifetime"].indexOf(plan) === -1) { return; }
    var links = doc.querySelectorAll('.oauth a[href^="/api/auth/"]');
    Array.prototype.forEach.call(links, function (a) {
      var href = a.getAttribute("href");
      a.setAttribute("href", href + (href.indexOf("?") === -1 ? "?" : "&") + "plan=" + plan);
    });
  })();

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

  /* ---------------------------------------------------------------- motion */
  function reduceMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  /* Reveals. [data-reveal] is only hidden once .js is on <html> (see site.css), so a
     browser without JS — or an error above this line — leaves the page visible.
     A scroll check rather than an IntersectionObserver, because a jump (anchor, End,
     find-in-page) never intersects the sections it skips and they would stay blank.
     Anything whose top has reached the viewport is revealed, including everything
     above it. */
  function initReveal() {
    var items = [].slice.call(doc.querySelectorAll("[data-reveal]"));
    if (!items.length) { return; }
    if (reduceMotion()) {
      items.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var check = function () {
      var h = window.innerHeight || 800;
      items = items.filter(function (el) {
        if (el.getBoundingClientRect().top < h * 0.94) {
          el.classList.add("in");
          return false;
        }
        return true;
      });
      if (!items.length) {
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
      }
    };
    var ticking = false;
    var onScroll = function () {
      if (ticking) { return; }
      ticking = true;
      window.requestAnimationFrame(function () { ticking = false; check(); });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    check();
    window.setTimeout(check, 350);
  }

  /* The proof numerals count up once, when the strip is first seen. The final value is
     already in the markup: this replaces a correct number with the same number, moving. */
  function initCounters() {
    var nums = [].slice.call(doc.querySelectorAll("[data-count]"));
    if (!nums.length || reduceMotion() || !("IntersectionObserver" in window)) { return; }
    var fmt = function (n) { return n.toLocaleString("en-US"); };
    var run = function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      var start = null, dur = 1100;
      var step = function (ts) {
        if (start === null) { start = ts; }
        var p = Math.min(1, (ts - start) / dur);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = fmt(Math.round(target * eased));
        if (p < 1) { window.requestAnimationFrame(step); } else { el.textContent = fmt(target); }
      };
      window.requestAnimationFrame(step);
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.35 });
    nums.forEach(function (el) { io.observe(el); });
  }

  /* A very small parallax in the hero: the pointer moves and the room shifts behind
     the type. Two custom properties, one rAF per frame, nothing on a touch screen. */
  function initHeroPointer() {
    var hero = doc.querySelector(".hero");
    var stage = doc.querySelector(".hero__stage");
    if (!hero || !stage || reduceMotion()) { return; }
    if (window.matchMedia && window.matchMedia("(hover: none)").matches) { return; }
    var raf = 0, tx = 0, ty = 0;
    hero.addEventListener("pointermove", function (ev) {
      var r = hero.getBoundingClientRect();
      tx = ((ev.clientX - r.left) / r.width - 0.5) * 18;
      ty = ((ev.clientY - r.top) / r.height - 0.5) * 12;
      if (raf) { return; }
      raf = window.requestAnimationFrame(function () {
        raf = 0;
        stage.style.setProperty("--mx", tx.toFixed(1) + "px");
        stage.style.setProperty("--my", ty.toFixed(1) + "px");
      });
    });
    hero.addEventListener("pointerleave", function () {
      stage.style.setProperty("--mx", "0px");
      stage.style.setProperty("--my", "0px");
    });
  }

  /* The library: chips filter the wall by the tag the build wrote on each card, and
     "Show more" reveals the rest. Without JS every card remains visible. */
  function initLibrary() {
    var wall = doc.querySelector("[data-wall]");
    if (!wall) { return; }
    var cards = [].slice.call(wall.querySelectorAll(".wall__card"));
    if (!cards.length) { return; }
    var toolbar = doc.querySelector(".wall__tools .chips");
    var chips = [].slice.call(doc.querySelectorAll("[data-filter]"));
    var countEl = doc.querySelector("[data-wall-count]");
    var more = doc.querySelector("[data-more]");
    var STEP = 16, shown = STEP, filter = "all";

    function apply() {
      var visible = 0;
      cards.forEach(function (card) {
        var tags = (card.getAttribute("data-tags") || "").split(/\s+/);
        var match = filter === "all" || tags.indexOf(filter) !== -1;
        var within = filter !== "all" || visible < shown;
        var show = match && within;
        card.classList.toggle("is-hidden", !show);
        if (show) { visible += 1; }
      });
      chips.forEach(function (chip) {
        var selected = chip.getAttribute("data-filter") === filter;
        chip.classList.toggle("is-active", selected);
        chip.setAttribute("aria-pressed", String(selected));
      });
      if (countEl) { countEl.textContent = "Showing " + visible + " of " + cards.length + " screens"; }
      if (more) {
        var left = cards.length - visible;
        more.hidden = filter !== "all" || left <= 0;
        more.textContent = "Show " + Math.max(0, left) + " more";
      }
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        filter = chip.getAttribute("data-filter");
        shown = STEP;
        apply();
      });
    });
    if (more) {
      more.addEventListener("click", function () { shown += cards.length; apply(); });
    }
    apply();
    if (toolbar) { toolbar.hidden = false; }
  }

  function boot() {
    /* Each feature guards itself: one failure must not stop the rest, and the reveals
       arm first so content is never left hidden by a later error. */
    try { initReveal(); } catch (e) { /* the CSS failsafe still shows everything */ }
    try { initCounters(); } catch (e) { /* the final numbers are already in the markup */ }
    try { initHeroPointer(); } catch (e) { /* decoration only */ }
    try { initLibrary(); } catch (e) { /* without it every card stays visible */ }
    try { initCopy(); } catch (e) { /* the code is selectable anyway */ }
    try { initTicker(); } catch (e) { /* no ticker on this page */ }
    try { initAuth(); } catch (e) { /* forms still post */ }
  }

  // The sign-in and sign-up forms post to the account service, which answers with a
  // redirect carrying ?error= or ?ok=. This shows that answer, remembers which plan the
  // visitor picked on the pricing page, and stops a double submit from creating two
  // accounts.
  function initAuth() {
    var card = doc.querySelector(".auth__card");
    if (!card) return;
    var params = new URLSearchParams(location.search);
    var note = params.get("error") || params.get("ok");
    if (note) {
      var msg = doc.createElement("div");
      msg.className = "auth__msg " + (params.get("error") ? "auth__msg--err" : "auth__msg--ok");
      msg.setAttribute("role", "status");
      // Verdict in words first, then the colour agrees with it (see .auth__msg in site.css).
    var cut = note.indexOf(". ");
    if (cut > 0 && cut <= 60) {
      var verdict = doc.createElement("b");
      verdict.textContent = note.slice(0, cut + 1);
      msg.appendChild(verdict);
      msg.appendChild(doc.createTextNode(" " + note.slice(cut + 2)));
    } else {
      msg.textContent = note;
    }
      card.insertBefore(msg, card.firstChild);
    }

    var form = card.querySelector("form");
    if (!form) return;
    var plan = params.get("plan");
    if (plan && /^(pro|team)$/.test(plan)) {
      var hidden = doc.createElement("input");
      hidden.type = "hidden";
      hidden.name = "plan";
      hidden.value = plan;
      form.appendChild(hidden);
      var label = form.querySelector("button[type=submit]");
      if (label) label.textContent = "Continue to " + plan.charAt(0).toUpperCase() + plan.slice(1);
      var head = card.querySelector(".auth__head p");
      if (head) head.textContent = "One step: your account, then " + plan.charAt(0).toUpperCase() +
        plan.slice(1) + ". Cancel any time from your account page.";
    }

    // A failed sign-in comes back as a redirect, which drops the email that was just typed:
    // one wrong password meant retyping both fields. Keep the address for the trip.
    var emailField = form.querySelector("input[name=email]");
    if (emailField) {
      try {
        var kept = sessionStorage.getItem("thinkui.email");
        if (kept && !emailField.value) emailField.value = kept;
      } catch (e) { /* storage blocked (private mode) - not worth failing over */ }
      form.addEventListener("submit", function () {
        try { sessionStorage.setItem("thinkui.email", emailField.value); } catch (e) { /* ignore */ }
      });
    }

    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = true; btn.textContent = "Working…"; }
    });
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
