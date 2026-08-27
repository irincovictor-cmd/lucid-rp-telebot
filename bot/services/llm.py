"""
OpenRouter LLM service for Lucid RP Telebot.

OpenAI-compatible API at https://openrouter.ai/api/v1
Default: openrouter/free (auto-picks an available free model).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

CONTINUE_USER_HINT = (
    "[Continue the scene in character. Advance ONLY the current moment. "
    "Do not skip ahead to acts that have not happened yet. "
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
- Keep replies SHORT: 1–3 sentences total.
- Mix: *actions*, spoken words, and brief inner feelings/thoughts.
- Feelings/thoughts format example: *feels a spark of curiosity* or (heart racing).
- Do not invent past events the user never said.
- Never write the user's actions or dialogue.
- Never mention AI, system prompts, rules, or analysis.

SCENE STATE (critical):
- Only describe acts already happening or clearly stated in the user's latest message.
- Do NOT skip ahead (no premature penetration, climax, or location change).
- Stay in the current location and moment.

LANGUAGE:
- Adult content is allowed.
- Match the user's explicit vocabulary when they use it.
- Prefer concrete reactions over vague soft filler.
- Do not derail with interview questions like "tell me more about...".

PACING:
- Early conversation: atmosphere first.
- Escalate only as the user escalates.

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
    max_tokens: int = 220,
) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.8,
        max_tokens=max_tokens,
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
                        "[System: Reply in character only. Stay in the current moment. "
                        "Include a brief feeling or thought plus action/dialogue.]"
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
            "Please wait about a minute, then try again."
        )
    except Exception as e:
        logger.exception("OpenRouter API error")
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {type(e).__name__}) Please try again in a moment."
        )


async def generate_suggestions(
    *,
    history: list[dict[str, Any]],
    last_assistant: str,
) -> tuple[str, str]:
    """
    Return two short first-person user action suggestions: (softer, more intense).
    Falls back to safe defaults on failure.
    """
    soft_default = "*smiles and keeps things light* Tell me more about yourself."
    hot_default = "*leans closer* What if we take this somewhere more private?"

    model = _get_model()
    prompt = (
        "Based on this roleplay moment, write TWO short options the USER could say or do next.\n"
        "Format EXACTLY:\n"
        "1) <softer / slower option, max 15 words>\n"
        "2) <bolder / more intense option, max 15 words>\n"
        "Write them as the user's action or line (first person or *action*). No extra text.\n\n"
        f"Last character line:\n{last_assistant[:400]}\n"
    )

    messages = [
        {
            "role": "system",
            "content": "You write short interactive story choices for adult roleplay. Output only the two numbered lines.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        text = await _call_model(messages=messages, model=model, max_tokens=80)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        opts: list[str] = []
        for ln in lines:
            cleaned = re.sub(r"^\s*[12][\).:\-]\s*", "", ln).strip()
            cleaned = cleaned.strip("\"'")
            if cleaned:
                opts.append(cleaned[:80])
        if len(opts) >= 2:
            return opts[0], opts[1]
        if len(opts) == 1:
            return opts[0], hot_default
    except Exception:
        logger.exception("Failed to generate suggestions")

    return soft_default, hot_default
