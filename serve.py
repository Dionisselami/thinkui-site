#!/usr/bin/env python3
"""
ThinkUI - local host.

Serves the product site with the routes it actually links to:
  /                       -> index.html
  /pricing, /docs         -> extensionless page names
  retired routes          -> 302 to the page that replaced them
  anything unknown        -> 404.html with a 404 status

Usage:
  python serve.py                 # http://127.0.0.1:8899 (this machine only)
  python serve.py --port 8000
  python serve.py --lan           # also reachable from your phone on the same Wi-Fi
  python serve.py --no-browser    # don't open a browser window
"""

import argparse
import http.server
import os
import socket
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES = {"", "index", "pricing", "docs", "login", "signup", "404", "terms", "privacy"}
# Files a browser asks for at the origin root even though the pages point at the
# copies under assets/img. Serving the real file beats answering 404 to a request
# the site itself provoked.
ROOT_FILES = {
    "/favicon.ico": "assets/img/favicon.ico",
    "/apple-touch-icon.png": "assets/img/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png": "assets/img/apple-touch-icon.png",
}

# Routes that existed before the redesign. They no longer have pages of their
# own, so they redirect rather than 404 — a dead link should land somewhere
# useful, not on an error.
LEGACY = {
    # the corpus browser pages are no longer part of the product site
    "screens": "index.html",
    "materials": "index.html",
    "elements": "index.html",
    "icons": "index.html",
    "mcp": "docs.html",
    "sources": "index.html",
    "design": "index.html",
    "explore": "index.html",
    "flows": "index.html",
    "flow": "index.html",
    "app": "index.html",
    "apps": "index.html",
}
MIME = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".webp": "image/webp", ".ico": "image/x-icon", ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8",
    ".xml": "application/xml; charset=utf-8", ".webmanifest": "application/manifest+json",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    # A class attribute, not an instance one. BaseHTTPRequestHandler.__init__
    # serves the request itself — socketserver calls handle() inside it — so
    # anything assigned after super().__init__() has already missed the
    # response, and the MIME table silently did not apply (.webp went out as
    # application/octet-stream).
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **MIME)

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        # quieten the default per-request noise; keep errors
        if not str(args[1] if len(args) > 1 else "").startswith("2"):
            sys.stderr.write("  %s\n" % (fmt % args))

    def handle(self):
        # A browser that navigates away mid-response is not an error worth a
        # traceback. Without this the dev host fills the console with noise
        # every time you click a link while a page is still loading.
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---------- routing ----------
    def translate_path(self, path):
        parsed = urllib.parse.urlparse(path).path
        if parsed in ROOT_FILES:
            return os.path.join(ROOT, *ROOT_FILES[parsed].split("/"))
        clean = urllib.parse.unquote(parsed).strip("/")
        parts = [p for p in clean.split("/") if p]

        # extensionless page name
        if len(parts) == 1 and parts[0] in PAGES and "." not in parts[0]:
            return os.path.join(ROOT, parts[0] + ".html")
        if not parts:
            return os.path.join(ROOT, "index.html")
        return os.path.join(ROOT, *parts)

    def send_head(self):
        parsed = urllib.parse.urlparse(self.path).path
        parts = [p for p in urllib.parse.unquote(parsed).strip("/").split("/") if p]
        # a retired route, or a retired route with a slug/id under it
        if parts and parts[0] in LEGACY:
            dest = LEGACY[parts[0]]
            self.send_response(302)
            self.send_header("Location", "/" + dest)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return self.serve_404()
        return super().send_head()

    def serve_404(self, *ignored):
        page = os.path.join(ROOT, "404.html")
        try:
            with open(page, "rb") as fh:
                body = fh.read()
        except OSError:
            body = b"404 - not found"
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        # do_GET() does `f = send_head()` and then `f.close()` on whatever came
        # back, so returning the byte count here (an int) blew up every request
        # that reached a missing file — and took the dev host down with it.
        # The body is already written: the contract is None.
        self.wfile.write(body)
        return None

    def end_headers(self):
        # dev host: always re-read files so edits show on refresh
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default=None, help="bind address (default 127.0.0.1, or 0.0.0.0 with --lan)")
    ap.add_argument("--lan", action="store_true", help="also serve to other devices on your network")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    host = args.host or ("0.0.0.0" if args.lan else "127.0.0.1")

    try:
        httpd = Server((host, args.port), Handler)
    except OSError as e:
        print("\n  Could not start on port %d (%s)." % (args.port, e))
        print("  Another server may already be using it. Try:  python serve.py --port 8010\n")
        return 1

    url = "http://127.0.0.1:%d/" % args.port
    print("")
    print("  ThinkUI is hosted locally")
    print("  " + "-" * 44)
    print("  Local     %s" % url)
    if args.lan:
        ip = lan_ip()
        if ip:
            print("  Network   http://%s:%d/   (phone / tablet on the same Wi-Fi)" % (ip, args.port))
    print("  Root      %s" % ROOT)
    print("")
    print("  Routes    /  /pricing  /docs  /login  /signup  /terms  /privacy")
    print("")
    print("  Stop      Ctrl+C in this window")
    print("")

    if not args.no_browser and not args.lan:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
