# Lucid RP Telebot

**Zero-budget Telegram bot for 18+ AI roleplay + NSFW image generation**  
Inspired by LucidDreams-style experiences.

> ⚠️ **Adult Content Only (18+)**  
> This project is strictly for adult users. All content is fictional.

---

## Project Overview

A Telegram bot that lets users:
- Engage in immersive AI-driven roleplay with customizable characters
- Generate NSFW images of characters and scenes on demand
- Maintain conversation memory and character consistency
- Create and save their own characters
- Use a simple credit/energy system (free for now)

**Core Philosophy**: Fully free to run and develop. No paid APIs required to get started.

---

## Tech Stack (All Free)

| Component              | Tool                          | Notes |
|------------------------|-------------------------------|-------|
| Bot Framework          | `python-telegram-bot`         | Asynchronous, well-maintained |
| Roleplay LLM           | **AI Horde (text)**           | Free community workers, NSFW-friendly |
| Image Generation       | **AI Horde (image)**          | Planned — same API key |
| Database               | SQLite                        | Zero cost |
| Hosting                | Local / free tier later       | Start local |
| Version Control        | GitHub                        | This repository |
| Language               | Python 3.11+                  | |

---

## Current Status (Updated Aug 27, 2026)

### Working now
- [x] Telegram bot (`/start`, `/help`, `/new`)
- [x] SQLite database (users, characters, conversations, messages, checkpoints, credits)
- [x] Conversation memory
- [x] Roleplay replies via **AI Horde text generation**
- [x] Default character (Aria)
- [x] Shorter-reply + consistency prompt tuning

### Not working yet
- [ ] Image generation
- [ ] Multiple characters / selection menu
- [ ] User-created characters
- [ ] Checkpoint commands wired to chat (`/save`, `/load`)
- [ ] Age gate, rate limits, admin tools

---

## Features Roadmap

### Phase 0 – Project Setup
- [x] Create GitHub repository
- [x] Project structure
- [x] Basic bot (`/start`, `/help`)
- [x] Database layer (schema + CRUD)
- [x] Telegram Bot Token + AI Horde key setup

### Phase 1 – Core Chat
- [x] LLM integration (switched from paid xAI → free AI Horde text)
- [x] Conversation memory (DB-backed)
- [x] Default character
- [x] `/new` to clear memory
- [x] Prompt tuning for shorter, more consistent replies
- [ ] Stronger character system
- [ ] 18+ age gate

### Phase 2 – Image Generation
- [ ] AI Horde image API integration
- [ ] `/img` or natural-language image requests
- [ ] Prompt rewriting from scene context
- [ ] Send images back to Telegram
- [ ] Queue / waiting messages

### Phase 3 – Characters & Persistence
- [ ] Multiple characters + selection menu
- [ ] User character creation
- [x] Persistent memory foundation
- [x] Checkpoint foundation (DB ready)
- [ ] Wire `/save`, `/load`, `/checkpoints`

### Phase 4 – Polish
- [ ] Error handling & rate limiting
- [ ] Better Telegram UI (buttons)
- [ ] Logging / admin commands

### Phase 5 – Deploy
- [ ] Free hosting
- [ ] Private testing

---

## Project Structure

```
lucid-rp-telebot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point + handlers
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py       # CRUD layer
│   │   └── schema.sql        # SQLite schema
│   └── services/
│       ├── __init__.py
│       └── llm.py            # AI Horde text roleplay
├── data/                     # lucid.db (gitignored)
├── docs/
│   ├── ROADMAP.md
│   ├── SETUP.md
│   └── API_NOTES.md
├── .env.example
├── .gitignore
├── requirements.txt
├── CHANGES.md
└── README.md
```

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

Required in `.env`:
```env
TELEGRAM_BOT_TOKEN=...
AI_HORDE_API_KEY=...          # same key for text + future images
```

Optional:
```env
XAI_API_KEY=...               # no longer used for roleplay
XAI_MODEL=grok-4.6
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help`  | Help text |
| `/new`   | Clear conversation memory and start fresh |

Just send any normal message to roleplay.

---

## Notes

- **Zero budget**: AI Horde is free (community workers). Quality and speed vary.
- **NSFW**: Designed for adult roleplay. Use responsibly.
- **AI Horde**: Be respectful of volunteer workers; avoid spam.

---

**Status**: Phase 1 in progress — roleplay via AI Horde is live; image gen next  
**Last Updated**: August 27, 2026
