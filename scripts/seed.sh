#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=backend
python3 backend/scripts/seed_neon_docs.py
