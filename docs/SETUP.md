# Setup Guide

Current status: **Phase 0 – Basic bot is working**

---

## 1. Prerequisites

- Python 3.11 or higher
- Git
- A Telegram account

---

## 2. Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the instructions (choose a name and username)
4. Copy the **Bot Token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Keep it secret — never commit it to GitHub

---

## 3. AI Horde Setup (for later image generation)

1. Go to [https://aihorde.net](https://aihorde.net)
2. Register an account (recommended for better priority)
3. Generate an API key in your account settings
4. You can also temporarily use the anonymous key `0000000000`

---

## 4. Grok / xAI API (for later roleplay)

1. Go to the xAI API dashboard
2. Create an API key
3. Save it securely

---

## 5. Local Development Setup

```bash
# Clone the repository
git clone https://github.com/irincovictor-cmd/lucid-rp-telebot.git
cd lucid-rp-telebot

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux / macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
```

Open the `.env` file and fill in your tokens:

```env
TELEGRAM_BOT_TOKEN=your_token_from_BotFather
XAI_API_KEY=your_xai_key_here
AI_HORDE_API_KEY=0000000000
```

---

## 6. Run the Bot

```bash
python -m bot.main
```

You should see:
```
Bot is starting...
```

Now open Telegram, search for your bot, and send `/start`.

---

## Troubleshooting

**"TELEGRAM_BOT_TOKEN is not set"**  
→ Make sure you created a `.env` file (not just `.env.example`) and put the correct token inside.

**Bot doesn't reply**  
→ Check that the token is correct and that the bot is running in your terminal.

**ModuleNotFoundError**  
→ Make sure you activated the virtual environment and ran `pip install -r requirements.txt`.

---

Last Updated: August 26, 2026
