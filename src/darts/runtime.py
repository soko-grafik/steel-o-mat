from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .scoring import ScoreResult, score_point

X01_GAMES = {"301", "501", "701", "901"}
CRICKET_GAME = "cricket"
SHANGHAI_GAME = "shanghai"

ALL_GAMES = X01_GAMES | {CRICKET_GAME, SHANGHAI_GAME}
ALLOWED_VARIATIONS = {
    "double_in",
    "double_out",
    "master_out",
    "cut_throat",
}
CRICKET_TARGETS = ["20", "19", "18", "17", "16", "15", "25"]


def _is_x01(game: str) -> bool:
    return game in X01_GAMES


def _allowed_for_game(game: str) -> set[str]:
    if _is_x01(game):
        return {"double_in", "double_out", "master_out"}
    if game == CRICKET_GAME:
        return {"cut_throat"}
    return {"double_in", "double_out", "master_out"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ScoreState:
    points: int = 0
    bed: str = "MISS"
    number: int | None = None
    x_mm: float | None = None
    y_mm: float | None = None
    source: str = "init"
    updated_at: str | None = None


@dataclass(slots=True)
class GameState:
    game: str = "501"
    variations: list[str] = field(default_factory=list)
    legs_to_win_set: int = 3


@dataclass(slots=True)
class PlayerState:
    name: str
    remaining: int | None = 501
    started: bool = True
    points: int = 0
    legs_won: int = 0
    sets_won: int = 0
    turn_start_remaining: int | None = 501
    cricket_marks: dict[str, int] = field(
        default_factory=lambda: {target: 0 for target in CRICKET_TARGETS}
    )


@dataclass(slots=True)
class MatchState:
    leg_number: int = 1
    set_number: int = 1
    turn_number: int = 1
    current_player_index: int = 0
    darts_in_turn: int = 0
    last_note: str = ""


@dataclass(slots=True)
class ThrowResolution:
    applied_points: int
    note: str
    end_turn: bool
    leg_reset: bool


class RuntimeState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._score = ScoreState(updated_at=_utc_now())
        self._game = GameState()
        self._players: list[PlayerState] = []
        self._match = MatchState()

        self._dart_history: list[dict[str, Any]] = []
        self._turn_history: list[dict[str, Any]] = []
        self._current_turn_darts: list[dict[str, Any]] = []
        self._undo_stack: list[dict[str, Any]] = []
        self._undo_count: int = 0

        self._set_players_locked(["Player 1", "Player 2"], legs_to_win_set=3)
        self._reset_leg_locked(starting_player_index=0)

    def _x01_start(self) -> int:
        return int(self._game.game)

    def _new_player(self, name: str) -> PlayerState:
        if _is_x01(self._game.game):
            start = self._x01_start()
            started = "double_in" not in set(self._game.variations)
            return PlayerState(
                name=name,
                remaining=start,
                turn_start_remaining=start,
                started=started,
            )
        return PlayerState(name=name, remaining=None, turn_start_remaining=None, started=True)

    def _clear_runtime_collections_locked(self) -> None:
        self._dart_history = []
        self._turn_history = []
        self._current_turn_darts = []
        self._undo_stack = []
        self._undo_count = 0

    def _set_players_locked(self, names: list[str], legs_to_win_set: int) -> None:
        if not 1 <= len(names) <= 4:
            raise ValueError("Players must be between 1 and 4")
        cleaned = [n.strip() for n in names if n.strip()]
        if len(cleaned) != len(names):
            raise ValueError("Player names must not be empty")
        lowered = [n.lower() for n in cleaned]
        if len(set(lowered)) != len(lowered):
            raise ValueError("Player names must be unique")
        if legs_to_win_set < 1:
            raise ValueError("legs_to_win_set must be >= 1")

        self._game.legs_to_win_set = int(legs_to_win_set)
        self._players = [self._new_player(name) for name in cleaned]

    def set_players(self, names: list[str], legs_to_win_set: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._set_players_locked(names, legs_to_win_set or self._game.legs_to_win_set)
            self._match = MatchState()
            self._reset_leg_locked(starting_player_index=0)
            self._clear_runtime_collections_locked()
            return self.match_snapshot_locked()

    def set_game(self, game: str, variations: list[str] | None = None) -> dict[str, Any]:
        game_normalized = str(game).strip().lower()
        if game_normalized not in ALL_GAMES:
            raise ValueError(f"Unsupported game '{game}'.")

        normalized_variations = sorted({str(v).strip().lower() for v in (variations or []) if str(v).strip()})
        unknown = [v for v in normalized_variations if v not in ALLOWED_VARIATIONS]
        if unknown:
            raise ValueError(f"Unknown variation(s): {', '.join(unknown)}")

        allowed = _allowed_for_game(game_normalized)
        disallowed = [v for v in normalized_variations if v not in allowed]
        if disallowed:
            raise ValueError(
                f"Variation(s) not allowed for {game_normalized}: {', '.join(disallowed)}"
            )

        with self._lock:
            self._game.game = game_normalized
            self._game.variations = normalized_variations
            current_names = [p.name for p in self._players] or ["Player 1", "Player 2"]
            self._set_players_locked(current_names, self._game.legs_to_win_set)
            self._match = MatchState()
            self._reset_leg_locked(starting_player_index=0)
            self._clear_runtime_collections_locked()
            return self.game_snapshot_locked()

    def _reset_leg_locked(self, starting_player_index: int) -> None:
        starting_idx = starting_player_index % len(self._players)
        for player in self._players:
            if _is_x01(self._game.game):
                start = self._x01_start()
                player.remaining = start
                player.turn_start_remaining = start
                player.started = "double_in" not in set(self._game.variations)
            else:
                player.remaining = None
                player.turn_start_remaining = None
                player.started = True
                player.points = 0
                player.cricket_marks = {target: 0 for target in CRICKET_TARGETS}

        self._match.current_player_index = starting_idx
        self._match.darts_in_turn = 0
        self._match.turn_number = 1
        self._current_turn_darts = []

    def game_snapshot_locked(self) -> dict[str, Any]:
        return {
            "game": self._game.game,
            "variations": list(self._game.variations),
            "allowed_variations": sorted(list(_allowed_for_game(self._game.game))),
            "legs_to_win_set": self._game.legs_to_win_set,
        }

    def game_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self.game_snapshot_locked()

    def _advance_turn_locked(self) -> None:
        self._match.current_player_index = (self._match.current_player_index + 1) % len(self._players)
        self._match.darts_in_turn = 0
        self._match.turn_number += 1
        self._current_turn_darts = []
        current = self._players[self._match.current_player_index]
        current.turn_start_remaining = current.remaining

    def _complete_leg_locked(self, winner_idx: int) -> None:
        winner = self._players[winner_idx]
        winner.legs_won += 1
        self._match.last_note = f"Leg won by {winner.name}"

        if winner.legs_won >= self._game.legs_to_win_set:
            winner.sets_won += 1
            for player in self._players:
                player.legs_won = 0
            self._match.set_number += 1
            self._match.leg_number = 1
            self._match.last_note = f"Set won by {winner.name}"
        else:
            self._match.leg_number += 1

        self._reset_leg_locked(starting_player_index=winner_idx)

    def _is_valid_double(self, bed: str) -> bool:
        return bed in {"D", "DB"}

    def _is_valid_master(self, bed: str) -> bool:
        return bed in {"D", "T", "DB"}

    def _apply_x01_throw_locked(self, result: ScoreResult) -> ThrowResolution:
        variations = set(self._game.variations)
        player = self._players[self._match.current_player_index]

        if player.turn_start_remaining is None:
            player.turn_start_remaining = player.remaining

        if "double_in" in variations and not player.started:
            if not self._is_valid_double(result.bed):
                return ThrowResolution(0, "Double-in required", False, False)
            player.started = True

        if not player.started:
            return ThrowResolution(0, "Waiting for valid in-shot", False, False)

        assert player.remaining is not None
        next_remaining = player.remaining - result.points

        if next_remaining < 0:
            player.remaining = player.turn_start_remaining
            return ThrowResolution(0, "Bust", True, False)

        if next_remaining == 1 and ("double_out" in variations or "master_out" in variations):
            player.remaining = player.turn_start_remaining
            return ThrowResolution(0, "Bust", True, False)

        if next_remaining == 0:
            if "master_out" in variations and not self._is_valid_master(result.bed):
                player.remaining = player.turn_start_remaining
                return ThrowResolution(0, "Master-out required", True, False)
            if "double_out" in variations and not self._is_valid_double(result.bed):
                player.remaining = player.turn_start_remaining
                return ThrowResolution(0, "Double-out required", True, False)

            player.remaining = 0
            self._complete_leg_locked(self._match.current_player_index)
            return ThrowResolution(result.points, "Checkout", True, True)

        player.remaining = next_remaining
        return ThrowResolution(result.points, "Scored", False, False)

    def _cricket_marks_for_result(self, result: ScoreResult) -> tuple[str | None, int]:
        if result.bed == "MISS" or result.number is None:
            return None, 0

        if result.number == 25:
            if result.bed == "OB":
                return "25", 1
            if result.bed == "DB":
                return "25", 2
            return None, 0

        if result.number not in {15, 16, 17, 18, 19, 20}:
            return None, 0

        multiplier = {"S": 1, "D": 2, "T": 3}.get(result.bed, 0)
        return str(result.number), multiplier

    def _all_closed(self, player: PlayerState) -> bool:
        return all(player.cricket_marks[t] >= 3 for t in CRICKET_TARGETS)

    def _apply_cricket_throw_locked(self, result: ScoreResult) -> ThrowResolution:
        target, marks = self._cricket_marks_for_result(result)
        player_idx = self._match.current_player_index
        player = self._players[player_idx]
        cut_throat = "cut_throat" in set(self._game.variations)

        if target is None or marks <= 0:
            return ThrowResolution(0, "No cricket score", False, False)

        current = player.cricket_marks[target]
        applied_marks = min(3, current + marks)
        overflow = max(0, current + marks - 3)
        player.cricket_marks[target] = applied_marks

        scored_points = 0
        value = int(target)
        if overflow > 0:
            open_opponents = [
                op for i, op in enumerate(self._players)
                if i != player_idx and op.cricket_marks[target] < 3
            ]
            if open_opponents:
                if cut_throat:
                    for op in open_opponents:
                        op.points += overflow * value
                else:
                    scored_points = overflow * value
                    player.points += scored_points

        if self._all_closed(player):
            if cut_throat:
                if all(player.points <= op.points for i, op in enumerate(self._players) if i != player_idx):
                    self._complete_leg_locked(player_idx)
                    return ThrowResolution(0, f"Cricket leg won by {player.name}", True, True)
            else:
                if all(player.points >= op.points for i, op in enumerate(self._players) if i != player_idx):
                    self._complete_leg_locked(player_idx)
                    return ThrowResolution(scored_points, f"Cricket leg won by {player.name}", True, True)

        return ThrowResolution(scored_points, "Cricket scored", False, False)

    def _push_undo_snapshot_locked(self) -> None:
        snapshot = {
            "score": copy.deepcopy(self._score),
            "game": copy.deepcopy(self._game),
            "players": copy.deepcopy(self._players),
            "match": copy.deepcopy(self._match),
            "dart_history": copy.deepcopy(self._dart_history),
            "turn_history": copy.deepcopy(self._turn_history),
            "current_turn_darts": copy.deepcopy(self._current_turn_darts),
        }
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 300:
            self._undo_stack.pop(0)

    def undo_last_action(self) -> dict[str, Any]:
        with self._lock:
            if not self._undo_stack:
                return {"ok": False, "message": "Nothing to undo"}
            restored = self._undo_stack.pop()
            self._score = restored["score"]
            self._game = restored["game"]
            self._players = restored["players"]
            self._match = restored["match"]
            self._dart_history = restored["dart_history"]
            self._turn_history = restored["turn_history"]
            self._current_turn_darts = restored["current_turn_darts"]
            self._undo_count += 1
            return {
                "ok": True,
                "state": {
                    **asdict(self._score),
                    **self.match_snapshot_locked(),
                },
            }

    def _finalize_turn_locked(self, player_name: str, reason: str) -> None:
        if not self._current_turn_darts:
            return
        turn_total = sum(int(item.get("applied_points", 0)) for item in self._current_turn_darts)
        self._turn_history.append(
            {
                "turn_id": len(self._turn_history) + 1,
                "set": self._match.set_number,
                "leg": self._match.leg_number,
                "turn": self._match.turn_number,
                "player": player_name,
                "darts": copy.deepcopy(self._current_turn_darts),
                "turn_total": turn_total,
                "reason": reason,
                "timestamp": _utc_now(),
            }
        )

    def _apply_throw_locked(self, result: ScoreResult, x_mm: float | None, y_mm: float | None, source: str) -> tuple[int, str]:
        player_idx = self._match.current_player_index
        player_name = self._players[player_idx].name
        dart_no = self._match.darts_in_turn + 1
        leg_no = self._match.leg_number
        set_no = self._match.set_number
        turn_no = self._match.turn_number

        if self._game.game == CRICKET_GAME:
            resolution = self._apply_cricket_throw_locked(result)
        else:
            resolution = self._apply_x01_throw_locked(result)

        note = "Scored (Shanghai mode)" if self._game.game == SHANGHAI_GAME else resolution.note

        dart_event = {
            "id": len(self._dart_history) + 1,
            "set": set_no,
            "leg": leg_no,
            "turn": turn_no,
            "dart": dart_no,
            "player": player_name,
            "bed": result.bed,
            "number": result.number,
            "raw_points": result.points,
            "applied_points": resolution.applied_points,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "source": source,
            "note": note,
            "timestamp": _utc_now(),
        }
        self._dart_history.append(dart_event)
        self._current_turn_darts.append(dart_event)

        self._score = ScoreState(
            points=resolution.applied_points,
            bed=result.bed,
            number=result.number,
            x_mm=x_mm,
            y_mm=y_mm,
            source=source,
            updated_at=_utc_now(),
        )
        self._match.last_note = note

        if resolution.leg_reset:
            self._finalize_turn_locked(player_name, note)
            return resolution.applied_points, note

        self._match.darts_in_turn += 1
        if resolution.end_turn or self._match.darts_in_turn >= 3:
            self._finalize_turn_locked(player_name, note)
            self._advance_turn_locked()

        return resolution.applied_points, note

    def update_from_result(self, result: ScoreResult, x_mm: float, y_mm: float, source: str) -> None:
        with self._lock:
            self._push_undo_snapshot_locked()
            self._apply_throw_locked(result=result, x_mm=x_mm, y_mm=y_mm, source=source)

    def update_from_point(self, x_mm: float, y_mm: float, source: str) -> ScoreResult:
        result = score_point(x_mm, y_mm)
        with self._lock:
            self._push_undo_snapshot_locked()
            self._apply_throw_locked(result=result, x_mm=x_mm, y_mm=y_mm, source=source)
        return result

    def update_manual(self, points: int, bed: str, source: str = "manual") -> None:
        result = ScoreResult(
            points=int(points),
            bed=bed,
            number=None,
            radius_mm=0.0,
            angle_deg=0.0,
        )
        with self._lock:
            self._push_undo_snapshot_locked()
            self._apply_throw_locked(result=result, x_mm=None, y_mm=None, source=source)

    def _build_stats_locked(self) -> dict[str, Any]:
        player_stats: dict[str, dict[str, Any]] = {}
        for player in self._players:
            player_stats[player.name] = {
                "darts_thrown": 0,
                "turns_played": 0,
                "total_applied_points": 0,
                "average_per_dart": 0.0,
                "average_per_turn": 0.0,
                "highest_dart": 0,
                "highest_turn": 0,
                "busts": 0,
                "checkouts": 0,
            }

        for dart in self._dart_history:
            p = player_stats[dart["player"]]
            p["darts_thrown"] += 1
            p["total_applied_points"] += int(dart["applied_points"])
            p["highest_dart"] = max(p["highest_dart"], int(dart["applied_points"]))
            if dart["note"] == "Bust":
                p["busts"] += 1
            if "Checkout" in dart["note"] or "leg won" in dart["note"].lower():
                p["checkouts"] += 1

        for turn in self._turn_history:
            p = player_stats[turn["player"]]
            p["turns_played"] += 1
            p["highest_turn"] = max(p["highest_turn"], int(turn["turn_total"]))

        for stats in player_stats.values():
            darts = stats["darts_thrown"]
            turns = stats["turns_played"]
            total = stats["total_applied_points"]
            stats["average_per_dart"] = round(total / darts, 2) if darts else 0.0
            stats["average_per_turn"] = round(total / turns, 2) if turns else 0.0

        total_points = sum(int(item["applied_points"]) for item in self._dart_history)
        total_darts = len(self._dart_history)
        total_turns = len(self._turn_history)

        return {
            "match": {
                "total_darts": total_darts,
                "total_turns": total_turns,
                "total_points": total_points,
                "average_per_dart": round(total_points / total_darts, 2) if total_darts else 0.0,
                "average_per_turn": round(total_points / total_turns, 2) if total_turns else 0.0,
                "undo_count": self._undo_count,
            },
            "players": player_stats,
        }

    def history_snapshot_locked(self) -> dict[str, Any]:
        return {
            "darts": copy.deepcopy(self._dart_history[-120:]),
            "turns": copy.deepcopy(self._turn_history[-60:]),
        }

    def match_snapshot_locked(self) -> dict[str, Any]:
        return {
            "game": self.game_snapshot_locked(),
            "match": asdict(self._match),
            "players": [asdict(p) for p in self._players],
            "current_player": self._players[self._match.current_player_index].name,
            "history": self.history_snapshot_locked(),
            "stats": self._build_stats_locked(),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **asdict(self._score),
                **self.match_snapshot_locked(),
            }
