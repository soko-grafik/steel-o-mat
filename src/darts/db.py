import sqlite3
import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

DB_PATH = Path("config/darts.db")

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                name TEXT PRIMARY KEY,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type TEXT,
                variations TEXT,
                players TEXT,
                start_time TEXT,
                end_time TEXT,
                winner_name TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS throws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                player_name TEXT,
                set_num INTEGER,
                leg_num INTEGER,
                turn_num INTEGER,
                dart_num INTEGER,
                points INTEGER,
                bed TEXT,
                number INTEGER,
                x_mm REAL,
                y_mm REAL,
                timestamp TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(id)
            )
        """)

def get_setting(key: str, default: Any = None) -> Any:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        return default

def set_setting(key: str, value: Any):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )

def get_players() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT name FROM players ORDER BY name ASC")
        return [row[0] for row in cur.fetchall()]

def add_player(name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO players (name, created_at) VALUES (?, ?)",
            (name, _utc_now())
        )

def delete_player(name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM players WHERE name = ?", (name,))

def start_match(game_type: str, variations: list[str], players: list[str]) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO matches (game_type, variations, players, start_time) VALUES (?, ?, ?, ?)",
            (game_type, json.dumps(variations), json.dumps(players), _utc_now())
        )
        return cur.lastrowid

def end_match(match_id: int, winner_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE matches SET end_time = ?, winner_name = ? WHERE id = ?",
            (_utc_now(), winner_name, match_id)
        )

def record_throw(
    match_id: int,
    player_name: str,
    set_num: int,
    leg_num: int,
    turn_num: int,
    dart_num: int,
    points: int,
    bed: str,
    number: Optional[int],
    x_mm: Optional[float],
    y_mm: Optional[float]
):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT INTO throws (
                match_id, player_name, set_num, leg_num, turn_num, dart_num,
                points, bed, number, x_mm, y_mm, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match_id, player_name, set_num, leg_num, turn_num, dart_num,
                points, bed, number, x_mm, y_mm, _utc_now()
            )
        )

def get_all_matches() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM matches ORDER BY id DESC")
        return [dict(row) for row in cur.fetchall()]

def get_match_throws(match_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM throws WHERE match_id = ? ORDER BY id ASC", (match_id,))
        return [dict(row) for row in cur.fetchall()]

def get_player_stats() -> list[dict[str, Any]]:
    # Simple aggregation for player stats
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT 
                player_name, 
                COUNT(*) as total_darts,
                SUM(points) as total_points,
                AVG(points) * 3 as avg_3_darts,
                (SELECT COUNT(*) FROM matches WHERE winner_name = throws.player_name) as matches_won
            FROM throws
            GROUP BY player_name
        """)
        return [dict(row) for row in cur.fetchall()]
