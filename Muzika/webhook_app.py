import os
from contextlib import asynccontextmanager

import asyncpg
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, HTTPException, Request

import bot as core

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not BOT_TOKEN or not DATABASE_URL or not WEBHOOK_SECRET or not PUBLIC_URL:
        raise RuntimeError("Set BOT_TOKEN, DATABASE_URL, WEBHOOK_SECRET and RENDER_EXTERNAL_URL.")
    core.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, command_timeout=10)
    async with core.db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ru' CHECK(language IN ('ru','en','uz')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS favorites(
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                track_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(user_id, track_id)
            );
        """)
    app.state.bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await app.state.bot.set_webhook(
        url=f"{PUBLIC_URL}/telegram",
        secret_token=WEBHOOK_SECRET,
        allowed_updates=core.dp.resolve_used_update_types(),
    )
    yield
    await app.state.bot.delete_webhook()
    await app.state.bot.session.close()
    await core.db.close()

app = FastAPI(title="Muzika Telegram Bot", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Muzika"}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": request.app.state.bot})
    await core.dp.feed_update(request.app.state.bot, update)
    return {"ok": True}
