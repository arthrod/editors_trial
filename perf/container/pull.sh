#!/usr/bin/env bash
set -euo pipefail
SCRIPT="$(cd "$(dirname "$0")" && pwd)/pull.py"
exec python3 -I "$SCRIPT" "$@"
