# web-cam-upload

Foto-Aktion für den Aktionsstand: Foto aufnehmen → QR-Code erscheint → Besucher scannen ihn und bekommen eine Seite mit Vorschau, Filtern und Download-Button.

Die Fotos liegen **nur auf deinem Laptop** (kein Cloud-Hoster). Wer den QR-Code nicht hat, kann ein Foto nicht abrufen: Jedes Foto hat einen zufälligen 128-Bit-Token, der nur im QR-Code steht. Es gibt keine Liste aller Bilder.

## So hängt es zusammen

```
Handy/Laptop-Kamera ──► laptop.html (GitHub Pages) ──► foto_server.py (dein Laptop, 127.0.0.1)
                                                              │  Cloudflare-Tunnel (https)
Besucher scannt QR ──► foto.html#s=<Tunnel>&t=<Token> ◄───────┘  holt Foto per Token
```

| Datei | Zweck |
|---|---|
| `foto_server.py` | Python-Server auf dem Laptop: speichert Fotos, liefert sie nur per Token aus, löscht sie nach 24 h, startet den Tunnel. Nur Standardbibliothek. |
| `laptop.html` | Webcam des Laptops, Foto machen, QR-Code anzeigen. Zeigt außerdem einen QR-Code, um ein Handy als Kamera zu koppeln. |
| `handy.html` | Handy-Kamera, wird über den QR auf der Laptop-Seite geöffnet und schickt das Foto direkt (WebRTC) an den Laptop. |
| `foto.html` | Seite für Besucher: Vorschau, 9 Filter, Herunterladen, Teilen. |
| `config.js` | Einstellungen (Seiten-Adresse, Countdown, Foto-Größe). |

## Einrichten (einmalig)

1. **GitHub Pages**: Repo → Settings → Pages → Branch `main`, Ordner `/ (root)`.
2. **Python 3** auf dem Laptop (ab 3.9).
3. **cloudflared** installieren (kostenlos, kein Account nötig). Windows: `winget install Cloudflare.cloudflared`, danach neues Terminal öffnen.

## Am Stand

```
python foto_server.py
```

Das Skript startet den Tunnel und zeigt die Adressen an. Danach `https://schnax3.github.io/web-cam-upload/laptop.html` im Browser öffnen (Kamera erlauben). Oben rechts muss „Server ✓“ stehen.

Optionen: `--ttl 2` (Fotos nach 2 h löschen), `--port`, `--public-url https://…` (eigener Tunnel statt Cloudflare), `--no-tunnel`.

Ändert sich die Tunnel-Adresse (bei jedem Start), ist das egal, sie steht im QR-Code. Alte QR-Codes funktionieren nach einem Neustart dann nicht mehr.

## Sicherheit

- Upload und `/info` nehmen nur Anfragen an, die direkt vom Laptop kommen (kein Tunnel-Header, Host/Origin geprüft). Von außen kann niemand Fotos hochladen.
- Nach außen gibt es nur `GET /img/<Token>`. Ohne Token: 404.
- Der Token steht im `#`-Teil des Links, der nie an einen Server geschickt wird.
- Wer den QR-Code fotografiert oder den Link weitergibt, kann das Foto bis zum Ablauf sehen. Das ist so gewollt.
- Fotos liegen im Ordner `photos/` (nicht im Git) und werden nach `--ttl` gelöscht.

## Hinweise

- Kamera geht nur über https (GitHub Pages) oder `localhost`.
- Chrome fragt beim ersten Mal evtl., ob die Seite auf Geräte im lokalen Netzwerk zugreifen darf. Erlauben. Alternativ die Laptop-Seite direkt vom Server öffnen: `http://localhost:8765/`.
- Der Laptop muss während der Aktion online bleiben, sonst kann niemand sein Foto laden.
