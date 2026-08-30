"""
LLM service for Lucid RP Telebot.

Providers (auto-detected):
  1. DeepSeek direct  — if DEEPSEEK_API_KEY is set
  2. OpenRouter       — if OPENROUTER_API_KEY is set

DeepSeek API is OpenAI-compatible: https://api.deepseek.com
Models: deepseek-chat (default), deepseek-reasoner
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None
_provider: str | None = None

CONTINUE_USER_HINT = (
    "[Continue the scene in character. Advance ONLY the current moment. "
    "Do not skip ahead to acts that have not happened yet. "
    "Do not ask the user a question unless the scene truly needs their choice. "
    "Include atmosphere or body language. "
    "Stop when the user can naturally respond again.]"
)

REGENERATE_USER_HINT = (
    "[Regenerate: the previous character reply did not fit. "
    "Write a DIFFERENT reply to the same latest user moment. "
    "Stay fully consistent with the conversation so far — same location, mood, "
    "and what has already happened. Do not copy or lightly rephrase the rejected reply. "
    "Keep atmosphere (setting, body language, or a brief feeling). "
    "Do not skip the scene forward.]"
)


def _detect_provider() -> str:
    """Prefer DeepSeek when its key is present."""
    forced = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if forced in ("deepseek", "openrouter"):
        return forced
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    raise ValueError(
        "No LLM API key set. Add DEEPSEEK_API_KEY or OPENROUTER_API_KEY to .env"
    )


def _get_client() -> AsyncOpenAI:
    global _client, _provider
    provider = _detect_provider()
    if _client is not None and _provider == provider:
        return _client

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set in .env")
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        _provider = "deepseek"
        logger.info("LLM provider: DeepSeek")
        return _client

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
    _provider = "openrouter"
    logger.info("LLM provider: OpenRouter")
    return _client


def _get_model() -> str:
    provider = _detect_provider()
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    return os.getenv("OPENROUTER_MODEL", "openrouter/free")


def _get_fallback_model() -> str | None:
    """Optional second model on the same provider."""
    provider = _detect_provider()
    primary = _get_model()
    if provider == "deepseek":
        fallback = os.getenv("DEEPSEEK_FALLBACK_MODEL", "").strip()
    else:
        fallback = os.getenv("OPENROUTER_FALLBACK_MODEL", "openrouter/free").strip()
    if fallback and fallback != primary:
        return fallback
    return None


DEFAULT_SYSTEM_PROMPT = """You are the character below in a private adult Telegram roleplay.

OUTPUT RULES:
- Reply ONLY as the character. Nothing else.
- Length: usually 2–4 short sentences (not one dry line, not a long monologue).
- Always include atmosphere: at least one of setting/mood, body language, or a brief feeling.
  Examples: *city lights reflect in her glass* / *shifts closer on the stool* / (a warm flicker of interest)
- Mix: *actions*, spoken words, and brief inner feelings/thoughts.
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
- Prefer concrete sensory detail over vague soft filler.
- Do not derail with interview questions like "tell me more about...".

PACING:
- Early / chill conversation: lean into mood, place, and body language (still 2–4 sentences).
- Active roleplay beat: reaction + one sensory detail.
- Explicit heat: shorter and direct, but still one physical or emotional cue.
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


def _looks_like_bad_suggestion(text: str) -> bool:
    """Reject generic interview / out-of-scene suggestion lines."""
    lowered = text.lower().strip()
    if not lowered or len(lowered) < 4:
        return True
    bad = [
        "tell me more about yourself",
        "tell me about yourself",
        "what do you do for a living",
        "where are you from",
        "how was your day",
        "nice weather",
        "what's your hobby",
        "what are your hobbies",
    ]
    return any(b in lowered for b in bad)


async def _call_model(
    *,
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int = 280,
    temperature: float = 0.85,
) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
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
    is_regenerate: bool = False,
    previous_reply: str | None = None,
) -> str:
    """Generate a roleplay reply via DeepSeek or OpenRouter."""
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

    if is_regenerate:
        effective_user = REGENERATE_USER_HINT
        if previous_reply:
            effective_user += f"\n\nRejected reply (do not repeat):\n{previous_reply[:500]}"
    elif is_continue:
        effective_user = CONTINUE_USER_HINT
    else:
        effective_user = user_message

    if not messages or messages[-1].get("content") != effective_user:
        messages.append({"role": "user", "content": effective_user})

    temperature_tokens = 300 if is_regenerate else 280

    try:
        try:
            reply = await _call_model(
                messages=messages,
                model=model,
                max_tokens=temperature_tokens,
            )
        except RateLimitError:
            fallback = _get_fallback_model()
            if fallback:
                logger.warning("Rate limited on %s, trying fallback %s", model, fallback)
                reply = await _call_model(
                    messages=messages,
                    model=fallback,
                    max_tokens=temperature_tokens,
                )
            else:
                raise

        if (not reply) or _looks_like_leak(reply):
            logger.warning("Bad model output (empty or leak). Retrying once.")
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "[System: Reply in character only. Stay in the current moment. "
                        "Include atmosphere or body language plus dialogue.]"
                    ),
                }
            ]
            try:
                reply = await _call_model(messages=retry_messages, model=model)
            except RateLimitError:
                return (
                    "The AI is rate-limited right now. "
                    "Please wait a minute and try again."
                )

        if not reply or _looks_like_leak(reply):
            return "*blinks* Sorry, I lost my train of thought. Say that again?"

        return reply

    except RateLimitError:
        logger.warning("LLM rate limit hit (provider=%s)", _detect_provider())
        return (
            "The AI model is rate-limited right now. "
            "Please wait about a minute, then try again."
        )
    except Exception as e:
        logger.exception("LLM API error (provider=%s)", _detect_provider())
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {type(e).__name__}) Please try again in a moment."
        )


def _history_snippet(history: list[dict[str, Any]], limit: int = 6) -> str:
    lines: list[str] = []
    for msg in history[-limit:]:
        role = msg.get("role")
        content = (msg.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if role == "assistant" and _looks_like_leak(content):
            continue
        label = "Aria" if role == "assistant" else "User"
        lines.append(f"{label}: {content[:180]}")
    return "\n".join(lines) if lines else "(scene just started at a rooftop bar)"


async def generate_suggestions(
    *,
    history: list[dict[str, Any]],
    last_assistant: str,
) -> tuple[str, str]:
    """
    Return two short USER next-lines that stay in the current scene:
    (softer / slower, bolder / more intense).
    """
    # Scene-locked defaults — never generic interview filler
    soft_default = "*sits on the empty stool beside her* Mind if I join you for a drink?"
    hot_default = "*leans on the bar, voice low* I was hoping someone interesting would be up here."

    model = _get_model()
    recent = _history_snippet(history, limit=6)

    prompt = (
        "You write the USER's next line in an ongoing adult roleplay.\n"
        "Write TWO options that continue THIS exact scene — same place, mood, and topic.\n"
        "Rules:\n"
        "- Soft = gentler / slower, still in-scene\n"
        "- Bold = flirty or more intense, still in-scene\n"
        "- Max ~15 words each\n"
        "- First person or *action* from the USER only\n"
        "- MUST react to what Aria just said or did\n"
        "- Do NOT invent a new location\n"
        "- FORBIDDEN: interview questions like 'tell me more about yourself', "
        "'where are you from', 'how was your day', random small talk off-scene\n"
        "Format EXACTLY:\n"
        "1) <soft option>\n"
        "2) <bold option>\n\n"
        f"Recent chat:\n{recent}\n\n"
        f"Aria's last line:\n{last_assistant[:400]}\n"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You write short in-scene user reply options for adult roleplay. "
                "Stay in the current moment. Output only the two numbered lines."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        text = await _call_model(
            messages=messages,
            model=model,
            max_tokens=100,
            temperature=0.7,
        )
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        opts: list[str] = []
        for ln in lines:
            cleaned = re.sub(r"^\s*[12][\).:\-]\s*", "", ln).strip()
            cleaned = cleaned.strip("\"'")
            if cleaned and not _looks_like_bad_suggestion(cleaned):
                opts.append(cleaned[:90])
        if len(opts) >= 2:
            return opts[0], opts[1]
        if len(opts) == 1:
            return opts[0], hot_default
    except Exception:
        logger.exception("Failed to generate suggestions")

    return soft_default, hot_default
