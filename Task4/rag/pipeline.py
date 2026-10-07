"""RAG-пайплайн: запрос → переформулирование → поиск → промпт → LLM.

Порядок шагов (все видны в выводе cli.py):
1. запрос пользователя (на его языке);
2. переформулирование на язык корпуса (английский) — один быстрый вызов
   LLM; без этого русские запросы почти не работают, т.к. MiniLM не
   переводит (проблема отмечена в Задании 3);
3. поиск топ-k чанков в FAISS;
4. проверка порога: если лучший фрагмент далек по смыслу — «не знаю»;
5. сборка промпта (few-shot + CoT + фрагменты) и вызов LLM.
"""

import re
from dataclasses import dataclass, field

from . import guard, llm, prompt
from .config import SETTINGS
from .retriever import search as faiss_search

REWRITE_SYSTEM = (
    "Вопрос пользователя относится к вымышленной вселенной Aetheri "
    "(персонажи, планеты, технологии, события). Переведи его на английский "
    "язык для поиска в англоязычной базе знаний. Названия персонажей, "
    "планет, фракций и технологий оставь в том виде, как в вопросе. "
    "Ответь только одним английским вопросом, без пояснений."
)


@dataclass
class Answer:
    text: str
    known: bool
    search_query: str = ""
    hits: list[tuple[float, dict]] = field(default_factory=list)

    @property
    def max_score(self) -> float | None:
        return self.hits[0][0] if self.hits else None


def rewrite_query(query: str) -> str:
    """Перевод вопроса на язык корпуса. Если вопрос уже на латинице —
    переформулировать нечего, возвращаем как есть."""
    if not re.search(r"[а-яА-ЯёЁ]", query):
        return query
    resp = llm.ask(
        [
            {"role": "system", "content": REWRITE_SYSTEM},
            {"role": "user", "content": query},
        ]
    )
    return resp.splitlines()[0].strip() or query


class RAGPipeline:
    def answer(self, query: str) -> Answer:
        search_q = rewrite_query(query)
        hits = faiss_search(search_q, SETTINGS.top_k)

        # слои защиты от инъекций (Задание 5): очистка текста +
        # выкидывание вредоносных чанков; порог — по оставшимся
        if SETTINGS.guard_sanitize or SETTINGS.guard_filter:
            hits = guard.apply(
                hits,
                sanitize_on=SETTINGS.guard_sanitize,
                filter_on=SETTINGS.guard_filter,
            )

        if not hits or hits[0][0] < SETTINGS.score_threshold:
            return Answer(
                text=(
                    "Не знаю — в базе знаний не нашлось фрагментов, "
                    "которые отвечали бы на этот вопрос."
                ),
                known=False,
                search_query=search_q,
                hits=hits,
            )

        messages = prompt.build_messages(query, hits)
        text = llm.ask(messages)
        return Answer(
            text=text, known=True, search_query=search_q, hits=hits
        )


PIPELINE = RAGPipeline()
