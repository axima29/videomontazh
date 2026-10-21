// Автор живой вырезкой без окна (раскладка, утвержденная 21.10.2026): после хука фигура из полного кадра
// уменьшается и уходит головой в зеленую зону справа сверху, ниже плеч растворяется. Подключать после screen.js и fig.js (его пишет prep.py --stage cut).
// FIGURE.run({spans: [[t, дубль], ...], pos: [[t, x, y], ...]}) - pos: центр головы в кадре, между ключами фигура плавно переезжает.
(function () {
  const HEAD = [870, 150], HW = 105, BUST = 1.3, FADE = 60, T_IN = .75;
  const ease = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  function at(keys, t) {
    if (t <= keys[0][0]) return keys[0].slice(1);
    for (let i = 0; i < keys.length - 1; i++) {
      const [t1, ...a] = keys[i], [t2, ...b] = keys[i + 1];
      if (t <= t2) { const k = ease(clamp((t - t1) / (t2 - t1), 0, 1)); return a.map((v, j) => v + (b[j] - v) * k); }
    }
    return keys[keys.length - 1].slice(1);
  }

  function run(o) {
    const spans = o.spans, pos = o.pos || [[0, ...HEAD]];
    const wrap = document.createElement('div'); wrap.id = 'fig';
    Object.assign(wrap.style, {position: 'absolute', left: 0, top: 0, width: '1080px', height: '1920px', zIndex: 4, pointerEvents: 'none',
      filter: 'drop-shadow(0 10px 24px rgba(0,0,0,.35))', opacity: 0});
    const img = document.createElement('img');
    Object.assign(img.style, {position: 'absolute', left: 0, top: 0, width: '1080px', height: '1920px', transformOrigin: '0 0'});
    wrap.appendChild(img);
    document.getElementById('stage').insertBefore(wrap, document.getElementById('grad'));
    const dir = SEG.dirs.author_cut;
    const base = window.renderAt;
    window.renderAt = async (t) => {
      const idx = Math.max(1, Math.floor(G.fullTime(Math.min(t, SEG.speech)) * 30 + 1e-6) + 1);
      const src = dir + '/' + KIT.pad(idx) + '.webp';
      if (img.dataset.src !== src) { img.dataset.src = src; img.src = src; try { await img.decode(); } catch (e) {} }
      await base(t);
      let tk = spans[0][1]; for (const [a, x] of spans) if (t >= a - .05) tk = x;
      const [cx, top, hw] = FIG[tk], k = HW / hw, cy = top + .75 * hw;
      const [hx, hy] = at(pos, t);
      const T0 = G.hookEnd + .1, e = ease(clamp((t - T0) / T_IN, 0, 1));
      img.style.transform = `translate(${(hx - cx * k) * e}px, ${(hy - cy * k) * e}px) scale(${1 + (k - 1) * e})`;
      const fade = 1920 + (hy + BUST * HW - 1920) * e;
      wrap.style.webkitMaskImage = `linear-gradient(#000 ${fade}px, transparent ${fade + FADE}px)`;
      wrap.style.opacity = t < T0 ? 0 : clamp((SEG.speech - .15 + .35 - t) / .35, 0, 1);
    };
  }
  window.FIGURE = {run, HEAD, HW};
})();
