"""Бенчмарк локальной эмбеддинг-модели (Sentence-Transformers, CPU).

Генерирует ~300 синтетических «чанков» по ~250 слов (как в Задании 3:
100–300 слов на чанк) и замеряет:
- время загрузки модели,
- время эмбеддинга всего корпуса (warm + замер),
- throughput в чанках/сек и токенах/сек,
- размерность вектора и потребление RAM.

Запуск:  .venv/bin/python benchmarks/bench_embeddings.py
Результат: benchmarks/results/embeddings_bench.json
"""

import json
import os
import random
import time

N_CHUNKS = 300
WORDS_PER_CHUNK = 250
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

WORDS = ("digital twin scada industrial sensor pipeline kafka microservice "
         "terraform helm release onboarding incident rollback capacity "
         "embedding vector index chunk retrieval generation prompt "
         "architecture decision record policy audit metric latency "
         "staging production deploy migration schema migration query "
         "support ticket customer feedback model token context window "
         ).split()


def make_chunks():
    random.seed(42)
    chunks = []
    for i in range(N_CHUNKS):
        words = [random.choice(WORDS) for _ in range(WORDS_PER_CHUNK)]
        text = " ".join(words)
        # имитируем структуру документа: заголовок + абзацы
        title = f"Document {i}: {words[0].capitalize()} {words[1].capitalize()}"
        chunks.append(f"{title}\n\n{text}")
    return chunks


def main():
    from sentence_transformers import SentenceTransformer

    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME)
    load_s = time.perf_counter() - t0
    dim = model.get_embedding_dimension()
    n_params_m = round(sum(p.numel() for p in model[0].parameters()) / 1e6, 1)

    import psutil
    rss_before = psutil.Process(os.getpid()).memory_info().rss // (1024 * 1024)

    chunks = make_chunks()
    # warm-up (JIT, аллокации)
    model.encode(chunks[:8], batch_size=32, normalize_embeddings=True, show_progress_bar=False)

    t0 = time.perf_counter()
    embeddings = model.encode(chunks, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    encode_s = time.perf_counter() - t0

    total_words = sum(len(c.split()) for c in chunks)
    rss_after = psutil.Process(os.getpid()).memory_info().rss // (1024 * 1024)

    out = {
        "model": MODEL_NAME,
        "dim": dim,
        "params_M": n_params_m,
        "chunks": N_CHUNKS,
        "words_per_chunk": WORDS_PER_CHUNK,
        "total_words": total_words,
        "model_load_s": round(load_s, 2),
        "encode_s": round(encode_s, 2),
        "chunks_per_s": round(N_CHUNKS / encode_s, 1),
        "words_per_s": round(total_words / encode_s, 0),
        "rss_mb_after": rss_after,
        "rss_delta_mb": rss_after - rss_before,
    }
    out_path = os.path.join(os.path.dirname(__file__), "results", "embeddings_bench.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
