#!/bin/sh
set -e

# Fix perms if running as root (Linux prod init), then drop privileges
if [ "$(id -u)" = '0' ]; then
    echo "Fixing volume permissions..."
    chown -R 1000:1000 /app/data /app/logs
    exec gosu appuser "$0" "$@"
fi

exec "$@"
