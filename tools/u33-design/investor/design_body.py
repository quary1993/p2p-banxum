# IP of Webby-Soft SRL.
"""Static <body> markup of the design app (scripts, styles and data URIs removed), for the
PurgeCSS content.
Usage: python3 -I design_body.py <dist dir> <out file>"""
import os
import re
import sys

page = os.path.join(sys.argv[1], 'app', 'mobile', 'banxum-prototype.html')
s = open(page, encoding='utf-8').read()
s = re.sub(r'<script\b[\s\S]*?</script>', '', s)
s = re.sub(r'<style\b[\s\S]*?</style>', '', s)
s = re.sub(r'data:[a-z/+.-]+;base64,[A-Za-z0-9+/=]+', 'data:', s)
open(sys.argv[2], 'w', encoding='utf-8').write(s)
print(len(s))
