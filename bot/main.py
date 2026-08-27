import json
import logging
import os
from io import BytesIO

from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    "/img <description> — generate a scene image (AI Horde, free, can be slow)"
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
    "Tone: Short replies with *actions*, dialogue, and brief feelings/thoughts."
)

# Temporary store for suggestion button texts (callback_data has size limits)
_suggestion_store: dict[str, tuple[str, str]] = {}


def _rp_keyboard(soft: str | None = None, bold: str | None = None, key: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("Continue ▶", callback_data="rp_continue")]]
    if soft and bold and key:
        rows.append(
            [
                InlineKeyboardButton("Soft 💬", callback_data=f"rp_sugg:{key}:0"),
                InlineKeyboardButton("Bold 🔥", callback_data=f"rp_sugg:{key}:1"),
            ]
        )
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
            for k in ("name", "setting", "personality", "tone"):
                if profile.get(k):
                    parts.append(f"{k.capitalize()}: {profile[k]}")
            if parts:
                return "\n".join(parts)
        except Exception:
            pass
    return ARIA_PROFILE


async def _send_aria_profile(update: Update) -> None:
    """Send cached/generated Aria portrait if available."""
    path = await image_gen.ensure_aria_profile_image()
    if path and path.exists():
        with path.open("rb") as f:
            await update.message.reply_photo(
                photo=InputFile(f, filename="aria.webp"),
                caption="Aria",
            )
    else:
        await update.message.reply_text(
            "_(Profile image unavailable right now — free image workers may be busy.)_",
            parse_mode="Markdown",
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
    # Cap store size
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
        "Reply in character, or use buttons:\n"
        "• **Continue** — Aria keeps going\n"
        "• **Soft / Bold** — pick a suggested reply\n\n"
        "Commands:\n"
        "/start — welcome + Aria\n"
        "/help — this help\n"
        "/new — reset memory\n"
        "/img <scene> — generate an image (slow free queue)"
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
    """Generate a scene image with AI Horde."""
    desc = " ".join(context.args).strip() if context.args else ""
    if not desc:
        await update.message.reply_text(
            "Usage: `/img Aria smiling at the rooftop bar`\n"
            "Free workers can take 30s–3min.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("Generating image… (free queue, please wait)")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")

    data = await image_gen.generate_scene_image(desc, character_name="Aria")
    if not data:
        await update.message.reply_text(
            "Image generation failed or timed out. Try again later."
        )
        return

    await update.message.reply_photo(
        photo=InputFile(BytesIO(data), filename="scene.webp"),
        caption=desc[:200],
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

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

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
    await query.answer()

    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    history = db.get_recent_messages(conversation_id, limit=16)
    profile_text = _character_profile_text(character_id)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

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
    """User picked Soft or Bold suggestion — treat as their message."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    # rp_sugg:{key}:{0|1}
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

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    # Echo what the user "said" via button
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

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("img", img_command))
    application.add_handler(CallbackQueryHandler(continue_callback, pattern="^rp_continue$"))
    application.add_handler(CallbackQueryHandler(suggestion_callback, pattern="^rp_sugg:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
