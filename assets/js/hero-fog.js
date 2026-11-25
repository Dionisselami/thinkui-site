/* The selected Vanta Fog preset; the rest of the homepage works without this script. */
(() => {
  'use strict';

  const hero = document.querySelector('.hero--fog');
  const stage = hero?.querySelector('.hero__fog-stage');
  const button = hero?.querySelector('.hero__fog-toggle');
  if (!stage || !button || !window.matchMedia) return;

  const vendor = new URL('../vendor/', document.currentScript.src);
  const staticMode = matchMedia('(prefers-reduced-motion: reduce), (forced-colors: active)');
  const canObserve = typeof IntersectionObserver === 'function';
  let nearby = !canObserve, paused = false, available = false, blocked = false;
  let assets, effect, starting = false;

  const shouldAnimate = () => nearby && !paused && !blocked && !staticMode.matches && !document.hidden;
  const load = path => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = new URL(path, vendor).href;
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });

  function supportsWebGL() {
    try {
      const probe = document.createElement('canvas');
      const context = probe.getContext('webgl2') || probe.getContext('webgl');
      if (!context) return false;
      context.getExtension('WEBGL_lose_context')?.loseContext();
      return true;
    } catch { return false; }
  }

  function stop() {
    if (!effect) return;
    const current = effect, renderer = current.renderer;
    effect = undefined;
    try { current.destroy(); }
    catch { stage.replaceChildren(); }
    // Vanta 0.5.23 removes the canvas/listeners but leaves its Three renderer to dispose.
    if (renderer) {
      renderer.forceContextLoss();
      renderer.dispose();
    }
  }

  async function start() {
    if (effect || starting || !shouldAnimate()) return;
    starting = true;
    try {
      if (!assets && !supportsWebGL()) { blocked = true; return; }
      assets ??= load('three-r134/three.r134.min.js').then(() => load('vanta-0.5.23/vanta.fog.min.js'));
      await assets;
      if (!shouldAnimate()) return;
      effect = window.VANTA.FOG({
        el: stage,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200.00,
        minWidth: 200.00,
        highlightColor: 0xff0092,
        midtoneColor: 0xce7bf0,
        lowlightColor: 0xff0000,
        baseColor: 0x1e0d0d,
        backgroundAlpha: 1,
        blurFactor: 0.6,
        scale: 2,
        scaleMobile: 4,
        speed: 1,
        zoom: 1
      });
      if (!stage.querySelector('canvas.vanta-canvas')) throw new Error('No WebGL canvas');
      available = true;
      button.hidden = staticMode.matches;
    } catch {
      blocked = true;
      stop();
      button.hidden = true;
    } finally {
      starting = false;
    }
  }

  function sync() {
    button.hidden = !available || blocked || staticMode.matches;
    if (shouldAnimate()) start();
    else stop();
  }

  button.title = 'Pause background animation';
  button.addEventListener('click', () => {
    paused = !paused;
    button.setAttribute('aria-pressed', String(paused));
    button.title = paused ? 'Play background animation' : 'Pause background animation';
    sync();
  });
  if (staticMode.addEventListener) staticMode.addEventListener('change', sync);
  else staticMode.addListener(sync);
  document.addEventListener('visibilitychange', sync);
  window.addEventListener('pagehide', stop);
  window.addEventListener('pageshow', sync);
  if (canObserve) {
    new IntersectionObserver(([entry]) => {
      nearby = entry.isIntersecting;
      sync();
    }, {rootMargin: '96px'}).observe(hero);
  } else sync();
})();
