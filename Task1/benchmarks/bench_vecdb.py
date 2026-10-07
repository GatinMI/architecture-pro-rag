"""Бенчмарк векторных баз: FAISS vs ChromaDB.

Замеряет:
- время создания индекса (bulk add),
- время сохранения/загрузки (peristance),
- латентность поиска (p50 / p95 / mean) на N случайных запросах,
- потребление RAM (RSS процесса).

Запуск:  .venv/bin/python benchmarks/bench_vecdb.py
Результат: benchmarks/results/vecdb_bench.json + таблица в stdout.
"""

import json
import os
import random
import time

import numpy as np
import psutil

N = 10_000  # количество векторов (порядка ~10K чанков БЗ)
D = 384     # размерность (all-MiniLM-L6-v2)
QUERIES = 200
K = 5
WORKDIR = os.path.join(os.path.dirname(__file__), "tmp")


def percentiles(lat: list[float]) -> dict:
    lat = sorted(lat)
    return {
        "mean_ms": round(np.mean(lat), 3),
        "p50_ms": round(np.percentile(lat, 50), 3),
        "p95_ms": round(np.percentile(lat, 95), 3),
        "max_ms": round(max(lat), 3),
    }


def rss_mb() -> int:
    return psutil.Process(os.getpid()).memory_info().rss // (1024 * 1024)


def make_vectors():
    rng = np.random.default_rng(42)
    vecs = rng.normal(size=(N, D)).astype("float32")
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)  # косинусное пространство
    queries = rng.normal(size=(QUERIES, D)).astype("float32")
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)
    return vecs, queries


def bench_faiss(vecs, queries):
    import faiss

    rss_before = rss_mb()
    t0 = time.perf_counter()
    index = faiss.IndexFlatIP(D)  # normalized vectors -> cosine similarity
    index.add(vecs)
    build_s = time.perf_counter() - t0

    path = os.path.join(WORKDIR, "faiss.index")
    t0 = time.perf_counter()
    faiss.write_index(index, path)
    save_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    index = faiss.read_index(path)
    load_s = time.perf_counter() - t0

    lat = []
    for q in queries:
        t0 = time.perf_counter()
        index.search(q.reshape(1, -1), K)
        lat.append((time.perf_counter() - t0) * 1000)

    return {
        "engine": "faiss (IndexFlatIP, in-memory, single file)",
        "build_s": round(build_s, 3),
        "save_s": round(save_s, 3),
        "load_s": round(load_s, 3),
        "search": percentiles(lat),
        "index_file_mb": round(os.path.getsize(path) / 1e6, 2),
        "rss_mb_after": rss_mb(),
        "rss_delta_mb": rss_mb() - rss_before,
    }


def bench_chroma(vecs, queries):
    import chromadb
    import shutil

    persist_dir = os.path.join(WORKDIR, "chroma")
    shutil.rmtree(persist_dir, ignore_errors=True)
    client = chromadb.PersistentClient(path=persist_dir)
    col = client.create_collection(
        "bench", metadata={"hnsw:space": "cosine"}
    )

    ids = [f"doc_{i}" for i in range(N)]
    metas = [{"chunk_id": i, "source": f"file_{i % 100}.md"} for i in range(N)]
    rss_before = rss_mb()
    t0 = time.perf_counter()
    BATCH = 4000  # лимит chroma на одну add-партию
    for i in range(0, N, BATCH):
        col.add(ids=ids[i:i + BATCH], embeddings=vecs[i:i + BATCH].tolist(),
                metadatas=metas[i:i + BATCH])
    build_s = time.perf_counter() - t0

    # "persist" для Chroma == сохранение на диск при каждом write; замеряем
    # восстановление (reload) коллекции из той же папки.
    t0 = time.perf_counter()
    client2 = chromadb.PersistentClient(path=persist_dir)
    col2 = client2.get_collection("bench")
    load_s = time.perf_counter() - t0

    lat = []
    for q in queries:
        t0 = time.perf_counter()
        col2.query(query_embeddings=[q.tolist()], n_results=K)
        lat.append((time.perf_counter() - t0) * 1000)

    return {
        "engine": "chroma (PersistentClient, HNSW, SQLite on disk)",
        "build_s": round(build_s, 3),
        "save_s": None,  # write-through, отдельного save() нет
        "load_s": round(load_s, 3),
        "search": percentiles(lat),
        "index_file_mb": None,  # данные распределены по SQLite + сегментам
        "rss_mb_after": rss_mb(),
        "rss_delta_mb": rss_mb() - rss_before,
    }


def bench_qdrant(vecs, queries):
    import shutil
    from qdrant_client import QdrantClient, models

    path = os.path.join(WORKDIR, "qdrant")
    shutil.rmtree(path, ignore_errors=True)
    client = QdrantClient(path=path)  # local storage mode (Rust-движок в процессе)
    client.create_collection(
        "bench",
        vectors_config=models.VectorParams(size=D, distance=models.Distance.COSINE),
    )

    metas = [{"chunk_id": i, "source": f"file_{i % 100}.md"} for i in range(N)]
    points = [
        models.PointStruct(id=i, vector=vecs[i].tolist(), payload=metas[i])
        for i in range(N)
    ]
    rss_before = rss_mb()
    t0 = time.perf_counter()
    BATCH = 1000
    for i in range(0, N, BATCH):
        client.upsert("bench", points=points[i:i + BATCH])
    build_s = time.perf_counter() - t0

    # "persist" для Qdrant — запись на диск при каждом upsert;
    # замеряем перечитывание из той же папки новым клиентом.
    t0 = time.perf_counter()
    client.close()
    client = QdrantClient(path=path)
    load_s = time.perf_counter() - t0

    lat = []
    for q in queries:
        t0 = time.perf_counter()
        client.query_points("bench", query=q.tolist(), limit=K, with_payload=False)
        lat.append((time.perf_counter() - t0) * 1000)

    return {
        "engine": "qdrant (local storage mode, HNSW by default)",
        "build_s": round(build_s, 3),
        "save_s": None,  # write-through
        "load_s": round(load_s, 3),
        "search": percentiles(lat),
        "index_file_mb": None,  # данные в сегментах под папкой storage
        "rss_mb_after": rss_mb(),
        "rss_delta_mb": rss_mb() - rss_before,
    }


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    vecs, queries = make_vectors()
    results = []
    for bench in (bench_faiss, bench_chroma, bench_qdrant):
        try:
            results.append(bench(vecs, queries))
        except Exception as e:  # noqa: BLE001
            results.append({"engine": bench.__name__, "error": str(e)})

    out = {
        "config": {"n": N, "dim": D, "queries": QUERIES, "k": K,
                   "cpu": os.cpu_count(), "host": "local dev machine (32 cores, 62GB RAM)"},
        "results": results,
    }
    out_path = os.path.join(os.path.dirname(__file__), "results", "vecdb_bench.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    random.seed(42)
    main()
