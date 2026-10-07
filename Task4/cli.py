#!/usr/bin/env python3
"""Консольный интерфейс RAG-пайплайна (то же, что отвечает Telegram-бот).

Интерактивно:
    .venv/bin/python Task4/cli.py
Одним запросом:
    .venv/bin/python Task4/cli.py "кто такой Pip?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag.pipeline import PIPELINE  # noqa: E402


def show(query: str) -> None:
    result = PIPELINE.answer(query)
    if result.search_query != query:
        print(f"[поиск]  «{result.search_query}»")
    if result.hits:
        top = result.hits[0]
        print(
            f"[найдено] топ-{len(result.hits)}, лучший: "
            f"{top[1]['doc']} · «{top[1]['title']}» · "
            f"секция «{top[1]['section']}» (cos {top[0]:.3f})"
        )
    else:
        print("[найдено] ничего")
    print()
    print(result.text)


def main() -> None:
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
        return

    print("RAG-бот (консоль). /exit — выход.\n")
    while True:
        try:
            query = input("Вопрос> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not query:
            continue
        if query in ("/exit", "/quit"):
            return
        show(query)
        print()


if __name__ == "__main__":
    main()
