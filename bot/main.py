import json
import logging
import os
from io import BytesIO

from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
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

BOT_WELCOME = (
    "💖 **HoneyChat / Lucid RP** — private 18+ AI roleplay\n\n"
    "Talk dirty or deep. Stay in a scene.\n\n"
    "⚠️ Adults only (18+).\n\n"
    "Buttons under replies:\n"
    "• **Continue** — advance the scene\n"
    "• **Soft / Bold** — suggested replies if you're stuck\n\n"
    "Commands:\n"
    "/start — welcome + meet Aria\n"
    "/help — how to use\n"
    "/new — reset memory\n"
    "/img — image from current scene (or `/img your details`)\n"
    "Images: 2D anime style via AI Horde (free, can be slow)"
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
    "Tone: Short replies with *actions*, dialogue, and brief feelings/thoughts.\n"
    "Appearance: 2D anime; long black hair; red eyes; thin glasses."
)

_suggestion_store: dict[str, tuple[str, str]] = {}


async def _safe_answer(query, text: str | None = None) -> None:
    """Answer callback without crashing on network timeouts."""
    try:
        if text:
            await query.answer(text)
        else:
            await query.answer()
    except (TimedOut, NetworkError, BadRequest) as e:
        logger.warning("callback answer failed (ignored): %s", e)


def _rp_keyboard(soft: str | None = None, bold: str | None = None, key: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("Continue ▶", callback_data="rp_continue")]]
    if soft and bold and key:
        rows.append(
            [
                InlineKeyboardButton("Soft 💬", callback_data=f"rp_sugg:{key}:0"),
                InlineKeyboardButton("Bold 🔥", callback_data=f"rp_sugg:{key}:1"),
            ]
        )
    rows.append([InlineKeyboardButton("🖼️ Image", callback_data="rp_img")])
    return InlineKeyboardMarkup(rows)


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
            "tone": "Short replies with actions, dialogue, and brief feelings.",
            "appearance": "2D anime; long black hair; red eyes; thin glasses",
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


async def _send_aria_profile(update: Update) -> None:
    status = await update.message.reply_text(
        "Loading Aria's portrait (2D anime)… first time can take 1–3 min on free workers."
    )

    async def on_progress(msg: str) -> None:
        try:
            await status.edit_text(f"Portrait: {msg}")
        except Exception:
            pass

    path = await image_gen.ensure_aria_profile_image(on_progress=on_progress)
    if path and path.exists():
        try:
            await status.delete()
        except Exception:
            pass
        with path.open("rb") as f:
            await update.message.reply_photo(
                photo=InputFile(f, filename="aria.webp"),
                caption="Aria",
            )
    else:
        try:
            await status.edit_text(
                "Portrait unavailable right now — free image workers busy. Try /start later."
            )
        except Exception:
            pass


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    await update.message.reply_text(BOT_WELCOME, parse_mode="Markdown")
    await _send_aria_profile(update)
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
        "**Images (2D anime)**\n"
        "• `/img` — generate from current chat scene\n"
        "• `/img torn stockings, glasses, on bed` — add your details\n"
        "• **Image** button under replies — same as `/img`\n\n"
        "Free queue can take 30s–3min; status messages will update."
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
    await _send_aria_profile(update)
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

    db.add_message(conversation_id, "assistant", reply)
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

    db.add_message(conversation_id, "assistant", reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
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

    pair = _suggestion_store.get(key)
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
    db.add_message(conversation_id, "assistant", reply)
    await _reply_with_suggestions(
        target_message=query.message,
        conversation_id=conversation_id,
        reply=reply,
        history=history,
    )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    db.init_db()

    # Longer timeouts help on slow/unstable networks (school/lab Wi‑Fi, etc.)
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
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("img", img_command))
    application.add_handler(CallbackQueryHandler(continue_callback, pattern="^rp_continue$"))
    application.add_handler(CallbackQueryHandler(suggestion_callback, pattern="^rp_sugg:"))
    application.add_handler(CallbackQueryHandler(img_callback, pattern="^rp_img$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
