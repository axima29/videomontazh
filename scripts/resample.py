"""Кадры записи экрана -> ровно 30 к/с на время сцены (кадр держится до следующего).
python3 resample.py <сцена>... [--clips ПАПКА]   (по умолчанию ./clips): clips/<сцена>/frames.json -> clips/<сцена>/seq/00001.jpg..."""
import json, os, pathlib, sys
args = sys.argv[1:]
H = pathlib.Path("clips")
if "--clips" in args:
    i = args.index("--clips"); H = pathlib.Path(args[i + 1]); del args[i:i + 2]
for name in args:
    d = H / name; m = json.load(open(d / "frames.json"))
    fr = [(ts - m["wall0"], f) for ts, f in m["frames"]]
    seq = d / "seq"; seq.mkdir(exist_ok=True)
    for f in seq.glob("*.jpg"): f.unlink()
    n = int(round((m["dur"] + 0.3) * 30)); k = 0
    for i in range(n):
        t = i / 30
        while k + 1 < len(fr) and fr[k + 1][0] <= t: k += 1
        os.link(d / "frames" / fr[k][1], seq / f"{i + 1:05d}.jpg")
    print(name, n, "кадров, первый кадр записи на", round(fr[0][0], 2), "с")
