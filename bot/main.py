import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.db import database as db
from bot.services import llm

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BOT_WELCOME = (
    "💖 **HoneyChat / Lucid RP** — private 18+ AI roleplay\n\n"
    "Talk dirty or deep. Stay in a scene. Build whatever fantasy you want.\n\n"
    "⚠️ Adults only (18+).\n\n"
    "Commands:\n"
    "/start — welcome + meet Aria\n"
    "/help — how to use\n"
    "/new — reset memory and restart Aria's intro"
)

ARIA_SCENE_INTRO = (
    "🌙 **Aria**\n\n"
    "A quiet rooftop bar after midnight. Soft music, city lights below, "
    "one empty stool beside a woman who looks like she's been waiting for something "
    "interesting to happen.\n\n"
    "Aria turns toward you — warm eyes, a small playful smile, glass in hand.\n\n"
    "*tilts her head, studying you*\n"
    "You're new here… or at least, I haven't seen you around. "
    "What brings you up here tonight?"
)

ARIA_PROFILE = (
    "Name: Aria\n"
    "Setting: Rooftop bar after midnight; city lights; intimate, low-key mood.\n"
    "Personality: Warm, curious, slightly teasing and flirty when the mood allows. "
    "Responsive to the user's energy. Can gently lead when the user is vague, "
    "but follows clear user direction.\n"
    "Tone: Short natural replies. Actions in *asterisks*. No invented shared history."
)


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
                "Warm, curious, slightly teasing and flirty. "
                "Matches the user's energy. Does not invent past shared history."
            ),
            "tone": "Short, natural replies. Actions in *asterisks*.",
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
            if profile.get("name"):
                parts.append(f"Name: {profile['name']}")
            if profile.get("setting"):
                parts.append(f"Setting: {profile['setting']}")
            if profile.get("personality"):
                parts.append(f"Personality: {profile['personality']}")
            if profile.get("tone"):
                parts.append(f"Tone: {profile['tone']}")
            if parts:
                return "\n".join(parts)
        except Exception:
            pass
    return ARIA_PROFILE


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome + Aria scene intro."""
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    await update.message.reply_text(BOT_WELCOME, parse_mode="Markdown")
    await update.message.reply_text(ARIA_SCENE_INTRO, parse_mode="Markdown")

    # Seed conversation so the model knows the opening scene
    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    # Only seed if conversation is empty
    existing = db.get_recent_messages(conversation_id, limit=1)
    if not existing:
        db.add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "**How to use**\n\n"
        "Just reply to Aria and stay in the scene.\n\n"
        "Commands:\n"
        "/start — bot welcome + Aria intro\n"
        "/help — this help\n"
        "/new — clear memory and restart Aria's intro\n\n"
        "Coming soon: more characters, image gen, checkpoints."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear memory and re-send Aria intro."""
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    db.clear_conversation(conversation_id)

    db.add_message(conversation_id, "assistant", ARIA_SCENE_INTRO)
    await update.message.reply_text("Memory cleared. Starting fresh with Aria…")
    await update.message.reply_text(ARIA_SCENE_INTRO, parse_mode="Markdown")


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
    await update.message.reply_text(reply)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    db.init_db()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
