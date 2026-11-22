# IP of Webby-Soft SRL.
"""Extract the design app's JS (inline <script> blocks + linked /app/*.js) as text, for the
PurgeCSS content.
Usage: python3 -I extract_js.py <dist dir> <out dir>. Reads only."""
import os
import re
import sys

dist, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
s = open(os.path.join(dist, 'app', 'mobile', 'banxum-prototype.html'), encoding='utf-8').read()
n = 0
pos = 0
while True:
    m = re.compile(r'<script\b([^>]*)>').search(s, pos)
    if not m:
        break
    end = s.find('</script>', m.end())
    attrs, body = m.group(1), s[m.end():end]
    src = re.search(r'src="([^"]+)"', attrs)
    if src:
        path = src.group(1).split('?')[0]
        body = open(os.path.join(dist, path.lstrip('/')), encoding='utf-8').read()
        name = os.path.basename(path)
    else:
        idm = re.search(r'id="([^"]+)"', attrs)
        name = (idm.group(1) if idm else 'inline') + '.js'
    open(os.path.join(out, f'{n:02d}-{name}'), 'w', encoding='utf-8').write(body)
    print(n, name, len(body))
    n += 1
    pos = end + 9
# Linked scripts loaded by other entry points of the app (auth, preview) are covered above.
