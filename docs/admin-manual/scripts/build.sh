#!/usr/bin/env bash
# Reproducible build of BANXUM-Admin-Manual.pdf from the capture manifest +
# authored content slices. Does NOT require the app/dev server (it works from
# the already-captured figures/ and content/). Requires Google Chrome + uv.
#
# Pipeline: render annotated HTML -> rasterize each annotated figure to a flat
# PNG (headless Chrome crashes printing many inline SVGs) -> build a print-safe
# HTML using those PNGs -> split into image-bounded chunks (Chrome also crashes
# printing too many images at once) -> print each chunk with a FRESH headless
# Chrome -> merge + drop blank pages.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

ws_for_port () { curl -s "http://127.0.0.1:$1/json/version" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{try{console.log(JSON.parse(s).webSocketDebuggerUrl)}catch{console.log('')}})"; }
launch_chrome () { # port
  rm -rf "/tmp/banxum-build-prof-$1"
  "$CHROME" --headless=new --disable-gpu --disable-dev-shm-usage --no-sandbox --hide-scrollbars \
    --remote-debugging-port="$1" --user-data-dir="/tmp/banxum-build-prof-$1" about:blank >/dev/null 2>&1 &
  for _ in $(seq 1 20); do sleep 0.5; [ -n "$(ws_for_port "$1")" ] && return 0; done; return 1
}
kill_chrome () { pkill -f "remote-debugging-port=$1" 2>/dev/null || true; sleep 1; }

echo "1/6 render annotated HTML"; node scripts/render.mjs

echo "2/6 rasterize annotated figures"
launch_chrome 9341; node scripts/rasterize.mjs "$(ws_for_port 9341)"; kill_chrome 9341

echo "3/6 build print-safe HTML"; node scripts/build-print.mjs
echo "4/6 split into chunks"; PARTS="$(node scripts/split-print.mjs)"; echo "    chunks: $PARTS"

echo "5/6 print each chunk (fresh Chrome per chunk)"
i=0; PDFS=""
for f in $PARTS; do
  i=$((i+1)); port=$((9350+i))
  launch_chrome "$port"
  node scripts/to-pdf.mjs "$(ws_for_port "$port")" "part$i.pdf" "$f"
  kill_chrome "$port"
  PDFS="$PDFS part$i.pdf"
done

echo "6/6 merge + drop blank pages"
uv run --with pypdf --with pymupdf python3 scripts/merge.py BANXUM-Admin-Manual.pdf $PDFS

rm -f part*.pdf manual-part*.html
echo "done -> $DIR/BANXUM-Admin-Manual.pdf"
