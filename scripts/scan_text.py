"""Машинный скан текста перед сдачей: запрещенные символы и запрещенные слова (бренд, фамилии, токены).
python3 scan_text.py <файл или папка>... [--words слова.txt]
Символы: е с точками, кавычки-елочки, длинное и среднее тире, стрелки, знак умножения, знак рубля.
--words: файл, одно слово или фраза в строке; ищется без учета регистра. Сам файл слов в репозиторий не класть.
Код выхода 1, если что-то найдено."""
import pathlib, re, sys
BAD = {"\u0451": "е с точками", "\u0401": "Е с точками", "\u00ab": "кавычка-елочка", "\u00bb": "кавычка-елочка",
       "\u2014": "длинное тире", "\u2013": "среднее тире", "\u2192": "стрелка", "\u2190": "стрелка", "\u21d2": "стрелка",
       "\u00d7": "знак умножения", "\u20bd": "знак рубля"}
TEXT = {".md", ".py", ".js", ".cjs", ".mjs", ".css", ".html", ".json", ".txt", ".sh", ".srt", ".vtt", ""}
args = sys.argv[1:]
words = []
if "--words" in args:
    i = args.index("--words"); words = [w.strip() for w in open(args[i + 1], encoding="utf-8") if w.strip()]; del args[i:i + 2]
rx = re.compile("|".join(re.escape(w) for w in words), re.I) if words else None
files = []
for a in args:
    p = pathlib.Path(a)
    files += [f for f in p.rglob("*") if f.is_file() and ".git" not in f.parts and "node_modules" not in f.parts] if p.is_dir() else [p]
hits = 0
for f in files:
    if f.suffix.lower() not in TEXT:
        continue
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        continue
    for n, line in enumerate(lines, 1):
        for ch, what in BAD.items():
            if ch in line:
                hits += 1; print(f"{f}:{n}: {what}: {line.strip()[:100]}")
        if rx and rx.search(line):
            hits += 1; print(f"{f}:{n}: слово {rx.search(line).group(0)!r}: {line.strip()[:100]}")
print("найдено", hits)
sys.exit(1 if hits else 0)
