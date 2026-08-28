"""
AI Horde image generation for Lucid RP Telebot.

Aligned with proven JustAAA / Nova Anime XL settings.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

HORDE_API_BASE = "https://aihorde.net/api/v2"
CLIENT_AGENT = "LucidRPTelebot:1.0:https://github.com/irincovictor-cmd/lucid-rp-telebot"

MAX_WAIT_SECONDS = 360
POLL_INTERVAL = 4.0

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ARIA_PROFILE_PATH = DATA_DIR / "aria_profile.webp"

# Pin the model that followed instructions well in JustAAA
DEFAULT_MODEL = os.getenv("AI_HORDE_MODEL", "Nova Anime XL")

# Character identity lock (Aria) — adult, consistent look
ARIA_VISUAL = (
    "Mature woman, Aria, long black hair, red eyes, thin glasses, "
    "fair skin, large breasts, slim waist, seductive expression, "
    "detailed eyes, beautiful detailed anime face"
)

# Quality tags from your working JustAAA prompt
QUALITY_TAGS = (
    "masterpiece, best quality, amazing quality, very aesthetic, "
    "high resolution, ultra-detailed, absurdres, newest, "
    "depth of field, volumetric lighting"
)

# Default profile scene (R18-leaning character card, not vanilla)
ARIA_PROFILE_SCENE = (
    "upper body portrait, looking at viewer, seductive expression, "
    "low-cut evening top, soft cleavage, rooftop bar night lights background"
)

NEGATIVE = (
    "modern, recent, old, oldest, cartoon, graphic, text, painting, crayon, graphite, "
    "abstract, glitch, deformed, mutated, ugly, disfigured, long body, lowres, "
    "bad anatomy, bad hands, missing fingers, extra digit, fewer digits, cropped, "
    "very displeasing, (worst quality, bad quality:1.2), sketch, jpeg artifacts, "
    "signature, watermark, username, simple background, conjoined, ai-generated, "
    "photorealistic, realistic photo, 3d, cgi, child, underage, loli, toddler"
)


def _api_key() -> str:
    return os.getenv("AI_HORDE_API_KEY", "0000000000")


def build_prompt(
    *,
    scene: str,
    character_visual: str = ARIA_VISUAL,
) -> str:
    """Quality tags + character lock + scene (JustAAA-style order)."""
    scene = (scene or "portrait, looking at viewer").strip()
    return f"{QUALITY_TAGS}, {character_visual}, {scene}"


def build_prompt_from_history(
    history: list[dict[str, Any]],
    extra: str = "",
) -> str:
    """
    Character lock + optional user instructions + recent chat context.
    """
    bits: list[str] = []
    for msg in history[-8:]:
        content = (msg.get("content") or "").strip()
        if not content or len(content) < 3:
            continue
        snippet = content.replace("\n", " ")[:120]
        bits.append(snippet)

    scene_from_chat = " ".join(bits[-4:]) if bits else "intimate scene"

    if extra.strip():
        # User instructions lead; chat only as light context
        scene = f"{extra.strip()}, {scene_from_chat[:160]}"
    else:
        scene = f"{scene_from_chat[:280]}"

    if len(scene) > 420:
        scene = scene[:420]
    return build_prompt(scene=scene)


async def generate_image(
    *,
    prompt: str,
    negative_prompt: str = NEGATIVE,
    nsfw: bool = True,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> bytes | None:
    """Generate via AI Horde using Nova Anime XL-style settings."""
    full_prompt = f"{prompt} ### {negative_prompt}"

    payload: dict[str, Any] = {
        "prompt": full_prompt,
        "params": {
            "width": 1024,
            "height": 1024,
            "steps": 25,
            "cfg_scale": 5,
            "sampler_name": "k_dpmpp_sde",
            "karras": True,
            "clip_skip": 2,
            "n": 1,
            "denoising_strength": 0.75,
        },
        "nsfw": nsfw,
        "censor_nsfw": False,
        "r2": True,
        "trusted_workers": False,
        "slow_workers": True,
        "models": [DEFAULT_MODEL],
        "replacement_filter": True,
    }

    headers = {
        "apikey": _api_key(),
        "Client-Agent": CLIENT_AGENT,
        "Content-Type": "application/json",
    }

    async def progress(msg: str) -> None:
        if on_progress:
            try:
                await on_progress(msg)
            except Exception:
                pass

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await progress(f"Submitting to AI Horde ({DEFAULT_MODEL})…")
            resp = await client.post(
                f"{HORDE_API_BASE}/generate/async",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error("Horde image submit failed: %s %s", resp.status_code, resp.text)
                # Fallback: retry without pinned model if model unavailable
                if "model" in resp.text.lower() or resp.status_code == 400:
                    await progress("Pinned model busy/unavailable — retrying any anime worker…")
                    payload["models"] = []
                    resp = await client.post(
                        f"{HORDE_API_BASE}/generate/async",
                        json=payload,
                        headers=headers,
                    )
                if resp.status_code >= 400:
                    await progress("Submit failed.")
                    return None

            data = resp.json()
            job_id = data.get("id")
            if not job_id:
                logger.error("Horde image no job id: %s", data)
                return None

            await progress("Queued (Nova Anime XL can take 1–3 min)…")

            elapsed = 0.0
            last_announce = 0.0
            while elapsed < MAX_WAIT_SECONDS:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

                status_resp = await client.get(
                    f"{HORDE_API_BASE}/generate/status/{job_id}",
                    headers=headers,
                )
                if status_resp.status_code >= 400:
                    continue

                status = status_resp.json()
                if status.get("faulted"):
                    logger.error("Horde image job faulted: %s", status)
                    await progress("Generation failed on worker.")
                    return None

                if elapsed - last_announce >= 20:
                    wait = status.get("wait_time")
                    queue = status.get("queue_position")
                    if wait is not None:
                        await progress(f"Still working… ~{wait}s left (queue {queue})")
                    else:
                        await progress(f"Still generating… {int(elapsed)}s elapsed")
                    last_announce = elapsed

                if status.get("done"):
                    gens = status.get("generations") or []
                    if not gens:
                        return None
                    img_url = gens[0].get("img")
                    if not img_url:
                        return None
                    await progress("Downloading image…")
                    img_resp = await client.get(img_url, timeout=60.0)
                    if img_resp.status_code >= 400:
                        return None
                    return img_resp.content

            await progress("Timed out waiting for workers.")
            return None

    except Exception:
        logger.exception("Horde image generation error")
        return None


async def ensure_aria_profile_image(
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> Path | None:
    """Cached Aria portrait using new R18-aligned prompt."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ARIA_PROFILE_PATH.exists() and ARIA_PROFILE_PATH.stat().st_size > 1000:
        return ARIA_PROFILE_PATH

    prompt = build_prompt(scene=ARIA_PROFILE_SCENE)
    data = await generate_image(
        prompt=prompt,
        nsfw=True,
        on_progress=on_progress,
    )
    if not data:
        return None

    ARIA_PROFILE_PATH.write_bytes(data)
    return ARIA_PROFILE_PATH


async def generate_scene_image(
    *,
    scene_hint: str = "",
    history: list[dict[str, Any]] | None = None,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> bytes | None:
    """Generate scene: user hint and/or chat history + Aria lock."""
    history = history or []
    if scene_hint.strip() or history:
        prompt = build_prompt_from_history(history, extra=scene_hint)
    else:
        prompt = build_prompt(scene=ARIA_PROFILE_SCENE)

    return await generate_image(prompt=prompt, nsfw=True, on_progress=on_progress)
