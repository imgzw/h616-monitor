#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export H616_CAMERA_DEVICE="${H616_CAMERA_DEVICE:-/dev/video0}"
export H616_RECORDINGS_DIR="${H616_RECORDINGS_DIR:-/opt/h616-monitor/recordings}"
export H616_GO2RTC_HOST="${H616_GO2RTC_HOST:-127.0.0.1}"
export H616_GO2RTC_PORT="${H616_GO2RTC_PORT:-1984}"

exec uvicorn app.main:app --host "${H616_HOST:-0.0.0.0}" --port "${H616_PORT:-8000}" --workers 1