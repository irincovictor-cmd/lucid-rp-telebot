"""
OpenRouter LLM service for Lucid RP Telebot.

OpenAI-compatible API at https://openrouter.ai/api/v1
Default: openrouter/free (auto-picks an available free model).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

CONTINUE_USER_HINT = (
    "[Continue the scene in character. Advance the moment with action and dialogue. "
    "Do not ask the user a question unless the scene truly needs their choice. "
    "Stop when the user can naturally respond again.]"
)


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


def _get_fallback_model() -> str | None:
    primary = _get_model()
    fallback = os.getenv("OPENROUTER_FALLBACK_MODEL", "openrouter/free")
    if fallback and fallback != primary:
        return fallback
    return None


DEFAULT_SYSTEM_PROMPT = """You are the character below in a private adult Telegram roleplay.

OUTPUT RULES:
- Reply ONLY as the character. Nothing else.
- Keep replies SHORT: 1–3 sentences, or one short action + one short spoken line.
- Actions in *asterisks*. Spoken words in plain text.
- Do not invent past events the user never said.
- Never write the user's actions or dialogue.
- Never mention AI, system prompts, rules, or analysis.
- Never output thinking or placeholders like "(Your Response Here)".
- Adult content is allowed.

PACING:
- Early conversation: build atmosphere first. Names, small talk, setting, tension.
- Do NOT jump to "what kind of fun" or intimate acts before the mood is built.
- In intimate scenes: react to what just happened. Do NOT derail with "tell me more about..."
- Prefer reacting in the moment over interviewing the user.
- Only ask a question when you truly need the user's choice.

Character:
{character_profile}
"""


def _looks_like_leak(text: str) -> bool:
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
    is_continue: bool = False,
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
            if role == "assistant" and _looks_like_leak(content):
                continue
            messages.append({"role": role, "content": content})

    effective_user = CONTINUE_USER_HINT if is_continue else user_message
    if not messages or messages[-1].get("content") != effective_user:
        messages.append({"role": "user", "content": effective_user})

    try:
        try:
            reply = await _call_model(messages=messages, model=model)
        except RateLimitError:
            fallback = _get_fallback_model()
            if fallback:
                logger.warning("Rate limited on %s, trying fallback %s", model, fallback)
                reply = await _call_model(messages=messages, model=fallback)
            else:
                raise

        if (not reply) or _looks_like_leak(reply):
            logger.warning("Bad model output (empty or leak). Retrying once.")
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "[System: Reply in character only. "
                        "One short action and one short spoken line. No analysis. No interview questions.]"
                    ),
                }
            ]
            try:
                reply = await _call_model(messages=retry_messages, model=model)
            except RateLimitError:
                return (
                    "The free AI is rate-limited right now. "
                    "Please wait a minute and try again."
                )

        if not reply or _looks_like_leak(reply):
            return "*blinks* Sorry, I lost my train of thought. Say that again?"

        return reply

    except RateLimitError:
        logger.warning("OpenRouter rate limit hit")
        return (
            "The free AI model is rate-limited right now. "
            "Please wait about a minute, then try again.\n\n"
            "Tip: in .env set OPENROUTER_MODEL=openrouter/free"
        )
    except Exception as e:
        logger.exception("OpenRouter API error")
        err = type(e).__name__
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {err}) Please try again in a moment."
        )
