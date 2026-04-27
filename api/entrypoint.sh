#!/bin/sh

set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running database migrations..."
  uv run --no-sync flask --app manage:app db upgrade
fi

exec "$@"
