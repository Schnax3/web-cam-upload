// Gemeinsame Funktionen für die Laptop-Seite (laptop.html)
(function () {
  const CFG = window.CONFIG;
  let currentStream = null;

  // Adresse des Foto-Servers (leer = gleicher Server wie die Seite)
  function server() {
    return CFG.LOCAL_SERVER || location.origin;
  }

  async function startCamera(video, facing) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Kamera nicht verfügbar. Die Seite bitte über http://localhost:8765/ öffnen.");
    }
    stopCamera();
    const constraints = {
      video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false,
    };
    currentStream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = currentStream;
    await video.play();
  }

  function stopCamera() {
    if (currentStream) currentStream.getTracks().forEach((t) => t.stop());
    currentStream = null;
  }

  // Standbild aus dem Video holen (nicht gespiegelt), auf MAX_SIZE verkleinert
  function snapshot(video) {
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) throw new Error("Kamerabild noch nicht bereit.");
    const scale = Math.min(1, CFG.MAX_SIZE / Math.max(w, h));
    const c = document.createElement("canvas");
    c.width = Math.round(w * scale);
    c.height = Math.round(h * scale);
    c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
    return new Promise((resolve, reject) =>
      c.toBlob((b) => (b ? resolve(b) : reject(new Error("Foto konnte nicht erstellt werden."))), "image/jpeg", 0.88)
    );
  }

  // Countdown anzeigen (Element bekommt Zahlen), danach resolve
  async function countdown(el, seconds) {
    for (let i = seconds; i > 0; i--) {
      el.textContent = i;
      el.classList.remove("pop");
      void el.offsetWidth; // Animation neu starten
      el.classList.add("pop");
      await new Promise((r) => setTimeout(r, 1000));
    }
    el.textContent = "";
  }

  // Blitz-Effekt
  function flash(el) {
    el.classList.remove("go");
    void el.offsetWidth;
    el.classList.add("go");
  }

  // ---------- Foto-Server ----------
  async function getJson(path) {
    const r = await fetch(server() + path, { cache: "no-store" });
    if (!r.ok) throw new Error("Server antwortet nicht richtig (" + r.status + ").");
    return r.json();
  }
  const serverInfo = () => getJson("/info");   // { public_url, ttl, lan_url, tls }
  const serverStatus = () => getJson("/status"); // { phone, seq, token, latest, tunnel }

  // Befehl an das Handy ("shoot" = auslösen)
  async function sendCmd(cmd) {
    const r = await fetch(server() + "/cmd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd: cmd }),
    });
    if (r.status === 409) throw new Error("Kein Handy verbunden.");
    if (!r.ok) throw new Error("Befehl fehlgeschlagen (" + r.status + ").");
  }

  // Foto der Laptop-Kamera auf dem Server speichern. Gibt den Token zurück.
  async function saveBlob(blob) {
    let res;
    try {
      res = await fetch(server() + "/upload", {
        method: "POST",
        headers: { "Content-Type": "image/jpeg" },
        body: blob,
      });
    } catch (e) {
      throw new Error("Foto konnte nicht gespeichert werden. Läuft foto_server.py?");
    }
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.token) throw new Error("Speichern fehlgeschlagen: " + (json.error || res.status));
    return json.token;
  }

  // Link im QR-Code: GitHub-Pages-Seite, Abhol-Adresse und Token stehen hinter dem #
  // (der Teil nach # wird nie an einen Server geschickt)
  function viewerLink(publicUrl, token) {
    return CFG.PAGES_URL + "foto.html#s=" + encodeURIComponent(publicUrl) + "&t=" + encodeURIComponent(token);
  }

  // QR-Code als SVG in ein Element zeichnen
  function renderQR(el, text) {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    const n = qr.getModuleCount();
    const m = 2; // ruhige Zone
    let d = "";
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (qr.isDark(r, c)) d += "M" + (c + m) + " " + (r + m) + "h1v1h-1z";
      }
    }
    const s = n + 2 * m;
    el.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + s + " " + s +
      '" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="' +
      d + '" fill="#000"/></svg>';
  }

  window.WCU = { server, startCamera, stopCamera, snapshot, countdown, flash, serverInfo, serverStatus, sendCmd, saveBlob, viewerLink, renderQR };
})();
