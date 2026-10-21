"""Шаблон обезличивания демо-копии продукта перед записью экрана. Все имена ниже вымышленные: замените на свои.
Правит КОПИЮ: текстовый файл или базу SQLite (все текстовые ячейки всех таблиц). Боевые данные не трогать.

python anonymize_example.py копия.db          # SQLite на месте
python anonymize_example.py вход.html выход.html

Как устроено:
- бренд и его написания (латиница, кириллица, все падежи) - регулярные выражения;
- фамилии - по основе: Иванов -> Петров, окончание сохраняется (Ивановой -> Петровой), поэтому склонение верное;
- несклоняемые и особые формы - словарь целых слов;
- имена - по основе той же парадигмы (Григорий -> Арсений: Григория -> Арсения);
- логины и почты - отдельный словарь латиницей.
После прогона: поиск по исходным значениям должен давать ноль (assert в конце), и кадры записи все равно смотреть глазами.
"""
import re, sqlite3, sys

BRAND = [(r"ACME|Acme", "DEMOBRAND"), (r"acme", "demobrand"), (r"Акме\w*", "Демобренд")]
STEMS = {"Иванов": "Петров", "Сидоров": "Козлов", "Кузнецов": "Морозов"}       # основа -> основа, окончание сохраняется
SUF = r"(?:ыми|ого|ому|ая|ой|ую|ий|им|ом|ым|ых|а|у|е|ы|и)?"
WORDS = {"Шевченко": "Гончаренко", "Саша": "Паша", "Саши": "Паши", "Саше": "Паше", "Сашу": "Пашу", "Сашей": "Пашей"}
NAMES = {"Григори": "Арсени", "Марин": "Лилиан"}                                 # основа имени -> основа той же парадигмы
NSUF = r"(?:ем|ой|ою|ей|ям|я|ю|е|у|а|ы|и|й)?"
LOGINS = {"ivanov": "petrov", "sidorova": "kozlova"}

subs = [(re.compile(a), b) for a, b in BRAND]
subs.append((re.compile(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b"), lambda m: WORDS[m.group(1)]))
subs.append((re.compile(r"\b(" + "|".join(sorted(STEMS, key=len, reverse=True)) + r")(" + SUF + r")\b"), lambda m: STEMS[m.group(1)] + m.group(2)))
subs.append((re.compile(r"\b(" + "|".join(sorted(NAMES, key=len, reverse=True)) + r")(" + NSUF + r")\b"), lambda m: NAMES[m.group(1)] + m.group(2)))
subs.append((re.compile(r"(?<![a-z])(" + "|".join(sorted(LOGINS, key=len, reverse=True)) + r")(?![a-z])"), lambda m: LOGINS[m.group(1)]))


def fix(s):
    for rx, rep in subs:
        s = rx.sub(rep, s)
    return s


ORIG = re.compile("|".join([a for a, _ in BRAND] + list(STEMS) + list(WORDS) + list(LOGINS)))

if __name__ == "__main__":
    if sys.argv[1].endswith(".db"):
        c = sqlite3.connect(sys.argv[1]); n = 0
        for (t,) in c.execute("select name from sqlite_master where type='table' and name not like '%fts%'").fetchall():
            for col in [r[1] for r in c.execute(f"pragma table_info({t})") if r[2].upper() in ("TEXT", "")]:
                for rid, v in c.execute(f"select rowid, {col} from {t} where typeof({col})='text'").fetchall():
                    nv = fix(v)
                    if nv != v:
                        c.execute(f"update {t} set {col}=? where rowid=?", (nv, rid)); n += 1
        c.commit()
        left = [v for (t,) in c.execute("select name from sqlite_master where type='table' and name not like '%fts%'").fetchall()
                for col in [r[1] for r in c.execute(f"pragma table_info({t})") if r[2].upper() in ("TEXT", "")]
                for (v,) in c.execute(f"select {col} from {t} where typeof({col})='text'") if ORIG.search(v)]
        print("ячеек изменено", n, "осталось исходных значений", len(left))
        assert not left, left[:5]
        print("поисковый индекс перестроить после обезличивания: в нем остались старые слова")
    else:
        t = fix(open(sys.argv[1], encoding="utf-8").read())
        assert not ORIG.search(t), ORIG.search(t).group(0)
        open(sys.argv[2], "w", encoding="utf-8").write(t)
        print("ok")
