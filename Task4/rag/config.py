"""Настройки пайплайна: всё берётся из .env в корне репозитория.

Переменные:
    LITELLM_URL      — базовый URL OpenAI-совместимого API (proxy LiteLLM)
    LITELLM_API_KEY  — ключ API
    LLM_MODEL        — имя модели, например selectel/qwen/qwen3.8-27b
    BOT_TOKEN        — токен Telegram-бота (только для bot.py)
    TELEGRAM_PROXY   — опционально, прокси для Telegram: socks5://host:port
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent  # Task4/
REPO_ROOT = BASE.parent

load_dotenv(REPO_ROOT / ".env")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"нет переменной {name} — проверьте .env в корне репозитория"
        )
    return value


@dataclass(frozen=True)
class Settings:
    llm_url: str = _required("LITELLM_URL")
    llm_api_key: str = _required("LITELLM_API_KEY")
    llm_model: str = _required("LLM_MODEL")
    bot_token: str = os.environ.get("BOT_TOKEN", "").strip()
    # опциональный прокси для Telegram (например socks5://localhost:2080);
    # пусто — прямые запросы к api.telegram.org
    telegram_proxy: str = os.environ.get("TELEGRAM_PROXY", "").strip()

    # индекс из Задания 3
    index_dir: Path = REPO_ROOT / "Task3" / "index"
    embedding_model: str = "all-MiniLM-L6-v2"

    # поиск
    top_k: int = 5
    # если максимальная косинусная близость ниже порога — «не знаю».
    # По замерам: запросы из базы дают 0.49–0.65, вне базы — не выше 0.33
    score_threshold: float = 0.40

    # LLM. Бюджет большой: модель «думающая», reasoning тоже ест токены,
    # и если content не помещается — ответ теряется
    temperature: float = 0.2
    max_tokens: int = 4096

    few_shot_file: Path = BASE / "few_shot_examples.json"


SETTINGS = Settings()
