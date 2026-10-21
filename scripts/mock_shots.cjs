// Снимки состояний продукта для мокапов: вертикальное окно 540x960 в 2x (кадр 1080x1920), курсор там, куда будем нажимать.
// node mock_shots.cjs <states.cjs> [имя...]  -> mock/st/<имя>.png (папка mock/st относительно текущей)
// states.cjs (пример: templates/states_example.cjs): module.exports = {login?: async (p, B) => {},
//   states: {имя: {url, run?: async (p) => {...}, cursor?: (p) => локатор}}}
// Переменные: BASE_URL, HOST_MAP, CHROME - как у rec.cjs.
const fs = require('fs'), path = require('path');
const {chromium} = require('playwright-core');
const B = process.env.BASE_URL || 'http://127.0.0.1:8080';
const CURSOR_SVG = '<svg width="26" height="34" viewBox="0 0 26 34"><path d="M2 2 L2 26 L8.5 20 L13 31 L17.5 29 L13 18.5 L22 18.5 Z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>';
(async () => {
  const S = require(path.resolve(process.argv[2]));
  fs.mkdirSync('mock/st', {recursive: true});
  const b = await chromium.launch({executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: [...(process.env.HOST_MAP ? ['--host-resolver-rules=MAP ' + process.env.HOST_MAP] : []), '--force-device-scale-factor=2']});
  const ctx = await b.newContext({viewport: {width: 540, height: 960}, deviceScaleFactor: 2, locale: 'ru-RU'});
  const p = await ctx.newPage(); p.on('dialog', d => d.accept().catch(() => {}));
  if (S.login) await S.login(p, B);
  const names = process.argv.slice(3).length ? process.argv.slice(3) : Object.keys(S.states);
  for (const n of names) {
    const s = S.states[n];
    await p.goto(/^(file|https?):/.test(s.url) ? s.url : B + s.url); await p.waitForTimeout(1800);
    try { if (s.run) await s.run(p); await p.waitForTimeout(900); } catch (e) { console.log(n, 'ошибка', e.message.split('\n')[0]); }
    if (s.cursor) try {
      const bb = await s.cursor(p).boundingBox({timeout: 1500});
      await p.evaluate(([x, y, svg]) => { const c = document.createElement('div'); c.innerHTML = svg;
        Object.assign(c.style, {position: 'fixed', left: x + 'px', top: y + 'px', zIndex: 2147483647, pointerEvents: 'none', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
        document.documentElement.append(c); }, [bb.x + Math.min(bb.width / 2, 40), bb.y + bb.height / 2, CURSOR_SVG]);
    } catch (e) { console.log(n, 'курсор', e.message.split('\n')[0]); }
    await p.screenshot({path: `mock/st/${n}.png`}); console.log(n);
  }
  await b.close();
})();
