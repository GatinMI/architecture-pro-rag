#!/usr/bin/env python3
"""Собирает FAISS-индекс из базы знаний Задания 2.

* документы: Task2/knowledge_base/docs/*.md (56 шт.);
* чанки: 100–300 слов (цель 200): документ режется по H2-секциям,
  короткие секции сливаются с предыдущими, внутри секции
  RecursiveCharacterTextSplitter режет по абзацам, а абзацы
  упаковываются в чанки; хвост короче 100 слов вливается в предыдущий;
* метаданные чанка: файл, заголовок (H1), секция (H2), смещение в
  словах, id чанка — чтобы бот мог цитировать источник;
* эмбеддинги: all-MiniLM-L6-v2 (384D, L2-нормализованные), CPU;
* индекс: FAISS IndexFlatIP (косинусное расстояние на нормализованных
  векторах) — решение Задания 1.

Результат:
    Task3/index/faiss.index   — сам индекс
    Task3/index/chunks.jsonl  — метаданные + текст чанков (по строке на чанк)

Запуск:
    .venv/bin/python Task3/build_index.py
"""

import json
import re
import time
from pathlib import Path

import faiss
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE / "Task2" / "knowledge_base" / "docs"
INDEX_DIR = Path(__file__).resolve().parent / "index"

MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_WORDS = 200
CHUNK_OVERLAP = 50
MIN_CHUNK_WORDS = 100  # нижняя граница из ТЗ (100–300 слов)
BATCH_SIZE = 64

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# считаем размер в словах (а не в символах)
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_WORDS,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=lambda t: len(t.split()),
)


def split_sections(text: str) -> list[tuple[str, str]]:
    """(заголовок_секции, текст_секции) по H2; до первого заголовка —
    «(вступление)». Короткие секции (< MIN_CHUNK_WORDS слов) сливаются
    с предыдущей, чтобы не было чанков-осколков."""
    raw: list[tuple[str, str]] = []
    current = "(вступление)"
    buf: list[str] = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 2:
            if buf:
                raw.append((current, "\n".join(buf)))
            current = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        raw.append((current, "\n".join(buf)))
    raw = [(h, t) for h, t in raw if t.strip()]

    merged: list[tuple[str, str]] = []
    for h, t in raw:
        if merged and len(t.split()) < MIN_CHUNK_WORDS:
            ph, pt = merged[-1]
            merged[-1] = (ph, pt + "\n" + t)
        else:
            merged.append((h, t))
    if len(merged) > 1 and len(merged[0][1].split()) < MIN_CHUNK_WORDS:
        merged[1] = (merged[1][0], merged[0][1] + "\n" + merged[1][1])
        merged.pop(0)
    return merged


def part_offsets(sec_words: list[str], parts: list[str]) -> list[int]:
    """Смещения частей в словном потоке секции.

    Части RecursiveCharacterTextSplitter перекрываются (не влезший остаток
    уносится в следующую), поэтому накопление не работает — каждое
    смещение ищется по сигнатуре первых слов, поиск идёт только вперёд.
    """
    offs: list[int] = []
    pointer = 0
    n = len(sec_words)
    for p in parts:
        pw = p.split()
        sig = pw[:8]
        found = -1
        for i in range(pointer, min(n, pointer + 1500)):
            if sec_words[i : i + len(sig)] == sig:
                found = i
                break
        if found < 0:
            found = pointer  # оценка — лучше, чем сломанное накопление
        offs.append(found)
        pointer = found + max(1, len(pw) - CHUNK_OVERLAP)
    return offs


def chunk_unit(sec_text: str) -> list[tuple[str, int]]:
    """Чанки внутри секции: (текст, смещение в словах от начала секции).

    Сплиттер на коротких параграфах вики отдаёт части по 90–160 слов,
    поэтому части упаковываются в чанки до CHUNK_WORDS слов;
    хвост короче MIN_CHUNK_WORDS слов вливается в предыдущий чанк
    (итого < 300 слов).
    """
    parts = SPLITTER.split_text(sec_text)
    poffs = part_offsets(sec_text.split(), parts)
    out: list[tuple[str, int]] = []
    cur: list[tuple[str, int]] = []

    def emit() -> None:
        if not cur:
            return
        out.append((" ".join(p for p, _ in cur), min(po for _, po in cur)))
        cur.clear()

    for p, po in zip(parts, poffs):
        w = len(p.split())
        cur_w = sum(len(q.split()) for q, _ in cur)
        if cur and (
            (cur_w >= MIN_CHUNK_WORDS and cur_w + w > CHUNK_WORDS)
            or cur_w + w > 300
        ):
            emit()
        cur.append((p, po))
    if cur and (sum(len(p.split()) for p, _ in cur) >= MIN_CHUNK_WORDS or not out):
        emit()
    elif cur:
        # хвост: первая часть перекрывается с концом предыдущего чанка —
        # убираем повторяющийся кусок (совпадение суффикса/префикса)
        prev_text, prev_off = out[-1]
        prev_words = prev_text.split()
        first = cur[0][0].split()
        m = 0
        for k in range(min(120, len(prev_words), len(first)), 0, -1):
            if prev_words[-k:] == first[:k]:
                m = k
                break
        tail_first = " ".join(first[m:])
        rest = " ".join(p for p, _ in cur[1:])
        tail_text = " ".join([tail_first, rest]).strip()
        if len((prev_text + " " + tail_text).split()) <= 300:
            out[-1] = (prev_text + " " + tail_text, prev_off)
        else:
            emit()
    return out


def build() -> None:
    t0 = time.time()
    files = sorted(DOCS_DIR.glob("*.md"))
    assert files, f"нет документов в {DOCS_DIR}"

    chunks: list[dict] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        m1 = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m1.group(1).strip() if m1 else f.stem

        base = 0
        for sec_name, sec_text in split_sections(text):
            sec_words = sec_text.split()
            for ch, off in chunk_unit(sec_text):
                chunks.append(
                    {
                        "id": f"{f.stem}#{len(chunks)}",
                        "doc": f.name,
                        "title": title,
                        "section": sec_name,
                        "word_start": base + off,
                        "text": ch,
                    }
                )
            base += len(sec_words)

    print(f"Документов: {len(files)}, чанков: {len(chunks)}")
    print(f"Средний чанк: {sum(len(c['text'].split()) for c in chunks) // len(chunks)} слов")

    print(f"Загружаю модель {MODEL_NAME} (CPU)...")
    t1 = time.time()
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    print("Генерирую эмбеддинги...")
    emb = model.encode(
        [c["text"] for c in chunks],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    emb = np.ascontiguousarray(emb, dtype=np.float32)
    t_emb = time.time() - t1

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)

    INDEX_DIR.mkdir(exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
    with open(INDEX_DIR / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(
        f"\nГотово за {time.time() - t0:.0f} с "
        f"(эмбеддинги: {t_emb:.0f} с, {len(chunks) / t_emb:.0f} чанков/с)"
    )
    print(f"Индекс: {INDEX_DIR / 'faiss.index'} ({index.ntotal} векторов, {index.d}D)")
    print(f"Чанки:  {INDEX_DIR / 'chunks.jsonl'}")


if __name__ == "__main__":
    build()
