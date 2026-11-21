# web-cam-upload

Foto-Aktion für den Aktionsstand: Foto aufnehmen → QR-Code erscheint → Besucher scannen ihn mit dem eigenen Handy und landen auf einer Seite mit **Vorschau, Filtern und Download-Button**.

**Alles läuft lokal auf deinem Laptop.** Nur das Abholen der Fotos geht über das Internet (GitHub-Pages-Seite + Tunnel). Die Fotos liegen ausschließlich auf dem Laptop und sind nur mit dem Token im QR-Code abrufbar.

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
        ┌──────────────── lokal, auf dem Laptop und im WLAN ────────────────┐
        │                                                                   │
        │  Laptop-Browser: http://localhost:8765/   (Laptop-Kamera)         │
        │  Handy im WLAN:  http://<Laptop-IP>:8765/handy.html#<Schlüssel>   │
        │            └──────────► foto_server.py (Python) ◄───┘             │
        │                          speichert photos/<Token>.jpg             │
        └───────────────────────────────┬───────────────────────────────────┘
                                        │ Cloudflare-Tunnel (https), nur GET /img/<Token>
                                        ▼
 Besucher scannt QR ─► foto.html#s=<Tunnel>&t=<Token>  (GitHub Pages) ─► Vorschau, Filter, Download
```

**Handy hat Vorrang:** Solange kein Handy verbunden ist, benutzt die Laptop-Seite die Laptop-Kamera. Sobald du ein Handy koppelst (auch nachträglich), pausiert die Laptop-Kamera, die Laptop-Seite zeigt „Handy-Kamera aktiv“ und neue Fotos kommen vom Handy. Schließt du die Handy-Seite (oder das Handy verliert das WLAN), geht die Laptop-Kamera nach ca. 8 Sekunden von selbst wieder an.

| Datei | Aufgabe |
|---|---|
| `foto_server.py` | Server auf dem Laptop. Liefert Laptop- und Handy-Seite aus, speichert Fotos, gibt sie nur per Token heraus, löscht sie nach Ablauf, startet den Tunnel. Nur Python-Standardbibliothek, keine Pakete nötig. |
| `laptop.html` | Seite für den Laptop: Laptop-Kamera mit Countdown, Handy-Kopplung, QR-Code zum Abholen. |
| `handy.html` | Seite für das Handy: Foto mit der Kamera-App aufnehmen, wird automatisch an den Laptop geschickt. |
| `foto.html` | Seite für Besucher nach dem Scannen (läuft auf GitHub Pages): Vorschau, 9 Filter, Herunterladen, Teilen. |
| `config.js` | Einstellungen (Seiten-Adresse, Countdown, Foto-Größe, Titel). |
| `common.js`, `style.css` | Gemeinsamer Code und Aussehen. |
| `lib/qrcode.js` | QR-Erzeugung, lokal eingebunden, kein CDN nötig. |
| `index.html` | Startseite mit Links (für GitHub Pages). |

Es werden **keine externen Dienste** für Kamera, Kopplung oder Speicherung benutzt. Nur `foto.html` kommt von GitHub Pages und das Foto selbst läuft durch den Tunnel.

---

## Einmalige Einrichtung

### 1. GitHub Pages einschalten

Repo auf GitHub → **Settings → Pages** → *Build and deployment*: Source **Deploy from a branch**, Branch **main**, Ordner **/ (root)** → Save.

Nach ein bis zwei Minuten ist die Seite erreichbar unter:

```
https://schnax3.github.io/web-cam-upload/
```

Sie wird nur für `foto.html` gebraucht (die Seite, die der QR-Code öffnet). Wenn dein Repo oder dein Benutzername anders heißt, die Adresse in `config.js` bei `PAGES_URL` anpassen (mit `/` am Ende) und den Server mit `--origin` starten (siehe unten).

### 2. Python

Python 3.9 oder neuer. Prüfen:

```
python --version
```

(Unter Linux/macOS evtl. `python3`.) Es müssen keine Pakete installiert werden.

### 3. cloudflared (der Tunnel zum Abholen)

Die Handys der Besucher müssen ihr Foto aus dem Internet vom Laptop holen können. Dafür nutzt das Skript einen kostenlosen Cloudflare-„Quick Tunnel“. Es ist **kein Account** nötig.

| System | Installation |
|---|---|
| Windows | `winget install Cloudflare.cloudflared` |
| macOS | `brew install cloudflared` |
| Linux | Paket von <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/> |

Danach **neues Terminal öffnen** und prüfen:

```
cloudflared --version
```

Statt Cloudflare geht auch ein eigener Tunnel (Tailscale Funnel, ngrok, eigener Cloudflare-Tunnel mit fester Adresse): Server mit `--public-url https://deine-adresse` starten.

### 4. Windows-Firewall (nur beim ersten Start)

Windows fragt beim ersten Start, ob Python im Netzwerk kommunizieren darf. **Zugriff in privaten Netzwerken erlauben.** Ohne das kann das Handy den Laptop im WLAN nicht erreichen.

---

## Am Stand

### Starten

Im Projektordner:

```
python foto_server.py
```

Das Skript startet den Server, startet den Tunnel und gibt die Adressen aus, z. B.:

```
Foto-Server läuft (Fotos werden nach 24 h gelöscht)
Starte Cloudflare-Tunnel …

Laptop-Seite:  http://localhost:8765/
Handy-Seite:   http://192.168.1.23:8765/handy.html#k3Jd8sLq0xw   (Handy im selben WLAN; auf der Laptop-Seite steht ein QR dafür)
Abhol-Adresse (nur per Token): https://xyz-abc.trycloudflare.com
```

Das Terminal-Fenster muss während der ganzen Aktion offen bleiben.

### Laptop-Seite öffnen

Im Browser des Laptops **`http://localhost:8765/`** öffnen und die Kamera erlauben. (Nicht die GitHub-Pages-Adresse: Die Laptop-Seite läuft lokal.) Oben rechts zeigt die Seite zwei Anzeigen:

| Anzeige | Bedeutung |
|---|---|
| **Server ✓** (grün) | Foto-Server und Tunnel laufen. Alles gut. |
| **Server nicht erreichbar** (rot) | `foto_server.py` läuft nicht. |
| **Server ohne Tunnel** (rot) | Server läuft, aber es gibt keine Abhol-Adresse (cloudflared fehlt oder `--no-tunnel`). |
| **Handy verbunden ✓** (grün) | Ein Handy ist gekoppelt. Die Handy-Kamera hat Vorrang. |

### Foto mit der Laptop-Kamera

1. **📸 Foto machen** klicken.
2. Countdown 3-2-1, Blitz, das Foto wird gespeichert.
3. Es erscheint ein großer QR-Code. Der Besucher scannt ihn mit der Handy-Kamera.
4. **Nächstes Foto** klicken für die nächste Person.

### Handy hinzufügen (jederzeit)

1. Handy ins **selbe WLAN** wie der Laptop.
2. Rechts auf der Laptop-Seite im Kasten **„Handy koppeln“** den QR-Code mit dem Handy scannen.
3. Auf dem Handy steht oben **„Mit Laptop verbunden ✓“**. Gleichzeitig wechselt die Laptop-Seite auf **„Handy-Kamera aktiv“**, die Laptop-Kamera wird ausgeschaltet.
4. Am Handy **📷 Foto aufnehmen** (hintere Kamera) oder **🤳 Selfie** (vordere Kamera) tippen. Es öffnet sich die Kamera-App des Handys. Nach dem Foto wird es automatisch gesendet.
5. Das Foto erscheint am Laptop samt QR-Code zum Abholen. Das Handy zeigt „Foto angekommen ✓“ und ist sofort bereit für das nächste.

Zurück zur Laptop-Kamera: Handy-Seite schließen. Nach ca. 8 Sekunden schaltet die Laptop-Seite wieder auf die Laptop-Kamera.

Die Kopplung bleibt gültig, auch nach Neustart des Servers (der Schlüssel steht in der Datei `.pairkey`), solange sich die WLAN-Adresse des Laptops nicht ändert. Das Handy kann denselben QR/Link also weiterverwenden. Bei einer neuen Adresse den QR neu scannen.

### Was der Besucher sieht

Nach dem Scannen öffnet sich `foto.html`:

- Vorschau des Fotos
- Filterleiste mit Mini-Vorschauen: Original, Schwarz-Weiß, Sepia, Vintage, Lebendig, Warm, Kühl, Dramatisch, Pastell
- **⬇️ Herunterladen** speichert das Foto mit dem gewählten Filter als JPG
- **📤 Teilen / Sichern** (nur auf Handys, die das können) öffnet das Teilen-Menü, dort „Bild sichern“ bzw. direkt in die Fotos-App

### Beenden

Im Terminal **Strg+C**. Der Tunnel wird mitbeendet. Die Fotos im Ordner `photos/` bleiben liegen und werden beim nächsten Start nach Ablauf der Zeit gelöscht. Wer alles sofort löschen will, löscht den Ordner `photos/`.

---

## Einstellungen

### `config.js`

| Eintrag | Standard | Bedeutung |
|---|---|---|
| `PAGES_URL` | `https://schnax3.github.io/web-cam-upload/` | Adresse der GitHub-Pages-Seite. Dorthin führt der QR-Code zum Abholen. Mit `/` am Ende. |
| `LOCAL_SERVER` | leer | Adresse des Foto-Servers. Leer = derselbe Server, von dem die Seite kommt. Normalerweise nie ändern. |
| `MAX_SIZE` | `1600` | Längste Kante des Fotos in Pixeln. Größer = schärfer, aber größere Dateien. |
| `COUNTDOWN` | `3` | Sekunden bis zum Auslösen der Laptop-Kamera. `0` = sofort. |
| `TITLE` | `Foto-Aktion` | Titel oben auf der Laptop-Seite. |

Die Laptop- und Handy-Seite kommen direkt vom Server, Änderungen an `config.js` wirken dort sofort nach Neuladen. `foto.html` auf GitHub Pages liest `config.js` nicht, dort ist nichts zu pushen.

### `foto_server.py`

| Option | Standard | Bedeutung |
|---|---|---|
| `--ttl 2` | `24` | Stunden, nach denen Fotos gelöscht werden. Bruchteile gehen auch (`--ttl 0.5`). |
| `--port 8766` | `8765` | Port des Servers. |
| `--origin https://...` | `https://schnax3.github.io` | Adresse der Pages-Seite (nur Protokoll + Domain, ohne Pfad). Nur diese Seite darf Fotos im Browser abrufen. |
| `--public-url https://...` | Cloudflare-Tunnel | Eigene öffentliche https-Adresse statt Cloudflare-Tunnel. |
| `--no-tunnel` | aus | Keinen Tunnel starten (zum Testen). |
| `--no-lan` | aus | Nur der Laptop selbst darf zugreifen, kein Handy im WLAN. |
| `--lan-ip 192.168.1.23` | automatisch | WLAN-Adresse des Laptops, falls die automatische Erkennung die falsche nimmt (z. B. bei VPN oder mehreren Netzwerkkarten). |
| `--key abc123` | zufällig | Eigener Kopplungsschlüssel (6–64 Zeichen: Buchstaben, Ziffern, `_`, `-`). Standard: zufällig erzeugt und in `.pairkey` gespeichert. Datei löschen = neuer Schlüssel. |

Beispiele:

```
python foto_server.py --ttl 2
python foto_server.py --lan-ip 192.168.178.20
python foto_server.py --public-url https://laptop.mein-tailnet.ts.net
python foto_server.py --no-tunnel --no-lan
```

---

## Sicherheit und Datenschutz

### Wer darf was?

Der Server prüft bei **jeder** Anfrage, woher sie kommt:

| Herkunft | Erkennung | Erlaubt |
|---|---|---|
| **Laptop selbst** | Loopback-Adresse, kein Tunnel-Header | Alles (Laptop-Seite, Foto hochladen, Status). |
| **Handy im WLAN** | private Adresse, kein Tunnel-Header | Nur `handy.html` (samt `style.css`, `config.js`), „Lebenszeichen“ und Foto senden, **und nur mit dem Kopplungsschlüssel**. |
| **Internet (Tunnel)** | Tunnel-Header (`Cf-Ray`, `X-Forwarded-For`, …) | Nur `GET /img/<Token>`. Alles andere: 403/404. |

Weitere Schutzmaßnahmen:

- Der **Schlüssel** für das Handy ist zufällig (ca. 72 Bit). Jemand anderes im selben WLAN, der die Handy-Adresse ohne Schlüssel aufruft, kann nichts senden.
- Der `Host`-Header muss `localhost` bzw. eine IP-Adresse sein (Schutz vor DNS-Rebinding), und ein Browser-`Origin` muss zur Seite passen (fremde Webseiten können nichts einschleusen).
- Es werden nur JPEG-Dateien bis 12 MB angenommen.
- Über den Tunnel ist **nichts außer den Fotos** erreichbar: Weder `laptop.html` noch `foto_server.py` noch der Ordner `photos/` lassen sich von außen laden.

### Wer kann Fotos sehen?

- Jedes Foto bekommt beim Speichern einen zufälligen Token (128 Bit, `secrets.token_urlsafe`). Der ist nicht erratbar.
- Der Token steht nur im QR-Code, im `#`-Teil des Links. Dieser Teil wird vom Browser nie an einen Server geschickt, taucht also in keinen Zugriffsprotokollen auf.
- Es gibt keine Liste, keinen Ordnerinhalt, keine Suche. Falscher Token = 404.
- Wer den QR-Code fotografiert oder den Link weitergibt, kann das Foto bis zum Ablauf sehen. Das ist bei „nur mit QR-Code“ nicht vermeidbar.

### Welche Dienste sind beteiligt?

| Dienst | Was er sieht |
|---|---|
| **GitHub Pages** | Liefert nur `foto.html` und die zugehörige Seite (Code). Fotos laufen nie darüber. |
| **Cloudflare (Tunnel)** | Leitet die Abrufe der Fotos durch. Technisch sieht Cloudflare den Datenverkehr, wie bei jedem Tunnel/Proxy. |

Kamera, Kopplung und Speicherung laufen komplett im lokalen Netz. Es gibt keinen Vermittlungsserver mehr.

### Hinweise für den Stand

- Es werden Fotos von Personen gemacht. Ein gut sichtbares Schild hilft: „Foto wird bis zu 24 Stunden auf dem Laptop gespeichert und danach gelöscht; nur mit dem QR-Code abrufbar.“ Bei Minderjährigen vorher klären, ob das für eure Veranstaltung eine Einwilligung der Eltern braucht.
- Nach der Aktion `photos/` löschen oder `--ttl` kurz wählen.
- Das WLAN sollte nicht für Fremde offen sein (die Handy-Seite ist im ganzen WLAN erreichbar, durch den Schlüssel aber nur für das gekoppelte Handy nutzbar). Am besten Handy-Hotspot oder eigenes WLAN für den Stand.
- Der Laptop sollte während der Aktion nicht in den Ruhezustand gehen (Energieeinstellungen).

---

## Probleme und Lösungen

**Laptop-Seite zeigt „Server nicht erreichbar“**
- Läuft `python foto_server.py` noch? Das Terminal-Fenster darf nicht geschlossen sein.
- Die Seite muss unter `http://localhost:8765/` geöffnet sein, nicht unter der GitHub-Pages-Adresse.
- Port belegt? Mit `--port 8766` starten und `http://localhost:8766/` öffnen.

**Handy zeigt „Keine Verbindung zum Laptop“ oder die Seite lädt gar nicht**
- Handy und Laptop müssen im **selben WLAN** sein (nicht Mobilfunk, nicht Gast-WLAN mit Geräteisolation). Manche öffentlichen/Schul-WLANs trennen Geräte voneinander: dann Handy-Hotspot für beide nutzen (Laptop ins Hotspot-WLAN).
- Windows-Firewall: Python für **private Netzwerke** erlauben (Einstellungen → Firewall → App zulassen).
- Falsche Adresse im QR (z. B. VPN-Adapter)? Server mit `--lan-ip <richtige WLAN-IP>` starten. Die IP des Laptops zeigt `ipconfig` (Windows) bzw. `ip a` (Linux).
- „Schlüssel falsch – QR neu scannen“: QR auf der Laptop-Seite erneut scannen (der Schlüssel wurde geändert, z. B. wegen gelöschter `.pairkey`).

**Handy hat Vorrang, aber ich will die Laptop-Kamera**
- Handy-Seite schließen. Nach ca. 8 Sekunden ist wieder die Laptop-Kamera aktiv.

**Laptop-Seite bleibt auf „Handy-Kamera aktiv“, obwohl das Handy weg ist**
- Das Handy sendet nur, solange die Seite offen und der Bildschirm an ist. Sperrt das Handy den Bildschirm, bricht die Verbindung nach 8 Sekunden ab und die Laptop-Kamera übernimmt. Beim Entsperren verbindet sich das Handy von selbst wieder.

**„Server ohne Tunnel“ / „cloudflared ist nicht installiert“**
- cloudflared installieren (siehe oben), **neues Terminal öffnen**, `cloudflared --version` prüfen.
- Oder `--public-url` mit einem eigenen Tunnel angeben.
- Firmen- oder Schulnetz kann Tunnel blockieren. Dann Handy-Hotspot für den Laptop nutzen.

**Laptop-Kamera zeigt schwarzes Bild oder Fehlermeldung**
- Kamera-Zugriff im Browser erlauben (Schloss-Symbol in der Adresszeile).
- Wird die Kamera von einem anderen Programm benutzt (Teams, Zoom, OBS)? Dort beenden.

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

### Warum öffnet das Handy die Kamera-App statt einer Live-Vorschau?

Browser erlauben den Live-Zugriff auf die Kamera nur über https oder `localhost`. Die Handy-Seite läuft aber über `http://<Laptop-IP>` im lokalen Netz (ohne Zertifikat, ohne Warnmeldungen). Deshalb nutzt sie das `capture`-Feld: Das öffnet die Kamera-App des Handys, die ohnehin die bessere Qualität hat. Das Foto wird danach auf `MAX_SIZE` verkleinert und gesendet.

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
| `GET /info` | Laptop | `public_url`, `ttl`, Handy-Link (`lan_url`). |
| `GET /status` | Laptop | `phone` (Handy verbunden?), `seq` (Zähler der Handy-Fotos), `token` (letztes Handy-Foto). Die Laptop-Seite fragt das jede Sekunde ab. |
| `POST /upload` | Laptop | Foto der Laptop-Kamera (JPEG) speichern, gibt `{token, expires_in}` zurück. |
| `POST /phone/hello` | Handy/Laptop + Schlüssel | Lebenszeichen des Handys alle 3 s. Nach 8 s ohne Lebenszeichen gilt das Handy als getrennt. |
| `POST /phone/photo` | Handy/Laptop + Schlüssel | Foto vom Handy (JPEG) speichern, erhöht `seq`. |
| `GET /img/<Token>` | jeder mit Token | Liefert das Foto. |
| `GET /`, `*.html`, `*.js`, `*.css` | Laptop alles, Handy nur `handy.html`, `style.css`, `config.js` | Seiten ausliefern. Nur diese Dateitypen im Projektordner, nie `.py` oder Fotos. |

Fotos liegen als `photos/<Token>.jpg`. Ein Hintergrund-Thread löscht jede Minute alles, was älter als `--ttl` ist. Der Ordner und `.pairkey` stehen in `.gitignore`. In der Server-Ausgabe erscheinen Tokens nicht.

---

## Testliste vor dem Einsatz

Am besten am Vortag mit dem echten Laptop, dem echten WLAN und einem fremden Handy:

- [ ] GitHub Pages ist an, `https://schnax3.github.io/web-cam-upload/` öffnet sich
- [ ] `python foto_server.py` zeigt eine `trycloudflare.com`-Adresse und eine Handy-Adresse mit der richtigen WLAN-IP
- [ ] `http://localhost:8765/`: **Server ✓** grün, Laptop-Kamera läuft
- [ ] Foto mit der Laptop-Kamera, QR erscheint
- [ ] QR mit einem fremden Handy **im Mobilfunk** (WLAN aus) scannen, Foto lädt
- [ ] Filter wechseln, Herunterladen funktioniert, Datei ist in der Foto-App/Downloads
- [ ] Eigenes Handy im WLAN koppeln: Laptop-Seite wechselt auf „Handy-Kamera aktiv“, Laptop-Kamera geht aus
- [ ] Foto am Handy aufnehmen, es erscheint am Laptop mit QR-Code
- [ ] Handy-Seite schließen: nach ca. 8 s ist wieder die Laptop-Kamera aktiv
- [ ] Server beenden und neu starten: neues Foto geht, altes sagt sauber „nicht erreichbar“
- [ ] Windows-Firewall erlaubt Python im privaten Netzwerk, Laptop-Ruhezustand ist aus, Netzteil steckt

---

## Anpassen

- **Filter ändern oder ergänzen:** In `foto.html` die Liste `FILTERS` bearbeiten. Jeder Eintrag hat einen Namen und beliebige der Werte `gray`, `sepia` (0 bis 1), `sat`, `contrast`, `bright` (Faktoren, 1 = unverändert), `tint` (Faktoren für Rot, Grün, Blau) und `vignette` (0 bis 1). Änderungen an `foto.html` müssen nach GitHub gepusht werden.
- **Aussehen:** Farben stehen oben in `style.css` unter `:root`.
- **Titel, Countdown, Foto-Größe:** `config.js`.
- **Eigene Adresse der Seite (z. B. eigene Domain):** `PAGES_URL` in `config.js` und `--origin` beim Server setzen.
