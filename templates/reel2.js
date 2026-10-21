// Графит для рилсов 1080x1920, версия 2 (утверждена 04.10.2026 по раскадровке): старт во весь кадр,
// после хука окно автора плавно уходит в правый верхний угол, под ним проступает графитовая панель (как урок 02).
// Кадры автора 1080x1920 (SEG.dirs.author_pb). Шапка и хук лежат поверх кадра, графика рилса в #content панели. Подключать после ./data.js, ../../kit/kit.js, gsap.min.js.
// Рилс склеен из кусков полного ролика (SEG.segs: [начало, конец, смещение в рилсе]): кадры автора и фона
// берутся из full/ по времени полного ролика. Основа сама рисует фон, панель, шапку, окно автора,
// хук в первые секунды, субтитры и финальную карточку. Рилс рисует свою графику в #content.
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const C = { paper: '#F5F3ED', ink: '#292929', violet: '#5842C3', lilac: '#CEC5EA', lime: '#D6E69C' };
  // бренд из config.py (BRAND): logo - путь или url картинки логотипа (необязательно), name - текст вместо логотипа,
  // author - подпись автора, channel - строка канала на финальной карточке
  const BR = SEG.brand || {};
  const LOGO = BR.logo ? `<img src="${BR.logo}" alt="">` : `<b class="logoTxt">${BR.name || ''}</b>`;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const R = SEG.reel;

  // Окно автора (координаты кадра): low - широкое окно под графикой, big - крупно на рассуждениях.
  // окно автора (координаты кадра): full - во весь кадр, corner - правый верхний угол рядом с заголовком
  const LAYOUT = {
    full: { x: 0, y: 0, w: 1080, h: 1920, op: 0, r: 0 },
    corner: { x: 728, y: 28, w: 316, h: 316, op: 14, r: 24 },  // раскладка 21.10: лицо в правом верхнем углу
  };
  LAYOUT.low = LAYOUT.corner;
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'expo.out' } });
  const E = 'expo.out', P = 'power3.out', IO = 'power3.inOut';
  const AU = { ...LAYOUT.full };
  const HOOK_END_DEFAULT = 0.95;  // хук и финальная карточка по 1 с

  // ---------- время рилса -> время полного ролика ----------
  function fullTime(t) {
    const S = SEG.segs;
    for (let i = 0; i < S.length; i++) {
      const [a, b, o] = S[i];
      if (t < o + (b - a) || i === S.length - 1) return Math.min(b - 1e-3, a + Math.max(0, t - o));
    }
  }

  // ---------- помощники таймлайна ----------
  const inn = (t, tg, o = {}) => tl.fromTo(tg, { opacity: 0, y: o.y ?? 26, x: o.x ?? 0, scale: o.s ?? 1 },
    { opacity: o.to ?? 1, y: 0, x: 0, scale: 1, duration: o.d ?? .75, ease: o.e ?? E, stagger: o.st ?? 0 }, t);
  const out = (t, tg, o = {}) => tl.fromTo(tg, { opacity: o.from ?? 1, y: 0 },
    { opacity: 0, y: o.y ?? -26, duration: o.d ?? .45, ease: 'power2.in', immediateRender: false, stagger: o.st ?? 0 }, t);
  const draw = (t, tg, d = .8, st = 0, ease = P) => tl.fromTo(tg, { attr: { 'stroke-dashoffset': 1.05 } },
    { attr: { 'stroke-dashoffset': 0 }, duration: d, ease, stagger: st }, t);
  const op = (t, tg, a, b, d = .6, ease = P) => tl.fromTo(tg, { opacity: a }, { opacity: b, duration: d, ease, immediateRender: false }, t);
  const words = s => $$(s + ' .w');
  const T = (phrase, after = 0) => {
    const v = KIT.wordAt(phrase, after);
    if (v == null) throw new Error('слово не найдено: ' + phrase + ' после ' + after);
    return v;
  };
  const authorTo = (t, mode, d = 1.1) => tl.to(AU, { ...LAYOUT[mode], duration: d, ease: IO }, t);
  const ringOn = (t, d = .5) => op(t, '#ringB', 0, 1, d);
  const ringOff = (t, d = .5) => op(t, '#ringB', 1, 0, d);
  function brackets(H, color = C.lime) {
    const s = H / 8, a = 0.375 * H;
    const L = `<svg class="brL" width="${a}" height="${H}" viewBox="0 0 ${a} ${H}" style="overflow:visible"><path fill="${color}" d="M0 0H${a}V${s}H${s}V${H - s}H${a}V${H}H0Z"/></svg>`;
    const Rr = `<svg class="brR" width="${a}" height="${H}" viewBox="0 0 ${a} ${H}" style="overflow:visible"><path fill="${color}" d="M${a} 0H0V${s}H${a - s}V${H - s}H0V${H}H${a}Z"/></svg>`;
    return { L, R: Rr, a, s };
  }
  function bracketsIn(t, left, right, dx = 40, colorTo = null) {
    tl.fromTo([left, right], { opacity: 0 }, { opacity: 1, duration: .3, ease: P }, t);
    tl.fromTo(left, { x: -dx }, { x: 0, duration: .8, ease: E }, t + .05);
    tl.fromTo(right, { x: dx }, { x: 0, duration: .8, ease: E }, t + .05);
    if (colorTo) tl.fromTo([left + ' path', right + ' path'], { attr: { fill: C.lilac } }, { attr: { fill: colorTo }, duration: .45, ease: P }, t + .45);
  }
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    parent && parent.appendChild(e); return e;
  };
  function iso(parent, x, y, w, h, D = 30, id) {
    const b = y + h;
    const front = `M${x} ${y}H${x + w}V${b}H${x}Z`;
    const top = `M${x} ${y}L${x + D} ${y - D}H${x + w + D}L${x + w} ${y}Z`;
    const side = `M${x + w} ${y}L${x + w + D} ${y - D}V${b - D}L${x + w} ${b}Z`;
    const g = el('g', id ? { id } : {}, parent);
    const gh = el('g', { class: 'gh', fill: 'none', stroke: 'rgba(245,243,237,.4)', 'stroke-width': 3, 'stroke-linejoin': 'round' }, g);
    [front, top, side].forEach(d => el('path', { d, class: 'dr', pathLength: 1 }, gh));
    const pf = el('g', { class: 'pf', stroke: 'rgba(245,243,237,.26)', 'stroke-width': 2, 'stroke-linejoin': 'round', opacity: 0 }, g);
    el('path', { d: front, fill: 'rgba(245,243,237,.045)' }, pf); el('path', { d: top, fill: 'rgba(245,243,237,.17)' }, pf); el('path', { d: side, fill: 'rgba(245,243,237,.08)' }, pf);
    const af = el('g', { class: 'af', opacity: 0 }, g);
    el('path', { d: front, fill: 'rgba(214,230,156,.08)' }, af); el('path', { d: top, fill: C.lime }, af); el('path', { d: side, fill: 'rgba(214,230,156,.38)' }, af);
    const as = el('g', { class: 'as', fill: 'none', stroke: C.lime, 'stroke-width': 3, 'stroke-linejoin': 'round' }, g);
    [front, top, side].forEach(d => el('path', { d, class: 'dr', pathLength: 1 }, as));
    return g;
  }
  const isoGhost = (t, g, d = .9) => draw(t, g.querySelectorAll('.gh path'), d, .05);
  function isoOn(t, g) { draw(t, g.querySelectorAll('.as path'), .9, .08); op(t + .35, g.querySelector('.af'), 0, 1, .7); op(t + .3, g.querySelector('.gh'), 1, 0, .5); }
  function isoOff(t, g) { op(t, [g.querySelector('.af'), g.querySelector('.as')], 1, 0, .6); op(t, g.querySelector('.pf'), 0, 1, .6); }
  function isoPlain(t, g) { op(t + .3, g.querySelector('.pf'), 0, 1, .6); op(t + .3, g.querySelector('.gh'), 1, 0, .5); }
  function icon(parent, x, y, size, innerSVG, color = C.lime, sw = 4) {
    const s = el('svg', { x, y, width: size, height: size, viewBox: '0 0 120 120', overflow: 'visible' }, parent);
    const g = el('g', { fill: 'none', 'stroke-width': sw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', style: 'stroke:' + color }, s);
    g.innerHTML = innerSVG;
    g.querySelectorAll('*').forEach(p => { p.setAttribute('pathLength', 1); p.classList.add('dr'); });
    return g;
  }
  function iconHTML(innerSVG, size = 56, color = C.lime, sw = 5) {
    const inner = innerSVG.replace(/<(path|circle|rect|line|polyline|ellipse)\b/g, '<$1 pathLength="1" class="dr"');
    return `<svg width="${size}" height="${size}" viewBox="0 0 120 120" style="overflow:visible"><g fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${inner}</g></svg>`;
  }

  // ---------- каркас, хук, финальная карточка ----------
  let hookEnd = HOOK_END_DEFAULT;
  function init(opts = {}) {
    hookEnd = opts.hookEnd ?? HOOK_END_DEFAULT;
    const content = $('#content');
    const stage = document.createElement('div'); stage.id = 'stage';
    stage.innerHTML = `<img id="bg" alt=""><div id="panel"><div id="glow"></div></div>
      <div id="author"><img id="au" alt=""><div class="ring" id="ringA"></div><div class="ring" id="ringB"></div><div id="atag">${BR.author || ''}</div></div>
      <div id="grad"></div><div id="hdr"></div><div id="hook"></div><div id="cap"></div>`;
    document.body.prepend(stage);
    const panel = $('#panel');
    panel.appendChild(content);
    const hdr = $('#hdr');
    hdr.innerHTML = `${LOGO}<i></i><span>${R.series || ''}</span>`;
    // хук: линия расходится из центра, строки приходят по очереди, снизу подъезжает подзаголовок
    const hook = $('#hook');
    hook.innerHTML = `<div id="hkLine"></div>` + R.hook.map((l, i) => `<div class="hk" id="hk${i}">${l}</div>`).join('') + `<div id="hkSub">${R.hook_sub}</div>`;
    const end = document.createElement('div'); end.id = 'end';
    // финальная карточка: версия для VK Клипов и Shorts (вопрос или "перешли") и для Instagram (?v=ig: только "сохрани")
    const IG = new URLSearchParams(location.search).get('v') === 'ig';
    const lab = IG ? R.ig_label : (R.cta_label || 'НАПИШИ В КОММЕНТАРИЯХ');
    // короткий предлог или союз не висит в конце строки: неразрывный пробел после него
    const nb = x => x.replace(/(^|\s)(в|и|а|с|к|у|о|на|не|за|по|до|от|из|для|без|что|кто|как)\s/gi, '$1$2\u00A0');
    const q = nb(IG ? R.ig_cta : R.cta);
    const sub = IG ? (BR.channel || '') : (BR.channel || '') + (BR.channel_more ? '<br>' + BR.channel_more : '');
    end.innerHTML = `<div id="enL">${lab}</div><div id="enQ">${q}</div>
      <div id="enLogo">${LOGO}</div><div id="enS">${sub}</div>`;
    panel.appendChild(end);
    tl.fromTo('#hkLine', { scaleX: 0 }, { scaleX: 1, duration: .5, ease: E }, 0);
    R.hook.forEach((l, i) => inn(.0 + i * .14, '#hk' + i, { y: 30, d: .45 }));
    inn(.0 + R.hook.length * .14 + .04, '#hkSub', { y: 20, d: .4 });
    out(hookEnd, ['#hk0', '#hk1', '#hk2', '#hkSub'].filter(s => R.hook.length > +s.slice(3) || s === '#hkSub'), { d: .4, st: .05 });
    tl.fromTo('#hkLine', { scaleX: 1, opacity: 1 }, { scaleX: 0, opacity: 0, duration: .45, ease: 'power2.in', immediateRender: false }, hookEnd);
    // переход: кадр во весь экран сжимается в окно правого верхнего угла, проступает панель
    const T0 = hookEnd + .1;
    // 21.10, вторая раскладка: окна нет, кадр хука гаснет, а сам автор уходит вырезкой в угол (graphite/figure.js)
    tl.fromTo('#author', { opacity: 1 }, { opacity: 0, duration: .6, ease: P, immediateRender: false }, T0 + .15);
    tl.fromTo('#panel', { opacity: 0 }, { opacity: 1, duration: .9, ease: P }, T0 + .15);
    tl.fromTo('#grad', { opacity: 1 }, { opacity: 0, duration: .6, ease: P, immediateRender: false }, T0);
    // финал: окно автора гаснет, вопрос для комментариев, логотип из размытия в резкость
    const sp = SEG.speech;
    tl.fromTo('#author', { opacity: 1 }, { opacity: 0, duration: .35, ease: 'power2.inOut', immediateRender: false }, sp - .15);
    inn(sp + .0, '#enL', { x: -20, y: 0, d: .4 });
    inn(sp + .05, '#enQ', { y: 30, d: .5 });
    tl.fromTo('#enLogo', { opacity: 0, filter: 'blur(14px)', scale: 1.06 }, { opacity: 1, filter: 'blur(0px)', scale: 1, duration: .55, ease: P }, sp + .2);
    inn(sp + .35, '#enS', { y: 12, d: .4 });
    if (opts.authorStart) Object.assign(AU, LAYOUT[opts.authorStart]);
  }
  // раскладка хука после загрузки шрифтов: строки вписываются в ширину 820
  let hookFitted = false;
  function fitHook() {
    if (hookFitted) return; hookFitted = true;
    let fs = 96;
    R.hook.forEach((l, i) => { const e = $('#hk' + i); e.style.fontSize = '96px'; fs = Math.min(fs, 96 * 820 / e.scrollWidth); });
    fs = Math.floor(fs);
    let y = 1010;
    R.hook.forEach((l, i) => { const e = $('#hk' + i); e.style.fontSize = fs + 'px'; e.style.top = y + 'px'; y += Math.round(fs * 1.06); });
    $('#hkSub').style.top = (y + 26) + 'px';
    // вопрос в финале: до 3 строк
    const q = $('#enQ'); let qs = 76; q.style.fontSize = qs + 'px';
    while (q.scrollHeight > 3 * qs * 1.06 + 4 && qs > 50) { qs -= 2; q.style.fontSize = qs + 'px'; }
  }

  // ---------- кадры ----------
  const frameCache = new Map();
  async function setFrame(img, dir, tf) {
    const idx = Math.max(1, Math.floor(tf * 30 + 1e-6) + 1);
    const name = KIT.pad(idx) + '.jpg';
    if (frameCache.get(img) === name) return;
    frameCache.set(img, name);
    img.src = dir + '/' + name;
    try { await img.decode(); } catch (e) { /* оставляем прошлый */ }
  }

  window.DURATION = SEG.duration;
  window.renderAt = async (t) => {
    fitHook();
    const tf = fullTime(Math.min(t, SEG.speech));
    await Promise.all([setFrame($('#au'), SEG.dirs.author_pb, tf), setFrame($('#bg'), SEG.dirs.bg, tf)]);
    tl.seek(t, false);
    const a = $('#author');
    a.style.left = AU.x + 'px'; a.style.top = AU.y + 'px'; a.style.width = AU.w + 'px'; a.style.height = AU.h + 'px';
    $('#au').style.objectPosition = `50% ${AU.op}%`;
    a.style.borderRadius = AU.r + 'px';
    // субтитры: плашка появляется и уходит за 0,12 с
    const cap = $('#cap');
    const c = SEG.cues.find(c => t >= c.s && t < c.e && c.s < SEG.speech);
    if (c) {
      if (cap.dataset.s !== String(c.s)) { cap.textContent = c.t; cap.dataset.s = c.s; }
      const k = Math.min(1, (t - c.s) / .12, (c.e - t) / .12);
      cap.style.opacity = k; cap.style.transform = `translateX(-50%) translateY(${(1 - k) * 8}px)`;
    } else cap.style.opacity = 0;
    if (G.onRender) G.onRender(t);
    $('#bg').style.transform = `scale(${1.08 + .04 * (t / SEG.duration)})`;
  };

  const G = { C, BR, tl, E, P, IO, init, inn, out, draw, op, words, T, authorTo, ringOn, ringOff, brackets, bracketsIn,
    el, iso, isoGhost, isoOn, isoOff, isoPlain, icon, iconHTML, LAYOUT, AU, $, $$, fullTime, get hookEnd() { return hookEnd; }, onRender: null };
  window.G = G;
})();
