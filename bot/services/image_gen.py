"""
AI Horde image generation for Lucid RP Telebot.

Free community workers: https://aihorde.net
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HORDE_API_BASE = "https://aihorde.net/api/v2"
CLIENT_AGENT = "LucidRPTelebot:1.0:https://github.com/irincovictor-cmd/lucid-rp-telebot"

MAX_WAIT_SECONDS = 300
POLL_INTERVAL = 4.0

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ARIA_PROFILE_PATH = DATA_DIR / "aria_profile.webp"

ARIA_PROFILE_PROMPT = (
    "portrait of Aria, young adult woman, warm playful expression, soft smile, "
    "elegant casual evening look, rooftop bar at night, city lights bokeh background, "
    "realistic, natural skin, detailed face, looking at viewer, soft lighting, "
    "high quality, photorealistic"
)
ARIA_PROFILE_NEGATIVE = (
    "lowres, blurry, deformed, extra limbs, bad anatomy, text, watermark, "
    "child, underage, loli"
)


def _api_key() -> str:
    return os.getenv("AI_HORDE_API_KEY", "0000000000")


async def generate_image(
    *,
    prompt: str,
    negative_prompt: str = "",
    nsfw: bool = True,
) -> bytes | None:
    """
    Generate an image via AI Horde. Returns image bytes, or None on failure.
    """
    neg = negative_prompt or (
        "lowres, blurry, deformed, bad anatomy, extra limbs, text, watermark, "
        "child, underage, loli"
    )

    payload: dict[str, Any] = {
        "prompt": f"{prompt} ### {neg}",
        "params": {
            "width": 512,
            "height": 768,
            "steps": 25,
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

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{HORDE_API_BASE}/generate/async",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error("Horde image submit failed: %s %s", resp.status_code, resp.text)
                return None

            job_id = resp.json().get("id")
            if not job_id:
                logger.error("Horde image no job id: %s", resp.text)
                return None

            elapsed = 0.0
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
                    return None

                if status.get("done"):
                    gens = status.get("generations") or []
                    if not gens:
                        return None
                    img_url = gens[0].get("img")
                    if not img_url:
                        return None
                    img_resp = await client.get(img_url, timeout=60.0)
                    if img_resp.status_code >= 400:
                        return None
                    return img_resp.content

            logger.error("Horde image timed out")
            return None

    except Exception:
        logger.exception("Horde image generation error")
        return None


async def ensure_aria_profile_image() -> Path | None:
    """
    Return path to cached Aria profile image, generating it once if missing.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ARIA_PROFILE_PATH.exists() and ARIA_PROFILE_PATH.stat().st_size > 1000:
        return ARIA_PROFILE_PATH

    logger.info("Generating Aria profile image via AI Horde...")
    data = await generate_image(
        prompt=ARIA_PROFILE_PROMPT,
        negative_prompt=ARIA_PROFILE_NEGATIVE,
        nsfw=False,
    )
    if not data:
        return None

    ARIA_PROFILE_PATH.write_bytes(data)
    return ARIA_PROFILE_PATH


async def generate_scene_image(scene_hint: str, character_name: str = "Aria") -> bytes | None:
    """Build a simple scene prompt and generate."""
    prompt = (
        f"{character_name}, {scene_hint}, realistic, detailed, "
        "natural lighting, high quality, photorealistic"
    )
    return await generate_image(prompt=prompt, nsfw=True)
