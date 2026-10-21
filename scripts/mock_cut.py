"""Вырезка автора без фона для мокапов: RVM по кадрам reels/<rid>/author/ с разгоном на 12 предыдущих кадрах.
python mock_cut.py <rid> <t> [<t>...] [--project ПАПКА]  -> mock/cut/<rid>_<t>.png (RGBA 1080x1920)
Нужен prep.py --stage audio и --stage frames. Время t - время рилса."""
import argparse, pathlib, cv2, numpy as np, torch
ap = argparse.ArgumentParser(); ap.add_argument("rid"); ap.add_argument("ts", nargs="+", type=float); ap.add_argument("--project", default=".")
a = ap.parse_args()
P = pathlib.Path(a.project).resolve()
dev = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
rvm = torch.hub.load("PeterL1n/RobustVideoMatting", "resnet50", trust_repo=True).eval().to(dev)
src = P / "reels" / a.rid / "author"
(P / "mock/cut").mkdir(parents=True, exist_ok=True)
with torch.no_grad():
    for t in a.ts:
        j = int(round(t * 30)) + 1; rec = [None] * 4
        for jj in range(max(1, j - 12), j + 1):
            bgr = cv2.imread(str(src / f"{jj:05d}.jpg"))
            x = torch.from_numpy(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).to(dev).permute(2, 0, 1)[None].float() / 255
            _, pha, *rec = rvm(x, *rec, downsample_ratio=0.4)
        al = (pha[0, 0].clamp(0, 1) * 255).round().byte().cpu().numpy()
        cv2.imwrite(str(P / "mock/cut" / f"{a.rid}_{t:g}.png"), np.dstack([bgr, al]))
        ys, xs = np.nonzero(al > 128); print(a.rid, t, "верх головы", ys.min(), "x", int(xs[ys < ys.min() + 200].mean()))
