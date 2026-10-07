#!/usr/bin/env python3
"""Точные контексты подозрительных слов в raw + список актёров из Behind the scenes."""
import re
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "raw"

def show(word, pat_extra="", n=3):
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])" + pat_extra, re.IGNORECASE)
    shown = 0
    for p in sorted(RAW.glob("*.md")):
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            s = max(0, m.start() - 55)
            e = min(len(p.read_text(encoding="utf-8")), m.end() + 55)
            ctx = p.read_text(encoding="utf-8")[s:e].replace("\n", " ")
            print(f"  {p.name}: …{ctx}…")
            shown += 1
            if shown >= n:
                return

print("== Sy")
show("Sy")
print("== Mas")
show("Mas")
print("== Rax")
show("Rax")
print("== Rogue (standalone)")
shown = 0
pat = re.compile(r"(?<![A-Za-z0-9])Rogue(?![A-Za-z0-9\-])")
for p in sorted(RAW.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    for m in pat.finditer(text):
        s = max(0, m.start() - 50); e = min(len(text), m.end() + 50)
        print(f"  {p.name}: …{text[s:e].replace(chr(10),' ')}…")
        shown += 1
        if shown >= 8:
            break
    if shown >= 8:
        break

print("== Phoenix")
show("Phoenix", n=4)
print("== Lambda")
show("Lambda", n=3)
print("== Ghost")
show("Ghost", n=3)
print("== San")
show("San", n=4)
print("== Aurra Sing")
show("Aurra Sing", n=2)
print("== Spark Eternal")
show("Spark Eternal", n=2)
print("== Ben (кто есть Ben)")
shown = 0
pat = re.compile(r"(?<![A-Za-z0-9])Ben (?=[A-Z])")
for p in sorted(RAW.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    for m in pat.finditer(text):
        s = max(0, m.start() - 30); e = min(len(text), m.end() + 30)
        print(f"  {p.name}: …{text[s:e].replace(chr(10),' ')}…")
        shown += 1
        if shown >= 6:
            break
    if shown >= 6:
        break
print("== Bail (кто есть Bail)")
shown = 0
pat = re.compile(r"(?<![A-Za-z0-9])Bail (?=[A-Z])")
for p in sorted(RAW.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    for m in pat.finditer(text):
        s = max(0, m.start() - 30); e = min(len(text), m.end() + 30)
        print(f"  {p.name}: …{text[s:e].replace(chr(10),' ')}…")
        shown += 1
        if shown >= 6:
            break
    if shown >= 6:
        break

# ---- актёры из Behind the scenes ----
print("== актёры (portrayed/voiced/played by)")
actor_re = re.compile(
    r"(?:portray(?:ed|ing)?|voice(?:d)?|play(?:ed|ing)?)\s+(?:the\s+role\s+of\s+|as\s+)?"
    r"(?:\w+\s+){0,2}\b([A-Z][a-zà-ÿ]+(?: [A-Z][a-zà-ÿ]+){1,2})\b",
    re.IGNORECASE,
)
names = {}
for p in sorted(RAW.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"(?:portrayed|voiced|played|performance|actor|actress|voice actor)[^.]{0,120}", text, re.IGNORECASE):
        seg = m.group(0)
        for nm in re.findall(r"\b([A-Z][a-zà-ÿ]{2,}(?: [A-Z][a-zà-ÿ]{2,}){1,2})\b", seg):
            names[nm] = names.get(nm, 0) + 1
for nm, n in sorted(names.items(), key=lambda kv: -kv[1])[:60]:
    print(f"  {n:4d}  {nm}")
