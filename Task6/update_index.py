#!/usr/bin/env python3
"""Ежедневное обновление базы знаний (Задание 6).

Источник данных — папка Task6/inbox/: в неё появляются новые .md-файлы
(симулирует «подхват» из S3 / Git-репозитория / Drive — из любого
источника, откуда приходят новые документы). Скрипт:

* сравнивает файлы inbox с манифестом (Task6/state/manifest.json)
  по sha256;
* новые файлы: чанкует по схеме Задания 3 (split_sections + chunk_unit)
  и пробегает тем же эмбеддером (all-MiniLM-L6-v2);
* изменённые: старые чанки удаляет, новые добавляет;
* удалённые (были в манифесте, пропали из inbox): чанки удаляет —
  индекс пересобирается из оставшихся векторов;
* сохраняет атомарно (tmp-файл + rename) — при сбое живая копия
  индекса не повредится;
* пишет лог в Task6/logs/update.log (человекочитаемый) и
  Task6/logs/updates.jsonl (JSON, одна строка на запуск).

При ошибке на файле: ошибка пишется в лог, остальные файлы
обрабатываются, exit code ненулевой — cron повторит завтра.
Скрипт идемпотентен: уже проиндексированные и неизменённые файлы
пропускаются, поэтому повторный запуск безопасен.

Первый запуск (индекс ещё не создан):
    .venv/bin/python Task6/update_index.py --init-from Task5/index

Дальше:
    .venv/bin/python Task6/update_index.py
    RAG_INDEX_DIR=/path .venv/bin/python Task6/update_index.py
"""

import hashlib
import json
import os
import re
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).resolve().parent  # Task6
REPO = BASE.parent

# та же схема чанков, что и в Задании 3
sys.path.insert(0, str(REPO / "Task3"))
from build_index import chunk_unit, split_sections  # noqa: E402

INBOX = BASE / "inbox"
MANIFEST = BASE / "state" / "manifest.json"
LOG_DIR = BASE / "logs"
INDEX_DIR = Path(os.environ.get("RAG_INDEX_DIR", str(BASE / "index")))

MODEL_NAME = "all-MiniLM-L6-v2"
DIM = 384
BATCH_SIZE = 64


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc_to_chunks(path: Path) -> list[dict]:
    """Чанки одного документа (схема Задания 3), id — `<файл>#<n>`."""
    text = path.read_text(encoding="utf-8")
    m1 = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    title = m1.group(1).strip() if m1 else path.stem
    out: list[dict] = []
    base = 0
    for sec, sec_text in split_sections(text):
        for ch, off in chunk_unit(sec_text):
            out.append(
                {
                    "id": f"{path.stem}#{len(out)}",
                    "doc": path.name,
                    "title": title,
                    "section": sec,
                    "word_start": base + off,
                    "text": ch,
                }
            )
        base += len(sec_text.split())
    return out


def rebuild_index(old_index: faiss.IndexFlatIP, keep_mask: list[bool]) -> faiss.IndexFlatIP:
    """Новый IndexFlatIP из векторов, оставшихся по маске (IndexFlatIP
    не умеет удалять векторы — пересобираем, при нашем размере это ~секунды)."""
    kept = [old_index.reconstruct(i) for i, keep in enumerate(keep_mask) if keep]
    index = faiss.IndexFlatIP(DIM)
    if kept:
        index.add(np.ascontiguousarray(np.vstack(kept), dtype=np.float32))
    return index


def run() -> int:
    started = datetime.now()
    lines: list[str] = []

    def log(msg: str) -> None:
        lines.append(f"{ts()} {msg}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (BASE / "state").mkdir(exist_ok=True)
    log(f"запуск: индекс={INDEX_DIR}, inbox={INBOX}")

    # первичная инициализация: индекс копировать от готового
    if not (INDEX_DIR / "faiss.index").exists() and "--init-from" in sys.argv:
        src = Path(sys.argv[sys.argv.index("--init-from") + 1])
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(src / "faiss.index", INDEX_DIR / "faiss.index")
        shutil.copy(src / "chunks.jsonl", INDEX_DIR / "chunks.jsonl")
        log(f"индекс инициализирован копией из {src}")

    errors: list[str] = []
    try:
        if not (INDEX_DIR / "faiss.index").exists():
            raise RuntimeError(
                f"нет индекса в {INDEX_DIR} — создайте (Task3/build_index.py) "
                "или запустите с --init-from"
            )

        model = SentenceTransformer(MODEL_NAME, device="cpu")
        index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
        with open(INDEX_DIR / "chunks.jsonl", encoding="utf-8") as fh:
            chunks = [json.loads(line) for line in fh]
        manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

        inbox_files = {f.name: f for f in sorted(INBOX.glob("*.md"))}
        added, changed, removed, skipped = [], [], [], []
        pending: dict[str, tuple[list[dict], np.ndarray, str]] = {}
        to_remove: set[str] = set()

        for name, f in inbox_files.items():
            try:
                h = sha256_of(f)
                if name in manifest and manifest[name].get("sha256") == h:
                    skipped.append(name)
                    continue
                new_chunks = doc_to_chunks(f)
                vecs = np.ascontiguousarray(
                    model.encode(
                        [c["text"] for c in new_chunks],
                        batch_size=BATCH_SIZE,
                        normalize_embeddings=True,
                    ),
                    dtype=np.float32,
                )
                if name in manifest:
                    to_remove.update(manifest[name]["chunks"])
                    changed.append(name)
                    log(f"изменён: {name} → {len(new_chunks)} чанков")
                else:
                    added.append(name)
                    log(f"новый: {name} → {len(new_chunks)} чанков")
                pending[name] = (new_chunks, vecs, h)
            except Exception as exc:  # файл битый — не валить весь запуск
                errors.append(f"{name}: {exc}")
                log(f"ОШИБКА {name}: {exc}")

        for name, meta in manifest.items():
            if name not in inbox_files:
                to_remove.update(meta["chunks"])
                removed.append(name)
                log(f"удалён источник: {name}")

        if to_remove:
            mask = [c["id"] not in to_remove for c in chunks]
            n_kept = sum(mask)
            index = rebuild_index(index, mask)
            chunks = [c for c, keep in zip(chunks, mask) if keep]
            log(f"индекс пересобран: -{len(to_remove)} чанков (осталось {n_kept})")

        for name, (new_chunks, vecs, h) in pending.items():
            index.add(vecs)
            chunks.extend(new_chunks)
            manifest[name] = {
                "sha256": h,
                "chunks": [c["id"] for c in new_chunks],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }

        # атомарное сохранение: tmp-файлы, затем rename поверх живых
        tmp_index = INDEX_DIR / "faiss.index.tmp"
        tmp_jsonl = INDEX_DIR / "chunks.jsonl.tmp"
        faiss.write_index(index, str(tmp_index))
        with open(tmp_jsonl, "w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        os.replace(tmp_index, INDEX_DIR / "faiss.index")
        os.replace(tmp_jsonl, INDEX_DIR / "chunks.jsonl")
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        finished = datetime.now()
        n_new_chunks = sum(len(v[0]) for v in pending.values())
        log(
            f"index updated at {finished.strftime('%Y-%m-%d %H:%M')}, "
            f"{len(added)} files added, {len(changed)} changed, "
            f"{len(removed)} removed, {n_new_chunks} chunks added, "
            f"index={index.ntotal} chunks, {len(errors)} errors"
        )
        with open(LOG_DIR / "update.log", "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        record = {
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="seconds"),
            "duration_s": round((finished - started).total_seconds(), 1),
            "index_dir": str(INDEX_DIR),
            "files_added": added,
            "files_changed": changed,
            "files_removed": removed,
            "files_skipped": len(skipped),
            "chunks_added": n_new_chunks,
            "index_size": index.ntotal,
            "errors": errors,
        }
        with open(LOG_DIR / "updates.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        print("\n".join(lines))
        return 1 if errors else 0
    except Exception:
        log("АВАРИЯ:\n" + traceback.format_exc())
        with open(LOG_DIR / "update.log", "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(lines[-1], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
