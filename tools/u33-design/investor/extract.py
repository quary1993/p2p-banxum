# IP of Webby-Soft SRL.
"""Extract the investor app's CSS in cascade order from the design's mobile prototype HTML.
Usage: python3 -I extract.py <dist dir> <out dir>
Writes NN-<name>.css files plus order.json. Only reads files; runs nothing from the package."""
import json
import os
import re
import sys

dist, out = sys.argv[1], sys.argv[2]
html_path = os.path.join(dist, 'app', 'mobile', 'banxum-prototype.html')
s = open(html_path, encoding='utf-8').read()
os.makedirs(out, exist_ok=True)
# The <head> ends before the body markup; the static style/link tags all sit in <head>.
head_end = s.find('</head>')
head = s[:head_end]
# Remove <script>...</script> contents so tag-like strings in JS do not match.
def blank_scripts(text):
    res, pos = [], 0
    for m in re.finditer(r'<script\b[^>]*>', text):
        if m.start() < pos:
            continue
        end = text.find('</script>', m.end())
        res.append(text[pos:m.end()])
        res.append(' ' * (end - m.end()))
        pos = end
    res.append(text[pos:])
    return ''.join(res)
clean = blank_scripts(head)
assert len(clean) == len(head)
order = []
n = 0
for m in re.finditer(r'<style\b([^>]*)>|<link\b([^>]*)>', clean):
    if m.group(1) is not None:
        attrs = m.group(1)
        end = clean.find('</style>', m.end())
        css = head[m.end():end]
        idm = re.search(r'id="([^"]+)"', attrs)
        name = idm.group(1) if idm else 'inline'
        kind = 'style'
    else:
        attrs = m.group(2)
        if 'stylesheet' not in attrs:
            continue
        href = re.search(r'href="([^"]+)"', attrs).group(1)
        path = href.split('?')[0]
        assert path.startswith('/app/'), href
        css = open(os.path.join(dist, path.lstrip('/')), encoding='utf-8').read()
        name = os.path.basename(path)[:-4]
        kind = 'link:' + href
    fn = f'{n:02d}-{name}.css'
    open(os.path.join(out, fn), 'w', encoding='utf-8').write(css)
    order.append({'n': n, 'file': fn, 'kind': kind, 'size': len(css)})
    n += 1
json.dump(order, open(os.path.join(out, 'order.json'), 'w'), indent=1)
for o in order:
    print(o['n'], o['file'], o['kind'], o['size'])
