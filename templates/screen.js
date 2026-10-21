// Запись экрана во весь кадр 1080x1920 (раскладка, утвержденная 21.10.2026). Подключать после reel2.js и G.init.
// Запись снята в вертикальном окне 540x960 css в 2x, поэтому кадр записи и есть кадр рилса, без кропа.
// SCREEN.run(scenes): сцена = {clip, t0, n, from, to, keys?: [[t, x, y, w], ...]}
//   clip - папка кадров seq/ (30 к/с, кадр 1 = момент t0 рилса), n - число кадров; from/to - когда сцена в кадре (наплыв 0,35 с);
//   keys - необязательный наезд в css-пикселях записи 540x960 (по умолчанию весь кадр [0, 0, 540]).
(function () {
  const VW = 540, VH = 960, FADE = .35;
  const ease = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  function crop(keys, t) {
    if (t <= keys[0][0]) return keys[0].slice(1);
    for (let i = 0; i < keys.length - 1; i++) {
      const [t1, ...a] = keys[i], [t2, ...b] = keys[i + 1];
      if (t <= t2) { const k = ease(clamp((t - t1) / (t2 - t1), 0, 1)); return a.map((v, j) => v + (b[j] - v) * k); }
    }
    return keys[keys.length - 1].slice(1);
  }
  function run(scenes) {
    const panel = document.querySelector('#panel');
    const win = document.createElement('div'); win.id = 'scr';
    Object.assign(win.style, {position: 'absolute', left: 0, top: 0, width: '1080px', height: '1920px', overflow: 'hidden', background: '#fff', opacity: 0});
    panel.appendChild(win);
    const imgs = scenes.map(() => { const im = document.createElement('img'); Object.assign(im.style, {position: 'absolute', left: 0, top: 0, opacity: 0, transformOrigin: '0 0'}); win.appendChild(im); return im; });
    const first = Math.min(...scenes.map(s => s.from)), last = Math.max(...scenes.map(s => s.to));
    const base = window.renderAt;
    window.renderAt = async (t) => {
      win.style.opacity = Math.min(ease(clamp((t - first) / .45, 0, 1)), 1 - ease(clamp((t - (last - .35)) / .35, 0, 1)));
      const jobs = [];
      scenes.forEach((s, i) => {
        const im = imgs[i], vis = Math.min(clamp((t - s.from) / FADE, 0, 1), clamp((s.to - t) / FADE, 0, 1));
        im.style.opacity = vis;
        if (vis <= 0) { im.style.display = 'none'; return; }
        im.style.display = 'block';
        const [x, y, w] = crop(s.keys && s.keys.length ? s.keys : [[0, 0, 0, VW]], t), k = 1080 / w;
        im.style.width = (VW * k) + 'px'; im.style.height = (VH * k) + 'px';
        im.style.transform = `translate(${-x * k}px, ${-y * k}px)`;
        const src = s.clip + '/' + KIT.pad(clamp(Math.floor((t - s.t0) * 30 + 1e-6) + 1, 1, s.n)) + '.jpg';
        if (im.dataset.src !== src) { im.dataset.src = src; im.src = src; jobs.push(im.decode().catch(() => {})); }
      });
      await Promise.all(jobs);
      await base(t);
    };
  }
  window.SCREEN = {run, VW, VH};
})();
