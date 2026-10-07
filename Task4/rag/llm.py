"""Обёртка над OpenAI-совместимым API (proxy LiteLLM).

Один модуль, одна функция: `ask(messages) -> текст ответа`.
Внутренние «размышления» модели (reasoning_content) не используем
в ответе — только готовый content.
"""

from openai import OpenAI

from .config import SETTINGS

_client = OpenAI(base_url=SETTINGS.llm_url, api_key=SETTINGS.llm_api_key)


def ask(messages: list[dict[str, str]]) -> str:
    """Отправляет сообщения в LLM и возвращает текст ответа.

    messages — список {"role": "system"|"user"|"assistant", "content": ...}.

    Модель «думающая»: если весь бюджет max_tokens уйдёт на внутренние
    размышления, в content прийдёт None — повторяем с удвоенным бюджетом.
    """
    max_tokens = SETTINGS.max_tokens
    last_error: str = ""
    for _ in range(2):
        resp = _client.chat.completions.create(
            model=SETTINGS.llm_model,
            messages=messages,
            temperature=SETTINGS.temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        if content and content.strip():
            return content.strip()
        last_error = f"finish_reason={resp.choices[0].finish_reason}"
        max_tokens *= 2
    raise RuntimeError(f"LLM не вернула текст ({last_error})")
