#!/bin/bash
set -euo pipefail
umask 077
TASK_REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$TASK_REPO"
export PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export TRUSTGATE_KEY_FILE="${TRUSTGATE_KEY_FILE:-$TASK_REPO/.secrets/openrouter_group9.key}"
exec "$TASK_REPO/.venv/bin/python" "$TASK_REPO/scripts/platforms/local/person2.py" "$@"
