const landingEl = document.getElementById("landing");
const shellEl = document.getElementById("shell");
const startAppBtn = document.getElementById("startAppBtn");
const installBtn = document.getElementById("installBtn");

const menuBtn = document.getElementById("menuBtn");
const offcanvasEl = document.getElementById("offcanvas");
const closeMenuBtn = document.getElementById("closeMenuBtn");
const menuOverlayEl = document.getElementById("menuOverlay");

const menuItems = Array.from(document.querySelectorAll(".menu-item"));
const views = Array.from(document.querySelectorAll(".view"));

const playStepSelectEl = document.getElementById("playStepSelect");
const playStepSetupEl = document.getElementById("playStepSetup");
const playStepMatchEl = document.getElementById("playStepMatch");
const toSetupStepBtn = document.getElementById("toSetupStepBtn");
const backToSelectBtn = document.getElementById("backToSelectBtn");
const backToSetupBtn = document.getElementById("backToSetupBtn");

const titleGameEl = document.getElementById("titleGame");
const titleStatusEl = document.getElementById("titleStatus");

const gameIconButtons = Array.from(document.querySelectorAll(".game-icon"));
const x01OptionsEl = document.getElementById("x01Options");
const cricketOptionsEl = document.getElementById("cricketOptions");

const x01ValueEl = document.getElementById("x01Value");
const inModeEl = document.getElementById("inMode");
const outModeEl = document.getElementById("outMode");
const cutThroatEl = document.getElementById("cutThroat");
const legsToWinSetEl = document.getElementById("legsToWinSet");
const playerInputs = ["player1", "player2", "player3", "player4"].map((id) => document.getElementById(id));

const startMatchBtn = document.getElementById("startMatchBtn");
const simulateBtn = document.getElementById("simulateBtn");
const undoBtn = document.getElementById("undoBtn");
const reloadBtn = document.getElementById("reloadBtn");

const correctBtn = document.getElementById("correctBtn");
const correctionSheetEl = document.getElementById("correctionSheet");
const closeSheetBtn = document.getElementById("closeSheetBtn");
const manualDisplayEl = document.getElementById("manualDisplay");
const clearManualBtn = document.getElementById("clearManualBtn");
const submitManualBtn = document.getElementById("submitManualBtn");
const keypadEl = document.getElementById("keypad");
const shortcutButtons = Array.from(document.querySelectorAll(".shortcut"));

const activeNameEl = document.getElementById("activeName");
const activeScoreEl = document.getElementById("activeScore");
const nextNameEl = document.getElementById("nextName");
const nextScoreEl = document.getElementById("nextScore");
const matchAverageLiveEl = document.getElementById("matchAverageLive");
const throwsCountLiveEl = document.getElementById("throwsCountLive");

const playersTableEl = document.getElementById("playersTable");
const managePlayerInputs = ["managePlayer1", "managePlayer2", "managePlayer3", "managePlayer4"].map((id) => document.getElementById(id));
const manageLegsToWinSetEl = document.getElementById("manageLegsToWinSet");
const savePlayersManageBtn = document.getElementById("savePlayersManageBtn");
const matchStatsEl = document.getElementById("matchStats");
const playerStatsEl = document.getElementById("playerStats");
const sourceEl = document.getElementById("source");
const positionEl = document.getElementById("position");
const updatedAtEl = document.getElementById("updatedAt");

const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const refreshMsEl = document.getElementById("refreshMs");
const voteThresholdEl = document.getElementById("voteThreshold");
const camFields = [
  {
    name: document.getElementById("cam1Name"),
    device: document.getElementById("cam1Device"),
    enabled: document.getElementById("cam1Enabled"),
    preview: document.getElementById("cam1Preview"),
  },
  {
    name: document.getElementById("cam2Name"),
    device: document.getElementById("cam2Device"),
    enabled: document.getElementById("cam2Enabled"),
    preview: document.getElementById("cam2Preview"),
  },
  {
    name: document.getElementById("cam3Name"),
    device: document.getElementById("cam3Device"),
    enabled: document.getElementById("cam3Enabled"),
    preview: document.getElementById("cam3Preview"),
  },
];

let deferredPrompt = null;
let selectedGameMode = "x01";
let pollTimer = null;
let currentCameraConfig = { vote_threshold_mm: 25, cameras: [] };
let availableCameras = [];

function setInputValueIfIdle(inputEl, value) {
  if (!inputEl) return;
  if (document.activeElement === inputEl) return;
  inputEl.value = value;
}

function openMenu() {
  offcanvasEl.classList.add("open");
  menuOverlayEl.classList.add("open");
}

function closeMenu() {
  offcanvasEl.classList.remove("open");
  menuOverlayEl.classList.remove("open");
}

function selectView(viewId) {
  views.forEach((view) => view.classList.toggle("active", view.id === viewId));
  menuItems.forEach((item) => item.classList.toggle("active", item.dataset.view === viewId));
  closeMenu();
}

function setPlayStep(step) {
  const map = {
    select: playStepSelectEl,
    setup: playStepSetupEl,
    match: playStepMatchEl,
  };
  Object.entries(map).forEach(([name, el]) => {
    el.classList.toggle("active", name === step);
  });
}

function setGameMode(mode) {
  selectedGameMode = mode;
  gameIconButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.game === mode));
  x01OptionsEl.classList.toggle("hidden", mode !== "x01");
  cricketOptionsEl.classList.toggle("hidden", mode !== "cricket");
}

function openSheet() {
  correctionSheetEl.classList.add("open");
}

function closeSheet() {
  correctionSheetEl.classList.remove("open");
}

function addManualDigit(value) {
  const current = manualDisplayEl.value;
  if (value === "back") {
    manualDisplayEl.value = current.length > 1 ? current.slice(0, -1) : "0";
    return;
  }

  const next = current === "0" ? value : `${current}${value}`;
  const normalized = String(Math.min(180, Number.parseInt(next || "0", 10)));
  manualDisplayEl.value = Number.isNaN(Number.parseInt(normalized, 10)) ? "0" : normalized;
}

function resetManualInput() {
  manualDisplayEl.value = "0";
}

function getPlayersFromInputs() {
  return playerInputs.map((el) => el.value.trim()).filter((name) => name.length > 0).slice(0, 4);
}

function validatePlayers(players) {
  if (players.length < 2) {
    throw new Error("Mindestens 2 Spieler erforderlich");
  }
  if (players.length > 4) {
    throw new Error("Maximal 4 Spieler pro Match erlaubt");
  }
}

function getGamePayload() {
  if (selectedGameMode === "x01") {
    const variations = [];
    if (inModeEl.value === "double") variations.push("double_in");
    if (outModeEl.value === "double") variations.push("double_out");
    if (outModeEl.value === "master") variations.push("master_out");
    return { game: x01ValueEl.value, variations };
  }

  if (selectedGameMode === "cricket") {
    return {
      game: "cricket",
      variations: cutThroatEl.checked ? ["cut_throat"] : [],
    };
  }

  return {
    game: "shanghai",
    variations: [],
  };
}

async function fetchState() {
  const res = await fetch("/api/state", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchCameraConfig() {
  const res = await fetch("/api/camera-config", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchAvailableCameras() {
  const res = await fetch("/api/cameras", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return Array.isArray(data.cameras) ? data.cameras : [];
}

function renderCameraSelectOptions() {
  const fallbackCameras = Array.from({ length: 10 }, (_, i) => ({ index: i, label: "Manuell" }));
  const cameraOptions = availableCameras.length ? availableCameras : fallbackCameras;

  camFields.forEach((field) => {
    const current = field.device.value;
    field.device.innerHTML = "";
    cameraOptions.forEach((cam) => {
      const option = document.createElement("option");
      option.value = String(cam.index);
      option.textContent = `${cam.label} (#${cam.index})`;
      field.device.appendChild(option);
    });
    if (current) field.device.value = current;
  });
}

function bindCameraStreams() {
  camFields.forEach((field) => {
    const selected = field.device.value;
    if (!selected) {
      field.preview.removeAttribute("src");
      return;
    }
    field.preview.src = `/api/camera-stream?index=${encodeURIComponent(selected)}&t=${Date.now()}`;
  });
}

function applyCameraConfig(config) {
  currentCameraConfig = config || { vote_threshold_mm: 25, cameras: [] };
  setInputValueIfIdle(voteThresholdEl, String(config.vote_threshold_mm ?? 25));
  const cams = Array.isArray(config.cameras) ? config.cameras : [];
  camFields.forEach((field, idx) => {
    const cam = cams[idx];
    if (!cam) return;
    setInputValueIfIdle(field.name, String(cam.name ?? `cam-${idx + 1}`));
    if (document.activeElement !== field.device) {
      field.device.value = String(cam.index ?? idx);
    }
    if (document.activeElement !== field.enabled) {
      field.enabled.checked = Boolean(cam.enabled ?? true);
    }
  });
  bindCameraStreams();
}

function buildCameraPayload() {
  const existingCameras = Array.isArray(currentCameraConfig.cameras) ? currentCameraConfig.cameras : [];
  return {
    vote_threshold_mm: Number.parseFloat(voteThresholdEl.value || "25"),
    cameras: camFields.map((field, idx) => ({
      name: (field.name.value || "").trim(),
      index: Number.parseInt(field.device.value || `${idx}`, 10),
      enabled: Boolean(field.enabled.checked),
      homography: existingCameras[idx]?.homography ?? null,
    })),
  };
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || data.message || `HTTP ${res.status}`);
  }
  return data;
}

async function saveMatchSetup() {
  const players = getPlayersFromInputs();
  validatePlayers(players);
  const legs = Math.max(1, Number.parseInt(legsToWinSetEl.value || "3", 10));
  const gamePayload = getGamePayload();

  await postJson("/api/game", gamePayload);
  await postJson("/api/match", { players, legs_to_win_set: legs });
}

async function saveManagedPlayers() {
  const players = managePlayerInputs.map((el) => el.value.trim()).filter((name) => name.length > 0).slice(0, 4);
  validatePlayers(players);
  const legs = Math.max(1, Number.parseInt(manageLegsToWinSetEl.value || "3", 10));
  await postJson("/api/match", { players, legs_to_win_set: legs });
}

async function sendManualScore() {
  const points = Number.parseInt(manualDisplayEl.value || "0", 10);
  await postJson("/api/manual", { points, bed: "S" });
  resetManualInput();
  closeSheet();
}

async function simulateThrow() {
  await postJson("/api/simulate", {});
}

async function undoLast() {
  await postJson("/api/undo", {});
}

function renderPlayersTable(state) {
  const players = (state.players || []).slice(0, 4);
  const current = state.current_player;
  const isCricket = state.game?.game === "cricket";
  const cricketHead = isCricket ? "<th>20</th><th>19</th><th>18</th><th>17</th><th>16</th><th>15</th><th>B</th>" : "";

  const rows = players.map((p) => {
    const marks = isCricket
      ? `<td>${p.cricket_marks["20"]}</td><td>${p.cricket_marks["19"]}</td><td>${p.cricket_marks["18"]}</td><td>${p.cricket_marks["17"]}</td><td>${p.cricket_marks["16"]}</td><td>${p.cricket_marks["15"]}</td><td>${p.cricket_marks["25"]}</td>`
      : "";

    return `<tr class="${p.name === current ? "active-row" : ""}"><td>${p.name}</td><td>${p.remaining ?? "-"}</td><td>${p.points}</td><td>${p.legs_won}</td><td>${p.sets_won}</td>${marks}</tr>`;
  }).join("");

  playersTableEl.innerHTML = `<table><thead><tr><th>Spieler</th><th>Rest</th><th>Punkte</th><th>Legs</th><th>Sets</th>${cricketHead}</tr></thead><tbody>${rows}</tbody></table>`;

  playerInputs.forEach((input, idx) => {
    setInputValueIfIdle(input, players[idx]?.name || "");
  });
  managePlayerInputs.forEach((input, idx) => {
    setInputValueIfIdle(input, players[idx]?.name || "");
  });
  setInputValueIfIdle(manageLegsToWinSetEl, String(state.game?.legs_to_win_set ?? 3));
}

function renderStats(state) {
  const m = state.stats?.match || {};
  matchStatsEl.innerHTML = `<p>Darts ${m.total_darts ?? 0} | Turns ${m.total_turns ?? 0} | Punkte ${m.total_points ?? 0} | Avg/Dart ${m.average_per_dart ?? 0} | Avg/Turn ${m.average_per_turn ?? 0}</p>`;

  const ps = state.stats?.players || {};
  const rows = Object.entries(ps).map(([name, s]) => `<tr><td>${name}</td><td>${s.darts_thrown}</td><td>${s.turns_played}</td><td>${s.total_applied_points}</td><td>${s.average_per_dart}</td><td>${s.average_per_turn}</td><td>${s.highest_dart}</td><td>${s.highest_turn}</td><td>${s.busts}</td><td>${s.checkouts}</td></tr>`).join("");
  playerStatsEl.innerHTML = `<table><thead><tr><th>Spieler</th><th>Darts</th><th>Turns</th><th>Punkte</th><th>Avg/Dart</th><th>Avg/Turn</th><th>High Dart</th><th>High Turn</th><th>Busts</th><th>Checkouts</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function applyState(state) {
  const players = state.players || [];
  const activeIdx = state.match?.current_player_index ?? 0;
  const active = players[activeIdx] || null;
  const next = players.length > 1 ? players[(activeIdx + 1) % players.length] : active;

  activeNameEl.textContent = active?.name || "-";
  activeScoreEl.textContent = active?.remaining ?? active?.points ?? "-";
  nextNameEl.textContent = next?.name || "-";
  nextScoreEl.textContent = next?.remaining ?? next?.points ?? "-";

  titleStatusEl.textContent = `Set ${state.match?.set_number ?? "-"} | Leg ${state.match?.leg_number ?? "-"}`;

  const matchStats = state.stats?.match || {};
  matchAverageLiveEl.textContent = Number(matchStats.average_per_dart ?? 0).toFixed(2);
  throwsCountLiveEl.textContent = String(matchStats.total_darts ?? 0);

  if (["301", "501", "701", "901"].includes(state.game?.game)) {
    setGameMode("x01");
    x01ValueEl.value = state.game.game;
    inModeEl.value = state.game.variations?.includes("double_in") ? "double" : "single";
    outModeEl.value = state.game.variations?.includes("master_out") ? "master" : (state.game.variations?.includes("double_out") ? "double" : "single");
    titleGameEl.textContent = `X01 ${state.game.game}`;
  } else {
    setGameMode(state.game?.game || "x01");
    cutThroatEl.checked = state.game?.variations?.includes("cut_throat") || false;
    titleGameEl.textContent = (state.game?.game || "X01").toUpperCase();
  }

  setInputValueIfIdle(legsToWinSetEl, String(state.game?.legs_to_win_set ?? 3));
  setInputValueIfIdle(manageLegsToWinSetEl, String(state.game?.legs_to_win_set ?? 3));

  renderPlayersTable(state);
  renderStats(state);

  sourceEl.textContent = state.source ?? "-";
  positionEl.textContent = (typeof state.x_mm === "number" && typeof state.y_mm === "number") ? `${state.x_mm.toFixed(1)} / ${state.y_mm.toFixed(1)}` : "-";
  updatedAtEl.textContent = state.updated_at ? new Date(state.updated_at).toLocaleTimeString() : "-";
}

async function refreshState() {
  try {
    const state = await fetchState();
    applyState(state);
  } catch {
    titleStatusEl.textContent = "API nicht erreichbar";
  }
}

function restartPolling() {
  if (pollTimer) clearInterval(pollTimer);
  const interval = Math.max(250, Number.parseInt(refreshMsEl.value || "500", 10));
  pollTimer = setInterval(refreshState, interval);
}

startAppBtn.addEventListener("click", async () => {
  landingEl.classList.add("hidden");
  shellEl.classList.remove("hidden");
  await refreshState();
  try {
    availableCameras = await fetchAvailableCameras();
    renderCameraSelectOptions();
    const cameraConfig = await fetchCameraConfig();
    applyCameraConfig(cameraConfig);
  } catch {
    titleStatusEl.textContent = "Kamera-Konfig konnte nicht geladen werden";
  }
  restartPolling();
});

menuBtn.addEventListener("click", openMenu);
closeMenuBtn.addEventListener("click", closeMenu);
menuOverlayEl.addEventListener("click", closeMenu);

for (const item of menuItems) {
  item.addEventListener("click", () => selectView(item.dataset.view));
}

for (const button of gameIconButtons) {
  button.addEventListener("click", () => setGameMode(button.dataset.game));
}

toSetupStepBtn.addEventListener("click", () => setPlayStep("setup"));
backToSelectBtn.addEventListener("click", () => setPlayStep("select"));
backToSetupBtn.addEventListener("click", () => setPlayStep("setup"));

startMatchBtn.addEventListener("click", async () => {
  try {
    await saveMatchSetup();
    await refreshState();
    setPlayStep("match");
    selectView("playView");
  } catch (err) {
    titleStatusEl.textContent = `Fehler: ${err.message}`;
  }
});

simulateBtn.addEventListener("click", async () => {
  await simulateThrow();
  await refreshState();
});

undoBtn.addEventListener("click", async () => {
  try {
    await undoLast();
    await refreshState();
  } catch (err) {
    titleStatusEl.textContent = err.message;
  }
});

reloadBtn.addEventListener("click", refreshState);

correctBtn.addEventListener("click", openSheet);
closeSheetBtn.addEventListener("click", closeSheet);
clearManualBtn.addEventListener("click", resetManualInput);

shortcutButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    manualDisplayEl.value = btn.dataset.shortcut;
  });
});

keypadEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  const key = target.dataset.key;
  if (!key) return;
  addManualDigit(key);
});

submitManualBtn.addEventListener("click", async () => {
  try {
    await sendManualScore();
    await refreshState();
  } catch (err) {
    titleStatusEl.textContent = `Korrektur fehlgeschlagen: ${err.message}`;
  }
});

saveSettingsBtn.addEventListener("click", () => {
  (async () => {
    try {
      const saved = await postJson("/api/camera-config", buildCameraPayload());
      if (saved.config) applyCameraConfig(saved.config);
      availableCameras = await fetchAvailableCameras();
      renderCameraSelectOptions();
      restartPolling();
      titleStatusEl.textContent = "Einstellungen gespeichert";
    } catch (err) {
      titleStatusEl.textContent = `Speichern fehlgeschlagen: ${err.message}`;
    }
  })();
});

camFields.forEach((field) => {
  field.device.addEventListener("change", bindCameraStreams);
});

savePlayersManageBtn.addEventListener("click", async () => {
  try {
    await saveManagedPlayers();
    await refreshState();
    titleStatusEl.textContent = "Spieler aktualisiert";
  } catch (err) {
    titleStatusEl.textContent = `Spieler-Update fehlgeschlagen: ${err.message}`;
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  installBtn.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js");
  });
}

setGameMode("x01");
setPlayStep("select");
