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
const matchStatsEl = document.getElementById("matchStats");
const playerStatsEl = document.getElementById("playerStats");
const sourceEl = document.getElementById("source");
const positionEl = document.getElementById("position");
const updatedAtEl = document.getElementById("updatedAt");

const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const refreshMsEl = document.getElementById("refreshMs");

let deferredPrompt = null;
let selectedGameMode = "x01";
let pollTimer = null;

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
  const legs = Math.max(1, Number.parseInt(legsToWinSetEl.value || "3", 10));
  const gamePayload = getGamePayload();

  await postJson("/api/game", gamePayload);
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
  const players = state.players || [];
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
    input.value = players[idx]?.name || "";
  });
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

  legsToWinSetEl.value = String(state.game?.legs_to_win_set ?? 3);

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
  restartPolling();
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
