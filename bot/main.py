import json
import logging
import os

from dotenv import load_dotenv

# Load .env as early as possible, before any module reads environment variables
load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.db import database as db
from bot.services import llm

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user

    db.upsert_user(user.id, user.username, user.first_name)

    welcome_text = (
        f"Hey {user.first_name} 👋\n\n"
        "Welcome to **Lucid RP Telebot** — an 18+ AI roleplay bot.\n\n"
        "⚠️ This bot is for adults only (18+).\n\n"
        "Just send me a message and I\'ll roleplay with you.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - How to use the bot\n"
        "/new - Start a fresh conversation (clears memory)"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "**How to use Lucid RP Telebot**\n\n"
        "Just send any message and I will reply in character.\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - This help\n"
        "/new - Reset conversation memory\n\n"
        "Coming soon:\n"
        "• Multiple characters + selection\n"
        "• NSFW image generation\n"
        "• Character creation\n"
        "• Save / load checkpoints\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the current conversation memory so the AI starts fresh."""
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)
    db.clear_conversation(conversation_id)

    await update.message.reply_text(
        "Conversation memory cleared. Send a new message to start fresh."
    )


def _get_or_create_default_character() -> int:
    """
    Temporary stand-in until the real character-selection flow exists.
    """
    conn = db.get_conn()
    row = conn.execute(
        "SELECT character_id FROM characters WHERE owner_id IS NULL LIMIT 1"
    ).fetchone()
    if row:
        return row["character_id"]
    return db.create_character(
        owner_id=None,
        name="Aria",
        short_desc="Playful, flirty companion for casual and explicit roleplay.",
        profile_json={
            "name": "Aria",
            "personality": (
                "Playful, a bit teasing, and responsive. "
                "Matches the user's energy. Does not invent past shared history."
            ),
            "tone": "Short, natural replies. Actions in *asterisks*.",
        },
        is_public=True,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the user message, call the LLM, save the reply, and send it."""
    user = update.effective_user
    text = update.message.text or ""

    if not text.strip():
        return

    db.upsert_user(user.id, user.username, user.first_name)

    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)

    db.add_message(conversation_id, "user", text)

    history = db.get_recent_messages(conversation_id, limit=16)

    character = db.get_character(character_id)
    profile_text = (
        "Name: Aria\n"
        "Personality: Playful, a bit teasing, responsive. Matches the user's energy. "
        "Does not invent past shared history.\n"
        "Tone: Short, natural replies. Actions in *asterisks*."
    )
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
            if profile.get("personality"):
                parts.append(f"Personality: {profile['personality']}")
            if profile.get("tone"):
                parts.append(f"Tone: {profile['tone']}")
            if parts:
                profile_text = "\n".join(parts)
        except Exception:
            pass

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],
        character_profile=profile_text,
    )

    db.add_message(conversation_id, "assistant", reply)
    await update.message.reply_text(reply)


def main() -> None:
    """Start the bot."""
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
