#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
pg_bin=/opt/homebrew/opt/postgresql@17/bin

if [[ ! -d .local/postgres ]]; then
  echo "Local PostgreSQL is not initialized in .local/postgres." >&2
  exit 1
fi
if [[ ! -x .venv/bin/python || ! -f platform_frontend/dist/index.html ]]; then
  echo "Install the Python dependencies and build platform_frontend first." >&2
  exit 1
fi

if ! "$pg_bin/pg_ctl" -D .local/postgres status >/dev/null 2>&1; then
  "$pg_bin/pg_ctl" -D .local/postgres \
    -o '-h 127.0.0.1 -p 55433' -l .local/postgres.log start
fi

# An inherited shell setting must never redirect this local copy to Supabase.
export DATABASE_URL=postgresql://geonwoolee@127.0.0.1:55433/braintutor_local
exec .venv/bin/python -m uvicorn platform_app.main:app --host 127.0.0.1 --port 8000
