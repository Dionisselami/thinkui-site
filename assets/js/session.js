/* Every page is static, so the header is baked before anyone signs in — which is why a
   signed-in visitor kept reading "Sign in" on the homepage. Ask the account service who
   this is and put the truthful thing in the header: their photo (or initial) and Account. */
(function () {
  var cta = document.querySelector('.nav__cta');
  if (!cta) return;

  var signin = cta.querySelector('a[href$="login.html"], a[href="/login"], a[href$="/login"]');
  var primary = cta.querySelector('.btn--primary');

  function initial(email) {
    var name = String(email || '').split('@')[0].replace(/[^a-zA-Z0-9]/g, '');
    return (name.charAt(0) || '?').toUpperCase();
  }

  function avatar(session) {
    if (session.picture) {
      var img = document.createElement('img');
      img.className = 'nav__avatar';
      img.src = session.picture;
      img.alt = '';
      img.width = 24;
      img.height = 24;
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', function () { img.replaceWith(badge(session.email)); });
      return img;
    }
    return badge(session.email);
  }

  function badge(email) {
    var span = document.createElement('span');
    span.className = 'nav__avatar nav__avatar--initial';
    span.textContent = initial(email);
    return span;
  }

  fetch('/api/auth/session', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      if (!s || !s.authenticated) return;

      if (signin) {
        var a = document.createElement('a');
        a.className = 'btn btn--text nav__acct';
        a.href = '/account';
        a.title = s.email || 'Your account';
        a.appendChild(avatar(s));
        a.appendChild(document.createTextNode('Account'));
        signin.replaceWith(a);
      }
      if (primary) {
        // A paying customer does not need the trial pitch in their own header; a free
        // account still does, so only touch it once there is nothing left to sell.
        if (s.plan && s.plan !== 'free') {
          primary.remove();
        }
      }
      var foot = document.querySelector('.footer a[href$="login.html"], .footer a[href="/login"], .footer a[href$="/login"]');
      if (foot) {
        foot.textContent = 'Account';
        foot.href = '/account';
      }
    })
    .catch(function () { /* sign-in state is decoration: never block the page on it */ });
})();
