#!/usr/bin/env python3
"""Поиск по FAISS-индексу: запрос → топ-k чанков с метаданными.

Запуск:
    .venv/bin/python Task3/query_index.py "кто такой Kael Drayden?"
    .venv/bin/python Task3/query_index.py "что такое Synth Flux?" -k 5
"""

import argparse
import json
import time
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path(__file__).resolve().parent / "index"
MODEL_NAME = "all-MiniLM-L6-v2"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=3)
    args = ap.parse_args()

    with open(INDEX_DIR / "chunks.jsonl", encoding="utf-8") as fh:
        chunks = [json.loads(line) for line in fh]
    index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    qv = model.encode([args.query], normalize_embeddings=True)
    t0 = time.time()
    scores, ids = index.search(qv, args.k)
    dt = (time.time() - t0) * 1000

    print(f'Запрос: {args.query!r}  (поиск: {dt:.0f} мс)\n')
    for rank, (score, i) in enumerate(zip(scores[0], ids[0]), 1):
        if i < 0:
            continue
        c = chunks[i]
        preview = c["text"][:220].replace("\n", " ")
        print(
            f"{rank}. [cos={score:.3f}] {c['doc']} · «{c['title']}» · "
            f"секция «{c['section']}» · слово ~{c['word_start']} ({c['id']})\n"
            f"   {preview}…"
        )
        print()


if __name__ == "__main__":
    main()
