#!/bin/sh
# IP of Webby-Soft SRL.
# Regenerates frontend/src/portal/u33/u33.css and src/portal/u33/assets/nioicon-u33.woff2 from the
# U33 design package. See ../README.md.
# Usage: U33_DESIGN_DIST=<design package>/site/dist tools/u33-design/investor/build.sh [--crawl]
#   --crawl             re-crawl the rendered design first (needs the design served, see ../README.md)
#   --no-legacy-guard   accepted for old scripts; no effect (S7 of audit step 4 removed the old skin and
#                       its guards, so the stylesheet is always built without them)
# The design package is read as data only: its scripts and build tools are never run.
set -eu
cd "$(dirname "$0")"
DIST="${U33_DESIGN_DIST:?set U33_DESIGN_DIST to the design package site/dist folder}"
mkdir -p "${U33_WORK_DIR:-../work/investor}"
U33_WORK_DIR="$(cd "${U33_WORK_DIR:-../work/investor}" && pwd)"
export U33_WORK_DIR
FRONTEND="$(cd ../../../frontend && pwd)"
CRAWL=0
GUARD="--no-legacy-guard"
for arg in "$@"; do
  case "$arg" in
    --crawl) CRAWL=1 ;;
    --no-legacy-guard) GUARD="--no-legacy-guard" ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
if [ "$CRAWL" = 1 ]; then ./run-crawl.sh; fi
OUT="$U33_WORK_DIR/out"
python3 -I extract.py "$DIST" "$OUT/raw" > /dev/null
python3 -I extract_js.py "$DIST" "$OUT/js" > /dev/null
python3 -I design_body.py "$DIST" "$OUT/design-body.html" > /dev/null
python3 -I fonts.py "$OUT/raw/00-inline.css" "$OUT/fonts" > /dev/null
node build-u33-css.mjs "$FRONTEND" $GUARD
mkdir -p "$FRONTEND/src/portal/u33/assets"
# Nioicon subset: only the glyphs the kept rules use (fonttools in an isolated uvx environment).
uvx --with brotli --from fonttools pyftsubset "$OUT/fonts/06-Nioicon-normal.woff" \
  --unicodes="$(cat "$OUT/nioicon-codepoints.txt")" --flavor=woff2 --layout-features='' \
  --no-hinting --desubroutinize --name-IDs='*' --notdef-outline \
  --output-file="$FRONTEND/src/portal/u33/assets/nioicon-u33.woff2"
ls -l "$FRONTEND/src/portal/u33/u33.css" "$FRONTEND/src/portal/u33/assets/nioicon-u33.woff2"
