# Setup Guide

This document will grow as the project develops. Current status: **Phase 0**.

---

## 1. Prerequisites

- Python 3.11 or higher
- Git
- A Telegram account
- (Optional but recommended) AI Horde account

---

## 2. Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the instructions (choose name and username)
4. Copy the **Bot Token** (looks like `123456:ABC-DEF...`)
5. Keep it secret

---

## 3. AI Horde Setup (Image Generation)

1. Go to [https://aihorde.net](https://aihorde.net)
2. Register an account (recommended for better priority)
3. Go to your account settings and generate an API key
4. Save the key

> You can use the anonymous key `0000000000` for testing, but it has the lowest priority.

---

## 4. Grok / xAI API

You will need an xAI API key to use Grok for roleplay.

1. Go to the xAI console / API dashboard
2. Create an API key
3. Save it securely

---

## 5. Local Development Setup (Coming in Phase 0)

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

# Install dependencies (once requirements.txt exists)
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Then edit .env and add your tokens
```

---

## 6. Environment Variables (Planned)

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
XAI_API_KEY=your_grok_api_key_here
AI_HORDE_API_KEY=your_horde_key_here
```

---

## 7. Running the Bot

```bash
python -m bot.main
```

---

**Note**: Full working setup instructions will be completed during Phase 0 implementation.

Last Updated: August 26, 2026
