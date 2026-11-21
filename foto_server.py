#!/usr/bin/env python3
"""
Foto-Server für die Foto-Aktion.

Alles wird am Laptop gesteuert:
  - Laptop-Seite:  http://localhost:8765/   (Steuerung, Laptop-Kamera, QR-Codes)
  - Handy:         https://<Laptop-IP>:8766/handy.html#<Schlüssel>  (nur externe Kamera)
Das Handy liefert ein Livebild und löst auf Befehl vom Laptop aus. Sobald ein Handy
verbunden ist, hat es Vorrang vor der Laptop-Kamera.

Beim Start erledigt das Skript automatisch:
  - cloudflared herunterladen (falls nicht vorhanden) und den Tunnel starten
    (bei Abbruch wird er neu gestartet)
  - ein Zertifikat für das Handy erzeugen (Browser erlauben die Handy-Kamera nur über https)
  - den Browser auf der Laptop-Seite öffnen

Wer darf was (Server prüft pro Anfrage, woher sie kommt):
  lokal  (Laptop selbst):  alles
  lan    (Handy im WLAN):  nur Handy-Seite, Livebild und Foto senden, nur mit Schlüssel
  remote (über Tunnel):    nur GET /img/<Token>

Start:   python foto_server.py
"""
import argparse
import datetime
import hmac
import ipaddress
import json
import platform
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
KEY_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
MAX_PHOTO = 12 * 1024 * 1024
MAX_FRAME = 3 * 1024 * 1024
PHONE_TIMEOUT = 4  # Sekunden ohne Livebild = Handy getrennt
ALLOWED_CMDS = {"shoot", "flip"}
# Diese Header setzen Tunnel/Proxys bei Anfragen von außen.
FORWARD_HEADERS = ("X-Forwarded-For", "CF-Connecting-IP", "Cf-Ray", "Forwarded", "X-Real-Ip", "Cdn-Loop")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}
LAN_FILES = {"handy.html", "style.css", "config.js"}  # das darf ein Handy im WLAN laden


class State:
    http_port = 8765
    phone_port = 8766
    tls = False
    ttl = 24 * 3600
    photos = ROOT / "photos"
    public_url = None
    pages_origin = "https://schnax3.github.io"
    key = ""
    lan_ip = None
    stopping = False
    cond = threading.Condition()
    phone_seen = 0.0
    frame = None
    frame_id = 0
    cmds = []
    seq = 0
    last_token = None
    tunnel_proc = None


def phone_connected():
    return (time.time() - State.phone_seen) < PHONE_TIMEOUT


def lan_url():
    if not State.lan_ip:
        return None
    scheme = "https" if State.tls else "http"
    return f"{scheme}://{State.lan_ip}:{State.phone_port}/handy.html#{State.key}"


class Handler(BaseHTTPRequestHandler):
    server_version = "FotoServer"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 30

    # ---------- Helfer ----------
    def setup(self):
        if isinstance(self.request, ssl.SSLSocket):
            self.request.settimeout(10)
            self.request.do_handshake()  # Fehler (z. B. Zertifikat abgelehnt) landen leise in handle_error
        super().setup()

    def log_message(self, fmt, *args):
        if not self.command:  # abgebrochene oder leere Verbindung
            return
        line = (self.requestline or "").split(" ")
        path = line[1] if len(line) > 1 else ""
        path = re.sub(r"/img/[^/?\s]+", "/img/…", path)
        if path.startswith(("/status", "/phone/frame", "/stream")):
            return  # Dauerverkehr nicht ausgeben
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
        """Schutz vor DNS-Rebinding: Host muss localhost bzw. eine IP-Adresse (mit Port) sein."""
        host = (self.headers.get("Host") or "").lower()
        port = self.server.server_address[1]
        if kind == "local":
            return host in (f"127.0.0.1:{port}", f"localhost:{port}")
        return re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}:%d" % port, host) is not None

    def origin_ok(self):
        """Browser-Anfragen müssen von derselben Adresse kommen wie die Seite (kein fremdes Skript)."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        u = urlparse(origin)
        return u.scheme in ("http", "https") and u.netloc.lower() == (self.headers.get("Host") or "").lower()

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
        if code >= 400:  # ungelesene Request-Bodys nicht in die nächste Anfrage laufen lassen
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def reply_json(self, code, obj):
        self.reply(code, json.dumps(obj).encode())

    def read_body(self, limit):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self.reply_json(400, {"error": "leer"})
            return None
        if length > limit:
            self.reply_json(413, {"error": "zu groß"})
            return None
        return self.rfile.read(length)

    def read_jpeg(self, limit):
        data = self.read_body(limit)
        if data is None:
            return None
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
            return self.reply_json(200, {"public_url": State.public_url, "ttl": State.ttl, "lan_url": lan_url(), "tls": State.tls})

        if path == "/status":
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            count = len(list(State.photos.glob("*.jpg"))) if State.photos.is_dir() else 0
            with State.cond:
                return self.reply_json(200, {
                    "phone": phone_connected(), "seq": State.seq, "token": State.last_token,
                    "photos": count, "tunnel": State.public_url is not None,
                })

        if path == "/stream":  # Livebild des Handys als Motion-JPEG
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            return self.stream()

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

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        last = -1
        try:
            while not State.stopping:
                with State.cond:
                    State.cond.wait_for(lambda: State.frame_id != last or State.stopping, timeout=1.0)
                    frame, last = State.frame, State.frame_id
                    alive = phone_connected()
                if not alive:
                    break
                if frame:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(frame))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
        except OSError:
            pass

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/upload":  # Foto der Laptop-Kamera
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            data = self.read_jpeg(MAX_PHOTO)
            if data is None:
                return
            token = self.save_photo(data)
            print("  Foto gespeichert (Laptop-Kamera)")
            return self.reply_json(200, {"token": token, "expires_in": State.ttl})

        if path == "/phone/frame":  # Livebild-Einzelbild vom Handy; Antwort enthält Befehle vom Laptop
            if not self.phone_ok():
                return self.reply_json(403, {"error": "Schlüssel falsch oder Zugriff nicht erlaubt"})
            data = self.read_jpeg(MAX_FRAME)
            if data is None:
                return
            with State.cond:
                was = phone_connected()
                State.phone_seen = time.time()
                State.frame = data
                State.frame_id += 1
                cmds, State.cmds = State.cmds, []
                State.cond.notify_all()
            if not was:
                print("  Handy verbunden")
            return self.reply_json(200, {"cmds": cmds})

        if path == "/phone/photo":  # Foto in voller Größe vom Handy
            if not self.phone_ok():
                return self.reply_json(403, {"error": "Schlüssel falsch oder Zugriff nicht erlaubt"})
            data = self.read_jpeg(MAX_PHOTO)
            if data is None:
                return
            token = self.save_photo(data)
            with State.cond:
                State.phone_seen = time.time()
                State.seq += 1
                State.last_token = token
            print("  Foto gespeichert (Handy)")
            return self.reply_json(200, {"ok": True})

        if path == "/cmd":  # Befehl vom Laptop an das Handy
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            body = self.read_body(1024)
            if body is None:
                return
            try:
                cmd = json.loads(body).get("cmd")
            except (ValueError, AttributeError):
                cmd = None
            if cmd not in ALLOWED_CMDS:
                return self.reply_json(400, {"error": "unbekannter Befehl"})
            with State.cond:
                if not phone_connected():
                    return self.reply_json(409, {"error": "kein Handy verbunden"})
                State.cmds.append(cmd)
            return self.reply_json(200, {"ok": True})

        if path == "/clear":  # alle Fotos löschen
            if not self.local_only():
                return self.reply_json(403, {"error": "nur lokal"})
            n = 0
            if State.photos.is_dir():
                for f in State.photos.glob("*.jpg"):
                    try:
                        f.unlink()
                        n += 1
                    except OSError:
                        pass
            with State.cond:
                State.last_token = None
            print(f"  {n} Fotos gelöscht")
            return self.reply_json(200, {"deleted": n})

        return self.reply_json(404, {"error": "nicht gefunden"})


class Server(ThreadingHTTPServer):
    """HTTP-Server, optional mit TLS (Handshake erst im Verbindungs-Thread, blockiert also nie den Annahme-Thread)."""
    ctx = None

    def get_request(self):
        sock, addr = super().get_request()
        if self.ctx:
            sock = self.ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
        return sock, addr

    def handle_error(self, request, client_address):
        # abgebrochene Verbindungen, abgelehnte Zertifikate usw. sind normal und nicht interessant
        if isinstance(sys.exc_info()[1], OSError):
            return
        super().handle_error(request, client_address)


def cleanup_loop():
    while not State.stopping:
        now = time.time()
        if State.photos.is_dir():
            for f in State.photos.glob("*.jpg"):
                try:
                    if now - f.stat().st_mtime > State.ttl:
                        f.unlink()
                except OSError:
                    pass
        time.sleep(60)


# ---------- Netzwerk ----------
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


# ---------- Zertifikat für das Handy (https) ----------
def import_cryptography(auto_install):
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        if not auto_install:
            return False
    print("Installiere 'cryptography' (einmalig, für das https-Zertifikat) …")
    for extra in ([], ["--break-system-packages"], ["--user"]):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "cryptography"] + extra,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            break
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_cert(ip, auto_install):
    """Erzeugt (falls nötig) ein selbstsigniertes Zertifikat für die WLAN-Adresse. Gibt (cert, key) oder None."""
    d = ROOT / "certs"
    cert_f, key_f, ip_f = d / "cert.pem", d / "key.pem", d / "ip.txt"
    try:
        fresh = (cert_f.is_file() and key_f.is_file() and ip_f.read_text() == str(ip)
                 and time.time() - cert_f.stat().st_mtime < 300 * 86400)
    except OSError:
        fresh = False
    if fresh:
        return str(cert_f), str(key_f)
    if not import_cryptography(auto_install):
        return None
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Foto-Aktion")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    if ip:
        san.append(x509.IPAddress(ipaddress.ip_address(ip)))
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .sign(key, hashes.SHA256()))
    d.mkdir(exist_ok=True)
    key_f.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    cert_f.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ip_f.write_text(str(ip))
    return str(cert_f), str(key_f)


# ---------- Cloudflare-Tunnel ----------
CF_ASSETS = {
    ("windows", "amd64"): "cloudflared-windows-amd64.exe",
    ("windows", "386"): "cloudflared-windows-386.exe",
    ("linux", "amd64"): "cloudflared-linux-amd64",
    ("linux", "arm64"): "cloudflared-linux-arm64",
    ("linux", "arm"): "cloudflared-linux-arm",
    ("darwin", "amd64"): "cloudflared-darwin-amd64.tgz",
    ("darwin", "arm64"): "cloudflared-darwin-arm64.tgz",
}


def find_cloudflared():
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    local = ROOT / "bin" / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
    return str(local) if local.is_file() else None


def install_cloudflared():
    """Lädt cloudflared von der offiziellen GitHub-Release-Seite nach ./bin. Gibt den Pfad oder None."""
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64",
            "armv7l": "arm", "armv6l": "arm", "i386": "386", "i686": "386", "x86": "386"}.get(platform.machine().lower())
    asset = CF_ASSETS.get((platform.system().lower(), arch))
    if not asset:
        print(f"!! Für dieses System ({platform.system()} {platform.machine()}) gibt es keinen automatischen Download.")
        return None
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
    bindir = ROOT / "bin"
    bindir.mkdir(exist_ok=True)
    target = bindir / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
    tmp = bindir / (asset + ".part")
    print(f"Lade cloudflared herunter (einmalig, ca. 40 MB) …\n  {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            nxt = 10
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total and done * 100 // total >= nxt:
                    print(f"  {nxt} %")
                    nxt += 10
        if asset.endswith(".tgz"):
            with tarfile.open(tmp) as tf:
                member = next((m for m in tf.getmembers() if Path(m.name).name == "cloudflared" and m.isfile()), None)
                if member is None:
                    raise RuntimeError("cloudflared nicht im Archiv gefunden")
                with tf.extractfile(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            tmp.unlink()
        else:
            tmp.replace(target)
        target.chmod(0o755)
    except Exception as e:  # noqa: BLE001 - jede Art von Fehler soll nur zu einer Meldung führen
        print(f"!! Download fehlgeschlagen: {e}")
        try:
            tmp.unlink()
        except OSError:
            pass
        return None
    print("  cloudflared installiert in ./bin")
    return str(target)


def tunnel_loop(exe, port):
    """Hält den Tunnel am Laufen. Bei Abbruch wird neu gestartet (die Adresse ändert sich dann)."""
    delay = 3
    while not State.stopping:
        State.public_url = None
        try:
            proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        except OSError as e:
            print(f"!! cloudflared lässt sich nicht starten: {e}")
            time.sleep(10)
            continue
        State.tunnel_proc = proc
        url = None
        timer = None
        published = []
        last_lines = []

        def publish(u, p=proc):
            if p.poll() is None and not State.stopping:
                State.public_url = u
                published.append(u)

        for line in proc.stdout:
            line = line.strip()
            if line:
                last_lines = (last_lines + [line])[-4:]
            m = URL_RE.search(line)
            if m and not url:
                url = m.group(0)
                # sobald der Tunnel „registered“ meldet, gilt er als bereit; sonst nach 15 s trotzdem
                timer = threading.Timer(15, publish, args=(url,))
                timer.daemon = True
                timer.start()
            if url and "egistered tunnel connection" in line:
                publish(url)
        if timer:
            timer.cancel()
        State.public_url = None
        if State.stopping:
            break
        if published:
            delay = 3  # lief eine Weile: schnell neu starten
        else:
            print("!! Tunnel konnte nicht aufgebaut werden. Letzte Meldungen von cloudflared:")
            for ln in last_lines:
                print("   " + ln[:200])
            delay = min(delay * 2, 60)  # ohne Internet nicht ständig neu versuchen
        print(f"!! Tunnel wurde beendet, neuer Versuch in {delay} s …")
        time.sleep(delay)


def main():
    ap = argparse.ArgumentParser(description="Foto-Server für die Foto-Aktion")
    ap.add_argument("--port", type=int, default=8765, help="Port der Laptop-Seite (nur lokal)")
    ap.add_argument("--phone-port", type=int, default=8766, help="Port für das Handy im WLAN (https)")
    ap.add_argument("--ttl", type=float, default=24, help="Stunden, nach denen Fotos gelöscht werden (Standard 24)")
    ap.add_argument("--origin", default="https://schnax3.github.io", help="Adresse der GitHub-Pages-Seite (nur Domain)")
    ap.add_argument("--public-url", help="Eigene https-Adresse statt Cloudflare-Tunnel (z. B. Tailscale Funnel)")
    ap.add_argument("--no-tunnel", action="store_true", help="Keinen Tunnel starten")
    ap.add_argument("--no-lan", action="store_true", help="Kein Handy im WLAN zulassen")
    ap.add_argument("--lan-ip", help="IP-Adresse des Laptops im WLAN, falls die automatische Erkennung falsch liegt")
    ap.add_argument("--key", help="Schlüssel für die Handy-Kopplung (Standard: zufällig, in .pairkey gespeichert)")
    ap.add_argument("--no-install", action="store_true", help="Nichts automatisch herunterladen/installieren")
    ap.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    args = ap.parse_args()

    State.http_port = args.port
    State.phone_port = args.phone_port
    State.ttl = int(args.ttl * 3600)
    State.pages_origin = args.origin.rstrip("/")
    State.photos.mkdir(exist_ok=True)
    State.key = load_key(args.key)
    State.lan_ip = None if args.no_lan else (args.lan_ip or detect_lan_ip())

    # Laptop-Seite: nur lokal erreichbar
    local = Server(("127.0.0.1", args.port), Handler)
    threading.Thread(target=local.serve_forever, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()

    # Handy-Seite: im WLAN, mit https
    phone = None
    if not args.no_lan:
        cert = ensure_cert(State.lan_ip, not args.no_install)
        phone = Server(("0.0.0.0", args.phone_port), Handler)
        if cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(*cert)
            phone.ctx = ctx
            State.tls = True
        else:
            print("!! Kein https-Zertifikat möglich ('pip install cryptography'). Die Handy-Kamera funktioniert so nicht.")
        threading.Thread(target=phone.serve_forever, daemon=True).start()

    print(f"Foto-Server läuft (Fotos werden nach {args.ttl:g} h gelöscht)")

    # Tunnel
    if args.public_url:
        State.public_url = args.public_url.rstrip("/")
    elif not args.no_tunnel:
        exe = find_cloudflared()
        if not exe and not args.no_install:
            exe = install_cloudflared()
        if not exe:
            print("\n!! cloudflared fehlt. Ohne Tunnel können Besucher ihr Foto nicht abholen.")
            print("   Manuell: winget install Cloudflare.cloudflared  oder  --public-url https://... angeben\n")
        else:
            print("Starte Cloudflare-Tunnel …")
            threading.Thread(target=tunnel_loop, args=(exe, args.port), daemon=True).start()
            for _ in range(90):
                if State.public_url:
                    break
                time.sleep(0.5)
            if not State.public_url:
                print("!! Noch keine Tunnel-Adresse. Internetverbindung prüfen. Es wird weiter versucht.")

    print()
    print(f"Laptop-Seite:  http://localhost:{args.port}/")
    if lan_url():
        print(f"Handy-Seite:   {lan_url()}   (QR dafür steht auf der Laptop-Seite)")
    elif not args.no_lan:
        print("!! Keine WLAN-Adresse gefunden. Mit --lan-ip 192.168.x.x angeben.")
    if State.public_url:
        print(f"Abhol-Adresse (nur per Token): {State.public_url}")
    print("Beenden mit Strg+C\n")

    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{args.port}/")
        except Exception:  # noqa: BLE001
            pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        State.stopping = True
        with State.cond:
            State.cond.notify_all()
        if State.tunnel_proc is not None:
            State.tunnel_proc.terminate()
        local.shutdown()
        if phone:
            phone.shutdown()


if __name__ == "__main__":
    sys.exit(main())
