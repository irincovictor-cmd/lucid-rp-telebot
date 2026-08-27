# Lucid RP Telebot (HoneyChat)

**Zero-budget Telegram bot for 18+ AI roleplay + NSFW image generation**  
Inspired by LucidDreams-style experiences.

> ⚠️ **Adult Content Only (18+)**  
> This project is strictly for adult users. All content is fictional.

---

## Project Overview

A Telegram bot that lets users:
- Engage in immersive AI-driven roleplay with characters
- Get a proper scene intro (like Lucid Dreams)
- Press **Continue** to advance narrative beats without typing
- (Soon) Generate NSFW images tied to the scene

**Core Philosophy**: Free tools first. Paid APIs only if needed later.

---

## Tech Stack

| Component | Tool | Notes |
|-----------|------|-------|
| Bot Framework | `python-telegram-bot` | Async polling |
| Roleplay LLM | **OpenRouter** | Free models (`openrouter/free` default) |
| Image Generation | AI Horde | Planned — same free key |
| Database | SQLite | Users, characters, messages, checkpoints |
| Language | Python 3.11+ | |

---

## Current Status (Updated Aug 28, 2026)

### Working
- [x] Telegram bot (`/start`, `/help`, `/new`)
- [x] SQLite memory (users, characters, conversations, messages)
- [x] Roleplay via **OpenRouter**
- [x] Default character **Aria** + rooftop-bar scene intro
- [x] Bot welcome + character intro on `/start` and `/new`
- [x] **Continue ▶** button under replies (SpicyChat-style)
- [x] Prompt rules: short replies, no invented history, slow-burn pacing
- [x] Prompt rules: no scene-skip, match explicit vocabulary, location lock
- [x] Rate-limit handling + optional fallback model
- [x] Leak detection / retry on bad free-model output

### Not yet
- [ ] NSFW image generation (AI Horde)
- [ ] Multiple characters / selection menu
- [ ] User-created characters
- [ ] Checkpoint commands wired (`/save`, `/load`)
- [ ] Age gate, rate limits, admin tools

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Bot welcome + Aria scene intro |
| `/help` | How to use |
| `/new` | Clear memory and restart Aria intro |
| **Continue ▶** | Advance the scene without typing |

Just send normal messages to roleplay.

---

## Getting Started

```bash
git clone https://github.com/irincovictor-cmd/lucid-rp-telebot.git
cd lucid-rp-telebot
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens
python -m bot.main
```

### Required `.env`

```env
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openrouter/free
# optional:
OPENROUTER_FALLBACK_MODEL=openrouter/free
AI_HORDE_API_KEY=0000000000
```

Get OpenRouter key: https://openrouter.ai/keys  
Free models list: https://openrouter.ai/models?q=free

---

## Project Structure

```
lucid-rp-telebot/
├── bot/
│   ├── main.py              # Handlers, intro, Continue button
│   ├── db/
│   │   ├── database.py
│   │   └── schema.sql
│   └── services/
│       └── llm.py            # OpenRouter roleplay
├── docs/
│   ├── ROADMAP.md
│   ├── SETUP.md
│   └── API_NOTES.md
├── .env.example
├── requirements.txt
└── README.md
```

---

## Notes

- Free OpenRouter models vary in quality and rate limits. Prefer `openrouter/free`.
- AI Horde remains planned for **images**, not chat.
- xAI / Venice were tried/dropped for cost or fit reasons.

---

**Status**: Phase 1 — roleplay usable; image gen next  
**Last Updated**: August 28, 2026
