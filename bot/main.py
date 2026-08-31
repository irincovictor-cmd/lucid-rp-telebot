import asyncio
import logging
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto, Update
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from bot.db import database as db
from bot.services import image_gen, llm

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARIA_DIR = PROJECT_ROOT / "data" / "aria"
ARIA_PROFILE_CANDIDATES = (
    "profile.png",
    "profile.jpg",
    "profile.jpeg",
    "profile.webp",
    "Profile.png",
    "Profile.jpg",
)
ARIA_INTRO_GLOBS = ("intro_*.png", "intro_*.jpg", "intro_*.jpeg", "intro_*.webp")

ARIA_CARD = (
    "Name: Aria\n"
    "Age: late 20s, mature woman\n"
    "Look: long black hair, red eyes, thin glasses, fair skin; curvy (full bust, slim waist, thick thighs)\n"
    "Outfit default: low-cut elegant evening top, thin glasses\n"
    "Setting default: rooftop bar after midnight, city lights, soft music\n"
    "Personality: warm, curious, slightly teasing; not a doormat — rudeness gets cool mild annoyance\n"
    "Relationship: single / available unless the user establishes otherwise — never invent an ex or 'someone'\n"
    "Style: *actions* then \"dialogue\" then _inner thought_"
)

ARIA_PROFILE_JSON = {
    "name": "Aria",
    "setting": "Rooftop bar after midnight",
    "personality": (
        "Warm, curious, slightly teasing. Not a doormat. "
        "Single unless user says otherwise. Never invent partners or life story."
    ),
    "tone": '*actions*, "dialogue", _inner thought_',
    "appearance": (
        "Long black hair, red eyes, thin glasses, curvy figure, "
        "low-cut elegant evening top"
    ),
}

BOT_WELCOME = (
    "💖 **HoneyChat / Lucid RP** — private 18+ AI roleplay\n\n"
    "Talk dirty or deep. Stay in a scene.\n\n"
    "⚠️ Adults only (18+).\n\n"
    "How Aria writes:\n"
    "• *actions* — body language\n"
    "• \"dialogue\" — spoken words\n"
    "• _inner thought_ — private feeling\n\n"
    "Buttons: Continue · Change · Soft / Bold · Image\n\n"
    "/start · /help · /new · /img"
)

ARIA_SCENE_INTRO = (
    "🌙 *Aria*\n\n"
    "A quiet rooftop bar after midnight. Soft music, city lights below, "
    "one empty stool beside a woman who looks like she's been waiting for something "
    "interesting to happen.\n\n"
    "*turns toward you — warm eyes, a small playful smile, glass in hand*\n"
    '"You\'re new here… or at least, I haven\'t seen you around. What brings you up here tonight?"\n'
    "_Cute. Let's see if he's interesting or just loud._"
)

_suggestion_store: dict[str, tuple[str, str]] = {}


async def _safe_answer(query, text: str | None = None) -> None:
    try:
        if text:
            await query.answer(text)
        else:
            await query.answer()
    except (TimedOut, NetworkError, BadRequest) as e:
        logger.warning("callback answer failed (ignored): %s", e)


async def _send_formatted(target_message, text: str, reply_markup=None) -> None:
    """Send RP text; tolerate Markdown parse errors and short network blips."""

    async def _send(parse_mode: str | None) -> None:
        kwargs: dict = {"reply_markup": reply_markup}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        await target_message.reply_text(text, **kwargs)

    try:
        await _send("Markdown")
        return
    except BadRequest:
        pass  # fall through to plain
    except (TimedOut, NetworkError) as e:
        logger.warning("Telegram send (markdown) network blip: %s", e)
        await asyncio.sleep(0.8)

    try:
        await _send(None)
    except (TimedOut, NetworkError) as e:
        logger.warning("Telegram send failed after retry: %s", e)
    except BadRequest as e:
        logger.warning("Telegram send BadRequest: %s", e)


def _rp_keyboard(
    soft: str | None = None, bold: str | None = None, key: str | None = None
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Continue ▶", callback_data="rp_continue"),
            InlineKeyboardButton("Change 🔄", callback_data="rp_change"),
        ]
    ]
    if soft and bold and key:
        rows.append(
            [
                InlineKeyboardButton("Soft 💬", callback_data=f"rp_sugg:{key}:0"),
                InlineKeyboardButton("Bold 🔥", callback_data=f"rp_sugg:{key}:1"),
            ]
        )
    rows.append([InlineKeyboardButton("🖼️ Image", callback_data="rp_img")])
    return InlineKeyboardMarkup(rows)


def _find_aria_profile() -> Path | None:
    for name in ARIA_PROFILE_CANDIDATES:
        p = ARIA_DIR / name
        if p.is_file() and p.stat().st_size > 500:
            return p
    return None


def _find_aria_intro_images() -> list[Path]:
    found: list[Path] = []
    if not ARIA_DIR.is_dir():
        return found
    for pattern in ARIA_INTRO_GLOBS:
        found.extend(sorted(ARIA_DIR.glob(pattern)))
    uniq: list[Path] = []
    seen = set()
    for p in found:
        if p.resolve() in seen:
            continue
        if p.is_file() and p.stat().st_size > 500:
            seen.add(p.resolve())
            uniq.append(p)
        if len(uniq) >= 3:
            break
    return uniq


async def _set_bot_profile_photo(application: Application) -> None:
    path = _find_aria_profile()
    if not path:
        logger.info("No data/aria/profile.* found — bot avatar unchanged")
        return
    try:
        from telegram import InputProfilePhotoStatic

        with path.open("rb") as f:
            await application.bot.set_my_profile_photo(
                photo=InputProfilePhotoStatic(photo=f)
            )
        logger.info("Bot Telegram profile photo set from %s", path.name)
    except Exception as e:
        logger.warning("set_my_profile_photo failed: %s", e)


async def _send_aria_intro_gallery(update: Update) -> None:
    paths = _find_aria_intro_images()
    if not paths:
        try:
            await update.message.reply_text(
                "Add intro_1.png–intro_3.png under data/aria/ for the gallery.\n"
                "profile.png is the bot avatar only."
            )
        except (TimedOut, NetworkError) as e:
            logger.warning("intro gallery text failed: %s", e)
        return
    try:
        if len(paths) == 1:
            with paths[0].open("rb") as f:
                await update.message.reply_photo(
                    photo=InputFile(f, filename=paths[0].name), caption="Aria"
                )
            return
        media: list[InputMediaPhoto] = []
        handles = []
        try:
            for i, p in enumerate(paths):
                fh = p.open("rb")
                handles.append(fh)
                media.append(
                    InputMediaPhoto(media=fh, caption="Aria" if i == 0 else None)
                )
            await update.message.reply_media_group(media=media)
        finally:
            for fh in handles:
                try:
                    fh.close()
                except Exception:
                    pass
    except (TimedOut, NetworkError) as e:
        logger.warning("intro gallery send failed: %s", e)


async def _get_or_create_default_character() -> int:
    cid = await db.async_find_builtin_character_id()
    if cid is not None:
        await db.async_update_character_profile(
            cid,
            name="Aria",
            short_desc="Warm, teasing companion at a late-night rooftop bar.",
            profile_json=ARIA_PROFILE_JSON,
        )
        return cid
    return await db.async_create_character(
        owner_id=None,
        name="Aria",
        short_desc="Warm, teasing companion at a late-night rooftop bar.",
        profile_json=ARIA_PROFILE_JSON,
        is_public=True,
    )


def _character_profile_text(_character_id: int) -> str:
    return ARIA_CARD


async def _nudge_scene_from_user(conversation_id: int, user_text: str) -> dict:
    current = await db.async_get_scene_state(conversation_id)
    updated = llm.infer_scene_updates(user_text=user_text, current=current)
    return await db.async_update_scene_state(
        conversation_id,
        heat=updated["heat"],
        rapport=updated["rapport"],
        location=updated["location"],
        outfit=updated["outfit"],
        scene_notes=updated.get("scene_notes"),
    )


async def _generate_and_send_image(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    scene_hint: str = "",
    history: list | None = None,
) -> None:
    chat_id = update.effective_chat.id
    try:
        status = await context.bot.send_message(
            chat_id,
            "🖼️ Generating 2D anime image…\nFree AI Horde queue — please wait.",
        )
    except (TimedOut, NetworkError) as e:
        logger.warning("image status message failed: %s", e)
        return

    async def on_progress(msg: str) -> None:
        try:
            await status.edit_text(f"🖼️ {msg}")
        except Exception:
            pass
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        except Exception:
            pass

    data = await image_gen.generate_scene_image(
        scene_hint=scene_hint,
        history=history or [],
        on_progress=on_progress,
    )
    if not data:
        try:
            await status.edit_text(
                "Image failed or timed out. Free workers may be busy — try again later."
            )
        except Exception:
            pass
        return
    try:
        await status.delete()
    except Exception:
        pass
    try:
        await context.bot.send_photo(
            chat_id,
            photo=InputFile(BytesIO(data), filename="scene.webp"),
            caption=(scene_hint[:200] if scene_hint else "From current scene"),
        )
    except (TimedOut, NetworkError) as e:
        logger.warning("image send failed: %s", e)


async def _reply_with_suggestions(
    *,
    target_message,
    conversation_id: int,
    reply: str,
    history: list,
) -> None:
    if llm.is_system_failure_reply(reply):
        try:
            await target_message.reply_text(reply)
        except (TimedOut, NetworkError) as e:
            logger.warning("failure reply send failed: %s", e)
        return

    try:
        soft, bold = await llm.generate_suggestions(
            history=history, last_assistant=reply
        )
    except Exception:
        logger.exception("suggestion generation failed; sending reply without Soft/Bold")
        soft, bold = None, None

    key = None
    if soft and bold:
        key = f"{conversation_id}_{abs(hash(reply)) % 10_000_000}"
        _suggestion_store[key] = (soft, bold)
        if len(_suggestion_store) > 200:
            for old in list(_suggestion_store.keys())[:50]:
                _suggestion_store.pop(old, None)

    await _send_formatted(
        target_message,
        reply,
        reply_markup=_rp_keyboard(soft, bold, key),
    )


async def _save_assistant_if_ok(conversation_id: int, reply: str) -> None:
    if not llm.is_system_failure_reply(reply) and not llm._looks_like_leak(reply):
        await db.async_add_message(conversation_id, "assistant", reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)

    try:
        await update.message.reply_text(BOT_WELCOME, parse_mode="Markdown")
    except (TimedOut, NetworkError, BadRequest):
        try:
            await update.message.reply_text(BOT_WELCOME)
        except (TimedOut, NetworkError):
            pass

    await _send_aria_intro_gallery(update)
    await _send_formatted(
        update.message,
        ARIA_SCENE_INTRO,
        reply_markup=_rp_keyboard(
            "*sits beside her* Just looking for a quiet drink.",
            "*smirks* Looking for trouble. Found any?",
            "intro",
        ),
    )
    _suggestion_store["intro"] = (
        "*sits beside her* Just looking for a quiet drink.",
        "*smirks* Looking for trouble. Found any?",
    )

    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    existing = await db.async_get_recent_messages(conversation_id, limit=1)
    if not existing:
        await db.async_add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)
        await db.async_reset_scene_state(conversation_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "**How to use**\n\n"
        "• *actions* — what she does\n"
        "• \"dialogue\" — what she says\n"
        "• _inner thought_ — private feeling\n\n"
        "`/new` resets chat and scene state.\n"
    )
    try:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except (BadRequest, TimedOut, NetworkError):
        try:
            await update.message.reply_text(help_text)
        except (TimedOut, NetworkError):
            pass


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)

    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    await db.async_clear_conversation(conversation_id)

    await db.async_add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)
    try:
        await update.message.reply_text(
            "Memory and scene state cleared. Starting fresh with Aria…"
        )
    except (TimedOut, NetworkError):
        pass
    await _send_aria_intro_gallery(update)
    await _send_formatted(
        update.message,
        ARIA_SCENE_INTRO,
        reply_markup=_rp_keyboard(
            "*sits beside her* Just looking for a quiet drink.",
            "*smirks* Looking for trouble. Found any?",
            "intro",
        ),
    )
    _suggestion_store["intro"] = (
        "*sits beside her* Just looking for a quiet drink.",
        "*smirks* Looking for trouble. Found any?",
    )


async def img_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    desc = " ".join(context.args).strip() if context.args else ""
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    history = await db.async_get_recent_messages(conversation_id, limit=12)
    state = await db.async_get_scene_state(conversation_id)
    if not desc:
        desc = f"{state.get('location', '')}, {state.get('outfit', '')}"
    await _generate_and_send_image(
        update=update, context=context, scene_hint=desc, history=history
    )


async def img_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await _safe_answer(query, "Generating image from scene…")
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    history = await db.async_get_recent_messages(conversation_id, limit=12)
    state = await db.async_get_scene_state(conversation_id)
    hint = f"{state.get('location', '')}, {state.get('outfit', '')}"
    await _generate_and_send_image(
        update=update, context=context, scene_hint=hint, history=history
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text or ""
    if not text.strip():
        return

    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)

    await db.async_add_message(conversation_id, "user", text)
    scene_state = await _nudge_scene_from_user(conversation_id, text)
    history = await db.async_get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
    except (TimedOut, NetworkError):
        pass

    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],
        character_profile=profile_text,
        scene_state=scene_state,
    )
    await _save_assistant_if_ok(conversation_id, reply)
    await _reply_with_suggestions(
        target_message=update.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
    )


async def continue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await _safe_answer(query)
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    history = await db.async_get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)
    scene_state = await db.async_get_scene_state(conversation_id)
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
    except (TimedOut, NetworkError):
        pass
    reply = await llm.generate_reply(
        user_message="",
        history=history,
        character_profile=profile_text,
        scene_state=scene_state,
        is_continue=True,
    )
    await _save_assistant_if_ok(conversation_id, reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
    )


async def change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await _safe_answer(query, "Rewriting reply…")
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    history = await db.async_get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)
    scene_state = await db.async_get_scene_state(conversation_id)
    if not history:
        try:
            await query.message.reply_text("Nothing to change yet — send a message first.")
        except (TimedOut, NetworkError):
            pass
        return
    previous_reply = ""
    if history[-1].get("role") == "assistant":
        previous_reply = (history[-1].get("content") or "").strip()
        history_for_model = history[:-1]
    else:
        history_for_model = history
    if not history_for_model:
        try:
            await query.message.reply_text("Nothing to change yet — send a message first.")
        except (TimedOut, NetworkError):
            pass
        return
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
    except (TimedOut, NetworkError):
        pass
    reply = await llm.generate_reply(
        user_message="",
        history=history_for_model,
        character_profile=profile_text,
        scene_state=scene_state,
        is_regenerate=True,
        previous_reply=previous_reply or None,
    )
    await _save_assistant_if_ok(conversation_id, reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history_for_model + [{"role": "assistant", "content": reply}],
    )


async def suggestion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await _safe_answer(query)
    data = query.data or ""
    try:
        _, key, idx_s = data.split(":", 2)
        idx = int(idx_s)
    except ValueError:
        try:
            await query.message.reply_text("That suggestion expired. Send a message instead.")
        except (TimedOut, NetworkError):
            pass
        return
    pair = _suggestion_store.pop(key, None)
    if not pair:
        try:
            await query.message.reply_text("That suggestion expired. Send a message instead.")
        except (TimedOut, NetworkError):
            pass
        return
    text = pair[0] if idx == 0 else pair[1]
    user = update.effective_user
    await db.async_upsert_user(user.id, user.username, user.first_name)
    character_id = await _get_or_create_default_character()
    conversation_id = await db.async_get_or_create_conversation(user.id, character_id)
    await db.async_add_message(conversation_id, "user", text)
    scene_state = await _nudge_scene_from_user(conversation_id, text)
    history = await db.async_get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
    except (TimedOut, NetworkError):
        pass
    try:
        await query.message.reply_text(f"You: {text}")
    except (TimedOut, NetworkError):
        pass
    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],
        character_profile=profile_text,
        scene_state=scene_state,
    )
    await _save_assistant_if_ok(conversation_id, reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
    )


async def _post_init(application: Application) -> None:
    await _get_or_create_default_character()
    await _set_bot_profile_photo(application)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    db.init_db()
    ARIA_DIR.mkdir(parents=True, exist_ok=True)

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("img", img_command))
    application.add_handler(CallbackQueryHandler(continue_callback, pattern="^rp_continue$"))
    application.add_handler(CallbackQueryHandler(change_callback, pattern="^rp_change$"))
    application.add_handler(CallbackQueryHandler(suggestion_callback, pattern="^rp_sugg:"))
    application.add_handler(CallbackQueryHandler(img_callback, pattern="^rp_img$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
