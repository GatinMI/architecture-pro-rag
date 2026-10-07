#!/usr/bin/env python3
"""Скачивает страницы со starwars.fandom.com и сохраняет чистый текст.

Для каждой страницы из PAGES через MediaWiki API (action=parse) достаём
рендеренный HTML, вычищаем его (инфобоксы, навигационные шаблоны, сноски,
картинки, секции References / See also) и сохраняем в ../raw/<slug>.md.

Запуск:
    .venv/bin/python Task2/scripts/download_wiki.py
"""

import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup, NavigableString

API = "https://starwars.fandom.com/api.php"
HEADERS = {"User-Agent": "RAG-homework/1.0 (course project; one-off knowledge base build)"}
OUT_DIR = Path(__file__).resolve().parent.parent / "raw"

# 30+ страниц по ключевым сущностям: персонажи, планеты, корабли, технологии,
# события, организации и расы.
PAGES = [
    # Персонажи
    "Darth Vader",
    "Anakin Skywalker",
    "Luke Skywalker",
    "Leia Organa",
    "Han Solo",
    "Chewbacca",
    "Obi-Wan Kenobi",
    "Yoda",
    "Emperor Palpatine",
    "Boba Fett",
    "C-3PO",
    "R2-D2",
    "Qui-Gon Jinn",
    "Mace Windu",
    "Grogu",
    "Ahsoka Tano",
    "Kylo Ren",
    "Rey Skywalker",
    "Finn",
    # Планеты и локации
    "Tatooine",
    "Coruscant",
    "Hoth",
    "Endor",
    "Naboo",
    "Alderaan",
    "Kamino",
    "Geonosis",
    "Mustafar",
    "Dantooine",
    "Jakku",
    "Yavin 4",
    # Корабли и объекты
    "Death Star",
    "Millennium Falcon",
    "X-wing starfighter",
    "TIE/ln space superiority starfighter",
    "Star Destroyer",
    # Технологии
    "The Force",
    "Lightsaber",
    "Hyperdrive",
    "Turbolaser",
    "Tractor beam",
    "Holocron",
    # События
    "Battle of Yavin",
    "Battle of Hoth",
    "Battle of Endor",
    "Battle of Jakku",
    "Order 66",
    # Организации и расы
    "Jedi Order",
    "Sith",
    "Galactic Empire",
    "Rebel Alliance",
    "Clone trooper",
    "Inquisitorius",
    "Wookiee",
    "Twi'lek",
    "Hutt",
]

DROP_AFTER = {"References", "External links", "See also", "Further reading",
              "Bibliography", "Citations", "Notes and references",
              "Appearances", "Sources"}


def slugify(title: str) -> str:
    s = title.replace(" (Star Wars)", "")
    s = re.sub(r"[^\w\s'-]", "", s)
    return re.sub(r"[\s]+", "-", s).strip("-")


def fetch_html(session: requests.Session, title: str) -> str | None:
    """Возвращает HTML статьи или None, если страница не найдена."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "redirects": 1,
        "format": "json",
        "formatversion": "2",
    }
    resp = session.get(API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        print(f"  ! {title}: {data['error'].get('info', data['error'])}")
        return None
    return data["parse"]["text"]


def clean_html(html: str, title: str) -> str:
    """Превращает HTML вики-статьи в простой markdown-подобный текст."""
    soup = BeautifulSoup(html, "lxml")

    # Убираем мусор: стили, скрипты, инфобоксы (в т.ч. новый Fandom-инфобокс
    # в aside), навигационные шаблоны, оглавление, «for other uses»,
    # служебные шапки, сноски, кнопки правки, картинки.
    for sel in [
        "style", "script",
        "aside.portable-infobox",
        "table.infobox", "table.navbox", "table.nb2",
        "table.toccolours", "table.mw-editsection",
        "div.toc", "div.navbox", "div.disambig",
        "div.messagebox", "div.headertemplate", "div.hatnote",
        "div.thumb", "div.thumbinner",
        "sup.reference", "span.mw-editsection", "span.citation-needed",
        "div.reflist", "div.rellink", "figure",
    ]:
        for el in soup.select(sel):
            el.decompose()

    lines: list[str] = [f"# {title}"]
    drop_section = False

    for el in soup.select("div.mw-parser-output > *"):
        name = el.name
        text = el.get_text(" ", strip=True) if name != "ul" else None

        if name in ("h2", "h3", "h4"):
            text = re.sub(r"\[\]\s*$", "", el.get_text(" ", strip=True))
            if text in DROP_AFTER:
                drop_section = True
            if drop_section:
                continue
            level = {"h2": "##", "h3": "###", "h4": "####"}[name]
            lines += ["", f"{level} {text}", ""]
            continue

        if drop_section:
            continue

        if name == "p":
            t = el.get_text(" ", strip=True)
            if t:
                lines += [t, ""]
        elif name == "ul":
            items = []
            for li in el.find_all("li", recursive=False):
                t = li.get_text(" ", strip=True)
                if t:
                    items.append(f"- {t}")
            if items:
                lines += items + [""]
        elif name == "dl":
            for dt in el.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                t = (dt.get_text(" ", strip=True) + ": " +
                     (dd.get_text(" ", strip=True) if dd else "")).strip()
                if t:
                    lines.append(f"- {t}")
            lines.append("")
        elif name == "blockquote":
            t = el.get_text(" ", strip=True)
            if t:
                lines += [f"> {t}", ""]
        elif name == "div":
            classes = el.get("class") or []
            if "quote" in classes:
                t = el.get_text(" ", strip=True)
                if t:
                    lines += [f"> {t}", ""]
            else:
                # обёртки (spoiler, responsivediv): берём содержимое
                inner = "\n".join(
                    x.get_text(" ", strip=True)
                    for x in el.find_all(["p", "li"], recursive=True)
                ).strip()
                if inner:
                    lines += [inner, ""]
        elif name == "table":
            continue  # остальные таблицы (списки, сравнения) не берём
        elif isinstance(el, NavigableString):
            continue
        else:
            if text:
                lines += [text, ""]

    # Схлопываем повторяющиеся пустые строки.
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out + "\n"


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    session = requests.Session()
    ok, failed = 0, []

    for i, title in enumerate(PAGES, 1):
        print(f"[{i}/{len(PAGES)}] {title}", end=" ", flush=True)
        try:
            html = fetch_html(session, title)
            if html is None:
                failed.append(title)
                print("— нет страницы")
                continue
            text = clean_html(html, title)
            path = OUT_DIR / f"{slugify(title)}.md"
            path.write_text(text, encoding="utf-8")
            words = len(text.split())
            print(f"ok ({words} слов → {path.name})")
            ok += 1
        except Exception as e:
            failed.append(title)
            print(f"— ошибка: {e}")
        time.sleep(0.5)  # не спамим API

    print(f"\nГотово: {ok}/{len(PAGES)} страниц в {OUT_DIR}/")
    if failed:
        print("Не скачано:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
