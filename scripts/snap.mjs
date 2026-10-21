// Стоп-кадры страницы анимации в PNG для проверки глазами до полного рендера.
// node snap.mjs --html page.html --times 2,8.5,20 --outdir snaps [--w 1920 --h 1080]
// Дополнительно кладет contact.png: все кадры одной сеткой с подписью времени.
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const HTML = path.resolve(arg('html'));
const OUT = path.resolve(arg('outdir', 'snaps'));
const W = +arg('w', 1920), H = +arg('h', 1080);
const times = arg('times').split(',').map(Number);
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new',
  args: ['--allow-file-access-from-files', '--disable-web-security', '--hide-scrollbars', '--force-color-profile=srgb'],
});
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
page.on('pageerror', e => console.error('[page error]', e.message));
page.on('console', m => { if (['error', 'warning'].includes(m.type())) console.error('[console]', m.text()); });
await page.goto('file://' + HTML, { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
const files = [];
for (const t of times) {
  await page.evaluate(async t => { await window.renderAt(t); }, t);
  const f = path.join(OUT, `t_${t.toFixed(2).padStart(6, '0')}.png`);
  await page.screenshot({ path: f });
  files.push([t, f]);
}
// сетка-превью
const cols = Math.min(3, files.length), rows = Math.ceil(files.length / cols), tw = 640, th = Math.round(tw * H / W);
const grid = `<html><body style="margin:0;background:#bdbcb7;display:grid;grid-template-columns:repeat(${cols},${tw}px);gap:8px;padding:8px">`
  + files.map(([t, f]) => `<div style="position:relative"><img src="file://${f}" style="width:${tw}px;height:${th}px;display:block">`
  + `<div style="position:absolute;left:6px;top:6px;background:#292929;color:#F5F3ED;font:14px monospace;padding:2px 6px">${t.toFixed(2)} c</div></div>`).join('')
  + '</body></html>';
const gp = path.join(OUT, '_grid.html'); fs.writeFileSync(gp, grid);
const g = await browser.newPage();
await g.setViewport({ width: cols * (tw + 8) + 8, height: rows * (th + 8) + 8 });
await g.goto('file://' + gp, { waitUntil: 'load' });
await g.screenshot({ path: path.join(OUT, 'contact.png') });
await browser.close();
console.log('готово', OUT, files.length, 'кадров + contact.png');
