// Покадровый рендер HTML-анимации в видео.
// Страница обязана объявить window.DURATION (сек) и async window.renderAt(t): рисует кадр для момента t
// и возвращает промис, который разрешается, когда картинки кадра декодированы.
// Время задает только renderAt, никаких таймеров: так движение детерминированное и без рывков.
//
// node capture.mjs --html page.html --out video.mp4 [--audio audio.wav] [--fps 30]
//                  [--from 0] [--to DURATION] [--workers 4] [--w 1920] [--h 1080] [--crf 16]
import puppeteer from 'puppeteer-core';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const HTML = path.resolve(arg('html'));
const OUT = path.resolve(arg('out'));
const AUDIO = arg('audio') ? path.resolve(arg('audio')) : null;
const FPS = +arg('fps', 30), W = +arg('w', 1920), H = +arg('h', 1080), CRF = arg('crf', '16');
const WORKERS = +arg('workers', Math.max(2, Math.min(6, os.cpus().length - 4)));
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: 'new', protocolTimeout: 600000,
  args: ['--allow-file-access-from-files', '--disable-web-security', '--hide-scrollbars',
         '--force-color-profile=srgb', '--font-render-hinting=none', `--window-size=${W},${H}`],
});

async function openPage() {
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('[page error]', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('[console]', m.text()); });
  await page.goto('file://' + HTML, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  return page;
}

const probe = await openPage();
const DURATION = await probe.evaluate(() => window.DURATION);
await probe.close();
if (!DURATION) throw new Error('window.DURATION не задан');
const from = +arg('from', 0), to = +arg('to', DURATION);
const f0 = Math.round(from * FPS), f1 = Math.round(to * FPS);
const total = f1 - f0;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cap-'));
const per = Math.ceil(total / WORKERS);
console.log(`кадров ${total}, потоков ${WORKERS}, ${W}x${H}@${FPS}`);

let done = 0; const t0 = Date.now();
async function worker(k) {
  const a = f0 + k * per, b = Math.min(f1, a + per);
  if (a >= b) return null;
  const part = path.join(tmp, `part_${String(k).padStart(2, '0')}.mp4`);
  const ff = spawn(FFMPEG, ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', CRF, '-pix_fmt', 'yuv420p', '-r', String(FPS), part],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  let page = await openPage();
  for (let f = a; f < b; f++) {
    // кадр обязан отрисоваться за 30 с; если страница зависла, открываем ее заново и рисуем тот же кадр
    let buf = null;
    for (let attempt = 0; attempt < 4 && !buf; attempt++) {
      try {
        await Promise.race([page.evaluate(async t => { await window.renderAt(t); }, f / FPS),
          new Promise((_, rej) => setTimeout(() => rej(new Error('кадр не отрисован за 30 с')), 30000))]);
        buf = await page.screenshot({ type: 'jpeg', quality: 95, optimizeForSpeed: false });
      } catch (e) {
        console.error(`[повтор] кадр ${f} (t=${(f / FPS).toFixed(3)}): ${e.message}`);
        try { await page.close(); } catch (_) { }
        page = await openPage();
      }
    }
    if (!buf) throw new Error('кадр ' + f + ' не отрисован после 4 попыток');
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    done++;
    if (done % 150 === 0) console.log(`  ${done}/${total}  ${((Date.now() - t0) / 1000).toFixed(0)} c`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await page.close();
  return part;
}
const parts = (await Promise.all([...Array(WORKERS).keys()].map(worker))).filter(Boolean).sort();
await browser.close();

const list = path.join(tmp, 'list.txt');
fs.writeFileSync(list, parts.map(p => `file '${p}'`).join('\n'));
const muxArgs = ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list];
if (AUDIO) muxArgs.push('-ss', String(from), '-t', String(to - from), '-i', AUDIO, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k', '-shortest');
muxArgs.push('-c:v', 'copy', '-movflags', '+faststart', OUT);
await new Promise((res, rej) => spawn(FFMPEG, muxArgs, { stdio: 'inherit' }).on('close', c => c ? rej(new Error('mux ' + c)) : res()));
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`готово ${OUT} за ${((Date.now() - t0) / 1000).toFixed(0)} c`);
