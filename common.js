// Gemeinsame Funktionen für laptop.html, handy.html und foto.html
(function () {
  const CFG = window.CONFIG;
  let currentStream = null;

  // Ordner-URL, in dem die Seiten liegen (funktioniert auf GitHub Pages und lokal)
  function baseUrl() {
    return location.origin + location.pathname.replace(/[^/]*$/, "");
  }

  async function startCamera(video, facing) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Kamera nicht verfügbar. Die Seite muss über https geöffnet werden.");
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
      c.toBlob((b) => (b ? resolve(b) : reject(new Error("Foto konnte nicht erstellt werden."))), "image/jpeg", 0.85)
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

  // Foto bei imgbb hochladen, gibt die direkte Bild-URL zurück
  async function uploadBlob(blob) {
    const key = CFG.IMGBB_KEY;
    if (!key || key.indexOf("HIER_") === 0) {
      throw new Error("Kein imgbb-API-Key in config.js eingetragen.");
    }
    const fd = new FormData();
    fd.append("image", blob, "foto.jpg");
    const url =
      "https://api.imgbb.com/1/upload?expiration=" +
      encodeURIComponent(CFG.EXPIRATION_SECONDS) +
      "&key=" + encodeURIComponent(key);
    const res = await fetch(url, { method: "POST", body: fd });
    let json;
    try { json = await res.json(); } catch (e) { throw new Error("Upload fehlgeschlagen (keine Antwort)."); }
    if (!json.success) {
      throw new Error((json.error && json.error.message) || "Upload fehlgeschlagen.");
    }
    return json.data.url;
  }

  // Link, den der QR-Code enthält: unsere Foto-Seite mit der Bild-URL
  function viewerLink(imageUrl) {
    return baseUrl() + "foto.html?i=" + encodeURIComponent(imageUrl);
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

  window.WCU = { baseUrl, startCamera, stopCamera, snapshot, countdown, flash, uploadBlob, viewerLink, renderQR };
})();
