#!/usr/bin/env bash
set -e
shopt -s nullglob

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Go to the folder that contains your images
cd "$SCRIPT_DIR/images/Portfolio"

# Collect image filenames
files=( *.jpg *.jpeg *.png *.JPG *.JPEG *.PNG )

# Write JSON to the file used by your site
printf "%s\n" "${files[@]}" \
  | jq -R -s -c 'split("\n")[:-1]' \
  > "$SCRIPT_DIR/gallery-images.json"

echo "Gallery updated! Push to GitHub to publish."
