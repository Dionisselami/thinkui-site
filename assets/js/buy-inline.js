/* Buy inline from the marketing pages.
 *
 * A signed-in visitor who clicks "Get Starter" on /pricing should not be sent back to
 * /signup to make an account they already have. This asks the auth service who they are,
 * and when there is a session it opens the Polar checkout as an overlay on the page.
 *
 * Signed out, no JS, a blocked CDN or a failed request: every link still goes to
 * /signup?plan=... exactly as before. The enhancement can only add a faster path, never
 * remove the working one.
 */
(function () {
  var PLAN = /[?&]plan=(starter|pro|lifetime)(?:[&#]|$)/;
  var links = Array.prototype.filter.call(
    document.querySelectorAll('a[href*="plan="]'),
    function (a) { return PLAN.test(a.getAttribute('href') || ''); }
  );
  if (!links.length) return;

  var polarQueued = false;

  function loadPolar() {
    if (polarQueued) return;
    polarQueued = true;
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/@polar-sh/checkout@latest/dist/embed.global.js';
    s.defer = true;
    s.setAttribute('data-polar-embed', '');
    document.head.appendChild(s);
  }

  function planOf(a) {
    var m = (a.getAttribute('href') || '').match(PLAN);
    return m ? m[1] : '';
  }

  function buy(a) {
    var plan = planOf(a);
    if (!plan) return;
    if (!(window.Polar && window.Polar.EmbedCheckout)) {
      window.location = '/signup?plan=' + plan;
      return;
    }
    var label = a.textContent;
    a.textContent = 'Opening checkout...';
    a.setAttribute('aria-busy', 'true');
    var body = new FormData();
    body.append('plan', plan);
    fetch('/api/billing/checkout', {
      method: 'POST',
      body: body,
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.url) throw new Error('no checkout url');
        return window.Polar.EmbedCheckout.create(d.url, { theme: 'dark' });
      })
      .then(function (checkout) {
        checkout.addEventListener('success', function (event) {
          if (event && event.detail && event.detail.redirect) return;
          window.location = '/account?notice=Payment+received.+Thank+you.';
        });
      })
      .catch(function () {
        a.textContent = label;
        a.removeAttribute('aria-busy');
        window.location = '/signup?plan=' + plan;
      });
  }

  fetch('/api/auth/session', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (session) {
      if (!session || !session.authenticated) return;
      loadPolar();
      links.forEach(function (a) {
        a.addEventListener('click', function (event) {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
          event.preventDefault();
          buy(a);
        });
      });
    })
    .catch(function () { /* signed out or offline: leave the links alone */ });
})();
