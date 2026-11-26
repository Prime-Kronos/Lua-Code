# AvtoXabar Agent (prototype)

Telegram-first assistant SaaS concept for Telegram Business automation. This repository currently contains a **safe prototype**: landing page, demo dashboard, health endpoint, webhook skeleton, database initialization, and basic Telegram commands.

## Important security note
A bot token was pasted into chat and must be revoked immediately via BotFather. **Never add it to source code, commits, screenshots, or README.** Add a fresh token only as Render environment variable `BOT_TOKEN`.

## Deploy (Render)
- Runtime: Python
- Build command: `cd avtoxabar-agent && pip install -r requirements.txt`
- Start command: `cd avtoxabar-agent && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add environment variables: `BOT_TOKEN` (fresh rotated token), `DATABASE_URL` (Neon connection string), `PUBLIC_URL` (Render URL), `WEBHOOK_SECRET` (random secret)
- Use HTTPS. Once token + public URL + webhook secret are configured, app sets Telegram webhook on startup.

## Prototype limitations
- Dashboard is demo-only and does not authenticate users yet.
- Telegram Business auto-replies are not implemented. Connection updates are only logged/stored; message contents are not saved.
- Do not invite customers or use this for real business conversations until authentication, tenant isolation, verified Telegram Business permissions, consent, anti-abuse/rate limits, and production tests are implemented.
- Mini App launch URL is not yet configured via BotFather; the website is designed to be opened from the bot keyboard after deployment.

## Local run
```bash
cd avtoxabar-agent
pip install -r requirements.txt
uvicorn main:app --reload
```
