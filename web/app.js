"use strict";

// All UI logic: rendering, camera, widget, charts, persistence, handlers.
// Backend data comes exclusively through Api.* (see api.js) — no fetch here.

// terrain id -> [barren RGB, lush RGB]; cells blend by vegetation level
const TERRAIN_COLORS = [
  [[24, 52, 84],   [24, 52, 84]],    // sea
  [[214, 197, 142],[214, 197, 142]], // beach
  [[164, 155, 104],[ 98, 141, 70]],  // grassland
  [[148, 143, 94], [112, 126, 66]],  // brush
  [[ 82, 100, 66], [ 42, 86, 48]],   // forest
  [[139, 135, 131],[139, 135, 131]], // rocky highland
  [[104, 117, 94], [ 76, 105, 82]],  // marsh
];
const SEA_COLOR = "rgb(24, 52, 84)";   // matches TERRAIN_COLORS[0]: infinite water
const CARCASS_COLOR = "#8c2f26";
const SELECT_COLOR = "#ffd76a";

let world = null, base = null, offscreen = null, off = null, lastState = null;
const canvas = document.getElementById("map");
const ctx = canvas.getContext("2d");

// camera: world coords of the top-left screen corner, plus pixels-per-cell
const cam = { x: 0, y: 0, scale: 3 };
const toWorldX = sx => cam.x + sx / cam.scale;
const toWorldY = sy => cam.y + sy / cam.scale;

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  rerender();
}
window.addEventListener("resize", resize);

function fitCamera() {
  cam.scale = Math.min(canvas.width / world.w, canvas.height / world.h) * 0.9;
  cam.x = world.w / 2 - canvas.width / (2 * cam.scale);
  cam.y = world.h / 2 - canvas.height / (2 * cam.scale);
}

async function loadWorld(refit) {
  world = await Api.world();
  offscreen = document.createElement("canvas");
  offscreen.width = world.w; offscreen.height = world.h;
  off = offscreen.getContext("2d");
  base = off.createImageData(world.w, world.h);
  if (refit) fitCamera();
}

async function init() {
  resize();
  const saved = loadUI();
  // only fit the camera on a truly first load; a saved camera wins
  await loadWorld(!(saved && saved.cam));
  if (saved) await restoreUI(saved);
  poll();
  setInterval(poll, 100);
}

let polling = false;
async function poll() {
  if (polling || document.hidden) return;
  polling = true;
  try {
    const s = await Api.state();
    render(s);
  } catch (e) { /* server restarting; keep trying */ }
  polling = false;
}

function rerender() { if (lastState) render(lastState); }

function render(s) {
  lastState = s;
  const { w, h, terrain, veg_max } = world;
  const px = base.data;
  const veg = s.veg;
  for (let i = 0; i < w * h; i++) {
    const [dry, lush] = TERRAIN_COLORS[terrain[i]];
    let t = 0;
    if (veg_max[i] > 0) t = Math.min(1, veg[i] / veg_max[i]);
    const j = i * 4;
    px[j]     = dry[0] + (lush[0] - dry[0]) * t;
    px[j + 1] = dry[1] + (lush[1] - dry[1]) * t;
    px[j + 2] = dry[2] + (lush[2] - dry[2]) * t;
    px[j + 3] = 255;
  }
  off.putImageData(base, 0, 0);

  // infinite sea, then the island through the camera transform
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = SEA_COLOR;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(cam.scale, 0, 0, cam.scale, -cam.x * cam.scale, -cam.y * cam.scale);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(offscreen, 0, 0);

  // movement trails: faint per-species polylines, behind everything that moves
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.globalAlpha = 0.25;
  ctx.lineWidth = Math.max(0.15, 1 / cam.scale);
  for (const a of s.animals) {
    const tr = a.trail;
    if (!tr || tr.length < 2) continue;
    ctx.strokeStyle = world.species_colors[a.species] || "#fff";
    ctx.beginPath();
    ctx.moveTo(tr[0][0] + 0.5, tr[0][1] + 0.5);
    for (let i = 1; i < tr.length; i++) ctx.lineTo(tr[i][0] + 0.5, tr[i][1] + 0.5);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  // the selected animal's FULL path (from the entity poll), bright and thick
  if (selectedId !== null && selectedPath && selectedPath.length > 1) {
    ctx.globalAlpha = 0.9;
    ctx.strokeStyle = SELECT_COLOR;
    ctx.lineWidth = Math.max(0.3, 2 / cam.scale);
    ctx.beginPath();
    ctx.moveTo(selectedPath[0][0] + 0.5, selectedPath[0][1] + 0.5);
    for (let i = 1; i < selectedPath.length; i++)
      ctx.lineTo(selectedPath[i][0] + 0.5, selectedPath[i][1] + 0.5);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  // carcasses: dark red crosses (world units: 1 = one cell)
  ctx.fillStyle = CARCASS_COLOR;
  for (const c of s.carcasses) {
    ctx.fillRect(c.x - 0.15, c.y + 0.35, 1.3, 0.3);
    ctx.fillRect(c.x + 0.35, c.y - 0.15, 0.3, 1.3);
  }
  // animals: dots by species (lions drawn bigger)
  let selected = null;
  for (const a of s.animals) {
    if (a.id === selectedId) selected = a;
    const color = world.species_colors[a.species] || "#fff";
    const r = a.species === "lion" ? 1.1 : a.adult ? 0.75 : 0.5;
    ctx.beginPath();
    ctx.arc(a.x + 0.5, a.y + 0.5, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.lineWidth = 1 / cam.scale;
    ctx.strokeStyle = "rgba(0,0,0,.55)";
    ctx.stroke();
  }
  // selection ring on top
  if (selected) {
    const r = selected.species === "lion" ? 1.1 : selected.adult ? 0.75 : 0.5;
    ctx.beginPath();
    ctx.arc(selected.x + 0.5, selected.y + 0.5, r + 0.9, 0, Math.PI * 2);
    ctx.lineWidth = 2 / cam.scale;
    ctx.strokeStyle = SELECT_COLOR;
    ctx.stroke();
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);

  document.getElementById("tick").textContent = "tick " + s.tick;
  const pops = document.getElementById("pops");
  const order = ["gazelle", "lion", "jackal"];
  pops.innerHTML = order.map(sp => {
    const n = s.populations[sp] || 0;
    return `<span class="pop"><span class="dot" style="background:${world.species_colors[sp]}"></span>${sp}: <b>${n}</b></span>`;
  }).join("") +
    `<span class="pop">carcasses: <b>${s.carcasses.length}</b></span>` +
    `<span class="pop">vegetation: <b>${(s.veg.reduce((a, b) => a + b, 0) / 1000).toFixed(0)}k</b></span>`;
  document.getElementById("events").innerHTML =
    s.events.slice().reverse().map(e => e.replace(/</g, "&lt;")).join("<br>");

  const jevEl = document.getElementById("jev");
  const j = s.jev;
  if (!j) {
    jevEl.innerHTML = `<span class="hdr">policy: mock heuristic (Jev off)</span>`;
  } else {
    const m = (val, label) => `<div class="m"><b>${val}</b><span>${label}</span></div>`;
    const cost = j.price_known ? `$${j.est_cost_usd.toFixed(4)}` : `${(j.input_tokens + j.output_tokens).toLocaleString()} tok`;
    jevEl.innerHTML =
      `<span class="hdr">JEV</span>` +
      m(j.requests.toLocaleString(), "requests") +
      m(j.avg_latency_ms + " ms", "avg latency") +
      m(j.req_per_s + "/s", "throughput") +
      m(j.avg_confidence, "avg confidence") +
      m(j.errors, "errors") +
      m(cost, j.price_known ? "est cost" : "tokens");
  }
  drawCharts(s.jev_series || []);
}

// two stacked per-tick bar charts: requests/tick (top) and latency/tick (bottom)
const chartCanvas = document.getElementById("chart");
const cctx = chartCanvas.getContext("2d");
function drawCharts(series) {
  const W = chartCanvas.width, H = chartCanvas.height;
  cctx.clearRect(0, 0, W, H);
  const data = series.slice(-80);
  if (!data.length) return;
  const gap = 2, n = data.length, bw = Math.max(1, (W - (n - 1) * gap) / n);
  const panelH = (H - 16) / 2;

  function panel(y0, key, color, label, unit) {
    const max = Math.max(1, ...data.map(d => d[key] || 0));
    cctx.fillStyle = "#6f8296";
    cctx.font = "10px ui-monospace, monospace";
    cctx.fillText(`${label}: ${data[data.length - 1][key]}${unit} (max ${Math.round(max)})`, 0, y0 + 8);
    const base = y0 + panelH;
    data.forEach((d, i) => {
      const h = Math.round(((d[key] || 0) / max) * (panelH - 12));
      cctx.fillStyle = color;
      cctx.fillRect(i * (bw + gap), base - h, bw, h);
    });
  }
  panel(0, "requests", "#7fd1a6", "requests/tick", "");
  panel(panelH + 16, "latency", "#5b8fc9", "latency", "ms");
}

// ---------------------------------------------------------- pan / zoom / select
const DRAG_THRESHOLD = 4;  // px of movement before a press counts as a pan
let mouseDown = null, panned = false;

canvas.addEventListener("mousedown", e => {
  mouseDown = { sx: e.clientX, sy: e.clientY, camX: cam.x, camY: cam.y };
  panned = false;
});
window.addEventListener("mousemove", e => {
  if (!mouseDown) return;
  const dx = e.clientX - mouseDown.sx, dy = e.clientY - mouseDown.sy;
  if (!panned && Math.hypot(dx, dy) > DRAG_THRESHOLD) {
    panned = true;
    canvas.classList.add("panning");
  }
  if (panned) {
    cam.x = mouseDown.camX - dx / cam.scale;
    cam.y = mouseDown.camY - dy / cam.scale;
    rerender();
  }
});
window.addEventListener("mouseup", e => {
  if (!mouseDown) return;
  const wasPan = panned;
  mouseDown = null; panned = false;
  canvas.classList.remove("panning");
  if (!wasPan && e.target === canvas) selectAt(e.clientX, e.clientY);
  if (wasPan) saveUICam();
});
canvas.addEventListener("wheel", e => {
  e.preventDefault();
  const factor = Math.exp(-e.deltaY * 0.0015);
  const ns = Math.min(80, Math.max(0.4, cam.scale * factor));
  // zoom toward the cursor: keep the world point under it fixed
  const wx = toWorldX(e.clientX), wy = toWorldY(e.clientY);
  cam.scale = ns;
  cam.x = wx - e.clientX / ns;
  cam.y = wy - e.clientY / ns;
  rerender();
  saveUICam();
}, { passive: false });

function selectAt(sx, sy) {
  if (!lastState) return;
  const wx = toWorldX(sx), wy = toWorldY(sy);
  let best = null, bestD = Infinity;
  for (const a of lastState.animals) {
    const d = Math.hypot(a.x + 0.5 - wx, a.y + 0.5 - wy);
    if (d < bestD) { best = a; bestD = d; }
  }
  const pickRadius = Math.max(1.6, 10 / cam.scale);  // ~10 px, generous when zoomed out
  if (best && bestD <= pickRadius) {
    openWidget(best, sx, sy);
  } else {
    closeWidget();
  }
  rerender();
}

// ---------------------------------------------------------- entity widget
const widget = document.getElementById("widget");
const wtitle = document.getElementById("wtitle");
const wstate = document.getElementById("wstate");
const waction = document.getElementById("waction");
const wbars = document.getElementById("wbars");
const wdead = document.getElementById("wdead");
let selectedId = null, entityTimer = null, entityBusy = false;
let selectedPath = null;  // full trail of the inspected animal, from the entity poll

function openWidget(animal, sx, sy) {
  selectedId = animal.id;
  selectedPath = null;
  wtitle.textContent = `${animal.species} #${animal.id}`;
  wdead.style.display = "none";
  // seed instantly from what we already know so the widget is never blank on click
  wstate.textContent = "loading…";
  waction.innerHTML = `action: <b>${animal.action}</b>`;
  wbars.innerHTML = "";
  widget.style.display = "block";
  // place near the click, clamped on-screen (keep position if already open)
  if (!widget.dataset.placed) {
    const x = Math.min(Math.max(8, sx + 18), window.innerWidth - 320);
    const y = Math.min(Math.max(8, sy - 10), window.innerHeight - 260);
    widget.style.left = x + "px";
    widget.style.top = y + "px";
    widget.dataset.placed = "1";
  }
  if (entityTimer) clearInterval(entityTimer);
  pollEntity();
  entityTimer = setInterval(pollEntity, 120);
  saveUI();
}

function closeWidget() {
  selectedId = null;
  selectedPath = null;
  widget.style.display = "none";
  if (entityTimer) { clearInterval(entityTimer); entityTimer = null; }
  saveUI();
}
document.getElementById("wclose").onclick = closeWidget;

async function pollEntity() {
  if (selectedId === null || entityBusy || document.hidden) return;
  entityBusy = true;
  try {
    const ent = await Api.entity(selectedId);
    if (ent.id === selectedId) {
      if (ent.alive && ent.path) selectedPath = ent.path;
      updateWidget(ent);
    }
  } catch (e) { /* transient; keep polling */ }
  entityBusy = false;
}

function updateWidget(ent) {
  if (!ent.alive) {
    wdead.style.display = "block";
    waction.innerHTML = "";
    wbars.innerHTML = "";
    if (entityTimer) { clearInterval(entityTimer); entityTimer = null; }
    return;
  }
  wtitle.textContent = `${ent.species} #${ent.id}`;
  wstate.textContent = ent.state_text || "(no perception yet — step the sim)";
  const conf = ent.confidence != null ? ` &middot; confidence ${(ent.confidence * 100).toFixed(0)}%` : "";
  waction.innerHTML = `action: <b>${ent.action}</b>${conf}`;

  let probs = ent.probabilities;
  if (!probs || typeof probs !== "object") {
    probs = {};
    if (ent.choice) probs[ent.choice] = ent.confidence != null ? ent.confidence : 1;
  }
  const rows = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  wbars.innerHTML = rows.map(([name, p]) => {
    const pct = Math.max(0, Math.min(100, p * 100));
    const chosen = name === ent.choice ? " chosen" : "";
    return `<div class="brow${chosen}"><span class="bl">${name}</span>` +
      `<span class="bt"><span class="bf" style="width:${pct.toFixed(1)}%"></span></span>` +
      `<span class="bv">${pct.toFixed(0)}%</span></div>`;
  }).join("");

  const hist = ent.history || [];
  const label = document.getElementById("whistlabel");
  const box = document.getElementById("whist");
  if (!hist.length) {
    label.style.display = "none"; box.innerHTML = "";
  } else {
    label.style.display = "block";
    // newest first, mark ticks where the action changed from the previous one
    const rows = hist.slice(-60).reverse();
    box.innerHTML = rows.map((r, i) => {
      const prev = rows[i + 1];
      const chg = prev && prev.action !== r.action ? " chg" : "";
      const c = r.confidence != null ? (r.confidence * 100).toFixed(0) + "%" : "";
      return `<div class="h${chg}"><span class="t">t${r.tick}</span>` +
        `<span class="a">${r.action}</span><span class="c">${c}</span></div>`;
    }).join("");
  }
}

// drag the widget by its header
let wdrag = null;
document.getElementById("whead").addEventListener("mousedown", e => {
  if (e.target.id === "wclose") return;
  wdrag = { sx: e.clientX, sy: e.clientY,
            left: widget.offsetLeft, top: widget.offsetTop };
  e.preventDefault();
});
window.addEventListener("mousemove", e => {
  if (!wdrag) return;
  widget.style.left = Math.max(0, wdrag.left + e.clientX - wdrag.sx) + "px";
  widget.style.top = Math.max(0, wdrag.top + e.clientY - wdrag.sy) + "px";
});
window.addEventListener("mouseup", () => {
  if (wdrag) { wdrag = null; saveUI(); }  // widget drag end
});

// ---------------------------------------------------------- UI persistence
// One JSON blob in localStorage; restored on load, so a refresh keeps the
// whole UI. Only "new run" resets SIM state -- and even that keeps the prefs.
const UI_KEY = "vesta-ecosim-ui";
let uiAuto = false, uiPlaying = false;

function saveUI() {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify({
      seed: document.getElementById("seed").value,
      sample: document.getElementById("sample").checked,
      auto: uiAuto,
      ticks: document.getElementById("speed").value,
      playing: uiPlaying,
      cam: { x: cam.x, y: cam.y, scale: cam.scale },
      selectedId,
      widgetOpen: selectedId !== null && widget.style.display === "block",
      // style.left survives display:none (offsetLeft would read 0)
      widgetPos: { left: parseFloat(widget.style.left) || 0,
                   top: parseFloat(widget.style.top) || 0 },
    }));
  } catch (e) { /* storage unavailable; UI still works, just not persisted */ }
}
let camSaveTimer = null;
function saveUICam() {           // debounced: wheel/pan fire in bursts
  clearTimeout(camSaveTimer);
  camSaveTimer = setTimeout(saveUI, 250);
}
function loadUI() {
  try { return JSON.parse(localStorage.getItem(UI_KEY) || "null"); }
  catch (e) { return null; }
}

async function restoreUI(saved) {
  if (saved.seed != null) document.getElementById("seed").value = saved.seed;
  if (saved.ticks != null) document.getElementById("speed").value = saved.ticks;
  {
    // sample defaults ON; a saved value overrides it
    const on = saved.sample != null ? !!saved.sample : true;
    document.getElementById("sample").checked = on;
    await control("sample", on ? 1 : 0);  // keep the server in step
  }
  if (saved.cam && saved.cam.scale > 0) Object.assign(cam, saved.cam);

  uiAuto = !!saved.auto;
  uiPlaying = !!saved.playing;
  if (uiPlaying && uiAuto) {       // it was explicitly running in auto: resume
    document.getElementById("speedval").textContent = "auto";
    await control("auto", 1);
  } else {
    uiAuto = false;                // never surprise-start an auto loop on load
    document.getElementById("speedval").textContent =
      document.getElementById("speed").value + " t/s";
    await control("speed", document.getElementById("speed").value);
    if (uiPlaying) await control("play");
  }

  if (saved.widgetPos && (saved.widgetPos.left || saved.widgetPos.top)) {
    widget.style.left = Math.min(Math.max(0, saved.widgetPos.left), window.innerWidth - 120) + "px";
    widget.style.top = Math.min(Math.max(0, saved.widgetPos.top), window.innerHeight - 80) + "px";
    widget.dataset.placed = "1";
  }
  if (saved.widgetOpen && saved.selectedId != null) {
    try {  // reopen only if that animal still exists; otherwise just clear it
      const ent = await Api.entity(saved.selectedId);
      if (ent.alive) {
        selectedId = ent.id;
        selectedPath = ent.path || null;
        wtitle.textContent = `${ent.species} #${ent.id}`;
        wdead.style.display = "none";
        widget.style.display = "block";
        updateWidget(ent);
        if (entityTimer) clearInterval(entityTimer);
        entityTimer = setInterval(pollEntity, 120);
      }
    } catch (e) { /* server hiccup; skip the widget restore */ }
  }
  saveUI();
}

// ---------------------------------------------------------- controls
async function control(cmd, value) {
  await Api.control(cmd, value);
}
document.getElementById("play").onclick = () => {
  uiPlaying = true;
  control("play");
  saveUI();
};
document.getElementById("pause").onclick = () => {
  uiPlaying = false;
  control("pause");
  saveUI();
};
document.getElementById("step").onclick = () => {
  uiPlaying = false;
  control("step");
  saveUI();
};
document.getElementById("auto").onclick = () => {
  uiAuto = true; uiPlaying = true;
  document.getElementById("speedval").textContent = "auto";
  control("auto", 1);
  saveUI();
};
document.getElementById("speed").oninput = (e) => {
  uiAuto = false;  // picking a numeric speed leaves auto mode (matches the server)
  document.getElementById("speedval").textContent = e.target.value + " t/s";
  control("speed", e.target.value);
  saveUI();
};
document.getElementById("seed").onchange = saveUI;
document.getElementById("newrun").onclick = async () => {
  const s = document.getElementById("seed").value || "7";
  await control("reset", s);        // the ONLY thing that resets sim state
  uiPlaying = false;                // reset leaves the server paused
  await loadWorld(false);           // new island, but the saved camera stays
  closeWidget();                    // old ids are gone; clears + saves
  poll();
};
document.getElementById("sample").onchange = (e) => {
  control("sample", e.target.checked ? 1 : 0);
  saveUI();
};

init();
