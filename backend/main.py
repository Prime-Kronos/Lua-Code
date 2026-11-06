import os, sqlite3, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
DB=os.getenv("DATABASE_PATH","requests.db"); TOKEN=os.getenv("TELEGRAM_BOT_TOKEN",""); ADMIN=os.getenv("TELEGRAM_ADMIN_CHAT_ID",""); OFFSET=0; awaiting={}
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 with connect() as c: c.execute("CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT,floor TEXT,room TEXT,kind TEXT,comment TEXT,status TEXT DEFAULT 'new',reply TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
async def telegram(method,data):
 if not TOKEN:return None
 async with httpx.AsyncClient(timeout=35) as client:
  r=await client.post(f"https://api.telegram.org/bot{TOKEN}/{method}",json=data); r.raise_for_status(); return r.json()
async def alert_staff(row):
 if not TOKEN or not ADMIN:return
 names={"waiter":"🔔 Вызов официанта","room_service":"🍽 Заказ в номер","reception":"💬 Вопрос ресепшен"}
 msg=f"{names[row['kind']]}\n\n🏢 Этаж: {row['floor']}\n🚪 Комната: {row['room']}\n📝 Комментарий: {row['comment'] or '—'}\n🆔 Заявка: #{row['id']}"
 await telegram("sendMessage",{"chat_id":ADMIN,"text":msg,"reply_markup":{"inline_keyboard":[[{"text":"↩️ Ответить гостю","callback_data":f"reply:{row['id']}"}],[{"text":"✅ Принято","callback_data":f"ack:{row['id']}"}]]}})
async def bot_loop():
 global OFFSET
 while True:
  try:
   result=await telegram("getUpdates",{"offset":OFFSET,"timeout":25,"allowed_updates":["message","callback_query"]})
   for u in (result or {}).get("result",[]):
    OFFSET=u["update_id"]+1; cb=u.get("callback_query")
    if cb:
     chat=str(cb["message"]["chat"]["id"]); action=cb.get("data","")
     if chat!=str(ADMIN):
      await telegram("answerCallbackQuery",{"callback_query_id":cb["id"],"text":"Нет доступа"}); continue
     if action.startswith("reply:"):
      rid=action.split(":")[1]; awaiting[chat]=rid
      await telegram("answerCallbackQuery",{"callback_query_id":cb["id"],"text":"Введите ответ гостю следующим сообщением"})
      await telegram("sendMessage",{"chat_id":chat,"text":f"Напишите ответ для заявки #{rid}. Он появится на сайте."})
     elif action.startswith("ack:"):
      rid=int(action.split(":")[1])
      with connect() as c:c.execute("UPDATE requests SET status='processing' WHERE id=?",(rid,))
      await telegram("answerCallbackQuery",{"callback_query_id":cb["id"],"text":"Отмечено как принято"})
     continue
    m=u.get("message",{}); chat=str(m.get("chat",{}).get("id","")); text=m.get("text","")
    if chat==str(ADMIN) and chat in awaiting and text:
     rid=int(awaiting.pop(chat))
     with connect() as c:c.execute("UPDATE requests SET reply=?,status='answered' WHERE id=?",(text,rid))
     await telegram("sendMessage",{"chat_id":chat,"text":f"✅ Ответ гостю отправлен. Заявка #{rid}."})
  except Exception as e: print("Telegram bot error:",e); await asyncio.sleep(4)
@asynccontextmanager
async def lifespan(app):
 init_db(); task=asyncio.create_task(bot_loop()) if TOKEN and ADMIN else None
 yield
 if task:task.cancel()
app=FastAPI(title="ADA Hotel Guest Service API",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","*").split(","),allow_methods=["*"],allow_headers=["*"])
class RequestIn(BaseModel):
 floor:str=Field(min_length=1,max_length=12); room:str=Field(min_length=1,max_length=12); kind:str=Field(pattern="^(waiter|room_service|reception)$"); comment:str=Field(default="",max_length=1000)
@app.get("/")
def home():return {"ok":True,"service":"ADA Hotel Guest Service API"}
@app.get("/health")
def health():return {"ok":True,"telegram_configured":bool(TOKEN and ADMIN)}
@app.post("/api/requests")
async def create(data:RequestIn):
 with connect() as c:
  cur=c.execute("INSERT INTO requests(floor,room,kind,comment) VALUES(?,?,?,?)",(data.floor,data.room,data.kind,data.comment)); rid=cur.lastrowid; row=dict(c.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone())
 try:await alert_staff(row)
 except Exception as e:print("Telegram notification failed:",e)
 return {"id":rid,"status":"new"}
@app.get("/api/requests/{rid}")
def read(rid:int):
 with connect() as c:row=c.execute("SELECT id,status,reply FROM requests WHERE id=?",(rid,)).fetchone()
 if not row:raise HTTPException(404,"Заявка не найдена")
 return dict(row)