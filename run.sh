#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d venv ]; then
    python3 -m venv venv
    venv/bin/pip install -q -r requirements.txt
fi

[ -f .env ] || cp .env.example .env

exec venv/bin/waitress-serve \
    --listen="${MONITOR_HOST:-0.0.0.0}:${MONITOR_PORT:-5000}" \
    --threads=4 \
    monitor:app
