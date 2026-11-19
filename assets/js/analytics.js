/* One page view, no storage.
 *
 * This posts to our own /api/pv rather than to PostHog: the visitor's IP and user agent
 * stay on the box, and the server sends a daily salted id instead. Nothing is written to
 * cookies or localStorage, which is why the site still needs no consent banner.
 * Respects Do Not Track; sendBeacon so an immediate navigation still counts.
 */
(function () {
  if (navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl) return;
  var sent = false;
  function send() {
    if (sent) return;
    sent = true;
    var body = JSON.stringify({ path: location.pathname, ref: document.referrer || "" });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/pv", new Blob([body], { type: "application/json" }));
      } else {
        fetch("/api/pv", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body,
          keepalive: true
        });
      }
    } catch (e) { /* measurement must never break the page */ }
  }
  if (document.readyState === "complete") send();
  else window.addEventListener("load", send, { once: true });
})();
