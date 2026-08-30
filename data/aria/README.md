# Aria character art (local)

Put your generated images here. The bot loads them on `/start` and `/new` — **no AI Horde** for intro.

## Required names

| File | Use |
|------|-----|
| `profile.png` (or `.jpg` / `.webp`) | Main portrait (first image) |
| `intro_1.png` | Extra angle / pose |
| `intro_2.png` | Extra angle / pose |
| `intro_3.png` | Extra angle / pose |

## From your Desktop folder

If files are in:

`C:\Users\Victorjames\Desktop\aria's character design`

Copy them into this folder and **rename**:

1. The one named **profile** → `profile.png` (keep extension if `.jpg`)
2. The other three → `intro_1.png`, `intro_2.png`, `intro_3.png`

Example (PowerShell from repo root):

```powershell
mkdir -Force data\aria
copy "C:\Users\Victorjames\Desktop\aria's character design\profile.*" data\aria\
# then rename the other three to intro_1, intro_2, intro_3
```

Restart the bot after copying.
