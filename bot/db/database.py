"""
Database access layer for Lucid RP Telebot.

Thin wrapper around sqlite3 with:
- a single shared connection (WAL mode, safe for asyncio single-process use)
- schema initialization + light migrations
- CRUD helpers for users, characters, conversations, messages,
  checkpoints, credit transactions, and scene state (heat/rapport/location)
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "lucid.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

DEFAULT_LOCATION = "rooftop bar after midnight"
DEFAULT_OUTFIT = "low-cut elegant evening top, thin glasses"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


def _migrate_scene_columns(conn: sqlite3.Connection) -> None:
    """Add scene-state columns on older DBs created before this feature."""
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    alters = []
    if "heat" not in cols:
        alters.append(
            "ALTER TABLE conversations ADD COLUMN heat INTEGER NOT NULL DEFAULT 0"
        )
    if "rapport" not in cols:
        alters.append(
            "ALTER TABLE conversations ADD COLUMN rapport INTEGER NOT NULL DEFAULT 15"
        )
    if "location" not in cols:
        alters.append(
            "ALTER TABLE conversations ADD COLUMN location TEXT NOT NULL DEFAULT 'rooftop bar after midnight'"
        )
    if "outfit" not in cols:
        alters.append(
            "ALTER TABLE conversations ADD COLUMN outfit TEXT NOT NULL DEFAULT 'low-cut elegant evening top, thin glasses'"
        )
    if "scene_notes" not in cols:
        alters.append(
            "ALTER TABLE conversations ADD COLUMN scene_notes TEXT NOT NULL DEFAULT ''"
        )
    for sql in alters:
        conn.execute(sql)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    _migrate_scene_columns(conn)
    conn.commit()


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_active_at = datetime('now')
            """,
            (user_id, username, first_name),
        )


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def set_active_character(user_id: int, character_id: Optional[int]) -> None:
    with tx() as conn:
        conn.execute(
            "UPDATE users SET active_character_id = ? WHERE user_id = ?",
            (character_id, user_id),
        )


def set_banned(user_id: int, banned: bool) -> None:
    with tx() as conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if banned else 0, user_id),
        )


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

def create_character(
    name: str,
    profile_json: str | dict,
    owner_id: Optional[int] = None,
    short_desc: Optional[str] = None,
    is_public: bool = False,
    avatar_file_id: Optional[str] = None,
) -> int:
    if isinstance(profile_json, dict):
        profile_json = json.dumps(profile_json)
    with tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO characters (owner_id, name, short_desc, profile_json, avatar_file_id, is_public)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (owner_id, name, short_desc, profile_json, avatar_file_id, 1 if is_public else 0),
        )
        return cur.lastrowid


def get_character(character_id: int) -> Optional[dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM characters WHERE character_id = ?", (character_id,)).fetchone()
    return dict(row) if row else None


def list_characters_for_user(user_id: int) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM characters
        WHERE owner_id IS NULL OR owner_id = ? OR is_public = 1
        ORDER BY owner_id IS NULL DESC, name ASC
        """,
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Conversations & Messages
# ---------------------------------------------------------------------------

def get_or_create_conversation(user_id: int, character_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT conversation_id FROM conversations WHERE user_id = ? AND character_id = ?",
        (user_id, character_id),
    ).fetchone()
    if row:
        return row["conversation_id"]
    with tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO conversations (user_id, character_id, heat, rapport, location, outfit, scene_notes)
            VALUES (?, ?, 0, 15, ?, ?, '')
            """,
            (user_id, character_id, DEFAULT_LOCATION, DEFAULT_OUTFIT),
        )
        return cur.lastrowid


def get_scene_state(conversation_id: int) -> dict[str, Any]:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT heat, rapport, location, outfit, scene_notes
        FROM conversations WHERE conversation_id = ?
        """,
        (conversation_id,),
    ).fetchone()
    if not row:
        return {
            "heat": 0,
            "rapport": 15,
            "location": DEFAULT_LOCATION,
            "outfit": DEFAULT_OUTFIT,
            "scene_notes": "",
        }
    return {
        "heat": int(row["heat"] or 0),
        "rapport": int(row["rapport"] or 15),
        "location": row["location"] or DEFAULT_LOCATION,
        "outfit": row["outfit"] or DEFAULT_OUTFIT,
        "scene_notes": row["scene_notes"] or "",
    }


def update_scene_state(
    conversation_id: int,
    *,
    heat: Optional[int] = None,
    rapport: Optional[int] = None,
    location: Optional[str] = None,
    outfit: Optional[str] = None,
    scene_notes: Optional[str] = None,
) -> dict[str, Any]:
    current = get_scene_state(conversation_id)
    new_heat = current["heat"] if heat is None else max(0, min(100, int(heat)))
    new_rapport = current["rapport"] if rapport is None else max(0, min(100, int(rapport)))
    new_loc = current["location"] if location is None else (location.strip() or current["location"])
    new_outfit = current["outfit"] if outfit is None else (outfit.strip() or current["outfit"])
    new_notes = current["scene_notes"] if scene_notes is None else scene_notes

    with tx() as conn:
        conn.execute(
            """
            UPDATE conversations SET
                heat = ?,
                rapport = ?,
                location = ?,
                outfit = ?,
                scene_notes = ?,
                updated_at = datetime('now')
            WHERE conversation_id = ?
            """,
            (new_heat, new_rapport, new_loc, new_outfit, new_notes, conversation_id),
        )
    return {
        "heat": new_heat,
        "rapport": new_rapport,
        "location": new_loc,
        "outfit": new_outfit,
        "scene_notes": new_notes,
    }


def reset_scene_state(conversation_id: int) -> dict[str, Any]:
    """Reset to Aria intro defaults (used by /new)."""
    return update_scene_state(
        conversation_id,
        heat=0,
        rapport=15,
        location=DEFAULT_LOCATION,
        outfit=DEFAULT_OUTFIT,
        scene_notes="",
    )


def add_message(conversation_id: int, role: str, content: str) -> int:
    assert role in ("user", "assistant", "system")
    with tx() as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE conversation_id = ?",
            (conversation_id,),
        )
        return cur.lastrowid


def get_recent_messages(conversation_id: int, limit: int = 20) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT role, content, created_at FROM messages
        WHERE conversation_id = ?
        ORDER BY message_id DESC
        LIMIT ?
        """,
        (conversation_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_conversation(conversation_id: int) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE conversation_id = ?",
            (conversation_id,),
        )
    reset_scene_state(conversation_id)


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------

def create_checkpoint(conversation_id: int, label: str) -> Optional[int]:
    conn = get_conn()
    last = conn.execute(
        "SELECT MAX(message_id) AS mid FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    if last is None or last["mid"] is None:
        return None
    with tx() as conn:
        cur = conn.execute(
            "INSERT INTO checkpoints (conversation_id, label, up_to_message_id) VALUES (?, ?, ?)",
            (conversation_id, label, last["mid"]),
        )
        return cur.lastrowid


def list_checkpoints(conversation_id: int) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM checkpoints WHERE conversation_id = ? ORDER BY created_at DESC",
        (conversation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_checkpoint_messages(checkpoint_id: int) -> list[dict[str, Any]]:
    conn = get_conn()
    cp = conn.execute(
        "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
    ).fetchone()
    if cp is None:
        return []
    rows = conn.execute(
        """
        SELECT role, content, created_at FROM messages
        WHERE conversation_id = ? AND message_id <= ?
        ORDER BY message_id ASC
        """,
        (cp["conversation_id"], cp["up_to_message_id"]),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------

def get_credits(user_id: int) -> int:
    user = get_user(user_id)
    return user["credits"] if user else 0


def adjust_credits(user_id: int, amount: int, reason: str) -> int:
    with tx() as conn:
        row = conn.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError(f"No such user: {user_id}")
        new_balance = row["credits"] + amount
        if new_balance < 0:
            raise ValueError("Insufficient credits")
        conn.execute("UPDATE users SET credits = ? WHERE user_id = ?", (new_balance, user_id))
        conn.execute(
            "INSERT INTO credit_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, amount, reason),
        )
        return new_balance
