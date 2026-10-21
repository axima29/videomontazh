// Стоп-кадры готовой страницы рилса через renderAt(t): проверка до рендера и снимок хука для мокапов.
// node still.cjs <папка проекта> <rid> t1 t2 ...  -> mock/still/<rid>_<t>.png; при t = 0.5 еще mock/st/<rid>_hook.png
const fs = require('fs'), path = require('path');
const {chromium} = require('playwright-core');
(async () => {
  const [proj, rid, ...ts] = process.argv.slice(2);
  const P = path.resolve(proj), still = path.join(P, 'mock/still'), st = path.join(P, 'mock/st');
  fs.mkdirSync(still, {recursive: true}); fs.mkdirSync(st, {recursive: true});
  const b = await chromium.launch({executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args: ['--allow-file-access-from-files']});
  const p = await (await b.newContext({viewport: {width: 1080, height: 1920}})).newPage();
  p.on('pageerror', e => console.log('ошибка страницы', e.message));
  await p.goto('file://' + path.join(P, 'reels', rid, 'index.html')); await p.waitForFunction(() => window.renderAt); await p.waitForTimeout(800);
  for (const t of ts) {
    await p.evaluate(t => window.renderAt(+t), t);
    const f = path.join(still, `${rid}_${t}.png`); await p.screenshot({path: f});
    if (+t === 0.5) fs.copyFileSync(f, path.join(st, `${rid}_hook.png`));
    console.log(f, await p.evaluate(() => (document.querySelector('#cap') || {}).innerText || ''));
  }
  await b.close();
})();
