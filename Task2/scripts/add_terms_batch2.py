#!/usr/bin/env python3
"""Вторая порция словарей после полного аудита готовой базы.

1. NEW_CI — термин, которого не хватило (редкие персонажи, дроид-коды,
   названия серий):
   * Sana Starros, Jocasta Nu / Nu-class, Wilhuff Tarkin, Darth Atrius,
     Aqualish, дройд Arex, standalone «3PO» (без «C-»), 4-LOM / LOM-series,
     IG-88B, Tunga Arpagion, Sagwa;
   * «3PO» и «4-LOM»/«LOM» мапятся на те же значения, что полные коды
     («C-3PO» → Astra-9), чтобы «3PO-series» читалось как «Astra-9-series».

2. MOVE_TO_CASE — термины из ci-мапы, которые в нижнем регистре являются
   обычными английскими словами (в raw такие вхождения есть и подменять
   их нельзя):
   * tie/ties (завязать), trace (след), solo (solo-миссия), sing (петь),
     maul (избить), bane (бедствие), grievous (тяжкий) — а заглавные
     TIE, Trace, Solo, Sing, Maul, Bane, Grievous — персонажи/техника.
   Переносятся в terms_map_case.json со значениями из ci-мапы.

Запуск:
    .venv/bin/python Task2/scripts/add_terms_batch2.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "knowledge_base"
MAP_FILE = BASE / "terms_map.json"
CASE_FILE = BASE / "terms_map_case.json"

NEW_CI = {
    "Starros": "Starric",
    "Nu": "Nura",
    "Wilhuff": "Wilhard",
    "Atrius": "Atrio",
    "Aqualish": "Aquari",
    "Arex": "Arekso",
    "3PO": "Astra-9",
    "4-LOM": "4-VOX",
    "LOM": "VOX",
    "IG-88B": "VX-88B",
    "Arpagion": "Arpagin",
    "Sagwa": "Sagor",
}

# термин: значение берётся из ci-мапы, если в словаре не указано явно
MOVE_TO_CASE = {
    "Grievous": None,
    "TIE": None,
    "TIEs": None,
    "Trace": None,
    "Solo": None,
    "Sing": None,
    "Maul": None,
    "Bane": None,
}


def main() -> int:
    m = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    case = {}
    if CASE_FILE.exists():
        case = json.loads(CASE_FILE.read_text(encoding="utf-8"))

    errors = []

    for term in NEW_CI:
        if term in m or term in case:
            errors.append(f"термин уже в мапе: {term!r}")
    for term in MOVE_TO_CASE:
        if term not in m:
            errors.append(f"переносимый термин не в ci-мапе: {term!r}")
        if term in case:
            errors.append(f"переносимый термин уже в case-мапе: {term!r}")

    def value_contains_term(repl: str) -> str | None:
        for other in list(m.keys()) + list(case.keys()) + list(NEW_CI):
            if other == repl:
                continue
            pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(other) + r"(?![A-Za-z0-9])", re.IGNORECASE)
            if pat.search(repl):
                return other
        return None

    for term, repl in NEW_CI.items():
        hit = value_contains_term(repl)
        if hit:
            errors.append(f"значение {repl!r} содержит термин {hit!r}")
    for term, repl in MOVE_TO_CASE.items():
        value = repl or m[term]
        hit = value_contains_term(value)
        if hit:
            errors.append(f"переношу {term!r}: значение {value!r} содержит термин {hit!r}")

    if errors:
        print("ОШИБКИ:")
        for e in errors:
            print("  -", e)
        return 1

    for term, repl in NEW_CI.items():
        m[term] = repl
    for term, repl in MOVE_TO_CASE.items():
        case[term] = repl or m.pop(term)

    MAP_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CASE_FILE.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"terms_map.json: +{len(NEW_CI)} ci, перенесено в case: {len(MOVE_TO_CASE)} (всего ci: {len(m)})")
    print(f"terms_map_case.json: +{len(MOVE_TO_CASE)} (всего: {len(case)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
