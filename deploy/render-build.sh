#!/usr/bin/env bash
set -euo pipefail
# Run from repository root, with Render's pinned Python and Node runtimes.
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
# TypeScript/Vite are build dependencies, even when the host sets NODE_ENV=production.
npm --prefix frontend ci --include=dev
npm --prefix frontend run build
