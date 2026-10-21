// Запись экрана продукта для рилса: кадры CDP screencast в вертикальном окне 540x960 css в 2x (= кадр 1080x1920),
// видимый курсор с кругом на клике, действия по времени рилса S.at(t).
// Сцена (пример: templates/scene_example.cjs): module.exports = {name, t0, dur, url, login?, prep?, run: async (S) => {...}}
// node rec.cjs scenes/<файл>.cjs  -> clips/<name>/frames/*.jpg + frames.json, потом resample.py
// Переменные: BASE_URL (адрес продукта, по умолчанию http://127.0.0.1:8080), HOST_MAP ("demo.local 127.0.0.1:8080" -
// продукт открывается под нейтральным именем, и в адресах на странице не виден локальный адрес), CHROME (путь к Chrome), OUT (папка clips).
const fs = require('fs'), path = require('path');
const {chromium} = require('playwright-core');
const B = process.env.BASE_URL || 'http://127.0.0.1:8080';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
// Окно как у телефона. Флаг Chrome --force-device-scale-factor=2 обязателен: deviceScaleFactor контекста
// без него не дает screencast в 2x, кадры приходят 540x960 и мылятся на 1080x1920.
const VW = 540, VH = 960;

const CURSOR = `(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="26" height="34" viewBox="0 0 26 34"><path d="M2 2 L2 26 L8.5 20 L13 31 L17.5 29 L13 18.5 L22 18.5 Z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position: 'fixed', left: '-100px', top: '-100px', zIndex: 2147483647, pointerEvents: 'none', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
    const r = document.createElement('div'); r.id = '__ring';
    Object.assign(r.style, {position: 'fixed', width: '36px', height: '36px', marginLeft: '-18px', marginTop: '-18px', borderRadius: '50%',
      background: 'rgba(82,130,255,.28)', border: '2px solid rgba(82,130,255,.7)', zIndex: 2147483646, pointerEvents: 'none', opacity: 0, transform: 'scale(.4)', transition: 'all .35s ease-out'});
    document.documentElement.append(r, c);
  };
  addEventListener('mousemove', e => { mk(); const c = document.getElementById('__cur'); c.style.left = (e.clientX - 2) + 'px'; c.style.top = (e.clientY - 2) + 'px'; }, true);
  addEventListener('mousedown', e => { mk(); const r = document.getElementById('__ring'); r.style.transition = 'none'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    r.style.opacity = 1; r.style.transform = 'scale(.4)'; requestAnimationFrame(() => { r.style.transition = 'all .45s ease-out'; r.style.opacity = 0; r.style.transform = 'scale(1.3)'; }); }, true);
  document.addEventListener('DOMContentLoaded', mk);
})();`;

(async () => {
  const sc = require(path.resolve(process.argv[2]));
  const out = path.join(process.env.OUT || 'clips', sc.name), fdir = path.join(out, 'frames');
  fs.rmSync(out, {recursive: true, force: true}); fs.mkdirSync(fdir, {recursive: true});
  const b = await chromium.launch({executablePath: CHROME, args: [...(process.env.HOST_MAP ? ['--host-resolver-rules=MAP ' + process.env.HOST_MAP] : []), '--force-device-scale-factor=2']});
  const ctx = await b.newContext({viewport: {width: VW, height: VH}, deviceScaleFactor: 2, locale: 'ru-RU'});
  await ctx.addInitScript(CURSOR);
  const p = await ctx.newPage();
  p.on('dialog', d => d.accept().catch(() => {}));  // уход со страницы с несохраненным: не спрашивать
  if (sc.login) await sc.login(p, B);   // вход в продукт до записи: логин и пароль демо-копии держать в сцене или переменных окружения
  let mx = VW - 60, my = VH - 120;
  const S = {
    p, B, t0: sc.t0,
    // плавное движение курсора к элементу или точке за ms
    async glide(target, ms = 500, dx = 0, dy = 0) {
      let x, y;
      if (typeof target === 'string' || target.boundingBox) {
        const loc = typeof target === 'string' ? p.locator(target).first() : target;
        const bb = await loc.boundingBox(); if (!bb) throw new Error('нет элемента ' + target);
        x = bb.x + bb.width / 2 + dx; y = bb.y + bb.height / 2 + dy;
      } else [x, y] = target;
      const n = Math.max(8, Math.round(ms / 16));
      for (let i = 1; i <= n; i++) {
        const k = i / n, e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        await p.mouse.move(mx + (x - mx) * e, my + (y - my) * e);
        await p.waitForTimeout(ms / n);
      }
      mx = x; my = y;
    },
    async click(target, ms = 450, dx = 0, dy = 0) { await S.glide(target, ms, dx, dy); await p.mouse.down(); await p.waitForTimeout(70); await p.mouse.up(); },
    async type(text, perChar = 70) { for (const ch of text) { await p.keyboard.type(ch); await p.waitForTimeout(perChar); } },
    at: null,
  };
  // подготовка до записи (страница, начальное положение курсора)
  if (sc.url) { await p.goto(sc.url.startsWith('file:') ? sc.url : B + sc.url); }
  if (sc.prep) await sc.prep(S);
  await p.waitForTimeout(sc.settle ?? 1200);
  await p.mouse.move(mx, my);
  const cdp = await ctx.newCDPSession(p);
  const frames = []; let n = 0, start = null;
  cdp.on('Page.screencastFrame', async (f) => {
    const ts = f.metadata.timestamp; if (start === null) start = ts;
    const name = String(++n).padStart(5, '0') + '.jpg';
    fs.writeFileSync(path.join(fdir, name), Buffer.from(f.data, 'base64'));
    frames.push([ts, name]);
    try { await cdp.send('Page.screencastFrameAck', {sessionId: f.sessionId}); } catch (e) {}
  });
  await cdp.send('Page.startScreencast', {format: 'jpeg', quality: 92, everyNthFrame: 1, maxWidth: VW * 2, maxHeight: VH * 2});
  const wall0 = Date.now() / 1000;
  S.at = async (t) => { const w = (t - sc.t0) - (Date.now() / 1000 - wall0); if (w > 0) await p.waitForTimeout(w * 1000); };
  // покадровая "дрожь" не нужна, но screencast шлет кадры только на изменения: держим страницу живой
  await sc.run(S);
  await S.at(sc.t0 + sc.dur + 0.3);
  await cdp.send('Page.stopScreencast');
  await p.waitForTimeout(300);
  fs.writeFileSync(path.join(out, 'frames.json'), JSON.stringify({t0: sc.t0, dur: sc.dur, wall0, start, frames}));
  console.log(sc.name, 'кадров', frames.length);
  await b.close();
})();
