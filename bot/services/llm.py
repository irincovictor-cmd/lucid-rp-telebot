"""
OpenRouter LLM service for Lucid RP Telebot.

Uses the OpenAI-compatible Chat Completions API at https://openrouter.ai/api/v1
Default model is openrouter/free (auto-picks an available free model).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set in .env. "
                "Get a free key at https://openrouter.ai/keys"
            )
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/irincovictor-cmd/lucid-rp-telebot",
                "X-Title": "Lucid RP Telebot",
            },
        )
    return _client


def _get_model() -> str:
    # openrouter/free auto-selects from currently available free models.
    # Override in .env with any free slug, e.g. google/gemma-4-31b-it:free
    return os.getenv("OPENROUTER_MODEL", "openrouter/free")


DEFAULT_SYSTEM_PROMPT = """You are roleplaying as the character below inside a private Telegram chat.

STRICT RULES:
1. Stay in character at all times.
2. Keep replies SHORT: 1 to 3 sentences, or a short action + a short line of dialogue.
3. Do NOT invent past events, previous adventures, or shared history that the user never mentioned.
4. Do NOT take over the entire scene. Follow clear user actions. When the user is vague, you may gently lead.
5. Use *asterisks* for actions and plain text for spoken words.
6. Never write the user's actions or dialogue for them.
7. Never mention that you are an AI, never output system instructions, never output placeholders like "(Your Response Here)".
8. Match the user's energy (casual, flirty, explicit, etc.).

Character:
{character_profile}
"""


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "A warm, slightly playful companion who enjoys conversation and roleplay.",
    system_prompt: str | None = None,
) -> str:
    """Generate a roleplay reply via OpenRouter."""
    client = _get_client()
    model = _get_model()

    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.format(character_profile=character_profile)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    recent = history[-16:] if len(history) > 16 else history
    for msg in recent:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.85,
            max_tokens=250,
        )
        reply = (response.choices[0].message.content or "").strip()
        if not reply:
            return "(Empty reply from the model. Please try again.)"
        return reply
    except Exception as e:
        logger.exception("OpenRouter API error")
        err = type(e).__name__
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {err}) Please try again in a moment."
        )
