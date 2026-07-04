// ─────────────────────────────────────────────────────────────
// PhotoSort — App Logic (v3, monochrome)
// ─────────────────────────────────────────────────────────────

const API = "http://localhost:5050";

let selectedFolder = "";
let allResults    = [];
let currentTab    = "all";

// ── Screens ───────────────────────────────────────────────────

function show(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  window.scrollTo(0, 0);
}

function goBack() {
  allResults = [];
  currentTab = "all";
  selectedFolder = "";
  document.getElementById("selectedFolder").classList.add("hidden");
  document.getElementById("startBtn").classList.add("hidden");
  document.getElementById("folderPath").value = "";
  closeModal();
  show("screen-pick");
}

// ── Server status ─────────────────────────────────────────────

async function ping() {
  const pill = document.getElementById("serverPill");
  const txt  = pill.querySelector(".status-txt");
  try {
    const r = await fetch(`${API}/status`, { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    if (d.ok) {
      pill.className = "status-dot-wrap ok";
      txt.textContent = "Ready";
    }
  } catch {
    pill.className = "status-dot-wrap err";
    txt.textContent = "Offline";
  }
}

// ── Folder picker ─────────────────────────────────────────────

async function pickFolder() {
  const btn = document.getElementById("pickBtn");
  btn.textContent = "Opening…";
  btn.disabled = true;

  try {
    const r = await fetch(`${API}/pick-folder`, { signal: AbortSignal.timeout(90000) });
    const d = await r.json();
    if (d.path) {
      applyFolder(d.path);
    } else if (d.error) {
      showToast(d.error, "err");
    }
    // if cancelled, just restore
  } catch (e) {
    showToast("Could not open folder picker", "err");
  }

  btn.innerHTML = `<svg class="folder-icon" width="20" height="20" viewBox="0 0 20 20" fill="none">
    <path d="M2 6a2 2 0 012-2h3.586a1 1 0 01.707.293L9.707 5.707A1 1 0 0010.414 6H16a2 2 0 012 2v7a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
  </svg> Choose folder…`;
  btn.disabled = false;
}

function useManualPath() {
  const val = document.getElementById("folderPath").value.trim();
  if (!val) { showToast("Enter a folder path first", "err"); return; }
  applyFolder(val);
}

function applyFolder(path) {
  selectedFolder = path;
  document.getElementById("selectedPath").textContent = path;
  document.getElementById("selectedFolder").classList.remove("hidden");
  document.getElementById("startBtn").classList.remove("hidden");
}

function goClassify() {
  if (!selectedFolder) { showToast("Pick a folder first", "err"); return; }
  show("screen-progress");
  classify();
}

// ── Classification ────────────────────────────────────────────

function getThreshold() {
  return parseInt(document.getElementById("threshSlider").value) / 100;
}

function effectiveLabel(entry) {
  if (!entry.label || entry.label === "unknown") return "uncertain";
  if (entry.confidence < getThreshold()) return "uncertain";
  return entry.label;
}

async function classify() {
  allResults = [];
  resetProg();
  let portraits = 0, landscapes = 0, uncertain = 0;

  try {
    const res = await fetch(`${API}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder: selectedFolder }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || "Classification failed", "err");
      show("screen-pick");
      return;
    }

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        const ev = JSON.parse(raw);

        if (ev.type === "start") {
          document.getElementById("progFraction").textContent = `0 of ${ev.total}`;

        } else if (ev.type === "progress") {
          allResults.push(ev.entry);
          const lbl = effectiveLabel(ev.entry);
          if (lbl === "portrait") portraits++;
          else if (lbl === "landscape") landscapes++;
          else uncertain++;

          const pct = Math.round((ev.index / ev.total) * 100);
          updateProg(pct, ev.index, ev.total, portraits, landscapes, uncertain, ev.entry.filename);

        } else if (ev.type === "done") {
          await new Promise(r => setTimeout(r, 300));
          buildResults();
          show("screen-results");

        } else if (ev.type === "error") {
          showToast(ev.message, "err");
          show("screen-pick");
          return;
        }
      }
    }
  } catch (e) {
    showToast("Error: " + e.message, "err");
    show("screen-pick");
  }
}

function resetProg() {
  updateProg(0, 0, 1, 0, 0, 0, "");
}

function updateProg(pct, idx, total, portraits, landscapes, uncertain, filename) {
  document.getElementById("progPct").textContent = pct + "%";
  document.getElementById("progFraction").textContent = `${idx} of ${total}`;
  document.getElementById("progBar").style.width = pct + "%";
  if (filename) document.getElementById("progFilename").textContent = filename;
  document.getElementById("tPortrait").textContent = portraits;
  document.getElementById("tLandscape").textContent = landscapes;
  document.getElementById("tUncertain").textContent = uncertain;
}

// ── Results ───────────────────────────────────────────────────

function buildResults() {
  currentTab = "all";
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.getElementById("tab-all").classList.add("active");
  updateCounts();
  renderGrid();
}

function updateCounts() {
  let p = 0, l = 0, u = 0;
  for (const r of allResults) {
    const lbl = effectiveLabel(r);
    if (lbl === "portrait") p++;
    else if (lbl === "landscape") l++;
    else u++;
  }
  document.getElementById("n-all").textContent = allResults.length;
  document.getElementById("n-portrait").textContent = p;
  document.getElementById("n-landscape").textContent = l;
  document.getElementById("n-uncertain").textContent = u;
}

function setTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  renderGrid();
}

function onThreshold(val) {
  document.getElementById("threshDisplay").textContent = val + "%";
  updateCounts();
  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById("photoGrid");
  grid.innerHTML = "";

  const items = allResults.filter(r =>
    currentTab === "all" || effectiveLabel(r) === currentTab
  );

  if (items.length === 0) {
    grid.innerHTML = `<div class="empty-state">No photos in this category</div>`;
    return;
  }

  items.forEach((entry, i) => {
    const lbl = effectiveLabel(entry);
    const labelText = lbl.charAt(0).toUpperCase() + lbl.slice(1);
    const confPct = Math.round(entry.confidence * 100);

    const card = document.createElement("div");
    card.className = `pcard ${lbl}`;
    card.style.animationDelay = `${Math.min(i * 20, 400)}ms`;
    card.innerHTML = `
      <img class="pcard-img"
           src="${API}/image?path=${encodeURIComponent(entry.path)}"
           alt="${entry.filename}" loading="lazy" />
      <div class="pcard-footer">
        <span class="pcard-label">${labelText}</span>
        <span class="pcard-conf">${confPct}%</span>
      </div>
    `;
    card.addEventListener("click", () => openLightbox(entry, lbl));
    grid.appendChild(card);
  });
}

// ── Lightbox ──────────────────────────────────────────────────

function openLightbox(entry, lbl) {
  const confPct = Math.round(entry.confidence * 100);
  document.getElementById("lbImg").src = `${API}/image?path=${encodeURIComponent(entry.path)}`;
  document.getElementById("lbInfo").innerHTML = `
    <strong style="color:#111">${entry.filename}</strong>
    <span>${lbl} · ${confPct}% confidence</span>
    <span>Portrait score: ${Math.round((entry.portrait_score || 0) * 100)}%</span>
    <span>Landscape score: ${Math.round((entry.landscape_score || 0) * 100)}%</span>
  `;
  document.getElementById("lightbox").classList.remove("hidden");
}

function closeLightbox() {
  document.getElementById("lightbox").classList.add("hidden");
  document.getElementById("lbImg").src = "";
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") { closeLightbox(); closeModal(); }
});

// ── Sort ──────────────────────────────────────────────────────

async function doSort() {
  const btn = document.getElementById("copyBtn");
  btn.disabled = true;
  btn.textContent = "Copying…";

  try {
    const r = await fetch(`${API}/sort`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder: selectedFolder,
        results: allResults,
        threshold: getThreshold(),
      }),
    });
    const d = await r.json();
    if (d.ok) {
      const { portraits, landscapes, uncertain } = d.counts;
      document.getElementById("doneBody").textContent =
        `Copied ${portraits} portrait${portraits !== 1 ? "s" : ""}, ${landscapes} landscape${landscapes !== 1 ? "s" : ""}, and ${uncertain} uncertain photo${uncertain !== 1 ? "s" : ""}.`;
      document.getElementById("donePath").textContent = d.sorted_dir;
      document.getElementById("doneModal").classList.remove("hidden");
    } else {
      showToast(d.error || "Copy failed", "err");
    }
  } catch (e) {
    showToast("Error: " + e.message, "err");
  }

  btn.disabled = false;
  btn.textContent = "Copy to folders";
}

function closeModal() {
  document.getElementById("doneModal").classList.add("hidden");
}

// ── Toast ─────────────────────────────────────────────────────

function showToast(msg, type = "") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add("hidden"), 4000);
}

// ── Init ──────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  ping();
  setInterval(ping, 10000);

  document.getElementById("folderPath").addEventListener("keydown", e => {
    if (e.key === "Enter") useManualPath();
  });

  show("screen-pick");
});
