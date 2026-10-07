#!/usr/bin/env bash
# Ежедневное обновление индекса (запускается cron-ом).
#
# Строка crontab:
#   0 6 * * * /home/mgatin/IdeaProjects/ya/architecture-pro-rag/Task6/run_update.sh
#
# Логи:
#   Task6/logs/update.log    — человекочитаемый (пишет сам скрипт)
#   Task6/logs/updates.jsonl — JSON, по одной записи на запуск
#   Task6/logs/cron.log      — stdout/stderr (на случай падения до старта скрипта)
set -u
cd /home/mgatin/IdeaProjects/ya/architecture-pro-rag
export RAG_INDEX_DIR="$PWD/Task6/index"
mkdir -p Task6/logs
"$PWD/.venv/bin/python" Task6/update_index.py >> Task6/logs/cron.log 2>&1
