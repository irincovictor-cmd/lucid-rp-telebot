# Detailed Project Roadmap

**Project**: Lucid RP Telebot  
**Budget**: $0 (free tools only)  
**Estimated Timeline**: 4–8 weeks

---

## Phase 0 – Foundation (Days 1–2)

**Goal**: Clean project foundation ready for development.

- [x] Create GitHub repository
- [ ] Initialize proper project structure
- [ ] Create `requirements.txt` with initial dependencies
- [ ] Create `.env.example`
- [ ] Set up virtual environment instructions
- [ ] Create Telegram bot via @BotFather and obtain token
- [ ] Register on [AI Horde](https://aihorde.net) and get personal API key
- [ ] Write and test a minimal "echo" or "hello" bot
- [ ] Add basic `.gitignore`

**Deliverable**: Bot that starts and replies to `/start`

---

## Phase 1 – Core Roleplay Engine (Week 1)

**Goal**: Users can have basic AI roleplay conversations.

- [ ] Integrate Grok (xAI API) for chat completions
- [ ] Design flexible character card format (JSON)
- [ ] Create 2–3 default characters
- [ ] Implement short-term conversation memory
- [ ] Add 18+ confirmation gate
- [ ] Commands: `/start`, `/help`, `/new`, `/characters`
- [ ] System prompt engineering for consistent roleplay style

**Deliverable**: Working roleplay chat with at least one character

---

## Phase 2 – Image Generation (Week 2)

**Goal**: Users can generate NSFW images related to the roleplay.

- [ ] Full AI Horde async API integration
- [ ] Support for positive + negative prompts
- [ ] LLM-powered prompt rewriting (user request → strong image prompt)
- [ ] Natural language triggers ("show me...", "generate a scene of...") + `/img` command
- [ ] Status updates while waiting for generation
- [ ] Error handling for timeouts / failed generations
- [ ] Basic model selection (recommend good NSFW models on Horde)

**Deliverable**: Bot can generate and send images from roleplay context

---

## Phase 3 – Persistence & Character System (Weeks 3–4)

**Goal**: Real multi-character experience with memory.

- [ ] SQLite database setup
- [ ] User profiles & energy/credit system (even if unlimited for now)
- [ ] Multiple character support + selection menu (Telegram InlineKeyboard)
- [ ] User-created characters (guided creation flow)
- [ ] Long-term memory per character
- [ ] Checkpoint system (`/save`, `/load`, `/checkpoints`)
- [ ] Character appearance description stored for better image consistency

**Deliverable**: Users can switch characters, create their own, and save progress

---

## Phase 4 – Quality & Polish (Weeks 5–6)

**Goal**: Make it feel production-ready and pleasant to use.

- [ ] Robust error handling everywhere
- [ ] Rate limiting (per user)
- [ ] Logging (file + console)
- [ ] Admin-only commands
- [ ] Improved Telegram UX (menus, buttons, formatting)
- [ ] Better default prompts and negative prompts
- [ ] Character consistency improvements for images
- [ ] Code cleanup and comments

**Deliverable**: Stable, user-friendly bot

---

## Phase 5 – Deployment & Soft Launch (Weeks 7–8)

**Goal**: Bot is online and testable by others.

- [ ] Choose and configure free hosting (Railway / Render / Fly.io / VPS)
- [ ] Environment variable management
- [ ] Private testing with trusted users
- [ ] Collect feedback and fix issues
- [ ] Optional: Add fallback image provider
- [ ] Write final user-facing documentation

**Deliverable**: Public or private working bot online 24/7

---

## Future Ideas (Post-MVP)

- Image-to-image / reference images for better character consistency
- Multiple image styles (anime / realistic toggle)
- Voice messages (optional)
- Group chat support
- Web dashboard for character management
- Paid premium tier later (if desired)

---

**Last Updated**: August 26, 2026
