const scoreValue = document.getElementById("scoreValue");
const scoreMeta = document.getElementById("scoreMeta");
const gameStatusEl = document.getElementById("gameStatus");
const sourceEl = document.getElementById("source");
const positionEl = document.getElementById("position");
const updatedAtEl = document.getElementById("updatedAt");
const playersTableEl = document.getElementById("playersTable");
const turnHistoryEl = document.getElementById("turnHistory");
const matchStatsEl = document.getElementById("matchStats");
const playerStatsEl = document.getElementById("playerStats");

const simulateBtn = document.getElementById("simulateBtn");
const undoBtn = document.getElementById("undoBtn");
const reloadBtn = document.getElementById("reloadBtn");
const saveGameBtn = document.getElementById("saveGameBtn");
const savePlayersBtn = document.getElementById("savePlayersBtn");
const installBtn = document.getElementById("installBtn");

const gameTypeEl = document.getElementById("gameType");
const legsToWinSetEl = document.getElementById("legsToWinSet");
const variationFieldset = document.getElementById("variationFieldset");
const playerInputs = ["player1", "player2", "player3", "player4"].map((id) => document.getElementById(id));

let deferredPrompt = null;

function variationCheckboxes() {
  return Array.from(variationFieldset.querySelectorAll("input[type='checkbox']"));
}

async function fetchState() {
  const res = await fetch("/api/state", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function saveGameConfig() {
  const selectedVariations = variationCheckboxes().filter((cb) => cb.checked).map((cb) => cb.value);
  const res = await fetch("/api/game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game: gameTypeEl.value, variations: selectedVariations }),
  });
  const payload = await res.json();
  if (!res.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${res.status}`);
}

async function savePlayers() {
  const players = playerInputs.map((el) => el.value.trim()).filter((name) => name.length > 0);
  const legsToWinSet = Number.parseInt(legsToWinSetEl.value || "3", 10);
  const res = await fetch("/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players, legs_to_win_set: legsToWinSet }),
  });
  const payload = await res.json();
  if (!res.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${res.status}`);
}

async function undoLastDart() {
  const res = await fetch("/api/undo", { method: "POST" });
  const payload = await res.json();
  if (!res.ok || payload.ok === false) throw new Error(payload.message || payload.error || "Undo fehlgeschlagen");
}

function applyGameConfig(gameCfg) {
  gameTypeEl.value = gameCfg.game || "501";
  legsToWinSetEl.value = String(gameCfg.legs_to_win_set || 3);

  const allowed = new Set(gameCfg.allowed_variations || []);
  const selected = new Set(gameCfg.variations || []);

  for (const checkbox of variationCheckboxes()) {
    const enabled = allowed.has(checkbox.value);
    checkbox.disabled = !enabled;
    checkbox.checked = enabled && selected.has(checkbox.value);
  }
}

function renderPlayersTable(state) {
  const players = state.players || [];
  const current = state.current_player;
  const game = state.game?.game || "501";

  const marksHeader = game === "cricket"
    ? "<th>20</th><th>19</th><th>18</th><th>17</th><th>16</th><th>15</th><th>Bull</th>"
    : "";

  const rows = players.map((p) => {
    const marksCells = game === "cricket"
      ? `<td>${p.cricket_marks["20"]}</td><td>${p.cricket_marks["19"]}</td><td>${p.cricket_marks["18"]}</td><td>${p.cricket_marks["17"]}</td><td>${p.cricket_marks["16"]}</td><td>${p.cricket_marks["15"]}</td><td>${p.cricket_marks["25"]}</td>`
      : "";

    return `<tr class="${p.name === current ? "active-row" : ""}">
      <td>${p.name}</td>
      <td>${p.remaining ?? "-"}</td>
      <td>${p.points}</td>
      <td>${p.legs_won}</td>
      <td>${p.sets_won}</td>
      ${marksCells}
    </tr>`;
  }).join("");

  playersTableEl.innerHTML = `<table>
    <thead>
      <tr>
        <th>Spieler</th><th>Rest</th><th>Punkte</th><th>Legs</th><th>Sets</th>${marksHeader}
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;

  playerInputs.forEach((input, idx) => {
    input.value = players[idx]?.name || "";
  });
}

function renderHistory(state) {
  const turns = state.history?.turns || [];
  const recent = turns.slice(-12).reverse();
  if (recent.length === 0) {
    turnHistoryEl.innerHTML = "<p class='meta'>Noch keine Würfe.</p>";
    return;
  }

  turnHistoryEl.innerHTML = recent.map((turn) => {
    const darts = turn.darts.map((d) => `${d.dart}: ${d.bed}${d.number ?? ""} (${d.applied_points})`).join(" | ");
    return `<div class="history-item">
      <strong>${turn.player}</strong> · Set ${turn.set} / Leg ${turn.leg} / Turn ${turn.turn}<br/>
      <span>${darts}</span><br/>
      <span class="muted">Total ${turn.turn_total} · ${turn.reason}</span>
    </div>`;
  }).join("");
}

function renderStats(state) {
  const match = state.stats?.match || {};
  matchStatsEl.innerHTML = `<p>Darts: ${match.total_darts ?? 0} | Turns: ${match.total_turns ?? 0} | Punkte: ${match.total_points ?? 0} | Avg/Dart: ${match.average_per_dart ?? 0} | Avg/Turn: ${match.average_per_turn ?? 0} | Undos: ${match.undo_count ?? 0}</p>`;

  const playerStats = state.stats?.players || {};
  const rows = Object.entries(playerStats).map(([name, s]) =>
    `<tr><td>${name}</td><td>${s.darts_thrown}</td><td>${s.turns_played}</td><td>${s.total_applied_points}</td><td>${s.average_per_dart}</td><td>${s.average_per_turn}</td><td>${s.highest_dart}</td><td>${s.highest_turn}</td><td>${s.busts}</td><td>${s.checkouts}</td></tr>`
  ).join("");

  playerStatsEl.innerHTML = `<table>
    <thead><tr><th>Spieler</th><th>Darts</th><th>Turns</th><th>Punkte</th><th>Avg/Dart</th><th>Avg/Turn</th><th>High Dart</th><th>High Turn</th><th>Busts</th><th>Checkouts</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function applyState(state) {
  scoreValue.textContent = String(state.points ?? 0);
  scoreMeta.textContent = `Feld: ${state.bed ?? "-"}`;
  sourceEl.textContent = state.source ?? "-";

  const match = state.match || {};
  gameStatusEl.textContent = `Matchstatus: Leg ${match.leg_number ?? "-"}, Set ${match.set_number ?? "-"}, Turn ${match.turn_number ?? "-"}, Spieler am Zug: ${state.current_player ?? "-"}, Info: ${match.last_note ?? "-"}`;

  if (state.game) applyGameConfig(state.game);
  renderPlayersTable(state);
  renderHistory(state);
  renderStats(state);

  if (typeof state.x_mm === "number" && typeof state.y_mm === "number") {
    positionEl.textContent = `${state.x_mm.toFixed(1)} mm / ${state.y_mm.toFixed(1)} mm`;
  } else {
    positionEl.textContent = "-";
  }

  updatedAtEl.textContent = state.updated_at ? new Date(state.updated_at).toLocaleTimeString() : "-";
}

async function refreshLoop() {
  try {
    const state = await fetchState();
    applyState(state);
  } catch {
    scoreMeta.textContent = "Verbindung zur API fehlgeschlagen";
  }
}

async function simulateThrow() {
  await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await refreshLoop();
}

saveGameBtn.addEventListener("click", async () => {
  try {
    await saveGameConfig();
    await refreshLoop();
  } catch (err) {
    scoreMeta.textContent = `Konfiguration fehlgeschlagen: ${err.message}`;
  }
});

savePlayersBtn.addEventListener("click", async () => {
  try {
    await savePlayers();
    await refreshLoop();
  } catch (err) {
    scoreMeta.textContent = `Spieler-Setup fehlgeschlagen: ${err.message}`;
  }
});

undoBtn.addEventListener("click", async () => {
  try {
    await undoLastDart();
    await refreshLoop();
  } catch (err) {
    scoreMeta.textContent = `Undo fehlgeschlagen: ${err.message}`;
  }
});

simulateBtn.addEventListener("click", simulateThrow);
reloadBtn.addEventListener("click", refreshLoop);

gameTypeEl.addEventListener("change", () => {
  const selectedGame = gameTypeEl.value;
  const allowedByGame = {
    "301": ["double_in", "double_out", "master_out"],
    "501": ["double_in", "double_out", "master_out"],
    "701": ["double_in", "double_out", "master_out"],
    "901": ["double_in", "double_out", "master_out"],
    cricket: ["cut_throat"],
    shanghai: ["double_in", "double_out", "master_out"],
  };

  const allowed = new Set(allowedByGame[selectedGame] || []);
  for (const checkbox of variationCheckboxes()) {
    checkbox.disabled = !allowed.has(checkbox.value);
    if (checkbox.disabled) checkbox.checked = false;
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

refreshLoop();
setInterval(refreshLoop, 500);
