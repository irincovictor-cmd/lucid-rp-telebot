"""
AI Horde image generation for Lucid RP Telebot.

By default uses ANY available worker (fastest queue).
Optional AI_HORDE_MODEL can pin a model, or "auto" picks a live anime model.
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

MAX_WAIT_SECONDS = 240  # fail sooner instead of hanging forever
POLL_INTERVAL = 4.0

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ARIA_PROFILE_PATH = DATA_DIR / "aria_profile.webp"

# "" or "any" = fastest (any worker). "auto" = best live anime model. Or pin e.g. "Nova Anime XL"
MODEL_SETTING = os.getenv("AI_HORDE_MODEL", "any").strip()

# Preferred anime/NSFW-capable models if using auto
PREFERRED_MODELS = [
    "Nova Anime XL",
    "Anything v5",
    "Anything Diffusion",
    "Grapefruit Hentai",
    "Hentai Diffusion",
    "Animagine XL",
    "Prefect Pony",
    "Pony Diffusion XL",
    "Flat-2D Animerge",
    "Mistoon Anime",
    "Rev Animated",
    "Dreamshaper",
    "stable_diffusion",
]

ARIA_VISUAL = (
    "Mature woman, Aria, long black hair, red eyes, thin glasses, "
    "fair skin, large breasts, slim waist, seductive expression, "
    "detailed eyes, beautiful detailed anime face"
)

QUALITY_TAGS = (
    "masterpiece, best quality, amazing quality, very aesthetic, "
    "high resolution, ultra-detailed, absurdres, newest, "
    "depth of field, volumetric lighting"
)

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
    scene = (scene or "portrait, looking at viewer").strip()
    return f"{QUALITY_TAGS}, {character_visual}, {scene}"


def build_prompt_from_history(
    history: list[dict[str, Any]],
    extra: str = "",
) -> str:
    bits: list[str] = []
    for msg in history[-8:]:
        content = (msg.get("content") or "").strip()
        if not content or len(content) < 3:
            continue
        snippet = content.replace("\n", " ")[:120]
        bits.append(snippet)

    scene_from_chat = " ".join(bits[-4:]) if bits else "intimate scene"

    if extra.strip():
        scene = f"{extra.strip()}, {scene_from_chat[:160]}"
    else:
        scene = f"{scene_from_chat[:280]}"

    if len(scene) > 420:
        scene = scene[:420]
    return build_prompt(scene=scene)


async def _fetch_model_status(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    try:
        resp = await client.get(
            f"{HORDE_API_BASE}/status/models",
            params={"type": "image"},
            headers={"Client-Agent": CLIENT_AGENT},
            timeout=15.0,
        )
        if resp.status_code >= 400:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        logger.exception("Failed to fetch Horde model status")
        return []


def _pick_models(status_list: list[dict[str, Any]]) -> tuple[list[str], str]:
    """
    Returns (models list for request, human label).
    Empty models list = any worker (usually fastest).
    """
    setting = MODEL_SETTING.lower()

    if setting in ("", "any", "auto-any", "fast"):
        return [], "any available worker (fastest)"

    # Index live models with at least 1 worker
    live: dict[str, dict[str, Any]] = {}
    for m in status_list:
        name = m.get("name") or ""
        count = int(m.get("count") or 0)
        if name and count > 0:
            live[name] = m

    if setting not in ("auto", "best"):
        # User pinned a specific model
        if MODEL_SETTING in live:
            info = live[MODEL_SETTING]
            eta = info.get("eta", "?")
            return [MODEL_SETTING], f"{MODEL_SETTING} (workers={info.get('count')}, eta~{eta}s)"
        # Pinned but offline -> fall back to any
        return [], f"{MODEL_SETTING} offline — using any worker"

    # auto: pick preferred anime model with most workers / lowest eta
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name in PREFERRED_MODELS:
        if name in live:
            candidates.append((name, live[name]))

    if not candidates:
        return [], "no preferred models online — any worker"

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple:
        name, info = item
        count = int(info.get("count") or 0)
        eta = info.get("eta")
        try:
            eta_v = float(eta)
        except (TypeError, ValueError):
            eta_v = 9999.0
        # More workers, lower ETA first
        return (-count, eta_v)

    candidates.sort(key=sort_key)
    name, info = candidates[0]
    return [name], f"{name} (workers={info.get('count')}, eta~{info.get('eta')}s)"


def _payload(
    *,
    full_prompt: str,
    nsfw: bool,
    width: int,
    height: int,
    steps: int,
    models: list[str],
) -> dict[str, Any]:
    return {
        "prompt": full_prompt,
        "params": {
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": 5,
            "sampler_name": "k_euler",
            "karras": True,
            "clip_skip": 2,
            "n": 1,
        },
        "nsfw": nsfw,
        "censor_nsfw": False,
        "r2": True,
        "trusted_workers": False,
        "slow_workers": True,
        "models": models,
        "replacement_filter": True,
    }


async def generate_image(
    *,
    prompt: str,
    negative_prompt: str = NEGATIVE,
    nsfw: bool = True,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> bytes | None:
    full_prompt = f"{prompt} ### {negative_prompt}"
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
            status_list = await _fetch_model_status(client)
            models, label = _pick_models(status_list)
            await progress(f"Using: {label}")

            # Prefer small/fast jobs first so free keys don't hit KudosUpfront
            attempts = [
                {"label": "512x768 fast", "width": 512, "height": 768, "steps": 20, "models": models},
                {"label": "512x512 fast", "width": 512, "height": 512, "steps": 20, "models": models},
                {"label": "any worker 512x768", "width": 512, "height": 768, "steps": 20, "models": []},
            ]

            job_id = None
            for attempt in attempts:
                payload = _payload(
                    full_prompt=full_prompt,
                    nsfw=nsfw,
                    width=attempt["width"],
                    height=attempt["height"],
                    steps=attempt["steps"],
                    models=attempt["models"],
                )
                await progress(f"Submitting ({attempt['label']})…")
                resp = await client.post(
                    f"{HORDE_API_BASE}/generate/async",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.error(
                        "Horde submit failed: %s %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    continue

                data = resp.json()
                job_id = data.get("id")
                if job_id:
                    break

            if not job_id:
                await progress(
                    "Could not start image job (kudos/workers). "
                    "Try again later or earn kudos at aihorde.net"
                )
                return None

            await progress("In queue…")

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
                    await progress("Worker failed this job.")
                    return None

                if elapsed - last_announce >= 15:
                    wait = status.get("wait_time")
                    queue = status.get("queue_position")
                    processing = status.get("processing")
                    if wait is not None:
                        await progress(
                            f"Queue {queue} | ~{wait}s | processing={processing}"
                        )
                    else:
                        await progress(f"Waiting… {int(elapsed)}s")
                    last_announce = elapsed

                if status.get("done"):
                    gens = status.get("generations") or []
                    if not gens:
                        return None
                    img_url = gens[0].get("img")
                    model_used = gens[0].get("model") or "unknown"
                    if not img_url:
                        return None
                    await progress(f"Done via {model_used}. Downloading…")
                    img_resp = await client.get(img_url, timeout=60.0)
                    if img_resp.status_code >= 400:
                        return None
                    return img_resp.content

            await progress("Timed out (queue too long). Try /img again later.")
            return None

    except Exception:
        logger.exception("Horde image generation error")
        return None


async def ensure_aria_profile_image(
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> Path | None:
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
    history = history or []
    if scene_hint.strip() or history:
        prompt = build_prompt_from_history(history, extra=scene_hint)
    else:
        prompt = build_prompt(scene=ARIA_PROFILE_SCENE)

    return await generate_image(prompt=prompt, nsfw=True, on_progress=on_progress)
