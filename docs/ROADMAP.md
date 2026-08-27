# Detailed Project Roadmap

**Project**: Lucid RP Telebot (HoneyChat)  
**Budget**: Free-first  
**Last Updated**: August 28, 2026

---

## Phase 0 – Foundation

- [x] GitHub repo + project structure
- [x] Basic bot (`/start`, `/help`)
- [x] SQLite schema + CRUD
- [x] Telegram token + env setup

---

## Phase 1 – Core Roleplay Engine

**Goal**: Usable AI roleplay with memory and scene framing.

- [x] LLM integration → **OpenRouter** (free models)
- [x] Conversation memory (SQLite)
- [x] Default character **Aria**
- [x] Bot welcome + Aria scene intro (`/start`, `/new`)
- [x] `/new` clears memory and restarts intro
- [x] **Continue ▶** button (advance scene without user text)
- [x] Prompt tuning:
  - Short replies
  - No invented history / instruction leaks
  - Slow-burn early pacing
  - No scene-skip (don't act acts that haven't happened)
  - Match user's explicit vocabulary
  - Stay in current location
- [x] Rate-limit handling + optional fallback model
- [ ] Stronger multi-character system
- [ ] 18+ confirmation gate

**Known limits**: Free models still vary (mild language, occasional slips). Prompt rules reduce but do not eliminate that.

---

## Phase 2 – Image Generation

- [ ] AI Horde image API
- [ ] `/img` or natural-language triggers
- [ ] Prompt built from character + recent scene
- [ ] Send images to Telegram + wait status

---

## Phase 3 – Characters & Persistence

- [x] DB foundation (characters, checkpoints, credits)
- [ ] Character selection menu
- [ ] User-created characters
- [ ] Wire `/save`, `/load`, `/checkpoints`

---

## Phase 4 – Polish

- [ ] Better error handling / rate limits
- [ ] Logging, admin commands
- [ ] Richer Telegram UI

---

## Phase 5 – Deploy

- [ ] Free hosting
- [ ] Private beta testing

---

## Provider history

| Provider | Role | Status |
|----------|------|--------|
| xAI / Grok | Early RP attempt | Dropped (paid) |
| AI Horde text | Temporary RP | Dropped (low quality) |
| OpenRouter | Current RP | **Live** |
| Venice AI | Evaluated | Dropped (not free) |
| AI Horde image | Future images | Planned |

---

**Current focus**: Stabilize RP quality → then Phase 2 images.
