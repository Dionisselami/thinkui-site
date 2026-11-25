/* Sign-in helpers for /signup and /login (2026-11-22).

   1. Plan choice: the radio buttons on /signup decide which plan rides on the Google and
      GitHub links, so every new account goes straight to checkout after sign-in. The
      choice starts from ?plan= when a pricing button sent the visitor here.
   2. In-app browsers: Google refuses to sign anyone in inside X's, Instagram's,
      Facebook's (and similar) built-in browsers. Those visitors get a notice with a
      Copy link button and, where the platform allows it, an Open in browser link.
      Nothing changes for a normal browser, and "Continue here anyway" hides the notice
      (GitHub sign-in can still work in there).

   Defensive like app.js: any failure leaves the page as it was. */
(function () {
  "use strict";
  var doc = document;
  /* "free" pre-selects the Free option (?plan=free from a "Try free" button). The
     account service only opens a checkout for the paid plans, so a free sign-up
     lands on /account with its key form. */
  var PLANS = ["starter", "pro", "lifetime", "free"];

  function validPlan(p) { p = (p || "").toLowerCase(); return PLANS.indexOf(p) === -1 ? "" : p; }

  function currentPlan() {
    var picked = doc.querySelector('.planpick input[name="plan"]:checked');
    if (picked) return validPlan(picked.value);
    try { return validPlan(new URLSearchParams(location.search).get("plan")); } catch (e) { return ""; }
  }

  function pageUrl() {
    var plan = currentPlan();
    return location.origin + location.pathname + (plan ? "?plan=" + plan : "");
  }

  /* ---- 1. plan choice ---- */
  function syncLinks() {
    var plan = currentPlan();
    var links = doc.querySelectorAll('.oauth a[href^="/api/auth/"]');
    Array.prototype.forEach.call(links, function (a) {
      var base = a.getAttribute("href").split("?")[0];
      a.setAttribute("href", plan ? base + "?plan=" + plan : base);
    });
    var copyTarget = doc.querySelector(".inapp [data-inapp-open]");
    if (copyTarget) copyTarget.setAttribute("href", openHref());
  }

  function initPicker() {
    var pick = doc.querySelector(".planpick");
    if (!pick) return;
    var wanted = "";
    try { wanted = validPlan(new URLSearchParams(location.search).get("plan")); } catch (e) { /* old browser */ }
    if (wanted) {
      var radio = pick.querySelector('input[value="' + wanted + '"]');
      if (radio) radio.checked = true;
    }
    pick.addEventListener("change", syncLinks);
  }

  /* ---- 2. in-app browsers ---- */
  var UA = navigator.userAgent || "";
  var APPS = [
    [/Twitter|TwitterAndroid/i, "X"],
    [/Instagram/i, "Instagram"],
    [/FBAN|FBAV|FB_IAB|FBIOS|FB4A|MessengerForiOS|\bMessenger\b/i, "Facebook"],
    [/Barcelona/i, "Threads"],
    [/LinkedInApp/i, "LinkedIn"],
    [/musical_ly|BytedanceWebview|TikTok|trill_/i, "TikTok"],
    [/Snapchat/i, "Snapchat"],
    [/Pinterest/i, "Pinterest"],
    [/\bLine\//i, "LINE"],
    [/MicroMessenger/i, "WeChat"],
    [/Telegram/i, "Telegram"],
    [/; wv\)/, ""]                     /* any other Android WebView */
  ];
  var isAndroid = /Android/i.test(UA);
  var isIOS = /iPhone|iPad|iPod/i.test(UA);

  function inAppName() {
    for (var i = 0; i < APPS.length; i++) {
      if (APPS[i][0].test(UA)) return APPS[i][1] || "this app";
    }
    return null;
  }

  function openHref() {
    var url = pageUrl();
    if (isAndroid) {
      var rest = url.replace(/^https?:\/\//, "");
      return "intent://" + rest + "#Intent;scheme=https;action=android.intent.action.VIEW;" +
        "S.browser_fallback_url=" + encodeURIComponent(url) + ";end";
    }
    if (isIOS) return "x-safari-" + url;   /* iOS 17+: opens Safari; older iOS ignores it */
    return url;
  }

  function copy(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { legacy(text, done); });
    } else {
      legacy(text, done);
    }
  }
  function legacy(text, done) {
    try {
      var ta = doc.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", "");
      ta.style.position = "fixed"; ta.style.opacity = "0";
      doc.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
      var ok = doc.execCommand("copy");
      doc.body.removeChild(ta);
      if (ok) done(); else window.prompt("Copy this link:", text);
    } catch (e) { window.prompt("Copy this link:", text); }
  }

  function initInApp() {
    var app = inAppName();
    var card = doc.querySelector(".auth__card");
    if (!app || !card) return;
    var browser = isIOS ? "Safari" : (isAndroid ? "Chrome" : "your browser");
    var how = isIOS
      ? "Tap the ••• or share button and choose Open in Safari, or copy the link and paste it into Safari."
      : (isAndroid ? "Tap ⋮ and choose Open in Chrome (or Open in browser), or copy the link."
                   : "Copy the link and open it in your browser.");
    var box = doc.createElement("div");
    box.className = "inapp";
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", "Open in your browser");
    box.innerHTML =
      '<p class="inapp__title">Open this page in ' + browser + ' to sign in with Google</p>' +
      '<p class="inapp__text">Google blocks sign-in inside ' + (app === "this app" ? "in-app browsers" : app + "’s built-in browser") +
      ". " + how + ' Your plan choice is kept in the link.</p>' +
      '<div class="inapp__actions">' +
      '<button type="button" class="btn btn--primary btn--block" data-inapp-copy>Copy link</button>' +
      ((isAndroid || isIOS) ? '<a class="btn btn--block" data-inapp-open href="#">Open in ' + browser + '</a>' : "") +
      '</div>' +
      '<p class="inapp__done" aria-live="polite"></p>' +
      '<button type="button" class="inapp__skip" data-inapp-skip>Continue here anyway (GitHub may work)</button>';
    var head = card.querySelector(".auth__head");
    if (head && head.nextSibling) card.insertBefore(box, head.nextSibling); else card.insertBefore(box, card.firstChild);
    doc.documentElement.classList.add("is-inapp");

    var openLink = box.querySelector("[data-inapp-open]");
    if (openLink) openLink.setAttribute("href", openHref());
    box.querySelector("[data-inapp-copy]").addEventListener("click", function () {
      var btn = this;
      copy(pageUrl(), function () {
        btn.textContent = "Link copied";
        box.querySelector(".inapp__done").textContent = "Now paste it into " + browser + ".";
        setTimeout(function () { btn.textContent = "Copy link"; }, 2500);
      });
    });
    box.querySelector("[data-inapp-skip]").addEventListener("click", function () {
      box.hidden = true;
    });
  }

  function boot() {
    try { initPicker(); } catch (e) { /* page stays as served */ }
    try { syncLinks(); } catch (e) { /* links keep their served href */ }
    try { initInApp(); } catch (e) { /* no notice is better than a broken page */ }
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", boot); else boot();
})();
