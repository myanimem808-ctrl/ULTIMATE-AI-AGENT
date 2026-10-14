from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH, ensure_directories

_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AppStore:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        ensure_directories()
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                server_name TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

    def add_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("Unsupported message role")
        with _LOCK, self._connect() as con:
            con.execute("INSERT INTO messages(role, content, created_at) VALUES(?,?,?)",
                        (role, content[:100000], now_iso()))
            # Keep recent context bounded, retain at most 500 dashboard messages.
            con.execute("DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT 500)")

    def history(self, limit: int = 12) -> list[dict[str, str]]:
        limit = max(1, min(int(limit), 50))
        with self._connect() as con:
            rows = con.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit * 2,)).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)
                if row["role"] in {"user", "assistant"}]

    def recent_messages(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("SELECT id, role, content, created_at FROM messages ORDER BY id DESC LIMIT ?",
                               (max(1, min(limit, 500)),)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def clear_messages(self) -> None:
        with _LOCK, self._connect() as con:
            con.execute("DELETE FROM messages")

    def create_approval(self, server_name: str, tool_name: str, display_name: str,
                        arguments: dict[str, Any]) -> str:
        approval_id = uuid.uuid4().hex
        timestamp = now_iso()
        with _LOCK, self._connect() as con:
            con.execute("""INSERT INTO approvals(id, server_name, tool_name, display_name,
                         arguments_json, status, created_at, updated_at) VALUES(?,?,?,?,?,'pending',?,?)""",
                        (approval_id, server_name, tool_name, display_name,
                         json.dumps(arguments, ensure_ascii=False), timestamp, timestamp))
        return approval_id

    def approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["arguments"] = json.loads(item.pop("arguments_json"))
        item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
        return item

    def pending_approvals(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("SELECT id FROM approvals WHERE status='pending' ORDER BY created_at DESC LIMIT ?",
                               (limit,)).fetchall()
        return [item for row in rows if (item := self.approval(row["id"])) is not None]

    def finish_approval(self, approval_id: str, status: str, result: dict[str, Any]) -> None:
        if status not in {"approved", "denied", "failed"}:
            raise ValueError("Invalid approval status")
        with _LOCK, self._connect() as con:
            con.execute("UPDATE approvals SET status=?, result_json=?, updated_at=? WHERE id=? AND status='pending'",
                        (status, json.dumps(result, ensure_ascii=False), now_iso(), approval_id))

store = AppStore()
