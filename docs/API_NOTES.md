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

## AI Horde (Image Generation) — **planned**

- **Website**: https://aihorde.net
- **API Docs**: https://aihorde.net/api
- **Cost**: Free (community workers)
- **NSFW**: Allowed (CSAM blocked)
- **Env**: `AI_HORDE_API_KEY` (or anonymous `0000000000`)

### Planned bot flow
1. Build prompt from character + recent scene
2. Submit async job
3. Poll until done
4. Send image to Telegram + status messages

---

## Deprecated / not used for RP

| Provider | Why |
|----------|-----|
| xAI / Grok | Paid |
| AI Horde text | Low / unstable RP quality |
| Venice AI | Not free long-term |

---

Last Updated: August 28, 2026
