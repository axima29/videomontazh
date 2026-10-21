"""Подготовка рилса из записи на камеру: куски речи, чистый звук, кадры автора, вырезка автора, слова и субтитры.

python prep.py <rid> [--project ПАПКА] [--stage all|audio|frames|cut|data]

Папка проекта (по умолчанию текущая) содержит config.py (образец: config.example.py в корне скилла)
и расшифровки дублей src/tr_<дубль>.json, src/a16_<дубль>.wav (их делает transcribe.py).

Что получается в reels/<rid>/:
  edl.json      какие куски исходника вошли (время исходника)
  audio.wav     речь: шумодав DeepFilterNet (предел 30 дБ), паузы сжаты до 0,28 с, ускорение 1,08,
                -14 LUFS, в конце тишина TAIL на финальную карточку
  author/       кадр автора 1080x1920, 30 к/с, кадр к кадру со звуком
  bg/           фон 1080x1920: кадр автора размыт до пятен и затемнен
  author_cut/   автор без фона (RobustVideoMatting), webp с прозрачностью, и fig.js с положением головы по дублям
  data.js       window.SEG для страницы рилса: слова, субтитры, хук, призыв, папки кадров
  speech.txt    текст субтитров и повторное распознавание смонтированного звука (сверка швов)

Рез: границы кусков уточняются по самой тихой точке между словами (окно RMS 10 мс),
время на стыке принадлежит следующему куску. Паузы внутри куска (тише NOISE_DB дольше 0,3 с) сжимаются до 0,28 с.
"""
import argparse, importlib.util, json, os, pathlib, re, shutil, subprocess, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from scipy.io import wavfile

ap = argparse.ArgumentParser()
ap.add_argument("rid")
ap.add_argument("--project", default=".")
ap.add_argument("--stage", default="all")
args = ap.parse_args()

WORK = pathlib.Path(args.project).resolve()
_spec = importlib.util.spec_from_file_location("config", WORK / "config.py")
CFG = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(CFG)
REELS, SERIES, TAKES = CFG.REELS, CFG.SERIES, CFG.TAKES
CROP_Y, ZOOM = getattr(CFG, "CROP_Y", {}), getattr(CFG, "ZOOM", {})
R = REELS[args.rid]

FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FPS, SP, TAIL = 30, getattr(CFG, "SPEED", 1.08), getattr(CFG, "TAIL", 1.0)
NOISE_DB, MIN_SIL, KEEP_SIL = -45.0, 0.30, 0.28
# кадр исходника после поворота и уменьшения (iPhone 4K вертикально: 1200x2134), из него окно 1080x1920 без масштаба
SRC_W, SRC_H = getattr(CFG, "SRC_FRAME", (1200, 2134))
ROTATE = getattr(CFG, "ROTATE", "clock")       # "clock" для вертикального видео iPhone, снятого с метаданными поворота; None - не поворачивать
OW, OH = 1080, 1920
SRC = None

OUT = WORK / "reels" / args.rid
TMP = OUT / "_tmp"
for d in ("author", "bg", "_tmp"):
    (OUT / d).mkdir(parents=True, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-2000:])
    return r


def log(*a):
    print(time.strftime("%H:%M:%S"), args.rid, *a, flush=True)


# ---------- рез по словам ----------
_TK = {}


def use(take):
    """текущий дубль: слова, громкость и путь исходника (в одном рилсе может быть несколько дублей)"""
    global W, sr16, RMS, SRC
    if take not in _TK:
        w_ = [w for s in json.load(open(WORK / f"src/tr_{take}.json")) for w in s["words"]]
        sr_, a_ = wavfile.read(WORK / f"src/a16_{take}.wav")
        a_ = a_.astype(np.float32) / 32768
        win = int(0.01 * sr_)
        _TK[take] = (w_, sr_, np.sqrt(np.convolve(a_ ** 2, np.ones(win) / win, mode="same") + 1e-12))
    W, sr16, RMS = _TK[take]
    SRC = TAKES[take]


def resolve(piece):
    """(дубль, начало первого слова, начало последнего слова[, флаги]) -> (a, b, флаги) по словам дубля"""
    use(piece[0])
    i = min(range(len(W)), key=lambda k: abs(W[k]["s"] - piece[1]))
    j = min(range(len(W)), key=lambda k: abs(W[k]["s"] - piece[2]))
    fl = piece[3] if len(piece) > 3 else ""
    return (piece[1] if "a" in fl else W[i]["s"]), (piece[2] if "b" in fl else W[j]["e"]), fl


PIECES = [resolve(pc) for pc in R["pieces"]]
TAKE_OF = [pc[0] for pc in R["pieces"]]


def quiet(a, b):
    ia, ib = int(a * sr16), max(int(a * sr16) + 1, int(b * sr16))
    return (ia + int(np.argmin(RMS[ia:ib]))) / sr16


def refine_start(a):
    """тишина перед словом: в паузе не дальше 0,3 с от слова; если слова идут вплотную - окно +-0,12 с
    (whisper ставит начало слова неточно, иногда раньше хвоста предыдущего)"""
    i = min(range(len(W)), key=lambda k: abs(W[k]["s"] - a))
    s = W[i]["s"]; pe = W[i - 1]["e"] if i else s - 0.5
    return quiet(max(pe, s - 0.30), s + 0.02) if s - pe > 0.06 else quiet(s - 0.12, s + 0.12)


def refine_end(b):
    j = min(range(len(W)), key=lambda k: abs(W[k]["e"] - b))
    e = W[j]["e"]; ns = W[j + 1]["s"] if j + 1 < len(W) else e + 0.5
    return quiet(e - 0.02, min(ns, e + 0.30)) if ns - e > 0.06 else quiet(e - 0.12, e + 0.12)


def loud_edges(a, b):
    """первое и последнее громкое окно 10 мс внутри [a, b]: по ним подрезаем тишину на краях куска"""
    step = int(0.01 * sr16)
    db = 20 * np.log10(RMS[int(a * sr16):int(b * sr16):step] + 1e-9)
    idx = np.where(db >= NOISE_DB)[0]
    if not len(idx):
        return a, b
    return a + idx[0] * 0.01, a + (idx[-1] + 1) * 0.01


def silences(a, b):
    """паузы внутри [a, b]: окна 10 мс тише NOISE_DB подряд дольше MIN_SIL, время исходника"""
    step = int(0.01 * sr16)
    db = 20 * np.log10(RMS[int(a * sr16):int(b * sr16):step] + 1e-9)
    quietw = db < NOISE_DB
    res, k = [], 0
    while k < len(quietw):
        if quietw[k]:
            m = k
            while m < len(quietw) and quietw[m]:
                m += 1
            if (m - k) * 0.01 >= MIN_SIL:
                res.append((a + k * 0.01, a + m * 0.01))
            k = m
        else:
            k += 1
    return res


def build_keep():
    keep = []
    for pi, piece in enumerate(PIECES):
        use(TAKE_OF[pi])
        a, b, exact = piece          # "a", "b": граница ровно по указанному времени; "c": фраза продолжается
        ra = a if "a" in exact else refine_start(a)
        rb = b if "b" in exact else refine_end(b)
        la, lb = loud_edges(ra, rb)
        ra, rb = max(ra, la - KEEP_SIL / 2), min(rb, lb + KEEP_SIL / 2)    # на стыке не больше 0,14 с тишины с каждой стороны
        loc, cur, half = [], ra, KEEP_SIL / 2
        for s, e in silences(ra, rb):
            cs, ce = s + half, e - half
            if ce - cs > 0.05:
                if cs > cur + 0.05:
                    loc.append([cur, cs])
                cur = ce
        if cur < rb - 0.03:
            loc.append([cur, rb])
        for xa, xb in R.get("skip", []):                    # оговорки и мычания внутри куска, время исходника
            nk = []
            for ka, kb in loc:
                if xb <= ka or xa >= kb:
                    nk.append([ka, kb]); continue
                if xa > ka: nk.append([ka, xa])
                if xb < kb: nk.append([xb, kb])
            loc = nk
        keep += [[round(x, 4), round(y, 4), pi] for x, y in loc if y - x >= 2 / FPS]
    return keep


def stage_audio():
    t0 = time.time()
    keep = build_keep()
    cum = [0.0]
    for a, b, _ in keep:
        cum.append(cum[-1] + (b - a))
    json.dump({"src": TAKES, "takes": TAKE_OF, "speed": SP, "fps": FPS, "keep": keep}, open(OUT / "edl.json", "w"), ensure_ascii=False, indent=1)
    # проверка швов: громкость исходника в точке реза. Громче -50 дБ - рез по звуку, слушать руками
    for k, (a, b, pi) in enumerate(keep):
        use(TAKE_OF[pi])
        for t, side in ((a, "начало"), (b, "конец")):
            db = 20 * np.log10(RMS[int(t * sr16)] + 1e-9)
            if db > -50:
                log(f"  шов {side} интервала {k} (кусок {pi}) {t:.3f}: {db:.0f} дБ - проверить")
    raw = sum(pc[1] - pc[0] for pc in PIECES)
    log(f"куски {raw:.1f} c, после пауз {cum[-1]:.1f} c, после ускорения {cum[-1] / SP:.1f} c, интервалов {len(keep)}")
    import torch
    from df.enhance import enhance, init_df
    model, st, _ = init_df()
    sr = 48000
    fade = int(0.010 * sr)
    parts = []
    for pi, pc in enumerate(PIECES):
        use(TAKE_OF[pi])
        ks = [k for k in keep if k[2] == pi]
        if not ks:
            continue
        pa = max(0.0, ks[0][0] - 0.6); pb = ks[-1][1] + 0.6          # шумодав с запасом: края без артефактов
        run([FF, "-v", "error", "-y", "-ss", f"{pa:.4f}", "-to", f"{pb:.4f}", "-i", SRC, "-map", "0:a:0",
             "-ac", "1", "-ar", str(sr), str(TMP / "raw.wav")])
        _, x = wavfile.read(TMP / "raw.wav")
        y = enhance(model, st, torch.from_numpy(x.astype(np.float32) / 32768.0)[None], atten_lim_db=30)[0].numpy()
        for ka, kb, _ in ks:
            seg = y[int((ka - pa) * sr):int((kb - pa) * sr)].copy()
            n = min(fade, len(seg) // 2)
            if n:
                r = np.linspace(0, 1, n, dtype=np.float32); seg[:n] *= r; seg[-n:] *= r[::-1]
            parts.append(seg)
    wavfile.write(TMP / "cut_df.wav", sr, (np.clip(np.concatenate(parts), -1, 1) * 32767).astype(np.int16))
    run([FF, "-v", "error", "-y", "-i", str(TMP / "cut_df.wav"), "-af",
         "highpass=f=70,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=200:makeup=2,"
         "dynaudnorm=f=250:g=13:p=0.9:m=6,loudnorm=I=-15:TP=-1.5:LRA=7,"
         f"atempo={SP}", "-ar", "48000", "-ac", "2", str(TMP / "speech.wav")])
    # громкость до -14 LUFS в два шага: замер, усиление, лимитер
    r = run([FF, "-hide_banner", "-nostats", "-i", str(TMP / "speech.wav"), "-af", "ebur128=peak=true", "-f", "null", "-"])
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    gain = -14.0 - I
    run([FF, "-v", "error", "-y", "-i", str(TMP / "speech.wav"), "-af",
         f"volume={gain:.2f}dB,alimiter=limit=0.89:attack=5:release=50:level=false,apad=pad_dur={TAIL}",
         "-ar", "48000", "-ac", "2", str(OUT / "audio.wav")])
    sr2, z = wavfile.read(OUT / "audio.wav")
    log(f"звук: {len(z) / sr2 - TAIL:.2f} c речи + {TAIL} c карточка, было {I:.1f} LUFS, усиление {gain:+.1f} дБ, {time.time() - t0:.0f} c")


def out_map():
    """для каждого кадра рилса: (кусок, время исходника, интервал)"""
    keep = json.load(open(OUT / "edl.json"))["keep"]
    cum = [0.0]
    for a, b, _ in keep:
        cum.append(cum[-1] + (b - a))
    sr2, z = wavfile.read(OUT / "audio.wav")
    frames = int(round(len(z) / sr2 * FPS))
    sp_frames = int(round(cum[-1] / SP * FPS))
    res, k = [], 0
    for j in range(frames):
        jj = min(j, sp_frames - 1)                     # на финальной карточке держим последний кадр речи
        tau = jj / FPS * SP
        while k < len(keep) - 1 and tau >= cum[k + 1]:
            k += 1
        res.append((keep[k][2], keep[k][0] + (tau - cum[k]), k))
    return res, keep, frames


def stage_frames():
    import cv2
    t0 = time.time()
    fmap, keep, frames = out_map()
    need = {}
    for j, (pi, src_t, _) in enumerate(fmap):
        need.setdefault(pi, []).append((j, src_t))
    cw, ch = OW, OH
    img = None
    for pi, lst in sorted(need.items()):
        use(TAKE_OF[pi])
        cy = CROP_Y.get(TAKE_OF[pi], (SRC_H - OH) // 2)
        A = min(t for _, t in lst) - 0.1; B = max(t for _, t in lst) + 0.2
        z, fx = ZOOM.get(TAKE_OF[pi], (1.0, SRC_W / 2))      # крупнее, если по краю кадра видно личное
        HW, HH = int(round(SRC_W * z / 2)) * 2, int(round(SRC_H * z / 2)) * 2
        cx = int(min(max(fx * z - cw / 2, 0), HW - cw))
        if sys.platform == "darwin":       # аппаратное декодирование и масштаб на Mac
            dec = ["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"]
            vf = (f"scale_vt=w={HH}:h={HW}," if ROTATE else f"scale_vt=w={HW}:h={HH},") + "hwdownload,format=nv12,"
        else:
            dec, vf = [], (f"scale={HH}:{HW}," if ROTATE else f"scale={HW}:{HH},")
        vf += (f"transpose={ROTATE}," if ROTATE else "") + f"fps={FPS}"
        cmd = [FF, "-v", "error", "-noautorotate", *dec, "-ss", f"{A:.4f}", "-to", f"{B:.4f}", "-i", SRC,
               "-vf", vf, "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=HW * HH * 3 * 4)
        want = {}
        for j, src_t in lst:
            want.setdefault(max(0, int(round((src_t - A) * FPS))), []).append(j)
        last = max(want); i = 0
        while i <= last:
            buf = proc.stdout.read(HW * HH * 3)
            if len(buf) < HW * HH * 3:
                break
            if i in want:
                fr = np.frombuffer(buf, np.uint8).reshape(HH, HW, 3)
                y0 = int(min(max(cy, 0), HH - ch))
                img = np.ascontiguousarray(fr[y0:y0 + ch, cx:cx + cw])
                for j in want[i]:
                    cv2.imwrite(str(OUT / "author" / f"{j + 1:05d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 93])
            i += 1
        proc.kill(); proc.wait()
        for idx, js in want.items():                 # хвост куска короче, чем ждали: держим последний кадр
            if idx >= i and img is not None:
                for j in js:
                    cv2.imwrite(str(OUT / "author" / f"{j + 1:05d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 93])
    # фон 1080x1920: кадр автора размыт до пятен и затемнен
    run([FF, "-v", "error", "-y", "-framerate", str(FPS), "-i", str(OUT / "author/%05d.jpg"),
         "-vf", "scale=270:480,gblur=sigma=10,eq=brightness=-0.10:saturation=0.8:contrast=0.95,"
                "vignette=PI/4,scale=1080:1920:flags=bicubic", "-q:v", "3", str(OUT / "bg/%05d.jpg")])
    log(f"кадры и фон: {frames}, {time.time() - t0:.0f} c")


def stage_cut():
    """Автор без фона: author_cut/NNNNN.webp RGBA и fig.js с головой по дублям для templates/figure.js.
    В кадре показывается только бюст (маска ниже плеч), поэтому то, что ниже стола, в рилс не попадает."""
    import cv2, torch
    t0 = time.time()
    fmap, keep, frames = out_map()
    resets = {0} | {j for j in range(1, frames) if fmap[j][0] != fmap[j - 1][0]}   # смена куска: память сети заново
    dev = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    rvm = torch.hub.load("PeterL1n/RobustVideoMatting", "resnet50", trust_repo=True).eval().to(dev)
    (OUT / "author_cut").mkdir(exist_ok=True)
    names = [f"{j + 1:05d}.jpg" for j in range(frames)]
    tens = lambda b: torch.from_numpy(cv2.cvtColor(b, cv2.COLOR_BGR2RGB)).to(dev).permute(2, 0, 1)[None].float() / 255
    heads = {}   # дубль -> [(центр x, верх головы, ширина головы)] по каждому 15-му кадру
    rec = [None] * 4
    with torch.no_grad():
        for j, name in enumerate(names):
            if j in resets:
                rec = [None] * 4
                for jj in range(j, min(frames, j + 8)):          # разгон памяти сети на первых кадрах куска
                    _, _, *rec = rvm(tens(cv2.imread(str(OUT / "author" / names[jj]))), *rec, downsample_ratio=0.4)
            bgr = cv2.imread(str(OUT / "author" / name))
            _, pha, *rec = rvm(tens(bgr), *rec, downsample_ratio=0.4)
            a = (pha[0, 0].clamp(0, 1) * 255).round().byte().cpu().numpy()
            cv2.imwrite(str(OUT / "author_cut" / name.replace(".jpg", ".webp")), np.dstack([bgr, a]), [cv2.IMWRITE_WEBP_QUALITY, 88])
            if j % 15 == 0:
                ys, xs = np.nonzero(a > 128)
                if len(ys):
                    top = int(ys.min())
                    hw = float(np.median([(a[y] > 128).sum() for y in range(top + 60, min(a.shape[0], top + 160))]))
                    heads.setdefault(TAKE_OF[fmap[j][0]], []).append((float(xs[ys < top + 200].mean()), top, hw))
    fig = {tk: [round(float(np.median([h[k] for h in v])), 1) for k in range(3)] for tk, v in heads.items()}
    (OUT / "fig.js").write_text("window.FIG = " + json.dumps(fig) + ";  // дубль: [центр головы x, верх головы y, ширина головы] в кадре 1080x1920\n")
    log(f"вырезка {frames} кадров, головы {fig}, {time.time() - t0:.0f} c")


# ---------- слова и субтитры ----------
def cues_for(toks_in):
    """до 26 знаков в строке, до 2 строк; плашка кончается на знаке препинания, если можно;
    короткий предлог не остается в конце строки"""
    toks = [dict(t) for t in toks_in]
    if toks:
        toks[-1]["w"] = re.sub(r"[,:]$", "", toks[-1]["w"])
        if not re.search(r"[.?!]$", toks[-1]["w"]):
            toks[-1]["w"] += "."
    for i in range(1, len(toks)):
        if re.search(r"[.?!]$", toks[i - 1]["w"]):
            toks[i]["w"] = toks[i]["w"][0].upper() + toks[i]["w"][1:]
    if toks:
        toks[0]["w"] = toks[0]["w"][0].upper() + toks[0]["w"][1:]
    txt = lambda c: " ".join(x["w"] for x in c)
    cues, cur = [], []
    for t in toks:
        if cur:
            over = len(txt(cur + [t])) > 48 or t["e"] - cur[0]["s"] > 3.4
            if t["s"] - cur[-1]["e"] > 0.6 or (re.search(r"[.?!]$", cur[-1]["w"]) and len(txt(cur)) > 12):
                cues.append(cur); cur = []
            elif over:
                j = max([k for k in range(len(cur) - 1) if re.search(r"[,.?!:]$", cur[k]["w"]) and len(txt(cur[:k + 1])) >= 14] or [-1])
                if j >= 0:
                    cues.append(cur[:j + 1]); cur = cur[j + 1:]
                else:
                    k = len(cur)
                    while k > 1 and len(re.sub(r"\W", "", cur[k - 1]["w"])) <= 2 and not re.search(r"[,.?!:]$", cur[k - 1]["w"]):
                        k -= 1
                    cues.append(cur[:k]); cur = cur[k:]
        cur.append(t)
    if cur:
        cues.append(cur)
    out = []
    for k, c in enumerate(cues):
        s = txt(c)
        if len(s) > 26:
            best = None
            for i, chh in enumerate(s):
                if chh != " ":
                    continue
                left = s[:i].split(" ")[-1]
                cost = abs(i - len(s) / 2) + (12 if len(re.sub(r"\W", "", left)) <= 2 else 0) - (4 if re.search(r"[,.?!:]$", left) else 0)
                if max(i, len(s) - i - 1) <= 28 and (best is None or cost < best[0]):
                    best = (cost, i)
            if best is None:
                best = (0, min((abs(i - len(s) / 2), i) for i, chh in enumerate(s) if chh == " ")[1])
            s = s[:best[1]] + "\n" + s[best[1] + 1:]
        end = c[-1]["e"] + 0.25
        if k + 1 < len(cues):
            end = min(end, cues[k + 1][0]["s"] - 0.03)
        out.append({"s": round(c[0]["s"] - 0.05, 2), "e": round(end, 2), "t": s})
    return out


def stage_data():
    from faster_whisper import WhisperModel
    t0 = time.time()
    sr2, z = wavfile.read(OUT / "audio.wav")
    dur = len(z) / sr2
    speech = dur - TAIL
    run([FF, "-v", "error", "-y", "-i", str(OUT / "audio.wav"), "-t", f"{speech:.3f}", "-ac", "1", "-ar", "16000", str(TMP / "a16.wav")])
    # повторное распознавание смонтированного звука: только для сверки швов (проглоченные и рваные слова)
    wm = WhisperModel("mobiuslabsgmbh/faster-whisper-large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=8)
    segs, _ = wm.transcribe(str(TMP / "a16.wav"), language="ru", word_timestamps=True, vad_filter=False, beam_size=5,
                            condition_on_previous_text=True, hotwords=getattr(CFG, "HOTWORDS", None))
    asr = [w.word.strip() for s in segs for w in s.words]
    # whisper дописывает на тишине "Продолжение следует", "Субтитры..." и т.п.: такие хвосты в сверке не нужны
    junk = re.compile(r"^(продолжение|следует|субтитр|редактор|корректор|спасибо|подписывайтесь)", re.I)
    while asr and junk.match(asr[-1]):
        asr = asr[:-1]
    asr_text = " ".join(asr)
    # слова для анимации и субтитров: расшифровка исходника, переведенная через монтажный лист во время рилса.
    # Слово берем, если в рилс вошла заметная его часть
    keep = json.load(open(OUT / "edl.json"))["keep"]
    cum = [0.0]
    for a, b, _ in keep:
        cum.append(cum[-1] + (b - a))
    words = []
    for tk in dict.fromkeys(TAKE_OF):
        use(tk)
        for w in W:
            ov = [(k, max(w["s"], a), min(w["e"], b)) for k, (a, b, pi) in enumerate(keep) if TAKE_OF[pi] == tk and min(w["e"], b) - max(w["s"], a) > 0]
            tot = sum(y - x for _, x, y in ov)
            if not ov or (tot < 0.5 * (w["e"] - w["s"]) and tot < 0.12):
                continue
            k0, x0, _ = ov[0]; k1, _, y1 = ov[-1]
            words.append({"w": w["w"], "s": round((cum[k0] + x0 - keep[k0][0]) / SP, 3), "e": round((cum[k1] + y1 - keep[k1][0]) / SP, 3),
                          "seg": keep[k0][2]})
    words.sort(key=lambda w: w["s"])
    fix = R.get("fix", {})
    toks = []
    for w in words:
        t = fix.get(w["w"], w["w"])
        if not t:
            continue
        t = t.replace("\u00ab", '"').replace("\u00bb", '"').replace("\u2014", "-").replace("\u2013", "-").replace("\u0451", "\u0435").replace("\u0401", "\u0415")
        if t.startswith("-") and len(t) > 1 and toks:
            toks[-1]["w"] += t; toks[-1]["e"] = w["e"]; continue
        if toks and w.get("seg") is not None and w["seg"] != toks[-1].get("seg"):
            if "c" in PIECES[w["seg"]][2]:
                if not re.search(r"[,.?!:]$", toks[-1]["w"]):
                    toks[-1]["w"] += ","
            else:
                toks[-1]["w"] = re.sub(r"[,:]$", "", toks[-1]["w"])
                if not re.search(r"[.?!]$", toks[-1]["w"]):
                    toks[-1]["w"] += "."
                t = t[0].upper() + t[1:]
        toks.append({"w": t, "s": w["s"], "e": w["e"], "seg": w.get("seg")})
    # замены фраз в субтитрах: ([слова как распознаны], [как писать]) - оговорки, слова-паразиты, дефисы
    for src_w, dst_w in R.get("subs_replace", []):
        n = len(src_w); i = 0
        norm = lambda x: re.sub(r"[^\w]", "", x.lower())
        while i + n <= len(toks):
            if [norm(t["w"]) for t in toks[i:i + n]] == [norm(x) for x in src_w]:
                tail = re.search(r"[,.?!:]$", toks[i + n - 1]["w"])
                new = [{"w": dst_w[k], "s": toks[i]["s"] if k == 0 else toks[i + min(k, n - 1)]["s"],
                        "e": toks[i + n - 1]["e"] if k == len(dst_w) - 1 else toks[i + min(k, n - 1)]["e"]} for k in range(len(dst_w))]
                if new and tail and not re.search(r"[,.?!:]$", new[-1]["w"]):
                    new[-1]["w"] += tail.group(0)
                toks[i:i + n] = new; i += max(1, len(new))
            else:
                i += 1
    # заглавная без точки перед ней (расшифровка не поставила точку): закрываем предложение. Имена собственные из конфига не трогаем
    PROPER = set(getattr(CFG, "PROPER", []))
    for i in range(1, len(toks)):
        t = toks[i]["w"]
        if re.match(r"[А-Я]", t) and not any(re.sub(r"\W", "", t).startswith(x) for x in PROPER) and not re.search(r"[.?!]$", toks[i - 1]["w"]):
            toks[i - 1]["w"] = re.sub(r"[,:]$", "", toks[i - 1]["w"]) + "."
    cues = cues_for(toks)
    data = {"fps": FPS, "frames": int(round(dur * FPS)), "duration": round(dur, 3), "speech": round(speech, 3),
            "segs": [[0, round(speech, 3), 0]], "words": words, "cues": cues,
            "reel": {"n": R["n"], "title": R["title"], "series": SERIES, "hook": R["hook"], "hook_sub": R["hook_sub"],
                     "cta_label": R["cta_label"], "cta": R["cta"],
                     "ig_label": R.get("ig_label", "СОХРАНИ"), "ig_cta": R.get("ig_cta", "Пригодится")},
            "brand": getattr(CFG, "BRAND", {}),
            "dirs": {"author_pb": "file://" + str(OUT / "author"), "author_cut": "file://" + str(OUT / "author_cut"), "bg": "file://" + str(OUT / "bg")}}
    (OUT / "data.js").write_text("window.SEG = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    (OUT / "speech.txt").write_text(" ".join(t["w"] for t in toks) + "\n\nРАСПОЗНАВАНИЕ СМОНТИРОВАННОГО ЗВУКА (сверка швов):\n" + asr_text, encoding="utf-8")
    log(f"слова {len(words)}, субтитров {len(cues)}, {time.time() - t0:.0f} c")
    print(" ".join(t["w"] for t in toks))


if __name__ == "__main__":
    st = args.stage
    for name, fn in (("audio", stage_audio), ("frames", stage_frames), ("cut", stage_cut), ("data", stage_data)):
        if st in ("all", name):
            fn()
