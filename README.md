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
| Roleplay LLM           | Grok (xAI API)                | Strong uncensored roleplay capability |
| Image Generation       | **AI Horde**                  | Completely free, NSFW-friendly, open source |
| Database               | SQLite                        | Zero cost, easy to start |
| Hosting                | Local / Railway / Render / Fly.io free tier | Start local |
| Version Control        | GitHub                        | This repository |
| Language               | Python 3.11+                  | |

---

## Features Roadmap

### Phase 0 – Project Setup (Days 1–2)
- [x] Create GitHub repository
- [x] Project structure & virtual environment
- [x] Basic "Hello World" bot (`/start`, `/help`)
- [x] Database layer (schema + CRUD)
- [ ] Telegram Bot Token setup (you need to do this)
- [ ] AI Horde account + API key (you need to do this)

### Phase 1 – Core Chat (Week 1)
- [ ] Grok integration for roleplay
- [ ] Character system (JSON-based)
- [ ] Conversation memory (using the new DB layer)
- [ ] 18+ age gate on `/start`
- [ ] Basic commands (`/start`, `/help`, `/characters`)

### Phase 2 – Image Generation (Week 2)
- [ ] AI Horde API integration
- [ ] Image generation command / natural language trigger
- [ ] Prompt rewriting by LLM
- [ ] Negative prompt support
- [ ] Send images back to Telegram
- [ ] Queue status messages

### Phase 3 – Advanced Features (Week 3–4)
- [ ] Multiple characters + selection menu
- [ ] User character creation flow
- [x] Persistent memory (SQLite) — foundation done
- [x] Checkpoint / save & load system — foundation done
- [x] Simple credit/energy system — foundation done
- [ ] Better character consistency prompting

### Phase 4 – Polish (Week 5–6)
- [ ] Improved error handling
- [ ] Rate limiting & anti-spam
- [ ] Logging system
- [ ] Admin commands
- [ ] Better Telegram UI (buttons, menus)
- [ ] Documentation improvements

### Phase 5 – Deployment & Testing (Week 7–8)
- [ ] Deploy to free hosting
- [ ] Private beta testing
- [ ] Bug fixes & feedback loop
- [ ] Optional second image provider as fallback

---

## Current Project Structure

```
lucid-rp-telebot/
├── bot/
│   ├── __init__.py
│   ├── main.py                 # Entry point (working basic bot)
│   └── db/
│       ├── __init__.py
│       ├── database.py         # Full CRUD layer
│       └── schema.sql          # SQLite schema
├── data/                       # Created at runtime (lucid.db) — gitignored
├── docs/
│   ├── ROADMAP.md
│   ├── SETUP.md
│   └── API_NOTES.md
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Database Layer (just added)

The `bot/db/` package provides:

| Table | Purpose |
|-------|--------|
| `users` | Telegram users, credits, active character, ban/admin flags |
| `characters` | Character cards (built-in or user-created) |
| `conversations` | One thread per (user + character) |
| `messages` | Full conversation memory |
| `checkpoints` | Named save points (`/save`, `/load`) |
| `credit_transactions` | Audit log for the credit system |

All access goes through `bot/db/database.py`. Call `init_db()` once on bot startup.

---

## Getting Started (How to run the bot)

### 1. Clone the repository
```bash
git clone https://github.com/irincovictor-cmd/lucid-rp-telebot.git
cd lucid-rp-telebot
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create your .env file
```bash
cp .env.example .env
```

Then open `.env` and add your tokens:
```env
TELEGRAM_BOT_TOKEN=your_token_from_BotFather
XAI_API_KEY=your_xai_key
AI_HORDE_API_KEY=0000000000
```

### 5. Run the bot
```bash
python -m bot.main
```

You should see `Bot is starting...` in the terminal.  
Open Telegram, find your bot, and send `/start`.

---

## Important Notes

- **Zero Budget**: All current tools are free. Paid upgrades are optional later.
- **NSFW Content**: This bot is designed for adult roleplay and image generation.
- **AI Horde**: Free community service. Be respectful of workers.
- **Legal**: You are responsible for complying with Telegram’s Terms of Service and local laws.

---

**Status**: Phase 0 – Basic bot + database layer ready  
**Last Updated**: August 26, 2026
