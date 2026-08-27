# Lucid RP Telebot (HoneyChat)

**Zero-budget Telegram bot for 18+ AI roleplay + NSFW image generation**  
Inspired by LucidDreams-style experiences.

> ⚠️ **Adult Content Only (18+)**

---

## Current Status (Updated Aug 28, 2026)

### Working
- [x] OpenRouter roleplay + SQLite memory
- [x] Aria character + rooftop intro
- [x] **Continue** button
- [x] **Soft / Bold** suggestion buttons (story-choice style)
- [x] Replies include actions + brief feelings/thoughts
- [x] Prompt: no scene-skip, explicit vocab match, location lock
- [x] `/img <description>` — AI Horde image generation (free, can be slow)
- [x] Aria profile portrait on `/start` and `/new` (cached after first gen)

### Not yet
- [ ] Auto scene images from chat context
- [ ] Multiple characters
- [ ] Checkpoints UI

---

## Commands

| Command / Button | Description |
|------------------|-------------|
| `/start` | Welcome + Aria profile + intro |
| `/help` | Help |
| `/new` | Reset memory + intro |
| `/img <scene>` | Generate image (AI Horde) |
| **Continue** | Advance scene |
| **Soft / Bold** | Pick a suggested user reply |

---

## Setup

```bash
git pull
pip install -r requirements.txt
# .env needs:
# TELEGRAM_BOT_TOKEN=
# OPENROUTER_API_KEY=
# OPENROUTER_MODEL=openrouter/free
# AI_HORDE_API_KEY=   # optional but better priority
python -m bot.main
```

---

## Notes

- First Aria profile image may take 1–3 minutes (free Horde queue), then it is cached in `data/`.
- `/img` is also free and can be slow.
- Free chat models still vary; prompts reduce but do not eliminate slips.

**Last Updated**: August 28, 2026
