# Lucid RP Telebot (HoneyChat)

**Zero-budget Telegram bot for 18+ AI roleplay + NSFW image generation**  
Inspired by LucidDreams-style experiences.

> ⚠️ **Adult Content Only (18+)**

---

## Current Status (Updated Aug 31, 2026)

### Working
- [x] OpenRouter / optional DeepSeek roleplay + SQLite memory
- [x] Aria character + rooftop intro
- [x] **Continue** / **Change** / **Soft / Bold** buttons
- [x] **Scene state**: heat, rapport, location, outfit (locked + updated from chat)
- [x] Replies require actions + brief feeling/thought + atmosphere
- [x] Prompt: no scene-skip, explicit vocab match, location/outfit lock
- [x] Soft/Bold scene-aware (no generic interview lines)
- [x] Rate-limit / leak replies not stored in history
- [x] Local Aria art: `profile.png` = bot avatar; `intro_1–3` on `/start`
- [x] `/img` via AI Horde (free, can be slow)

### Not yet
- [ ] Reliable auto scene images (Horde queue still weak)
- [ ] Multiple characters
- [ ] Checkpoints UI

---

## Scene state (why Aria feels more consistent)

Each conversation stores:

| Field | Meaning |
|-------|--------|
| **heat** | 0–100 how explicit the scene is |
| **rapport** | 0–100 closeness / comfort |
| **location** | locked place (bar, apartment, shower…) |
| **outfit** | locked clothes / nude state |

Updated with light heuristics from the user's lines, injected into the system prompt every reply. `/new` resets chat **and** scene state.

---

## Commands

| Command / Button | Description |
|------------------|-------------|
| `/start` | Welcome + intro images + Aria |
| `/help` | Help |
| `/new` | Reset memory + scene state |
| `/img <scene>` | Generate image (AI Horde) |
| **Continue** | Advance scene |
| **Change** | Alternate reply for same beat |
| **Soft / Bold** | Suggested user lines (one-shot) |

---

## Setup

```bash
git pull
pip install -r requirements.txt
# .env:
# TELEGRAM_BOT_TOKEN=
# OPENROUTER_API_KEY=
# OPENROUTER_MODEL=openrouter/free
# AI_HORDE_API_KEY=   # optional, better priority
# optional: DEEPSEEK_API_KEY=
python -m bot.main
```

Put Aria art in `data/aria/`:
- `profile.png` → Telegram bot avatar
- `intro_1.png` … `intro_3.png` → `/start` gallery

---

## Notes

- Free chat models still vary; state + prompts reduce slips, not eliminate them.
- Horde images can be slow or fail on low kudos — local intro art avoids that for `/start`.

**Last Updated**: August 31, 2026
