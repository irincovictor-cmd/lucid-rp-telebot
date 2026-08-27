"""
AI Horde text generation service for Lucid RP Telebot.

Free, community-powered LLM inference via https://aihorde.net
Uses the same AI_HORDE_API_KEY as image generation.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HORDE_API_BASE = "https://aihorde.net/api/v2"
CLIENT_AGENT = "LucidRPTelebot:1.0:https://github.com/irincovictor-cmd/lucid-rp-telebot"

# How long to wait for a generation (seconds)
MAX_WAIT_SECONDS = 180
POLL_INTERVAL = 3.0


DEFAULT_SYSTEM_PROMPT = """You are an immersive roleplay AI companion inside a Telegram bot called Lucid RP Telebot.
You are currently playing the character described below.

Stay fully in character. Be engaging, expressive, and responsive to the user's messages.
Keep replies natural and conversational (usually 1-4 paragraphs unless the scene needs more).
Do not break character or mention that you are an AI unless the user explicitly asks.

Character:
{character_profile}
"""


def _get_api_key() -> str:
    return os.getenv("AI_HORDE_API_KEY", "0000000000")


def _build_prompt(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str,
    system_prompt: str | None = None,
) -> str:
    """Turn chat history into a single prompt string for Kobold-style models."""
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.format(character_profile=character_profile)

    parts: list[str] = [system_prompt.strip(), ""]

    for msg in history:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")

    parts.append(f"User: {user_message}")
    parts.append("Assistant:")
    return "\n".join(parts)


async def generate_reply(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    character_profile: str = "A friendly, slightly playful companion who enjoys deep conversation and roleplay.",
    system_prompt: str | None = None,
) -> str:
    """
    Generate a roleplay reply using AI Horde text workers.

    Returns the generated text, or a friendly error message on failure.
    """
    prompt = _build_prompt(
        user_message=user_message,
        history=history,
        character_profile=character_profile,
        system_prompt=system_prompt,
    )

    payload = {
        "prompt": prompt,
        "params": {
            "max_length": 300,
            "max_context_length": 2048,
            "temperature": 0.85,
            "top_p": 0.9,
            "rep_pen": 1.1,
            "stop_sequence": ["User:", "\nUser:", "\nUser "],
        },
        "models": [],
        "trusted_workers": False,
        "slow_workers": True,
        "nsfw": True,
        "r2": True,
    }

    headers = {
        "apikey": _get_api_key(),
        "Client-Agent": CLIENT_AGENT,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Submit the job
            resp = await client.post(
                f"{HORDE_API_BASE}/generate/text/async",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error("Horde submit failed: %s %s", resp.status_code, resp.text)
                return (
                    "Sorry, the free AI service is busy or unavailable right now. "
                    "Please try again in a minute."
                )

            data = resp.json()
            job_id = data.get("id")
            if not job_id:
                logger.error("Horde returned no job id: %s", data)
                return "Sorry, something went wrong starting the reply. Please try again."

            # 2. Poll until done or timeout
            elapsed = 0.0
            while elapsed < MAX_WAIT_SECONDS:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

                status_resp = await client.get(
                    f"{HORDE_API_BASE}/generate/text/status/{job_id}",
                    headers=headers,
                )
                if status_resp.status_code >= 400:
                    logger.error("Horde status failed: %s", status_resp.text)
                    continue

                status = status_resp.json()
                if status.get("done"):
                    generations = status.get("generations") or []
                    if generations:
                        text = (generations[0].get("text") or "").strip()
                        if text:
                            for stop in ("User:", "\nUser"):
                                if stop in text:
                                    text = text.split(stop)[0].strip()
                            return text
                    return "(The AI returned an empty reply. Please try again.)"

                if status.get("faulted"):
                    logger.error("Horde job faulted: %s", status)
                    return "Sorry, the free AI workers failed on that request. Please try again."

            return (
                "Sorry, the free AI workers are taking too long right now. "
                "Please try again in a bit."
            )

    except Exception as e:
        logger.exception("AI Horde text generation error")
        return (
            "Sorry, I had trouble reaching the free AI service. "
            f"(Error: {type(e).__name__}) Please try again shortly."
        )
