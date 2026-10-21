"""Мокапы кадров рилса до рендера: снимок продукта во весь кадр, живая фигура автора без окна (голова в зоне справа сверху),
субтитр этого момента внизу. Каждый кадр утверждает автор ролика, только потом запись сцен и рендер.

python3 mock_compose.py <rid> [--project ПАПКА]  -> mock/slides/<rid>_NN.png и лист mock/sheet_<rid>.png

Список кадров - MOCK[rid] в config.py: (название, время рилса, фон, центр головы [x, y] или None).
Фон: "hook" - снимок хука mock/st/<rid>_hook.png (делает still.cjs), иначе имя снимка mock/st/<фон>.png
(делает mock_shots.cjs или любой скриншот окна 540x960 в 2x). Фигура: mock/cut/<rid>_<t>.png (делает mock_cut.py).
Субтитр берется из reels/<rid>/data.js на этот момент.
"""
import argparse, importlib.util, json, os, pathlib, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser(); ap.add_argument("rid"); ap.add_argument("--project", default=".")
a = ap.parse_args()
P = pathlib.Path(a.project).resolve(); H = P / "mock"
spec = importlib.util.spec_from_file_location("config", P / "config.py"); CFG = importlib.util.module_from_spec(spec); spec.loader.exec_module(CFG)
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
HEAD = (870, 150)      # центр головы: середина зоны справа сверху
HW = 105               # ширина головы: голова с плечами помещается в зону около 280 px
SUB_Y = 1757           # центр субтитров по вертикали
s = (P / "reels" / a.rid / "data.js").read_text()
CUES = json.loads(s[s.index("{"):s.rindex("}") + 1])["cues"]
for d in ("slides", "html"):
    (H / d).mkdir(parents=True, exist_ok=True)


def caption(t):
    c = next((c for c in CUES if c["s"] <= t < c["e"]), None)
    return c["t"] if c else ""


def figure(t, head):
    f = H / "cut" / f"{a.rid}_{t:g}.png"
    al = np.array(Image.open(f))[:, :, 3]
    ys, xs = np.nonzero(al > 128); top = ys.min()
    hw = np.median([(al[y] > 128).sum() for y in range(top + 60, top + 160)])
    k = HW / hw
    cx = xs[ys < top + 200].mean(); cy = top + .75 * hw
    x, y = head[0] - cx * k, head[1] - cy * k
    fade = head[1] + 1.3 * HW   # бюст до груди, ниже растворяется
    return (f'<div class="fig" style="-webkit-mask-image:linear-gradient(#000 {fade:.0f}px,transparent {fade + 60:.0f}px)">'
            f'<img src="{f.as_uri()}" style="left:{x:.0f}px;top:{y:.0f}px;width:{1080 * k:.0f}px"></div>')


CSS = f"""@import url("https://fonts.googleapis.com/css2?family=Manrope:wght@400..800&display=block");
*{{margin:0;padding:0;box-sizing:border-box}} body{{width:1080px;height:1920px;overflow:hidden;position:relative;background:#1E1C24;font-family:Manrope,sans-serif}}
.bg{{position:absolute;left:0;top:0;width:1080px;height:1920px}}
.fig{{position:absolute;inset:0;filter:drop-shadow(0 10px 24px rgba(0,0,0,.35))}} .fig img{{position:absolute}}
.cap{{position:absolute;left:540px;top:{SUB_Y}px;transform:translate(-50%,-50%);max-width:900px;padding:14px 28px 16px;border-radius:20px;background:rgba(24,22,30,.88);
  font:600 50px/1.16 Manrope,sans-serif;color:#F5F3ED;text-align:center;white-space:pre;letter-spacing:-.01em}}"""

outs = []
for i, (name, t, bg, head) in enumerate(CFG.MOCK[a.rid], 1):
    png = H / "slides" / f"{a.rid}_{i:02d}.png"; outs.append((name, png))
    if bg == "hook":
        Image.open(H / "st" / f"{a.rid}_hook.png").convert("RGB").save(png); continue
    body = f'<img class="bg" src="{(H / "st" / (bg + ".png")).as_uri()}">'
    if head:
        body += figure(t, head)
    cap = caption(t)
    if cap:
        body += f'<div class="cap">{cap}</div>'
    hp = H / "html" / f"{a.rid}_{i:02d}.html"
    hp.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>', encoding="utf-8")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files", f"--screenshot={png}",
                    "--window-size=1080,1920", "--virtual-time-budget=3000", hp.as_uri()], capture_output=True, check=True)
# лист: 5 в ряд, подпись номером и названием кадра
# шрифт подписей с кириллицей: из конфига или первый найденный системный (шрифт Pillow по умолчанию кириллицу не рисует)
font = next((f for f in [getattr(CFG, "MOCK_FONT", None), "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                         "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"] if f and os.path.exists(f)), None)
fnt = ImageFont.truetype(font, 30) if font else ImageFont.load_default(size=30)
cols, w, h = 5, 432, 768; rows = (len(outs) + cols - 1) // cols
sh = Image.new("RGB", (cols * (w + 24) + 24, rows * (h + 80) + 24), "#ECEAE4"); d = ImageDraw.Draw(sh)
for j, (name, png) in enumerate(outs):
    x, y = 24 + (j % cols) * (w + 24), 24 + (j // cols) * (h + 80)
    d.text((x, y), f"{j + 1}. {name}", font=fnt, fill="#292929"); sh.paste(Image.open(png).convert("RGB").resize((w, h)), (x, y + 48))
sh.save(H / f"sheet_{a.rid}.png"); print(a.rid, len(outs), "кадров", H / f"sheet_{a.rid}.png")
