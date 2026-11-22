// ============================================================
//  EINSTELLUNGEN – hier einmal anpassen
// ============================================================
window.CONFIG = {
  // Adresse der GitHub-Pages-Seite (mit / am Ende). Dorthin führt der QR-Code zum Abholen.
  PAGES_URL: "https://schnax3.github.io/web-cam-upload/",

  // Adresse des Foto-Servers. Leer lassen = derselbe Server, von dem die Seite kommt
  // (Normalfall: Laptop-Seite läuft auf http://localhost:8765/).
  LOCAL_SERVER: "",

  // Größte Kantenlänge des Fotos in Pixeln. Hoch genug wählen, denn die Hochkant-Version
  // ist ein Ausschnitt aus der Mitte (bei 2560 px: 9:16 = ca. 810 x 1440 px, 3:4 = ca. 1080 x 1440 px).
  MAX_SIZE: 2560,

  // Countdown vor dem Foto in Sekunden (0 = sofort auslösen)
  COUNTDOWN: 3,

  // Wie das Livebild in der linken Hälfte des Laptop-Bildschirms eingepasst wird:
  // "cover"   = füllt die Hälfte, Ränder werden abgeschnitten (ähnelt dem Hochkant-Ausschnitt)
  // "contain" = zeigt das ganze Bild genau wie im Foto, mit schwarzen Balken
  VIEW_FIT: "cover",

  // Titel (Browser-Tab)
  TITLE: "Foto-Aktion"
};
