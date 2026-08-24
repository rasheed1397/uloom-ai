#!/bin/sh
# Runs on every container start, not just first deploy - `alembic upgrade
# head` is a no-op when already at head, so this is safe to repeat and
# means the image never needs a separate manual migration step.
set -e

alembic upgrade head
exec "$@"
