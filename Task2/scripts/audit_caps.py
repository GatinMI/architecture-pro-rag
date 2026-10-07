#!/usr/bin/env python3
"""Аудит: все токены с заглавной в итоговых docs, кроме значений/ключей мапы."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
DOCS = BASE / "Task2/knowledge_base/docs"
m = json.loads((BASE / "Task2/knowledge_base/terms_map.json").read_text(encoding="utf-8"))

cnt = Counter()
for p in DOCS.glob("*.md"):
    text = p.read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.lstrip("#> \t")
        if not s:
            continue
        body = s[1:] if s[0].isupper() else s  # скидываем начало предложения
        for t in re.findall(r"[A-Z][A-Za-z0-9'./\-]*", body):
            cnt[t] += 1

exclude = set()
for v in m.values():
    for t in re.findall(r"[A-Z][A-Za-z0-9'./\-]*", v):
        exclude.add(t)
for k in m.keys():
    for t in re.findall(r"[A-Z][A-Za-z0-9'./\-]*", k):
        exclude.add(t)

min_n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
print(f"Топ токенов с заглавной вне мапы (порог {min_n}, всего токенов: {len(cnt)}):")
for t, n in cnt.most_common(500):
    if t in exclude or n < min_n:
        continue
    print(f"  {n:6d}  {t}")
