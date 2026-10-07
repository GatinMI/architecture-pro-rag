"""Поиск по FAISS-индексу из Задания 3.

Загружает один раз (модуль-синглтон) и дальше отвечает на запросы:
эмбеддинг запроса тем же энкодером, что и чанки, + IndexFlatIP.
"""

import json
import threading

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from .config import SETTINGS

_lock = threading.Lock()
_state: dict = {}


def _init() -> None:
    if _state:
        return
    with _lock:
        if _state:
            return
        _state["model"] = SentenceTransformer(
            SETTINGS.embedding_model, device="cpu"
        )
        _state["index"] = faiss.read_index(str(SETTINGS.index_dir / "faiss.index"))
        with open(SETTINGS.index_dir / "chunks.jsonl", encoding="utf-8") as fh:
            _state["chunks"] = [json.loads(line) for line in fh]


def search(query: str, k: int | None = None) -> list[tuple[float, dict]]:
    """Топ-k чанков: список (косинусная близость, чанк-с-метаданными)."""
    _init()
    k = k or SETTINGS.top_k
    qv = _state["model"].encode([query], normalize_embeddings=True)
    scores, ids = _state["index"].search(np.ascontiguousarray(qv, np.float32), k)
    results = []
    for score, i in zip(scores[0], ids[0]):
        if i < 0:
            continue
        results.append((float(score), _state["chunks"][i]))
    return results
