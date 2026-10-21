// Общие помощники страницы рилса. Подключать после data.js и gsap.min.js.
// SEG (из data.js): fps, frames, duration, words [{w,s,e}], cues, dirs {author_pb, author_cut, bg}.
(function () {
  const pad = n => String(n).padStart(5, '0');
  const cache = new Map();

  // Кадр видео для момента t. Меняет src только при смене кадра и ждет декодирования.
  async function setFrame(img, dir, t) {
    const idx = Math.min(SEG.frames, Math.max(1, Math.floor(t * SEG.fps + 1e-6) + 1));
    const src = `${dir}/${pad(idx)}.jpg`;
    if (cache.get(img) === src) return;
    cache.set(img, src);
    img.src = src;
    try { await img.decode(); } catch (e) { /* кадр за пределами - оставляем прошлый */ }
  }

  // CSS-анимации (@keyframes) переводятся в ручной режим: время задаем сами.
  function seekCSS(t) {
    for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  }

  // Время начала первого вхождения слова (или фразы из нескольких слов) после момента after.
  function wordAt(phrase, after = 0) {
    const want = phrase.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, '').split(/\s+/).filter(Boolean);
    const norm = s => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
    const W = SEG.words;
    for (let i = 0; i < W.length; i++) {
      if (W[i].s < after) continue;
      let ok = true;
      for (let j = 0; j < want.length; j++) { if (!W[i + j] || norm(W[i + j].w) !== want[j]) { ok = false; break; } }
      if (ok) return W[i].s;
    }
    console.error('слово не найдено: ' + phrase);
    return null;
  }

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const prog = (t, start, dur) => clamp((t - start) / dur);
  const ease = {
    outCubic: x => 1 - Math.pow(1 - x, 3),
    inOutCubic: x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
    outExpo: x => x === 1 ? 1 : 1 - Math.pow(2, -10 * x),
    outBack: (x, s = 1.2) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
  };

  window.KIT = { setFrame, seekCSS, wordAt, clamp, prog, ease, pad };
})();
