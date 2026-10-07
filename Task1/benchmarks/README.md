# Бенчмарки (Задание 1)

Скрипты и результаты замеров, на которые ссылается отчёт
[`Task1/research.md`](../research.md).

| Скрипт | Что замеряет | Результат |
| --- | --- | --- |
| `bench_vecdb.py` | FAISS vs ChromaDB vs Qdrant: build, save/load, латентность поиска (p50/p95), RAM, размер индекса | `results/vecdb_bench.json` |
| `bench_embeddings.py` | Локальная модель `all-MiniLM-L6-v2` (CPU): загрузка, throughput, RAM | `results/embeddings_bench.json` |

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install faiss-cpu chromadb qdrant-client sentence-transformers numpy psutil

python benchmarks/bench_vecdb.py
python benchmarks/bench_embeddings.py
```

## Параметры замера (на момент выполнения задания)

- Машина: 32 ядра CPU, 62 ГБ RAM, без GPU (эмбеддинги считаются на CPU —
  наихудший реалистичный сценарий для локального инференса).
- Индекс: 10 000 векторов × 384 dim (размерность MiniLM), 200 запросов, k=5.
- Корпус для эмбеддингов: 300 чанков × ~250 слов (формат чанков как в Задании 3).

Результаты чувствительны к железу и объёму: при росте базы до сотен тысяч
чанков (масштаб реальной БЗ QuantumForge) цифры поиска по flat-индексу
FAISS линейно вырастут — см. раздел «Векторные БД» в отчёте.
