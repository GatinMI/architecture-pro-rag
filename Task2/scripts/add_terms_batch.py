#!/usr/bin/env python3
"""Добавляет новый блок терминов в terms_map.json и terms_map_case.json.

* ci-термины (без учёта регистра) — в terms_map.json;
* термины, которые в нижнем регистре являются обычными английскими словами
  (ghost, rogue, malevolence, omega и т.п.), — в terms_map_case.json
  (подмена строго по регистру);

Самопроверка:
* новое значение не содержит в себе другие термины мапы (с границами слова);
* термин/значение не дублируют существующие записи.
"""
import json
import re
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "knowledge_base"
MAP_FILE = KB / "terms_map.json"
CASE_FILE = KB / "terms_map_case.json"

# (термин, замена) — подмена без учёта регистра
NEW_CI = {
    # крупные упущенные персонажи
    "Ben": "Beno",
    "Quadinaros": "Quadinar",
    "Bail": "Bael",
    "Shmi": "Shira",
    "Norra": "Nevra",
    "Watto": "Waddu",
    "Elsbeth": "Elveth",
    "Cylo": "Silvar",
    "Wren": "Wrenna",
    "Hera": "Lena",
    "Poe": "Pova",
    "Orson": "Orren",
    "Pryce": "Pryssa",
    "Janard": "Janarda",
    "Bo-Katan": "Bo-Katin",
    "Katan": "Katin",
    "Quinlan": "Quilav",
    "Vos": "Vossa",
    "Rae": "Raena",
    "Gideon": "Giedan",
    "Chopper": "Chomper",
    "Din": "Dinna",
    "Bren": "Brena",
    "Durge": "Durk",
    "Nute": "Nutis",
    "Garazeb": "Gara-Zev",
    "Zuckuss": "Zuckusso",
    "Bonteri": "Bontero",
    "Eeth": "Etha",
    "Zare Leonis": "Zara Leonisa",
    "Karé Kun": "Kare Kunna",
    "Iolo": "Iola",
    "Arana": "Aranna",
    "Piell": "Piele",
    "Jek": "Jekko",
    "Beris": "Berisa",
    "Freemaker": "Freymark",
    "Freemakers": "Freymarks",
    "Rowan": "Rowenna",
    "Gann": "Ganna",
    "Nute Gang": "Nutis Gell",
    "Shin Hati": "Shen Hadik",
    "Hati": "Hadik",
    "Fenn Rau": "Fen Raun",
    "Rau": "Raun",
    "Cara Dune": "Cara Dunmore",
    "Gerrera": "Vess",
    "Mas": "Mazan",
    "San": "Saan",
    "Sy": "Syra",
    "Rax": "Raxen",
    "Gallius": "Gallard",
    "Cham": "Chavar",
    "Belkor": "Belka",
    "Dray": "Drayn",
    "Tage": "Tagin",
    "Tamsin": "Tamris",
    "Preigo": "Preik",
    "Sato": "Savren",
    "Greef": "Grevan",
    "Karga": "Kargan",
    "Nala-Se": "Nalle-Seris",
    "Wampas": "Frostmaws",
    "Crosshair": "Crossline",
    "War-Mantle": "Warshroud",
    "Thand": "Thandir",
    "Parasitti": "Parast",
    "Clawdite": "Gloamite",
    "Xanadu": "Xanor",
    "Jerec": "Jeric",
    "Lama Su": "Lamir",
    "Chi Cho": "Chivva",
    "Techno Union": "Artificer Union",
    "Crimson Dawn": "Carmine Dawn",
    "ISB": "IVB",
    "Imperial Security Bureau": "Imperium Vigil Bureau",
    "BT-1": "VT-1",
    "ZED-6-7": "ZEV-6-7",
    "Lambda": "Vectis",
    "Phoenix": "Ember",
    "Rogue One": "Renegade One",
    "Rogue Squadron": "Renegade Squadron",
    "Rogue -class": "Renegade -class",
    "Revenge of the Sith": "Fury of the Umbra",
    "Spark Eternal": "Everspark",
    "Trios": "Triova",
    "Lee-Char": "Liarch",
    "Gree": "Grev",
    "Wullf Yularen": "Wulric Yular",
    "Yularen": "Yular",
    "Wullf": "Wulric",
    "Nite Owl": "Gloom Owl",
    "Death Watch": "Grave Watch",
    "Dark Acolyte": "Dark Adept",
    "The Acolyte": "The Adeptis",
    "Miyazaki": "Miyara",
    "Hayao": "Hayora",
    "Mononoke": "Monorike",
    "Ghibli": "Ghibria",
    "George": "Orin",
    "ILM": "VLM",
    "Industrial Light & Magic": "Vask Light & Magic",
    "StarWars.com": "Aetherion.com",
    "Respeecher": "Voxcraft",
    "Sims": "Simza",
    "Pinewood": "Pinegrove",
    "Ealing": "Ealinga",
    "Joby Harold": "Jovet Harlo",
    "Harold": "Harlo",
    "Ryan Church": "Ryan Charke",
    "Ray Park": "Ray Parkin",
    # реальные люди (фамилии), Behind the scenes
    "Filoni": "Filono",
    "Abrams": "Abramo",
    "Kasdan": "Kasdano",
    "Gilroy": "Gilron",
    "McQuarrie": "Quarrio",
    "Favreau": "Favra",
    "Kennedy": "Kenna",
    "Ridley": "Ridella",
    "Boyega": "Boyeko",
    "Dawson": "Dawso",
    "Neeson": "Neesona",
    "Lloyd": "Lloydo",
    "Prowse": "Prowsko",
    "Lanter": "Lanteri",
    "Bauza": "Bauzo",
    "Wilding": "Wildink",
    "Gurland": "Gurlandi",
    "Naprous": "Naporus",
    "Manriquez": "Manrivo",
    "Lawrence": "Lawrin",
    "Sloan": "Sloani",
    "Bistrevsky": "Bistrevo",
    "Logan": "Logano",
    "Barton": "Bartono",
    "Blair": "Blairi",
    "Kershner": "Kershnar",
    "Guinness": "Gunnis",
    "Beattie": "Beattino",
    "Ford": "Fordo",
    "Fisher": "Fishera",
    "Daniels": "Danielo",
    "Baker": "Bakeri",
    "Shaw": "Shavo",
    "Jones": "Jonis",
    "McDiarmid": "Diarno",
    "Oz": "Ozzik",
    "Morrison": "Morison",
    "Hidalgo": "Hidra",
    "Taylor": "Taylen",
    "Fry": "Fryo",
    "Chiang": "Chiano",
    "Soule": "Soulea",
    "Chow": "Chova",
    "Williams": "Wilham",
    "Mayhew": "Mahevo",
    "Ewan": "Evaan",
    "Christensen": "Kristano",
    "McGregor": "Gregan",
}

# (термин, замена) — строго с учётом регистра (в нижнем регистре — обычные слова)
NEW_CASE = {
    "Ghost": "Wisp",
    "Rogue": "Renegade",
    "Malevolence": "Malignar",
    "Omega": "Omaya",
    "Shin": "Shen",
    "Acolyte": "Adeptis",
    "Driver": "Drivari",
    "Wood": "Wooda",
    "Se": "Seris",
    "Saw": "Torrik",
}


def main() -> int:
    # убираем заглушки (ключ == значение — это не термин)
    new_ci = {k: v for k, v in NEW_CI.items() if k != v}
    new_case = {k: v for k, v in NEW_CASE.items() if k != v}

    m = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    case = {}
    if CASE_FILE.exists():
        case = json.loads(CASE_FILE.read_text(encoding="utf-8"))

    errors = []
    for term, repl in {**new_ci, **new_case}.items():
        if term in m or term in case:
            errors.append(f"термин уже в мапе: {term!r}")
        if repl in m.values() and m.get(repl) != repl:
            pass  # совпадение значений допустимо (разные термины -> одно имя)
        # значение не должно содержать другие термины мапы
        for other in list(m.keys()) + list(case.keys()):
            if other == term:
                continue
            pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(other) + r"(?![A-Za-z0-9])", re.IGNORECASE)
            if pat.search(repl):
                errors.append(f"значение {repl!r} содержит термин {other!r}")

    if errors:
        print("ОШИБКИ:")
        for e in errors:
            print("  -", e)
        return 1

    added_ci = added_case = 0
    for term, repl in new_ci.items():
        m[term] = repl
        added_ci += 1
    for term, repl in new_case.items():
        case[term] = repl
        added_case += 1

    MAP_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    CASE_FILE.write_text(json.dumps(case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"terms_map.json: +{added_ci} (всего {len(m)})")
    print(f"terms_map_case.json: +{added_case} (всего {len(case)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
