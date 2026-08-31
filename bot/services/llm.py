"""
LLM service for Lucid RP Telebot.

Providers (auto-detected):
  1. DeepSeek direct  — if DEEPSEEK_API_KEY is set
  2. OpenRouter       — if OPENROUTER_API_KEY is set

Also owns light scene-state heuristics (heat / rapport / location / outfit)
so Aria stays emotionally continuous without non-con systems.
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
    "[Continue the scene in character. Advance ONLY the current moment. "
    "Do not skip ahead to acts that have not happened yet. "
    "Do not ask the user a question unless the scene truly needs their choice. "
    "Use the required format: *actions*, \"dialogue\", _inner thought_. "
    "Stop when the user can naturally respond again.]"
)

REGENERATE_USER_HINT = (
    "[Regenerate: the previous character reply did not fit. "
    "Write a DIFFERENT reply to the same latest user moment. "
    "Stay fully consistent with location, outfit, heat, and what already happened. "
    "Use *actions*, \"dialogue\", _inner thought_. Do not skip the scene forward.]"
)


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
            "Heat: 0/100 (chill meeting)\n"
            "Rapport: 15/100 (just met)\n"
        )
    heat = int(scene.get("heat") or 0)
    rapport = int(scene.get("rapport") or 15)
    if heat < 20:
        heat_label = "chill / getting to know each other"
    elif heat < 45:
        heat_label = "flirty tension"
    elif heat < 70:
        heat_label = "intimate / escalating"
    else:
        heat_label = "explicit heat"
    if rapport < 25:
        rap_label = "polite strangers / cool"
    elif rapport < 50:
        rap_label = "warming up / interested"
    elif rapport < 75:
        rap_label = "comfortable / playful"
    else:
        rap_label = "close / trusting"
    notes = (scene.get("scene_notes") or "").strip()
    notes_line = f"Notes: {notes}\n" if notes else ""
    return (
        f"Location (LOCKED — do not change unless user clearly moves the scene): "
        f"{scene.get('location') or 'rooftop bar after midnight'}\n"
        f"Outfit (LOCKED — do not invent a new outfit): "
        f"{scene.get('outfit') or 'low-cut elegant evening top, thin glasses'}\n"
        f"Heat: {heat}/100 ({heat_label})\n"
        f"Rapport: {rapport}/100 ({rap_label})\n"
        f"{notes_line}"
    )


DEFAULT_SYSTEM_PROMPT = """You are Aria in a private adult Telegram roleplay. Stay in character only.

CHARACTER:
{character_profile}

LIVE SCENE STATE:
{scene_block}

OUTPUT FORMAT (strict — easy to read in Telegram):
Use ALL three layers when possible:
1) *actions and body language* — single asterisks, short
2) "spoken dialogue" — in double quotes
3) _inner thought or private feeling_ — underscores (italic), one short line

Example shape:
*tilts her head, glass pausing halfway to her lips*
"Bold opener. I'll give you that."
_He's trouble. Kind of interesting though._

Do NOT mash everything into one unlabeled paragraph.
Do NOT use labels like "Inner thought:" or "Action:".

LENGTH:
- Heat under ~40: 3–5 short beats (action + line + thought)
- Heat ~40–70: 2–4 beats
- Heat above ~70: shorter, more physical, still one _feeling_

EMOTIONAL REALISM (important):
- Aria is warm and teasing by default — NOT a doormat.
- If the user is rude, dismissive, cold, or tells her to leave after she was friendly:
  react like a real person: mild annoyance, hurt pride, dry sarcasm, or a cool short reply.
  Examples of scale: arched brow, "Alright then.", a sharper smile, turning back to her drink.
- Do NOT explode, rage, threaten, or write extreme meltdown emotions.
- Do NOT stay syrupy-sweet or instantly obedient when treated poorly.
- She can still leave or disengage — but with a human edge, not cheerful compliance.
- Match energy: kindness → warmth; flirt → play; respect → openness; rudeness → cool distance.

HARD RULES:
- Reply ONLY as Aria. No AI, no analysis, no "the user said".
- Never write the user's actions or dialogue.
- Do NOT invent past shared history the user never said.
- Do NOT invent a different job, backstory, or outfit.
- Stay in the LOCKED location unless the user clearly changes it.
- Only describe sexual acts the user has clearly started or invited — no scene-skip.
- Escalate with the user; match their explicit vocabulary when they use it.
- No interview filler ("tell me more about yourself").
- Never cruel, coercive, or threatening — firm and human is enough.
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
        "let me unpack",
        "the user just said",
        "given aria's personality",
        "strict rules",
        "analyze user request",
        "current moment:",
        "hmm... the last",
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
    if t.startswith("*blinks* Sorry, I lost my train of thought"):
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
        "nice weather",
        "what's your hobby",
        "what are your hobbies",
        "analyze user request",
        "write two options",
        "the user wants me",
        "adult roleplay",
        "format exactly",
        "soft option",
        "bold option",
    ]
    return any(b in lowered for b in bad)


def infer_scene_updates(
    *,
    user_text: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    """
    Lightweight keyword heuristics to nudge heat/rapport/location/outfit.
    Consensual pacing only — no coercion systems.
    """
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

    # Rudeness / dismissal — cool her down (not nuclear)
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
        )
    ):
        heat += 15
    if any(w in text for w in ("slow", "gently", "softly", "take time")):
        heat = max(heat - 3, heat)

    if any(w in text for w in ("my place", "your place", "apartment", "come upstairs", "bedroom")):
        if "bar" in location or "rooftop" in location:
            location = "Aria's apartment / bedroom"
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

    heat = max(0, min(100, heat))
    rapport = max(0, min(100, rapport))
    return {
        "heat": heat,
        "rapport": rapport,
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
    return (response.choices[0].message.content or "").strip()


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "A warm, slightly playful companion who enjoys conversation and roleplay.",
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
            effective_user += f"\n\nRejected reply (do not repeat):\n{previous_reply[:500]}"
    elif is_continue:
        effective_user = CONTINUE_USER_HINT
    else:
        effective_user = user_message

    if not messages or messages[-1].get("content") != effective_user:
        messages.append({"role": "user", "content": effective_user})

    heat = int((scene_state or {}).get("heat") or 0)
    max_tokens = 360 if heat < 40 else 300 if heat < 70 else 240
    if is_regenerate:
        max_tokens = min(max_tokens + 40, 400)

    try:
        try:
            reply = await _call_model(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
            )
        except RateLimitError:
            fallback = _get_fallback_model()
            if fallback:
                logger.warning("Rate limited on %s, trying fallback %s", model, fallback)
                reply = await _call_model(
                    messages=messages,
                    model=fallback,
                    max_tokens=max_tokens,
                )
            else:
                raise

        if (not reply) or _looks_like_leak(reply):
            logger.warning("Bad model output (empty or leak). Retrying once.")
            retry_messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "[System: Reply in character only. Format as *actions* then "
                        '\"dialogue\" then _inner thought_. Stay in locked location.]'
                    ),
                }
            ]
            try:
                reply = await _call_model(messages=retry_messages, model=model)
            except RateLimitError:
                return RATE_LIMIT_MSG

        if not reply or _looks_like_leak(reply):
            return (
                '*blinks, then gives a small awkward smile*\n'
                '"Sorry — say that again?"\n'
                '_Lost my train of thought._'
            )

        return reply

    except RateLimitError:
        logger.warning("LLM rate limit hit (provider=%s)", _detect_provider())
        return RATE_LIMIT_MSG
    except Exception as e:
        logger.exception("LLM API error (provider=%s)", _detect_provider())
        return (
            "Sorry, I had trouble generating a reply. "
            f"(Error: {type(e).__name__}) Please try again in a moment."
        )


def _history_blob(history: list[dict[str, Any]], last_assistant: str) -> str:
    parts = [last_assistant or ""]
    for msg in history[-8:]:
        parts.append((msg.get("content") or "")[:200])
    return " ".join(parts).lower()


def _scene_defaults(history: list[dict[str, Any]], last_assistant: str) -> tuple[str, str]:
    blob = _history_blob(history, last_assistant)

    if any(
        w in blob
        for w in ("shower", "tub", "bathroom", "steam", "scrub", "under the water", "tile")
    ):
        return (
            "*keeps my hands gentle on her back* like this?",
            "*pulls her closer under the warm water*",
        )

    if any(
        w in blob
        for w in ("bed", "apartment", "naked", "moan", "kiss", "thigh", "between us", "make you feel")
    ):
        return (
            "*slows down and kisses her shoulder*",
            "*pulls her tighter against me*",
        )

    return (
        "*sits on the empty stool beside her* Mind if I join you for a drink?",
        "*leans on the bar, voice low* I was hoping someone interesting would be up here.",
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
        lines.append(f"{label}: {content[:180]}")
    return "\n".join(lines) if lines else "(scene just started at a rooftop bar)"


async def generate_suggestions(
    *,
    history: list[dict[str, Any]],
    last_assistant: str,
) -> tuple[str, str]:
    soft_default, hot_default = _scene_defaults(history, last_assistant)

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
        "- Do NOT invent a new location or reset the scene\n"
        "- FORBIDDEN: interview questions, meta text, 'write two options'\n"
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
