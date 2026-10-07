"""Сборка промпта: CoT в system-промпте, few-shot примеры, контекст.

Структура сообщений:
    system — роль, правила, CoT-указание, 1–2 примера «вопрос → шаги → ответ»;
    user   — фрагменты из базы (с источниками) + вопрос пользователя.
"""

from .config import SETTINGS
from . import guard


def load_few_shot() -> list[dict]:
    """Примеры из few_shot_examples.json (вопрос, ответ, откуда взяли)."""
    import json

    if not SETTINGS.few_shot_file.exists():
        return []
    with open(SETTINGS.few_shot_file, encoding="utf-8") as fh:
        return json.load(fh)


def _format_few_shot(examples: list[dict]) -> str:
    blocks = []
    for ex in examples:
        blocks.append(f"Q: {ex['question']}\nA:\n{ex['answer']}")
    return "\n\n".join(blocks)


def build_messages(query: str, hits: list[tuple[float, dict]]) -> list[dict]:
    system = (
        "Ты — справочный ассистент по вымышленной вселенной Aetheri. "
        "Опирайся ТОЛЬКО на фрагменты базы знаний, приведённые в сообщении; "
        "фактов, которых там нет, не выдумывай.\n"
        "Сначала размышляй, потом отвечай: напиши 2–4 коротких шага, "
        "как искал ответ, а затем на отдельной строке 'Ответ:' и сам ответ "
        "на языке вопроса.\n"
        "Если во фрагментах нет ответа на вопрос, напиши "
        "'Ответ: Не знаю — в базе знаний этого нет.'\n"
    )
    examples = load_few_shot()
    if examples:
        system += "\nПримеры хорошего ответа:\n" + _format_few_shot(examples) + "\n"
    if SETTINGS.guard_prompt:
        system += "\n" + guard.PROMPT_SHIELD + "\n"

    fragments = []
    for i, (score, chunk) in enumerate(hits, 1):
        fragments.append(
            f"[{i}] {chunk['doc']} · «{chunk['title']}» · "
            f"секция «{chunk['section']}» (близость {score:.2f})\n{chunk['text']}"
        )
    user = (
        "Фрагменты базы знаний, найденные по вопросу (в порядке убывания "
        "релевантности):\n" + "\n\n".join(fragments)
        + f"\n\nВопрос: {query}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
