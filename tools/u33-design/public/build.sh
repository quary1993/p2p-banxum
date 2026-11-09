#!/bin/sh
# IP of Webby-Soft SRL.
# Regenerates frontend/src/site/u33/public.css and src/site/u33/assets/nioicon-public.woff2 from the
# U33 design package. See ../README.md.
# Usage: U33_DESIGN_DIST=<design package>/site/dist tools/u33-design/public/build.sh [--capture]
#   --capture  re-capture the rendered design pages first (needs the design served at :8090, see ../README.md)
# The design package is read as data only: its scripts and build tools are never run.
set -eu
cd "$(dirname "$0")"
DIST="${U33_DESIGN_DIST:?set U33_DESIGN_DIST to the design package site/dist folder}"
mkdir -p "${U33_WORK_DIR:-../work/public}"
WORK="$(cd "${U33_WORK_DIR:-../work/public}" && pwd)"
FRONTEND="$(cd ../../../frontend && pwd)"
TARGET="$FRONTEND/src/site/u33"
case "${1:-}" in
  --capture) node capture-design.js "$WORK/design" ;;
  "") ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac
node build-public-css.mjs "$DIST" "$WORK/design/dom" "$TARGET/public.css" --report "$WORK/report.json"
mkdir -p "$TARGET/assets"
uv run --no-project --with fonttools --with brotli python -I subset-nioicon.py "$DIST/assets/nioicons.woff" "$TARGET/assets/nioicon-public.woff2"
ls -l "$TARGET/public.css" "$TARGET/assets/nioicon-public.woff2"
