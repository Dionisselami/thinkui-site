/* Black Friday, Lifetime only, until 22:59:59 UTC on 27 Nov 2026.
   The page is static HTML, so the sale is applied by script and disappears by itself
   when the deadline passes: after UNTIL this file does nothing and every price falls
   back to the list numbers baked into the build. The backend closes the discount on the
   same timestamp (THINKUI_BF_UNTIL), so page and checkout agree without a midnight deploy. */
(function () {
  var UNTIL = Date.parse("2026-11-27T22:59:59Z");
  if (!(Date.now() < UNTIL)) return;

  function setAll(sel, value) {
    var nodes = document.querySelectorAll(sel);
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = value;
  }

  setAll("[data-bf-price]", "$95");
  setAll("[data-bf-price-once]", "$95 once");

  if (document.querySelector(".bf-strip")) return;

  var strip = document.createElement("a");
  strip.className = "bf-strip";
  strip.href = "/signup?plan=lifetime";
  strip.innerHTML =
    '<b>Black Friday</b> Lifetime is <s>$190</s> <strong>$95</strong>' +
    ' \u2014 today only, ends tonight at 23:59. <span>Get it \u2192</span>';
  document.body.insertBefore(strip, document.body.firstChild);
})();
