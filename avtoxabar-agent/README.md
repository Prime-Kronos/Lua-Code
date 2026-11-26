# AvtoXabar Agent

Telegram Business auto-reply starter: responsive website + Telegram Mini App + webhook backend + Neon PostgreSQL.

## Features implemented
- Responsive marketing site at `/` (CSS, optional GSAP motion).
- Telegram Mini App at `/app`; Telegram WebApp initData HMAC validation on API endpoints.
- Per-Telegram-user settings persisted in PostgreSQL: auto-reply toggle, welcome, language, business name, welcome text, FAQ keyword lines.
- Telegram webhook with secret-token header validation, `/start`, `/help`, `/settings`, Business connection events and incoming Business messages.
- Rule-based FAQ replies (line format `keyword: reply`) and default greeting. No AI model is currently connected.
- Health endpoint `/health`.

## Security
A bot token was pasted into a previous chat. Revoke it using BotFather and create a new token. Never commit or share tokens. Add the new token only in Render Environment settings. WebApp API requires valid Telegram initData; webhook uses Telegram's secret header when configured.

## Render deploy
Service repository root: `Prime-Kronos/Lua-Code`; rootDir empty.
Build command:
```sh
cd avtoxabar-agent && pip install -r requirements.txt
```
Start command:
```sh
cd avtoxabar-agent && uvicorn main:app --host 0.0.0.0 --port $PORT
```
Required Render environment variables:
- `BOT_TOKEN`: fresh token from BotFather
- `DATABASE_URL`: Neon connection URI (use pooled connection string if desired; driver compatible with psycopg)
- `PUBLIC_URL`: `https://avtoxabar-agent.onrender.com`
- `WEBHOOK_SECRET`: generate a long random secret, at least 32 random characters; don't use a sample value

When all are present, service startup sets the Telegram webhook. Check `/health` to confirm `bot_configured` and `database_configured` both true.

## Mini App launch configuration
The bot's `/start` reply includes a Web App button linking to `https://avtoxabar-agent.onrender.com/app`. To make the Mini App available from Telegram's menu too, configure BotFather menu button / Web App URL to the same URL. If asked for a domain, set `avtoxabar-agent.onrender.com`. Use HTTPS.

## Telegram Business setup (account owner)
1. In Telegram, open Settings → Telegram Business → Chatbots (wording may vary).
2. Connect `@AvtoXabar_agent` and grant the message access needed for reply handling.
3. Open the Mini App from the bot's `/start` button, save settings and enable auto replies.
4. Test with a separate test account first. The bot only uses saved rule/greeting settings; no AI generation is enabled.

## FAQ rules
Enter each line in the Mini App as `keyword: answer`. A reply is selected when a keyword appears in the incoming text. Example:
```
delivery: We deliver within the city. Ask us for the current delivery fee.
hours: We are open daily from 09:00 to 18:00.
```
If no rule matches, the welcome template is used when enabled. Keep replies accurate and avoid storing sensitive customer data.

## Local run
```sh
cd avtoxabar-agent
pip install -r requirements.txt
export PUBLIC_URL=http://localhost:8000
uvicorn main:app --reload
```
For Mini App auth and webhook locally, configure valid secrets and use a public HTTPS tunnel; localhost by itself won't be opened by Telegram.
