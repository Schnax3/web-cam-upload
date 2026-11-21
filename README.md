# web-cam-upload

Foto-Aktion für den Aktionsstand: Foto aufnehmen → QR-Code erscheint → Besucher scannen ihn mit dem eigenen Handy und landen auf einer Seite mit **Vorschau, Filtern und Download-Button**.

- **Alles wird am Laptop gesteuert.** Das Handy ist nur eine externe Kamera (Livebild, Auslösen und Kamerawechsel kommen vom Laptop). Ausgelöst wird mit der **Enter-Taste**.
- **Für den Stand gebaut:** Ist das Handy (quer gehalten) verbunden, zeigt der Laptop nur noch dessen Livebild im Vollbild. Besucher laden ihr Foto **quer oder hochkant** (Mitte des Querbilds) herunter.
- **Alles läuft lokal.** Nur das Abholen der Fotos geht über das Internet (GitHub-Pages-Seite + Cloudflare-Tunnel).
- **Der Tunnel richtet sich selbst ein.** Ein Befehl startet alles, cloudflared wird bei Bedarf automatisch heruntergeladen.
- Die Fotos liegen ausschließlich auf dem Laptop und sind nur mit dem Token im QR-Code abrufbar.

## Inhalt

1. [Überblick](#überblick)
2. [Einrichtung](#einrichtung)
3. [Am Stand](#am-stand)
4. [Einstellungen](#einstellungen)
5. [Sicherheit und Datenschutz](#sicherheit-und-datenschutz)
6. [Probleme und Lösungen](#probleme-und-lösungen)
7. [Technik im Detail](#technik-im-detail)
8. [Testliste vor dem Einsatz](#testliste-vor-dem-einsatz)
9. [Anpassen](#anpassen)

---

## Überblick

```
   Laptop-Browser  http://localhost:8765/   ◄── Steuerung: Auslöser, Countdown, Kamerawechsel, Löschen
        │                                        zeigt Livebild (Laptop-Kamera ODER Handy)
        ▼
   foto_server.py  (Python auf dem Laptop)  ── speichert photos/<Token>.jpg
        ▲                          │
        │  https, nur im WLAN      │  Cloudflare-Tunnel (wird automatisch gestartet), nur GET /img/<Token>
   Handy = externe Kamera          ▼
   sendet Livebild,        Besucher scannt QR ─► foto.html#s=<Tunnel>&t=<Token>  (GitHub Pages)
   löst auf Befehl aus                              └─► Vorschau, Filter, Download
```

**Handy hat Vorrang:** Solange kein Handy verbunden ist, benutzt die Laptop-Seite die Laptop-Kamera und zeigt rechts den Kopplungs-QR. Sobald ein Handy gekoppelt ist (auch nachträglich), **verschwindet der QR** und die Laptop-Seite zeigt **nur noch das Livebild des Handys im Vollbild** (Stand-Ansicht). Die Laptop-Kamera pausiert. **Enter** löst am Handy aus. Schließt du die Handy-Seite, schaltet die Laptop-Seite nach ca. 4 Sekunden von selbst wieder auf die Laptop-Kamera und zeigt den QR wieder.

| Datei | Aufgabe |
|---|---|
| `foto_server.py` | Der Server. Liefert die Seiten aus, nimmt Livebild und Fotos entgegen, gibt Fotos nur per Token heraus, löscht sie nach Ablauf, erzeugt das Zertifikat für das Handy, lädt cloudflared herunter und hält den Tunnel am Laufen. |
| `laptop.html` | Steuerzentrale auf dem Laptop. |
| `handy.html` | Externe Kamera auf dem Handy. Zeigt nur das Kamerabild, keine Bedienelemente. |
| `foto.html` | Seite für Besucher nach dem Scannen (läuft auf GitHub Pages): Vorschau, 9 Filter, Herunterladen, Teilen. |
| `start.bat` / `start.sh` | Doppelklick-Start für Windows bzw. Linux/macOS. |
| `config.js` | Einstellungen (Seiten-Adresse, Countdown, Foto-Größe, Titel). |
| `common.js`, `style.css`, `lib/qrcode.js` | Gemeinsamer Code, Aussehen, QR-Erzeugung (alles lokal, kein CDN). |
| `index.html` | Startseite für GitHub Pages. |

---

## Einrichtung

Nur zwei Dinge sind nötig. Alles andere macht der Server beim ersten Start selbst.

### 1. GitHub Pages einschalten (einmalig)

Repo auf GitHub → **Settings → Pages** → Source **Deploy from a branch**, Branch **main**, Ordner **/ (root)** → Save. Nach ein bis zwei Minuten ist die Seite erreichbar unter:

```
https://schnax3.github.io/web-cam-upload/
```

Sie wird nur für `foto.html` gebraucht (die Seite, die der QR-Code zum Abholen öffnet). Heißt dein Repo oder Benutzername anders, `PAGES_URL` in `config.js` anpassen (mit `/` am Ende) und den Server mit `--origin` starten.

### 2. Python 3.9 oder neuer

```
python --version
```

(Unter Linux/macOS `python3`.) Windows: <https://www.python.org/downloads/>, beim Installieren „Add python.exe to PATH“ anhaken.

### Was beim ersten Start automatisch passiert

| Schritt | Was der Server tut |
|---|---|
| **cloudflared** | Findet er das Programm nicht (weder im PATH noch in `bin/`), lädt er es von der offiziellen GitHub-Release-Seite von Cloudflare herunter (ca. 40 MB, passend zu Windows/macOS/Linux und deiner Prozessorart) und legt es in `bin/` ab. |
| **Tunnel** | Startet einen kostenlosen Cloudflare-Quick-Tunnel (kein Account nötig) und wartet, bis die Adresse bereit ist. Bricht der Tunnel ab, wird er automatisch neu gestartet. Ohne Internet wird die Wartezeit schrittweise länger (bis 60 s) und der Grund angezeigt. |
| **Zertifikat** | Browser erlauben die Handy-Kamera nur über https. Der Server installiert dafür einmalig das Python-Paket `cryptography` und stellt ein eigenes Zertifikat für die WLAN-Adresse des Laptops aus (`certs/`, gültig 1 Jahr, wird bei neuer WLAN-Adresse neu erzeugt). |
| **Schlüssel** | Erzeugt einen zufälligen Kopplungsschlüssel (`.pairkey`). |
| **Browser** | Öffnet die Laptop-Seite. |

Mit `--no-install` wird nichts automatisch heruntergeladen oder installiert.

### Windows-Firewall (nur beim ersten Start)

Windows fragt, ob Python im Netzwerk kommunizieren darf. **Zugriff in privaten Netzwerken erlauben**, sonst erreicht das Handy den Laptop nicht.

---

## Am Stand

### Starten

Windows: Doppelklick auf **`start.bat`**. Linux/macOS: **`./start.sh`**. Oder im Terminal:

```
python foto_server.py
```

Ausgabe, z. B.:

```
Foto-Server läuft (Fotos werden nach 24 h gelöscht)
Starte Cloudflare-Tunnel …

Laptop-Seite:  http://localhost:8765/
Handy-Seite:   https://192.168.1.23:8766/handy.html#k3Jd8sLq0xw   (QR dafür steht auf der Laptop-Seite)
Abhol-Adresse (nur per Token): https://xyz-abc.trycloudflare.com
```

Der Browser öffnet sich von selbst auf der Laptop-Seite. Das Terminal-Fenster muss während der Aktion offen bleiben.

### Die Laptop-Seite

Oben rechts zeigt die Seite den Zustand:

| Anzeige | Bedeutung |
|---|---|
| **Server ✓ Tunnel ✓** (grün) | Alles bereit, Fotos können abgeholt werden. |
| **Tunnel startet …** (rot) | Server läuft, der Tunnel ist noch nicht bereit (dauert beim Start einige Sekunden). |
| **Server nicht erreichbar** (rot) | `foto_server.py` läuft nicht mehr. |
| **Handy verbunden ✓** | Ein Handy ist gekoppelt, die Handy-Kamera hat Vorrang. |

Alles Wichtige wird hier bedient:

- **Enter:** Foto auslösen (mit Countdown) mit der aktiven Kamera (Laptop oder Handy). Im Ergebnis (Foto + QR) schließt Enter die Anzeige und zeigt wieder das Livebild. Prellen und gehaltene Taste lösen nur einmal aus.
- **F:** Vollbild des Browsers ein/aus.
- **📸 Foto machen:** dasselbe wie Enter, per Mausklick.
- **🔄 Handy-Kamera wechseln:** Hinten/vorne (nur sichtbar, wenn ein Handy verbunden ist).
- **Countdown:** aus, 3, 5 oder 10 Sekunden (wird im Browser gemerkt).
- **Foto + QR schließen:** „mit Enter“ oder automatisch nach 30 s / 60 s / 2 Min. (zeigt „Schließt automatisch in … s“). Praktisch, wenn am Stand niemand die Taste drückt.
- **🗑️ Alle Fotos löschen:** löscht sofort alles auf dem Laptop (mit Rückfrage).
- **Abhol-Adresse:** zeigt die aktuelle Tunnel-Adresse.
- **QR-Code „Handy als externe Kamera“:** zum Koppeln des Handys, nur sichtbar, solange kein Handy verbunden ist.

### Stand-Ansicht (sobald ein Handy verbunden ist)

Der Bildschirm zeigt **nur das Livebild des Handys**, ohne Rahmen, Knöpfe oder QR-Code, und der Mauszeiger ist ausgeblendet. Der Countdown erscheint groß über dem Bild. Bewegst du die Maus, erscheint unten eine Leiste mit **Foto machen**, **Kamera wechseln**, **Vollbild** und **Einstellungen**. „Einstellungen“ zeigt die normale Ansicht (Countdown, Löschen, Abhol-Adresse), „🖥️ Nur Kamerabild zeigen“ bringt die Stand-Ansicht zurück. Verbindet sich das Handy neu, startet automatisch wieder die Stand-Ansicht.

Tipp für den Stand: **F** drücken (Vollbild), Maus weg, ab jetzt nur noch **Enter**.

### Foto aufnehmen und abholen

1. **Enter** drücken, der Countdown läuft über dem Kamerabild.
2. Das Foto erscheint groß mit einem **QR-Code**. Der Besucher scannt ihn mit der Handy-Kamera.
3. **Enter** (oder die eingestellte Zeit) schließt die Anzeige, das Livebild ist wieder da. Nächste Person, wieder **Enter**.

### Handy als externe Kamera hinzufügen (jederzeit)

1. Handy ins **selbe WLAN** wie der Laptop. Das Handy wird **quer** gehalten (16:9). Hält man es hochkant, zeigt es den Hinweis „Bitte das Handy quer halten“. Bildschirmdrehung am Handy einschalten, am besten das Handy fest aufstellen (Stativ/Halterung).
2. Den QR-Code im Kasten „Handy als externe Kamera“ mit dem Handy scannen.
3. **Beim ersten Mal** zeigt das Handy eine Zertifikatswarnung („Verbindung nicht privat“ / „Nicht sicher“), weil der Laptop sein Zertifikat selbst ausstellt: Android/Chrome „Erweitert → Weiter zu … (unsicher)“, iPhone/Safari „Details einblenden → Diese Website besuchen“. Das ist nur für das eigene Handy nötig und wird später nicht mehr gefragt. Danach noch die Kamera erlauben.
4. Das Handy zeigt das Kamerabild vollflächig und oben „Mit Laptop verbunden ✓“. Der Bildschirm bleibt an.
5. Auf dem Laptop **verschwindet der Kopplungs-QR**, die Laptop-Kamera pausiert und es ist nur noch das Livebild des Handys im Vollbild zu sehen.
6. Ab jetzt alles am Laptop: **Enter** = Foto, Kamera wechseln über die Bedienleiste. Das Foto kommt in hoher Auflösung (`MAX_SIZE`, Standard 2560 px) vom Handy und erscheint mit QR-Code am Laptop.

Zurück zur Laptop-Kamera: Handy-Seite schließen (oder Handy sperren). Nach ca. 4 Sekunden schaltet die Laptop-Seite um.

Die Kopplung bleibt auch nach Neustart des Servers gültig (der Schlüssel steht in `.pairkey`), solange sich die WLAN-Adresse des Laptops nicht ändert.

### Was der Besucher sieht

Nach dem Scannen öffnet sich `foto.html`:

- Vorschau des Fotos
- **Format:** **Quer** (Original, 16:9), **Hochkant 3:4** oder **Hochkant 9:16**. Hochkant ist immer ein Ausschnitt aus der **Mitte des Querbilds** in voller Höhe (bei 2560 × 1440 px: 3:4 = 1080 × 1440, 9:16 = 810 × 1440). Die Vorschau zeigt genau den Ausschnitt, der heruntergeladen wird.
- Filterleiste mit Mini-Vorschauen: Original, Schwarz-Weiß, Sepia, Vintage, Lebendig, Warm, Kühl, Dramatisch, Pastell
- **⬇️ Herunterladen** speichert das Foto im gewählten Format mit dem gewählten Filter als JPG (z. B. `foto-quer.jpg`, `foto-hochkant-9x16-sepia.jpg`)
- **📤 Teilen / Sichern** (nur auf Handys, die das können) öffnet das Teilen-Menü, dort „Bild sichern“ bzw. direkt in die Fotos-App

### Beenden

Im Terminal **Strg+C**. Der Tunnel wird mitbeendet. Die Fotos im Ordner `photos/` werden beim nächsten Start nach Ablauf der Zeit gelöscht, oder gleich über **🗑️ Alle Fotos löschen**.

---

## Einstellungen

### `config.js`

| Eintrag | Standard | Bedeutung |
|---|---|---|
| `PAGES_URL` | `https://schnax3.github.io/web-cam-upload/` | Adresse der GitHub-Pages-Seite. Dorthin führt der QR-Code zum Abholen. Mit `/` am Ende. |
| `LOCAL_SERVER` | leer | Adresse des Foto-Servers. Leer = derselbe Server, von dem die Seite kommt. Normalerweise nie ändern. |
| `MAX_SIZE` | `2560` | Längste Kante des Fotos in Pixeln. Hoch lassen: Die Hochkant-Version ist ein Ausschnitt aus der Mitte und hat nur einen Teil der Breite. Größer = schärfer, aber größere Dateien (ca. 1 MB bei 2560). |
| `COUNTDOWN` | `3` | Vorgabe für den Countdown (auf der Laptop-Seite umstellbar). |
| `TITLE` | `Foto-Aktion` | Titel oben auf der Laptop-Seite. |

Die Laptop- und Handy-Seite kommen direkt vom Server, Änderungen wirken nach Neuladen. `foto.html` auf GitHub Pages liest `config.js` nicht.

### `foto_server.py`

| Option | Standard | Bedeutung |
|---|---|---|
| `--ttl 2` | `24` | Stunden, nach denen Fotos gelöscht werden. Bruchteile gehen auch (`--ttl 0.5`). |
| `--port 8766` | `8765` | Port der Laptop-Seite (nur lokal erreichbar). |
| `--phone-port 8767` | `8766` | Port für das Handy im WLAN (https). |
| `--origin https://...` | `https://schnax3.github.io` | Adresse der Pages-Seite (nur Protokoll + Domain, ohne Pfad). Nur diese Seite darf Fotos im Browser abrufen. |
| `--public-url https://...` | automatischer Tunnel | Eigene öffentliche https-Adresse (z. B. Tailscale Funnel) statt Cloudflare-Tunnel. |
| `--no-tunnel` | aus | Keinen Tunnel starten (zum Testen). |
| `--no-lan` | aus | Kein Handy zulassen. Nur Laptop-Kamera. |
| `--lan-ip 192.168.1.23` | automatisch | WLAN-Adresse des Laptops, falls die automatische Erkennung die falsche nimmt (VPN, mehrere Netzwerkkarten). |
| `--key abc123` | zufällig | Eigener Kopplungsschlüssel (6–64 Zeichen: Buchstaben, Ziffern, `_`, `-`). |
| `--no-install` | aus | Nichts automatisch herunterladen/installieren (cloudflared, cryptography). |
| `--no-browser` | aus | Browser nicht automatisch öffnen. |

---

## Sicherheit und Datenschutz

### Wer darf was?

Der Server prüft bei **jeder** Anfrage, woher sie kommt, und die Laptop-Seite ist nur lokal erreichbar (Port 8765 hört nur auf `127.0.0.1`):

| Herkunft | Erkennung | Erlaubt |
|---|---|---|
| **Laptop selbst** | Loopback-Adresse, kein Tunnel-Header | Alles: Seite, Steuerbefehle, Livebild, Foto hochladen, Löschen. |
| **Handy im WLAN** | private Adresse, kein Tunnel-Header | Nur `handy.html` (samt `style.css`, `config.js`), Livebild senden und Foto senden, **und nur mit dem Kopplungsschlüssel**. Es kann nichts steuern, nichts ansehen, nichts löschen. |
| **Internet (Tunnel)** | Tunnel-Header (`Cf-Ray`, `X-Forwarded-For`, …) | Nur `GET /img/<Token>`. Alles andere: 403/404. |

Weitere Schutzmaßnahmen:

- Der Schlüssel fürs Handy ist zufällig (ca. 72 Bit). Wer im selben WLAN die Handy-Adresse ohne Schlüssel aufruft, kann nichts senden.
- Die Verbindung Handy ↔ Laptop ist per TLS verschlüsselt.
- Der `Host`-Header muss `localhost` bzw. eine IP-Adresse sein (Schutz vor DNS-Rebinding), und ein Browser-`Origin` muss zur Seite passen (fremde Webseiten können im Browser des Laptops nichts auslösen).
- Es werden nur JPEG-Dateien angenommen (Foto max. 12 MB, Livebild-Einzelbild max. 3 MB).
- Über den Tunnel ist **nichts außer den Fotos** erreichbar: Weder die Laptop-Seite noch das Livebild noch `foto_server.py` noch der Ordner `photos/`.
- Das Livebild des Handys wird nie gespeichert, nur das jeweils letzte Einzelbild liegt kurz im Arbeitsspeicher.

### Wer kann Fotos sehen?

- Jedes Foto bekommt beim Speichern einen zufälligen Token (128 Bit). Der ist nicht erratbar.
- Der Token steht nur im QR-Code, im `#`-Teil des Links. Dieser Teil wird vom Browser nie an einen Server geschickt, taucht also in keinen Zugriffsprotokollen auf.
- Es gibt keine Liste, keinen Ordnerinhalt, keine Suche. Falscher Token = 404.
- Wer den QR-Code fotografiert oder den Link weitergibt, kann das Foto bis zum Ablauf sehen. Das ist bei „nur mit QR-Code“ nicht vermeidbar.

### Welche Dienste sind beteiligt?

| Dienst | Was er sieht |
|---|---|
| **GitHub** | Liefert `foto.html` (Code) über GitHub Pages und beim ersten Start die cloudflared-Programmdatei. Fotos laufen nie darüber. |
| **Cloudflare (Tunnel)** | Leitet die Abrufe der Fotos durch. Technisch sieht Cloudflare den Datenverkehr, wie bei jedem Tunnel/Proxy. |
| **PyPI** | Einmalig beim Installieren von `cryptography`. |

Kamera, Livebild, Steuerung und Speicherung laufen komplett im lokalen Netz.

### Hinweise für den Stand

- Es werden Fotos von Personen gemacht. Ein gut sichtbares Schild hilft: „Foto wird bis zu 24 Stunden auf dem Laptop gespeichert und danach gelöscht; nur mit dem QR-Code abrufbar.“ Bei Minderjährigen vorher klären, ob das für eure Veranstaltung eine Einwilligung der Eltern braucht.
- Nach der Aktion **🗑️ Alle Fotos löschen** oder `--ttl` kurz wählen.
- Das WLAN sollte nicht für Fremde offen sein. Am besten eigenes WLAN oder Handy-Hotspot für den Stand.
- Der Laptop sollte während der Aktion nicht in den Ruhezustand gehen (Energieeinstellungen).

---

## Probleme und Lösungen

**Laptop-Seite zeigt „Server nicht erreichbar“**
- Läuft `foto_server.py` noch? Das Terminal-Fenster darf nicht geschlossen sein.
- Die Seite muss unter `http://localhost:8765/` geöffnet sein, nicht unter der GitHub-Pages-Adresse.
- Port belegt? Mit `--port 8770` starten und `http://localhost:8770/` öffnen.

**„Tunnel startet …“ bleibt stehen**
- Im Terminal steht der Grund. Meist keine Internetverbindung oder ein Netz, das Cloudflare-Tunnel blockiert (Firmen-/Schulnetz). Dann Handy-Hotspot für den Laptop nutzen. Der Server versucht es automatisch weiter.
- Download von cloudflared nicht möglich? Manuell installieren (`winget install Cloudflare.cloudflared` bzw. `brew install cloudflared`) oder `--public-url` mit einem eigenen Tunnel angeben.
- Die Tunnel-Adresse ändert sich bei jedem Start und jedem automatischen Neustart des Tunnels. **Bereits angezeigte QR-Codes funktionieren danach nicht mehr.** Neue Fotos bekommen immer die aktuelle Adresse.

**Handy lädt die Seite nicht**
- Handy und Laptop müssen im **selben WLAN** sein (nicht Mobilfunk, nicht Gast-WLAN mit Geräteisolation). Manche öffentlichen/Schul-WLANs trennen Geräte voneinander: dann Handy-Hotspot für beide nutzen (Laptop ins Hotspot-WLAN).
- Windows-Firewall: Python für **private Netzwerke** erlauben (Einstellungen → Firewall → App zulassen).
- Falsche Adresse im QR (z. B. VPN-Adapter)? Server mit `--lan-ip <richtige WLAN-IP>` starten. Die IP zeigt `ipconfig` (Windows) bzw. `ip a` (Linux).

**Handy meldet „Kamera nicht erlaubt“ / „braucht https“**
- Der Server konnte das Zertifikat nicht erzeugen. Im Terminal `pip install cryptography` ausführen (nicht mit `--no-install` gestartet?), Server neu starten, QR neu scannen.

**Handy meldet „Schlüssel falsch – QR neu scannen“**
- Der Schlüssel hat sich geändert (z. B. `.pairkey` gelöscht). QR auf der Laptop-Seite neu scannen.

**Handy zeigt „Keine Verbindung zum Laptop“**
- Laptop im WLAN erreichbar? Bei geänderter WLAN-Adresse des Laptops den QR neu scannen. Handy-Bildschirm muss an sein und die Seite im Vordergrund.

**Das Handy-Livebild ruckelt**
- Es sind ca. 9 Bilder pro Sekunde bei 640 Pixeln. Näher an den Router, 5-GHz-WLAN nutzen. Das Foto selbst kommt unabhängig davon in voller Qualität.

**Enter tut nichts**
- Das Browserfenster der Laptop-Seite muss im Vordergrund sein (einmal ins Fenster klicken). Läuft schon ein Countdown oder wird gerade ein Foto angezeigt, schließt Enter zuerst die Anzeige.
- Unter dem Livebild erscheint eine rote Meldung, wenn kein Handy antwortet („Das Handy hat kein Foto geschickt“). Dann ist die Handy-Seite zu oder das Handy im Ruhezustand.

**Das Hochkant-Bild ist zu schmal/unscharf**
- Hochkant ist ein Ausschnitt aus der Mitte. Personen beim Fotografieren in die Bildmitte stellen. Für mehr Schärfe `MAX_SIZE` in `config.js` erhöhen (z. B. 3200). Das Handy muss die Auflösung liefern (der Browser fragt 2560 × 1440 an).

**Das Handy zeigt „Bitte das Handy quer halten“**
- Das Handy ist hochkant. Das Foto soll quer sein: Handy drehen und die Bildschirmdrehung aktivieren.

**Ich will wieder die Laptop-Kamera**
- Handy-Seite schließen. Nach ca. 4 Sekunden ist die Laptop-Kamera wieder aktiv.

**Laptop-Kamera zeigt schwarzes Bild oder Fehlermeldung**
- Kamera-Zugriff im Browser erlauben (Schloss-Symbol in der Adresszeile). Wird die Kamera von einem anderen Programm benutzt (Teams, Zoom, OBS)? Dort beenden.

**Foto-Seite meldet „Dieses Foto gibt es nicht mehr“**
- Abgelaufen (`--ttl`) oder gelöscht.

**Foto-Seite meldet „Der Foto-Server ist gerade nicht erreichbar“**
- Laptop aus, offline oder Tunnel gerade neu gestartet (siehe oben, alte QR-Codes sind dann ungültig).

**Der QR-Code lässt sich schlecht scannen**
- Browserfenster größer machen oder Bildschirm heller stellen. Der QR-Code skaliert mit dem Fenster und ist weiß hinterlegt.

**Download-Button macht am iPhone nichts Sichtbares**
- Das iPhone legt die Datei in der Dateien-App unter „Downloads“ ab. Besser: **📤 Teilen / Sichern** nehmen und „Bild sichern“ wählen, dann landet es in Fotos.

---

## Technik im Detail

### Zwei Server-Ports

| Port | Adresse | Zweck |
|---|---|---|
| `8765` (HTTP) | nur `127.0.0.1` | Laptop-Seite und Steuerung. `localhost` zählt für Browser als sicher (Kamera funktioniert). Der Cloudflare-Tunnel zeigt ebenfalls auf diesen Port, dort kommen aber nur Abrufe von `/img/<Token>` durch. |
| `8766` (HTTPS) | WLAN (`0.0.0.0`) | Nur für das Handy. Selbstsigniertes Zertifikat für die WLAN-Adresse, weil Browser die Kamera nur über https erlauben. |

### Handy → Laptop

Das Handy schickt etwa 9-mal pro Sekunde ein verkleinertes Einzelbild (`POST /phone/frame`, 640 px). Die Antwort enthält die offenen Befehle des Laptops (`shoot`, `flip`). So braucht es keine dauerhafte Verbindung und keinen zusätzlichen Dienst. Der Server reicht die Einzelbilder als Motion-JPEG an den Laptop weiter (`GET /stream`). Bei `shoot` nimmt das Handy ein Foto in voller Auflösung (längste Kante `MAX_SIZE`) und sendet es per `POST /phone/photo`. Nach 4 Sekunden ohne Livebild gilt das Handy als getrennt.

### Der Link im QR-Code zum Abholen

```
https://schnax3.github.io/web-cam-upload/foto.html#s=<Tunnel-Adresse>&t=<Token>
```

`foto.html` akzeptiert nur `https`-Server und Token aus 16–64 Zeichen `A-Z a-z 0-9 _ -`. Es holt `GET <Tunnel>/img/<Token>` und verarbeitet das Bild komplett im Browser.

### Filter

Die Filter rechnen jeden Pixel selbst (Sepia, Graustufen, Sättigung, Kontrast, Helligkeit, Farbtönung, Vignette). Sie nutzen bewusst nicht `canvas.filter`, das auf iPhones fehlt. Der Download enthält exakt das, was die Vorschau zeigt.

### Server-Schnittstellen

| Anfrage | Wer darf | Zweck |
|---|---|---|
| `GET /info` | Laptop | Abhol-Adresse, Aufbewahrungszeit, Handy-Link. |
| `GET /status` | Laptop | Handy verbunden?, Zähler und Token des letzten Handy-Fotos, Anzahl Fotos, Tunnel bereit? Die Laptop-Seite fragt das jede Sekunde ab. |
| `GET /stream` | Laptop | Livebild des Handys (Motion-JPEG). |
| `POST /cmd` | Laptop | Befehl `shoot` oder `flip` an das Handy. |
| `POST /upload` | Laptop | Foto der Laptop-Kamera speichern. |
| `POST /clear` | Laptop | Alle Fotos löschen. |
| `POST /phone/frame` | Handy + Schlüssel | Livebild-Einzelbild senden, Befehle abholen. |
| `POST /phone/photo` | Handy + Schlüssel | Foto in voller Größe senden. |
| `GET /img/<Token>` | jeder mit Token | Liefert das Foto. Nur diese Anfrage erreicht den Server über den Tunnel. |
| `GET /`, `*.html`, `*.js`, `*.css` | Laptop alles, Handy nur `handy.html`, `style.css`, `config.js` | Seiten ausliefern. Nie `.py`, Fotos oder Schlüssel. |

Fotos liegen als `photos/<Token>.jpg`. Ein Hintergrund-Thread löscht jede Minute alles, was älter als `--ttl` ist. `photos/`, `bin/`, `certs/` und `.pairkey` stehen in `.gitignore` und werden nie committet.

---

## Testliste vor dem Einsatz

Am besten am Vortag mit dem echten Laptop, dem echten WLAN und einem fremden Handy:

- [ ] GitHub Pages ist an, `https://schnax3.github.io/web-cam-upload/` öffnet sich
- [ ] `start.bat` / `start.sh` startet ohne Fehler, Browser öffnet sich, **Server ✓ Tunnel ✓** ist grün
- [ ] Windows-Firewall: Python in privaten Netzwerken erlaubt
- [ ] Foto mit der Laptop-Kamera, QR erscheint
- [ ] QR mit einem fremden Handy **im Mobilfunk** (WLAN aus) scannen, Foto lädt
- [ ] Filter wechseln, Herunterladen funktioniert, Datei ist in der Foto-App/Downloads
- [ ] Eigenes Handy koppeln (Zertifikatswarnung bestätigen, Kamera erlauben): Livebild erscheint am Laptop, Laptop-Kamera pausiert
- [ ] Handy quer halten: Auf dem Laptop **verschwindet der Kopplungs-QR**, nur noch das Livebild im Vollbild (mit **F**)
- [ ] **Enter** löst am Handy aus (Countdown), Foto erscheint mit QR-Code, **Enter** schließt die Anzeige
- [ ] Mit dem fremden Handy: Format **Quer**, **Hochkant 3:4** und **9:16** herunterladen, Ausschnitt stimmt (Mitte des Querbilds)
- [ ] Maus bewegen: Bedienleiste erscheint, „Einstellungen“ und „Nur Kamerabild zeigen“ funktionieren
- [ ] 🔄 wechselt zwischen Hinter- und Frontkamera
- [ ] Handy-Seite schließen: nach ca. 4 s ist wieder die Laptop-Kamera aktiv und der Kopplungs-QR wieder da
- [ ] 🗑️ Alle Fotos löschen funktioniert
- [ ] Server beenden und neu starten: neues Foto geht, alter QR sagt sauber „nicht erreichbar“
- [ ] Laptop-Ruhezustand ist aus, Netzteil steckt

---

## Anpassen

- **Filter ändern oder ergänzen:** In `foto.html` die Liste `FILTERS` bearbeiten. Jeder Eintrag hat einen Namen und beliebige der Werte `gray`, `sepia` (0 bis 1), `sat`, `contrast`, `bright` (Faktoren, 1 = unverändert), `tint` (Faktoren für Rot, Grün, Blau) und `vignette` (0 bis 1). Änderungen an `foto.html` müssen nach GitHub gepusht werden.
- **Aussehen:** Farben stehen oben in `style.css` unter `:root`.
- **Titel, Countdown, Foto-Größe:** `config.js`.
- **Eigene Adresse der Seite (z. B. eigene Domain):** `PAGES_URL` in `config.js` und `--origin` beim Server setzen.
