"""SQLite-backed persistence for chat conversations and messages.

Kept intentionally small and dependency-free (Python's stdlib `sqlite3`),
so it drops into the existing FastAPI backend without a new container.
The database file lives under the backend data directory.

Schema
------
conversations(id TEXT PK, title TEXT, created_at TEXT, updated_at TEXT)
messages(id TEXT PK, conversation_id TEXT FK, role TEXT, content TEXT,
         sources TEXT(json), reflection TEXT, created_at TEXT)
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from backend.core import config

DB_PATH = os.path.join(config.DATA_DIR, "chat.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _connect() -> sqlite3.Connection:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                sources         TEXT,
                reflection      TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conv "
            "ON messages (conversation_id, created_at)"
        )


# ── Conversations ────────────────────────────────────────────────

def create_conversation(title: str = "Nouvelle conversation") -> dict:
    cid = _new_id()
    ts = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (cid, title, ts, ts),
        )
    return {"id": cid, "title": title, "created_at": ts, "updated_at": ts}


def list_conversations() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conversation_id: str) -> dict | None:
    with _connect() as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conv is None:
            return None
        msgs = conn.execute(
            "SELECT id, role, content, sources, reflection, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()

    return {
        **dict(conv),
        "messages": [_row_to_message(m) for m in msgs],
    }


def rename_conversation(conversation_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), conversation_id),
        )


def delete_conversation(conversation_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
    return cur.rowcount > 0


# ── Messages ─────────────────────────────────────────────────────

def _row_to_message(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "reflection": row["reflection"],
        "created_at": row["created_at"],
    }


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    reflection: str | None = None,
) -> dict:
    """Insert a message and bump the parent conversation's updated_at."""
    mid = _new_id()
    ts = _now()
    sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages "
            "(id, conversation_id, role, content, sources, reflection, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, conversation_id, role, content, sources_json, reflection, ts),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (ts, conversation_id),
        )
    return {
        "id": mid,
        "role": role,
        "content": content,
        "sources": sources or [],
        "reflection": reflection,
        "created_at": ts,
    }


def conversation_exists(conversation_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    return row is not None
