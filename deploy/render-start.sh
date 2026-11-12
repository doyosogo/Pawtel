#!/usr/bin/env bash
set -euo pipefail
: "${PORT:?Render must supply PORT}"
cd backend
# No trust in arbitrary forwarding headers: identity/rate budgets never use XFF.
# Cookie security and exact external Origin/Host are configured explicitly.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 \
  --no-proxy-headers --no-access-log --log-config ../deploy/logging.json \
  --timeout-graceful-shutdown 30 --limit-concurrency 40
