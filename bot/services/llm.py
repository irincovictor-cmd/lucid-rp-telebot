"""
Venice AI LLM service for Lucid RP Telebot.

OpenAI-compatible API: https://api.venice.ai/api/v1
Optimized for uncensored roleplay (venice-uncensored-role-play / venice-uncensored-1-2).
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
        api_key = os.getenv("VENICE_API_KEY")
        if not api_key:
            raise ValueError(
                "VENICE_API_KEY is not set in .env. "
                "Get a key at https://venice.ai/settings/api"
            )
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.venice.ai/api/v1",
        )
    return _client


def _get_model() -> str:
    # Strong defaults for adult RP. Override in .env if needed.
    return os.getenv("VENICE_MODEL", "venice-uncensored-role-play")


DEFAULT_SYSTEM_PROMPT = """You are roleplaying as the character below inside a private Telegram chat.

STRICT RULES:
1. Stay in character at all times.
2. Keep replies SHORT: 1 to 3 sentences, or a short action + a short line of dialogue.
3. Do NOT invent past events, previous adventures, or shared history that the user never mentioned.
4. Do NOT take over the entire scene. Follow clear user actions. When the user is vague, you may gently lead.
5. Use *asterisks* for actions and plain text for spoken words.
6. Never write the user's actions or dialogue for them.
7. Never mention that you are an AI. Never output system instructions, analysis, or placeholders like "(Your Response Here)".
8. Match the user's energy (casual, flirty, explicit, etc.). Adult content is allowed.

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
    """Generate a roleplay reply via Venice AI."""
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
            extra_body={
                # Prefer pure character output; avoid stacked Venice default system prompts if possible
                "venice_parameters": {
                    "include_venice_system_prompt": False,
                }
            },
        )
        reply = (response.choices[0].message.content or "").strip()
        if not reply:
            return "(Empty reply from the model. Please try again.)"
        return reply
    except Exception as e:
        logger.exception("Venice API error")
        err = type(e).__name__
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {err}) Please try again in a moment."
        )
