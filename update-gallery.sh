#!/usr/bin/env bash
# Regenerate gallery-images.json after adding photos to images/Portfolio/.
# Thin wrapper so `./update-gallery.sh` keeps working; the real work (including
# reading each photo's pixel dimensions) lives in update-gallery.py.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/update-gallery.py"
