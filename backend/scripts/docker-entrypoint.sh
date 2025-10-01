#!/usr/bin/env bash

set -euo pipefail

# Wait for dependencies to be reachable before starting the API server.
APP_DIR=${APP_DIR:-/app/backend}
cd "$APP_DIR"

export PYTHONPATH="${PYTHONPATH:-$APP_DIR}"

wait_for_postgres() {
  python - <<'PYCODE'
import os
import sys
import time
from sqlalchemy import create_engine, text

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    sys.stderr.write("DATABASE_URL is not set.\n")
    sys.exit(1)

engine = create_engine(database_url, pool_pre_ping=True)
last_error = None
for attempt in range(1, 31):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("PostgreSQL is available")
        break
    except Exception as exc:  # pragma: no cover - operational guard
        last_error = exc
        print(f"Waiting for PostgreSQL ({attempt}/30)...")
        time.sleep(2)
else:
    sys.stderr.write(f"Failed to connect to PostgreSQL: {last_error}\n")
    sys.exit(1)
PYCODE
}

wait_for_redis() {
  python - <<'PYCODE'
import os
import sys
import time
import redis

redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    print("REDIS_URL not set, skipping Redis availability check")
    sys.exit(0)

client = redis.from_url(redis_url)
last_error = None
for attempt in range(1, 31):
    try:
        client.ping()
        print("Redis is available")
        break
    except Exception as exc:  # pragma: no cover - operational guard
        last_error = exc
        print(f"Waiting for Redis ({attempt}/30)...")
        time.sleep(2)
else:
    sys.stderr.write(f"Failed to connect to Redis: {last_error}\n")
    sys.exit(1)
PYCODE
}

echo "==> Waiting for dependencies"
wait_for_postgres
wait_for_redis

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
  echo "==> Running database migrations"
  if alembic -c alembic.ini upgrade head; then
    echo "==> Migrations applied"
  else
    status=$?
    if [ "${MIGRATION_STRICT:-false}" = "true" ]; then
      echo "Migration failed (strict mode); exiting" >&2
      exit "$status"
    fi
    echo "WARNING: Database migrations failed (status $status); continuing startup because MIGRATION_STRICT is not enabled." >&2
  fi
else
  echo "==> Skipping database migrations (SKIP_MIGRATIONS=${SKIP_MIGRATIONS})"
fi

echo "==> Starting application"
exec "$@"
