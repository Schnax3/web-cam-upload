#!/usr/bin/env python3
"""
Foto-Server für die Foto-Aktion (nur Python-Standardbibliothek).

Alles läuft lokal auf dem Laptop:
  - Laptop-Seite:  http://localhost:8765/            (Kamera des Laptops)
  - Handy-Seite:   http://<Laptop-IP>:8765/handy.html#<Schlüssel>  (im selben WLAN)
Nur das Abholen der Fotos läuft über das Internet: foto.html (GitHub Pages) holt das
Foto per Token über einen Cloudflare-Tunnel vom Laptop.

Wer darf was (Server prüft pro Anfrage, woher sie kommt):
  lokal  (Laptop selbst):  alles
  lan    (Handy im WLAN):  nur Handy-Seite + Foto senden, und nur mit Schlüssel
  remote (über Tunnel):    nur GET /img/<Token>

Start:   python foto_server.py
"""
import argparse
import hmac
import ipaddress
import json
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
KEY_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
MAX_BYTES = 12 * 1024 * 1024
PHONE_TIMEOUT = 8  # Sekunden ohne Lebenszeichen = Handy getrennt
# Diese Header setzen Tunnel/Proxys bei Anfragen von außen.
FORWARD_HEADERS = ("X-Forwarded-For", "CF-Connecting-IP", "Cf-Ray", "Forwarded", "X-Real-Ip", "Cdn-Loop")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}
LAN_FILES = {"handy.html", "style.css", "config.js"}  # das darf ein Handy im WLAN laden


class State:
    port = 8765
    ttl = 24 * 3600
    photos = ROOT / "photos"
    public_url = None
    pages_origin = "https://schnax3.github.io"
    key = ""
    lan_ip = None
    lock = threading.Lock()
    phone_seen = 0.0
    seq = 0
    last_token = None


def lan_url():
    if not State.lan_ip:
        return None
    return f"http://{State.lan_ip}:{State.port}/handy.html#{State.key}"


class Handler(BaseHTTPRequestHandler):
    server_version = "FotoServer"
    sys_version = ""

    # ---------- Helfer ----------
    def log_message(self, fmt, *args):
        line = (self.requestline or "").split(" ")
        path = line[1] if len(line) > 1 else ""
        path = re.sub(r"/img/[^/?\s]+", "/img/…", path)
        if path.startswith(("/status", "/phone/hello")):
            return  # Polling nicht ausgeben
        print(f"  {self.command} {path}")

    def kind(self):
        """'local' (Laptop selbst), 'lan' (Gerät im WLAN) oder 'remote' (Tunnel/Internet)."""
        if any(self.headers.get(h) for h in FORWARD_HEADERS):
            return "remote"
        try:
            ip = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return "remote"
        if ip.is_loopback:
            return "local"
        if ip.is_private or ip.is_link_local:
            return "lan"
        return "remote"

    def host_ok(self, kind):
        """Schutz vor DNS-Rebinding: Host muss localhost bzw. eine IP-Adresse sein."""
        host = (self.headers.get("Host") or "").lower()
        if kind == "local":
            return host in (f"127.0.0.1:{State.port}", f"localhost:{State.port}")
        return re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}:%d" % State.port, host) is not None

    def origin_ok(self):
        """Browser-Anfragen müssen von derselben Adresse kommen wie die Seite (kein fremdes Skript)."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        u = urlparse(origin)
        return u.scheme == "http" and u.netloc.lower() == (self.headers.get("Host") or "").lower()

    def local_only(self):
        return self.kind() == "local" and self.host_ok("local") and self.origin_ok()

    def phone_ok(self):
        k = self.kind()
        if k not in ("local", "lan") or not self.host_ok(k) or not self.origin_ok():
            return False
        return hmac.compare_digest(self.headers.get("X-Key", ""), State.key)

    def cors(self):
        # Nur die GitHub-Pages-Seite darf Fotos per Browser abrufen (foto.html)
        if self.headers.get("Origin") == State.pages_origin:
            self.send_header("Access-Control-Allow-Origin", State.pages_origin)
            self.send_header("Vary", "Origin")

    def reply(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def reply_json(self, code, obj):
        self.reply(code, json.dumps(obj).encode())

    def read_jpeg(self):
        """Liest den Body, prüft Größe und JPEG-Kennung. Gibt Bytes oder None (Antwort ist dann schon gesendet)."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self.reply_json(400, {"error": "leer"})
            return None
        if length > MAX_BYTES:
            self.reply_json(413, {"error": "zu groß"})
            return None
        data = self.rfile.read(length)
        if data[:3] != b"\xff\xd8\xff":
            self.reply_json(400, {"error": "kein JPEG"})
            return None
        return data

    @staticmethod
    def save_photo(data):
        token = secrets.token_urlsafe(16)
        State.photos.mkdir(exist_ok=True)
        (State.photos / f"{token}.jpg").write_bytes(data)
        return token

    # ---------- Anfragen ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "ngrok-skip-browser-warning")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/info":
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            return self.reply_json(200, {"public_url": State.public_url, "ttl": State.ttl, "lan_url": lan_url()})

        if path == "/status":
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            with State.lock:
                phone = (time.time() - State.phone_seen) < PHONE_TIMEOUT
                return self.reply_json(200, {"phone": phone, "seq": State.seq, "token": State.last_token})

        m = re.fullmatch(r"/img/([^/]+)", path)
        if m:
            token = m.group(1)
            if not TOKEN_RE.match(token):
                return self.reply_json(404, {"error": "nicht gefunden"})
            try:
                data = (State.photos / f"{token}.jpg").read_bytes()
            except OSError:
                return self.reply_json(404, {"error": "nicht gefunden"})
            return self.reply(200, data, "image/jpeg")

        # Seiten ausliefern: Laptop alles, Handy im WLAN nur die Handy-Seite
        k = self.kind()
        if k in ("local", "lan") and self.host_ok(k):
            name = "laptop.html" if path == "/" else path.lstrip("/")
            if k == "lan" and name not in LAN_FILES:
                return self.reply_json(404, {"error": "nicht gefunden"})
            p = (ROOT / name).resolve()
            if p.suffix in STATIC_TYPES and p.is_file() and ROOT in p.parents:
                return self.reply(200, p.read_bytes(), STATIC_TYPES[p.suffix])
        return self.reply_json(404, {"error": "nicht gefunden"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/upload":  # Foto von der Laptop-Kamera
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            data = self.read_jpeg()
            if data is None:
                return
            token = self.save_photo(data)
            print("  Foto gespeichert (Laptop)")
            return self.reply_json(200, {"token": token, "expires_in": State.ttl})

        if path == "/phone/hello":  # Lebenszeichen des Handys
            if not self.phone_ok():
                return self.reply_json(403, {"error": "Schlüssel falsch oder Zugriff nicht erlaubt"})
            with State.lock:
                State.phone_seen = time.time()
            return self.reply_json(200, {"ok": True})

        if path == "/phone/photo":  # Foto vom Handy
            if not self.phone_ok():
                return self.reply_json(403, {"error": "Schlüssel falsch oder Zugriff nicht erlaubt"})
            data = self.read_jpeg()
            if data is None:
                return
            token = self.save_photo(data)
            with State.lock:
                State.phone_seen = time.time()
                State.seq += 1
                State.last_token = token
            print("  Foto gespeichert (Handy)")
            return self.reply_json(200, {"ok": True})

        return self.reply_json(404, {"error": "nicht gefunden"})


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


def detect_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # es wird nichts gesendet, nur die Route bestimmt
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return None


def load_key(cli_key):
    f = ROOT / ".pairkey"
    if cli_key:
        if not KEY_RE.match(cli_key):
            sys.exit("--key: nur Buchstaben, Ziffern, _ und -, 6 bis 64 Zeichen")
        return cli_key
    try:
        k = f.read_text().strip()
        if KEY_RE.match(k):
            return k
    except OSError:
        pass
    k = secrets.token_urlsafe(9)
    try:
        f.write_text(k)
    except OSError:
        pass
    return k


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
    ap.add_argument("--origin", default="https://schnax3.github.io", help="Adresse der GitHub-Pages-Seite (nur Domain)")
    ap.add_argument("--public-url", help="Eigene https-Adresse statt Cloudflare-Tunnel (z. B. Tailscale Funnel)")
    ap.add_argument("--no-tunnel", action="store_true", help="Keinen Tunnel starten")
    ap.add_argument("--no-lan", action="store_true", help="Nur der Laptop selbst darf zugreifen (kein Handy im WLAN)")
    ap.add_argument("--lan-ip", help="IP-Adresse des Laptops im WLAN, falls die automatische Erkennung falsch liegt")
    ap.add_argument("--key", help="Schlüssel für die Handy-Kopplung (Standard: zufällig, in .pairkey gespeichert)")
    args = ap.parse_args()

    State.port = args.port
    State.ttl = int(args.ttl * 3600)
    State.pages_origin = args.origin.rstrip("/")
    State.photos.mkdir(exist_ok=True)
    State.key = load_key(args.key)
    State.lan_ip = None if args.no_lan else (args.lan_ip or detect_lan_ip())

    bind = "127.0.0.1" if args.no_lan else "0.0.0.0"
    server = ThreadingHTTPServer((bind, args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    print(f"Foto-Server läuft (Fotos werden nach {args.ttl:g} h gelöscht)")

    proc = None
    if args.public_url:
        State.public_url = args.public_url.rstrip("/")
    elif not args.no_tunnel:
        print("Starte Cloudflare-Tunnel …")
        proc = start_tunnel(args.port)
        if proc is None:
            print("\n!! 'cloudflared' ist nicht installiert. Ohne Tunnel können Besucher ihr Foto nicht abholen.")
            print("   Windows: winget install Cloudflare.cloudflared   (danach neues Terminal öffnen)")
            print("   Oder eigene Adresse angeben: python foto_server.py --public-url https://...\n")
        elif not State.public_url:
            print("!! Tunnel-Adresse nicht erhalten. Internetverbindung prüfen.")

    print()
    print(f"Laptop-Seite:  http://localhost:{args.port}/")
    if lan_url():
        print(f"Handy-Seite:   {lan_url()}   (Handy im selben WLAN; auf der Laptop-Seite steht ein QR dafür)")
    elif not args.no_lan:
        print("!! Keine WLAN-Adresse gefunden. Mit --lan-ip 192.168.x.x angeben.")
    if State.public_url:
        print(f"Abhol-Adresse (nur per Token): {State.public_url}")
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
