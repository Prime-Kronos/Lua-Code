import asyncio, html, os, secrets
from pathlib import Path
from typing import List, Optional
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN = os.getenv("BOT_ADMIN_ID", "").strip()
API = "https://api.telegram.org/bot" + TOKEN
app = FastAPI(title="Amu Sazan Menu")
orders, notifications, pending = {}, {}, {}
offset, bot_task = 0, None

class Item(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=30)
    price: int = Field(ge=0, le=10000000)
class Order(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    customer_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=7, max_length=30)
    table: str = Field(min_length=1, max_length=30)
    payment: str
    items: List[Item] = Field(min_length=1, max_length=30)
    total: int = Field(ge=0, le=100000000)
    comment: Optional[str] = Field(default="", max_length=500)
class Review(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    name: str = Field(default="Гость", max_length=80)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=3, max_length=1000)
class Waiter(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    table: str = Field(min_length=1, max_length=30)
    message: Optional[str] = Field(default="", max_length=300)

def notify(sid, kind, message):
    if not sid: return
    arr = notifications.setdefault(sid, [])
    arr.append({"id": arr[-1]["id"] + 1 if arr else 1, "type": kind, "message": message})
    if len(arr) > 50: del arr[:-50]

async def tg(method, payload):
    if not TOKEN: raise RuntimeError("BOT_TOKEN is not configured")
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(API + "/" + method, json=payload)
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"): raise RuntimeError(data.get("description", "Telegram API error"))
    return data.get("result")

async def admin_send(message, keyboard=None):
    if not ADMIN: raise RuntimeError("BOT_ADMIN_ID is not configured")
    payload = {"chat_id": ADMIN, "text": message, "parse_mode": "HTML"}
    if keyboard: payload["reply_markup"] = keyboard
    return await tg("sendMessage", payload)

def fmt(n): return format(n, ",").replace(",", " ") + " сум"
def order_text(o):
    lines = ["🛎 <b>НОВЫЙ ЗАКАЗ — AMU SAZAN</b>", "Номер: <code>"+o["id"]+"</code>",
      "👤 "+html.escape(o["customer_name"]), "📞 "+html.escape(o["phone"]),
      "🪑 Стол: "+html.escape(o["table"]), "💳 Оплата: "+o["payment_label"], "", "🍽 <b>Состав:</b>"]
    for x in o["items"]: lines.append("• "+html.escape(x["name"])+" × "+str(x["quantity"])+" — "+fmt(x["price"]*x["quantity"]))
    lines += ["", "<b>Итого: "+fmt(o["total"])+"</b>"]
    if o.get("comment"): lines.append("📝 "+html.escape(o["comment"]))
    return "\n".join(lines)

async def callback(update):
    q = update.get("callback_query", {})
    chat = str(q.get("from", {}).get("id", ""))
    await tg("answerCallbackQuery", {"callback_query_id": q.get("id")})
    if not ADMIN or chat != ADMIN: return
    bits = q.get("data", "").split(":")
    if len(bits) != 2: return
    action, oid = bits
    if action == "waiter_done":
        await tg("sendMessage", {"chat_id": chat, "text": "Вызов официанта отмечен выполненным."})
        return
    o = orders.get(oid)
    if not o:
        await tg("sendMessage", {"chat_id": chat, "text": "Заказ не найден (возможно, сервер перезапускался)."})
        return
    if action == "reply":
        pending[chat] = oid
        await tg("sendMessage", {"chat_id": chat, "text": "✍️ Напишите одним сообщением ответ клиенту по заказу "+oid+"."})
    elif action in ("accept", "reject"):
        o["status"] = action
        msg = "Заказ "+oid+(" принят рестораном ✅" if action == "accept" else " отклонён рестораном.")
        notify(o["session_id"], "order_status", msg)
        await tg("sendMessage", {"chat_id": chat, "text": msg})

async def message(update):
    chat = str(update.get("chat", {}).get("id", ""))
    text = (update.get("text") or "").strip()
    if not chat or not text: return
    if text.startswith("/start") or text.startswith("/id"):
        if not ADMIN:
            answer = "🤖 Amu Sazan Menu Bot\nВаш Telegram ID: "+chat+"\nДобавьте его в BOT_ADMIN_ID в настройках сервера."
        elif chat == ADMIN:
            answer = "✅ Панель администратора активна.\nЗаказы, отзывы и вызовы официанта будут приходить сюда.\nИспользуйте кнопку «Ответить клиенту» под заказом."
        else: answer = "Бот работает. Ваш ID: "+chat+". Доступ к панели есть только у администратора."
        await tg("sendMessage", {"chat_id": chat, "text": answer})
        return
    if not ADMIN or chat != ADMIN: return
    oid = pending.pop(chat, None)
    if oid and oid in orders:
        notify(orders[oid]["session_id"], "admin_reply", "Ответ ресторана по заказу "+oid+": "+text)
        await tg("sendMessage", {"chat_id": chat, "text": "✅ Ответ отправлен на сайт клиенту."})

async def poll():
    global offset
    while True:
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                r = await client.get(API+"/getUpdates", params={"offset":offset,"timeout":25,"allowed_updates":'["message","callback_query"]'})
                data = r.json()
            if data.get("ok"):
                for u in data.get("result", []):
                    offset = max(offset, u["update_id"]+1)
                    try:
                        if "callback_query" in u: await callback(u)
                        elif "message" in u: await message(u["message"])
                    except Exception as exc: print("Telegram update error:", exc)
        except asyncio.CancelledError: raise
        except Exception as exc:
            print("Telegram polling error:", exc)
            await asyncio.sleep(5)

@app.on_event("startup")
async def start_bot():
    global bot_task
    if TOKEN: bot_task = asyncio.create_task(poll())
@app.on_event("shutdown")
async def stop_bot():
    if bot_task: bot_task.cancel()

@app.get("/api/health")
async def health():
    return {"ok":True,"service":"amu-sazan-menu","bot_token_configured":bool(TOKEN),"admin_configured":bool(ADMIN)}

@app.post("/api/orders")
async def new_order(req: Order):
    if req.payment not in ("cash","card"): raise HTTPException(400,"Выберите способ оплаты.")
    if sum(x.price*x.quantity for x in req.items) != req.total: raise HTTPException(400,"Сумма заказа не совпадает.")
    oid = "AS-"+secrets.token_hex(3).upper()
    o = req.model_dump()
    o.update({"id":oid,"status":"pending","payment_label":"Наличные" if req.payment=="cash" else "Картой у официанта"})
    orders[oid] = o
    keyboard = {"inline_keyboard":[[{"text":"✍️ Ответить клиенту","callback_data":"reply:"+oid}],
      [{"text":"✅ Принять заказ","callback_data":"accept:"+oid},{"text":"❌ Отклонить","callback_data":"reject:"+oid}]]}
    try: await admin_send(order_text(o), keyboard)
    except Exception as exc:
        orders.pop(oid,None)
        raise HTTPException(503,"Telegram не настроен: проверьте BOT_TOKEN и BOT_ADMIN_ID. "+str(exc))
    notify(req.session_id,"order_sent","Заказ "+oid+" отправлен ресторану. Ожидайте подтверждения.")
    return {"ok":True,"order_id":oid}

@app.post("/api/reviews")
async def new_review(req: Review):
    stars = "★"*req.rating+"☆"*(5-req.rating)
    msg = "⭐ <b>НОВЫЙ ОТЗЫВ — AMU SAZAN</b>\n"+stars+"\n👤 "+html.escape(req.name or "Гость")+"\n\n"+html.escape(req.text)
    try: await admin_send(msg)
    except Exception as exc: raise HTTPException(503,"Не удалось отправить отзыв в Telegram. "+str(exc))
    return {"ok":True}

@app.post("/api/waiter")
async def new_waiter(req: Waiter):
    msg = "🔔 <b>ВЫЗОВ ОФИЦИАНТА</b>\n🪑 Стол: <b>"+html.escape(req.table)+"</b>"
    if req.message: msg += "\n📝 "+html.escape(req.message)
    msg += "\n\nОтметьте вызов выполненным после обслуживания."
    try: await admin_send(msg,{"inline_keyboard":[[{"text":"✅ Вызов выполнен","callback_data":"waiter_done:"+secrets.token_hex(3)}]]})
    except Exception as exc: raise HTTPException(503,"Не удалось отправить вызов в Telegram. "+str(exc))
    notify(req.session_id,"waiter","Вызов официанта отправлен. Сотрудник скоро подойдёт.")
    return {"ok":True}

@app.get("/api/notifications")
async def get_notifications(session_id: str = Query(min_length=8,max_length=100), after: int = 0):
    return {"items":[x for x in notifications.get(session_id,[]) if x["id"]>after]}

@app.get("/")
async def home(): return FileResponse(STATIC/"index.html")
app.mount("/static",StaticFiles(directory=STATIC),name="static")
