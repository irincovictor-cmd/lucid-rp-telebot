-- Lucid RP Telebot — Database Schema
-- SQLite. Run via bot/db/database.py:init_db()

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- users: one row per Telegram user
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id              INTEGER PRIMARY KEY,          -- Telegram user id
    username             TEXT,
    first_name           TEXT,
    credits              INTEGER NOT NULL DEFAULT 100,
    active_character_id  INTEGER,                      -- FK to characters, nullable
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    last_active_at       TEXT NOT NULL DEFAULT (datetime('now')),
    is_banned            INTEGER NOT NULL DEFAULT 0,   -- 0/1 boolean
    is_admin             INTEGER NOT NULL DEFAULT 0,   -- 0/1 boolean
    FOREIGN KEY (active_character_id) REFERENCES characters(character_id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------------
-- characters: character cards (built-in or user-created)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS characters (
    character_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        INTEGER,                           -- NULL = built-in / global
    name            TEXT NOT NULL,
    short_desc      TEXT,                              -- one-liner for menus
    profile_json    TEXT NOT NULL,                     -- personality, tone, backstory, appearance, etc.
    avatar_file_id  TEXT,                              -- optional Telegram file_id
    is_public       INTEGER NOT NULL DEFAULT 0,        -- 0/1
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_characters_owner ON characters(owner_id);

-- ---------------------------------------------------------------------------
-- conversations: one thread per (user, character) pair
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    character_id    INTEGER NOT NULL,
    title           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(character_id) ON DELETE CASCADE,
    UNIQUE(user_id, character_id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);

-- ---------------------------------------------------------------------------
-- messages: individual turns (the conversation memory)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- ---------------------------------------------------------------------------
-- checkpoints: named save points (/save, /load)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  INTEGER NOT NULL,
    label            TEXT NOT NULL,
    up_to_message_id INTEGER NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    FOREIGN KEY (up_to_message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- credit_transactions: audit log for the credit/energy system
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_transactions (
    transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    amount          INTEGER NOT NULL,               -- negative = spend, positive = grant
    reason          TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_credit_tx_user ON credit_transactions(user_id, created_at);
