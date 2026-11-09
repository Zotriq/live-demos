"""SQLite storage: conversations, message history, processed message ids, bookings."""

from __future__ import annotations

import datetime as dt
import json
import secrets
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (wamid TEXT PRIMARY KEY, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
    phone      TEXT PRIMARY KEY,
    name       TEXT,
    mode       TEXT NOT NULL DEFAULT 'bot',      -- bot | human
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    phone   TEXT NOT NULL,
    role    TEXT NOT NULL,                       -- user | assistant | tool
    content TEXT NOT NULL,                       -- JSON-encoded OpenAI-style message
    at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    code      TEXT PRIMARY KEY,
    phone     TEXT NOT NULL,
    name      TEXT NOT NULL,
    service   TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at   TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'booked'
);
"""

HISTORY_LIMIT = 20


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # --- dedupe: Meta re-delivers webhooks, so every message id is processed once ---
    def first_time(self, wamid: str) -> bool:
        try:
            self.conn.execute("INSERT INTO processed VALUES (?, ?)", (wamid, now_iso()))
            return True
        except sqlite3.IntegrityError:
            return False

    # --- conversations ---
    def conversation(self, phone: str, name: str | None = None) -> sqlite3.Row:
        self.conn.execute(
            "INSERT INTO conversations (phone, name, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(phone) DO UPDATE SET name = COALESCE(excluded.name, name), updated_at = excluded.updated_at",
            (phone, name, now_iso()),
        )
        return self.conn.execute("SELECT * FROM conversations WHERE phone = ?", (phone,)).fetchone()

    def set_mode(self, phone: str, mode: str) -> bool:
        return self.conn.execute("UPDATE conversations SET mode = ? WHERE phone = ?", (mode, phone)).rowcount == 1

    def waiting_for_human(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM conversations WHERE mode = 'human' ORDER BY updated_at")]

    # --- history (kept short: the model only needs recent context) ---
    def add(self, phone: str, message: dict) -> None:
        self.conn.execute(
            "INSERT INTO messages (phone, role, content, at) VALUES (?, ?, ?, ?)",
            (phone, message["role"], json.dumps(message), now_iso()),
        )

    def history(self, phone: str, limit: int = HISTORY_LIMIT) -> list[dict]:
        rows = self.conn.execute(
            "SELECT content FROM messages WHERE phone = ? ORDER BY id DESC LIMIT ?", (phone, limit)
        ).fetchall()
        msgs = [json.loads(r["content"]) for r in reversed(rows)]
        # Never start the window on an orphaned tool result or an assistant turn whose tool results were cut off.
        while msgs and (msgs[0]["role"] == "tool" or (msgs[0]["role"] == "assistant" and msgs[0].get("tool_calls"))):
            msgs.pop(0)
        return msgs

    # --- bookings ---
    def booked_ranges(self, day: dt.date) -> list[tuple[dt.datetime, dt.datetime]]:
        rows = self.conn.execute(
            "SELECT starts_at, ends_at FROM bookings WHERE status = 'booked' AND substr(starts_at, 1, 10) = ?",
            (day.isoformat(),),
        )
        return [(dt.datetime.fromisoformat(r["starts_at"]), dt.datetime.fromisoformat(r["ends_at"])) for r in rows]

    def insert_booking(self, phone: str, name: str, service: str, start: dt.datetime, end: dt.datetime) -> str:
        code = secrets.token_hex(3).upper()
        self.conn.execute(
            "INSERT INTO bookings (code, phone, name, service, starts_at, ends_at) VALUES (?, ?, ?, ?, ?, ?)",
            (code, phone, name, service, start.isoformat(), end.isoformat()),
        )
        return code

    def bookings_for(self, phone: str, after: dt.datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM bookings WHERE phone = ? AND status = 'booked' AND starts_at >= ? ORDER BY starts_at",
            (phone, after.isoformat()),
        ).fetchall()

    def cancel_booking(self, phone: str, code: str) -> sqlite3.Row | None:
        row = self.conn.execute(
            "SELECT * FROM bookings WHERE code = ? AND phone = ? AND status = 'booked'", (code.upper(), phone)
        ).fetchone()
        if row:
            self.conn.execute("UPDATE bookings SET status = 'cancelled' WHERE code = ?", (row["code"],))
        return row
