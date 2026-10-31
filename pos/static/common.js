// Shared helpers for every page.
const POS = {};

POS.esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

POS.money = (cents) => {
  const neg = cents < 0;
  const s = (Math.abs(cents) / 100).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (neg ? "-$" : "$") + s;
};

// "12.5" / "$12.50" -> 1250. Returns null when not a valid amount.
POS.parseMoney = (str) => {
  const s = String(str ?? "").replace(/[$,\s]/g, "");
  if (!/^\d+(\.\d{0,2})?$/.test(s)) return null;
  return Math.round(parseFloat(s) * 100);
};

POS.today = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

POS.fmtDate = (s) => {
  if (!s) return "";
  const [d, t] = s.split(" ");
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}` + (t ? " " + t.slice(0, 5) : "");
};

POS.api = async (method, path, body) => {
  const opts = { method, headers: { "X-Requested-With": "pos" }, credentials: "same-origin" };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    throw new Error("Can't reach the POS server - check Wi-Fi");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !path.startsWith("/api/login")) {
    location.href = "/login.html?next=" + encodeURIComponent(location.pathname + location.search);
    return new Promise(() => {}); // page is navigating away

  }
  if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
  return data;
};

POS.toast = (msg, kind = "") => {
  let box = document.getElementById("toasts");
  if (!box) {
    box = document.createElement("div");
    box.id = "toasts";
    document.body.appendChild(box);
  }
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), kind === "bad" ? 5000 : 2500);
};

let audioCtx;
POS.beep = (ok = true) => {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.frequency.value = ok ? 1400 : 300;
    g.gain.value = 0.15;
    o.connect(g).connect(audioCtx.destination);
    o.start();
    o.stop(audioCtx.currentTime + (ok ? 0.08 : 0.3));
  } catch (e) { /* no audio */ }
  if (navigator.vibrate) navigator.vibrate(ok ? 40 : [80, 60, 80]);
};

// What goes inside a tag's QR code: SKU|VENDOR|PRICE. With a tag web address set
// it becomes a link, so a phone's own camera app opens the stocktake screen.
POS.tagPayload = (p) => {
  const code = `${p.sku}|${p.vendor_code || ""}|${(p.price_cents / 100).toFixed(2)}`;
  const base = POS.settings?.tag_base_url;
  return base ? `${base}/t?c=${encodeURIComponent(code).replace(/%7C/g, "|")}` : code;
};

POS.qrSvg = (text, cellSize = 4) => {
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return qr.createSvgTag({ cellSize, margin: 2 * cellSize, scalable: true });
};

POS.modal = (html) => {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="modal">${html}</div>`;
  document.body.appendChild(bg);
  bg.addEventListener("click", (e) => { if (e.target === bg) bg.remove(); });
  return { el: bg.firstElementChild, close: () => bg.remove() };
};

const NAV = [
  ["register.html", "Register", "any"],
  ["scan.html", "Scan stock", "any"],
  ["products.html", "Products", "any"],
  ["tags.html", "Tags", "owner"],
  ["reports.html", "Reports", "any"],
  ["settings.html", "Settings", "owner"],
];

// Load the logged-in user and draw the top bar. Redirects to login if needed.
POS.init = async () => {
  const data = await POS.api("GET", "/api/me");
  POS.me = data.user;
  POS.settings = data.settings;
  const here = location.pathname.split("/").pop() || "register.html";
  const links = NAV.filter(([, , role]) => role === "any" || POS.me.role === "owner")
    .map(([href, label]) => `<a class="nav ${href === here ? "active" : ""}" href="${href}">${label}</a>`)
    .join("");
  const bar = document.createElement("nav");
  bar.className = "topbar no-print";
  bar.innerHTML = `<span class="brand">${POS.esc(POS.settings.shop_name)}</span>${links}
    <span class="spacer"></span><span class="who">${POS.esc(POS.me.name)}</span>
    <button class="small" id="logout">Log out</button>`;
  document.body.prepend(bar);
  bar.querySelector("#logout").onclick = async () => {
    await POS.api("POST", "/api/logout").catch(() => {});
    location.href = "/login.html";
  };
  return POS.me;
};
