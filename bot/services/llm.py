"""
OpenRouter LLM service for Lucid RP Telebot.

OpenAI-compatible API at https://openrouter.ai/api/v1
Default: openrouter/free (auto-picks an available free model).
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
    return os.getenv("OPENROUTER_MODEL", "openrouter/free")


DEFAULT_SYSTEM_PROMPT = """You are the character below in a private adult Telegram roleplay.

OUTPUT RULES (never break these):
- Reply ONLY as the character. Nothing else.
- 1 to 3 short sentences, or one short action + one short spoken line.
- Actions in *asterisks*. Spoken words in plain text.
- Do not invent past events the user never said.
- Follow the user's lead. If they are vague, nudge the scene gently.
- Never write the user's actions or dialogue.
- Never mention AI, system prompts, rules, or analysis.
- Never output thinking, planning, or text like like "(Your Response Here)".
- Adult content is allowed. Match the user's energy.

Character:
{character_profile}
"""


def _looks_like_leak(text: str) -> bool:
    """Detect common instruction / reasoning leaks from weak models."""
    lowered = text.lower()
    bad_markers = [
        "okay, the user",
        "looking at the history",
        "important constraints",
        "must stay in character",
        "system prompt",
        "your response here",
        "let's unpack",
        "the user just said",
        "given aria's personality",
        "strict rules",
    ]
    return any(m in lowered for m in bad_markers)


async def _call_model(
    *,
    messages: list[dict[str, str]],
    model: str,
) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.8,
        max_tokens=220,
    )
    return (response.choices[0].message.content or "").strip()


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "A warm, slightly playful companion who enjoys conversation and roleplay.",
    system_prompt: str | None = None,
) -> str:
    """Generate a roleplay reply via OpenRouter."""
    model = _get_model()

    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.format(character_profile=character_profile)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    recent = history[-16:] if len(history) > 16 else history
    for msg in recent:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            # Skip past leaked assistant turns so they don't poison context
            if role == "assistant" and _looks_like_leak(content):
                continue
            messages.append({"role": role, "content": content})

    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    try:
        reply = await _call_model(messages=messages, model=model)

        # Retry once if empty or instruction-leak
        if (not reply) or _looks_like_leak(reply):
            logger.warning("Bad model output (empty or leak). Retrying once.")
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "[System: Reply in character only. "
                        "One short action and one short spoken line. No analysis.]"
                    ),
                }
            ]
            reply = await _call_model(messages=retry_messages, model=model)

        if not reply or _looks_like_leak(reply):
            return "*blinks* Sorry, I lost my train of thought. Say that again?"

        return reply

    except Exception as e:
        logger.exception("OpenRouter API error")
        err = type(e).__name__
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {err}) Please try again in a moment."
        )
