"""Страница рилса reels/<rid>/index.html: хук, запись экрана во весь кадр, автор вырезкой в углу, субтитры, финальная карточка.
python3 build_page.py <rid> [--project ПАПКА]

Берет из config.py: REELS[rid]["scenes"] - список (клип, от, до, ключи наезда); "figpos" - центр головы автора
по времени [[t, x, y], ...]; необязательные "intro_html" и "intro_js" - своя графика до записи экрана.
Клип - папка screen/clips/<клип> после rec.cjs и resample.py. Время - время рилса.
Ключи наезда [[t, x, y, w], ...] в css-пикселях записи 540x960; [] - весь кадр (по умолчанию так и надо).
Страница подключает шаблоны и скрипты прямо из папки скилла, копировать их в проект не нужно.
"""
import argparse, importlib.util, json, pathlib

SKILL = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("rid")
ap.add_argument("--project", default=".")
a = ap.parse_args()
P = pathlib.Path(a.project).resolve()
spec = importlib.util.spec_from_file_location("config", P / "config.py"); CFG = importlib.util.module_from_spec(spec); spec.loader.exec_module(CFG)
R = CFG.REELS[a.rid]
CLIPS = P / "screen" / "clips"
OUT = P / "reels" / a.rid


def take_spans():
    """с какого времени рилса какой дубль: у каждого дубля своя посадка головы в fig.js"""
    s = (OUT / "data.js").read_text()
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    takes = [p[0] for p in R["pieces"]]
    out = []
    for w in d["words"]:
        tk = takes[w["seg"]]
        if not out or out[-1][1] != tk:
            out.append([round(w["s"], 2), tk])
    return out


sc = []
for clip, t_from, t_to, *keys in R["scenes"]:
    m = json.load(open(CLIPS / clip / "frames.json"))
    n = len(list((CLIPS / clip / "seq").glob("*.jpg")))
    assert n, f"нет кадров {CLIPS / clip / 'seq'}: запусти resample.py"
    sc.append({"clip": (CLIPS / clip / "seq").as_uri(), "t0": m["t0"], "n": n, "from": t_from, "to": t_to, "keys": keys[0] if keys else []})
u = lambda p: (SKILL / p).as_uri()
html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{R['title']}</title>
<link rel="stylesheet" href="{u('templates/reel2.css')}"></head><body>
<div id="content">{R.get('intro_html', '')}</div>
<script src="data.js"></script><script src="fig.js"></script><script src="{u('scripts/kit.js')}"></script>
<script src="{u('scripts/node_modules/gsap/dist/gsap.min.js')}"></script><script src="{u('templates/reel2.js')}"></script>
<script src="{u('templates/screen.js')}"></script><script src="{u('templates/figure.js')}"></script>
<script>
G.init({{ hookEnd: 0.95 }});
{R.get('intro_js', '')}
SCREEN.run({json.dumps(sc, ensure_ascii=False)});
FIGURE.run({{spans: {json.dumps(take_spans())}, pos: {json.dumps(R.get('figpos', [[0, 870, 150]]))}}});
</script></body></html>
"""
(OUT / "index.html").write_text(html, encoding="utf-8")
print(a.rid, len(sc), "сцен", OUT / "index.html")
