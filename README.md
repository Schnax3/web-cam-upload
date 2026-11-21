# web-cam-upload

Foto-Aktion für den Aktionsstand: Foto aufnehmen → QR-Code erscheint → Besucher scannen ihn mit dem eigenen Handy und speichern das Bild.

Reine statische Seite, läuft auf GitHub Pages (kein eigener Server).

## Seiten

| Seite | Zweck |
|---|---|
| `laptop.html` | Laptop-Webcam, Foto machen, QR-Code zum Abholen. Zeigt außerdem einen QR-Code, mit dem ein Handy als Kamera gekoppelt wird. |
| `handy.html` | Handy-Kamera. **Mit Kopplung** (`handy.html#CODE`, Link steht im QR auf der Laptop-Seite): Foto geht an den Laptop. **Ohne Kopplung**: Foto wird direkt hochgeladen und der QR erscheint auf dem Handy. |
| `foto.html` | Seite, die der Besucher nach dem Scannen sieht (Foto + Speichern-Button). |

## Einrichten

1. Kostenlosen API-Key bei <https://api.imgbb.com/> holen und in `config.js` bei `IMGBB_KEY` eintragen.
2. GitHub: Repo → **Settings → Pages** → Source: *Deploy from a branch*, Branch `main`, Ordner `/ (root)`.
3. Danach erreichbar unter `https://schnax3.github.io/web-cam-upload/`.
   - Laptop: `.../laptop.html`
   - Handy: einfach den QR auf der Laptop-Seite scannen

## Ablauf

- Das Foto wird verkleinert und bei imgbb hochgeladen (wird nach `EXPIRATION_SECONDS` automatisch gelöscht, Standard 24 h).
- Der QR-Code enthält den Link `foto.html?i=<Bild-URL>`.
- Handy → Laptop läuft direkt per WebRTC (PeerJS), das Foto wandert also nicht über einen Server, bis der Laptop es hochlädt.

## Hinweise

- Kamera funktioniert nur über **https** (GitHub Pages passt) oder `localhost`.
- Der imgbb-Key steht im Quelltext und ist damit öffentlich sichtbar. Für diesen Zweck ist das okay, aber keinen Key mit Bezahlfunktionen nehmen.
- Fotos von Personen: Besucher am Stand kurz darauf hinweisen, dass das Bild bis zum Ablauf online liegt.
- `lib/` enthält `peerjs` und `qrcode-generator` lokal, die Seite braucht kein CDN.
