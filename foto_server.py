#!/usr/bin/env python3
"""
Foto-Server für die Foto-Aktion (nur Python-Standardbibliothek).

- Nimmt Fotos vom Laptop-Browser entgegen (nur lokal) und speichert sie unter einem
  zufälligen, nicht erratbaren Token.
- Liefert ein Foto nur aus, wenn man den Token kennt (steht nur im QR-Code).
  Es gibt keine Liste und keine Übersicht aller Bilder.
- Löscht Fotos automatisch nach --ttl Stunden.
- Startet (wenn installiert) einen kostenlosen Cloudflare-Quick-Tunnel, damit die
  Handys der Besucher den Laptop per https erreichen. Die Adresse ändert sich bei
  jedem Start, das ist egal – sie steht im QR-Code.

Start:   python foto_server.py
"""
import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_BYTES = 12 * 1024 * 1024
# Diese Header setzen Tunnel/Proxys bei Anfragen von außen. Fehlen sie, kommt die
# Anfrage direkt vom Laptop selbst.
FORWARD_HEADERS = ("X-Forwarded-For", "CF-Connecting-IP", "Cf-Ray", "Forwarded", "X-Real-Ip", "Cdn-Loop")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


class State:
    port = 8765
    ttl = 24 * 3600
    photos = ROOT / "photos"
    public_url = None
    origins = set()


class Handler(BaseHTTPRequestHandler):
    server_version = "FotoServer"
    sys_version = ""

    # ---------- Helfer ----------
    def log_message(self, fmt, *args):
        # Token nicht ins Log schreiben
        line = (self.requestline or "").split(" ")
        path = line[1] if len(line) > 1 else ""
        path = re.sub(r"/img/[^/?\s]+", "/img/…", path)
        print(f"  {self.command} {path}")

    def is_local(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        for h in FORWARD_HEADERS:
            if self.headers.get(h):
                return False
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{State.port}", f"localhost:{State.port}")

    def origin_ok(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in State.origins

    def cors(self):
        origin = self.headers.get("Origin")
        if origin and origin in State.origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def reply(self, code, body=b"", ctype="application/json", extra=None):
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def reply_json(self, code, obj):
        self.reply(code, json.dumps(obj).encode())

    # ---------- Anfragen ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/info":
            if not (self.is_local() and self.origin_ok()):
                return self.reply_json(403, {"error": "nur lokal"})
            return self.reply_json(200, {"public_url": State.public_url, "ttl": State.ttl})

        m = re.fullmatch(r"/img/([^/]+)", path)
        if m:
            token = m.group(1)
            if not TOKEN_RE.match(token):
                return self.reply_json(404, {"error": "nicht gefunden"})
            f = State.photos / f"{token}.jpg"
            try:
                data = f.read_bytes()
            except OSError:
                return self.reply_json(404, {"error": "nicht gefunden"})
            return self.reply(200, data, "image/jpeg")

        # Statische Seiten nur lokal (Notlösung: Laptop-Seite direkt vom Server öffnen)
        if self.is_local():
            name = "laptop.html" if path == "/" else path.lstrip("/")
            p = (ROOT / name).resolve()
            if p.suffix in STATIC_TYPES and p.is_file() and ROOT in p.parents:
                return self.reply(200, p.read_bytes(), STATIC_TYPES[p.suffix])
        return self.reply_json(404, {"error": "nicht gefunden"})

    def do_POST(self):
        if urlparse(self.path).path != "/upload":
            return self.reply_json(404, {"error": "nicht gefunden"})
        if not (self.is_local() and self.origin_ok()):
            return self.reply_json(403, {"error": "nur lokal"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self.reply_json(400, {"error": "leer"})
        if length > MAX_BYTES:
            return self.reply_json(413, {"error": "zu groß"})
        data = self.rfile.read(length)
        if data[:3] != b"\xff\xd8\xff":
            return self.reply_json(400, {"error": "kein JPEG"})
        token = secrets.token_urlsafe(16)
        State.photos.mkdir(exist_ok=True)
        (State.photos / f"{token}.jpg").write_bytes(data)
        print("  Foto gespeichert")
        return self.reply_json(200, {"token": token, "expires_in": State.ttl})


def cleanup_loop():
    while True:
        now = time.time()
        if State.photos.is_dir():
            for f in State.photos.glob("*.jpg"):
                try:
                    if now - f.stat().st_mtime > State.ttl:
                        f.unlink()
                except OSError:
                    pass
        time.sleep(60)


def start_tunnel(port):
    exe = shutil.which("cloudflared")
    if not exe:
        return None
    proc = subprocess.Popen(
        [exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    found = threading.Event()

    def reader():
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not State.public_url:
                State.public_url = m.group(0)
                found.set()

    threading.Thread(target=reader, daemon=True).start()
    found.wait(40)
    return proc


def main():
    ap = argparse.ArgumentParser(description="Foto-Server für die Foto-Aktion")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--ttl", type=float, default=24, help="Stunden, nach denen Fotos gelöscht werden (Standard 24)")
    ap.add_argument("--origin", default="https://schnax3.github.io", help="Erlaubte Seite (GitHub Pages)")
    ap.add_argument("--public-url", help="Eigene https-Adresse statt Cloudflare-Tunnel (z. B. Tailscale Funnel)")
    ap.add_argument("--no-tunnel", action="store_true", help="Keinen Tunnel starten")
    args = ap.parse_args()

    State.port = args.port
    State.ttl = int(args.ttl * 3600)
    State.photos.mkdir(exist_ok=True)
    State.origins = {args.origin.rstrip("/"), f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"}

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    print(f"Foto-Server läuft auf http://127.0.0.1:{args.port}  (Fotos werden nach {args.ttl:g} h gelöscht)")

    proc = None
    if args.public_url:
        State.public_url = args.public_url.rstrip("/")
    elif not args.no_tunnel:
        print("Starte Cloudflare-Tunnel …")
        proc = start_tunnel(args.port)
        if proc is None:
            print("\n!! 'cloudflared' ist nicht installiert. Ohne Tunnel erreichen Besucher den Laptop nicht.")
            print("   Windows: winget install Cloudflare.cloudflared   (danach neues Terminal öffnen)")
            print("   Oder eigene Adresse angeben: python foto_server.py --public-url https://...\n")
        elif not State.public_url:
            print("!! Tunnel-Adresse nicht erhalten. Internetverbindung prüfen.")

    if State.public_url:
        print(f"Öffentliche Adresse (nur per QR-Token abrufbar): {State.public_url}")
    print(f"\nLaptop-Seite:  {args.origin.rstrip('/')}/web-cam-upload/laptop.html")
    print(f"oder lokal:    http://localhost:{args.port}/   (falls der Browser die erste nicht erlaubt)")
    print("Beenden mit Strg+C\n")

    try:
        while True:
            time.sleep(1)
            if proc is not None and proc.poll() is not None:
                print("!! Tunnel wurde beendet. Server neu starten.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        if proc is not None:
            proc.terminate()
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
