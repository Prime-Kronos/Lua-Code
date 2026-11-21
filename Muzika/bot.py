import asyncio
import html
import logging
import os
from typing import Any
from urllib.parse import urlparse

import aiohttp
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("muzika")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN", "").strip()
MAX_AUDIO_SECONDS = 6 * 60
PREVIEW_SECONDS = 30

TEXTS = {
    "ru": {
        "choose": "🌍 <b>Выберите язык / Choose your language / Tilni tanlang</b>",
        "welcome": "🎧 <b>Добро пожаловать в Muzika!</b>\n\nТвой музыкальный помощник: ищи треки, слушай короткие превью, распознавай музыку по ссылке и сохраняй любимое.\n\n<i>Мы отправляем официальные превью и ваши собственные аудиофайлы — не храним музыку на сервере.</i>",
        "search": "🔎 Поиск музыки", "recognize": "🔗 Распознать по ссылке",
        "favorites": "❤️ Избранное", "language": "🌍 Язык", "about": "ℹ️ О боте",
        "prompt_search": "Напиши название песни или исполнителя:",
        "prompt_url": "Отправь ссылку на видео или аудио. Попробую определить трек, если источник поддерживается.",
        "searching": "🔎 Ищу до 10 совпадений…",
        "not_found": "Ничего не нашёл. Попробуй другое название.",
        "search_error": "Не удалось выполнить поиск. Попробуй чуть позже.",
        "found": "🎵 <b>Результаты поиска</b> — выбери трек:",
        "preview": "▶️ Слушать превью (до 30 сек)",
        "favorite": "❤️ В избранное", "saved": "Добавлено в избранное!",
        "already": "Этот трек уже в избранном.",
        "sent": "💙 Спасибо, что слушаете Muzika — @Muzika_agent!",
        "too_long": "⛔ Файл длиннее 6 минут. Такой файл бот не принимает.",
        "audio_only": "Пришли аудиофайл (не видео), пожалуйста.",
        "recognition_off": "Распознавание ссылок временно не настроено. Администратор должен добавить AUDD_API_TOKEN.",
        "recognition_fail": "Не получилось распознать музыку по этой ссылке. Проверь ссылку или попробуй другую.",
        "recognized": "🎼 <b>Похоже, это:</b>\n<b>{title}</b> — {artist}",
        "url_invalid": "Нужна корректная ссылка, начинающаяся с http:// или https://.",
        "no_favs": "Пока нет избранных треков. Найди музыку и добавь её ❤️",
        "your_favs": "❤️ <b>Твоё избранное:</b>",
        "about_text": "🎧 <b>Muzika</b> — музыкальный помощник.\n\n• Поиск по названию и исполнителю\n• До 10 результатов\n• Официальные 30-секундные превью\n• Распознавание музыки по ссылкам (если поддерживается сервисом)\n• Избранное\n• Возврат твоих аудиофайлов без повторной загрузки на наш сервер\n\nПолные защищённые авторским правом записи бот не раздаёт.",
        "cancel": "Отменено. Открой меню, чтобы продолжить.",
        "lang_saved": "✅ Язык сохранён.",
        "track_missing": "Результат устарел. Выполни поиск ещё раз.",
        "error": "Что-то пошло не так. Попробуй ещё раз.",
    },
    "en": {
        "choose": "🌍 <b>Choose your language / Выберите язык / Tilni tanlang</b>",
        "welcome": "🎧 <b>Welcome to Muzika!</b>\n\nYour music companion: search tracks, listen to short previews, recognize music from a link, and save favorites.\n\n<i>We send official previews and your own audio files — we do not keep music on the server.</i>",
        "search": "🔎 Search music", "recognize": "🔗 Recognize from link",
        "favorites": "❤️ Favorites", "language": "🌍 Language", "about": "ℹ️ About",
        "prompt_search": "Send a song title or artist:",
        "prompt_url": "Send a video or audio link. I’ll try to identify the track if the source is supported.",
        "searching": "🔎 Searching for up to 10 matches…",
        "not_found": "No matches found. Try another title.",
        "search_error": "Search failed. Please try again later.",
        "found": "🎵 <b>Search results</b> — choose a track:",
        "preview": "▶️ Play preview (up to 30 sec)",
        "favorite": "❤️ Add to favorites", "saved": "Added to favorites!",
        "already": "This track is already in your favorites.",
        "sent": "💙 Thanks for listening with Muzika — @Muzika_agent!",
        "too_long": "⛔ This file is longer than 6 minutes, so Muzika cannot accept it.",
        "audio_only": "Please send an audio file, not a video.",
        "recognition_off": "Link recognition is not configured yet. The admin must add AUDD_API_TOKEN.",
        "recognition_fail": "Could not recognize music from this link. Check it or try another one.",
        "recognized": "🎼 <b>This may be:</b>\n<b>{title}</b> — {artist}",
        "url_invalid": "Please send a valid link starting with http:// or https://.",
        "no_favs": "No favorites yet. Find a track and tap ❤️",
        "your_favs": "❤️ <b>Your favorites:</b>",
        "about_text": "🎧 <b>Muzika</b> — your music companion.\n\n• Search by title or artist\n• Up to 10 results\n• Official 30-second previews\n• Link-based music recognition (where supported)\n• Favorites\n• Return your own audio files without re-uploading them to our server\n\nThe bot does not distribute full copyrighted recordings.",
        "cancel": "Cancelled. Use the menu to continue.",
        "lang_saved": "✅ Language saved.",
        "track_missing": "This result has expired. Please search again.",
        "error": "Something went wrong. Please try again.",
    },
    "uz": {
        "choose": "🌍 <b>Tilni tanlang / Choose your language / Выберите язык</b>",
        "welcome": "🎧 <b>Muzika’ga xush kelibsiz!</b>\n\nMusiqa yordamchingiz: qo‘shiqlarni qidiring, qisqa namunalarni tinglang, havola orqali musiqani aniqlang va sevimlilarni saqlang.\n\n<i>Rasmiy qisqa namunalar va o‘zingiz yuborgan audio fayllar jo‘natiladi — musiqa serverda saqlanmaydi.</i>",
        "search": "🔎 Musiqa qidirish", "recognize": "🔗 Havola orqali aniqlash",
        "favorites": "❤️ Sevimlilar", "language": "🌍 Til", "about": "ℹ️ Bot haqida",
        "prompt_search": "Qo‘shiq nomi yoki ijrochini yozing:",
        "prompt_url": "Video yoki audio havolasini yuboring. Manba qo‘llab-quvvatlansa, musiqani aniqlayman.",
        "searching": "🔎 10 tagacha natija qidirilmoqda…",
        "not_found": "Hech narsa topilmadi. Boshqa nomni sinab ko‘ring.",
        "search_error": "Qidiruv amalga oshmadi. Keyinroq urinib ko‘ring.",
        "found": "🎵 <b>Qidiruv natijalari</b> — trekni tanlang:",
        "preview": "▶️ Namunani tinglash (30 soniyagacha)",
        "favorite": "❤️ Sevimlilarga", "saved": "Sevimlilarga qo‘shildi!",
        "already": "Bu trek allaqachon sevimlilarda.",
        "sent": "💙 Muzika’dan foydalanganingiz uchun rahmat — @Muzika_agent!",
        "too_long": "⛔ Fayl 6 daqiqadan uzun. Bot bunday faylni qabul qilmaydi.",
        "audio_only": "Iltimos, video emas, audio fayl yuboring.",
        "recognition_off": "Havola orqali aniqlash sozlanmagan. Administrator AUDD_API_TOKEN qo‘shishi kerak.",
        "recognition_fail": "Bu havoladan musiqani aniqlab bo‘lmadi. Havolani tekshiring yoki boshqasini yuboring.",
        "recognized": "🎼 <b>Bu trek bo‘lishi mumkin:</b>\n<b>{title}</b> — {artist}",
        "url_invalid": "http:// yoki https:// bilan boshlanadigan to‘g‘ri havola yuboring.",
        "no_favs": "Hozircha sevimlilar yo‘q. Musiqa topib ❤️ tugmasini bosing.",
        "your_favs": "❤️ <b>Sevimli treklaringiz:</b>",
        "about_text": "🎧 <b>Muzika</b> — musiqa yordamchisi.\n\n• Nomi va ijrochi bo‘yicha qidiruv\n• 10 tagacha natija\n• Rasmiy 30 soniyalik namunalar\n• Havola orqali musiqani aniqlash (xizmat qo‘llasa)\n• Sevimlilar\n• O‘zingiz yuborgan audio faylni serverga qayta yuklamasdan qaytarish\n\nBot mualliflik huquqi bilan himoyalangan to‘liq yozuvlarni tarqatmaydi.",
        "cancel": "Bekor qilindi. Davom etish uchun menyudan foydalaning.",
        "lang_saved": "✅ Til saqlandi.",
        "track_missing": "Natija eskirgan. Qayta qidiring.",
        "error": "Xatolik yuz berdi. Qayta urinib ko‘ring.",
    },
}

dp = Dispatcher()
db: asyncpg.Pool | None = None
bot_username = "Muzika_agent"
track_cache: dict[int, dict[str, Any]] = {}

class SearchState(StatesGroup):
    waiting_query = State()
    waiting_url = State()

def t(lang: str, key: str, **kwargs: Any) -> str:
    return TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"].get(key, key)).format(**kwargs)

def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
        InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
    ]])

def menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    x = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=x["search"], callback_data="menu:search")],
        [InlineKeyboardButton(text=x["recognize"], callback_data="menu:recognize")],
        [InlineKeyboardButton(text=x["favorites"], callback_data="menu:favs"),
         InlineKeyboardButton(text=x["about"], callback_data="menu:about")],
        [InlineKeyboardButton(text=x["language"], callback_data="menu:language")],
    ])

async def get_lang(user_id: int) -> str:
    assert db
    row = await db.fetchrow("SELECT language FROM users WHERE user_id=$1", user_id)
    return row["language"] if row else "ru"

async def set_user(user_id: int, lang: str | None = None) -> None:
    assert db
    await db.execute("""
        INSERT INTO users(user_id, language) VALUES($1, COALESCE($2, 'ru'))
        ON CONFLICT(user_id) DO UPDATE SET language=COALESCE($2, users.language), updated_at=NOW()
    """, user_id, lang)

async def deezer_search(query: str) -> list[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=8, connect=3)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get("https://api.deezer.com/search", params={"q": query, "limit": 10}) as resp:
            resp.raise_for_status()
            payload = await resp.json()
            return payload.get("data", [])[:10]

def results_keyboard(tracks: list[dict[str, Any]], lang: str) -> InlineKeyboardMarkup:
    rows = []
    for item in tracks:
        track_cache[int(item["id"])] = item
        label = f'{item.get("title", "Unknown")} — {item.get("artist", {}).get("name", "Unknown")}'
        rows.append([InlineKeyboardButton(text=("🎵 " + label)[:60], callback_data=f'track:{item["id"]}')])
    rows.append([InlineKeyboardButton(text="⬅️ Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def track_keyboard(track_id: int, lang: str) -> InlineKeyboardMarkup:
    x = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=x["preview"], callback_data=f"preview:{track_id}")],
        [InlineKeyboardButton(text=x["favorite"], callback_data=f"fav:{track_id}")],
        [InlineKeyboardButton(text="⬅️ Menu", callback_data="menu:home")],
    ])

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    row = await db.fetchrow("SELECT language FROM users WHERE user_id=$1", message.from_user.id)
    # New users are asked to choose their language before the greeting.
    if not row or not row["language"]:
        await message.answer(t("ru", "choose"), reply_markup=lang_keyboard())
        return
    lang = row["language"]
    await message.answer(t(lang, "welcome"), reply_markup=menu_keyboard(lang))

@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "cancel"), reply_markup=menu_keyboard(lang))

@dp.callback_query(F.data.startswith("lang:"))
async def choose_language(call: CallbackQuery, state: FSMContext):
    lang = call.data.split(":", 1)[1]
    if lang not in TEXTS:
        await call.answer()
        return
    await set_user(call.from_user.id, lang)
    await state.clear()
    await call.message.edit_text(t(lang, "lang_saved"))
    await call.message.answer(t(lang, "welcome"), reply_markup=menu_keyboard(lang))
    await call.answer()

@dp.callback_query(F.data.startswith("menu:"))
async def menu(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":", 1)[1]
    lang = await get_lang(call.from_user.id)
    await state.clear()
    if action == "language":
        await call.message.answer(t(lang, "choose"), reply_markup=lang_keyboard())
    elif action == "search":
        await state.set_state(SearchState.waiting_query)
        await call.message.answer(t(lang, "prompt_search"))
    elif action == "recognize":
        await state.set_state(SearchState.waiting_url)
        await call.message.answer(t(lang, "prompt_url"))
    elif action == "about":
        await call.message.answer(t(lang, "about_text"), reply_markup=menu_keyboard(lang))
    elif action == "favs":
        rows = await db.fetch("""
            SELECT track_id, title, artist FROM favorites
            WHERE user_id=$1 ORDER BY created_at DESC LIMIT 30
        """, call.from_user.id)
        if not rows:
            await call.message.answer(t(lang, "no_favs"), reply_markup=menu_keyboard(lang))
        else:
            await call.message.answer(t(lang, "your_favs") + "\n\n" + "\n".join(
                f'• {html.escape(r["title"])} — {html.escape(r["artist"])}' for r in rows
            ), reply_markup=menu_keyboard(lang))
    else:
        await call.message.answer(t(lang, "welcome"), reply_markup=menu_keyboard(lang))
    await call.answer()

@dp.message(SearchState.waiting_query, F.text)
async def search_music(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    query = message.text.strip()[:100]
    if len(query) < 2:
        await message.answer(t(lang, "prompt_search"))
        return
    status = await message.answer(t(lang, "searching"))
    try:
        tracks = await deezer_search(query)
    except Exception:
        log.exception("Deezer search failed")
        await status.edit_text(t(lang, "search_error"))
        await state.clear()
        return
    await state.clear()
    if not tracks:
        await status.edit_text(t(lang, "not_found"))
        return
    await status.edit_text(t(lang, "found"), reply_markup=results_keyboard(tracks, lang))

@dp.callback_query(F.data.startswith("track:"))
async def show_track(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    track_id = int(call.data.split(":", 1)[1])
    item = track_cache.get(track_id)
    if not item:
        await call.answer(t(lang, "track_missing"), show_alert=True)
        return
    title = html.escape(item.get("title", "Unknown"))
    artist = html.escape(item.get("artist", {}).get("name", "Unknown"))
    album = item.get("album", {})
    cover = album.get("cover_medium")
    caption = f"🎵 <b>{title}</b>\n👤 {artist}\n⏱ {int(item.get('duration') or 0)//60}:{int(item.get('duration') or 0)%60:02d}"
    if cover:
        await call.message.answer_photo(cover, caption=caption, reply_markup=track_keyboard(track_id, lang))
    else:
        await call.message.answer(caption, reply_markup=track_keyboard(track_id, lang))
    await call.answer()

@dp.callback_query(F.data.startswith("preview:"))
async def send_preview(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    track_id = int(call.data.split(":", 1)[1])
    item = track_cache.get(track_id)
    if not item or not item.get("preview"):
        await call.answer(t(lang, "track_missing"), show_alert=True)
        return
    try:
        await call.message.answer_audio(
            audio=item["preview"],
            title=item.get("title", "Muzika preview"),
            performer=item.get("artist", {}).get("name", "Muzika"),
            duration=PREVIEW_SECONDS,
            caption=t(lang, "sent"),
        )
        await call.answer()
    except Exception:
        log.exception("Preview send failed")
        await call.answer(t(lang, "error"), show_alert=True)

@dp.callback_query(F.data.startswith("fav:"))
async def add_favorite(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    track_id = int(call.data.split(":", 1)[1])
    item = track_cache.get(track_id)
    if not item:
        await call.answer(t(lang, "track_missing"), show_alert=True)
        return
    result = await db.execute("""
        INSERT INTO favorites(user_id, track_id, title, artist)
        VALUES($1,$2,$3,$4) ON CONFLICT(user_id, track_id) DO NOTHING
    """, call.from_user.id, track_id, item.get("title", "Unknown"),
         item.get("artist", {}).get("name", "Unknown"))
    await call.answer(t(lang, "saved") if result.endswith("1") else t(lang, "already"), show_alert=True)

@dp.message(SearchState.waiting_url, F.text)
async def recognize_link(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    url = message.text.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await message.answer(t(lang, "url_invalid"))
        return
    await state.clear()
    if not AUDD_API_TOKEN:
        await message.answer(t(lang, "recognition_off"), reply_markup=menu_keyboard(lang))
        return
    try:
        timeout = aiohttp.ClientTimeout(total=15, connect=4)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.audd.io/",
                data={"api_token": AUDD_API_TOKEN, "url": url, "return": "apple_music,spotify"},
            ) as resp:
                data = await resp.json()
        result = data.get("result")
        if not result:
            await message.answer(t(lang, "recognition_fail"), reply_markup=menu_keyboard(lang))
            return
        title = result.get("title", "Unknown")
        artist = result.get("artist", "Unknown")
        await message.answer(t(lang, "recognized", title=html.escape(title), artist=html.escape(artist)))
        tracks = await deezer_search(f"{title} {artist}")
        if tracks:
            await message.answer(t(lang, "found"), reply_markup=results_keyboard(tracks, lang))
        else:
            await message.answer(t(lang, "not_found"), reply_markup=menu_keyboard(lang))
    except Exception:
        log.exception("Audio recognition failed")
        await message.answer(t(lang, "recognition_fail"), reply_markup=menu_keyboard(lang))

@dp.message(F.audio)
async def return_user_audio(message: Message):
    lang = await get_lang(message.from_user.id)
    audio = message.audio
    if not audio:
        return
    if (audio.duration or 0) > MAX_AUDIO_SECONDS:
        await message.answer(t(lang, "too_long"))
        return
    # Reuse Telegram's file_id: no audio download, disk write, or server-side transcoding.
    await message.answer_audio(
        audio=audio.file_id,
        caption=t(lang, "sent"),
        title=audio.title or "Audio",
        performer=audio.performer or "Muzika user audio",
    )

@dp.message(F.video)
async def video_not_supported(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "audio_only"))

@dp.message()
async def fallback(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "welcome"), reply_markup=menu_keyboard(lang))

async def main():
    global db
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Add it as a Render secret.")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Add the Neon connection string as a Render secret.")
    db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, command_timeout=10)
    async with db.acquire() as conn:
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
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    global bot_username
    bot_username = me.username or "Muzika_agent"
    log.info("Muzika started as @%s", bot_username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
