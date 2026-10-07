#!/usr/bin/env python3
"""Telegram-бот RAG (aiogram 3).

Запуск:
    .venv/bin/python Task4/bot.py
Токен и (опционально) прокси — в .env в корне репозитория:
    BOT_TOKEN=...
    TELEGRAM_PROXY=socks5://localhost:2080   # если Telegram недоступен напрямую

Бот принимает обычные текстовые сообщения, пропускает их через тот же
RAGPipeline, что и консоль, и отвечает текстом (шаги + ответ).
"""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Message

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag.config import SETTINGS  # noqa: E402
from rag.pipeline import PIPELINE  # noqa: E402

TELEGRAM_LIMIT = 4096


def split_text(text: str) -> list[str]:
    """Режем длинный ответ на части <= TELEGRAM_LIMIT по границе абзаца."""
    parts = []
    while len(text) > TELEGRAM_LIMIT:
        cut = text.rfind("\n", 0, TELEGRAM_LIMIT)
        if cut < TELEGRAM_LIMIT // 2:
            cut = TELEGRAM_LIMIT
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


def make_bot() -> Bot:
    """Бот с сессией; если задан TELEGRAM_PROXY — все запросы к
    api.telegram.org идут через него (aiogram сам подберёт socks-коннектор,
    нужен пакет aiohttp-socks)."""
    session = (
        AiohttpSession(proxy=SETTINGS.telegram_proxy)
        if SETTINGS.telegram_proxy
        else None
    )
    return Bot(token=SETTINGS.bot_token, session=session)


bot = make_bot()
dp = Dispatcher()


@dp.message(F.text == "/start")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я RAG-бот по вселенной Aetheri. "
        "Спрашивай про персонажей, планеты, технологии и события — "
        "отвечаю только по базе знаний, если не знаю, скажу."
    )


@dp.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Просто напиши вопрос текстом, например:\n"
        "• кто такой Kael Drayden?\n"
        "• что такое Synth Flux?\n"
        "• что произошло в битве при Mossfell?"
    )


@dp.message(F.text)
async def on_text(message: Message) -> None:
    query = message.text.strip()
    await message.answer("Ищу в базе знаний…")
    # пайплайн блокирующий (эмбеддинги на CPU + 2 вызова LLM) — в поток
    result = await asyncio.to_thread(PIPELINE.answer, query)
    for part in split_text(result.text):
        await message.answer(part)


def main() -> None:
    if not SETTINGS.bot_token:
        raise SystemExit("нет BOT_TOKEN — укажите в .env или в окружении")
    dp.run_polling(bot)


if __name__ == "__main__":
    main()
