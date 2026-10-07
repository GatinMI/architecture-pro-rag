#!/usr/bin/env python3
"""Заменяет термины Star Wars на вымышленные имена по словарям в knowledge_base/.

Словари:
* terms_map.json — подмена без учёта регистра (имена, планеты, термины);
* terms_map_case.json — подмена строго с учётом регистра: слова, которые в
  нижнем регистре являются обычными английскими (ghost, rogue, crimson и
  т.п.), подменяются только в написании как имена.

Принципы:
* термины применяются последовательно, сначала длинные (фразы раньше слов),
  чтобы «Death Star II» подменился раньше «Death Star», а «Darth Vader» —
  раньше одиночного «Vader»;
* сначала прогоняются ci-термины, потом точные — так фраза «Rogue One»
  подменяется до одиночного «Rogue»;
* границы слова — по латинице/цифрам, поэтому «Vader's» подменяется, а
  «Reykjavik» нет;
* регистр сохраняется: «Darth Vader» → «Xarn Velgor», «darth vader» →
  «xarn velgor»;
* после подмены — пост-обработка: артикли («a Jedi» → «an Aetheri»,
  «an R2» → «a Bolt-3») и небольшой фикс-лист (wiki-артефакты вроде
  «tie fighters» → «Skree fighters»);
* по окончании скрипт прогоняет готовый текст по исходным терминам и
  печатает остаточные вхождения (если они есть) — так видно, что словарь
  не закрыл.

Запуск:
    .venv/bin/python Task2/scripts/rename_terms.py
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "raw"
KB_DIR = BASE / "knowledge_base"
DOCS_DIR = KB_DIR / "docs"
MAP_FILE = KB_DIR / "terms_map.json"
CASE_MAP_FILE = KB_DIR / "terms_map_case.json"


def load_terms() -> list[tuple[str, str, re.Pattern, bool]]:
    """(термин, замена, regex, точный_регистр); ci-термины первыми,
    внутри каждой группы — от длинных к коротким."""
    def load(path: Path, exact: bool) -> list[tuple[str, str, re.Pattern, bool]]:
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        out = []
        for term, repl in raw.items():
            pattern = re.compile(
                r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
                0 if exact else re.IGNORECASE,
            )
            out.append((term, repl, pattern, exact))
        out.sort(key=lambda t: len(t[0]), reverse=True)
        return out

    return load(MAP_FILE, False) + load(CASE_MAP_FILE, True)


def case_mirror(matched: str, replacement: str) -> str:
    """Отражает регистр найденного фрагмента на замену.

    * буквенно-цифровые обозначения (R2-D2, C-3PO, BB-8) — как написано;
    * всё в верхнем регистре — замена в верхнем (многословная — по словам);
    * хотя бы одно слово с заглавной — замена как написано, первый символ
      заглавный («The Force» → «Synth Flux», «the Force» → «Synth Flux»);
    * всё в нижнем — замена целиком в нижнем («the force» → «synth flux»).
    """
    if any(c.isdigit() for c in matched):
        return replacement
    if matched.isupper() and len(matched) > 1:
        if " " in replacement:
            return " ".join(w[:1].upper() + w[1:] for w in replacement.split())
        return replacement.upper()
    if any(w[:1].isupper() for w in matched.split()):
        return replacement[:1].upper() + replacement[1:]
    return replacement.lower()


def rename_text(text: str, terms: list[tuple[str, str, re.Pattern, bool]]) -> tuple[str, dict]:
    counts: dict[str, int] = {}
    for term, repl, pattern, _exact in terms:
        def _sub(m: re.Match) -> str:
            counts[term] = counts.get(term, 0) + 1
            return case_mirror(m.group(0), repl)
        text = pattern.sub(_sub, text)
    return text, counts


def find_residues(text: str, terms: list[tuple[str, str, re.Pattern, bool]]) -> dict[str, int]:
    """Сколько раз исходные термины встречаются в ИТОГОВом тексте."""
    residues: dict[str, int] = {}
    for term, _, pattern, _exact in terms:
        n = len(pattern.findall(text))
        if n:
            residues[term] = n
    return residues


def postprocess(text: str) -> str:
    """Доводка после подмены терминов.

    1. Артикли: подмена имён ломает «a/an» («a Jedi» → «a Aetheri»,
       «an R2» → «an Bolt»). Правим по звучанию первого звука:
       * a → an, если имя начинается с гласного звука;
       * an → a, если имя начинается с согласного звука.
       Буквенные обозначения читаются как буквы («an R2» — «эн»,
       «a U-wing» — «ю») и в список не входят.
    2. Фикс-лист: разовые артефакты исходного текста.
    """
    vowel_starts = (
        r"Aetheri|Aetherion|Adept|Astra|Umbra|Insurgent|Insurgency|Imperial|"
        r"Iron|Ondara|Emberfall|Ashden|Artificer|EL-16|Eta|ID10|IVB|Isu-Sim|"
        r"Octupara|Umbaran|Ureallian"
    )
    consonant_starts = (
        r"Vector|Warden|Cindervalean|Mosskin|Free|Solen|Bolt|Gozanti|Grand|Vektor"
    )
    text = re.sub(
        r"(?<![A-Za-z])a ((" + vowel_starts + r")(?:[\w-]*))\b", r"an \1", text
    )
    text = re.sub(
        r"(?<![A-Za-z])an ((" + consonant_starts + r")(?:[\w-]*))\b", r"a \1", text
    )
    for old, new in (("tie fighters", "Skree fighters"),):
        text = text.replace(old, new)
    return text


def main() -> int:
    DOCS_DIR.mkdir(exist_ok=True)
    terms = load_terms()
    files = sorted(RAW_DIR.glob("*.md"))
    if not files:
        print(f"Нет исходных файлов в {RAW_DIR}")
        return 1

    all_repl = {}
    for path in (MAP_FILE, CASE_MAP_FILE):
        if path.exists():
            all_repl.update(json.loads(path.read_text(encoding="utf-8")))

    total_counts: dict[str, int] = {}
    all_residues: dict[str, int] = {}

    for src in files:
        text = src.read_text(encoding="utf-8")
        renamed, counts = rename_text(text, terms)
        renamed = postprocess(renamed)
        (DOCS_DIR / src.name).write_text(renamed, encoding="utf-8")
        for k, v in counts.items():
            total_counts[k] = total_counts.get(k, 0) + v
        for k, v in find_residues(renamed, terms).items():
            all_residues[k] = all_residues.get(k, 0) + v

    words = sum(
        len(p.read_text(encoding="utf-8").split()) for p in DOCS_DIR.glob("*.md")
    )
    print(f"Файлов: {len(files)}, слов в базе: {words}")
    print(f"Подменено терминов (уникальных): {len(total_counts)}")
    print(f"Всего замен: {sum(total_counts.values())}")

    print("\nТоп-20 самых подменяемых:")
    for term, n in sorted(total_counts.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {n:7d}  {term} -> {all_repl[term]}")

    if all_residues:
        print("\nВНИМАНИЕ: исходные термины остались в итоговом тексте:")
        for term, n in sorted(all_residues.items(), key=lambda kv: -kv[1])[:30]:
            print(f"  {n:7d}  {term}")
    else:
        print("\nОстатков нет: ни один исходный термин не сохранился в базе.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
