#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=backend
python3 -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
