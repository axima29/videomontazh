"""Слова дубля с временем исходника: по ним выбираются точные границы кусков в config.py.
python words.py <дубль> <от> <до> [--project ПАПКА]"""
import argparse, json, pathlib
ap = argparse.ArgumentParser(); ap.add_argument("take"); ap.add_argument("a", type=float); ap.add_argument("b", type=float); ap.add_argument("--project", default=".")
x = ap.parse_args()
W = [w for s in json.load(open(pathlib.Path(x.project) / f"src/tr_{x.take}.json")) for w in s["words"] if x.a <= w["s"] <= x.b]
print(" ".join(f"[{w['s']:.2f}]{w['w']}" for w in W))
