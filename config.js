// ============================================================
//  EINSTELLUNGEN – hier einmal anpassen
// ============================================================
window.CONFIG = {
  // Kostenloser API-Key von https://api.imgbb.com/  (Account anlegen -> "Get API key")
  IMGBB_KEY: "HIER_IMGBB_KEY_EINTRAGEN",

  // Wie lange das Bild online bleibt, dann löscht imgbb es automatisch.
  // Erlaubt: 60 bis 15552000 Sekunden.  86400 = 24 Stunden, 3600 = 1 Stunde
  EXPIRATION_SECONDS: 86400,

  // Größte Kantenlänge des Fotos in Pixeln (kleiner = schnellerer Upload)
  MAX_SIZE: 1600,

  // Countdown vor dem Foto in Sekunden (0 = sofort auslösen)
  COUNTDOWN: 3,

  // Titel auf den Seiten
  TITLE: "Foto-Aktion"
};
