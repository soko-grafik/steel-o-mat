const landingEl = document.getElementById("landing");
const appRootEl = document.getElementById("appRoot");
const startAppBtn = document.getElementById("startAppBtn");
const installBtn = document.getElementById("installBtn");

const navButtons = Array.from(document.querySelectorAll(".nav-btn"));
const views = Array.from(document.querySelectorAll(".view"));

const scoreValue = document.getElementById("scoreValue");
const scoreMeta = document.getElementById("scoreMeta");
const currentPlayerEl = document.getElementById("currentPlayer");
const gameStatusEl = document.getElementById("gameStatus");
const sourceEl = document.getElementById("source");
const positionEl = document.getElementById("position");
const updatedAtEl = document.getElementById("updatedAt");

const gameModeEl = document.getElementById("gameMode");
const x01ConfigEl = document.getElementById("x01Config");
const cricketConfigEl = document.getElementById("cricketConfig");
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
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const refreshMsEl = document.getElementById("refreshMs");

const playersTableEl = document.getElementById("playersTable");
const turnHistoryEl = document.getElementById("turnHistory");
const matchStatsEl = document.getElementById("matchStats");
const playerStatsEl = document.getElementById("playerStats");

let deferredPrompt = null;
let pollTimer = null;

function selectView(id) {
  for (const view of views) {
    view.classList.toggle("active", view.id === id);
  }
  for (const btn of navButtons) {
    btn.classList.toggle("active", btn.dataset.view === id);
  }
}

function setModeVisibility() {
  const mode = gameModeEl.value;
  x01ConfigEl.classList.toggle("hidden", mode !== "x01");
  cricketConfigEl.classList.toggle("hidden", mode !== "cricket");
}

function getPlayersFromInputs() {
  return playerInputs.map((el) => el.value.trim()).filter((name) => name.length > 0).slice(0, 4);
}

function buildGamePayload() {
  const mode = gameModeEl.value;
  const variations = [];
  let game = mode;

  if (mode === "x01") {
    game = x01ValueEl.value;
    if (inModeEl.value === "double") variations.push("double_in");
    if (outModeEl.value === "double") variations.push("double_out");
    if (outModeEl.value === "master") variations.push("master_out");
  }

  if (mode === "cricket" && cutThroatEl.checked) {
    variations.push("cut_throat");
  }

  return { game, variations };
}

async function fetchState() {
  const res = await fetch("/api/state", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function applyGameAndPlayers() {
  const gamePayload = buildGamePayload();
  const players = getPlayersFromInputs();
  const legsToWinSet = Number.parseInt(legsToWinSetEl.value || "3", 10);

  const gameRes = await fetch("/api/game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(gamePayload),
  });
  const gameData = await gameRes.json();
  if (!gameRes.ok || gameData.ok === false) {
    throw new Error(gameData.error || "Spiel konnte nicht gesetzt werden");
  }

  const matchRes = await fetch("/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players, legs_to_win_set: legsToWinSet }),
  });
  const matchData = await matchRes.json();
  if (!matchRes.ok || matchData.ok === false) {
    throw new Error(matchData.error || "Spieler konnten nicht gesetzt werden");
  }
}

async function simulateThrow() {
  await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await refreshState();
}

async function undoLastDart() {
  const res = await fetch("/api/undo", { method: "POST" });
  const payload = await res.json();
  if (!res.ok || payload.ok === false) {
    throw new Error(payload.message || payload.error || "Undo fehlgeschlagen");
  }
}

function renderPlayersTable(state) {
  const players = state.players || [];
  const current = state.current_player;
  const game = state.game?.game || "501";
  const showCricket = game === "cricket";

  const headers = showCricket ? "<th>20</th><th>19</th><th>18</th><th>17</th><th>16</th><th>15</th><th>Bull</th>" : "";

  const rows = players.map((p) => {
    const marks = showCricket
      ? `<td>${p.cricket_marks["20"]}</td><td>${p.cricket_marks["19"]}</td><td>${p.cricket_marks["18"]}</td><td>${p.cricket_marks["17"]}</td><td>${p.cricket_marks["16"]}</td><td>${p.cricket_marks["15"]}</td><td>${p.cricket_marks["25"]}</td>`
      : "";

    return `<tr class="${p.name === current ? "active-row" : ""}">
      <td>${p.name}</td>
      <td>${p.remaining ?? "-"}</td>
      <td>${p.points}</td>
      <td>${p.legs_won}</td>
      <td>${p.sets_won}</td>
      ${marks}
    </tr>`;
  }).join("");

  playersTableEl.innerHTML = `<table>
    <thead>
      <tr><th>Spieler</th><th>Rest</th><th>Punkte</th><th>Legs</th><th>Sets</th>${headers}</tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;

  playerInputs.forEach((input, idx) => {
    input.value = players[idx]?.name || "";
  });
}

function renderHistory(state) {
  const turns = state.history?.turns || [];
  const recent = turns.slice(-14).reverse();
  if (!recent.length) {
    turnHistoryEl.innerHTML = "<p class='muted'>Noch keine Historie vorhanden.</p>";
    return;
  }

  turnHistoryEl.innerHTML = recent.map((turn) => {
    const darts = turn.darts.map((d) => `${d.dart}. ${d.bed}${d.number ?? ""} (${d.applied_points})`).join(" | ");
    return `<div class="history-item"><strong>${turn.player}</strong> · Set ${turn.set} / Leg ${turn.leg} / Turn ${turn.turn}<br/>${darts}<br/><span class="muted">Total ${turn.turn_total} · ${turn.reason}</span></div>`;
  }).join("");
}

function renderStats(state) {
  const match = state.stats?.match || {};
  matchStatsEl.innerHTML = `<p>Darts: ${match.total_darts ?? 0} | Turns: ${match.total_turns ?? 0} | Punkte: ${match.total_points ?? 0} | Avg/Dart: ${match.average_per_dart ?? 0} | Avg/Turn: ${match.average_per_turn ?? 0} | Undos: ${match.undo_count ?? 0}</p>`;

  const players = state.stats?.players || {};
  const rows = Object.entries(players).map(([name, s]) => `<tr>
    <td>${name}</td><td>${s.darts_thrown}</td><td>${s.turns_played}</td><td>${s.total_applied_points}</td><td>${s.average_per_dart}</td><td>${s.average_per_turn}</td><td>${s.highest_dart}</td><td>${s.highest_turn}</td><td>${s.busts}</td><td>${s.checkouts}</td>
  </tr>`).join("");

  playerStatsEl.innerHTML = `<table>
    <thead><tr><th>Spieler</th><th>Darts</th><th>Turns</th><th>Punkte</th><th>Avg/Dart</th><th>Avg/Turn</th><th>High Dart</th><th>High Turn</th><th>Busts</th><th>Checkouts</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function applyState(state) {
  scoreValue.textContent = String(state.points ?? 0);
  scoreMeta.textContent = `Feld: ${state.bed ?? "-"}`;
  currentPlayerEl.textContent = state.current_player ?? "-";

  const match = state.match || {};
  gameStatusEl.textContent = `Set ${match.set_number ?? "-"}, Leg ${match.leg_number ?? "-"}, Turn ${match.turn_number ?? "-"}, ${match.last_note ?? "-"}`;

  const game = state.game || {};
  if (["301", "501", "701", "901"].includes(game.game)) {
    gameModeEl.value = "x01";
    x01ValueEl.value = game.game;
    inModeEl.value = (game.variations || []).includes("double_in") ? "double" : "single";
    outModeEl.value = (game.variations || []).includes("master_out") ? "master" : ((game.variations || []).includes("double_out") ? "double" : "single");
    cutThroatEl.checked = false;
  } else {
    gameModeEl.value = game.game || "x01";
    cutThroatEl.checked = (game.variations || []).includes("cut_throat");
  }
  legsToWinSetEl.value = String(game.legs_to_win_set ?? 3);
  setModeVisibility();

  sourceEl.textContent = state.source ?? "-";
  positionEl.textContent = (typeof state.x_mm === "number" && typeof state.y_mm === "number")
    ? `${state.x_mm.toFixed(1)} mm / ${state.y_mm.toFixed(1)} mm`
    : "-";
  updatedAtEl.textContent = state.updated_at ? new Date(state.updated_at).toLocaleTimeString() : "-";

  renderPlayersTable(state);
  renderHistory(state);
  renderStats(state);
}

async function refreshState() {
  try {
    const state = await fetchState();
    applyState(state);
  } catch {
    scoreMeta.textContent = "Verbindung zur API fehlgeschlagen";
  }
}

function restartPolling() {
  if (pollTimer) clearInterval(pollTimer);
  const ms = Math.max(250, Number.parseInt(refreshMsEl.value || "500", 10));
  pollTimer = setInterval(refreshState, ms);
}

startAppBtn.addEventListener("click", async () => {
  landingEl.classList.add("hidden");
  appRootEl.classList.remove("hidden");
  await refreshState();
  restartPolling();
});

for (const btn of navButtons) {
  btn.addEventListener("click", () => selectView(btn.dataset.view));
}

gameModeEl.addEventListener("change", setModeVisibility);

startMatchBtn.addEventListener("click", async () => {
  try {
    await applyGameAndPlayers();
    await refreshState();
    scoreMeta.textContent = "Match übernommen";
  } catch (err) {
    scoreMeta.textContent = `Setup fehlgeschlagen: ${err.message}`;
  }
});

simulateBtn.addEventListener("click", simulateThrow);

undoBtn.addEventListener("click", async () => {
  try {
    await undoLastDart();
    await refreshState();
  } catch (err) {
    scoreMeta.textContent = `Undo fehlgeschlagen: ${err.message}`;
  }
});

reloadBtn.addEventListener("click", refreshState);

saveSettingsBtn.addEventListener("click", () => {
  restartPolling();
  scoreMeta.textContent = "Einstellungen gespeichert";
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

setModeVisibility();
