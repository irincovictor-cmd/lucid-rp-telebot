# Detailed Project Roadmap

**Project**: Lucid RP Telebot (HoneyChat)  
**Budget**: Free-first  
**Last Updated**: August 31, 2026

---

## Phase 0 – Foundation

- [x] GitHub repo + project structure
- [x] Basic bot (`/start`, `/help`)
- [x] SQLite schema + CRUD
- [x] Telegram token + env setup

---

## Phase 1 – Core Roleplay Engine

**Goal**: Usable AI roleplay with memory and scene framing.

- [x] LLM integration → **OpenRouter** (optional DeepSeek)
- [x] Conversation memory (SQLite)
- [x] Default character **Aria**
- [x] Bot welcome + Aria scene intro (`/start`, `/new`)
- [x] `/new` clears memory and restarts intro
- [x] **Continue ▶** / **Change 🔄** / **Soft / Bold**
- [x] Prompt tuning:
  - Atmosphere + brief feeling/thought every reply
  - No invented history / instruction leaks
  - Adaptive length by heat
  - No scene-skip
  - Match user's explicit vocabulary
  - Stay in current location / outfit
- [x] **Scene state** (heat, rapport, location, outfit) in DB + prompt
- [x] Rate-limit handling + optional fallback model
- [x] Do not store rate-limit / leak text in RP history
- [ ] Stronger multi-character system
- [ ] 18+ confirmation gate

**Known limits**: Free models still vary. State + prompts reduce but do not eliminate slips.

---

## Phase 2 – Image Generation

- [x] AI Horde image API wired (`/img`, Image button)
- [x] Prompt from character visual lock + scene / history
- [x] Progress status messages
- [x] Local `data/aria/profile.png` as **bot avatar**
- [x] Local `intro_1–3` gallery on `/start`
- [ ] Stable fast queue (Horde kudos / worker limits remain)
- [ ] Pre-baked spicy scene pack for offline consistency (optional)

---

## Phase 3 – Characters & Persistence

- [x] DB foundation (characters, checkpoints, credits, scene state)
- [ ] Character selection menu
- [ ] User-created characters
- [ ] Wire `/save`, `/load`, `/checkpoints`

---

## Phase 4 – Polish

- [x] Scene-aware Soft/Bold defaults
- [x] One-shot suggestion keys
- [ ] Better error handling / rate limits UX
- [ ] Logging, admin commands
- [ ] Richer Telegram UI (optional status footer)

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
| DeepSeek | Optional RP | Supported if key set |
| Venice AI | Evaluated | Dropped (not free) |
| AI Horde image | Images | **Live** (slow/free) |

---

**Current focus**: Stabilize stateful Aria RP → improve image reliability without paid APIs.
