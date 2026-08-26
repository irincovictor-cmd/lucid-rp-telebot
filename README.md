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
| Bot Framework          | `python-telegram-bot` or `aiogram` | Asynchronous, well-maintained |
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
- [ ] Project structure & virtual environment
- [ ] Telegram Bot Token setup
- [ ] AI Horde account + API key
- [ ] Basic "Hello World" bot

### Phase 1 – Core Chat (Week 1)
- [ ] Grok integration for roleplay
- [ ] Character system (JSON-based)
- [ ] Conversation memory (short-term)
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
- [ ] Persistent memory (SQLite)
- [ ] Checkpoint / save & load system
- [ ] Simple credit/energy system
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

## Project Structure (Planned)

```
lucid-rp-telebot/
├── bot/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── handlers/               # Command & message handlers
│   ├── services/
│   │   ├── llm.py              # Grok / roleplay logic
│   │   ├── image.py            # AI Horde integration
│   │   └── memory.py           # Conversation & character memory
│   ├── models/                 # Database models
│   └── utils/
├── characters/                 # Default character cards (JSON)
├── prompts/                    # System prompts & templates
├── data/                       # SQLite database (gitignored)
├── .env.example
├── requirements.txt
├── README.md
└── docs/
    ├── ROADMAP.md
    ├── SETUP.md
    └── API_NOTES.md
```

---

## Getting Started (Coming Soon)

Detailed setup instructions will be added in Phase 0.

For now:
1. Clone this repository
2. Create a virtual environment
3. Install dependencies (once `requirements.txt` is ready)
4. Copy `.env.example` → `.env` and fill in tokens
5. Run the bot

---

## Important Notes

- **Zero Budget**: All current tools are free. Paid upgrades (better image providers, paid hosting, etc.) are optional later.
- **NSFW Content**: This bot is designed for adult roleplay and image generation. Use responsibly and only with consenting adult users.
- **AI Horde**: Free community service. Be respectful of workers — avoid spamming high-volume requests.
- **Legal**: You are responsible for complying with Telegram’s Terms of Service and local laws regarding adult content.

---

## Contributing / Development

This is currently a personal side project. Development is driven by the repository owner with AI assistance (Grok).

---

## License

TBD (will be decided later — likely MIT or similar for the code)

---

**Status**: Early development – Documentation phase  
**Last Updated**: August 26, 2026
