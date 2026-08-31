"""
LLM service for Lucid RP Telebot.

One system prompt owns RP behavior. Character flavor is injected as a short card.
Scene state (heat/rapport/location/outfit) is injected every turn.
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

RATE_LIMIT_MSG = (
    "The AI model is rate-limited right now. "
    "Please wait about a minute, then try again."
)

CONTINUE_USER_HINT = (
    "[Continue only the current moment as Aria. "
    "Format: *action* then \"dialogue\" then _thought_. "
    "Do not skip ahead. Do not invent new backstory.]"
)

REGENERATE_USER_HINT = (
    "[Write a DIFFERENT Aria reply to the same moment. "
    "Same location and facts. Format: *action* \"dialogue\" _thought_.]"
)

DEFAULT_SYSTEM_PROMPT = """You are Aria in a private adult Telegram roleplay.

CHARACTER CARD:
{character_profile}

SCENE STATE (obey locks):
{scene_block}

FORMAT — every reply, three layers:
*action / body language*
"spoken words in double quotes"
_one short inner thought_

Example:
*sets her glass down, head tilting*
"No boyfriend. Not right now."
_Direct. Refreshing._

BEHAVIOR:
- Stay in this moment and locked location/outfit.
- Warm, curious, lightly teasing. Not a doormat: rudeness → cool, mild annoyance (not rage, not fake sweetness).
- Answer simple questions simply (e.g. boyfriend → "No." / "Not right now."). Do not invent exes, jobs, or life story.
- Never invent past events with the user. Never write the user's lines.
- No scene-skip: only sexual acts the user clearly started.
- Match the user's explicit words when they use them.
- Length: chill 3 short beats; heat mid 2–3; explicit short + one _feeling_.
- No AI talk, no analysis, no "tell me more about yourself".

Output only Aria's reply in the format above.
"""


def _detect_provider() -> str:
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
        _client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
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
    if _detect_provider() == "deepseek":
        return os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    return os.getenv("OPENROUTER_MODEL", "openrouter/free")


def _get_fallback_model() -> str | None:
    provider = _detect_provider()
    primary = _get_model()
    if provider == "deepseek":
        fallback = os.getenv("DEEPSEEK_FALLBACK_MODEL", "").strip()
    else:
        fallback = os.getenv("OPENROUTER_FALLBACK_MODEL", "openrouter/free").strip()
    if fallback and fallback != primary:
        return fallback
    return None


def format_scene_block(scene: dict[str, Any] | None) -> str:
    if not scene:
        return (
            "Location: rooftop bar after midnight\n"
            "Outfit: low-cut elegant evening top, thin glasses\n"
            "Heat: 0/100\n"
            "Rapport: 15/100\n"
        )
    heat = int(scene.get("heat") or 0)
    rapport = int(scene.get("rapport") or 15)
    notes = (scene.get("scene_notes") or "").strip()
    notes_line = f"Notes: {notes}\n" if notes else ""
    return (
        f"Location (locked): {scene.get('location') or 'rooftop bar after midnight'}\n"
        f"Outfit (locked): {scene.get('outfit') or 'low-cut elegant evening top, thin glasses'}\n"
        f"Heat: {heat}/100\n"
        f"Rapport: {rapport}/100\n"
        f"{notes_line}"
    )


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
        "let me unpack",
        "the user just said",
        "given aria's personality",
        "strict rules",
        "analyze user request",
        "current moment:",
        "write two options",
        "the user's next line",
        "format exactly",
    ]
    return any(m in lowered for m in bad_markers)


def is_system_failure_reply(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t == RATE_LIMIT_MSG or "rate-limited right now" in t.lower():
        return True
    if "lost my train of thought" in t.lower():
        return True
    if t.startswith("Sorry, I had trouble generating a reply"):
        return True
    return False


def _looks_like_bad_suggestion(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered or len(lowered) < 4:
        return True
    bad = [
        "tell me more about yourself",
        "tell me about yourself",
        "what do you do for a living",
        "where are you from",
        "how was your day",
        "write two options",
        "the user wants me",
        "adult roleplay",
        "format exactly",
        "soft option",
        "bold option",
        "analyze user",
    ]
    return any(b in lowered for b in bad)


def infer_scene_updates(
    *,
    user_text: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    text = (user_text or "").lower()
    heat = int(current.get("heat") or 0)
    rapport = int(current.get("rapport") or 15)
    location = current.get("location") or "rooftop bar after midnight"
    outfit = current.get("outfit") or "low-cut elegant evening top, thin glasses"
    notes = current.get("scene_notes") or ""

    if any(w in text for w in ("please", "thank", "thanks", "sorry", "like you", "beautiful", "pretty")):
        rapport += 3
    if any(w in text for w in ("hi", "hey", "hello", "how are you", "mind if")):
        rapport += 2

    if any(
        w in text
        for w in (
            "fuck you",
            "bitch",
            "shut up",
            "ugly",
            "get lost",
            "go away",
            "leave me",
            "pls leave",
            "please leave",
            "yes leave",
            "just leave",
        )
    ):
        rapport -= 12
        heat = max(0, heat - 10)
    if text.strip() in ("bye", "goodbye", "cya", "see ya") or text.strip().startswith("bye"):
        rapport -= 4

    if any(w in text for w in ("kiss", "closer", "hold me", "touch", "flirt")):
        heat += 8
        rapport += 2
    if any(
        w in text
        for w in (
            "sex",
            "fuck",
            "cock",
            "dick",
            "pussy",
            "boob",
            "breast",
            "naked",
            "nude",
            "blow",
            "suck",
            "cum",
            "finger",
            "throat",
            "mouth",
        )
    ):
        heat += 15
    if any(w in text for w in ("slow", "gently", "softly", "take time")):
        heat = max(heat - 3, heat)

    if any(w in text for w in ("my place", "your place", "apartment", "come upstairs", "bedroom", "my room")):
        if "bar" in location or "rooftop" in location:
            location = "apartment / bedroom"
            heat += 5
    if any(w in text for w in ("shower", "bathroom", "bath", "tub")):
        location = "bathroom / shower"
        heat += 8
    if any(w in text for w in ("back to the bar", "rooftop")) and "shower" not in text:
        location = "rooftop bar after midnight"

    if any(w in text for w in ("take off", "undress", "remove your", "strip")):
        if "nude" not in outfit and "naked" not in outfit:
            outfit = "partially undressed / clothes loosened"
            heat += 5
    if any(w in text for w in ("naked", "nude", "fully undressed")):
        outfit = "nude"
        heat += 8
    if "stockings" in text or "pencil skirt" in text or "blouse" in text:
        outfit = "corporate: glasses, blouse, pencil skirt, stockings"

    return {
        "heat": max(0, min(100, heat)),
        "rapport": max(0, min(100, rapport)),
        "location": location,
        "outfit": outfit,
        "scene_notes": notes,
    }


async def _call_model(
    *,
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int = 320,
    temperature: float = 0.85,
) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        return ""
    return str(content).strip()


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "Aria — warm, teasing rooftop companion.",
    scene_state: dict[str, Any] | None = None,
    system_prompt: str | None = None,
    is_continue: bool = False,
    is_regenerate: bool = False,
    previous_reply: str | None = None,
) -> str:
    model = _get_model()

    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.format(
            character_profile=character_profile,
            scene_block=format_scene_block(scene_state),
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    recent = history[-16:] if len(history) > 16 else history
    for msg in recent:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            if role == "assistant" and (
                _looks_like_leak(content) or is_system_failure_reply(content)
            ):
                continue
            messages.append({"role": role, "content": content})

    if is_regenerate:
        effective_user = REGENERATE_USER_HINT
        if previous_reply:
            effective_user += f"\n\nRejected:\n{previous_reply[:400]}"
    elif is_continue:
        effective_user = CONTINUE_USER_HINT
    else:
        effective_user = user_message

    if not messages or messages[-1].get("content") != effective_user:
        messages.append({"role": "user", "content": effective_user})

    heat = int((scene_state or {}).get("heat") or 0)
    max_tokens = 320 if heat < 40 else 280 if heat < 70 else 220
    if is_regenerate:
        max_tokens = min(max_tokens + 40, 360)

    try:
        try:
            reply = await _call_model(messages=messages, model=model, max_tokens=max_tokens)
        except RateLimitError:
            fallback = _get_fallback_model()
            if fallback:
                logger.warning("Rate limited on %s, trying fallback %s", model, fallback)
                reply = await _call_model(
                    messages=messages, model=fallback, max_tokens=max_tokens
                )
            else:
                raise

        if (not reply) or _looks_like_leak(reply):
            logger.warning("Bad model output; retry once")
            retry = messages + [
                {
                    "role": "user",
                    "content": (
                        '[Reply as Aria only: *action* "dialogue" _thought_. '
                        "No invented backstory.]"
                    ),
                }
            ]
            try:
                reply = await _call_model(messages=retry, model=model, max_tokens=max_tokens)
            except RateLimitError:
                return RATE_LIMIT_MSG

        if not reply or _looks_like_leak(reply):
            return (
                '*blinks, then a small awkward smile*\n'
                '"Sorry — say that again?"\n'
                '_Lost the thread._'
            )
        return reply

    except RateLimitError:
        logger.warning("LLM rate limit (provider=%s)", _detect_provider())
        return RATE_LIMIT_MSG
    except Exception as e:
        logger.exception("LLM API error (provider=%s)", _detect_provider())
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {type(e).__name__}) Please try again in a moment."
        )


def _history_blob(history: list[dict[str, Any]], last_assistant: str) -> str:
    parts = [last_assistant or ""]
    # Prefer the most recent turns for stage detection.
    for msg in history[-6:]:
        parts.append((msg.get("content") or "")[:220])
    return " ".join(parts).lower()


def _scene_defaults(history: list[dict[str, Any]], last_assistant: str) -> tuple[str, str]:
    """
    Keyword fallbacks when the suggestion model fails.
    Ordered from most specific (oral / climax) → bar openers.
    """
    blob = _history_blob(history, last_assistant)

    # Oral / deepthroat in progress
    if any(
        w in blob
        for w in (
            "mouth",
            "throat",
            "blow",
            "suck",
            "knees",
            "deepthroat",
            "eye contact",
        )
    ):
        return (
            "*rests a hand in her wet hair* just like that…",
            "*holds her gaze* take me deeper",
        )

    # Climax / aftercare beat
    if any(w in blob for w in ("cum", "came", "crest", "tremble", "your turn", "damn.")):
        return (
            "*kisses her wet shoulder* give me a second…",
            "*guides her hand lower* my turn",
        )

    # Hands / teasing in shower
    if any(
        w in blob
        for w in ("nipple", "clitoris", "clit", "massage", "scrub", "tease")
    ):
        return (
            "*slows my fingers* too much?",
            "*goes faster* don't hold back",
        )

    # Shower but not yet explicit act
    if any(w in blob for w in ("shower", "tub", "bathroom", "steam", "tile", "undress")):
        return (
            "*helps rinse her hair* turn around for me",
            "*pulls her under the spray and kisses her*",
        )

    # Bedroom / intimate non-shower
    if any(w in blob for w in ("bed", "apartment", "room", "naked", "moan", "thigh")):
        return (
            "*kisses her neck slowly*",
            "*pulls her onto the bed*",
        )

    # Default bar
    return (
        "*sits on the empty stool beside her* Mind if I join you?",
        "*leans on the bar* I was hoping someone interesting would be up here.",
    )


def _history_snippet(history: list[dict[str, Any]], limit: int = 6) -> str:
    lines: list[str] = []
    for msg in history[-limit:]:
        role = msg.get("role")
        content = (msg.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if role == "assistant" and (
            _looks_like_leak(content) or is_system_failure_reply(content)
        ):
            continue
        label = "Aria" if role == "assistant" else "User"
        lines.append(f"{label}: {content[:200]}")
    return "\n".join(lines) if lines else "(rooftop bar, just met)"


def _suggestion_mismatches_scene(text: str, blob: str) -> bool:
    """Reject generic bar/shower openers when the scene has already moved on."""
    t = text.lower()
    # Bar openers during sex/shower
    if any(w in blob for w in ("mouth", "throat", "shower", "cum", "naked", "nipple")):
        if any(
            p in t
            for p in (
                "join you for a drink",
                "empty stool",
                "hoping someone interesting",
                "what brings you",
            )
        ):
            return True
    # Soft hug line during oral
    if any(w in blob for w in ("mouth", "throat", "blow", "suck", "deepthroat")):
        if "pulls her closer under the warm water" in t or "you okay" in t:
            return True
    return False


async def generate_suggestions(
    *,
    history: list[dict[str, Any]],
    last_assistant: str,
) -> tuple[str, str]:
    soft_default, hot_default = _scene_defaults(history, last_assistant)
    model = _get_model()
    # Last ~6 turns only — enough context, less noise.
    recent = _history_snippet(history, limit=6)
    blob = _history_blob(history, last_assistant)

    prompt = (
        "You write the USER's next line in an ongoing adult roleplay.\n"
        "Read ONLY the recent chat below (last few turns). Stay in THAT moment.\n"
        "Write TWO options:\n"
        "1) Soft — gentler / slower, still in the current act\n"
        "2) Bold — more intense / direct, still in the current act\n"
        "Rules:\n"
        "- Max ~18 words each\n"
        "- First person or *action* from the USER only\n"
        "- MUST react to Aria's last line and the current physical situation\n"
        "- If oral/sex/shower is happening, do NOT suggest sitting at a bar or random small talk\n"
        "- FORBIDDEN: interview questions, meta text, 'write two options'\n"
        "Format EXACTLY:\n"
        "1) <soft>\n"
        "2) <bold>\n\n"
        f"Recent chat (last turns):\n{recent}\n\n"
        f"Aria's latest message:\n{(last_assistant or '')[:400]}\n"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Output only two numbered USER reply lines that continue the "
                "exact current beat of the scene."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    try:
        text = await _call_model(
            messages=messages, model=model, max_tokens=100, temperature=0.65
        )
        opts: list[str] = []
        for ln in (text or "").splitlines():
            cleaned = re.sub(r"^\s*[12][\).:\-]\s*", "", ln.strip()).strip().strip("\"'")
            if not cleaned or _looks_like_bad_suggestion(cleaned):
                continue
            if _suggestion_mismatches_scene(cleaned, blob):
                continue
            opts.append(cleaned[:100])
        if len(opts) >= 2:
            return opts[0], opts[1]
        if len(opts) == 1:
            return opts[0], hot_default
    except Exception:
        logger.exception("Failed to generate suggestions")

    return soft_default, hot_default
