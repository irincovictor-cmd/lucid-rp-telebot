"""
AI Horde image generation for Lucid RP Telebot.

Style: 2D anime / illustration (not photorealistic).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

HORDE_API_BASE = "https://aihorde.net/api/v2"
CLIENT_AGENT = "LucidRPTelebot:1.0:https://github.com/irincovictor-cmd/lucid-rp-telebot"

MAX_WAIT_SECONDS = 300
POLL_INTERVAL = 4.0

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ARIA_PROFILE_PATH = DATA_DIR / "aria_profile.webp"

# Fixed character lock for consistency
ARIA_VISUAL = (
    "Aria, 2d anime style, anime girl, young woman, "
    "long black hair, red eyes, thin glasses, fair skin, "
    "large breasts, slim waist, beautiful detailed anime face, "
    "soft playful expression"
)

STYLE_TAGS = (
    "2d anime, anime style, illustration, cel shading, clean line art, "
    "detailed eyes, high quality anime, not photorealistic, not 3d, not realistic photo"
)

NEGATIVE = (
    "photorealistic, realistic photo, 3d, cgi, western comic, "
    "deformed, bad anatomy, extra limbs, blurry, lowres, "
    "text, watermark, child, underage, loli, toddler"
)


def _api_key() -> str:
    return os.getenv("AI_HORDE_API_KEY", "0000000000")


def build_prompt(
    *,
    scene: str,
    character_visual: str = ARIA_VISUAL,
) -> str:
    """Character base + scene + style."""
    scene = (scene or "portrait, looking at viewer").strip()
    return f"{character_visual}, {scene}, {STYLE_TAGS}"


def build_prompt_from_history(
    history: list[dict[str, Any]],
    extra: str = "",
) -> str:
    """
    Infer a short scene description from recent chat, optionally merge user extra.
    """
    bits: list[str] = []
    for msg in history[-8:]:
        content = (msg.get("content") or "").strip()
        if not content or len(content) < 3:
            continue
        # Keep short snippets only
        snippet = content.replace("\n", " ")[:120]
        role = msg.get("role")
        if role == "user":
            bits.append(snippet)
        elif role == "assistant":
            bits.append(snippet)

    scene_from_chat = " ".join(bits[-4:]) if bits else "intimate scene with Aria"
    if extra.strip():
        scene = f"{extra.strip()}, based on recent roleplay: {scene_from_chat[:200]}"
    else:
        scene = f"scene from roleplay: {scene_from_chat[:280]}"

    # Keep prompt length reasonable for workers
    if len(scene) > 400:
        scene = scene[:400]
    return build_prompt(scene=scene)


async def generate_image(
    *,
    prompt: str,
    negative_prompt: str = NEGATIVE,
    nsfw: bool = True,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> bytes | None:
    """Generate via AI Horde. Optional on_progress(status_text) callback."""
    full_prompt = f"{prompt} ### {negative_prompt}"

    payload: dict[str, Any] = {
        "prompt": full_prompt,
        "params": {
            "width": 512,
            "height": 768,
            "steps": 30,
            "cfg_scale": 7,
            "sampler_name": "k_euler",
            "n": 1,
        },
        "nsfw": nsfw,
        "censor_nsfw": False,
        "r2": True,
        "trusted_workers": False,
        "models": [],
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
            await progress("Submitting to AI Horde…")
            resp = await client.post(
                f"{HORDE_API_BASE}/generate/async",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error("Horde image submit failed: %s %s", resp.status_code, resp.text)
                await progress("Submit failed.")
                return None

            data = resp.json()
            job_id = data.get("id")
            if not job_id:
                logger.error("Horde image no job id: %s", data)
                return None

            await progress("Queued on free workers (can take 30s–3min)…")

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

                # Periodic wait updates
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

            await progress("Timed out waiting for free workers.")
            return None

    except Exception:
        logger.exception("Horde image generation error")
        return None


async def ensure_aria_profile_image(
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> Path | None:
    """Cached 2D anime Aria portrait."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ARIA_PROFILE_PATH.exists() and ARIA_PROFILE_PATH.stat().st_size > 1000:
        return ARIA_PROFILE_PATH

    prompt = build_prompt(
        scene=(
            "upper body portrait, looking at viewer, soft smile, "
            "elegant casual evening top, rooftop bar night lights background"
        )
    )
    data = await generate_image(
        prompt=prompt,
        nsfw=False,
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
    """
    Generate anime scene image.
    If scene_hint empty, uses recent chat history.
    """
    history = history or []
    if scene_hint.strip():
        prompt = build_prompt_from_history(history, extra=scene_hint)
    elif history:
        prompt = build_prompt_from_history(history)
    else:
        prompt = build_prompt(scene="portrait, looking at viewer")

    return await generate_image(prompt=prompt, nsfw=True, on_progress=on_progress)
