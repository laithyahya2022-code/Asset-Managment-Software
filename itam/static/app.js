"use strict";

// Confirm dialogs
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-confirm]");
  if (btn && !window.confirm(btn.dataset.confirm)) {
    e.preventDefault();
    e.stopPropagation();
  }
});

// Select-all checkbox for bulk tables
document.querySelectorAll("[data-check-all]").forEach((master) => {
  master.addEventListener("change", () => {
    master.closest("table").querySelectorAll('input[type="checkbox"][name="id"]')
      .forEach((cb) => { cb.checked = master.checked; });
  });
});

// Close mobile sidebar when a nav link is chosen
document.querySelectorAll(".sidebar nav a").forEach((a) => {
  a.addEventListener("click", () => {
    const toggle = document.getElementById("nav-toggle");
    if (toggle) toggle.checked = false;
  });
});

// QR / barcode camera scanner (native BarcodeDetector)
const startBtn = document.getElementById("scan-start");
if (startBtn) {
  const video = document.getElementById("scan-video");
  const status = document.getElementById("scan-status");
  startBtn.addEventListener("click", async () => {
    if (!("BarcodeDetector" in window)) {
      status.textContent = "This browser has no built-in barcode detector — use manual entry.";
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      video.srcObject = stream;
      video.hidden = false;
      startBtn.hidden = true;
      status.textContent = "Scanning…";
      const detector = new BarcodeDetector({
        formats: ["qr_code", "code_128", "ean_13", "code_39"],
      });
      const tick = async () => {
        if (!video.srcObject) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) {
            const raw = codes[0].rawValue;
            const code = raw.includes("code=") ? raw.split("code=").pop() : raw;
            stream.getTracks().forEach((t) => t.stop());
            window.location.href = "/scan-go?code=" + encodeURIComponent(code);
            return;
          }
        } catch (err) { /* keep scanning */ }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    } catch (err) {
      status.textContent = "Camera unavailable (" + err.name + ") — use manual entry.";
    }
  });
}

// PWA service worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
