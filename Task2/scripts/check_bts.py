#!/usr/bin/env python3
"""Акты из Behind the sections + недостающие счётчики raw."""
import json
import re
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "raw"
KB = Path(__file__).resolve().parent.parent / "knowledge_base"
m = json.loads((KB / "terms_map.json").read_text(encoding="utf-8"))

exclude = set()
for v in m.values():
    for t in re.findall(r"[A-Z][A-Za-z0-9'./\-]*", v):
        exclude.add(t)

# ---- Behind the scenes: токены с заглавной вне мапы ----
from collections import Counter
cnt = Counter()
for p in sorted(RAW.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    i = text.find("Behind the scenes")
    if i < 0:
        continue
    seg = text[i:]
    for t in re.findall(r"[A-Z][A-Za-z0-9'./\-]*", seg):
        cnt[t] += 1

print("== Токены с заглавной в Behind the scenes, вне мапы, >=2:")
for t, n in cnt.most_common(400):
    if t in exclude or n < 2:
        continue
    print(f"  {n:5d}  {t}")

# ---- недостающие счётчики ----
def c(w):
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    n = 0
    for p in RAW.glob("*.md"):
        n += len(pat.findall(p.read_text(encoding="utf-8")))
    return n

print("\n== Счётчики raw:")
for w in ["Parasitti", "Clawdite", "Torb Rask", "Rask", "Quadinaros", "Gallius", "Tekka",
          "Wullf", "Yularen", "Lama Su", "Chi Cho", "Xanadu", "Jerec", "Cham", "Belkor",
          "Dray", "Tage", "Tamsin", "Preigo", "Sato", "Greef", "Karga", "Wampas", "Crosshair",
          "Omega", "War-Mantle", "Thand", "Phoenix Squadron", "Phoenix Cell", "Phoenix Leader",
          "Rogue Squadron", "Rogue -class", "Rogue-class", "Spark Eternal", "Imperial Security Bureau",
          "Cad Bane", "Aurra Sing", "Crimson Dawn", "King San", "Lor San Tekka", "Mas Amedda",
          "Gallius Rax", "Ben Quadinaros", "Ben Solo", "Shmi Skywalker", "Norra Wexley", "Watto",
          "Elsbeth", "Hondo", "Bo-Katan", "Katan", "Apoc", "Sugi", "Chirrut", "Baze", "Holdo",
          "Bodhi", "Jyn", "Cassian", "Andor", "Fulcrum", "Moff", "Aphra", "Reva", "Din Djarin",
          "Grogu", "Rex", "Fives", "Crosshair", "Riot", "Scourge", "Ody", "Vatara", "Durge",
          "Nute", "Gang", "Riff Tamson", "Prince X", "Sabé", "Sable", "Yoda", "Quinlan",
          "Vos", "Meren", "Rae", "Saw", "Greez", "Bodhi Rook", "Ezra", "Kallus", "Agent Kallus",
          "Garazeb", "Zeb", "Hera", "Chopper", "Epguide", "Cid", "Riot", "Bren", "Mala",
          "Ruth", "Rho", "Gree", "Din", "Apoc", "Gorian", "Shin", "Moff Gideon", "Gideon",
          "Morag", "Fenn", "Rau", "Greef Karga", "Cara Dune", "Dune", "Kryll", "Vray"]:
    n = c(w)
    if n:
        print(f"  {n:5d}  {w}")
