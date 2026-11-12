#!/usr/bin/env bash
set -euo pipefail
# Run from repository root, with Render's pinned Python and Node runtimes.
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
npm --prefix frontend ci
npm --prefix frontend run build
