# Muzika — @Muzika_agent

A multilingual Telegram music assistant (RU / EN / Uzbek Latin).

## Features
- Language selection before the first welcome message.
- Clean inline menu and localized replies.
- Search by track title or artist, up to 10 Deezer results.
- Album artwork, artist/title metadata, and official 30-second previews.
- Optional link recognition through AudD (requires an API token).
- Favorites stored in Neon Postgres.
- Returns user-sent Telegram audio by reusing its `file_id`; the bot does not download or store that audio.
- Rejects user-sent audio longer than 6 minutes.

## Copyright and delivery limits
This bot does not download or redistribute full copyrighted tracks from arbitrary video links. Search results provide official short previews. Link recognition identifies a track and then offers its legal preview where available. Users may send their own audio files or material they have permission to share; the bot returns the Telegram file directly without downloading it to the server.

Preview delivery time depends on Telegram and the preview provider; a 1–3 second delivery time cannot be guaranteed.

## Environment variables
Copy `.env.example` to `.env` for local development:
- `BOT_TOKEN` — create/revoke through @BotFather and keep secret.
- `DATABASE_URL` — Neon Postgres connection string.
- `AUDD_API_TOKEN` — optional; enables link recognition.
- `ADMIN_IDS` — reserved for future admin features.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

The database tables are created automatically at startup.

## Deployment
Deploy the included Render Blueprint as a web service using Telegram webhooks. The free Render web service may sleep after inactivity, so the first message after idle time can be delayed; 1–3 seconds cannot be guaranteed. Set `BOT_TOKEN` and `DATABASE_URL` in Render Environment as secrets; optionally set `AUDD_API_TOKEN`. Never commit `.env` or paste bot tokens into source control.
