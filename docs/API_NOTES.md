# API Notes

Useful reference for the free APIs used in this project.

---

## AI Horde (Image Generation)

- **Website**: https://aihorde.net
- **API Docs**: https://aihorde.net/api
- **Cost**: Completely free (community GPU power)
- **NSFW**: Allowed (only CSAM is blocked)
- **Authentication**: API key (register for better priority) or anonymous `0000000000`

### Key Concepts
- Asynchronous: Submit job → receive ID → poll for result
- Kudos system: Higher kudos = higher priority
- Workers can choose which models and NSFW settings they support

### Recommended Approach for the Bot
1. Submit generation request with good positive + negative prompt
2. Poll `/generate/check` until done
3. Download image from the returned URL
4. Send to Telegram user
5. Show progress messages so user knows it’s working

### Useful Models (subject to change)
Check currently active models via the API. Popular NSFW-capable ones often include various Pony, SDXL, and specialized fine-tunes.

---

## Grok (xAI) – Roleplay LLM

- Used for character roleplay and prompt rewriting
- Strong long-context and uncensored capabilities
- Requires xAI API key

### Recommended Usage
- System prompt defines the character + roleplay style
- Include recent conversation history
- Separate call for rewriting user image requests into strong prompts

---

## Future / Fallback Image Providers

These can be added later if needed:

- PixAI (good for anime, has free daily credits)
- Self-hosted ComfyUI / Automatic1111 (best quality long-term if you get a GPU)
- Other free/uncensored APIs as they appear

The image generation service should be abstracted so switching providers is easy.

---

Last Updated: August 26, 2026
