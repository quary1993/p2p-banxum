# IP of Webby-Soft SRL.
"""Static server for the U33 design package's site/dist (the crawl and capture scripts render it).
Usage: python3 -I serve_dist.py <site/dist dir> <port> [spa]
Serves files only (never runs anything from the package); "/x" falls back to "/x.html"."""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = sys.argv[1]
PORT = int(sys.argv[2])
SPA = len(sys.argv) > 3
TYPES = {".mjs": "text/javascript", ".woff2": "font/woff2", ".pdf": "application/pdf"}


class Handler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map, **TYPES)

    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = urlsplit(self.path)
        target = Path(self.translate_path(parts.path))
        if not target.exists() and not target.suffix and target.with_suffix(".html").is_file():
            self.path = parts.path + ".html" + ("?" + parts.query if parts.query else "")
        elif SPA and not target.exists():
            self.path = "/index.html"
        super().do_GET()


ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=ROOT)).serve_forever()
