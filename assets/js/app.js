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
    initCopy();
    initTicker();
    initAuth();
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
