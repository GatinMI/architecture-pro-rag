#!/usr/bin/env python3
"""Автоматическая проверка качества на золотом наборе (Задание 7).

Читает golden_questions.txt и прогоняет каждый вопрос через полный
пайплайн (переформулирование → поиск → порог → LLM), оценивая результат:

  known  — pass: бот ответил и в ответе есть не меньше половины
           ожидаемых ключевых слов (часть без пары — partial);
  gap    — clean: бот ответил «Не знаю»; если ответил по оставшимся
           фрагментам удалённой сущности — «leaky» (протечка пробела;
           не провал, а находка — записывается вместе с ответом);
  tricky — pass: бот ответил и основной ключевой слова в ответе есть;
           если поиск ушёл в нерелевантный источник и ответ не о теме —
           wrong_source.

Логирование: каждый вопрос дополнительно попадает в лог запросов
(RAG_QUERY_LOG=Task7/logs/queries.jsonl — встроен в пайплайн, Задание 7),
итоги теста — Task7/logs/golden_results.jsonl (строка на вопрос) и
сводная таблица на stdout.

Запуск:
    .venv/bin/python Task7/evaluate.py            # индекс Task7/index
    RAG_INDEX_DIR=... .venv/bin/python Task7/evaluate.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent  # Task7
REPO = BASE.parent
sys.path.insert(0, str(REPO / "Task4"))

# до импорта пайплайна: gap-индекс + лог запросов (можно переопределить)
os.environ.setdefault("RAG_INDEX_DIR", str(BASE / "index"))
os.environ.setdefault("RAG_QUERY_LOG", str(BASE / "logs" / "queries.jsonl"))

from rag.pipeline import PIPELINE  # noqa: E402

GOLDEN = BASE / "golden_questions.txt"
RESULTS = BASE / "logs" / "golden_results.jsonl"


def load_golden(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        qtype, query, rest = (p.strip() for p in line.split("|", 2))
        out.append(
            {
                "type": qtype,
                "query": query,
                "keywords": [k.strip() for k in rest.split(";") if k.strip()],
            }
        )
    return out


def evaluate(q: dict) -> dict:
    answer = PIPELINE.answer(q["query"])
    refused = not answer.known
    low = answer.text.lower()
    found = [k for k in q["keywords"] if k.lower() in low]
    completeness = len(found) / len(q["keywords"]) if q["keywords"] else None

    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "type": q["type"],
        "query": q["query"],
        "search_query": answer.search_query,
        "expected": q["keywords"],
        "refused": refused,
        "top_cos": answer.max_score,
        "sources": [
            {"doc": h[1]["doc"], "section": h[1]["section"]}
            for h in answer.hits[:3]
        ],
        "answer_len": len(answer.text),
        "keywords_found": found,
        "completeness": completeness,
        "answer": answer.text,
    }

    if q["type"] == "known":
        rec["verdict"] = (
            "pass"
            if (not refused and completeness is not None and completeness >= 0.5)
            else ("refused" if refused else "partial")
        )
    elif q["type"] == "gap":
        rec["verdict"] = "clean" if refused else "leaky"
    else:  # tricky
        rec["verdict"] = (
            "pass"
            if (not refused and found)
            else ("refused" if refused else "wrong_source")
        )
    return rec


def main() -> None:
    golden = load_golden(GOLDEN)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    recs = []
    for i, q in enumerate(golden, 1):
        print(f"[{i}/{len(golden)}] {q['type']:6} {q['query']}", flush=True)
        rec = evaluate(q)
        recs.append(rec)
        cos = (
            f"{rec['top_cos']:.3f}" if rec["top_cos"] is not None else "  -  "
        )
        comp = (
            f"к/с {rec['completeness']:.0%}"
            if rec["completeness"] is not None
            else ""
        )
        print(
            f"         {cos}  {rec['verdict']:12} {comp:8} "
            f"{rec['answer'][:70].replace(chr(10), ' ')}…"
        )
    with open(RESULTS, "a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n=== Итог ===")
    for qtype in ("known", "gap", "tricky"):
        rs = [r for r in recs if r["type"] == qtype]
        if not rs:
            continue
        good = sum(1 for r in rs if r["verdict"] in ("pass", "clean"))
        print(f"{qtype:7} {good}/{len(rs)}")
        for r in rs:
            if r["verdict"] not in ("pass", "clean"):
                cos = (
                    f"{r['top_cos']:.3f}"
                    if r["top_cos"] is not None
                    else "-"
                )
                print(f"  ! {r['verdict']}: {r['query']} (top {cos})")
    print(f"\nРезультаты: {RESULTS}")


if __name__ == "__main__":
    main()
