import json
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

# Local Aria art (copy your files here — see data/aria/README)
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

BOT_WELCOME = (
    "💖 **HoneyChat / Lucid RP** — private 18+ AI roleplay\n\n"
    "Talk dirty or deep. Stay in a scene.\n\n"
    "⚠️ Adults only (18+).\n\n"
    "Buttons under replies:\n"
    "• **Continue** — advance the scene\n"
    "• **Change** — different reply for the same moment\n"
    "• **Soft / Bold** — suggested replies if you're stuck\n\n"
    "Commands:\n"
    "/start — welcome + meet Aria\n"
    "/help — how to use\n"
    "/new — reset memory\n"
    "/img — image from current scene (or `/img your details`)\n"
    "Bot avatar: data/aria/profile.png · Intro gallery: intro_1–3"
)

ARIA_SCENE_INTRO = (
    "🌙 **Aria**\n\n"
    "A quiet rooftop bar after midnight. Soft music, city lights below, "
    "one empty stool beside a woman who looks like she's been waiting for something "
    "interesting to happen.\n\n"
    "Aria turns toward you — warm eyes, a small playful smile, glass in hand.\n\n"
    "*tilts her head, studying you* *curious, a little amused*\n"
    "You're new here… or at least, I haven't seen you around. "
    "What brings you up here tonight?"
)

ARIA_PROFILE = (
    "Name: Aria\n"
    "Setting: Rooftop bar after midnight; city lights; intimate, low-key mood.\n"
    "Personality: Warm, curious, slightly teasing. Builds atmosphere before escalating.\n"
    "Tone: Short-to-medium replies with *actions*, dialogue, and atmosphere.\n"
    "Appearance: 2D anime; long black hair; red eyes; thin glasses; low-cut evening top.\n"
    "Do not invent a different job, outfit, or backstory unless the user establishes it."
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


def _rp_keyboard(soft: str | None = None, bold: str | None = None, key: str | None = None) -> InlineKeyboardMarkup:
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
    """Only intro_* files — profile.png is the bot avatar, not chat media."""
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
    """Set Telegram bot avatar from data/aria/profile.* (not sent in chat)."""
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
        return
    except ImportError:
        logger.warning(
            "InputProfilePhotoStatic not available in this python-telegram-bot version"
        )
    except Exception as e:
        logger.warning("set_my_profile_photo failed: %s", e)

    # Fallback: raw Bot API (static profile photo)
    try:
        import httpx

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyProfilePhoto"
        with path.open("rb") as f:
            # Telegram expects photo as InputProfilePhoto JSON + file attach
            files = {"photo": (path.name, f, "image/jpeg")}
            data = {"photo": '{"type":"static","photo":"attach://photo"}'}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, data=data, files=files)
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info("Bot Telegram profile photo set via raw API from %s", path.name)
        else:
            logger.warning(
                "Could not set bot avatar (%s). "
                "Open @BotFather → /setuserpic and upload profile.png manually.",
                resp.text[:300],
            )
    except Exception as e:
        logger.warning(
            "Bot avatar not set (%s). Use @BotFather /setuserpic with profile.png",
            e,
        )


async def _send_aria_intro_gallery(update: Update) -> None:
    """Send intro_1–3 in chat only (profile.png is bot avatar, not posted here)."""
    paths = _find_aria_intro_images()

    if not paths:
        await update.message.reply_text(
            "Add `intro_1.png`–`intro_3.png` under data/aria/ to show Aria in chat.\n"
            "`profile.png` is used only as the bot’s Telegram avatar."
        )
        return

    if len(paths) == 1:
        with paths[0].open("rb") as f:
            await update.message.reply_photo(
                photo=InputFile(f, filename=paths[0].name),
                caption="Aria",
            )
        return

    media: list[InputMediaPhoto] = []
    handles = []
    try:
        for i, p in enumerate(paths):
            fh = p.open("rb")
            handles.append(fh)
            cap = "Aria" if i == 0 else None
            media.append(InputMediaPhoto(media=fh, caption=cap))
        await update.message.reply_media_group(media=media)
    finally:
        for fh in handles:
            try:
                fh.close()
            except Exception:
                pass


def _get_or_create_default_character() -> int:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT character_id FROM characters WHERE owner_id IS NULL LIMIT 1"
    ).fetchone()
    if row:
        return row["character_id"]
    return db.create_character(
        owner_id=None,
        name="Aria",
        short_desc="Warm, playful companion at a late-night rooftop bar.",
        profile_json={
            "name": "Aria",
            "setting": "Rooftop bar after midnight",
            "personality": (
                "Warm, curious, slightly teasing. Builds atmosphere before escalating. "
                "Matches the user's pace. Does not invent past shared history."
            ),
            "tone": "Short-to-medium replies with actions, dialogue, and atmosphere.",
            "appearance": (
                "2D anime; long black hair; red eyes; thin glasses; "
                "low-cut elegant evening top"
            ),
        },
        is_public=True,
    )


def _character_profile_text(character_id: int) -> str:
    character = db.get_character(character_id)
    if character and character.get("profile_json"):
        try:
            profile = (
                json.loads(character["profile_json"])
                if isinstance(character["profile_json"], str)
                else character["profile_json"]
            )
            parts = []
            for k in ("name", "setting", "personality", "tone", "appearance"):
                if profile.get(k):
                    parts.append(f"{k.capitalize()}: {profile[k]}")
            if parts:
                return "\n".join(parts)
        except Exception:
            pass
    return ARIA_PROFILE


async def _generate_and_send_image(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    scene_hint: str = "",
    history: list | None = None,
) -> None:
    chat_id = update.effective_chat.id
    status = await context.bot.send_message(
        chat_id,
        "🖼️ Generating 2D anime image…\nFree AI Horde queue — please wait.",
    )

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
                "Image failed or timed out. Free workers may be busy — try again in a bit."
            )
        except Exception:
            pass
        return

    try:
        await status.delete()
    except Exception:
        pass

    caption = scene_hint[:200] if scene_hint else "From current scene"
    await context.bot.send_photo(
        chat_id,
        photo=InputFile(BytesIO(data), filename="scene.webp"),
        caption=caption,
    )


async def _reply_with_suggestions(
    *,
    target_message,
    conversation_id: int,
    reply: str,
    history: list,
) -> None:
    if llm.is_system_failure_reply(reply):
        await target_message.reply_text(reply)
        return

    soft, bold = await llm.generate_suggestions(history=history, last_assistant=reply)
    key = f"{conversation_id}_{abs(hash(reply)) % 10_000_000}"
    _suggestion_store[key] = (soft, bold)
    if len(_suggestion_store) > 200:
        for old in list(_suggestion_store.keys())[:50]:
            _suggestion_store.pop(old, None)

    await target_message.reply_text(
        reply,
        reply_markup=_rp_keyboard(soft, bold, key),
    )


async def _save_assistant_if_ok(conversation_id: int, reply: str) -> None:
    if not llm.is_system_failure_reply(reply) and not llm._looks_like_leak(reply):
        db.add_message(conversation_id, "assistant", reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    await update.message.reply_text(BOT_WELCOME, parse_mode="Markdown")
    await _send_aria_intro_gallery(update)
    await update.message.reply_text(
        ARIA_SCENE_INTRO,
        parse_mode="Markdown",
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

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    existing = db.get_recent_messages(conversation_id, limit=1)
    if not existing:
        db.add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "**How to use**\n\n"
        "Reply in character, or use buttons.\n\n"
        "**Buttons**\n"
        "• Continue / Change / Soft / Bold / Image\n\n"
        "**Aria images**\n"
        "• `data/aria/profile.png` → **bot Telegram avatar** (not posted in chat)\n"
        "• `data/aria/intro_1.png` … `intro_3.png` → shown on /start\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    db.clear_conversation(conversation_id)

    db.add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)
    await update.message.reply_text("Memory cleared. Starting fresh with Aria…")
    await _send_aria_intro_gallery(update)
    await update.message.reply_text(
        ARIA_SCENE_INTRO,
        parse_mode="Markdown",
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
    db.upsert_user(user.id, user.username, user.first_name)
    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    history = db.get_recent_messages(conversation_id, limit=12)

    await _generate_and_send_image(
        update=update,
        context=context,
        scene_hint=desc,
        history=history,
    )


async def img_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await _safe_answer(query, "Generating image from scene…")

    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    history = db.get_recent_messages(conversation_id, limit=12)

    await _generate_and_send_image(
        update=update,
        context=context,
        scene_hint="",
        history=history,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text or ""
    if not text.strip():
        return

    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)

    db.add_message(conversation_id, "user", text)
    history = db.get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except (TimedOut, NetworkError):
        pass

    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],
        character_profile=profile_text,
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
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    history = db.get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except (TimedOut, NetworkError):
        pass

    reply = await llm.generate_reply(
        user_message="",
        history=history,
        character_profile=profile_text,
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
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    history = db.get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    if not history:
        await query.message.reply_text("Nothing to change yet — send a message first.")
        return

    previous_reply = ""
    if history[-1].get("role") == "assistant":
        previous_reply = (history[-1].get("content") or "").strip()
        history_for_model = history[:-1]
    else:
        history_for_model = history

    if not history_for_model:
        await query.message.reply_text("Nothing to change yet — send a message first.")
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except (TimedOut, NetworkError):
        pass

    reply = await llm.generate_reply(
        user_message="",
        history=history_for_model,
        character_profile=profile_text,
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
        await query.message.reply_text("That suggestion expired. Send a message instead.")
        return

    pair = _suggestion_store.pop(key, None)
    if not pair:
        await query.message.reply_text("That suggestion expired. Send a message instead.")
        return

    text = pair[0] if idx == 0 else pair[1]

    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)

    db.add_message(conversation_id, "user", text)
    history = db.get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except (TimedOut, NetworkError):
        pass

    await query.message.reply_text(f"You: {text}")

    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],
        character_profile=profile_text,
    )
    await _save_assistant_if_ok(conversation_id, reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
    )


async def _post_init(application: Application) -> None:
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
    logger.info("Aria art folder: %s", ARIA_DIR)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
