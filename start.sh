#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if command -v python3.12 >/dev/null 2>&1; then
  exec python3.12 scripts/bootstrap.py "$@"
else
  exec python3 scripts/bootstrap.py "$@"
fi
