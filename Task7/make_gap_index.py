#!/usr/bin/env python3
"""Вносит искусственные «пробелы» в базу знаний (Задание 7).

Берёт живой индекс (Task6/index) и удаляет ВСЕ чанки, в тексте которых
упоминаются ключевые сущности:

    Xarn Velgor   — персонаж (аналог тёмного лорда)
    Void Core     — супероружие
    Synth Flux    — базовый концепт мира

Матч — подстрока без учёта регистра (покрывает «Void Core II»,
«Synth Flux-sensitive» и т.п.). Результат — Task7/index/: индекс
с «пробелами», на котором проверяем, как бот ведёт себя, когда
нужной информации в базе нет.

Запуск:
    .venv/bin/python Task7/make_gap_index.py
"""

import json
from collections import Counter
from pathlib import Path

import faiss
import numpy as np

BASE = Path(__file__).resolve().parent  # Task7
SRC = BASE.parent / "Task6" / "index"
DST = BASE / "index"

ENTITIES = ["Xarn Velgor", "Void Core", "Synth Flux"]
DIM = 384


def main() -> None:
    index = faiss.read_index(str(SRC / "faiss.index"))
    with open(SRC / "chunks.jsonl", encoding="utf-8") as fh:
        chunks = [json.loads(line) for line in fh]
    assert index.ntotal == len(chunks), "индекс и chunks.jsonl в разногласии"

    per_entity = Counter()
    affected_docs = Counter()
    kept: list[dict] = []
    kept_vecs: list[np.ndarray] = []
    for i, c in enumerate(chunks):
        low = c["text"].lower()
        hit = [e for e in ENTITIES if e.lower() in low]
        if hit:
            per_entity.update(hit)
            affected_docs[c["doc"]] += 1
            continue
        kept.append(c)
        kept_vecs.append(index.reconstruct(i))

    DST.mkdir(parents=True, exist_ok=True)
    new_index = faiss.IndexFlatIP(DIM)
    new_index.add(np.ascontiguousarray(np.vstack(kept_vecs), dtype=np.float32))
    faiss.write_index(new_index, str(DST / "faiss.index"))
    with open(DST / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for c in kept:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(
        f"чанков было: {len(chunks)}, удалено: {len(chunks) - len(kept)}, "
        f"осталось: {len(kept)}"
    )
    for e in ENTITIES:
        print(f"  {e}: -{per_entity[e]} чанков")
    print("документы, затронуты сильнее всего:")
    for doc, n in affected_docs.most_common(10):
        print(f"  {doc}: -{n}")


if __name__ == "__main__":
    main()
