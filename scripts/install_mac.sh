#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/MacOS/scripts/install_mac.sh"

if [[ ! -f "$TARGET" ]]; then
  echo "Missing compatibility target: $TARGET" >&2
  exit 1
fi

exec bash "$TARGET" "$@"
