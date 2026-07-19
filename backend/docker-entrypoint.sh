#!/bin/sh
# Container entrypoint: bring the schema up to date, seed the demo accounts,
# then hand off to the CMD.
#
# Running both here rather than as separate manual steps is what makes
# `docker compose up --build` the only command anyone needs. Each step is a
# no-op once it has been done, so this is safe on every restart, not just the
# first.

set -eu

# Compose gates this container on the database's healthcheck, so Postgres is
# normally ready before we run. This retry exists for the case that gate does
# not cover: a restart where the database is still coming back up. Without it
# the container would exit and rely on the restart policy to try again, which
# turns a two-second wait into a crash loop in the logs.
ATTEMPTS=30
DELAY=2

echo "entrypoint: waiting for the database to accept migrations"

attempt=1
while [ "$attempt" -le "$ATTEMPTS" ]; do
    if alembic upgrade head; then
        echo "entrypoint: schema is up to date"
        break
    fi

    if [ "$attempt" -eq "$ATTEMPTS" ]; then
        echo "entrypoint: database unreachable after $ATTEMPTS attempts, giving up" >&2
        exit 1
    fi

    echo "entrypoint: migration attempt $attempt/$ATTEMPTS failed, retrying in ${DELAY}s"
    attempt=$((attempt + 1))
    sleep "$DELAY"
done

# Seeding is skipped in production by the module itself; it runs here so a
# reviewer has working logins the moment the stack is up. Existing accounts are
# left untouched, so a password changed while testing survives a restart.
python -m app.db.seed

# exec so uvicorn becomes PID 1 and receives SIGTERM directly — otherwise the
# shell swallows it and compose waits out the full stop timeout on every down.
exec "$@"
