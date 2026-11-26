import os, json, logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("avtoxabar")

APP_NAME = "AvtoXabar Agent"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
engine = None

if DATABASE_URL:
    # Neon URLs commonly use postgres://; normalize for SQLAlchemy.
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title=APP_NAME, version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    if not engine:
        return
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
          telegram_id BIGINT PRIMARY KEY,
          username TEXT,
          first_name TEXT,
          language_code TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_settings (
          telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
          auto_reply_enabled BOOLEAN NOT NULL DEFAULT FALSE,
          welcome_enabled BOOLEAN NOT NULL DEFAULT TRUE,
          business_hours_enabled BOOLEAN NOT NULL DEFAULT FALSE,
          reply_language TEXT NOT NULL DEFAULT 'auto',
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS business_connections (
          connection_id TEXT PRIMARY KEY,
          telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
          is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
          connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS message_events (
          id BIGSERIAL PRIMARY KEY,
          telegram_id BIGINT,
          event_type TEXT NOT NULL,
          details JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """))

@app.on_event("startup")
async def startup():
    if engine:
        try:
            init_db()
            log.info("Database initialized")
        except Exception:
            log.exception("Database init failed")
    # Bot token is intentionally not bundled. Set it in Render Environment.
    if BOT_TOKEN and PUBLIC_URL and WEBHOOK_SECRET:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                    json={"url": f"{PUBLIC_URL}/telegram/webhook",
                          "secret_token": WEBHOOK_SECRET,
                          "allowed_updates": ["message", "business_message", "business_connection"]})
                log.info("Webhook set result: %s", r.status_code)
        except Exception:
            log.exception("Webhook setup failed; check deployment environment")

@app.get("/health")
def health():
    return {"ok": True, "service": "avtoxabar-agent", "bot_configured": bool(BOT_TOKEN), "database_configured": bool(engine)}

@app.get("/api/config")
def config():
    return {"product": APP_NAME, "telegram_bot": "@AvtoXabar_agent", "bot_ready": bool(BOT_TOKEN),
            "database_ready": bool(engine), "features": ["dashboard-preview", "settings-preview"]}

@app.get("/", response_class=HTMLResponse)
def index():
    return Path("static/index.html").read_text(encoding="utf-8")

async def telegram_call(method: str, payload: dict):
    if not BOT_TOKEN:
        return None
    import httpx
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload)
        return r.json()

def persist_user(user: dict):
    if not engine or not user.get("id"):
        return
    with engine.begin() as conn:
        conn.execute(text("""
          INSERT INTO users (telegram_id, username, first_name, language_code)
          VALUES (:id, :username, :first_name, :language)
          ON CONFLICT (telegram_id) DO UPDATE SET
            username=EXCLUDED.username, first_name=EXCLUDED.first_name,
            language_code=EXCLUDED.language_code, updated_at=NOW()
        """), {"id": user["id"], "username": user.get("username"),
               "first_name": user.get("first_name"), "language": user.get("language_code")})
        conn.execute(text("INSERT INTO user_settings (telegram_id) VALUES (:id) ON CONFLICT DO NOTHING"),
                     {"id": user["id"]})

async def send_start(chat_id: int, user: dict):
    persist_user(user)
    name = user.get("first_name") or "друг"
    webapp_button = {"text": "🌐 Открыть AvtoXabar"}
    if PUBLIC_URL:
        webapp_button["web_app"] = {"url": PUBLIC_URL}
    else:
        webapp_button["url"] = "https://t.me/AvtoXabar_agent"
    keyboard = {"keyboard": [[webapp_button], [{"text": "⚙️ Настройки"}, {"text": "❓ Помощь"}]],
                "resize_keyboard": True}
    welcome = (f"Привет, {name}! 👋\n\nЯ AvtoXabar Agent — помощник для автоматизации общения "
              "в Telegram Business.\n\nЧерез сайт можно посмотреть панель, настроить ответы и "
              "подготовить подключение Business-аккаунта.\n\nСейчас проект в ранней версии.")
    await telegram_call("sendMessage", {"chat_id": chat_id, "text": welcome, "reply_markup": keyboard})

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    update = await request.json()
    try:
        msg = update.get("message")
        if msg:
            user = msg.get("from", {})
            text_msg = (msg.get("text") or "").strip()
            chat_id = msg.get("chat", {}).get("id")
            if text_msg.startswith("/start") and chat_id:
                await send_start(chat_id, user)
            elif text_msg.startswith("/help") and chat_id:
                await telegram_call("sendMessage", {"chat_id": chat_id,
                  "text": "Команды:\n/start — начать\n/help — помощь\n/settings — настройки\n\nДля автоответов Business подключение и настройки будут доступны в веб-панели."})
            elif text_msg.startswith("/settings") and chat_id:
                link = PUBLIC_URL or "https://t.me/AvtoXabar_agent"
                await telegram_call("sendMessage", {"chat_id": chat_id, "text": "Открой панель настроек:", "reply_markup":{"inline_keyboard":[[{"text":"Открыть сайт","url":link}]]}})
            elif chat_id and text_msg:
                await telegram_call("sendMessage", {"chat_id": chat_id, "text": "Получил сообщение. В этой версии пока доступен базовый помощник. Используй /help для команд."})
        # Telegram Business connection events: log safely, no message contents in DB.
        bc = update.get("business_connection")
        if bc and engine:
            with engine.begin() as conn:
                conn.execute(text("""
                INSERT INTO business_connections(connection_id, telegram_id, is_enabled)
                VALUES (:cid, :uid, :enabled)
                ON CONFLICT (connection_id) DO UPDATE SET is_enabled=EXCLUDED.is_enabled
                """), {"cid": bc.get("id"), "uid": (bc.get("user") or {}).get("id"),
                       "enabled": bc.get("is_enabled", False)})
    except Exception:
        log.exception("Webhook update processing failed")
    return {"ok": True}

@app.get("/api/demo/settings")
def demo_settings():
    return {"auto_reply": False, "welcome": True, "schedule": False, "language": "auto", "mode": "rules"}

@app.post("/api/demo/settings")
async def save_demo_settings(request: Request):
    data = await request.json()
    # Demo UI only until Telegram auth and per-user session validation are added.
    allowed = {"auto_reply", "welcome", "schedule", "language", "mode"}
    return {"saved": {k: data[k] for k in allowed if k in data}, "demo": True,
            "notice": "Prototype settings are local/demo and not yet applied to Telegram Business."}
