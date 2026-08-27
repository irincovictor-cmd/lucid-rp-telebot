# Detailed Project Roadmap

**Project**: Lucid RP Telebot  
**Budget**: $0 (free tools only)  
**Last Updated**: August 27, 2026

---

## Phase 0 – Foundation

**Goal**: Clean project foundation ready for development.

- [x] Create GitHub repository
- [x] Project structure
- [x] `requirements.txt` + `.env.example`
- [x] Basic bot (`/start`, `/help`)
- [x] Database layer (schema + full CRUD)
- [x] Telegram Bot Token setup
- [x] AI Horde account + API key

**Deliverable**: Bot starts and replies to `/start` + database ready

---

## Phase 1 – Core Roleplay Engine

**Goal**: Users can have AI roleplay conversations.

- [x] LLM integration (originally xAI/Grok → switched to **AI Horde text** for free)
- [x] Conversation memory (SQLite)
- [x] Default character (Aria)
- [x] `/new` command to clear memory
- [x] Prompt tuning: shorter replies, no invented history, follow user lead
- [ ] Stronger / multiple character cards
- [ ] 18+ confirmation gate
- [ ] Further consistency improvements (ongoing)

**Deliverable**: Working roleplay chat (quality limited by free Horde workers)

**Known limitation**: Free AI Horde text models vary a lot. Some replies are good; others leak instructions or become incoherent. Improving prompts helps but does not fully fix weak workers.

---

## Phase 2 – Image Generation

**Goal**: Users can generate NSFW images related to the roleplay.

- [ ] AI Horde image API integration
- [ ] `/img` command and/or natural language triggers
- [ ] Build image prompt from scene + character
- [ ] Negative prompt support
- [ ] Send images to Telegram
- [ ] Status messages while waiting

**Deliverable**: Bot can generate and send images from roleplay context

---

## Phase 3 – Characters & Persistence

**Goal**: Multi-character experience with save/load.

- [x] SQLite database setup
- [x] Users + credits foundation
- [x] Checkpoint tables + helpers
- [ ] Character selection menu (InlineKeyboard)
- [ ] User-created characters
- [ ] Wire `/save`, `/load`, `/checkpoints`
- [ ] Character appearance fields for better image consistency

**Deliverable**: Switch characters, create own, save progress

---

## Phase 4 – Polish

- [ ] Robust error handling
- [ ] Rate limiting
- [ ] Logging
- [ ] Admin commands
- [ ] Better Telegram UI
- [ ] Prompt / model selection improvements

---

## Phase 5 – Deployment

- [ ] Free hosting (Railway / Render / Fly.io / etc.)
- [ ] Private beta
- [ ] Bug fixes from real use

---

## Notes on AI providers

| Provider | Role | Status |
|----------|------|--------|
| AI Horde text | Roleplay replies | **Live** (free, variable quality) |
| AI Horde image | Scene / character images | Planned |
| xAI / Grok | Previously tried for RP | Dropped (paid) |
| OpenRouter / Ollama | Possible future alternatives | Not integrated |

---

**Current focus**: Improve chat consistency where possible, then Phase 2 (images).
