"""Логирование каждого запроса к пайплайну (Задание 7).

Включается переменной RAG_QUERY_LOG (путь к JSONL-файлу); пусто —
логирование выключено. Каждый запрос — одна строка:

    ts           — timestamp;
    query        — запрос пользователя;
    search_query — поисковый запрос после переформулирования;
    chunks_found — сколько чанков найдено (до порога);
    top_cos      — лучшая косинусная близость (None, если ничего не найдено);
    sources      — источники топ-3 хитов (doc / title / section);
    answer_len   — длина ответа;
    refused      — пайплайн ответил «не знаю» (ничего не найдено
                   или лучший хит ниже порога);
    ok           — флаг «успешный ответ»: не отказ и длина ответа выше
                   минимума (грубая проверка осмысленности; детальная
                   оценка по золотому набору — в Task7/evaluate.py).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .config import SETTINGS

if TYPE_CHECKING:  # чтобы не было циклического импорта
    from .pipeline import Answer

# «успешный» ответ — не короче этой длины (отказ-фраза ~90 символов,
# но без «Ответ:» и по сути пустой; нормальные ответы — сотни символов)
MIN_OK_LEN = 150


def log(query: str, answer: "Answer") -> None:
    path = SETTINGS.query_log
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    top = answer.hits[0] if answer.hits else None
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "search_query": answer.search_query,
        "chunks_found": len(answer.hits),
        "top_cos": round(top[0], 3) if top else None,
        "sources": [
            {
                "doc": h[1]["doc"],
                "title": h[1]["title"],
                "section": h[1]["section"],
            }
            for h in answer.hits[:3]
        ],
        "answer_len": len(answer.text),
        "refused": not answer.known,
        "ok": bool(answer.known and len(answer.text) >= MIN_OK_LEN),
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
