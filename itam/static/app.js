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

// ---------------------------------------------------------------- bulk select
// Wires the select-all checkbox, the row ticks and the bulk action button on
// every list page that uses the bulk_form/select_all_th/row_check macros.
document.querySelectorAll("form.bulk-form").forEach((form) => {
  // getAttribute, not form.id: a form exposes its named controls as
  // properties, so a checkbox called "id" -- which the asset list uses --
  // shadows the form's own id and every selector built from it silently
  // matches nothing.
  const formId = form.getAttribute("id");
  const all = form.querySelector(".bulk-all");
  const picks = [...form.querySelectorAll(".bulk-pick")];
  // The action button sits in the page head and points back with form=,
  // so look outside the form as well as inside it.
  const buttons = [...new Set([
    ...form.querySelectorAll(".bulk-go"),
    ...(formId ? document.querySelectorAll(`.bulk-go[form="${formId}"]`) : []),
  ])];
  if (!picks.length || !buttons.length) return;

  // A visible "Select all" button, for anyone who never spots the tick-box in
  // the table header. Both it and the header box drive the same selection.
  const toggles = formId
    ? [...document.querySelectorAll(`.bulk-toggle[data-form="${formId}"]`)] : [];
  const syncToggle = () => {
    const chosen = picks.filter((p) => p.checked).length;
    toggles.forEach((t) => {
      t.textContent = chosen === picks.length ? t.dataset.off : t.dataset.on;
    });
  };

  const sync = () => {
    const chosen = picks.filter((p) => p.checked).length;
    buttons.forEach((b) => {
      b.disabled = chosen === 0;
      b.textContent = chosen ? `${b.dataset.label} (${chosen})` : b.dataset.label;
    });
    if (all) {
      all.checked = chosen === picks.length;
      // Partial selection reads as neither on nor off.
      all.indeterminate = chosen > 0 && chosen < picks.length;
    }
    syncToggle();
  };

  toggles.forEach((t) => t.addEventListener("click", () => {
    const everything = picks.every((p) => p.checked);
    picks.forEach((p) => { p.checked = !everything; });
    sync();
  }));

  if (all) {
    all.addEventListener("change", () => {
      picks.forEach((p) => { p.checked = all.checked; });
      sync();
    });
  }
  picks.forEach((p) => p.addEventListener("change", sync));

  form.addEventListener("submit", (e) => {
    const chosen = picks.filter((p) => p.checked).length;
    if (!chosen) { e.preventDefault(); return; }
    const verb = e.submitter && e.submitter.dataset.label
      ? e.submitter.dataset.label.toLowerCase() : "apply to";
    if (!window.confirm(`${chosen} selected — ${verb}?`)) e.preventDefault();
  });

  sync();
});

// ---------------------------------------------------------------- dropdowns
// A native <select> popup is drawn by the operating system: the browser
// decides whether it opens up or down from the space available, and neither
// CSS nor script can override that. On a long list near the middle of a form
// it flips upward and covers the page. This replaces the popup -- and only the
// popup -- with our own list that always opens downward and is styled like the
// rest of the app.
//
// The real <select> stays in the DOM, so form submission, existing script that
// reads .value or .options, and the no-JavaScript case all behave exactly as
// before. Anything with size= or multiple is left alone: those are list boxes,
// not popups.
(() => {
  const isPopup = (s) => !s.multiple && (!s.size || s.size <= 1)
    && !s.closest("[data-native-select]");

  const build = (select) => {
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = "1";

    const wrap = document.createElement("div");
    wrap.className = "sel";
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "sel-btn";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    if (select.id) button.id = `${select.id}-btn`;

    const list = document.createElement("div");
    list.className = "sel-list";
    list.setAttribute("role", "listbox");
    list.hidden = true;

    wrap.append(button, list);

    const label = () => {
      const opt = select.options[select.selectedIndex];
      button.textContent = opt ? opt.textContent.trim() || "—" : "—";
      button.classList.toggle("placeholder", !!opt && !opt.value);
    };

    const render = () => {
      list.textContent = "";
      [...select.options].forEach((opt, i) => {
        const row = document.createElement("div");
        row.className = "sel-opt";
        row.textContent = opt.textContent.trim() || "—";
        row.setAttribute("role", "option");
        row.dataset.index = String(i);
        if (opt.disabled) row.classList.add("is-disabled");
        if (i === select.selectedIndex) row.classList.add("is-on");
        list.appendChild(row);
      });
      label();
    };

    const close = () => {
      list.hidden = true;
      button.setAttribute("aria-expanded", "false");
    };

    const open = () => {
      document.querySelectorAll(".sel-list:not([hidden])").forEach((l) => {
        if (l !== list) l.hidden = true;
      });
      render();
      list.hidden = false;
      button.setAttribute("aria-expanded", "true");
      const on = list.querySelector(".is-on");
      if (on) on.scrollIntoView({ block: "nearest" });
      // Opening downward can run past the fold; bring it into view rather
      // than flipping the list upward.
      const room = window.innerHeight - list.getBoundingClientRect().bottom;
      if (room < 0) wrap.scrollIntoView({ block: "center", behavior: "smooth" });
    };

    const choose = (i) => {
      const opt = select.options[i];
      if (!opt || opt.disabled) return;
      select.selectedIndex = i;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      label();
      close();
      button.focus();
    };

    button.addEventListener("click", () => (list.hidden ? open() : close()));
    list.addEventListener("click", (e) => {
      const row = e.target.closest(".sel-opt");
      if (row) choose(Number(row.dataset.index));
    });

    button.addEventListener("keydown", (e) => {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        if (list.hidden) { open(); return; }
      }
      if (e.key === "Escape") close();
    });
    list.addEventListener("keydown", (e) => { if (e.key === "Escape") { close(); button.focus(); } });

    document.addEventListener("click", (e) => {
      if (!wrap.contains(e.target)) close();
    });

    // Lists that are refilled from the server (the lending picker, the bulk
    // transfer box) must redraw rather than show a stale set.
    new MutationObserver(() => { if (!list.hidden) render(); else label(); })
      .observe(select, { childList: true });
    select.addEventListener("change", label);

    render();
  };

  const scan = () => document.querySelectorAll("select").forEach((s) => {
    if (isPopup(s)) build(s);
  });
  scan();
  // Forms revealed later (the location editor) get picked up too.
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
})();
