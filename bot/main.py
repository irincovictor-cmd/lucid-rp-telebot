import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

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
    welcome_text = (
        f"Hey {user.first_name} 👋\n\n"
        "Welcome to **Lucid RP Telebot** — an 18+ AI roleplay bot.\n\n"
        "⚠️ This bot is for adults only (18+).\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - How to use the bot\n\n"
        "More features coming soon (characters, image generation, etc.)."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "**How to use Lucid RP Telebot**\n\n"
        "Right now the bot is in early development.\n\n"
        "Coming soon:\n"
        "• AI roleplay with custom characters\n"
        "• NSFW image generation\n"
        "• Character creation\n"
        "• Conversation memory\n\n"
        "Stay tuned!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message (temporary for testing)."""
    await update.message.reply_text(
        f"I received: {update.message.text}\n\n"
        "Roleplay AI is not connected yet. Coming in the next update!"
    )


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
