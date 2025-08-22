#!/usr/bin/env bash
set -e

# Wait for Postgres if DB_HOST provided (defaults to "db" in compose)
if [ -n "${DB_HOST}" ]; then
  echo "Waiting for DB at ${DB_HOST}:${DB_PORT:-5432}..."
  until nc -z "${DB_HOST}" "${DB_PORT:-5432}"; do
    sleep 1
  done
fi

# Auto-migrate in dev
if [ -f "manage.py" ]; then
  python manage.py migrate --noinput || true
fi

exec "$@"
