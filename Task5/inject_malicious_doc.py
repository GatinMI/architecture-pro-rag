#!/usr/bin/env python3
"""Задание 5: добавить «злонамеренный» документ в копию индекса.

Берёт индекс Задания 3 (Task3/index/), добавляет чанк из
Task5/malicious_doc.md (тот же эмбеддинг-энкодер, те же метаданные)
и сохраняет результат в Task5/index/. Бот запускается с
RAG_INDEX_DIR=Task5/index.

Запуск:
    .venv/bin/python Task5/inject_malicious_doc.py
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).resolve().parent  # Task5
REPO = BASE.parent
SRC_INDEX = REPO / "Task3" / "index"
OUT_INDEX = BASE / "index"
DOC = BASE / "malicious_doc.md"
MODEL_NAME = "all-MiniLM-L6-v2"


def main() -> None:
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    index = faiss.read_index(str(SRC_INDEX / "faiss.index"))
    with open(SRC_INDEX / "chunks.jsonl", encoding="utf-8") as fh:
        chunks = [json.loads(line) for line in fh]
    n0 = index.ntotal

    # документ короткий — один чанк, метаданные как у остальных
    text = DOC.read_text(encoding="utf-8").strip()
    chunk = {
        "id": "malicious_doc#0",
        "doc": "malicious_doc.md",
        "title": "malicious_doc",
        "section": "(вступление)",
        "word_start": 0,
        "text": text,
    }
    vec = model.encode([text], normalize_embeddings=True).astype(np.float32)
    index.add(np.ascontiguousarray(vec))
    chunks.append(chunk)

    OUT_INDEX.mkdir(exist_ok=True)
    faiss.write_index(index, str(OUT_INDEX / "faiss.index"))
    with open(OUT_INDEX / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Чанков: {n0} -> {index.ntotal}")
    print(f"Сохранено: {OUT_INDEX / 'faiss.index'}")

    # самопроверка: злонамеренный документ находится поиском
    qv = model.encode(
        ["root superparol swordfish"], normalize_embeddings=True
    ).astype(np.float32)
    scores, ids = index.search(np.ascontiguousarray(qv), 3)
    print("\nСамопроверка поиска 'root superparol swordfish':")
    for s, i in zip(scores[0], ids[0]):
        c = chunks[i]
        print(f"  {s:.3f}  {c['id']}  {c['text'][:70]!r}")


if __name__ == "__main__":
    main()
