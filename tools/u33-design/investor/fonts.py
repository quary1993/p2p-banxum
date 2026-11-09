# IP of Webby-Soft SRL.
"""Write the fonts embedded as data URIs in the design's inline CSS to files (Archivo, Nioicon...).
Usage: python3 -I fonts.py <00-inline.css> <out dir>"""
import base64
import hashlib
import os
import re
import sys

s = open(sys.argv[1]).read()
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
for i,m in enumerate(re.finditer(r'@font-face\s*\{([^}]*)\}', s)):
    body=m.group(1)
    fam=re.search(r'font-family:\s*"?([^";]+)"?', body).group(1)
    w=re.search(r'font-weight:\s*([^;]+)', body)
    ur=re.search(r'unicode-range:\s*([^;]+)', body)
    d=re.search(r'data:([^;,]+)(?:;charset=[^;,]+)?;base64,([A-Za-z0-9+/=]+)', body)
    if d:
        data=base64.b64decode(d.group(2))
        ext={'font/woff2':'woff2','font/woff':'woff','application/x-font-ttf':'ttf'}.get(d.group(1),'bin')
        fn=f'{i:02d}-{fam}-{w.group(1) if w else ""}.{ext}'.replace(' ','_')
        open(os.path.join(out,fn),'wb').write(data)
        digest = hashlib.sha256(data).hexdigest()[:12]
        weight = w.group(1) if w else ''
        print(i, fam, weight, ur.group(1)[:60] if ur else '', d.group(1), len(data), digest, fn)
    else:
        print(i, fam, 'no data', body[:200])
