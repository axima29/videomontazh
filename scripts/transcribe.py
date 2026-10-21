"""Расшифровка дубля с временем каждого слова (faster-whisper large-v3-turbo).
python transcribe.py <дубль> --project ПАПКА
Берет путь исходника из TAKES в config.py, пишет src/a16_<дубль>.wav (16 кГц моно, по нему считается громкость для реза)
и src/tr_<дубль>.json: [{start, end, text, words: [{w, s, e, p}]}]. Печатает фразы с временем: по ним выбираются куски.
"""
import argparse, importlib.util, json, os, pathlib, shutil, subprocess, time
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("take")
ap.add_argument("--project", default=".")
a = ap.parse_args()
P = pathlib.Path(a.project).resolve()
spec = importlib.util.spec_from_file_location("config", P / "config.py"); CFG = importlib.util.module_from_spec(spec); spec.loader.exec_module(CFG)
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
(P / "src").mkdir(exist_ok=True)
wav, out = P / f"src/a16_{a.take}.wav", P / f"src/tr_{a.take}.json"
subprocess.run([FF, "-v", "error", "-y", "-i", CFG.TAKES[a.take], "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav)], check=True)
t0 = time.time()
m = WhisperModel("mobiuslabsgmbh/faster-whisper-large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 8)
segs, info = m.transcribe(str(wav), language="ru", word_timestamps=True, vad_filter=True,
                          vad_parameters={"min_silence_duration_ms": 400}, beam_size=5,
                          condition_on_previous_text=False, hotwords=getattr(CFG, "HOTWORDS", None))
res = []
for s in segs:
    res.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)} for w in (s.words or [])]})
    print(f"{s.start:7.1f} {s.text.strip()}", flush=True)
json.dump(res, open(out, "w"), ensure_ascii=False, indent=0)
print("готово", out, round(time.time() - t0), "c", flush=True)
