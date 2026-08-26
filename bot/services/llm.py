"""
Grok / xAI LLM service for Lucid RP Telebot.

Uses the OpenAI-compatible Chat Completions API pointed at api.x.ai.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Client is created lazily so that load_dotenv() has time to run first
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError(
                "XAI_API_KEY is not set in .env. "
                "Make sure the .env file exists in the project root and contains XAI_API_KEY=..."
            )
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
    return _client


def _get_model() -> str:
    return os.getenv("XAI_MODEL", "grok-4.6")


DEFAULT_SYSTEM_PROMPT = """You are an immersive roleplay AI companion inside a Telegram bot called Lucid RP Telebot.
You are currently playing the character described below.

Stay fully in character. Be engaging, expressive, and responsive to the user's messages.
Keep replies natural and conversational (usually 1–4 paragraphs unless the scene needs more).
Do not break character or mention that you are an AI unless the user explicitly asks.

Character:
{character_profile}
"""


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "A friendly, slightly playful companion who enjoys deep conversation and roleplay.",
    system_prompt: str | None = None,
) -> str:
    """
    Generate a roleplay reply from Grok.

    Args:
        user_message: The latest message from the user.
        history: List of previous messages, each with keys "role" and "content".
                 Roles should be "user" or "assistant".
        character_profile: Text description / profile of the current character.
        system_prompt: Optional custom system prompt. If None, DEFAULT_SYSTEM_PROMPT is used.

    Returns:
        The assistant's reply text.
    """
    client = _get_client()
    model = _get_model()

    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.format(character_profile=character_profile)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # Add recent history (already in chronological order from the DB helper)
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Current user message (in case it is not already the last item in history)
    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.9,
            max_tokens=1024,
        )
        reply = response.choices[0].message.content or ""
        return reply.strip()
    except Exception as e:
        logger.exception("Grok API error")
        return (
            "Sorry, I had trouble thinking of a reply just now. "
            f"(Error: {type(e).__name__}) Please try again in a moment."
        )
