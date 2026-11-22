#!/bin/sh
# IP of Webby-Soft SRL.
# Runs the design DOM crawl for the four contexts (light: deep crawl; dark: routes and shell menus).
# Needs the design served at DESIGN_BASE (default http://127.0.0.1:8090/app/mobile/banxum-prototype.html?lang=en).
set -eu
cd "$(dirname "$0")"
OUT="${U33_WORK_DIR:-../work/investor}/snap"
mkdir -p "$OUT"
node crawl.js "$OUT" desk-light 60 > "$OUT/progress-desk-light.txt" 2>&1 &
node crawl.js "$OUT" mob-light 60 > "$OUT/progress-mob-light.txt" 2>&1 &
wait
NO_DEEP=1 node crawl.js "$OUT" desk-dark > "$OUT/progress-desk-dark.txt" 2>&1 &
NO_DEEP=1 node crawl.js "$OUT" mob-dark > "$OUT/progress-mob-dark.txt" 2>&1 &
wait
echo done
