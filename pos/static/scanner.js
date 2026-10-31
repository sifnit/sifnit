// Camera QR scanning (phones, webcams) and USB/Bluetooth "keyboard" scanners.

class CameraScanner {
  // onCode(text) fires once per item: the same code won't fire again until it
  // has been out of view for `holdMs` - so an item resting on the bench reads once.
  constructor(container, onCode, { holdMs = 1500 } = {}) {
    this.container = container;
    this.onCode = onCode;
    this.holdMs = holdMs;
    this.running = false;
    this.last = null;
    this.lastSeen = 0;
    container.classList.add("cam");
    container.innerHTML = '<video playsinline muted></video><div class="frame"></div><div class="flash"></div>';
    this.video = container.querySelector("video");
    this.flash = container.querySelector(".flash");
    this.canvas = document.createElement("canvas");
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });
  }

  async start() {
    if (this.running) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Camera not available. The page must be opened over https://");
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    this.video.srcObject = this.stream;
    await this.video.play();
    if ("BarcodeDetector" in window) {
      try {
        const formats = await BarcodeDetector.getSupportedFormats();
        if (formats.includes("qr_code")) this.detector = new BarcodeDetector({ formats: ["qr_code"] });
      } catch (e) { /* fall back to jsQR */ }
    }
    this.running = true;
    this.loop();
  }

  stop() {
    this.running = false;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }

  async detect() {
    const v = this.video;
    if (v.readyState < 2) return null;
    if (this.detector) {
      const codes = await this.detector.detect(v);
      return codes[0]?.rawValue ?? null;
    }
    const scale = Math.min(1, 640 / v.videoWidth);
    const w = Math.round(v.videoWidth * scale);
    const h = Math.round(v.videoHeight * scale);
    this.canvas.width = w;
    this.canvas.height = h;
    this.ctx.drawImage(v, 0, 0, w, h);
    const img = this.ctx.getImageData(0, 0, w, h);
    return jsQR(img.data, w, h, { inversionAttempts: "dontInvert" })?.data ?? null;
  }

  async loop() {
    while (this.running) {
      let code = null;
      try { code = await this.detect(); } catch (e) { /* skip frame */ }
      const now = Date.now();
      if (code) {
        if (code !== this.last || now - this.lastSeen > this.holdMs) {
          this.flash.classList.add("on");
          setTimeout(() => this.flash.classList.remove("on"), 150);
          this.onCode(code);
        }
        this.last = code;
        this.lastSeen = now;
      }
      await new Promise((r) => setTimeout(r, 120));
    }
  }
}

// Hardware scanners type the code quickly and press Enter. Catch that anywhere
// on the page unless the user is typing in a normal text field.
function attachKeyboardScanner(onCode, { field = null } = {}) {
  let buf = "";
  let lastKey = 0;
  document.addEventListener("keydown", (e) => {
    const now = Date.now();
    const target = e.target;
    const inOtherField = target !== field && target.matches?.("input, textarea, select");
    if (inOtherField) return;
    if (now - lastKey > 80) buf = "";
    lastKey = now;
    if (e.key === "Enter") {
      if (buf.length >= 3 && target !== field) {
        e.preventDefault();
        onCode(buf);
      }
      buf = "";
    } else if (e.key.length === 1) {
      buf += e.key;
    }
  });
}
