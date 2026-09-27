#!/bin/sh
set -e
VIDEO_DIR="${VIDEO_STORAGE_PATH:-/app/var/videos}"
mkdir -p "$VIDEO_DIR"
if [ "$(id -u)" = "0" ]; then
  chown -R appuser:appuser "$VIDEO_DIR" || chmod 0777 "$VIDEO_DIR"
  exec gosu appuser "$@"
fi
exec "$@"
