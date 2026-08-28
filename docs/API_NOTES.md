# API Notes

Reference for APIs used in this project.

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
- Prompt rules in `bot/services/llm.py` handle short replies, no scene-skip, explicit vocab matching, and leak retries.

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
- Prompt style aligned with JustAAA tests (quality tags + Aria visual lock + scene)
- Prefer **Nova Anime XL**
- Sizes tried in order: **768×768** → **512×768** → any worker 512×768
- Sampler: `k_euler`, CFG 5, steps 20–25, clip skip 2
- Progress messages while queued

### Kudos / resolution limits
- Jobs that are too large or use expensive samplers can return **403 `KudosUpfront`**
- Example: 1024×1024 + `k_dpmpp_sde` required ~56 kudos and was rejected on a low-kudos key
- Stay on smaller resolutions unless the account has enough kudos

### CivitAI vs Horde
- **CivitAI** hosts model files (e.g. Nova Anime XL) and has its own website generator with separate filters
- **AI Horde** runs volunteer workers that already loaded those models; generation does **not** go through CivitAI
- NSFW on Horde works because Horde allows adult content, not because it “bypasses CivitAI”

### Experiment: auto-pick any worker (reverted)
- Tried selecting the fastest live model / empty `models: []` for shorter queues
- Result in practice: **not better** for this project (style inconsistent, waits still long)
- **Reverted** to Nova-first with size fallbacks (Aug 28, 2026)
- Keep for future reference only if we later need max speed over consistency

### Status API (optional future use)
- `GET /api/v2/status/models?type=image` lists workers, queue, ETA per model
- Can be used again to pick a live model, but empty `models` = any worker is usually the only true “fast path”

---

## Deprecated / not used for RP

| Provider | Why |
|----------|-----|
| xAI / Grok | Paid |
| AI Horde text | Low / unstable RP quality |
| Venice AI | Not free long-term |

---

Last Updated: August 28, 2026
