#!/usr/bin/env bash
set -euo pipefail

BROKER_URL="${CELERY_BROKER_URL:-redis://127.0.0.1:6379/0}"

exec "$(dirname "$0")/../.venv/bin/celery" -A config worker -l info --broker="$BROKER_URL"
