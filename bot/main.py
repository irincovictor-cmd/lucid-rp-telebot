import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.db import database as db
from bot.services import llm

# Load environment variables
load_dotenv()

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

    # Create/refresh the user's row so credits, memory, etc. have somewhere to live.
    db.upsert_user(user.id, user.username, user.first_name)

    welcome_text = (
        f"Hey {user.first_name} 👋\n\n"
        "Welcome to **Lucid RP Telebot** — an 18+ AI roleplay bot.\n\n"
        "⚠️ This bot is for adults only (18+).\n\n"
        "Just send me a message and I\'ll roleplay with you.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - How to use the bot"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "**How to use Lucid RP Telebot**\n\n"
        "Just send any message and I will reply in character.\n\n"
        "Coming soon:\n"
        "• Multiple characters + selection\n"
        "• NSFW image generation\n"
        "• Character creation\n"
        "• Save / load checkpoints\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


def _get_or_create_default_character() -> int:
    """
    Temporary stand-in until the real character-selection flow exists.
    Ensures there is at least one built-in character so conversations can attach to it.
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
        short_desc="A warm, slightly playful companion who loves deep conversation and immersive roleplay.",
        profile={
            "name": "Aria",
            "personality": "Warm, curious, slightly playful and flirty when the mood allows. Enjoys immersive roleplay and emotional connection.",
            "tone": "Natural, expressive, never robotic",
        },
        is_public=True,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the user message, call Grok, save the reply, and send it."""
    user = update.effective_user
    text = update.message.text or ""

    if not text.strip():
        return

    # Ensure user exists
    db.upsert_user(user.id, user.username, user.first_name)

    # Get or create default character + conversation
    character_id = _get_or_create_default_character()
    conversation_id = db.get_or_create_conversation(user.id, character_id)

    # Save user message
    db.add_message(conversation_id, "user", text)

    # Load recent history for context
    history = db.get_recent_messages(conversation_id, limit=20)

    # Build a simple character profile string from the DB row
    character = db.get_character(character_id)
    profile_text = "A warm, slightly playful companion who enjoys deep conversation and roleplay."
    if character and character.get("profile_json"):
        import json
        try:
            profile = json.loads(character["profile_json"]) if isinstance(character["profile_json"], str) else character["profile_json"]
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

    # Show typing indicator while waiting for Grok
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Generate reply
    reply = await llm.generate_reply(
        user_message=text,
        history=history[:-1],  # history already includes the latest user message; avoid duplicating it
        character_profile=profile_text,
    )

    # Save assistant reply
    db.add_message(conversation_id, "assistant", reply)

    # Send to user
    await update.message.reply_text(reply)


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    # Set up the database (creates tables on first run, no-op after that)
    db.init_db()

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
