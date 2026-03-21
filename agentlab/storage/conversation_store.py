"""SQLite-backed store for playground conversation threads.

Uses only the Python stdlib ``sqlite3`` module — no additional dependencies.

Schema
------
conversations
    id          TEXT  PRIMARY KEY
    agent_name  TEXT  NOT NULL
    agent_snapshot TEXT  (JSON)
    title       TEXT
    created_at  TEXT
    updated_at  TEXT

messages
    id              INTEGER  PRIMARY KEY AUTOINCREMENT
    conversation_id TEXT     NOT NULL  REFERENCES conversations(id)
    seq             INTEGER  NOT NULL
    role            TEXT     NOT NULL   ('user' | 'assistant')
    content         TEXT
    trace           TEXT     (JSON list of TraceEntry dicts)
    created_at      TEXT
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentlab.models.schemas import (
    AgentConfig,
    ConversationMessage,
    ConversationRecord,
)

_DDL = """
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    agent_snapshot  TEXT,
    task_id         TEXT,
    title           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT    NOT NULL,
    seq             INTEGER NOT NULL,
    role            TEXT    NOT NULL,
    content         TEXT,
    trace           TEXT    DEFAULT '[]',
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, seq);
CREATE INDEX IF NOT EXISTS idx_conv_agent    ON conversations(agent_name);
CREATE INDEX IF NOT EXISTS idx_conv_updated  ON conversations(updated_at DESC);
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Thin SQLite wrapper for playground conversations and messages.

    A single ``.db`` file lives alongside the file-based ``Store`` artefacts::

        <root>/
            agents/
            runs/
            conversations.db   ← this class manages this file
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._init()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)
            # Migration: add task_id if missing (existing DBs)
            try:
                cursor = conn.execute("PRAGMA table_info(conversations)")
                columns = [row[1] for row in cursor.fetchall()]
                if "task_id" not in columns:
                    conn.execute("ALTER TABLE conversations ADD COLUMN task_id TEXT")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(self, record: ConversationRecord) -> ConversationRecord:
        now = _utcnow_iso()
        snapshot = record.agent_snapshot.model_dump_json() if record.agent_snapshot else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations (id, agent_name, agent_snapshot, task_id, title, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record.id, record.agent_name, snapshot, record.task_id, record.title, now, now),
            )
        record.created_at = datetime.fromisoformat(now)
        record.updated_at = record.created_at
        return record

    def get_conversation(self, conv_id: str) -> ConversationRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_conv(row)

    def list_conversations(self, agent_name: str | None = None) -> list[ConversationRecord]:
        sql = "SELECT * FROM conversations"
        params: tuple[Any, ...] = ()
        if agent_name:
            sql += " WHERE agent_name = ?"
            params = (agent_name,)
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_conv(r) for r in rows]

    def update_conversation_title(self, conv_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, _utcnow_iso(), conv_id),
            )

    def touch_conversation(self, conv_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_utcnow_iso(), conv_id),
            )

    def delete_conversation(self, conv_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(self, msg: ConversationMessage) -> ConversationMessage:
        now = _utcnow_iso()
        trace_json = json.dumps(msg.trace)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, seq, role, content, trace, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (msg.conversation_id, msg.seq, msg.role, msg.content, trace_json, now),
            )
            msg.id = cur.lastrowid
        msg.created_at = datetime.fromisoformat(now)
        self.touch_conversation(msg.conversation_id)
        return msg

    def get_messages(self, conv_id: str) -> list[ConversationMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq",
                (conv_id,),
            ).fetchall()
        return [self._row_to_msg(r) for r in rows]

    def next_seq(self, conv_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM messages WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()
        return (row[0] or 0) + 1

    # ------------------------------------------------------------------
    # Row mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_conv(row: sqlite3.Row) -> ConversationRecord:
        snapshot = None
        if row["agent_snapshot"]:
            try:
                snapshot = AgentConfig.model_validate_json(row["agent_snapshot"])
            except Exception:
                pass
        task_id = row["task_id"] if "task_id" in row.keys() else None
        return ConversationRecord(
            id=row["id"],
            agent_name=row["agent_name"],
            agent_snapshot=snapshot,
            task_id=task_id,
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_msg(row: sqlite3.Row) -> ConversationMessage:
        trace: list[dict] = []
        if row["trace"]:
            try:
                trace = json.loads(row["trace"])
            except Exception:
                pass
        return ConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            seq=row["seq"],
            role=row["role"],
            content=row["content"],
            trace=trace,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
