# web-cam-upload

Foto-Aktion für den Aktionsstand: Foto aufnehmen → QR-Code erscheint → Besucher scannen ihn mit dem eigenen Handy und landen auf einer Seite mit **Vorschau, Filtern und Download-Button**.

Die Fotos liegen **nur auf deinem Laptop** (kein Cloud-Bilderdienst). Abrufbar sind sie nur mit dem Token, der im QR-Code steht.

## Inhalt

1. [Überblick](#überblick)
2. [Einmalige Einrichtung](#einmalige-einrichtung)
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
 Kamera (Laptop-Webcam oder gekoppeltes Handy)
        │
        ▼
 laptop.html  (GitHub Pages, im Browser des Laptops)
        │  POST /upload  (nur lokal erlaubt)
        ▼
 foto_server.py  (Python auf deinem Laptop, 127.0.0.1)
        │  speichert photos/<Token>.jpg
        │
        │  Cloudflare-Tunnel  (https://irgendwas.trycloudflare.com)
        │
 Besucher scannt QR ─► foto.html#s=<Tunnel-Adresse>&t=<Token>  (GitHub Pages)
                            └─► holt GET /img/<Token> und zeigt Vorschau + Filter
```

| Datei | Aufgabe |
|---|---|
| `foto_server.py` | Server auf dem Laptop. Speichert Fotos, gibt sie nur per Token heraus, löscht sie nach Ablauf, startet den Tunnel. Nur Python-Standardbibliothek, keine Pakete nötig. |
| `laptop.html` | Seite für den Laptop: Webcam-Vorschau, Foto mit Countdown, QR-Code zum Abholen. Zeigt außerdem einen QR-Code, um ein Handy als Kamera zu koppeln. |
| `handy.html` | Seite für das Handy als Kamera. Wird über den Kopplungs-QR der Laptop-Seite geöffnet und schickt das Foto direkt an den Laptop. |
| `foto.html` | Seite, die Besucher nach dem Scannen sehen: Vorschau, 9 Filter, Herunterladen, Teilen. |
| `config.js` | Einstellungen (Seiten-Adresse, Countdown, Foto-Größe, Titel). |
| `common.js`, `style.css` | Gemeinsamer Code und Aussehen. |
| `lib/` | `peerjs.min.js` (Handy-Kopplung) und `qrcode.js` (QR-Erzeugung), lokal eingebunden, kein CDN nötig. |
| `index.html` | Startseite mit Links zu Laptop- und Handy-Seite. |

Es gibt zwei Wege, ein Foto aufzunehmen. Beide enden gleich (Foto landet auf dem Laptop-Server, QR-Code erscheint auf dem Laptop):

- **Laptop-Webcam:** Auf der Laptop-Seite „Foto machen“ klicken.
- **Handy als Kamera:** Handy scannt den Kopplungs-QR auf der Laptop-Seite, löst dort aus, das Foto erscheint auf dem Laptop.

---

## Einmalige Einrichtung

### 1. GitHub Pages einschalten

Repo auf GitHub → **Settings → Pages** → *Build and deployment*: Source **Deploy from a branch**, Branch **main**, Ordner **/ (root)** → Save.

Nach ein bis zwei Minuten ist die Seite erreichbar unter:

```
https://schnax3.github.io/web-cam-upload/
```

Wenn dein Repo oder dein Benutzername anders heißt, die Adresse in `config.js` bei `PAGES_URL` anpassen (mit `/` am Ende) und den Server mit `--origin` starten (siehe unten).

### 2. Python

Python 3.9 oder neuer. Prüfen:

```
python --version
```

(Unter Linux/macOS evtl. `python3`.) Es müssen keine Pakete installiert werden.

### 3. cloudflared (der Tunnel)

Die Handys der Besucher müssen deinen Laptop aus dem Internet erreichen. Dafür nutzt das Skript einen kostenlosen Cloudflare-„Quick Tunnel“. Es ist **kein Account** nötig.

| System | Installation |
|---|---|
| Windows | `winget install Cloudflare.cloudflared` |
| macOS | `brew install cloudflared` |
| Linux | Paket von <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/> |

Danach **neues Terminal öffnen** und prüfen:

```
cloudflared --version
```

Du kannst stattdessen auch einen eigenen Tunnel verwenden (Tailscale Funnel, ngrok, eigener Cloudflare-Tunnel mit fester Adresse). Dann den Server mit `--public-url https://deine-adresse` starten.

---

## Am Stand

### Starten

Im Projektordner:

```
python foto_server.py
```

Das Skript

1. startet den Server auf `127.0.0.1:8765`,
2. startet den Tunnel und wartet, bis die Adresse da ist,
3. gibt die Adressen aus, z. B.:

```
Foto-Server läuft auf http://127.0.0.1:8765  (Fotos werden nach 24 h gelöscht)
Starte Cloudflare-Tunnel …
Öffentliche Adresse (nur per QR-Token abrufbar): https://xyz-abc.trycloudflare.com

Laptop-Seite:  https://schnax3.github.io/web-cam-upload/laptop.html
oder lokal:    http://localhost:8765/   (falls der Browser die erste nicht erlaubt)
```

Das Terminal-Fenster muss während der ganzen Aktion offen bleiben.

### Laptop-Seite öffnen

`https://schnax3.github.io/web-cam-upload/laptop.html` im Browser öffnen und die Kamera erlauben. Oben rechts zeigt die Seite zwei Anzeigen:

| Anzeige | Bedeutung |
|---|---|
| **Server ✓** (grün) | Foto-Server und Tunnel laufen. Alles gut. |
| **Server nicht erreichbar** (rot) | `foto_server.py` läuft nicht oder der Browser blockiert den Zugriff. Siehe [Probleme](#probleme-und-lösungen). |
| **Server ohne Tunnel** (rot) | Server läuft, aber es gibt keine öffentliche Adresse (cloudflared fehlt oder `--no-tunnel`). |
| **Handy verbunden ✓** | Mindestens ein Handy ist als Kamera gekoppelt. |

### Foto per Laptop-Webcam

1. **📸 Foto machen** klicken.
2. Countdown 3-2-1, Blitz, Foto wird hochgeladen.
3. Es erscheint ein großer QR-Code. Der Besucher scannt ihn mit der Handy-Kamera.
4. **Nächstes Foto** klicken für die nächste Person.

### Foto per Handy

1. Auf der Laptop-Seite rechts den Kasten **„Handy als Kamera nutzen“** mit dem QR-Code zeigen.
2. Mit dem Handy scannen, Kamera erlauben. Oben links muss **„Mit Laptop verbunden ✓“** stehen.
3. Am Handy den runden Auslöser drücken (🔄 wechselt zwischen Front- und Rückkamera).
4. Das Foto erscheint am Laptop samt QR-Code. Das Handy zeigt „Foto angekommen ✓“ und ist sofort für das nächste Foto bereit.

Die Kopplung bleibt erhalten, auch wenn die Laptop-Seite neu geladen wird (der Code wird im Browser des Laptops gespeichert). Bricht die Verbindung ab, versucht das Handy sich alle 3 Sekunden neu zu verbinden.

### Was der Besucher sieht

Nach dem Scannen öffnet sich `foto.html`:

- Vorschau des Fotos
- Filterleiste mit Mini-Vorschauen: Original, Schwarz-Weiß, Sepia, Vintage, Lebendig, Warm, Kühl, Dramatisch, Pastell
- **⬇️ Herunterladen** speichert das Foto mit dem gewählten Filter als JPG
- **📤 Teilen / Sichern** (nur auf Handys, die das können) öffnet das Teilen-Menü, dort „Bild sichern“ bzw. direkt in die Fotos-App

### Beenden

Im Terminal **Strg+C**. Der Tunnel wird mitbeendet. Die Fotos im Ordner `photos/` bleiben liegen. Wer alles sofort löschen will, löscht den Ordner `photos/` (bei laufendem Server ist das ebenfalls in Ordnung).

---

## Einstellungen

### `config.js`

| Eintrag | Standard | Bedeutung |
|---|---|---|
| `PAGES_URL` | `https://schnax3.github.io/web-cam-upload/` | Adresse der GitHub-Pages-Seite. Dorthin führen die QR-Codes. Mit `/` am Ende. |
| `LOCAL_SERVER` | `http://127.0.0.1:8765` | Adresse des Foto-Servers auf dem Laptop. Nur ändern, wenn du `--port` änderst. |
| `MAX_SIZE` | `1600` | Längste Kante des Fotos in Pixeln. Größer = schärfer, aber größere Dateien. |
| `COUNTDOWN` | `3` | Sekunden bis zum Auslösen. `0` = sofort. |
| `TITLE` | `Foto-Aktion` | Titel oben auf der Laptop-Seite. |

Änderungen an `config.js` müssen nach GitHub gepusht werden, damit sie auf der Pages-Seite ankommen. Zum schnellen Testen kannst du die Laptop-Seite lokal vom Server laden (`http://localhost:8765/`), dann wirken Änderungen sofort.

### `foto_server.py`

| Option | Standard | Bedeutung |
|---|---|---|
| `--ttl 2` | `24` | Stunden, nach denen Fotos gelöscht werden. Bruchteile gehen auch (`--ttl 0.5`). |
| `--port 8766` | `8765` | Port des Servers. Dann auch `LOCAL_SERVER` in `config.js` anpassen. |
| `--origin https://...` | `https://schnax3.github.io` | Adresse der Pages-Seite (nur Protokoll + Domain, ohne Pfad). Nur diese Seite darf mit dem Server sprechen. |
| `--public-url https://...` | Cloudflare-Tunnel | Eigene öffentliche https-Adresse statt Cloudflare-Tunnel. |
| `--no-tunnel` | aus | Keinen Tunnel starten (zum Testen). |

Beispiele:

```
python foto_server.py --ttl 2
python foto_server.py --public-url https://laptop.mein-tailnet.ts.net
python foto_server.py --no-tunnel
```

---

## Sicherheit und Datenschutz

### Wer kann Fotos sehen?

- Jedes Foto bekommt beim Speichern einen zufälligen Token (128 Bit, mit `secrets.token_urlsafe`). Der ist nicht erratbar.
- Der Token steht nur im QR-Code, im `#`-Teil des Links. Dieser Teil wird vom Browser nie an einen Server geschickt, taucht also in keinen Zugriffsprotokollen auf.
- Nach außen gibt es **nur** `GET /img/<Token>`. Es gibt keine Liste, keinen Ordnerinhalt, keine Suche. Falscher Token = 404.
- Wer den QR-Code fotografiert oder den Link weitergibt, kann das Foto bis zum Ablauf sehen. Das ist bei „nur mit QR-Code“ nicht vermeidbar.

### Wer kann Fotos hochladen oder den Server steuern?

Nur die Seite auf dem Laptop selbst. Der Server lehnt `/upload` und `/info` ab, wenn

- ein Tunnel-/Proxy-Header gesetzt ist (die Anfrage kommt also von außen),
- die Anfrage nicht von `127.0.0.1` kommt,
- der `Host`-Header nicht `127.0.0.1:<Port>` oder `localhost:<Port>` ist (Schutz vor DNS-Rebinding),
- der `Origin` nicht deine Pages-Seite oder localhost ist (Schutz vor fremden Webseiten, die im Browser des Laptops Fotos einschleusen wollen).

Zusätzlich werden nur JPEG-Dateien bis 12 MB angenommen. Der Server hört nur auf `127.0.0.1`, ist also im WLAN nicht direkt erreichbar, nur über den Tunnel und dort nur für `GET /img/<Token>`.

### Welche Dienste sind beteiligt?

| Dienst | Was er sieht |
|---|---|
| **GitHub Pages** | Liefert nur die Webseiten (Code). Fotos laufen nie darüber. |
| **Cloudflare (Tunnel)** | Leitet die Abrufe der Fotos durch. Technisch sieht Cloudflare den Datenverkehr, wie bei jedem Tunnel/Proxy. |
| **PeerJS-Server** (`0.peerjs.com`) | Vermittelt nur den Verbindungsaufbau zwischen Handy und Laptop (kurze zufällige IDs). Das Foto selbst geht direkt per WebRTC von Handy zu Laptop. |

### Hinweise für den Stand

- Es werden Fotos von Personen gemacht. Ein gut sichtbares Schild hilft: „Foto wird bis zu 24 Stunden auf dem Laptop gespeichert und danach gelöscht; nur mit dem QR-Code abrufbar.“ Bei Minderjährigen vorher klären, ob das für eure Veranstaltung eine Einwilligung der Eltern braucht.
- Nach der Aktion `photos/` löschen oder `--ttl` kurz wählen.
- Der Laptop sollte während der Aktion nicht in den Ruhezustand gehen (Energieeinstellungen).

---

## Probleme und Lösungen

**Laptop-Seite zeigt „Server nicht erreichbar“**
- Läuft `python foto_server.py` noch? Das Terminal-Fenster darf nicht geschlossen sein.
- Chrome/Edge fragen beim ersten Mal evtl., ob die Seite auf Geräte im lokalen Netzwerk zugreifen darf: **Erlauben**. Wurde es abgelehnt: Schloss-Symbol in der Adresszeile → Website-Einstellungen → Zugriff auf lokale Geräte erlauben.
- Safari und manche Browser (z. B. Brave mit Shields) blocken Zugriffe von einer https-Seite auf `http://127.0.0.1`. Dann die Laptop-Seite **direkt vom Server** öffnen: `http://localhost:8765/`. Das geht in der Regel auch für die Kamera, weil `localhost` als sicher gilt.
- Port belegt? Mit `--port 8766` starten und `LOCAL_SERVER` in `config.js` anpassen (oder lokal über `http://localhost:8766/`).

**„Server ohne Tunnel“ / „cloudflared ist nicht installiert“**
- cloudflared installieren (siehe oben), **neues Terminal öffnen**, `cloudflared --version` prüfen.
- Oder `--public-url` mit einem eigenen Tunnel angeben.
- Firmen- oder Schulnetz kann Tunnel blockieren. Dann Handy-Hotspot für den Laptop nutzen.

**Kamera zeigt schwarzes Bild oder Fehlermeldung**
- Kamera-Zugriff im Browser erlauben (Schloss-Symbol in der Adresszeile).
- Wird die Kamera von einem anderen Programm benutzt (Teams, Zoom, OBS)? Dort beenden.
- Auf dem Handy die Seite nicht in einer In-App-Ansicht öffnen (z. B. Scanner-App mit eingebautem Browser), sondern in Safari/Chrome.

**Handy verbindet sich nicht („Laptop nicht gefunden …“)**
- Die Laptop-Seite muss geöffnet sein. Wurde sie in einem anderen Browser oder Profil geöffnet oder der Browserspeicher gelöscht, gibt es einen neuen Code. Dann den Kopplungs-QR neu scannen.
- Kommt trotzdem keine Verbindung zustande, ist meist ein strenges Netz schuld (Mobilfunk mit CGNAT, Firmen-WLAN). Handy und Laptop ins **gleiche WLAN** bringen. Für diese Verbindung gibt es keinen TURN-Server.

**Foto-Seite meldet „Dieses Foto gibt es nicht mehr“**
- Abgelaufen (`--ttl`) oder `photos/` wurde gelöscht.

**Foto-Seite meldet „Der Foto-Server ist gerade nicht erreichbar“**
- Laptop aus, offline, Server oder Tunnel beendet. Nach einem Neustart des Servers hat sich die Tunnel-Adresse geändert, **alte QR-Codes funktionieren dann nicht mehr**. Neue Fotos machen.

**Der QR-Code lässt sich schlecht scannen**
- Browserfenster größer machen oder den Laptop-Bildschirm heller stellen. Der QR-Code skaliert mit dem Fenster. Er ist weiß hinterlegt und hat eine ruhige Zone, funktioniert also auch auf dunklem Hintergrund.

**Download-Button macht am iPhone nichts Sichtbares**
- Das iPhone legt die Datei in der Dateien-App unter „Downloads“ ab. Besser: den Button **📤 Teilen / Sichern** nehmen und „Bild sichern“ wählen, dann landet es in Fotos.

---

## Technik im Detail

### Der Link im QR-Code

```
https://schnax3.github.io/web-cam-upload/foto.html#s=<Tunnel-Adresse>&t=<Token>
```

`foto.html` akzeptiert nur `https`-Server und Token aus 16–64 Zeichen `A-Z a-z 0-9 _ -`. Es holt `GET <Tunnel>/img/<Token>` und verarbeitet das Bild komplett im Browser.

### Filter

Die Filter rechnen jeden Pixel selbst (Sepia, Graustufen, Sättigung, Kontrast, Helligkeit, Farbtönung, Vignette). Sie nutzen bewusst nicht `canvas.filter`, das auf iPhones fehlt. Der Download enthält exakt das, was die Vorschau zeigt.

### Server-Schnittstellen

| Anfrage | Wer darf | Zweck |
|---|---|---|
| `GET /info` | nur lokal | Liefert `public_url` und `ttl`. Die Laptop-Seite prüft damit, ob alles läuft. |
| `POST /upload` | nur lokal | Nimmt ein JPEG entgegen, gibt `{token, expires_in}` zurück. |
| `GET /img/<Token>` | jeder mit Token | Liefert das Foto. |
| `GET /`, `/laptop.html`, `/*.js`, `/*.css` | nur lokal | Notlösung: Seiten direkt vom Server öffnen. Nur `.html`, `.css`, `.js` im Projektordner, nie `.py` oder Fotos. |

Fotos liegen als `photos/<Token>.jpg`. Ein Hintergrund-Thread löscht jede Minute alles, was älter als `--ttl` ist. Der Ordner steht in `.gitignore` und wird nie committet. In der Server-Ausgabe erscheinen Tokens nicht.

### Handy-Kopplung

Die Laptop-Seite erzeugt einen 6-stelligen Code (z. B. `k7m2xq`) und meldet sich damit als `wcu-k7m2xq` beim PeerJS-Vermittlungsserver an. Der Kopplungs-QR enthält `…/handy.html#k7m2xq`. Das Handy verbindet sich direkt per WebRTC, schickt das Foto als Binärdaten und bekommt eine Empfangsbestätigung. Der Code wird im `localStorage` des Laptop-Browsers gespeichert, damit ein Neuladen die Kopplung nicht zerstört.

---

## Testliste vor dem Einsatz

Am besten am Vortag mit dem echten Laptop, dem echten WLAN und einem fremden Handy:

- [ ] GitHub Pages ist an, `https://schnax3.github.io/web-cam-upload/` öffnet sich
- [ ] `python foto_server.py` zeigt eine `trycloudflare.com`-Adresse
- [ ] Laptop-Seite: **Server ✓** grün
- [ ] Foto mit Laptop-Webcam, QR erscheint
- [ ] QR mit einem fremden Handy **im Mobilfunk** (WLAN aus) scannen, Foto lädt
- [ ] Filter wechseln, Herunterladen funktioniert, Datei ist in der Foto-App/Downloads
- [ ] Handy als Kamera koppeln, Foto aufnehmen, erscheint am Laptop
- [ ] Laptop-Seite neu laden: Handy-Kopplung funktioniert weiter
- [ ] Server beenden und neu starten: neues Foto geht, altes sagt sauber „nicht erreichbar“
- [ ] Laptop-Ruhezustand ist aus, Netzteil steckt

---

## Anpassen

- **Filter ändern oder ergänzen:** In `foto.html` die Liste `FILTERS` bearbeiten. Jeder Eintrag hat einen Namen und beliebige der Werte `gray`, `sepia` (0 bis 1), `sat`, `contrast`, `bright` (Faktoren, 1 = unverändert), `tint` (Faktoren für Rot, Grün, Blau) und `vignette` (0 bis 1).
- **Aussehen:** Farben stehen oben in `style.css` unter `:root`.
- **Titel, Countdown, Foto-Größe:** `config.js`.
- **Eigene Adresse der Seite (z. B. eigene Domain):** `PAGES_URL` in `config.js` und `--origin` beim Server setzen.
