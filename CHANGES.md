# Backend Update — Changelog

## Latest: Database wired into the bot

- `bot/main.py` now calls `db.init_db()` on startup
- User messages are saved to the SQLite conversation memory
- A default placeholder character is auto-created if none exists
- `/start` also creates/updates the user row in the database

**Still not implemented:**
- Roleplay LLM (Grok) integration
- Image generation (AI Horde)
- Character selection / creation UI
- Checkpoints commands (`/save`, `/load`)

The bot will reply with a message confirming the message was saved to memory, but it does **not** yet generate roleplay replies or images.

---

## Database layer (`bot/db/`)

### Tables
- `users` — Telegram users, credits, active character, ban/admin flags
- `characters` — Character cards (built-in or user-created)
- `conversations` — One thread per (user + character)
- `messages` — Conversation memory
- `checkpoints` — Named save points
- `credit_transactions` — Credit audit log

### Key functions
- `init_db()`, `upsert_user()`, `get_or_create_conversation()`, `add_message()`, `get_recent_messages()`
- `create_character()`, `list_characters_for_user()`
- `create_checkpoint()`, `load_checkpoint_messages()`
- `adjust_credits()`, `get_credits()`
