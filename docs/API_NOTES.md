# API Notes

Reference for APIs and internal systems used in this project.

---

## OpenRouter (Roleplay LLM) — **current**

- **Website**: https://openrouter.ai
- **Keys**: https://openrouter.ai/keys
- **Free models**: https://openrouter.ai/models?q=free
- **API**: OpenAI-compatible `https://openrouter.ai/api/v1`
- **Env**:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL` (default `openrouter/free`)
  - `OPENROUTER_FALLBACK_MODEL` (optional)

### Notes
- Free models are rate-limited and change over time.
- Prefer `openrouter/free` so one busy model does not block the bot.
- Prompt rules in `bot/services/llm.py` handle atmosphere, feelings, no scene-skip, explicit vocab matching, leak retries, and **scene state injection**.

---

## DeepSeek (optional RP)

- **Env**: `DEEPSEEK_API_KEY`, optional `DEEPSEEK_MODEL` (default `deepseek-chat`)
- Used automatically if key is set (unless `LLM_PROVIDER=openrouter`)
- Official API is **not** free long-term; balance required

---

## Scene state (internal — not an external API)

Stored per conversation in SQLite (`conversations` table):

| Column | Range / default | Role |
|--------|-----------------|------|
| `heat` | 0–100, default 0 | Explicit intensity → reply length & tone |
| `rapport` | 0–100, default 15 | Closeness |
| `location` | text | Locked place |
| `outfit` | text | Locked clothes |
| `scene_notes` | text | Optional freeform facts |

Updated by `llm.infer_scene_updates()` from user text keywords, then passed into `generate_reply(..., scene_state=...)`.  
`/new` and `clear_conversation` reset to rooftop defaults.

Inspired by stateful RP bots (e.g. trust/emotion continuity) but **consensual Aria-only** — no coercion systems.

---

## AI Horde (Image Generation) — **current**

- **Website**: https://aihorde.net
- **API Docs**: https://aihorde.net/api
- **Cost**: Free (community workers); priority depends on **kudos**
- **NSFW**: Allowed when `nsfw: true` (CSAM blocked)
- **Env**:
  - `AI_HORDE_API_KEY` (registered key preferred over anonymous `0000000000`)
  - `AI_HORDE_MODEL` (default `Nova Anime XL`)

### Current bot settings (`bot/services/image_gen.py`)
- Prompt style: quality tags + Aria visual lock + scene
- Prefer **Nova Anime XL**
- Sizes: **768×768** → **512×768** → any worker 512×768
- Sampler: `k_euler`, CFG 5, steps 20–25, clip skip 2

### Local art (preferred for /start)
- `data/aria/profile.png` → Telegram **bot avatar** via `setMyProfilePhoto`
- `data/aria/intro_1.png` … `intro_3.png` → in-chat gallery only

### Kudos / resolution limits
- Large jobs can return **403 `KudosUpfront`**
- Stay on smaller resolutions unless the account has enough kudos

---

## Deprecated / not used for RP

| Provider | Why |
|----------|-----|
| xAI / Grok | Paid |
| AI Horde text | Low / unstable RP quality |
| Venice AI | Not free long-term |

---

Last Updated: August 31, 2026
