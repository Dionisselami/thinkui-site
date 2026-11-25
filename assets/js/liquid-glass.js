/* Edge refraction for the two glass surfaces. Colors are sampled from the live backdrop. */
(() => {
  'use strict';
  if (!document.body.classList.contains('glass-home') || !window.CSS?.supports('backdrop-filter', 'url(#glass-optics)')) return;

  // Parsing a URL is not proof of painting an SVG backdrop filter. Enable the
  // measured Chromium path; the CSS blur/rim remains on other engines.
  const chromium = navigator.userAgentData?.brands.some(({brand}) => brand === 'Chromium') ||
    /\b(?:Chrome|Chromium|Edg)\/\d/.test(navigator.userAgent) && !/\b(?:iPhone|iPad|iPod)\b/.test(navigator.userAgent);
  if (!chromium) return;

  const nav = document.querySelector('.header__inner');
  const action = document.querySelector('.hero__actions .btn--ghost');
  if (!nav && !action) return;
  const noGlass = matchMedia('(prefers-reduced-transparency: reduce), (forced-colors: active)');
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', '0');
  svg.setAttribute('height', '0');
  svg.setAttribute('aria-hidden', 'true');
  svg.style.cssText = 'position:absolute;pointer-events:none';
  const defs = document.createElementNS(svgNS, 'defs');
  svg.append(defs);
  document.body.append(svg);

  const map = document.createElement('canvas');
  const ctx = map.getContext('2d');
  if (!ctx) return;
  const surfaces = [];
  if (nav) {
    for (const [name, side] of [['left', -1], ['right', 1]]) {
      const el = document.createElement('span');
      el.className = `glass-cap glass-cap--${name}`;
      el.setAttribute('aria-hidden', 'true');
      nav.append(el);
      surfaces.push({el, side});
    }
    nav.dataset.glassSegments = '';
  }
  if (action) surfaces.push({el: action, side: 0});
  const previous = new Map();
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function displacement(w, h, rim, side) {
    map.width = w; map.height = h;
    const image = ctx.createImageData(w, h);
    const r = h / 2, axis = Math.max(0, w / 2 - r);
    for (let y = 0; y < h; y++) {
      const dy = y + .5 - r;
      for (let x = 0; x < w; x++) {
        const cx = x + .5 - w / 2;
        const dx = side < 0 ? Math.min(0, x + .5 - r) : side > 0 ? Math.max(0, x + .5 - w + r) : cx - clamp(cx, -axis, axis);
        const dist = Math.hypot(dx, dy), depth = r - dist;
        // Normal to the capsule, strongest just within the curved rim. Keep
        // the center clear and the outermost pixels continuous with the page.
        // Ease back to unmoved pixels near the join with the nav's frosted span.
        const join = side === 0 ? 1 : Math.min(1, (side < 0 ? w - x - .5 : x + .5) / 18);
        const falloff = depth > 0 && depth < rim ? join * Math.min(1, depth / 2) * (1 - depth / rim) ** 1.55 : 0;
        const pull = dist ? 122 * falloff / dist : 0;
        const i = (y * w + x) * 4;
        image.data[i] = 128 - dx * pull;
        image.data[i + 1] = 128 - dy * pull;
        image.data[i + 2] = 255 * Math.min(1, falloff * 1.3);
        image.data[i + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
    return map.toDataURL();
  }

  const components = {
    red:   '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0',
    green: '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0',
    blue:  '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0'
  };

  function setLens({el, side}, index) {
    const {width, height} = el.getBoundingClientRect();
    const w = Math.round(width), h = Math.round(height);
    const old = previous.get(el);
    if (w < h || h < 1 || (old?.w === w && old.h === h)) return;

    const id = `thinkui-lens-${index}`;
    const filter = document.createElementNS(svgNS, 'filter');
    Object.entries({id, filterUnits: 'userSpaceOnUse', primitiveUnits: 'userSpaceOnUse', x:0, y:0, width:w, height:h,
      'color-interpolation-filters': 'sRGB'}).forEach(([key, value]) => filter.setAttribute(key, String(value)));
    const href = displacement(w, h, side ? 15 : 12, side);
    const scales = side ? [18, 28, 38] : [24, 35, 46];
    // Inputs here are computed dimensions, a locally generated PNG, and constants.
    filter.innerHTML = `<feImage href="${href}" x="0" y="0" width="${w}" height="${h}" preserveAspectRatio="none" result="lensMap"/>` +
      Object.entries(components).map(([channel, matrix], i) =>
        `<feDisplacementMap in="SourceGraphic" in2="lensMap" scale="${scales[i]}" xChannelSelector="R" yChannelSelector="G" result="bend${i}"/>` +
        `<feColorMatrix in="bend${i}" type="matrix" values="${matrix}" result="${channel}"/>`
      ).join('') + '<feBlend in="red" in2="green" mode="screen" result="redGreen"/><feBlend in="redGreen" in2="blue" mode="screen" result="dispersed"/>' +
      // The map's blue channel isolates the curved edge. Concentrate the
      // sampled light there, without tinting or dimming the clear center.
      '<feColorMatrix in="lensMap" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 1 0 0" result="rimMask"/>' +
      '<feColorMatrix in="dispersed" type="matrix" values="1.48 0 0 0 .008  0 1.48 0 0 .008  0 0 1.48 0 .008  0 0 0 1 0" result="focused"/>' +
      '<feComposite in="focused" in2="rimMask" operator="in" result="rim"/>' +
      '<feMerge><feMergeNode in="dispersed"/><feMergeNode in="rim"/></feMerge>';
    if (old) old.filter.replaceWith(filter); else defs.append(filter);
    previous.set(el, {w, h, filter});
    el.style.setProperty('--glass-optics', `url("#${id}")`);
    el.dataset.glassOptics = '';
  }

  let frame = 0;
  function update() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (!noGlass.matches) surfaces.forEach(setLens);
    });
  }
  if (typeof ResizeObserver === 'function') {
    const observer = new ResizeObserver(update);
    surfaces.forEach(({el}) => observer.observe(el));
  } else window.addEventListener('resize', update, {passive:true});
  if (noGlass.addEventListener) noGlass.addEventListener('change', update);
  else noGlass.addListener(update);
  update();
})();
