# Aria character art (local)

| File | Where it appears |
|------|------------------|
| `profile.png` (or `.jpg` / `.webp`) | **Telegram bot avatar** (profile picture of the bot account). **Not** sent in chat. |
| `intro_1.png` | In-chat gallery on `/start` |
| `intro_2.png` | In-chat gallery on `/start` |
| `intro_3.png` | In-chat gallery on `/start` |

On bot startup, `profile.png` is applied via Telegram `setMyProfilePhoto`.
If that fails (old library / API), set it manually:

1. Open **@BotFather**
2. `/setuserpic`
3. Choose your bot
4. Upload `profile.png`

## Copy from Desktop

```powershell
cd C:\Users\Victorjames\lucid-rp-telebot
mkdir data\aria -Force
copy "C:\Users\Victorjames\Desktop\aria's character design\profile.*" data\aria\
# rename the other three to intro_1, intro_2, intro_3
```

Restart the bot after copying.
